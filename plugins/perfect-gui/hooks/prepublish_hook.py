#!/usr/bin/env python3
"""Hook PreToolUse (Bash) de ui-audit-gate : avant une commande de publication (git push, npm publish,
vercel, netlify deploy, firebase deploy, etc.), exige une revue complète et réussie de la suite de
scènes, faite sur l'interface exacte qui va partir.

Actif seulement si le projet a une suite (ui-scenes/scenes.json, ou "scenes" dans .ui-audit/config.json).
Réglages : UI_AUDIT_PUBLISH_GATE=block|ask|off, ou .ui-audit/config.json
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
from _common import ui_fingerprint  # noqa: E402

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
    root = Path(top.stdout.strip()) if top.returncode == 0 else Path(cwd)
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
        problems.append("aucune revue complète des scènes n'a été faite")
    else:
        if review.get("mode") != "review":
            problems.append("la dernière exécution était une prise de référence, pas une revue")
        if review.get("empreinte_scenes") != hashlib.sha1(scenes_file.read_bytes()).hexdigest():
            problems.append("scenes.json a changé depuis la dernière revue")
        current = ui_fingerprint(root, config.get("include", []), config.get("exclude", []))
        if current and review.get("empreinte_ui") != current:
            problems.append("des fichiers d'interface ont changé depuis la dernière revue")
        status = review.get("statut")
        if status != "ok":
            details = {
                "echec": f"{review.get('compteurs', {}).get('bloquantes')} anomalie(s) bloquante(s)",
                "a-revoir": f"{review.get('compteurs', {}).get('changements_visuels')} changement(s) visuel(s) non accepté(s)",
                "incomplet": "scènes non exécutées ou en erreur",
            }.get(status, status)
            problems.append(f"dernière revue au statut « {status} » ({details})")
    if not problems:
        sys.exit(0)
    total = len(json.loads(scenes_file.read_text(encoding="utf-8")).get("scenes", []))
    reason = (
        f"ui-audit-gate : publication bloquée, la revue des {total} scènes UI n'est pas valide ({'; '.join(problems)}). "
        f"Lance l'application, puis : python3 \"{SCRIPTS_DIR / 'play_scenarios.py'}\" --suite \"{suite}\" --url <URL>. "
        "Corrige les anomalies bloquantes ; accepte les changements visuels voulus avec --accept. "
        "Une anomalie connue ne s'accepte (--accept-anomaly) que sur décision explicite de l'utilisateur. "
        "Désactivation : UI_AUDIT_PUBLISH_GATE=off."
    )
    respond("ask" if mode == "ask" else "deny", reason)


if __name__ == "__main__":
    main()
