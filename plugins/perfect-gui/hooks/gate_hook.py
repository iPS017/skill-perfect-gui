#!/usr/bin/env python3
"""ui-audit-gate Stop hook: blocks the end of the turn once if interface files were
changed in the git repository without a more recent consistent audit report.

Settings: variable UI_AUDIT_GATE=block|warn|off, or .ui-audit/config.json
{"gate": {"mode": "block", "include": ["*.tpl"], "exclude": ["docs/*"]}}.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "ui-audit-gate" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from _common import is_ui_path  # noqa: E402


def git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    return result.stdout if result.returncode == 0 else None


def respond(payload):
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        hook_input = {}
    cwd = hook_input.get("cwd") or os.getcwd()
    top = git("rev-parse", "--show-toplevel", cwd=cwd)
    if not top:
        sys.exit(0)
    root = Path(top.strip())
    config = {}
    config_path = root / ".ui-audit" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8")).get("gate", {})
        except (json.JSONDecodeError, OSError):
            config = {}
    mode = os.environ.get("UI_AUDIT_GATE") or config.get("mode") or "block"
    if mode == "off":
        sys.exit(0)

    status = git("status", "--porcelain", "--untracked-files=all", cwd=root) or ""
    changed = []
    for line in status.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path.startswith(".ui-audit/") or line[:2].strip() == "D":
            continue
        if is_ui_path(path, config.get("include", []), config.get("exclude", [])):
            changed.append(path)
    if not changed:
        sys.exit(0)
    latest_change = max((root / p).stat().st_mtime for p in changed if (root / p).exists()) if any((root / p).exists() for p in changed) else 0

    skip = root / ".ui-audit" / "SKIP"
    if skip.exists() and skip.stat().st_mtime >= latest_change and skip.read_text(encoding="utf-8").strip():
        respond({"systemMessage": f"ui-audit-gate: audit skipped at the user's request ({skip.read_text(encoding='utf-8').strip()[:120]})."})

    reports = sorted((root / ".ui-audit").glob("RUN-*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    fresh = [r for r in reports if r.stat().st_mtime >= latest_change]
    problem = None
    if not fresh:
        problem = "no audit report is more recent than the changes"
    else:
        try:
            from verify_report import verify

            result = verify(fresh[0].parent)
            if result["status"] != "ok" or not result.get("written_decision"):
                problem = f"report {fresh[0].parent.name} is inconsistent or has no decision ({'; '.join(result.get('errors', [])[:3]) or 'decision missing'})"
        except Exception as exc:
            problem = f"report verification failed ({type(exc).__name__})"
    if problem is None:
        sys.exit(0)

    listed = ", ".join(changed[:8]) + (f" (+{len(changed) - 8})" if len(changed) > 8 else "")
    message = (
        f"ui-audit-gate: interface files changed ({listed}) and {problem}. "
        "Before declaring the work done, run the ui-audit-gate skill and finish with verify_report.py --apply --render, "
        "or tell the user clearly that the audit was not done and offer to run it. "
        "If the user explicitly asked not to audit, write their reason in .ui-audit/SKIP."
    )
    if mode == "warn" or hook_input.get("stop_hook_active"):
        respond({"systemMessage": message})
    respond({"decision": "block", "reason": message})


if __name__ == "__main__":
    main()
