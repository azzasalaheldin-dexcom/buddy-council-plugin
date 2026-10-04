---
description: Internal (used by /bc:automate and /bc:run-automation) — Locate the automation framework checkout on this machine without hardcoded paths, detect which framework provider applies, and verify the checkout is ready to compile and run.
user-invocable: false
---

# Resolve Automation Framework — Skill

Find the team's automation framework on the current machine and decide which provider file describes it.
Paths are **discovered, never assumed** — this is what lets `/bc:automate` run on any laptop.

## Input

- `--repo <path>` from the command, if given
- `.buddy-council/sources.json` `automation` block (may be absent)

## Configuration

`.buddy-council/sources.json` → `automation`:

| Field | Purpose |
|-------|---------|
| `repo_url` | The framework's git remote (e.g. `https://github.com/<org>/<repo>`). Shared, safe to keep in config. Used to recognise a checkout regardless of where it was cloned. |
| `framework_root` | Absolute path of the checkout **on this machine**. A cache, like `plugin_root` — re-validated every run, repaired silently when stale. |
| `provider` | `auto` or a provider name (e.g. `testng-gradle`). |
| `default_platform` | Platform used when `--platform` is not given. |
| `branch_prefix` | Prefix for the optional work branch. Default `automation/`. |

## Procedure

### Step 1: Normalise remotes for comparison

Compare remotes by `host/owner/repo`, lower-cased, ignoring scheme, `git@host:` vs `https://host/`, a trailing
`.git`, and a trailing `/`. `git@github.com:Org/Repo.git` and `https://github.com/org/repo` match.

### Step 2: Resolve the root — first match wins

1. `--repo <path>` — expand `~`, resolve to an absolute path, require it to exist.
2. `$BC_AUTOMATION_ROOT`, if set and the directory exists.
3. `automation.framework_root`, if the directory exists **and** (`repo_url` is unset **or** its `origin` matches).
4. The current working directory, if its `origin` (`git -C . remote get-url origin`) matches `repo_url`.
5. Scan these parents, **one level deep only**, for a directory whose `origin` matches `repo_url`:
   `~/Documents/GitHub`, `~/GitHub`, `~/src`, `~/code`, `~/repos`, `~/workspace`, `~/projects`, `~/dev`.
   Skip parents that don't exist. Don't recurse further — this must stay fast.
6. Nothing found:
   - `repo_url` known → ask: *"Clone `<repo_url>` into `<suggested parent>/<repo>`, or give the path of an
     existing checkout?"* Suggest the first existing parent from the step-5 list. Clone only after a yes
     (`git clone <repo_url> <dir>`); a clone failing on auth means the user needs repo access — say so.
   - `repo_url` unknown → ask for the framework's repo URL or local path.

When the root came from steps 1, 2, 4, 5, or 6, read its `origin` and fill `repo_url` if it was empty.

### Step 3: Detect the provider

If `automation.provider` is set and not `auto`, use it. Otherwise probe the root:

| Markers | Provider file |
|---------|---------------|
| `build.gradle`/`build.gradle.kts` **and** (`useTestNG` in any `*.gradle` **or** `org.testng` in dependencies) | `${CLAUDE_PLUGIN_ROOT}/providers/testng-gradle/framework.md` |

No match → STOP and report the markers that were found: "No automation provider supports this framework yet
(found: …). Add one under `providers/<name>/framework.md`."

### Step 4: Build the profile

Follow the provider file's **Profile** section. The profile is computed from the checkout every run — it is
cheap, and caching it would go stale on every pull.

### Step 5: Readiness

Follow the provider file's **Readiness** section. Print one line per check:

```
Readiness: framework → <root> (testng-gradle, branch <branch>, HEAD <sha>)
Readiness: JDK → 11.0.22
Readiness: execution.properties → missing (gitignored — create it before running)
```

Split the checks into **build** checks (needed to compile) and **run** checks (needed only to execute). A
failed build check stops both commands. Run checks are evaluated only for `/bc:run-automation`, where a
failure stops the run and is reported with the fix.

### Step 6: Persist

If `framework_root`, `repo_url`, or `provider` changed, update `.buddy-council/sources.json` (merge — never
drop other keys). Report it in one line: `Config: automation.framework_root → <root>`.

## Output

`{ root, provider, provider_file, profile, readiness: { build_ok, run_ok, checks[] } }`
