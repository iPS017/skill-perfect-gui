#!/usr/bin/env python3
"""Create an audit folder .ui-audit/RUN-<date>-<slug>/ with its skeleton files.

Example:
  python3 init_run.py --slug checkout-footer --level N2 --trigger C2
"""
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

from _common import SKILL_DIR, emit, now_iso, safe_name, write_json


def ensure_gitignore(root):
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "git unavailable"
    if top.returncode != 0:
        return "not a git repository"
    gitignore = Path(top.stdout.strip()) / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if any(line.strip() in (".ui-audit", ".ui-audit/", "/.ui-audit", "/.ui-audit/") for line in lines):
        return "already ignored"
    with gitignore.open("a", encoding="utf-8") as handle:
        handle.write(("\n" if lines and lines[-1].strip() else "") + "# UI audit evidence (local screenshots)\n.ui-audit/\n")
    return f"added to {gitignore}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--root", default=".", help="Root of the audited project")
    parser.add_argument("--title", default="")
    parser.add_argument("--level", default="N1", choices=["N1", "N2", "N3"])
    parser.add_argument("--mode", default="full", choices=["full", "mockup", "no_execution"])
    parser.add_argument("--trigger", default="C1", choices=["C1", "C2", "C3"], help="C1 semantic, C2 explicit command, C3 hook or CI")
    parser.add_argument("--no-gitignore", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_name(args.slug)}"
    run = root / ".ui-audit" / run_id
    for sub in ["before", "after", "inspect", "keyboard", "diff", "findings", "research", "traces"]:
        (run / sub).mkdir(parents=True, exist_ok=True)

    scope_template = (SKILL_DIR / "templates" / "scope.md").read_text(encoding="utf-8")
    (run / "scope.md").write_text(scope_template.replace("{{RUN_ID}}", run_id).replace("{{DATE}}", now_iso()), encoding="utf-8")
    write_json(run / "research" / "log.json", [])
    write_json(run / "research" / "references.json", [])
    write_json(run / "coverage.json", {"executed": [], "excluded": []})
    write_json(run / "report.json", {
        "run_id": run_id,
        "title": args.title or args.slug,
        "created_at": now_iso(),
        "trigger": args.trigger,
        "request": "",
        "goal": "",
        "acceptance_criteria": [],
        "scope": {"zones": [], "impact_radius": []},
        "level": args.level,
        "computed_level": args.level,
        "reduced_coverage": False,
        "reduction_justification": None,
        "mode": args.mode,
        "baseline": "before",
        "environment": {"tools": [], "fidelity": "emulation"},
        "assumptions": [],
        "research": {"status": "not_done", "cause": "not done yet"},
        "comparisons": [],
        "visual_change": True,
        "controls": [],
        "findings": [],
        "fixes": [],
        "variants": [],
        "before_after": [],
        "regressions": [],
        "coverage": "coverage.json",
        "limitations": [],
        "human_checks": [],
        "decision": None,
    })
    gitignore = "unchanged (--no-gitignore)" if args.no_gitignore else ensure_gitignore(root)
    emit({"tool": "init_run", "run": str(run), "run_id": run_id, "gitignore": gitignore,
          "next": "probe.py --out RUN/capabilities.json then impact_scan.py --out RUN/impact.json"})


if __name__ == "__main__":
    main()
