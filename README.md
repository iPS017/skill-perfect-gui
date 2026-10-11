# skill-perfect-gui

Claude Code plugin **perfect-gui**. It contains the `ui-audit-gate` skill, a UI/UX quality gate that runs before a newly created or modified interface is declared done.

The skill opens the real rendering and captures the before and after states. It inspects geometry, overlaps, overflows, accessibility, keyboard use, forms and responsive behaviour. It runs a traced Web search for references, fixes issues or proposes fixes, then issues a bounded, evidence-backed validation decision. It does not promise a flawless interface: it states what was checked, how, and what was not.

The original specification, [CAHIER_DES_CHARGES.md](CAHIER_DES_CHARGES.md), is written in French.

## Installation

In Claude Code (version 2.1.275 or later), in one step:

```
/plugin install perfect-gui --marketplace iPS017/skill-perfect-gui
```

Or in two steps:

```
/plugin marketplace add iPS017/skill-perfect-gui
/plugin install perfect-gui@skill-perfect-gui
```

Restart Claude Code, then install the script dependencies (a dedicated venv in `~/.cache/ui-audit-gate`):

```bash
bash ~/.claude/plugins/marketplaces/skill-perfect-gui/plugins/perfect-gui/skills/ui-audit-gate/scripts/setup.sh
```

The exact path depends on your installation. The skill suggests this command itself when Playwright is missing. A system Chrome or Edge is enough. Otherwise, `setup.sh` downloads Chromium. `--with-browsers` adds Firefox and WebKit.

Requirements: Python 3.9 or later and git. Node is not needed.

## Usage

- **Automatic**: the skill triggers when Claude creates or modifies an interface (page, component, style, token, form, navigation, displayed translation, and so on).
- **Explicit**: `/perfect-gui:ui-audit [N1|N2|N3] [url] [scope]`, or just ask for a "perfect gui" audit.
- **Mechanical gate**: a `Stop` hook blocks the end of the turn once if interface files changed in the repository without a newer, consistent audit report. To disable it: `UI_AUDIT_GATE=off` (or `warn`), or `.ui-audit/config.json`:

```json
{"gate": {"mode": "warn", "include": ["*.tpl"], "exclude": ["docs/*"]}}
```

### Test the whole site and review it before every publish

`/perfect-gui:ui-scenes [url]` explores the website or Web application and lists everything a user can do: pages, buttons, menus, tabs, fields, lists, forms, URL parameters, settings (theme, language, sorting, filters). It then generates a versioned scene suite in `ui-scenes/scenes.json`, for example 257 scenes replayed on mobile and desktop.

Before every new publish, all scenes are replayed and reviewed. The review detects graphical bugs (overflows, overlaps, clipped text, contrast) and inconsistencies with the environment (dead button, locked scrolling, dark theme not adapted, untranslated content, fallback font, style that differs from one page to another, JavaScript errors), and compares each screenshot with its baseline.

A hook refuses `git push`, `npm publish`, `vercel`, `netlify deploy`, and similar commands until the latest review has the status `ok` on the exact interface being shipped. To disable it: `UI_AUDIT_PUBLISH_GATE=off` (or `ask`).

The same suite can be exported to `@playwright/test` (`--export-playwright tests/ui-scenes.spec.ts`) to run in CI. Details are in [exploration.md](plugins/perfect-gui/skills/ui-audit-gate/reference/exploration.md).

### Project setup

Put a project's defaults in `.ui-audit/config.json` (viewports, browser, session state, named views, gate settings, custom release commands) instead of repeating flags:

- **Apps without a URL per screen** (tab-based apps, Tauri or Electron launchers): declare named views in `.ui-audit/views.json` and pass `--view NAME`; the exploration covers every named view.
- **Logged-in screens**: `login.py --remember` replays the login once (passwords come from environment variables, never from files) and saves the session for every other script.
- **Desktop web-view apps**: `--viewports app` reads the window sizes from `src-tauri/tauri.conf.json` or the Electron main file; `--viewports sweep:800-1920:80` checks every width in between.
- **User flows**: `flow_run.py` runs flows with assertions (visible, text, attribute, focus, no console error), uploads, offline steps and a keyboard-only mode, with screenshots as evidence.
- **Reports**: `summarize.py` merges every output into deduplicated candidates; `report_build.py` pre-fills the report so only the judgments remain.
- **No git**: changes are detected from a snapshot of the last audited state or from modification dates, and the Stop hook reads the files Claude edited in the session.

Evidence (screenshots, measurements, reports) goes into `.ui-audit/` at the root of the audited project. This folder is added to `.gitignore` by default.

## Contents

```text
.claude-plugin/marketplace.json        repository catalogue
plugins/perfect-gui/
  .claude-plugin/plugin.json
  skills/ui-audit-gate/
    SKILL.md                           skill instructions (9-step workflow, rules, decision)
    reference/                         controls, configurations, research, severity, gate, tools, devices, report, exploration
    config/                            viewports, levels and fundamental controls, edge-case data sets
    scripts/                           capture, inspection, keyboard, resize, flows, login, diff, impact, research, summary, report, exploration, scenes, review
    schemas/ templates/
  commands/ui-audit.md                 /perfect-gui:ui-audit command
  commands/ui-scenes.md                /perfect-gui:ui-scenes command
  hooks/                               Stop gate hook and pre-publish hook
  tests/                               test application with injectable defects, test site and acceptance scenarios
CAHIER_DES_CHARGES.md                  original specification (in French)
```

## What is automated, assisted or human

| Area | Automated by the scripts | Assisted (tool plus judgement) | Human only |
|---|---|---|---|
| Geometry, overflows, overlaps | Measurement and detection | Alignment intent | |
| Contrast | Solid backgrounds | Image or gradient backgrounds | |
| Keyboard, focus | Order, traps, visibility, obscuring | Logic of the order | |
| Semantics, ARIA | axe-core rules, accessibility tree | Relevance of names | Output from a real screen reader |
| Content | Lengths, pseudo-localisation | Clarity | Tone, fit for the audience |
| User journeys | Scripted execution | Effort, friction | Real understanding (user testing) |
| Responsive | Viewport emulation, resizing, emulated virtual keyboard | Adaptation choices | Real device (hinge, native keyboard) |
| Aesthetics | | Comparison with references | Brand judgement |

## Tests

```bash
python3 plugins/perfect-gui/tests/run_scenarios.py
```

The suite serves a test application with injectable defects. It checks that the scripts detect each defect (offset button, text overflowing a button, overlay hiding an action, responsive regression, focus trap, poorly reported form error, translation too long, regression introduced by a fix, state lost on resize, virtual keyboard hiding an action) with no false positive on the healthy version. It also covers the Web-unavailable and capture-failed cases, the decision rules, the research log, the hooks and the impact analysis. It explores a multi-page test site, generates its scenes, checks that the healthy version passes the review and that the broken version reports every injected defect (dead button, overflowing menu, locked scrolling, dark theme not adapted, untranslated content, JavaScript error, inconsistent style, visual changes).
