---
description: Internal (used by /bc:run-automation) — Run one automated test in the automation framework through its provider, without editing the framework's build files, and summarise the result.
user-invocable: false
---

# Run Automated Test — Skill

Execute one or more automated tests in a single run and report PASSED / FAILED / SKIPPED per case with the reason.

## Input

- `{root, provider_file, profile, readiness}` from `resolve-automation-framework`
- `tests`: `[{case_id, test_class (fully qualified), method_name}]`
- `platform` (`--platform`, else `automation.default_platform`, else ask)

## Procedure

### Step 1: Run readiness

If any **run** readiness check failed, print them with their fixes and return `SKIPPED (not ready: …)`.
Do not create machine-specific config files (app paths, SDK paths, device ids) for the user — those differ
per laptop and are gitignored on purpose. Show what is missing and where it goes.

### Step 2: Device farm and device check

When `automation.device_farm` is configured, follow `${CLAUDE_PLUGIN_ROOT}/skills/ensure-device-farm/SKILL.md`:
it starts the farm if needed and confirms this machine's device is listed on the nodes page with status FREE
(green ✅). Any stop reason → return `SKIPPED (<reason>)` for every test; do not start Gradle.

Without a device farm, fall back to the provider's **Devices** section for the platform. No
device/emulator/simulator available → `SKIPPED (no <platform> device connected)`.

### Step 3: Execute

Follow the provider's **Run** section. Run the command from the framework root in the foreground, so the
output returns when the run ends. Use the wrapper for the current OS (`./gradlew` on macOS/Linux,
`gradlew.bat` on Windows).

### Step 4: Collect the result

Follow the provider's **Results** section and report one line per case:

```
C<id>  PASSED  <duration>
C<id>  FAILED  <class> — <exception type>: <first message line>  (<first frame inside the framework's own packages>)
C<id>  SKIPPED <reason>
Artifacts: <results dir> · <report dir> · <logs dir>
```

On failure, classify it so the user knows what to do next:

| Class | Signal | Meaning |
|---|---|---|
| **placeholder** | failure is in a method containing the provider's placeholder token | expected — finish the TODO locator |
| **locator** | element not found / timeout waiting for an element | locator or screen-flow mismatch |
| **assertion** | assertion error | app behaviour differs from the TestRail expected result — possibly a real bug |
| **environment** | session not created, no device, connection refused, app not found | setup, not the test |

Do not retry a failed run automatically, and do not edit the test to make it pass. Offer the fix as a
suggestion; the user decides.
