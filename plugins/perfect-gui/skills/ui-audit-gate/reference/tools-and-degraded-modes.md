# Tools, permissions and degraded modes

## Provided scripts

| Script | Role | Dependencies |
|---|---|---|
| `init_run.py` | Creates `.ui-audit/RUN-<date>-<slug>/`, the skeletons and the `.gitignore` entry | stdlib |
| `probe.py` | Probes capabilities (Python, Playwright, engines, Pillow, axe, git, native SDKs, screen readers) | stdlib, optional Playwright |
| `impact_scan.py` | Classifies changed files, propagates tokens, components and i18n keys, suggests a level | git |
| `capture.py` | Screenshots and manifests per configuration | Playwright |
| `inspect_page.py` | Automated in-page checks, annotated screenshot, accessibility tree, axe | Playwright, optional Pillow, optional axe |
| `keyboard_walk.py` | Keyboard walk | Playwright |
| `resize_probe.py` | State loss on resize, emulated virtual keyboard | Playwright |
| `visual_diff.py` | Before/after pixel diff | Pillow |
| `pseudo_locale.py` | Pseudo-localization of JSON files | stdlib |
| `explore_site.py` | Inventory of everything a user can do on the site | Playwright |
| `generate_scenarios.py` | Stable scene suite, `@playwright/test` export | stdlib |
| `play_scenarios.py` | Full scene review, baselines, comparison, acceptance | Playwright, Pillow |
| `research_log.py` | Research log and reference records | stdlib |
| `verify_report.py` | Report consistency, decision, rendering of `report.md` | stdlib |
| `setup.sh` | Creates the venv and installs Playwright and Pillow (with consent) | python3, network |
| `login.py` | Replays the login actions of `views.json` once (secrets from `${env:NAME}`) and saves the session state | Playwright |
| `flow_run.py` | User flows with assertions, uploads, offline steps, keyboard-only mode and automatic screenshots | Playwright |
| `summarize.py` | Merges every output of a run into deduplicated candidates and a per-check matrix | stdlib |
| `report_build.py` | Pre-fills `report.json` from the outputs (passed controls with evidence, placeholders, pairs, candidates) | stdlib |

Options shared by the browser scripts: `--url`, `--viewports` (IDs, `P0`, `P1`, `P2`, `WxH`, `app` for the Tauri or Electron window sizes, `sweep:MIN-MAX:STEP`), `--view NAME` (named view from `.ui-audit/views.json`), `--network normal|slow|offline`, `--theme light|dark`, `--locale`, `--timezone`, `--zoom`, `--reduced-motion reduce|no-preference`, `--forced-colors`, `--engine chromium|firefox|webkit`, `--browser-path`, `--headed`, `--actions` (file or JSON), `--storage-state` (authenticated session), `--freeze-time`, `--wait-ms`.

Browser launch order: `--browser-path` if given (only attempt), otherwise `browser_path` from `.ui-audit/config.json`, `UI_AUDIT_BROWSER`, the browser remembered from the last successful launch (`~/.cache/ui-audit-gate/browser.json`), Playwright's Chromium, Chrome and Edge channels, then system binaries (`google-chrome`, `chromium`, `microsoft-edge`, macOS and Windows install paths).

## Project settings

`.ui-audit/config.json` holds the defaults of a project: `viewports`, `browser_path`, `storage_state`, `views_file`, `gate` and `publish_gate`. Command-line flags always win.

## Projects without git

- `init_run.py` stores a snapshot of the UI files in the run (`snapshot-start.json`).
- `impact_scan.py` compares with `.ui-audit/snapshot.json`, saved when the previous audit was applied, or lists the UI files modified in the last `--since-hours` hours (default 24). Detection confidence is reported (`certain` for a snapshot, `probable` for dates).
- The Stop hook reads the files written or edited by Claude in the current session from the transcript.
- The pre-publish hook fingerprints UI files by walking the project (ignoring `node_modules`, `dist`, `target` and similar folders).

## Desktop web-view apps

Tauri and Electron render with a system web view. `--viewports app` uses the declared window sizes. Chromium matches WebView2 (Windows) and Electron, but not WKWebView (macOS) or WebKitGTK (Linux): run the key checks with `--engine webkit` as an approximation, and keep rendering in the real web view `not_verified` unless a tauri-driver (WebDriver) session or a manual check covers it. Linux screen reader checks can use Orca through AT-SPI by hand; the scripts do not drive it.

## Installation

```bash
bash "$SKILL_DIR/scripts/setup.sh"                  # venv ~/.cache/ui-audit-gate/venv + playwright + pillow
bash "$SKILL_DIR/scripts/setup.sh" --with-browsers  # also downloads Playwright's Chromium, Firefox and WebKit
```

Always ask for consent before installing, and give the exact command. axe-core is downloaded once from cdnjs, or jsDelivr as a fallback, into `~/.cache/ui-audit-gate/`. `--no-axe` disables this download. `UI_AUDIT_AXE=/path/axe.min.js` uses a local copy.

## Alternatives by environment

| Capability | First choice | Alternatives |
|---|---|---|
| Controllable browser | Playwright scripts | The host's browser tool (Chrome DevTools MCP, browser extension, computer use), reproducing the same measurements manually |
| Accessibility rules | axe-core via `inspect_page.py` | Lighthouse (subset), axe extension in a real browser |
| Visual diff | `visual_diff.py` (local) | The project's visual regression tool. An online service only with permission and without sensitive data. |
| Native iOS | XCUITest, Accessibility Inspector (macOS and Xcode required) | Screenshots and computer use |
| Native Android | Espresso or UI Automator, `adb shell uiautomator dump`, Accessibility Scanner | Screenshots and computer use |
| Windows desktop | UI Automation (Inspect.exe, Accessibility Insights) | Computer use |
| macOS desktop | AX API (Accessibility Inspector) | Computer use |
| Linux desktop | AT-SPI (Accerciser) | Computer use |
| Hybrid (WebView, Electron, Tauri, Capacitor) | Remote debugging of the WebView, then web scripts | Same as native for the shell |
| Screen reader | NVDA, JAWS, VoiceOver, TalkBack operated by a human | Automated driver only if installed and configured |
| Real devices | Local device with USB debugging | Remote device farm, with permission and anonymization |

Never assume that a tool inspects a native application or drives a screen reader without a suitable integration. Without structural inspection, the native audit is visual, and the structural and assistive controls are `not_verified`.

## Degraded modes

| Situation | Alternative | Controls not verified | Ceiling |
|---|---|---|---|
| No controllable browser | Screenshots provided by the user, reading the code | All behavioral, dynamic structural and assistive controls | LIMITED_VALIDATION (`mode: no_execution`) |
| Capture impossible | Diagnosis (launch log), other engine, `--headed`, production build. Otherwise structural analysis without images. | Visual controls, before/after | NOT_VALIDATED if the change is visual |
| No web access | `research_log.py unavailable` | Research | VALIDATED_TESTED_SCOPE |
| No accessibility tree | DOM and ARIA inspection | ACC-05 partial, ACC-06 | Reported |
| Native without integration | Screenshots and computer use | Structure, accessible names | LIMITED_VALIDATION |
| No real device | Declared emulation | Hardware behaviors | Listed |
| Mockup only | Static visual audit | Interactions, real responsive behavior, structural accessibility | LIMITED_VALIDATION (`mode: mockup`) |

For each tool failure, record a concise trace (command, summarized error), the alternative attempted and the list of affected controls in `report.json > limitations`.

## Permissions and confidentiality

- Respect the host's permission mode. Do not widen the scope of changes without consent.
- User flows with external effects run against a test environment or fake data. Otherwise, stop before the irreversible action and ask for explicit confirmation.
- Screenshots stay in `.ui-audit/`, which is in `.gitignore` by default. Nothing is sent to a search engine or a third-party service without permission. Anonymize before any sharing.
- No secrets in reports, manifests or logs. `--storage-state` points to a local file that is never copied into the run.
