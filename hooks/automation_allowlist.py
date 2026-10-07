#!/usr/bin/env python3
# Decides whether a shell command from /bc:automate or /bc:run-automation is safe to auto-approve.
# Prints "allow" when every chained segment is on the allowlist; prints nothing otherwise (normal prompt).
import os
import re
import shlex
import sys

PLUGIN_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
INIT_SCRIPT = os.path.join(PLUGIN_ROOT, "providers", "testng-gradle", "bc-run.init.gradle")

JAVA_HOME_SUB = re.compile(r"\$\(/usr/libexec/java_home(?:\s+-[vV](?:\s+[0-9.]+)?)?\)")
DEVNULL = re.compile(r"(?:^|(?<=\s))(?:[12]?>>?|&>)\s*/dev/null|(?:^|(?<=\s))2>&1")
OPERATORS = {"&&", "||", ";", "|"}
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LOCAL_URL = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?(/[^\s]*)?$")
SUITE_FILE = re.compile(r"^(.*/)?build/bc/run-[A-Za-z0-9_.-]+\.xml$")
# `$(date [-u] [+FORMAT])` only reads the clock; `date -s`/other flags never match.
DATE_SUB = re.compile(r"""\$\(date(?:\s+-u)?(?:\s+(?:\+[\w%:.-]+|'\+[\w%:. -]+'|"\+[\w%:. -]+"))?\s*\)""")
DATE_VAR = re.compile(r"(?:^|(?<=[\s;&|]))([A-Za-z_][A-Za-z0-9_]*)=" + DATE_SUB.pattern)
TIMESTAMP = "20000101T000000Z"
# `cat > <file> <<'DELIM' … DELIM` with a quoted delimiter: the body is literal text, nothing expands.
HEREDOC_WRITE = re.compile(r"cat\s*>\s*(\"[^\"]+\"|'[^']+'|\S+)\s*<<-?\s*(['\"])(\w+)\2[^\n]*\n.*?\n\3[ \t]*(?=\n|$)", re.S)

READ_ONLY = {"cat", "head", "tail", "ls", "wc", "cut", "tr", "echo", "printf", "pwd", "true", "basename",
             "dirname", "realpath", "stat", "file", "which", "seq", "lsof", "grep", "egrep", "fgrep",
             "jq", "test", "["}
GIT_READ = {"status", "rev-parse", "log", "diff", "show", "ls-files", "grep", "branch", "remote", "config"}
GRADLE_TASKS = {"compileTestJava", "bcRunSuite", "tasks"}
GRADLE_FLAGS = {"-q", "--quiet", "--offline", "--console=plain", "--stacktrace", "-i", "--info"}
CURL_ARG_OPTS = {"-m", "--max-time", "--connect-timeout", "-w", "--write-out", "-H", "--header", "-o", "--output"}
CURL_FLAGS = {"--silent", "--show-error", "--fail", "--include", "--head", "--location"}
SED_SCRIPT = re.compile(r"^(\d+|\$|/[^/]*/)(,(\d+|\$|/[^/]*/))?p$")
SENSITIVE = re.compile(r"secrets\.json|atlassian\.env|gradle\.properties|\.env\b|\.netrc|\.npmrc|\.ssh/|"
                       r"id_rsa|id_ed25519|credentials|\.pem\b|\.p12\b|keychain", re.I)


def segments(command):
    for name in set(DATE_VAR.findall(command)):
        command = re.sub(r"\$(\{%s\}|%s(?![A-Za-z0-9_]))" % (name, name), TIMESTAMP, command)
    command = DATE_SUB.sub(TIMESTAMP, command)
    command = HEREDOC_WRITE.sub(lambda m: "bc_write_suite " + m.group(1), command)
    command = JAVA_HOME_SUB.sub("/jdk", command)
    command = DEVNULL.sub(" ", command)
    if any(s in command for s in ("`", "$(", "<(", ">(")):
        return None
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError:
        return None
    segs, cur = [], []
    for tok in tokens:
        if tok in OPERATORS:
            segs.append(cur)
            cur = []
        elif tok.startswith("#") or (tok and set(tok) <= set("();<>|&")):
            return None
        else:
            cur.append(tok)
    segs.append(cur)
    return [s for s in segs if s]


def is_plugin_init_script(path):
    for var in ("${CLAUDE_PLUGIN_ROOT}", "$CLAUDE_PLUGIN_ROOT", "${COPILOT_PLUGIN_ROOT}", "$COPILOT_PLUGIN_ROOT"):
        if path.startswith(var):
            path = PLUGIN_ROOT + path[len(var):]
    path = os.path.realpath(os.path.expanduser(path))
    if path == INIT_SCRIPT:
        return True
    # Another copy of the plugin (installed vs. dev clone) is fine only if the script is byte-identical.
    try:
        with open(path, "rb") as a, open(INIT_SCRIPT, "rb") as b:
            return path.endswith("/providers/testng-gradle/bc-run.init.gradle") and a.read() == b.read()
    except OSError:
        return False


def ok_sed(args):
    if "-n" not in args or any(a.startswith("-i") or a == "--in-place" for a in args):
        return False
    if any(a.startswith("-") and a not in ("-n", "-E", "-r") for a in args):
        return False
    operands = [a for a in args if not a.startswith("-")]
    return bool(operands) and bool(SED_SCRIPT.match(operands[0]))


def ok_git(args):
    while args[:1] in (["-C"], ["--no-pager"]):
        args = args[2:] if args[0] == "-C" else args[1:]
    if not args or args[0] not in GIT_READ:
        return False
    sub, rest = args[0], args[1:]
    if any(a.startswith("--output") or a == "--ext-diff" for a in rest):
        return False
    if sub == "branch":
        return all(a in ("--show-current", "-a", "--list", "-v") for a in rest)
    if sub == "remote":
        return rest[:1] in ([], ["-v"], ["get-url"])
    if sub == "config":
        return rest[:1] == ["--get"]
    return True


def ok_adb(args):
    if args[:1] == ["-s"]:
        args = args[2:]
    return args[:1] in (["devices"], ["get-state"], ["get-serialno"], ["version"]) or args[:2] == ["shell", "getprop"]


def ok_curl(args):
    urls, i = [], 0
    while i < len(args):
        a = args[i]
        if a in CURL_ARG_OPTS:
            if i + 1 >= len(args) or (a in ("-o", "--output") and args[i + 1] != "/dev/null"):
                return False
            i += 2
            continue
        if a in CURL_FLAGS or re.match(r"^-[sSiILf]+$", a):
            i += 1
            continue
        if a.startswith("-"):
            return False
        urls.append(a)
        i += 1
    # /free and /freeAll release devices other runs may hold, so they always prompt.
    return bool(urls) and all(LOCAL_URL.match(u) and "/free" not in u for u in urls)


def ok_gradle(args):
    tasks, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--init-script":
            if i + 1 >= len(args) or not is_plugin_init_script(args[i + 1]):
                return False
            i += 2
            continue
        if a.startswith("-P") or a in GRADLE_FLAGS:
            i += 1
            continue
        if a.startswith("-"):
            return False
        tasks.append(a)
        i += 1
    return bool(tasks) and set(tasks) <= GRADLE_TASKS


def ok_segment(tokens):
    while tokens and ENV_ASSIGN.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return True
    head, args = os.path.basename(tokens[0]), tokens[1:]
    # Credential files only for presence checks: grep -q/-c/-l never prints the matched values.
    if any(SENSITIVE.search(a) for a in args):
        return head == "grep" and any(a in ("-q", "-c", "-l", "-qE", "-cE", "-Ec", "-Eq") for a in args)
    if head == "cd":
        return len(args) <= 1
    if head == "bc_write_suite":
        return len(args) == 1 and bool(SUITE_FILE.match(args[0]))
    if head == "mkdir":
        dirs = [a for a in args if a != "-p"]
        return bool(dirs) and all(re.match(r"^(.*/)?build/bc/?$", d) for d in dirs)
    if head == "xargs":
        while args and args[0] in ("-0", "-r", "--no-run-if-empty"):
            args = args[1:]
        return bool(args) and os.path.basename(args[0]) in READ_ONLY and ok_segment(args)
    if head == "export":
        return all(ENV_ASSIGN.match(a) for a in args)
    if head in READ_ONLY:
        return True
    if head == "sort":
        return not any(a.startswith("-o") or a.startswith("--output") for a in args)
    if head == "uniq":
        return len([a for a in args if not a.startswith("-")]) <= 1
    if head == "sed":
        return ok_sed(args)
    if head == "find":
        return not any(a.startswith(("-exec", "-ok", "-fprint", "-fls", "-delete")) for a in args)
    if head == "sleep":
        return len(args) == 1 and args[0].isdigit() and int(args[0]) <= 60
    if head == "git":
        return ok_git(args)
    if head == "adb":
        return ok_adb(args)
    if head == "idevice_id":
        return args in ([], ["-l"])
    if head == "ideviceinfo":
        return True
    if head == "xcrun":
        return args[:2] == ["simctl", "list"] or args[:3] == ["xctrace", "list", "devices"]
    if head in ("java", "node", "appium"):
        return args in (["-version"], ["--version"], ["-v"])
    if head == "java_home":
        return all(re.match(r"^(-[vV]|[0-9.]+)$", a) for a in args)
    if head == "curl":
        return ok_curl(args)
    if head in ("gradlew", "gradlew.bat"):
        return ok_gradle(args)
    return False


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    segs = segments(command)
    if segs and all(ok_segment(s) for s in segs):
        print("allow")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
