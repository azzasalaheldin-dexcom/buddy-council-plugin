---
description: Run automated tests for TestRail cases in your automation framework — find the test linked to each case, check the machine and device are ready, run it, and report the result.
---

# /bc:run-automation — Run Automated Tests for TestRail Cases

Run the automated test that implements a TestRail case. The test must already exist in the framework (write it
with `/bc:automate`). Like `/bc:automate`, nothing about the framework's location is hardcoded, so this works on
any laptop.

## Usage

```
/bc:run-automation https://<instance>.testrail.io/index.php?/cases/view/2926799
/bc:run-automation C2926799                         # also 2926799, TC-2926799
/bc:run-automation C2926799 C2926800                # several cases, one run
/bc:run-automation C2926799 --platform iOS          # default: automation.default_platform
/bc:run-automation C2926799 --repo ~/code/ApolloAutomation
```

## Arguments: $ARGUMENTS

- **Cases** (required): one or more TestRail case URLs, `C<id>`, `TC-<id>`, or bare numbers.
- **Flags**:
  - `--platform <name>`: platform to run on (e.g. `Android`, `iOS`). Default: `automation.default_platform`, then the last run's platform; ask only if none is known.
  - `--repo <path>`: framework checkout to use. Validated and recorded as `automation.framework_root`.

## Execution

**Ask as little as possible.** Every answer the user has already given lives in `.buddy-council/sources.json`
(`automation.default_platform`, `automation.run_memory`, `automation.device_farm.auto_start`) — read it first
and never ask a question it already answers. Keep shell commands to the plain read-only forms the skills
show (`grep`, `cat`, `git -C … status`, `adb devices`, `curl -s <farm url>/…`, `sleep N`, `./gradlew …`);
those are auto-approved by the plugin's hooks. Python heredocs, `for` loops, and redirects to files are not,
and each one costs the user a permission prompt.

1. Verify `.buddy-council/sources.json` exists. If not: tell the user to run `/bc:setup` first.
2. Parse every case argument into a numeric id (for a URL, the digits after `cases/view/`).
3. Resolve the framework with `${CLAUDE_PLUGIN_ROOT}/skills/resolve-automation-framework/SKILL.md`, including
   its **run** readiness checks. Any failed check → print the `Readiness:` lines with their fixes and stop.
4. Find each case's test: search the framework's test sources for the provider profile's `linkage` pattern
   with the id (e.g. `TC#<id>_`), then the bare id as a whole word inside a test annotation.
   - **One match** → record its fully qualified class and method.
   - **Several matches** → use `automation.run_memory.tests["<id>"]` if it is one of them; otherwise list them,
     ask which to run, and remember the answer there.
   - **None** → `C<id>: no automated test found — write it with /bc:automate C<id>`. Run the remaining cases;
     stop if none are left.
   Print `Found: C<id> → <relative/path/TestClass.java>#<method>` for each.
5. Note any matched test still carrying the provider's placeholder token (e.g. `BC_TODO_LOCATOR`): it will
   run, but is expected to fail at that step.
6. **Device farm gate** — before anything runs, follow
   `${CLAUDE_PLUGIN_ROOT}/skills/ensure-device-farm/SKILL.md`: start the farm if it isn't up (after one
   confirmation), then confirm the mobile device connected to this machine appears on `<farm url>/nodes`
   with status **FREE** (green ✅). Not listed or ❌ IN_USE → stop and say why; nothing runs.
   ```
   Device farm: up at http://localhost:7890 (already running)
   Device: ✅ FREE Pixel_7 (2A231FDH200CYX) ANDROID 14 REAL
   ```
7. Follow `${CLAUDE_PLUGIN_ROOT}/skills/run-automated-test/SKILL.md` with all found tests in **one** run
   (one generated suite, one Gradle invocation).
8. Report one line per case, then the artifacts. Then save what this run settled to
   `automation.run_memory` (merge, never drop keys): `{platform, device_id, tests: {"<id>": "<fqcn>#<method>"}}`.
   If `automation.default_platform` was empty, set it to the platform used.

```
C2926799  PASSED   12m04s
C2926800  FAILED   locator — NoSuchElementException: …  (MonitorPage.java:88)
Artifacts: allure-results/ · test-output/ · logs/
```

## What This Command Does NOT Do

- Does NOT write or change test code. A failure is reported with a suggested fix; editing is up to you
  (or re-run `/bc:automate C<id>` to update the test).
- Does NOT report results back to TestRail.
- Does NOT edit the framework's build files — single tests run through a Gradle init script shipped with the plugin.
- Does NOT create machine-specific config (app paths, SDK paths, device ids) — it tells you what is missing.
- Does NOT stop the device farm, and never frees a busy device without your explicit yes (`/freeAll` is never called).
