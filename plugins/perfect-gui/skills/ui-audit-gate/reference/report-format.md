# Report and evidence format

## Run tree

```text
.ui-audit/
  config.json                 # optional: hook and project settings
  research-cache.json         # reusable references (revalidation required)
  exceptions.json             # exceptions still open
  RUN-20261011-1430-checkout/
    scope.md
    impact.json
    capabilities.json
    coverage.json
    research/log.json
    research/references.json
    before/<config_id>/<name>__<state>.png
    before/manifests/<config_id>.json
    after/... after-fix-1/... diff/...
    inspect/<config_id>/inspect.json | annotated.png | aria-snapshot.txt
    keyboard/<config_id>/keyboard.json
    findings/DEF-001.json
    report.json
    report.md                 # produced by verify_report.py --render
```

## `report.json`

`init_run.py` creates this skeleton. The agent completes it, then `verify_report.py --apply --render` writes the decision and produces `report.md`.

```json
{
  "run_id": "RUN-20261011-1430-checkout",
  "title": "Checkout form footer",
  "created_at": "2026-10-11T14:30:00Z",
  "trigger": "C1 | C2 | C3",
  "request": "Text of the user's request",
  "goal": "...",
  "acceptance_criteria": ["..."],
  "scope": {"zones": ["Checkout/Footer"], "impact_radius": ["Button (14 instances)"]},
  "level": "N2",
  "computed_level": "N2",
  "reduced_coverage": false,
  "reduction_justification": null,
  "mode": "full | mockup | no_execution",
  "baseline": "before | first-render | unavailable",
  "environment": {"tools": ["playwright 1.x", "chromium 1xx"], "fidelity": "emulation"},
  "assumptions": [{"assumption": "...", "source": "...", "impact_if_wrong": "..."}],
  "research": {"status": "done | partial | not_done", "cause": null},
  "comparisons": [{"ref": "REF-001", "observation": "...", "principle": "...", "gap": "...", "adaptation": "...", "benefit": "...", "nature": "REQUIREMENT"}],
  "visual_change": true,
  "controls": [
    {"id": "GEO-03", "status": "passed", "nature": ["visual", "structural"], "configs": ["mobile-..."], "evidence": ["inspect/mobile-.../inspect.json"]},
    {"id": "ACC-11", "status": "not_verified", "reason": "No screen reader available", "reason_type": "human"},
    {"id": "DAT-01", "status": "not_applicable", "reason": "No table in the scope"}
  ],
  "findings": ["see the record below"],
  "fixes": ["see severity-and-fixes.md"],
  "variants": [],
  "before_after": [{"config_id": "mobile-...", "before": "before/.../checkout__normal.png", "after": "after-fix-1/.../checkout__normal.png", "diff": "diff/...png", "comment": "Expected difference, wider button"}],
  "regressions": [{"control": "DS-05", "result": "No unexpected difference on 6 screens"}],
  "coverage": "coverage.json",
  "limitations": ["Native virtual keyboard not tested (emulation)"],
  "human_checks": ["ACC-11 screen reader on the payment flow"],
  "decision": null
}
```

Possible values of `decision` are `VALIDATED_FULL_PROTOCOL`, `VALIDATED_TESTED_SCOPE`, `VALIDATED_WITH_EXCEPTIONS`, `NOT_VALIDATED` and `LIMITED_VALIDATION`.

## Finding record (`findings[]` or `findings/DEF-xxx.json`)

```json
{
  "id": "DEF-012",
  "title": "Label \"Confirm booking\" clipped at 320 px",
  "control": "CTA-01",
  "screen_component": "Checkout / Button(primary)",
  "preconditions": "Cart with 1 item, user signed in",
  "data": "fixture typical, language de",
  "config_id": "mobile-narrow-w320h640-z100-light-de-DE-m-chromium",
  "steps": ["Open /checkout", "Scroll to the footer"],
  "expected": "Label fully visible within the button surface",
  "observed": "Text cut after \"Reservierung best\"; scrollWidth=212, clientWidth=176",
  "interpretation": "white-space:nowrap and fixed container width",
  "nature": "REQUIREMENT",
  "evidence": ["inspect/mobile-narrow-.../annotated.png", "inspect/mobile-narrow-.../inspect.json"],
  "reproductions": "2/2",
  "severity": "major",
  "priority": "P1",
  "confidence": "high",
  "effort": "S",
  "status": "open | fixed | failed_unresolved | accepted_exception",
  "introduced_by_fix": false,
  "retest": {"status": "passed", "config_id": "...", "evidence": ["after-fix-1/..."]},
  "exception": null,
  "blocking_cause": null,
  "required_action": null
}
```

`nature` takes the value `REQUIREMENT`, `HYPOTHESIS` or `PREFERENCE`. Findings can be written directly into `report.json > findings` or into `findings/*.json`. `verify_report.py` merges both sources by ID.

## Configuration manifest (`manifests/<config_id>.json`)

Written by `capture.py`. It contains the CSS viewport, the DPR, the zoom, the theme, the locale, the time zone, the preferences, the pointer, the engine and its version, the fidelity, the frozen clock, the URL, the navigation steps and the git revision.
