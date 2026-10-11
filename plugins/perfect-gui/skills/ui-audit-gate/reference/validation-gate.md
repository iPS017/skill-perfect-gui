# Validation gate

`verify_report.py` applies exactly these rules. When in doubt, the script is authoritative, and any discrepancy between the script and this document is a bug to report.

## Control statuses (`controls[].status`)

| Status | Condition | Required fields |
|---|---|---|
| `passed` | Method fully executed, compliant result, evidence kept | `evidence` (existing files) |
| `failed` | Executed, not compliant | At least one finding record that references the control |
| `not_verified` | Not executed or inconclusive | `reason`, `reason_type` |
| `not_applicable` | The context does not lend itself to it | Factual `reason` ("no form in the scope") |

`reason_type` takes one of these values:
- `technical` for a missing tool or an impossible capture;
- `human` for a real screen reader, a brand judgment or a user test;
- `real_device` for a hinge, a native keyboard or sensors;
- `out_of_scope` for a declared coverage reduction;
- `other`.

`not_applicable` is not used to hide a `not_verified`. "No time" is not a reason for non-applicability.

## Blocking conditions

| Code | Condition |
|---|---|
| B1 | A `critical` finding is open (`open`, `failed_unresolved`, or `accepted_exception`, since a critical finding cannot be covered by an exception) |
| B2 | A `major` finding of nature `REQUIREMENT` is open without a valid exception |
| B3 | A fundamental control (`config/levels.json`) is missing from the report, or is `not_verified` with a `reason_type` other than `technical`, `human` or `real_device` |
| B4 | PAR-01 (main user flow) is not `passed`, in full mode. `not_applicable` is tolerated with a reason and produces a warning. |
| B5 | Visual change without a before/after pair whose "after" screenshot exists. If fixes were applied, at least one "after" screenshot must have been taken in an `after-fix-*` folder. |
| B6 | A regression introduced by a fix (`introduced_by_fix: true`) is open |

## Decision

```text
if B1 or B3 or B4 or B5 or B6, or B2 not covered by an exception:
    NOT_VALIDATED
else if mode in {mockup, no_execution}:
    LIMITED_VALIDATION
else if a major REQUIREMENT finding is covered by an exception:
    VALIDATED_WITH_EXCEPTIONS
else if research.status != "done"
     or a required control is not_verified with reason_type in {technical, out_of_scope, other}
     or reduced_coverage:
    VALIDATED_TESTED_SCOPE
else:
    VALIDATED_FULL_PROTOCOL
```

`not_verified` controls of type `human` or `real_device` do not lower the decision. They are listed in `human_checks` and in the final message.

`VALIDATED_FULL_PROTOCOL` means the protocol was fully followed at the required level. It does not mean that no defect exists. The report says so.

## Consistency checked by the script

- Each `passed` has evidence whose files exist (paths relative to the run or absolute).
- Each `failed` is referenced by a finding record.
- Each `fixed` finding has `retest.status = "passed"` with existing evidence.
- Each `accessed` or `revalidated` reference has its URL in `research/log.json`. A missing URL is treated as fabricated and makes the report invalid.
- `research.status = "done"` requires at least one valid reference. `not_done` requires a cause.
- An exception requires `accepted_by`, `date` and an explicit request from the user (`quote`). The agent never grants itself one.
- The written decision must equal the computed decision. `--apply` writes the computed decision only if everything else is consistent.

## Residual findings and exceptions

- Remaining moderate and minor findings are listed with their priority. They do not block, unless the project requires otherwise.
- Exception on a major `REQUIREMENT` finding: only if the user explicitly accepts it in the conversation. Record `{"accepted_by": "user", "date": "...", "quote": "<their words>", "due": "..."}`.
- Open exceptions are brought up again in later audits (`.ui-audit/exceptions.json`).
