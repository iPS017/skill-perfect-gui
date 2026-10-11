---
name: ui-audit-gate
description: Perfect GUI (perfect-gui, "perfect gui") mandatory UI/UX quality gate before declaring any interface creation or change finished (GUI, UI, UX, page, screen, component, form, navigation, interaction, style, CSS, design token, font, theme, responsive layout, displayed translation, loading or error states). Opens the real rendered UI, captures before/after screenshots, inspects geometry, overlaps, overflow, accessibility, keyboard, forms and responsive behavior, runs a traced web search for references, fixes or proposes fixes, then issues a bounded, evidence-backed validation decision. Also explores a whole website or web app, generates a scene for every possible action, option, parameter and setting, and reviews every scene before each release. Use whenever you create, change, restyle, or refactor any user interface, web page, component, form, layout, CSS, or design token, before saying the UI work is done; when the user asks for a UI/UX audit, a design review of a rendered page, or a responsive or accessibility check; when they want to test everything a user can do on a site or a desktop web-view app (Tauri, Electron), generate UI scenarios or regression scenes, or review the UI before publishing, deploying, or pushing; and whenever the user says "perfect gui" or "perfect-gui".
---

# ui-audit-gate

This skill sits between "the interface has been changed" and "it is validated". It does not promise a flawless interface. It reduces risk, proves what was checked and states honestly what was not.

`SKILL_DIR` is the folder that contains this file. Scripts are run with `python3 "$SKILL_DIR/scripts/<script>.py"`. They switch to the venv `~/.cache/ui-audit-gate/venv` on their own if it exists. Every script prints JSON. Exit code 3 signals a missing capability, to be translated into `not_verified` controls.

Write reports and messages to the user in the user's language.

## Non-negotiable rules

1. **No validation without a real render**, except in a declared degraded mode (mockup, no execution).
2. **A control that was not run is never `passed`.** Possible statuses: `passed`, `failed`, `not_verified` (with a reason), `not_applicable` (with a factual reason).
3. **Three distinct checks**: visual, behavioral, assistive. A correct screenshot proves neither a user flow nor accessibility.
4. **Real web research on every audit**, traced in `research/log.json`. No invented URL, source or visit. A reference cited from memory without revalidation is `memory_not_revalidated` and does not count.
5. **Label every finding**: `[REQUIREMENT]` (explicit applicable rule), `[HYPOTHESIS]` (to be verified), `[PREFERENCE]` (taste, never blocking on its own).
6. **Emulation is not a real device.** An emulated viewport is not a phone test. No invented device dimensions (see `reference/devices.md`).
7. **Do not say "done", "validated" or "ready"** until step 9 has produced a decision. Say "implemented, audit in progress" instead.
8. **Confidentiality**: no screenshot, data or internal product name in search queries. Nothing is sent to a third-party service without permission.
9. **Fix the cause** (token, shared component) rather than hiding the symptom. An `overflow:hidden` or a `z-index:9999` added without analysis is a workaround and must be declared as one.
10. **Never grant yourself an exception.** Only the user can accept a residual major finding. A critical finding cannot be covered by an exception.

## When to use it

Triggers: new interface; change of style, content, structure, shared component, behavior, navigation, states, displayed data or responsive layout; **indirect change** (font, token, global CSS, reset, UI library upgrade, CSS build configuration, translation files).

Not for: purely backend code with no displayed effect, or a theoretical question with no interface to examine. In the latter case, offer the audit.

## Getting started

```bash
python3 "$SKILL_DIR/scripts/init_run.py" --slug checkout-footer        # creates .ui-audit/RUN-.../ and a UI files snapshot
python3 "$SKILL_DIR/scripts/probe.py" --out "$RUN/capabilities.json"   # capabilities, system browsers, app window sizes
python3 "$SKILL_DIR/scripts/impact_scan.py" --out "$RUN/impact.json"   # scope and level (git, or snapshot / mtime without git)
```

If `probe.py` reports that Playwright is missing, offer `bash "$SKILL_DIR/scripts/setup.sh"` with the exact command and ask for consent before installing. Without consent, switch to a degraded mode (table below). The first browser that launches (bundled Chromium, Chrome, Edge, or a system binary such as `/usr/bin/google-chrome`) is remembered: no `--browser-path` on every command.

### Project setup (once per project)

Put the project's settings in `.ui-audit/config.json` instead of repeating flags. Every key is optional:

```json
{
  "viewports": "app",
  "browser_path": "/usr/bin/google-chrome",
  "storage_state": ".ui-audit/auth/state.json",
  "views_file": ".ui-audit/views.json",
  "gate": {"mode": "block", "include": ["src/**/*.vue"], "exclude": ["docs/*"]},
  "publish_gate": {"mode": "block", "patterns": ["scripts/build-rpm\\.sh", "make release"]}
}
```

- **Apps without URLs per screen** (tabs, stores, desktop apps): declare named views in `.ui-audit/views.json` (`{"views": {"skin": [{"click": "role=tab[name=\"Skin\"]"}]}}`) and pass `--view skin` to any script instead of hand-written `eval` actions.
- **Logged-in screens**: add a `"login"` action list to `views.json` with `${env:NAME}` placeholders for secrets, then run `login.py --url URL --remember` once. It saves the session state in `.ui-audit/auth/` (git-ignored) and records it in the config. Never write a password in a file.
- **Desktop web-view apps (Tauri, Electron)**: `--viewports app` reads the window sizes from `src-tauri/tauri.conf.json` or the Electron main file (minimum, default, 1366, 1920). Phone sizes are then out of scope: record them as excluded in `coverage.json`. The scripts render in Chromium. The real engine differs: WebView2 (Windows) is Chromium, but WKWebView (macOS) and WebKitGTK (Linux) are WebKit, so also run the key checks with `--engine webkit` when it is installed (`setup.sh --with-browsers`), and list rendering in the real web view as `not_verified` (`reason_type: technical`) until a tauri-driver run or a manual check covers it.
- **Width sweep**: `--viewports sweep:800-1920:80` checks every width between the minimum and the maximum, which catches collisions that only happen in a narrow band.
- **Selectors**: prefer role selectors (`role=tab[name="Skin"]`, `role=button[name="Sign in"]`) over `text=`, which can hit a hidden heading.

## Mandatory workflow (9 steps)

Full details, inputs and outputs: `reference/workflow.md`. Each step produces evidence or a justified `not_verified` status.

1. **Frame.** Restate the goal and the acceptance criteria in `scope.md`. Run `impact_scan.py`. List the assumptions. Set the level (N1, N2 or N3, see below). Use the repository and the conversation before asking anything. Ask only the blocking questions, all in one batch.
2. **Capture the before state.** If the agent has not changed the code yet, capture now. Otherwise, rebuild the previous state in an isolated worktree (`git worktree add`) and run it. For a new interface, record `baseline=first-render`. If nothing is possible, record `baseline=unavailable` with the reason.
   `capture.py --url URL --viewports P0 --out "$RUN/before" --name home --state normal`
3. **Research.** Protocol: `reference/research-protocol.md`. Use the host's web search tool, then log every query and every opened page with `research_log.py`. Keep 2 to 5 references (8 at N3), fill in the comparison table, then stop according to the stopping rule.
4. **Run and capture the after state.** Start the real application (project scripts), wait for it to settle and go through the chosen states and configurations (`reference/configurations.md`). Perform the interactions of the user flows (`--actions`).
5. **Inspect and cross-check.**
   - `inspect_page.py`: horizontal overflow, clipped text, overlap (`--scan-scroll`), target size, alignment of sibling elements, contrast, labels, accessible names, form errors, images, headings, language, axe-core if available, console.
   - `keyboard_walk.py`: tab order, focus traps, visible focus, obscured focus, unreachable elements.
   - `inspect_page.py` also checks `spacing` (neighboring blocks of a row touching or overlapping: tabs glued to a profile block, for example) and re-measures contrast alerts on the screenshot pixels when a layer (overlay, `clip-path`, gradient) is invisible to computed styles.
   - `resize_probe.py --mode state` (state lost on resize or fold) and `--mode keyboard` (emulated virtual keyboard).
   - `flow_run.py`: user flows with assertions (`expect_visible`, `expect_text`, `expect_attr`, `expect_focus`, `expect_no_console_error`...) and automatic screenshots, with `upload`, `set_offline`, `tab_to` steps and a `--keyboard-only` mode. Use it for PAR-01, FRM-03 and ACC-02 instead of writing Playwright scripts by hand.
   - `--network slow|offline` on any script shows the loading, empty and offline states.
   - `summarize.py "$RUN"` merges every output into deduplicated candidates (one line per problem across views and sizes).
   - Visual review of the annotated screenshots. Controls without a script are listed in `reference/controls.md`.
6. **Record and prioritize.** One record per finding (schema `schemas/finding.schema.json`), reproduced twice, with the observed facts kept separate from the interpretation. Severity, priority, confidence and effort are four distinct fields (`reference/severity-and-fixes.md`). Group findings by common cause.
7. **Fix or propose.** Within the authorized scope, fix the cause and propagate it. Outside the scope, provide a concrete fix. Offer 2 or 3 variants **only** when there is a real trade-off, and recommend one.
8. **Re-verify.** Rerun the controls, **re-capture under the same conditions** (`--out "$RUN/after-fix-1"`), then run `visual_diff.py` on before/after and on the impact radius. Explain every difference. Limit: 3 iterations by default, 6 per run. Beyond that, mark `failed_unresolved` with the cause and the required action.
9. **Report and decide.** Run `report_build.py "$RUN"`: it pre-fills `report.json` with the controls that passed (with their evidence), placeholders for the fundamental controls still to judge, the before/after pairs and the candidate list. Complete the judgments, then run `verify_report.py "$RUN" --apply --render`. If an evidence path is wrong, the error names the closest existing file. The script computes the decision according to `reference/validation-gate.md`, rejects an inconsistent report and produces `report.md`. Announce the decision in the conversation (format below).

## Exploration mode: every scene, reviewed before each release

When the user wants to test everything a user can do, before a production release, or when the level is N3 on a whole site, follow these steps (details in `reference/exploration.md`):

1. `explore_site.py` inventories pages, buttons, menus, tabs, toggles, fields, selects, checkboxes, forms, URL parameters, settings (theme, language, sort, filters), languages and breakpoints, including controls revealed by an interaction.
2. `generate_scenarios.py` derives `ui-scenes/scenes.json` from it: one scene per action, option, parameter, setting, form (empty, invalid, valid, very long) and environment (dark theme, reduced motion, zoom, languages). IDs stay stable. `--export-playwright` produces the same suite for CI.
3. `play_scenarios.py --mode baseline` records the baselines. Then, **before each release**, `play_scenarios.py` replays every scene on every viewport. It detects visual bugs and inconsistencies with the environment (dead button, locked scrolling, theme not adapted, untranslated content, fallback font, style inconsistent across pages, JS errors) and compares each screenshot with its baseline.
4. Fix, accept intended visual changes (`--accept`), rerun until the status is `ok`. The pre-publish hook refuses `git push`, `npm publish`, `vercel`, etc. as long as the last review is not `ok` on the exact interface being shipped.

Destructive actions are never played and POST, PUT and DELETE requests are blocked, unless `--allow-mutations` is used in a test environment. What is not covered (multiple combinations, file upload, drag and drop, hover) is listed in the report. For a pure native application, scenes are replayed in assisted mode and declared as such.

## N3 checklist (critical flows, global styles, releases)

Beyond the fundamental controls, an N3 audit covers or explicitly excludes, with the reason:
- the scene suite (`/perfect-gui:ui-scenes`), which is the regression net to replay before every release;
- extreme content: `config/fixtures/edge-text.json`, pseudo-localization, long names in tight blocks (profile, tabs, toasts);
- slow and offline network on every loading state (`--network slow|offline`, `set_offline` in flows);
- flows that the generator skips: file upload (`upload` step), long-running states (download in progress), persistent error toasts, destructive actions in a test environment only;
- `--forced-colors` (Windows high contrast) and `--reduced-motion reduce`;
- canvas or WebGL views: rendering and fallback when WebGL is unavailable are checked by hand (`not_verified` otherwise);
- screen reader: ACC-11 stays a human check unless a real screen reader session is run.

## Audit levels

| Level | When | Coverage |
|---|---|---|
| N1 | Always | Fundamental controls (`config/levels.json`) on the scope, P0 viewports, affected states, targeted research |
| N2 | Shared component, behavior, navigation, form, or a finding at N1 | N1, plus consumers and neighboring screens, P0+P1, full keyboard pass on the user flow |
| N3 | Token or global style, UI dependency, redesign, critical flow (payment, authentication, personal data, destructive action) | N2, plus P2, user preferences, localization, degraded network, foldables, broad sampling |

`impact_scan.py` suggests a level. Any downgrade is declared in `report.json` (`reduced_coverage`, `reduction_justification`).

## Minimum configurations

- Viewports in CSS pixels: `config/viewports.json` (P0: 320x640, 390x844, 1366x768, 1440x900). Add the project's real breakpoints at `b-1`, `b` and `b+1` (`--viewports 767x900,768x900,769x900`).
- Content: `config/fixtures/` (long, empty, unexpected) and pseudo-localization (`inspect_page.py --pseudo`, `pseudo_locale.py`).
- Preferences: `--theme dark`, `--reduced-motion reduce`, `--forced-colors`, `--zoom 2`, `--text-spacing`.
- Record in `coverage.json` the combinations executed **and** those excluded, with the reason and the risk. Never write "tested on all devices".

## Degraded modes

| Situation | What to do | Decision ceiling |
|---|---|---|
| No Playwright and no browser | Offer `setup.sh`. Otherwise use screenshots provided by the user and read the code. | LIMITED_VALIDATION (no_execution) |
| Capture impossible | Diagnose, retry with another engine (`--engine`, `--browser-path`, `--headed`), then mark every visual control `not_verified` | NOT_VALIDATED if the change is visual (B5) |
| Web unavailable | `research_log.py unavailable --cause ...`, continue the local controls, label recommendations `[HYPOTHESIS, not sourced online]` | VALIDATED_TESTED_SCOPE at best |
| Mockup only | Static visual audit, interactions `not_verified` | LIMITED_VALIDATION (mockup) |
| Native or hybrid | `reference/tools-and-degraded-modes.md` | Depends on tooling |
| No git | `impact_scan.py` compares with the last audited snapshot (`.ui-audit/snapshot.json`) or uses `--since-hours`; the Stop hook reads the files edited in the session | No ceiling |
| No real device | Declared emulation, hardware controls `not_verified` with `reason_type: real_device` | No ceiling, but listed |
| No screen reader | ACC-11 `not_verified` with `reason_type: human` | Listed as a human check |

## User flow safety

External or irreversible actions (payment, sending, deletion, publishing) are tested with fake data or a test environment. Otherwise, stop before the action and ask for confirmation. Secrets never go into reports. Anonymize any screenshot that leaves the machine.

## Mechanical gate

The plugin installs two hooks. The `PreToolUse` hook blocks publish commands without a valid scene review (see exploration mode). The `Stop` hook blocks the end of the turn once if interface files changed (git status, or the files Claude edited in the session outside git) without a consistent, more recent `report.json`. Projects with a custom release command (`scripts/build-rpm.sh`, `make release`) list it in `publish_gate.patterns`. Disabling: `UI_AUDIT_GATE=off|warn` or `.ui-audit/config.json`. Create `.ui-audit/SKIP` (with a reason) **only** if the user explicitly asked not to audit. Do not claim the skill is "always active" if the hook is not installed.

## Final message in the conversation

```
UI audit: <DECISION> (RUN-...)
Checked: <level, configurations, controls run>
Findings: <n critical / n major / ...>; fixed: <n>; remaining: <short list>
Not verified: <e.g. real screen reader, physical foldable, native keyboard>
Report: .ui-audit/RUN-.../report.md
```

Never conclude with "everything is perfect". Do not present the absence of detected findings as the absence of defects.

## Reference files

| File | Content | When to read it |
|---|---|---|
| `reference/workflow.md` | Detailed steps, determinism, loop | Always, on the first audit of a session |
| `reference/controls.md` | Full control matrix (IDs, method, expected result, severity) | Step 5 |
| `reference/configurations.md` | States, viewports, foldables, virtual keyboard, sampling | Steps 4 and 5 |
| `reference/research-protocol.md` | Queries, source hierarchy, reference record, stopping | Step 3 |
| `reference/severity-and-fixes.md` | Severity, priority, fix record, variants | Steps 6 and 7 |
| `reference/validation-gate.md` | Statuses, blocking conditions, decisions, exceptions | Step 9 |
| `reference/tools-and-degraded-modes.md` | Scripts, alternatives, native, permissions | Step 1 or when a tool fails |
| `reference/devices.md` | Checking devices and screen classes | Foldables and named devices |
| `reference/report-format.md` | Structure of `report.json`, evidence tree | Steps 6 and 9 |
| `reference/exploration.md` | Exploration, scene suite, pre-release review, statuses, publish gate | Whole site, "test everything", before a release |
