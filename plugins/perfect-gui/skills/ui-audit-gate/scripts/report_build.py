#!/usr/bin/env python3
"""Pre-fill report.json from the run outputs, so only judgments remain to be written by hand.

It never overwrites an entry that already exists in report.json. It adds:
- "passed" controls whose method is fully automated and clean in every view where it ran, with their evidence;
- "not_verified" placeholders for fundamental controls that no output covers yet (reason_type "other": they must be
  judged, which keeps the decision honest until then);
- before/after pairs matched by file name between before/ and the latest after-fix-N/ (or after/);
- tools and fidelity from the capture manifests, research status from the traced references;
- the candidate list from summarize.py, to turn into DEF-xxx findings or dismiss with a reason.

Example:
  python3 report_build.py .ui-audit/RUN-x && python3 verify_report.py .ui-audit/RUN-x --apply --render
"""
import argparse
from pathlib import Path

from _common import emit, load_config, now_iso, read_json, write_json
from summarize import collect, relative

CHECK_CONTROLS = {
    "horizontal-overflow": ["GEO-01"],
    "text-overflow": ["GEO-03", "CTA-01"],
    "target-size": ["CTA-03"],
    "headings": ["TXT-02"],
    "document": ["ACC-12"],
    "landmarks": ["ACC-10"],
    "console": ["ROB-01"],
    "spacing": ["GEO-04"],
}


def passing_controls(summary):
    proposals = {}
    sources = summary["sources"]

    def propose(control, ok, evidence, how):
        current = proposals.get(control)
        if current is None:
            proposals[control] = {"ok": ok, "evidence": list(evidence), "how": how}
        else:
            current["ok"] = current["ok"] and ok
            current["evidence"] += [e for e in evidence if e not in current["evidence"]]

    for check, controls in CHECK_CONTROLS.items():
        runs = sources.get(check, [])
        if runs:
            for control in controls:
                propose(control, all(r["result"] == "clean" for r in runs), [r["file"] for r in runs], f"{check} clean in {len(runs)} views")
    pseudo = [r for r in sources.get("text-overflow", []) if any("pseudo" in v for v in r.get("variants", []))]
    if pseudo:
        propose("LOC-01", all(r["result"] == "clean" for r in pseudo), [r["file"] for r in pseudo], "text-overflow clean with pseudo-localization")
    spacing = [r for r in sources.get("text-overflow", []) if any("1.4.12" in v for v in r.get("variants", []))]
    if spacing:
        propose("TXT-04", all(r["result"] == "clean" for r in spacing), [r["file"] for r in spacing], "text-overflow clean with WCAG 1.4.12 spacing")
    scans = [r for r in sources.get("occlusion", []) if r.get("mode") == "scan"]
    if scans:
        propose("STK-01", all(r["result"] == "clean" for r in scans), [r["file"] for r in scans], "occlusion scan clean")
    axe = sources.get("axe", [])
    if axe:
        propose("ACC-01", all(r["result"] == "clean" and not r.get("incomplete") for r in axe), [r["file"] for r in axe], "axe-core clean, no incomplete rule")
    keyboard = sources.get("keyboard", [])
    if keyboard:
        propose("ACC-03", all(r.get("outcome") == "full-cycle" and "focus-trap" not in r.get("issues", []) for r in keyboard), [r["file"] for r in keyboard], "keyboard walk completed without trap")
    flows = sources.get("flow", [])
    if flows:
        propose("PAR-01", all(r["status"] == "passed" for r in flows), sorted({r["file"] for r in flows}), "all flows passed")
        keyboard_flows = [r for r in flows if r.get("keyboard_only")]
        if keyboard_flows:
            propose("ACC-02", all(r["status"] == "passed" for r in keyboard_flows), sorted({r["file"] for r in keyboard_flows}), "keyboard-only flows passed")
    return proposals


def latest_after(run):
    fixes = sorted((p for p in run.glob("after-fix-*") if p.is_dir()), key=lambda p: int(p.name.rsplit("-", 1)[-1]) if p.name.rsplit("-", 1)[-1].isdigit() else 0)
    return fixes[-1] if fixes else (run / "after" if (run / "after").is_dir() else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    args = parser.parse_args()
    run = Path(args.run)
    report = read_json(run / "report.json")
    if report is None:
        emit({"status": "error", "error": f"{run / 'report.json'} not found: run init_run.py first"}, 2)
    summary = collect(run)
    write_json(run / "summary.json", summary)
    existing = {c["id"] for c in report.get("controls", [])}
    added_passed, added_placeholders, not_passing = [], [], []
    for control, proposal in sorted(passing_controls(summary).items()):
        if control in existing:
            continue
        if proposal["ok"]:
            report.setdefault("controls", []).append({"id": control, "status": "passed", "evidence": proposal["evidence"], "note": f"pre-filled by report_build: {proposal['how']}"})
            existing.add(control)
            added_passed.append(control)
        else:
            not_passing.append(control)
    for control in load_config("levels.json")["fundamental"]:
        if control not in existing:
            report.setdefault("controls", []).append({"id": control, "status": "not_verified", "reason": "no automated output covers it yet: judge it (passed with evidence, failed with a finding, or not_applicable with a reason)", "reason_type": "other"})
            existing.add(control)
            added_placeholders.append(control)

    pairs_added = 0
    after_dir = latest_after(run)
    known_pairs = {(p.get("before"), p.get("after")) for p in report.get("before_after", [])}
    if after_dir and (run / "before").is_dir():
        for after in sorted(after_dir.rglob("*.png")):
            rel = after.relative_to(after_dir)
            before = run / "before" / rel
            if not before.exists() or "manifests" in rel.parts:
                continue
            pair = (relative(run, before), relative(run, after))
            if pair in known_pairs:
                continue
            diff = next((d for d in run.glob(f"diff*/{rel.as_posix()}") if d.is_file()), None)
            report.setdefault("before_after", []).append({"config_id": rel.parts[0] if len(rel.parts) > 1 else None, "before": pair[0], "after": pair[1],
                                                           "diff": relative(run, diff) if diff else None, "comment": "to qualify: expected change or regression"})
            known_pairs.add(pair)
            pairs_added += 1

    engines = sorted({(read_json(m, {}) or {}).get("engine") for m in run.rglob("manifests/*.json")} - {None})
    environment = report.setdefault("environment", {"tools": [], "fidelity": "emulation"})
    for engine in engines:
        if engine not in environment.setdefault("tools", []):
            environment["tools"].append(engine)
    references = read_json(run / "research" / "references.json", []) or []
    research = report.setdefault("research", {"status": "not_done", "cause": "not done yet"})
    if research.get("status") == "not_done" and research.get("cause") == "not done yet" and any(r.get("access_status") in ("accessed", "revalidated") for r in references):
        report["research"] = {"status": "done", "cause": None}
    report["candidates"] = [{k: c[k] for k in ("id", "check", "kind", "selector", "severity_hint", "views", "evidence", "controls")} for c in summary["candidates"]]
    report["prefilled_at"] = now_iso()
    write_json(run / "report.json", report)
    emit({
        "tool": "report_build", "report": str(run / "report.json"),
        "controls_passed_added": added_passed, "fundamental_placeholders": added_placeholders,
        "controls_with_issues": not_passing, "before_after_pairs_added": pairs_added,
        "candidates": len(summary["candidates"]),
        "next": "Confirm each candidate (DEF-xxx finding or dismissal), judge the placeholders, then verify_report.py --apply --render",
    })


if __name__ == "__main__":
    main()
