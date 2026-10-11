#!/usr/bin/env python3
"""ui-audit-gate PreToolUse (Bash) hook: before a publish command (git push, npm publish,
vercel, netlify deploy, firebase deploy, etc.), require a complete and successful review of the scene
suite, run on the exact interface that is about to ship.

Active only if the project has a suite (ui-scenes/scenes.json, or "scenes" in .ui-audit/config.json).
Settings: UI_AUDIT_PUBLISH_GATE=block|ask|off, or .ui-audit/config.json
{"publish_gate": {"mode": "block", "suite": "ui-scenes", "patterns": ["make release"]}}.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "ui-audit-gate" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from _common import project_root, ui_fingerprint  # noqa: E402

PUBLISH_PATTERNS = [
    r"\bgit\s+push\b", r"\b(npm|pnpm|bun)\s+publish\b", r"\byarn\s+(npm\s+)?publish\b",
    r"\bvercel\b(?!\s+(dev|env|login|logs|ls|list|whoami)\b)", r"\bnetlify\s+deploy\b", r"\bfirebase\s+deploy\b",
    r"\bfly(ctl)?\s+deploy\b", r"\bwrangler\s+(pages\s+)?(deploy|publish)\b", r"\bgh\s+release\s+create\b",
    r"\bdocker\s+push\b", r"\b(npm|pnpm|yarn|bun)\s+run\s+(deploy|release|publish)\b", r"\bgh-pages\b",
    r"\bsurge\b", r"\brailway\s+up\b", r"\bheroku\s+.*deploy\b", r"\bamplify\s+publish\b",
    r"\beas\s+(submit|update)\b", r"\bfastlane\s+(deliver|release|beta|supply)\b",
]


def respond(decision, reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)
    command = (hook_input.get("tool_input") or {}).get("command") or ""
    cwd = hook_input.get("cwd") or os.getcwd()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True)
    root = Path(top.stdout.strip()) if top.returncode == 0 else project_root(cwd)
    config = {}
    config_path = root / ".ui-audit" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8")).get("publish_gate", {})
        except (json.JSONDecodeError, OSError):
            config = {}
    mode = os.environ.get("UI_AUDIT_PUBLISH_GATE") or config.get("mode") or "block"
    if mode == "off":
        sys.exit(0)
    patterns = PUBLISH_PATTERNS + config.get("patterns", [])
    if not any(re.search(p, command) for p in patterns):
        sys.exit(0)
    suite = root / config.get("suite", "ui-scenes")
    scenes_file = suite / "scenes.json"
    if not scenes_file.exists():
        sys.exit(0)

    review = None
    review_path = suite / "last-review.json"
    if review_path.exists():
        try:
            review = json.loads(review_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            review = None
    problems = []
    if not review:
        problems.append("no complete scene review has been run")
    else:
        if review.get("mode") != "review":
            problems.append("the last run was a baseline capture, not a review")
        if review.get("scenes_fingerprint") != hashlib.sha1(scenes_file.read_bytes()).hexdigest():
            problems.append("scenes.json changed since the last review")
        current = ui_fingerprint(root, config.get("include", []), config.get("exclude", []))
        if current and review.get("ui_fingerprint") != current:
            problems.append("interface files changed since the last review")
        status = review.get("status")
        if status != "ok":
            details = {
                "failed": f"{review.get('counts', {}).get('blocking')} blocking anomaly(ies)",
                "needs-review": f"{review.get('counts', {}).get('visual_changes')} unaccepted visual change(s)",
                "incomplete": "scenes not run or with errors",
            }.get(status, status)
            problems.append(f"last review has status \"{status}\" ({details})")
    if not problems:
        sys.exit(0)
    total = len(json.loads(scenes_file.read_text(encoding="utf-8")).get("scenes", []))
    reason = (
        f"ui-audit-gate: publish blocked, the review of the {total} UI scenes is not valid ({'; '.join(problems)}). "
        f"Start the application, then run: python3 \"{SCRIPTS_DIR / 'play_scenarios.py'}\" --suite \"{suite}\" --url <URL>. "
        "Fix the blocking anomalies; accept intended visual changes with --accept. "
        "A known anomaly may be accepted (--accept-anomaly) only on an explicit user decision. "
        "To disable: UI_AUDIT_PUBLISH_GATE=off."
    )
    respond("ask" if mode == "ask" else "deny", reason)


if __name__ == "__main__":
    main()
