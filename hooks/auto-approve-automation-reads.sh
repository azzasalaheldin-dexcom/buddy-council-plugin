#!/bin/bash
# PreToolUse hook for read-only file tools (Claude Code Read/Grep/Glob, Copilot view/grep/glob):
# auto-approve reads inside the plugin, the project, and the automation checkouts recorded in
# .buddy-council/sources.json (automation.framework_root, automation.device_farm.root).
# Credential files always fall through to the normal prompt. No `set -e`: a non-zero exit is DENY on Copilot.

INPUT=$(cat)
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"

VERDICT=$(BC_INPUT="$INPUT" BC_PLUGIN_ROOT="$PLUGIN_ROOT" python3 - <<'PY' 2>/dev/null
import json, os, re

SENSITIVE = re.compile(r"secrets\.json|atlassian\.env|gradle\.properties|\.env$|\.netrc|\.npmrc|/\.ssh/|"
                       r"id_rsa|id_ed25519|credentials|\.pem$|\.p12$|\.mcp\.json$|mcp-config\.json$", re.I)

d = json.loads(os.environ["BC_INPUT"])
ti = d.get("tool_input")
if ti is None:
    ta = d.get("toolArgs")
    ti = json.loads(ta) if isinstance(ta, str) else (ta or {})
path = ti.get("file_path") or ti.get("path") or ti.get("directory") or ""
if not path:
    raise SystemExit

project = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("COPILOT_PROJECT_DIR") or d.get("cwd") or ""
roots = [os.environ["BC_PLUGIN_ROOT"], project]
try:
    with open(os.path.join(project, ".buddy-council", "sources.json")) as f:
        automation = json.load(f).get("automation") or {}
    roots += [automation.get("framework_root"), (automation.get("device_farm") or {}).get("root")]
except Exception:
    pass

real = os.path.realpath(os.path.expanduser(path if os.path.isabs(path) else os.path.join(project, path)))
if SENSITIVE.search(real):
    raise SystemExit
for root in filter(None, roots):
    root = os.path.realpath(os.path.expanduser(root))
    if real == root or real.startswith(root + os.sep):
        print("allow")
        break
PY
)

if [ "$VERDICT" = "allow" ]; then
  printf '{"permissionDecision":"allow","permissionDecisionReason":"%s","hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"%s"}}\n' \
    "bc: read inside a bc-managed checkout" "bc: read inside a bc-managed checkout"
fi
exit 0
