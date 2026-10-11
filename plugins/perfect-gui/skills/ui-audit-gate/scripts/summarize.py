#!/usr/bin/env python3
"""Aggregate every output of a run (inspect.json, keyboard.json, flows.json, diff.json, resize outputs) into one
deduplicated list of candidates (same check, kind and selector across views and sizes) plus a per-check matrix.

Example:
  python3 summarize.py .ui-audit/RUN-x            -> RUN-x/summary.json and RUN-x/summary.md
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from _common import emit, now_iso, read_json, write_json

SEVERITY_HINT = {
    "occlusion": "critical", "horizontal-overflow": "major", "text-overflow": "major", "contrast": "major",
    "form-errors": "major", "accessible-names": "major", "form-labels": "major", "spacing": "moderate",
    "target-size": "moderate", "images": "moderate", "alignment": "minor", "headings": "moderate",
    "document": "moderate", "landmarks": "minor", "axe": "major", "console": "moderate",
    "keyboard": "major", "flow": "major", "resize": "major", "visual-diff": "to-review",
}


def relative(run, path):
    try:
        return Path(path).resolve().relative_to(Path(run).resolve()).as_posix()
    except (ValueError, TypeError):
        return str(path)


def collect(run):
    run = Path(run)
    candidates = {}
    matrix = defaultdict(dict)
    sources = defaultdict(list)

    def add(check, kind, selector, view, item, evidence, controls):
        key = (check, kind or "", selector or "")
        entry = candidates.setdefault(key, {
            "check": check, "kind": kind, "selector": selector, "controls": controls or [],
            "severity_hint": SEVERITY_HINT.get(check, "moderate"), "views": [], "evidence": [], "sample": item,
        })
        if view not in entry["views"]:
            entry["views"].append(view)
        for proof in evidence:
            if proof and proof not in entry["evidence"]:
                entry["evidence"].append(proof)

    for path in sorted(run.rglob("inspect.json")):
        report = read_json(path, {}) or {}
        view = report.get("config_id") or path.parent.name
        variants = report.get("variants", [])
        label = view + (f" [{', '.join(variants)}]" if variants else "")
        proof = [relative(run, path)] + ([relative(run, report["annotated"])] if report.get("annotated") else [])
        for check, data in (report.get("checks") or {}).items():
            matrix[check][label] = data.get("result")
            sources[check].append({"file": relative(run, path), "view": label, "result": data.get("result"), "variants": variants,
                                   "mode": data.get("mode"), "incomplete": len(data.get("incomplete", [])) if check == "axe" else None})
            if data.get("result") != "issues":
                continue
            items = data.get("items") or data.get("violations") or []
            for item in items:
                if check == "text-overflow" and not item.get("candidate", True):
                    continue
                if check == "occlusion" and item.get("state") in ("clear", "covered-at-some-positions", "partially-covered"):
                    continue
                selector = item.get("selector") or item.get("id") or json.dumps(item.get("target") or item.get("nodes", [{}])[0].get("target", ""))
                add(check, item.get("kind") or item.get("state") or item.get("id"), selector, label, item, proof, data.get("controls"))

    for path in sorted(run.rglob("keyboard.json")):
        report = read_json(path, {}) or {}
        view = report.get("config_id") or path.parent.name
        matrix["keyboard"][view] = report.get("result")
        sources["keyboard"].append({"file": relative(run, path), "view": view, "result": report.get("result"), "outcome": report.get("outcome"),
                                    "issues": [i.get("kind") for i in report.get("issues", [])]})
        for issue in report.get("issues", []):
            if issue.get("level") == "info":
                continue
            add("keyboard", issue.get("kind"), issue.get("selector") or issue.get("dialog") or "page", view, issue, [relative(run, path)], issue.get("controls"))

    for path in sorted(run.rglob("flows.json")):
        report = read_json(path, {}) or {}
        for flow in report.get("flows", []):
            view = flow.get("config_id")
            name = f"{flow.get('flow')}{' (keyboard only)' if flow.get('keyboard_only') else ''}"
            matrix["flow"][f"{name} @ {view}"] = "clean" if flow.get("status") == "passed" else "issues"
            sources["flow"].append({"file": relative(run, path), "view": view, "flow": flow.get("flow"), "keyboard_only": flow.get("keyboard_only"), "status": flow.get("status")})
            if flow.get("status") != "passed":
                last = flow["steps"][-1] if flow.get("steps") else {}
                add("flow", "failed-step", name, view, last, [relative(run, path)] + ([relative(run, last["screenshot"])] if last.get("screenshot") else []), ["PAR-01"])

    for path in sorted(run.rglob("diff.json")):
        report = read_json(path, {}) or {}
        for item in report.get("items", []):
            view = item.get("config_id") or "unknown"
            matrix["visual-diff"][f"{item.get('name') or item.get('file')} @ {view}"] = "issues" if item.get("flagged") or str(item.get("status", "")).startswith("missing") else "clean"
            if item.get("flagged") or str(item.get("status", "")).startswith("missing"):
                add("visual-diff", item.get("status"), item.get("file"), view, item, [relative(run, path)] + ([relative(run, item["diff_image"])] if item.get("diff_image") else []), ["DS-05"])

    for path in sorted(run.rglob("*.json")):
        report = read_json(path, None)
        if not isinstance(report, dict) or report.get("tool") != "resize_probe":
            continue
        for config in report.get("configs", []):
            view = f"{config.get('config_id')} ({report.get('mode')})"
            matrix["resize"][view] = config.get("result")
            sources["resize"].append({"file": relative(run, path), "view": view, "mode": report.get("mode"), "result": config.get("result")})
            for issue in config.get("issues", []):
                add("resize", issue.get("kind"), json.dumps(issue.get("items") or issue.get("containers") or issue.get("width")), view, issue, [relative(run, path)], issue.get("controls"))

    ordered = sorted(candidates.values(), key=lambda c: (["critical", "major", "moderate", "minor", "to-review"].index(c["severity_hint"]) if c["severity_hint"] in ("critical", "major", "moderate", "minor", "to-review") else 9, c["check"], -len(c["views"])))
    for number, candidate in enumerate(ordered, 1):
        candidate["id"] = f"C-{number:03d}"
    return {"tool": "summarize", "created_at": now_iso(), "run": str(run), "candidates": ordered,
            "matrix": {check: dict(views) for check, views in matrix.items()}, "sources": dict(sources)}


def render(summary, path):
    lines = [f"# Summary of automated outputs: {Path(summary['run']).name}", "",
             f"{len(summary['candidates'])} distinct candidates (deduplicated across views and sizes). Candidates are not findings: confirm each one, then write a DEF-xxx record.", ""]
    lines += ["| Id | Check | Kind | Selector | Severity hint | Views | Evidence |", "|---|---|---|---|---|---|---|"]
    for c in summary["candidates"]:
        lines.append(f"| {c['id']} | {c['check']} | {c['kind'] or ''} | `{(c['selector'] or '')[:70]}` | {c['severity_hint']} | {len(c['views'])}: {', '.join(c['views'][:3])}{'...' if len(c['views']) > 3 else ''} | {', '.join(c['evidence'][:2])} |")
    lines += ["", "## Results per check and view", ""]
    for check, views in summary["matrix"].items():
        issues = [v for v, r in views.items() if r == "issues"]
        lines.append(f"- {check}: {len(views) - len(issues)} clean, {len(issues)} with issues" + (f" ({', '.join(issues[:4])})" if issues else ""))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    args = parser.parse_args()
    summary = collect(args.run)
    write_json(Path(args.run) / "summary.json", summary)
    render(summary, Path(args.run) / "summary.md")
    emit({"tool": "summarize", "summary": str(Path(args.run) / "summary.json"), "markdown": str(Path(args.run) / "summary.md"),
          "candidates": len(summary["candidates"]),
          "by_check": {check: sum(1 for c in summary["candidates"] if c["check"] == check) for check in sorted({c["check"] for c in summary["candidates"]})}})


if __name__ == "__main__":
    main()
