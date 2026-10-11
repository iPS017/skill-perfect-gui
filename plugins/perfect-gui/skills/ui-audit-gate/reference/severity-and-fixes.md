# Severity, fixes and variants

## Severity (impact on the user)

| Level | Definition | Examples |
|---|---|---|
| `critical` | Prevents an essential task for all or some users, with no reasonable workaround, or risks harm (data loss, unintended irreversible action, dangerous flashing) | "Pay" button hidden by a banner, focus trap, user flow impossible with the keyboard |
| `major` | Severely hinders the task, causes frequent errors or excludes a group, with a costly workaround | Clipped button label that makes the action ambiguous, unannounced form error |
| `moderate` | Slows down or confuses without blocking, simple workaround | Ambiguous label, visibly offset alignment, empty state without guidance |
| `minor` | Cosmetic or consistency issue, with no measurable impact on the task | Spacing 2 px off the scale, icon offset by 1 px |

Adjustment factors: frequency (main screen or rare), extent (one instance or a shared component), workaround, affected population. A visual defect can be critical if it hides an essential action.

## Four distinct fields

| Field | Values | Meaning |
|---|---|---|
| `severity` | critical, major, moderate, minor | Impact |
| `priority` | P1 (before validation), P2 (before production release), P3 (backlog) | Order of handling |
| `confidence` | high (reproduced, with structural evidence), medium (reproduced, presumed cause), low (observed once or heuristic judgment) | Strength of the diagnosis |
| `effort` | S, M, L | Estimated cost of the fix |

## Nature

- `[REQUIREMENT]` covers an applicable standard, an acceptance criterion, the design system or a functional contract. Can block.
- `[HYPOTHESIS]` is plausible but not demonstrated. To be verified or explicitly assumed.
- `[PREFERENCE]` is an aesthetic judgment. Never blocks on its own.

## Fix record (`report.json > fixes[]`)

```json
{
  "findings": ["DEF-012"],
  "probable_cause": "The --space-btn-x token went from 16 to 8 px and .btn has no min-width",
  "cause_established": true,
  "solution": "Restore min-width in the Button component, without touching the token used elsewhere",
  "type": "common_cause",
  "files": ["src/components/Button.css"],
  "affected_components": ["Button", "Toolbar", "DialogFooter"],
  "instances_rechecked": 14,
  "benefit": "Labels readable in every language",
  "risks": "Wider buttons, possible line wrap in DialogFooter at 320 px",
  "non_regression": ["CTA-01@320", "CTA-01@pseudo", "GEO-06@DialogFooter", "DS-05@radius"],
  "authorization": "in_scope"
}
```

`type` is `common_cause`, `local` or `declared_workaround`. `authorization` is `in_scope` or `proposal_only`.

Anti-patterns to refuse or to declare as workarounds:
- `overflow: hidden` or `text-overflow: ellipsis` on an action label without access to the full text;
- `z-index: 9999` without analyzing the stacking contexts (`transform`, `opacity < 1`, `filter`, `isolation`, `position` with `z-index`);
- reducing the font size of a shared component to make a label fit (risk for targets and readability);
- `outline: none` without a replacement focus indicator;
- a fixed pixel width on a container of translated text.

## Variants

Only offer them when there is a real trade-off: several valid solutions with different compromises, or a conflict between constraints. Two or three at most.

| Criterion | Variant A | Variant B | Variant C |
|---|---|---|---|
| Comprehension | | | |
| Efficiency (steps, time) | | | |
| Accessibility | | | |
| Consistency with the design system | | | |
| Implementation complexity | | | |
| Business and technical constraints | | | |
| Visual quality `[PREFERENCE]` | | | |
| Uncertainties | | | |

Attach a screenshot or a rendered prototype if the cost is reasonable (a branch or a temporary file, captured with `capture.py`). Recommend one option with its justification. State that the evaluation is heuristic and is no substitute for testing with users.
