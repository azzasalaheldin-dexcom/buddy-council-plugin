---
description: Automate a TestRail test case — fetch it by link or ID and write the test script in your automation framework following that framework's own conventions, then compile it. Run it with /bc:run-automation.
---

# /bc:automate — Write a TestRail Case as an Automated Test

Take one TestRail case and turn it into an automated test script in the team's automation framework: fetch the
case, locate the framework on this machine, reuse the framework's existing page objects and step methods, write
the test, and compile it. **This command does not run the test** — use `/bc:run-automation` for that.

The workflow is **machine-independent**. Nothing about the framework's location is hardcoded — it is resolved
on every run (see "Locating the framework"), so the same command works on any laptop that has the framework
cloned, or offers to clone it when it doesn't.

## Usage

```
/bc:automate https://<instance>.testrail.io/index.php?/cases/view/2926799   # by link
/bc:automate C2926799                                                       # by case ID (also 2926799, TC-2926799)
/bc:automate C2926799 --repo ~/code/ApolloAutomation                        # use/record a framework checkout
/bc:automate C2926799 --dry-run                                             # plan + diff only, write nothing
```

## Arguments: $ARGUMENTS

- **Case** (required): a TestRail case URL (`…/index.php?/cases/view/<id>`), `C<id>`, `TC-<id>`, or a bare number.
- **Flags**:
  - `--repo <path>`: framework checkout to use. Validated and recorded as `automation.framework_root`.
  - `--dry-run`: fetch, map, and show the full plan and diff; write no files and compile nothing.

## Safety Posture

1. **Files in the framework repo are written only after one confirmation** of the plan and diff. `--dry-run` writes nothing.
2. **Never commit or push.** The agent may create a local branch (after asking); committing and pushing are left to the user, with the exact commands printed.
3. **Never invent locators.** A step with no existing page-object method gets a clearly marked placeholder, and the test is tagged with the framework's "in progress" marker so it cannot break a suite run.

## Execution

1. Verify `.buddy-council/sources.json` exists and has a `test_cases` block. If not: tell the user to run `/bc:setup` first.
2. Parse the case argument into a numeric case id. For a URL, the id is the digits after `cases/view/`. If the URL's host differs from the host of `test_cases.base_url`, stop: the TestRail MCP server is bound to the configured instance and cannot read another one.
3. Follow `${CLAUDE_PLUGIN_ROOT}/agents/automation-agent.agent.md`, passing the case id, the original link, and the flags.

## Locating the framework

Resolved fresh on every run by `${CLAUDE_PLUGIN_ROOT}/skills/resolve-automation-framework/SKILL.md`, first match wins:

1. `--repo <path>`
2. the `BC_AUTOMATION_ROOT` environment variable
3. `automation.framework_root` in `.buddy-council/sources.json` — a per-machine cache, used only if the directory still exists and its `origin` remote matches `automation.repo_url`
4. the current working directory, if its `origin` remote matches `automation.repo_url`
5. a shallow scan of common clone locations (`~/Documents/GitHub`, `~/GitHub`, `~/src`, `~/code`, `~/repos`, `~/workspace`, `~/projects`) for a checkout whose `origin` matches
6. offer to `git clone automation.repo_url` into a directory the user picks

## What This Command Does NOT Do

- Does NOT run the test — that is `/bc:run-automation`.
- Does NOT create or edit TestRail cases — the case is read-only input.
- Does NOT commit, push, or open pull requests.
