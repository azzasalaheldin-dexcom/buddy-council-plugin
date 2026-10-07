# TestNG + Gradle Automation Framework — Provider Skill

Framework-specific rules for `/bc:automate`. Everything here is **discovered from the checkout** — the
examples in parentheses show what that discovery finds in a typical Appium framework (e.g. ApolloAutomation),
not values to hardcode.

All paths below are relative to the resolved framework `root`.

## Profile

Build this from the checkout every run:

| Key | How to find it |
|---|---|
| `test_src` | `src/test/java` if it exists, else `src/main/java` |
| `tests_pkg_root` | Package holding most `@Test` classes (e.g. `tests`) |
| `pageobjects_dirs` | Directories whose classes declare locator fields (`@FindBy`, `@AndroidFindBy`, `@iOSXCUITFindBy`) (e.g. `pageobjects/`) |
| `helpers` | Classes used in many tests as `new X(driver)` chains or protected base-class fields (e.g. `ITDSSharedSteps`, `jarvisMethods`) |
| `base_test` | The superclass most `@Test` classes extend (e.g. `ApolloBaseTest`) |
| `linkage` | How a test names its case. Sample 10 `@Test` annotations: a `testName`/`description` prefix like `TC#<n>_`, a `C<n>` prefix, or `@TmsLink`/`@TestCaseId` annotations |
| `groups_class` | Class of group-name constants used in `groups = {…}` (e.g. `listeners.Suite`) |
| `in_progress_group` | A group excluded by **every** suite XML (e.g. `InProgress`) — this is the in-progress marker. None found → no marker; warn that placeholders could break suite runs |
| `suites_dir` | Directory of TestNG suite XMLs (e.g. `src/test/test-configurations`) |
| `listeners` | `<listeners>` block of the suite most Gradle tasks point at |
| `platform_param` | `<parameter name=…>` that selects the platform in suites (e.g. `platformName`) |
| `props_file` | Properties file Gradle test tasks load into system properties (e.g. `execution.properties`) |
| `task_sysprops` | Literal `systemProperty 'k', 'v'` lines shared by every `Test` task (e.g. `buildReference=dev`) |
| `wrapper` | `gradlew` present? Gradle version from `gradle/wrapper/gradle-wrapper.properties` |
| `java_version` | `sourceCompatibility`/`toolchain` in `build.gradle` |
| `credential_props` | Gradle properties `build.gradle` reads for repository credentials (names only, e.g. `artifactory_saas_user_read`) |

## Placement

- Feature packages live under `tests_pkg_root` (e.g. `tests/Alerts/`, `tests/onboardingtests/`). Match the
  TestRail section path to a package by name similarity; ask once if two packages are equally likely.
- New class name: PascalCase from the feature or the case title's subject, matching sibling class naming.

## Test template

Mirror the reference test. The shape is:

```java
@Test(testName = "<linkage prefix with the TestRail id>_<case title>", groups = {<groups_class>.<GROUP>})
// …the same capability/environment annotations the reference test uses for this kind of flow…
@Features(value = {@Feature("<section / feature name>")})
@Description("<case title>")
public void <methodName>() {
    // Step 1: <action>
    new SomePage(getAppiumDriver())
            .existingMethod(<data field>)
            .nextMethod();
    // Step 2: <action>
    …
}
```

- **Linkage**: use the TestRail case id in the detected `linkage` pattern (e.g. `TC#2926799_<title>`). The
  id must appear in the test so `/bc:automate`'s duplicate guard and any TestRail reporter can find it.
- **Method name**: the detected style, prefixed with the id (e.g. `tc_2926799ValidateThat…`). Keep it
  under 120 characters.
- **Groups**: the feature's group constant from `groups_class` if one exists. Add `in_progress_group` when
  any step is a placeholder. Never add a new group constant without asking.
- **Annotations**: copy capability/environment annotations (`@DesiredCapability`, `@Transmitter`,
  `@BluetoothEnabled`, `@Simulated`, …) only from a reference test with the same kind of flow.
- **Fluent chain, no page-object locals**: write the flow as one `new FirstPage(getAppiumDriver())…` chain
  where each call returns the next page. Never declare page-object variables (`SetupPage setupPage = …`).
  When an existing method in the path returns `void`, change it to return `this` (or the page it lands on) —
  existing callers still compile — and list that edit in the plan. Start a new statement only where the
  reference test does (e.g. a shared-steps helper that doesn't return a page).
- **Assertions**: use the framework's mechanism — page-object verify methods first, then the soft-assert
  helper on the page base class, then TestNG `Assert`. If the framework uses a shared soft-assert, end the
  test with whatever the reference test uses to flush it.
- **Style**: 4-space indent, chained fluent calls with 8-space continuation, line length per the
  framework's checkstyle config if present.

### Placeholder method (for a **new** step)

```java
// TODO(bc): verify locator for C<id> step <n>
@iOSXCUITFindBy(accessibility = "BC_TODO_LOCATOR")
@AndroidFindBy(xpath = "BC_TODO_LOCATOR")
private transient WebElement <elementName>;

@Step("<step text>")
public <ThisPage> <actionName>() {
    <element click/type via the page base class helpers>;
    return this;
}
```

The placeholder token is **`BC_TODO_LOCATOR`**. Use only the locator annotations the framework already uses.

## Readiness

**Build checks** (stop on failure):

| Check | How | Fix to print |
|---|---|---|
| JDK | `java -version` matches `java_version` (major) | Install that JDK and point `JAVA_HOME` at it |
| Wrapper | `gradlew` (or `gradlew.bat` on Windows) exists and is executable | `chmod +x gradlew` |
| Repo credentials | each `credential_props` name has a non-empty value: `grep -c '^<name>=.' ~/.gradle/gradle.properties <root>/gradle.properties` (counts only), or `ORG_GRADLE_PROJECT_<name>` is set | Add it to `~/.gradle/gradle.properties` (per-user, outside the repo) |

**Never print credential values** — report each property as `set` or `missing` only.

**Run checks** (block only the run):

| Check | How |
|---|---|
| `props_file` | exists at the root. It is usually gitignored, so a fresh clone lacks it — say so, and show the keys the build/suite reads |
| Environment config | any gitignored config dir the framework reads (e.g. `local-environment-configuration/`) exists; every absolute path inside it (SDK, node, appium, app binary) exists **on this machine** |
| Appium | `appium --version` succeeds, when the framework depends on Appium |

## Devices

- **Android**: `adb devices` lists at least one `device` (not `unauthorized`/`offline`).
- **iOS**: `xcrun simctl list devices booted` shows a booted simulator, or `xcrun xctrace list devices`
  shows a connected device (macOS only — on other OSes, iOS is `SKIPPED (requires macOS)`).

## Compile

```
./gradlew compileTestJava -q
```

Compile errors are reported as `path:line: message`; match them against the files you wrote.

## Run

Do **not** edit `build.gradle`/`tests.gradle` and do not use the framework's suite-wide tasks. Instead:

1. Write the suite to `build/bc/run-<UTC timestamp>.xml` (`build/` is gitignored, so nothing is left in git),
   with one `<class>` entry per test (group methods of the same class under one `<class>`). Put the timestamp
   in the filename **literally** (e.g. `run-20261004T144000Z.xml`) — no `$(date …)` or shell variables, which
   force a permission prompt. Write it with the file tool, or `mkdir -p build/bc && cat > build/bc/run-<ts>.xml
   <<'EOF' … EOF` (quoted delimiter); both are auto-approved:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE suite SYSTEM "https://testng.org/testng-1.0.dtd" >
   <suite name="bc run" verbose="1">
       <!-- copied verbatim from profile.listeners -->
       <listeners>…</listeners>
       <test name="bc <platform>">
           <parameter name="<platform_param>" value="<platform>" />
           <classes>
               <class name="<fully.qualified.TestClass>">
                   <methods><include name="<methodName>"/></methods>
               </class>
           </classes>
       </test>
   </suite>
   ```

   No `<groups>` block — methods are selected explicitly, so an in-progress test still runs.

2. Run it through the plugin's init script, which registers a `bcRunSuite` task without touching the
   framework's build files:

   ```
   ./gradlew --init-script "<plugin_root>/providers/testng-gradle/bc-run.init.gradle" bcRunSuite \
       -PbcSuite=build/bc/run-<UTC timestamp>.xml \
       -PbcPropsFile=<props_file> \
       -PbcSysProps="<k=v;k=v from task_sysprops>"
   ```

   `<plugin_root>`: `${CLAUDE_PLUGIN_ROOT}`, else `$COPILOT_PLUGIN_ROOT`, else `plugin_root` from
   `sources.json` — use the first that exists on disk. Pass `JAVA_HOME` as a literal path or
   `$(/usr/libexec/java_home -v <n>)`; never read paths from temp files with `$(cat …)`.

## Results

- JUnit XML: `build/test-results/bcRunSuite/TEST-*.xml` (list them with
  `find build/test-results/bcRunSuite -name 'TEST-*.xml' -newer build/bc/run-<ts>.xml | xargs grep -h '<testcase'`) — map each `<testcase classname name>` back to its
  case id, and read its `time` and first `<failure>`/`<error>` message and stack frame. A requested test with
  no `<testcase>` entry did not run — report it as SKIPPED.
- If that directory is empty, the build failed before tests ran — report the Gradle error instead.
- Artifacts to point at: `allure-results/` (open with `allure serve allure-results`), `test-output/`,
  `logs/`, if they exist.
