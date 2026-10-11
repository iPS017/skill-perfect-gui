#!/usr/bin/env python3
"""Check the consistency of an audit report, compute the decision (reference/validation-gate.md)
and produce report.md.

Exit codes: 0 consistent, 1 inconsistencies, 2 missing files.

Examples:
  python3 verify_report.py .ui-audit/RUN-x
  python3 verify_report.py .ui-audit/RUN-x --apply --render
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_config, now_iso, read_json, ui_snapshot, write_json  # noqa: E402

EVIDENCE_INDEX = {}


def closest_evidence(run, proof):
    import difflib

    key = str(run)
    if key not in EVIDENCE_INDEX:
        EVIDENCE_INDEX[key] = [p.relative_to(run).as_posix() for p in Path(run).rglob("*") if p.is_file()]
    matches = difflib.get_close_matches(str(proof), EVIDENCE_INDEX[key], n=1, cutoff=0.6)
    return f" (closest existing file: {matches[0]})" if matches else ""

DECISIONS = ["VALIDATED_FULL_PROTOCOL", "VALIDATED_TESTED_SCOPE", "VALIDATED_WITH_EXCEPTIONS", "NOT_VALIDATED", "LIMITED_VALIDATION"]
DECISION_LABELS = {
    "VALIDATED_FULL_PROTOCOL": "VALIDATED: full protocol",
    "VALIDATED_TESTED_SCOPE": "VALIDATED: tested scope only",
    "VALIDATED_WITH_EXCEPTIONS": "VALIDATED with accepted exceptions",
    "NOT_VALIDATED": "NOT VALIDATED",
    "LIMITED_VALIDATION": "LIMITED VALIDATION",
}
STATUSES = {"passed", "failed", "not_verified", "not_applicable"}
REASON_TYPES = {"technical", "human", "real_device", "out_of_scope", "other"}
SEVERITIES = {"critical", "major", "moderate", "minor"}
FINDING_STATUSES = {"open", "fixed", "failed_unresolved", "accepted_exception"}
OPEN_STATUSES = {"open", "failed_unresolved", "accepted_exception"}
NATURES = {"REQUIREMENT", "HYPOTHESIS", "PREFERENCE"}
FINDING_FIELDS = ["id", "title", "control", "severity", "priority", "confidence", "nature", "status", "expected", "observed", "evidence"]


def normalize(url):
    parsed = urlparse(url.strip())
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}" + (f"?{parsed.query}" if parsed.query else "")


def normalize_nature(value):
    return str(value or "").strip().strip("[]").strip().upper()


def exists(run, path):
    p = Path(path)
    return (p if p.is_absolute() else run / p).exists()


def load_findings(run, report):
    merged = {}
    for finding in report.get("findings", []):
        if isinstance(finding, dict) and finding.get("id"):
            merged[finding["id"]] = finding
    for path in sorted((run / "findings").glob("*.json")) if (run / "findings").exists() else []:
        data = read_json(path)
        if isinstance(data, dict) and data.get("id"):
            merged.setdefault(data["id"], {}).update(data)
    return list(merged.values())


def verify(run):
    run = Path(run)
    report = read_json(run / "report.json")
    if report is None:
        return {"status": "missing", "errors": [f"report.json missing in {run}"]}
    errors, warnings, blocking, downgrades = [], [], [], []
    levels = load_config("levels.json")
    fundamentals = set(levels["fundamental"])
    mode = report.get("mode", "full")
    limited = mode in ("mockup", "no_execution")

    controls = {}
    for control in report.get("controls", []):
        cid = control.get("id")
        if not cid:
            errors.append("Control without an id")
            continue
        if cid in controls:
            warnings.append(f"{cid} listed several times: the last entry is kept")
        controls[cid] = control
        status = control.get("status")
        if status not in STATUSES:
            errors.append(f"{cid}: invalid status {status!r} (expected {sorted(STATUSES)})")
            continue
        if status == "passed":
            proofs = control.get("evidence") or []
            if not proofs:
                errors.append(f"{cid}: 'passed' without evidence")
            for proof in proofs:
                if not exists(run, proof):
                    errors.append(f"{cid}: evidence not found {proof}{closest_evidence(run, proof)}")
        if status in ("not_verified", "not_applicable") and not control.get("reason"):
            errors.append(f"{cid}: '{status}' without a reason")
        if status == "not_verified" and control.get("reason_type") not in REASON_TYPES:
            errors.append(f"{cid}: reason_type missing or invalid (expected {sorted(REASON_TYPES)})")

    findings = load_findings(run, report)
    finding_controls = {f.get("control") for f in findings}
    for cid, control in controls.items():
        if control.get("status") == "failed" and cid not in finding_controls:
            errors.append(f"{cid}: 'failed' without a finding that references it")

    exceptions_used = []
    for finding in findings:
        fid = finding.get("id", "?")
        missing = [f for f in FINDING_FIELDS if finding.get(f) in (None, "", [])]
        if missing:
            errors.append(f"{fid}: missing fields {missing}")
        if finding.get("severity") not in SEVERITIES:
            errors.append(f"{fid}: invalid severity {finding.get('severity')!r}")
        if finding.get("status") not in FINDING_STATUSES:
            errors.append(f"{fid}: invalid status {finding.get('status')!r}")
        nature = normalize_nature(finding.get("nature"))
        if nature not in NATURES:
            errors.append(f"{fid}: invalid nature {finding.get('nature')!r} (REQUIREMENT, HYPOTHESIS, PREFERENCE)")
        for proof in finding.get("evidence") or []:
            if not exists(run, proof):
                errors.append(f"{fid}: evidence not found {proof}{closest_evidence(run, proof)}")
        status = finding.get("status")
        if status == "fixed":
            retest = finding.get("retest") or {}
            if retest.get("status") != "passed" or not retest.get("evidence"):
                errors.append(f"{fid}: 'fixed' without a passed retest backed by evidence")
            for proof in retest.get("evidence") or []:
                if not exists(run, proof):
                    errors.append(f"{fid}: retest evidence not found {proof}{closest_evidence(run, proof)}")
        if status == "failed_unresolved" and not (finding.get("blocking_cause") and finding.get("required_action")):
            errors.append(f"{fid}: 'failed_unresolved' requires blocking_cause and required_action")
        if status not in OPEN_STATUSES:
            continue
        severity = finding.get("severity")
        if severity == "critical":
            blocking.append(f"B1: open critical finding {fid}")
            if status == "accepted_exception":
                errors.append(f"{fid}: an exception cannot cover a critical finding")
        elif severity == "major" and nature == "REQUIREMENT":
            exception = finding.get("exception") or {}
            valid = status == "accepted_exception" and all(exception.get(k) for k in ("accepted_by", "date", "quote"))
            if valid:
                exceptions_used.append(fid)
            else:
                blocking.append(f"B2: open major [REQUIREMENT] finding without a valid exception {fid}")
                if status == "accepted_exception":
                    errors.append(f"{fid}: incomplete exception (accepted_by, date, quote from the user)")
        if finding.get("introduced_by_fix"):
            blocking.append(f"B6: open regression introduced by a fix {fid}")

    for cid in sorted(fundamentals):
        control = controls.get(cid)
        if control is None:
            blocking.append(f"B3: fundamental control missing from the report {cid}")
        elif control.get("status") == "not_verified" and control.get("reason_type") not in ("technical", "human", "real_device"):
            blocking.append(f"B3: fundamental control not verified without a technical reason {cid}")

    if not limited:
        main_path = controls.get("PAR-01")
        if main_path and main_path.get("status") == "not_applicable":
            warnings.append("PAR-01 not applicable: justify it in the report")
        elif not main_path or main_path.get("status") != "passed":
            blocking.append("B4: main flow (PAR-01) not passed")

    if report.get("visual_change", True) and not limited:
        pairs = [p for p in report.get("before_after", []) if p.get("after") and exists(run, p["after"])]
        for pair in report.get("before_after", []):
            for key in ("before", "after", "diff"):
                if pair.get(key) and not exists(run, pair[key]):
                    errors.append(f"before_after: file not found {pair[key]}")
        if not pairs:
            blocking.append("B5: visual change without an existing after (before/after) capture")
        elif report.get("fixes") and not any("after-fix" in p["after"] for p in pairs):
            blocking.append("B5: fixes applied without re-capture in an after-fix-* folder")

    log = read_json(run / "research" / "log.json", []) or []
    refs = read_json(run / "research" / "references.json", []) or []
    seen = {normalize(entry["url"]) for entry in log if entry.get("type") == "visit" and not entry.get("failed") and entry.get("url")}
    valid_refs = []
    for ref in refs:
        if ref.get("access_status") in ("accessed", "revalidated"):
            if normalize(ref.get("url", "")) not in seen:
                errors.append(f"{ref.get('id', '?')}: URL missing from the research log (reference not traced or fabricated) {ref.get('url')}")
            else:
                valid_refs.append(ref)
    research = report.get("research") or {}
    research_status = research.get("status")
    if research_status not in ("done", "partial", "not_done"):
        errors.append(f"research.status invalid {research_status!r}")
    if research_status in ("done", "partial") and not valid_refs:
        errors.append("research declared done without any accessed and traced reference")
    if research_status == "not_done" and not research.get("cause"):
        errors.append("research not done without a cause")
    if research_status != "done":
        downgrades.append(f"Web research: {research_status}")
    max_refs = levels["max_references"].get(report.get("level", "N1"), 5)
    if len(valid_refs) > max_refs:
        warnings.append(f"{len(valid_refs)} references for an indicative cap of {max_refs}: justify them or remove decorative links")
    compared = {c.get("ref") for c in report.get("comparisons", [])}
    for ref in valid_refs:
        if ref.get("id") not in compared:
            warnings.append(f"{ref.get('id')} kept without a comparison row")

    human_checks = []
    for cid, control in controls.items():
        if control.get("status") != "not_verified":
            continue
        if control.get("reason_type") in ("human", "real_device"):
            human_checks.append(f"{cid} ({control.get('reason_type')}): {control.get('reason')}")
        else:
            downgrades.append(f"{cid} not verified ({control.get('reason_type')})")
    if report.get("reduced_coverage"):
        downgrades.append("reduced coverage: " + str(report.get("reduction_justification") or "justification missing"))
        if not report.get("reduction_justification"):
            errors.append("reduced_coverage without reduction_justification")
    if not exists(run, report.get("coverage") or "coverage.json"):
        warnings.append("coverage.json missing: list the executed and excluded combinations")

    if blocking:
        decision = "NOT_VALIDATED"
    elif limited:
        decision = "LIMITED_VALIDATION"
    elif exceptions_used:
        decision = "VALIDATED_WITH_EXCEPTIONS"
    elif downgrades:
        decision = "VALIDATED_TESTED_SCOPE"
    else:
        decision = "VALIDATED_FULL_PROTOCOL"

    written = report.get("decision")
    if written is None:
        warnings.append("decision missing from the report (use --apply)")
    elif written not in DECISIONS:
        errors.append(f"decision invalid {written!r}")
    elif written != decision:
        errors.append(f"decision written {written} differs from the computed decision {decision}")

    return {
        "status": "ok" if not errors else "inconsistent",
        "run": str(run),
        "computed_decision": decision,
        "written_decision": written,
        "blocking": blocking,
        "downgrades": downgrades,
        "exceptions": exceptions_used,
        "human_checks": human_checks,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "valid_references": valid_refs,
    }


def bullet(items, empty="None."):
    return "\n".join(f"- {i}" for i in items) if items else empty


def render(run, report, result):
    run = Path(run)
    findings = result["findings"]
    counts = {s: sum(1 for f in findings if f.get("severity") == s) for s in ["critical", "major", "moderate", "minor"]}
    open_counts = {s: sum(1 for f in findings if f.get("severity") == s and f.get("status") in OPEN_STATUSES) for s in counts}
    controls = report.get("controls", [])
    by_status = {s: [c["id"] for c in controls if c.get("status") == s] for s in ["passed", "failed", "not_verified", "not_applicable"]}
    lines = [
        f"# UI audit: {report.get('title', '')} ({report.get('run_id', run.name)})",
        "",
        f"## Decision: {DECISION_LABELS[result['computed_decision']]}",
        "",
        f"Findings: {counts['critical']} critical, {counts['major']} major, {counts['moderate']} moderate, {counts['minor']} minor. "
        f"Still open: {open_counts['critical']} / {open_counts['major']} / {open_counts['moderate']} / {open_counts['minor']}.",
        "",
        "Blocking conditions:",
        bullet(result["blocking"]),
        "",
        "What limits the validation:",
        bullet(result["downgrades"]),
        "",
        "> No detected finding does not mean no finding. This decision only holds for the scope, configurations and controls listed below.",
        "",
        "## Scope",
        "",
        f"- Request: {report.get('request') or 'not provided'}",
        f"- Goal: {report.get('goal') or 'not provided'}",
        f"- Zones: {', '.join(report.get('scope', {}).get('zones', [])) or 'not provided'}",
        f"- Impact radius: {', '.join(report.get('scope', {}).get('impact_radius', [])) or 'not provided'}",
        f"- Level: {report.get('level')} (computed: {report.get('computed_level')})" + (f", reduced coverage: {report.get('reduction_justification')}" if report.get("reduced_coverage") else ""),
        f"- Mode: {report.get('mode')}; baseline: {report.get('baseline')}; trigger: {report.get('trigger')}",
        "",
        "Acceptance criteria:",
        bullet(report.get("acceptance_criteria", [])),
        "",
        "## Assumptions",
        "",
    ]
    assumptions = report.get("assumptions", [])
    if assumptions:
        lines += ["| Assumption | Source | Impact if wrong |", "|---|---|---|"]
        lines += [f"| {a.get('assumption', '')} | {a.get('source', '')} | {a.get('impact_if_wrong', '')} |" for a in assumptions]
    else:
        lines.append("None.")
    env = report.get("environment", {})
    lines += ["", "## Environment", "", f"- Tools: {', '.join(env.get('tools', [])) or 'not provided'}", f"- Fidelity: {env.get('fidelity', 'not provided')}", ""]
    research = report.get("research", {})
    lines += ["## References consulted", "", f"Research status: {research.get('status')}" + (f" ({research.get('cause')})" if research.get("cause") else ""), ""]
    refs = result["valid_references"]
    if refs:
        lines += ["| Ref. | Title | Organization | Accessed on | Published or updated | Question | Limits |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {r['id']} | [{r['title']}]({r['url']}) | {r.get('author_organization', '')} | {r.get('accessed_at', '')} | {r.get('published_or_updated') or 'not stated'} | {r.get('question', '')} | {r.get('transfer_limits', '')} |" for r in refs]
    comparisons = report.get("comparisons", [])
    if comparisons:
        lines += ["", "| Ref. | Observation | Principle | Gap | Adaptation | Benefit | Nature |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {c.get('ref')} | {c.get('observation', '')} | {c.get('principle', '')} | {c.get('gap', '')} | {c.get('adaptation', '')} | {c.get('benefit', '')} | {c.get('nature', '')} |" for c in comparisons]
    lines += ["", "## Coverage", "", "| Status | Controls |", "|---|---|"]
    lines += [f"| {s} | {', '.join(ids) or '-'} |" for s, ids in by_status.items()]
    coverage = read_json(run / (report.get("coverage") or "coverage.json"), {}) or {}
    lines += ["", f"Combinations executed: {len(coverage.get('executed', []))}; excluded: {len(coverage.get('excluded', []))}."]
    for excluded in coverage.get("excluded", [])[:30]:
        if isinstance(excluded, dict):
            lines.append(f"- Excluded: {excluded.get('combination')}; reason: {excluded.get('reason')}; risk: {excluded.get('risk')}")
    non_verified = [c for c in controls if c.get("status") == "not_verified"]
    if non_verified:
        lines += ["", "Not verified:"]
        lines += [f"- {c['id']} ({c.get('reason_type')}): {c.get('reason')}" for c in non_verified]
    lines += ["", "## Findings", ""]
    order = {"critical": 0, "major": 1, "moderate": 2, "minor": 3}
    for f in sorted(findings, key=lambda x: (order.get(x.get("severity"), 9), x.get("id", ""))):
        lines += [
            f"### {f.get('id')}: {f.get('title')}",
            "",
            f"- Control: {f.get('control')}; screen or component: {f.get('screen_component', '')}",
            f"- Severity: {f.get('severity')}; priority: {f.get('priority')}; confidence: {f.get('confidence')}; effort: {f.get('effort', '')}; nature: [{f.get('nature')}]",
            f"- Status: {f.get('status')}" + (" (regression introduced by a fix)" if f.get("introduced_by_fix") else ""),
            f"- Preconditions: {f.get('preconditions', '')}; data: {f.get('data', '')}; configuration: {f.get('config_id', '')}",
            "- Steps: " + "; ".join(f.get("steps", [])),
            f"- Expected: {f.get('expected')}",
            f"- Observed: {f.get('observed')}",
            f"- Interpretation: {f.get('interpretation', '')}",
            "- Evidence: " + ", ".join(f.get("evidence", [])),
        ]
        if f.get("retest"):
            lines.append(f"- Retest: {f['retest'].get('status')} ({', '.join(f['retest'].get('evidence', []))})")
        if f.get("exception"):
            e = f["exception"]
            lines.append(f"- Exception accepted by {e.get('accepted_by')} on {e.get('date')}: \"{e.get('quote')}\"; due {e.get('due', 'not set')}")
        if f.get("blocking_cause"):
            lines.append(f"- Unresolved: {f.get('blocking_cause')}; required action: {f.get('required_action')}")
        lines.append("")
    if not findings:
        lines += ["No finding recorded.", ""]
    variants = report.get("variants", [])
    if variants:
        lines += ["## Variants", "", "```json", json.dumps(variants, ensure_ascii=False, indent=2), "```", ""]
    fixes = report.get("fixes", [])
    lines += ["## Fixes", ""]
    if fixes:
        lines += ["| Findings | Cause | Solution | Type | Files | Instances rechecked |", "|---|---|---|---|---|---|"]
        lines += [f"| {', '.join(c.get('findings', []))} | {c.get('probable_cause', '')} | {c.get('solution', '')} | {c.get('type', '')} | {', '.join(c.get('files', []))} | {c.get('instances_rechecked', '')} |" for c in fixes]
    else:
        lines.append("None.")
    lines += ["", "## Before / after", ""]
    pairs = report.get("before_after", [])
    if pairs:
        lines += ["| Configuration | Before | After | Diff | Comment |", "|---|---|---|---|---|"]
        lines += [f"| {p.get('config_id', '')} | {p.get('before', '')} | {p.get('after', '')} | {p.get('diff', '')} | {p.get('comment', '')} |" for p in pairs]
    else:
        lines.append("No pair.")
    lines += ["", "## Regressions", "", bullet([f"{r.get('control')}: {r.get('result')}" for r in report.get("regressions", [])]), ""]
    lines += ["## Limitations and human checks", "", bullet(report.get("limitations", []) + result["human_checks"] + report.get("human_checks", [])), ""]
    if result["warnings"]:
        lines += ["## Verifier warnings", "", bullet(result["warnings"]), ""]
    lines += [f"_Report generated on {now_iso()} by verify_report.py._", ""]
    (run / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return str(run / "report.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    parser.add_argument("--apply", action="store_true", help="Write the computed decision if everything else is consistent")
    parser.add_argument("--render", action="store_true", help="Produce report.md")
    args = parser.parse_args()

    result = verify(args.run)
    if result["status"] == "missing":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(2)
    run = Path(args.run)
    if args.apply:
        decision_errors = [e for e in result["errors"] if e.startswith("decision")]
        other_errors = [e for e in result["errors"] if not e.startswith("decision")]
        if not other_errors:
            report = read_json(run / "report.json")
            report["decision"] = result["computed_decision"]
            report["verified_at"] = now_iso()
            write_json(run / "report.json", report)
            result = verify(args.run)
            result["applied"] = True
            project = run.resolve().parent.parent
            if run.resolve().parent.name == ".ui-audit":
                write_json(project / ".ui-audit" / "snapshot.json", ui_snapshot(project))
                result["snapshot"] = "UI files snapshot saved: the next audit compares against this audited state"
        else:
            result["applied"] = False
            result["apply_refused"] = "inconsistencies to fix before writing the decision"
            if decision_errors:
                result["errors"] = other_errors + decision_errors
    if args.render:
        result["report_md"] = render(run, read_json(run / "report.json"), result)
    output = {k: v for k, v in result.items() if k not in ("findings", "valid_references")}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
