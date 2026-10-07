---
description: Internal (used by /bc:run-automation) — Make sure the device farm is running (start it if not), then confirm the mobile device connected to this machine is listed on the farm's nodes page and FREE (green ✅) before any test runs.
user-invocable: false
---

# Ensure Device Farm — Skill

Tests reserve devices through the device farm, so a run is only safe to start when the farm is up **and** the
device plugged into this machine is registered there and free. This skill gets to that state or stops with
the reason.

## Input

- `platform` (`Android` / `iOS`) for the run
- `.buddy-council/sources.json` → `automation.device_farm` (absent → skip this skill with
  `Device farm: not configured — skipped`)
- Optional target device id: `executionDevice` from the framework's run properties file, when set

## Configuration

`automation.device_farm`:

| Field | Default | Purpose |
|---|---|---|
| `url` | `http://localhost:7890` | Farm base URL. `GET /` returns 200 when up; `GET /nodes` lists devices |
| `repo_url` | — | The farm's git remote, used to find its checkout on this machine (e.g. `https://github.com/<org>/TheDeviceFarm`) |
| `root` | — | Per-machine cache of the checkout path. Re-validated every run, like `framework_root` |
| `start_command` | `./startup-local-async.sh` | Run from `root`; must return immediately and leave the farm running in the background |
| `log_file` | `localLogFile.txt` | Relative to `root`; tailed when startup fails |
| `start_timeout_s` | `240` | How long to wait for `GET /` → 200 after starting (first start compiles the farm) |
| `device_wait_s` | `60` | How long to wait for the device to appear (the farm re-scans every ~15 s) |
| `auto_start` | `false` | Start the farm without asking. Set to `true` when the user answers **always** |

## Procedure

### Step 1: Is the farm up?

```sh
curl -s -m 5 -o /dev/null -w '%{http_code}' "<url>/"
```

`200` → `Device farm: up at <url> (already running)`, go to Step 3. Anything else → Step 2.

### Step 2: Start it

1. Locate the checkout with the same resolution order as
   `${CLAUDE_PLUGIN_ROOT}/skills/resolve-automation-framework/SKILL.md` Step 2, using `device_farm.repo_url`
   and `device_farm.root` (no `--repo`; env var `BC_DEVICE_FARM_ROOT`). Record the found path in
   `device_farm.root`. Not found → ask to clone, exactly as that skill does.
2. If `device_farm.auto_start` is `true`, start without asking. Otherwise ask once: *"The device farm isn't
   running. Start it from `<root>`? (yes / always / no)"*. On **always**, set `device_farm.auto_start: true`
   in `sources.json` so future runs start it silently.
3. From `root`, run `start_command` (it backgrounds itself; the farm keeps running after the test run, so
   later runs reuse it). The farm picks its own JDK — do **not** pass the framework's `JAVA_HOME`.
4. Wait for it, bounded, with separate short polls (each one is auto-approved — a shell loop is not):

   ```sh
   sleep 15 && curl -s -m 3 -o /dev/null -w '%{http_code}' "<url>/"
   ```

   Repeat until `200`, at most `start_timeout_s / 15` times.

   Still not `200` → STOP with `Device farm: failed to start within <n>s` and the last 30 lines of `log_file`.
   Never kill or restart a farm process — another user's run may own it.

Print `Device farm: started from <root> → <url>`.

### Step 3: Identify the device connected to this machine

| Platform | Command | Device ids |
|---|---|---|
| Android | `adb devices` | serials in state `device` (`unauthorized` → tell the user to accept the USB-debugging prompt on the phone) |
| iOS | `idevice_id -l`, then `xcrun simctl list devices booted` | UDIDs |

If `executionDevice` is set, that is the target and it must be among these ids. Otherwise, if
`automation.run_memory.device_id` is among them, prefer it. If several ids still match, use all of them as
candidates (any free one will do) — don't ask. None → STOP:
`Device: no <platform> device connected to this machine`.

### Step 4: Check the device on the nodes page

```sh
curl -s -m 5 "<url>/nodes" | grep -oE 'id: "[^"]+" platform: [A-Z]+ name: "[^"]*" osVersion: "[^"]*" type: [A-Z]+ status: [A-Z_]+'
```

Each line is one device: `id`, `platform`, `name`, `osVersion`, `type` (`REAL`/`VIRTUAL`), `status`.
`status: FREE` is what the page shows as the green ✅; `IN_USE` is the red ❌. (🟢/🔵 only mark
Android/iOS, not availability.) Transmitter lines have a different shape and are ignored by this pattern.

Match a candidate when the farm's `id` equals the local id, or starts with `<local id>.` (the farm suffixes
emulator ids with the node address, e.g. `emulator-5554.192.168.1.3`). Compare `platform` case-insensitively.

| Result | Action |
|---|---|
| Listed, `status: FREE` | `Device: ✅ FREE <name> (<id>) <platform> <osVersion> <type>` → proceed |
| Not listed | `curl -s <url>/updateDevices` once to force a re-scan, then poll with `sleep 5 && curl -s -m 5 "<url>/nodes"` up to `device_wait_s`. Still missing → STOP: `Device: <id> is connected but not registered on the device farm` and the last 30 lines of `log_file` if known |
| Listed, `status: IN_USE` | STOP: `Device: ❌ IN_USE <name> (<id>) — busy with another run`. If the user says the lock is stale (e.g. a crashed run), offer `GET <url>/free/<id>` and call it only after an explicit yes. **Never** call `/freeAll` |

## Output

`{ farm_url, started: bool, device: {id, name, platform, osVersion, type} }` — or a stop reason.
