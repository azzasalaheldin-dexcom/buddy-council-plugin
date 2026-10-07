---
description: Internal (used by /bc:automate) — Map a TestRail case's steps onto the automation framework's existing page objects and step methods, then generate the test (and only the missing page-object methods) following the framework's own conventions.
user-invocable: false
---

# Implement Automated Test — Skill

Write the automated test for one TestRail case so it reads like the framework's authors wrote it. Reuse
first; add new code only where nothing existing fits; never invent what you cannot verify.

## Input

- The case: `id`, `title`, section path, preconditions, steps `[{content, expected}]`, `refs`
- `{root, profile, provider_file}` from `resolve-automation-framework`
- `existing_test` — set when the agent is updating a test found by the duplicate guard

## Procedure

### Step 1: Normalise the case into steps

- Prefer `custom_steps_separated` (`[{content, expected}]`).
- Text templates: split `custom_steps` on numbered lines, pair with `custom_expected` by number when it is
  numbered the same way; otherwise keep the expected text as one final verification step.
- Preconditions become setup steps, in order, before step 1.
- Strip TestRail markup (`**`, `![](…)`, HTML) but keep literal values — names, numbers, units, thresholds.
  Literal values become test data (Step 4), not hardcoded inside page objects.

### Step 2: Pick the target location

Using the provider's **Placement** rules:

1. Find existing tests in the same feature: match the section path's last segments, then the title's key
   nouns, against test package/class names.
2. Prefer **adding a method to an existing test class for the same feature** when that class has the setup
   this case needs. Otherwise create a new class in that feature's package.
3. Pick one existing test in that area as the **reference test** — the closest match by title and setup.
   Copy its class-level structure (base class, fields, annotations, imports style) rather than inventing one.

### Step 3: Build the step vocabulary

Bounded search — at most 200 candidate files, 50 full reads:

- From the provider's **Vocabulary** locations, collect public methods of page objects, shared-step classes,
  and helpers: name, parameters, return type, and any step/description annotation text.
- For each case step, extract 2–4 key terms (screen name, control, action verb) and rank methods by term
  overlap with method names and step-annotation text.
- Read the reference test fully — its call chains are the best evidence of how methods compose.

### Step 4: Map every step

For each step decide exactly one of:

| Decision | When | Output |
|---|---|---|
| **reuse** | One existing method (or a chain the reference test already uses) performs it | the call |
| **compose** | A short sequence of existing methods performs it | the calls |
| **assert** | The step's *expected* result is checkable via an existing getter/verify method | the assertion in the provider's style |
| **new** | Nothing fits | a new method on the page object for that screen, with a placeholder locator |

Rules for **new**:
- Add it to the page object that owns that screen; only create a new page object if no existing one covers it.
- Use the provider's locator annotation shape, but mark the locator value with the provider's placeholder
  token and a `TODO(bc): verify locator for C<id> step <n>` comment. Never guess accessibility ids or xpaths.
- Mark the test with the provider's **in-progress marker** so suite runs exclude it.

Test data (names, values) from the case goes into fields or constants at the top of the test class, matching
how the reference test holds its data.

### Step 5: Generate

Follow the provider's **Test template** exactly — naming, annotations, case-id linkage, groups, description,
and the call style (e.g. a single fluent chain with no page-object local variables).
Keep each TestRail step visible in the code as a one-line comment `// Step <n>: <short action>` above its
calls, so a reviewer can trace code back to the case.

Edit only:
- the target test file, and
- page objects that receive **new** methods.

Do not reformat, reorder imports, or otherwise touch unrelated code in edited files.

### Step 6: Return

`{ target_file, method_name, mapping: [{step, decision, code}], placeholders: [{file, line, step}], diff }`
— the agent presents it and writes only after confirmation.
