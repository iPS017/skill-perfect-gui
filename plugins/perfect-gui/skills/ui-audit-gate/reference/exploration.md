# Exploration and scene review before release

The per-change audit (9-step workflow) checks what has just changed. This mode covers **everything a user can do** on the website or web application. It generates a versioned scene suite and replays all of it before each release.

## Cycle

```text
1. explore_site.py        real site -> ui-scenes/site-map.json   (inventory of everything that can be done)
2. generate_scenarios.py  site-map  -> ui-scenes/scenes.json     (one scene per action, option, parameter, setting)
3. play_scenarios.py --mode baseline                              (baseline screenshots, once)
4. before each release:
   play_scenarios.py      replays every scene on every viewport, compares, detects
   -> status ok | needs-review | failed | incomplete  ->  ui-scenes/last-review.json + runs/<date>/review.md
5. fix, or accept intended visual changes (--accept), then rerun the review
6. the pre-publish hook lets git push, npm publish, vercel, etc. through only if
   the last review is "ok", complete, and was run on the exact interface being shipped
```

After a structural change (new page, new form), rerun 1 and 2. The IDs of existing scenes do not change. New scenes are added and the ones that disappeared are listed in `removed`.

## Commands

```bash
SK="$SKILL_DIR/scripts"
python3 "$SK/explore_site.py" --url http://localhost:3000/ --out ui-scenes/site-map.json --max-pages 40
python3 "$SK/generate_scenarios.py" --site-map ui-scenes/site-map.json --out ui-scenes/scenes.json \
        --export-playwright tests/ui-scenes.spec.ts
python3 "$SK/play_scenarios.py" --suite ui-scenes --url http://localhost:3000/ --mode baseline
python3 "$SK/play_scenarios.py" --suite ui-scenes --url http://localhost:3000/ --viewports mobile,laptop --workers 4
python3 "$SK/play_scenarios.py" --suite ui-scenes --accept S-0012,S-0040     # intended visual changes
```

Useful options:
- explore takes `--max-pages`, `--max-depth`, `--include` and `--exclude` (path regexes), `--reveal-budget` (toggles opened to find hidden controls), `--storage-state` (signed-in session);
- generate takes `--max-options`, `--env-pages`, `--max-scenes`;
- play takes `--viewports` (default mobile,laptop; `P0,P1` at N3), `--scenes`, `--categories`, `--workers`, `--allow-mutations`, `--max-diff-ratio`, `--mask` (intentionally dynamic areas such as a carousel, a date or an ad).

Dynamic areas to mask permanently can also be declared in `scenes.json` (`"masks": [".carousel", "#live-date"]`). Lazy-loaded images are loaded before each screenshot. If a review against its own baseline shows changes, the content is not deterministic: pin the test data or mask the area, never raise the threshold blindly. A refused page (HTTP error, bot protection) is reported and not bypassed. Explore the development or test environment instead.

## What the scenes cover

| Category | Generated scenes |
|---|---|
| page | Loading of each discovered page, including URL parameter variants |
| control | Each safe button, anchor or action, with effect detection (dead button) |
| toggle | Open, then close (Escape for a menu or popup, second click for a collapsible panel) |
| tab, menu | Activation of each tab and each menu item |
| select, checkbox, radio, range | Each option (sampled beyond `--max-options`), check and uncheck, min and max bounds |
| form | Empty submit, invalid values, valid values, very long content |
| url-param | Each observed value, plus an unexpected value and an empty value |
| setting | Theme, language, sort, filters, units, etc. (controls recognized as settings) |
| environment | System dark theme, reduced motion, 200% zoom (desktop), each `hreflang` language |

Hidden controls revealed by an interaction (menu, dialog, accordion) are played together with the action that reveals them.

## What each step checks

Each `snapshot` step checks horizontal overflow, clipped text, overlap (outside modals and open overlays), target size, contrast, form errors, alignment, images, accessible names. Consistency checks against the environment are added on top:

| Anomaly | Control | Blocking |
|---|---|---|
| `dead-click`, a click with no change to the DOM, the URL or the scroll position, and no request | PAR-08 | yes |
| `scroll-locked`, a page that cannot be scrolled with no dialog open | STK-08 | yes |
| `theme-not-adapted`, a large light area in a dark page | COL-03 | yes |
| `untranslated-content`, more than half of the texts unchanged after a language change | LOC-02 | yes |
| `javascript-error`, an unhandled exception | ROB-01 | yes |
| `lang-not-updated`, texts translated but the `lang` attribute unchanged | ACC-12 | no |
| `font-not-loaded`, a web font declared but a fallback rendered | TXT-05 | no |
| `style-inconsistency`, a component that differs from its peers on the site (font, size, radius, link color) | DS-03 | no |
| `escape-does-not-close`, a menu or popup that stays open after Escape | STK-03 | no |
| `control-unavailable-at-viewport`, a control not found or not clickable at this viewport | NAV-06 | no (judgment call) |
| `dark-scheme-ignored`, the site declares a dark theme but the page stays light | COL-03 | no |
| `blocked-request`, a POST, PUT or DELETE request blocked by the guard | - | no |

Each screenshot is compared with its baseline (`visual_changes`). A difference is neither good nor bad, it must be reviewed. Either it is intended and accepted with `--accept`, or it is a regression and gets fixed.

## Review statuses

| Status | Condition | Publishing |
|---|---|---|
| `ok` | Every scene executed, no blocking anomaly, no unaccepted visual change | allowed |
| `needs-review` | Visual changes or new screenshots without a baseline | blocked until accepted or fixed |
| `failed` | At least one unaccepted blocking anomaly | blocked |
| `incomplete` | Scenes in error, partial selection (`--scenes`, `--categories`) | blocked |

A blocking anomaly is only accepted (`--accept-anomaly KEY --reason ... --accepted-by ...`) on the user's explicit decision. It is then recorded in `ui-scenes/known-issues.json`. The agent never accepts one on its own.

## Safety

- Destructive actions (delete, pay, send, sign out, cancel a subscription, etc.) are not generated. They are listed in `not_covered`.
- All requests other than GET, HEAD and OPTIONS are blocked during exploration and review, except with `--allow-mutations`, which is reserved for a test environment with fake data.
- Signed-in sessions go through `--storage-state`. No real password in the scenes.

## Suite files

| File | Versioned | Role |
|---|---|---|
| `ui-scenes/scenes.json` | yes | Scene suite, stable IDs |
| `ui-scenes/site-map.json` | yes (recommended) | Inventory of what can be done |
| `ui-scenes/baseline/` | yes (Git LFS if large) | Baseline screenshots |
| `ui-scenes/known-issues.json` | yes | Anomalies accepted by the user |
| `ui-scenes/runs/` | no (added to `.gitignore`) | Screenshots, diffs, reports of each review |
| `ui-scenes/last-review.json` | no | State read by the pre-publish hook |
| `tests/ui-scenes.spec.ts` | optional | Same suite as `@playwright/test` for CI (`npx playwright test --update-snapshots` the first time) |

## Publish gate

The plugin's `PreToolUse` hook intercepts publish commands (`git push`, `npm`, `pnpm`, `yarn` and `bun publish`, `vercel`, `netlify deploy`, `firebase deploy`, `fly deploy`, `wrangler deploy`, `gh release create`, `docker push`, `npm run deploy`, `eas submit`, `fastlane`, etc.). It refuses the command if:
- no complete review exists;
- `scenes.json` has changed since the review;
- an interface file has changed since the review (fingerprint of tracked and untracked files);
- the review status is not `ok`.

It only acts if the project has `ui-scenes/scenes.json` (or the path set in `.ui-audit/config.json > publish_gate.suite`). Settings are `UI_AUDIT_PUBLISH_GATE=block|ask|off`, or `publish_gate.mode`. Additional commands are declared in `publish_gate.patterns`.

## Non-web applications

- **Web, PWA, hybrid served locally** (Capacitor, Ionic, React Native Web, Flutter Web, Tauri or Electron with their development server): full cycle, pointing `--url` at the development server.
- **Pure native application** (iOS, Android, desktop): these scripts do not drive it. The skill can write the list of scenes from the code (screens, routes, settings) and replay them in assisted mode, through computer use or with the platform tools (XCUITest, Espresso, UI Automation). These are then assisted checks, declared as such in the report, not an automated review.

## Limits

- One option at a time: combinations of several settings are not all generated. Add the critical combinations by hand in `scenes.json` (same format, new ID).
- No file upload, drag and drop or multi-finger gesture is generated automatically.
- Menus that only open on hover are not discovered. They are listed in `not_covered` when their items exist but stay hidden.
- `dead-click` has medium confidence, since an action can act on a canvas, the clipboard or the sound without changing the DOM.
- Screenshots depend on the engine and the machine, so baseline and review must run in the same environment (same browser, same OS, ideally in CI).
