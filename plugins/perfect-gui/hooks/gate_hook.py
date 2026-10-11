#!/usr/bin/env python3
"""Hook Stop de ui-audit-gate : bloque une fois la fin du tour si des fichiers d'interface ont été
modifiés dans le dépôt git sans rapport d'audit cohérent plus récent.

Réglages : variable UI_AUDIT_GATE=block|warn|off, ou .ui-audit/config.json
{"gate": {"mode": "block", "include": ["*.tpl"], "exclude": ["docs/*"]}}.
"""
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "ui-audit-gate" / "scripts"
UI_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".styl", ".pcss", ".html", ".htm", ".vue", ".svelte", ".astro",
                 ".jsx", ".tsx", ".mdx", ".twig", ".erb", ".hbs", ".njk", ".liquid", ".razor", ".cshtml",
                 ".swift", ".dart", ".xaml", ".storyboard", ".xib"}
UI_PATH_HINTS = ("components/", "component/", "pages/", "views/", "screens/", "layouts/", "ui/", "styles/", "theme", "tokens", "locales/", "i18n/", "res/layout", "res/values")
SCRIPT_EXTENSIONS = {".js", ".ts", ".mjs", ".kt", ".json"}


def git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    return result.stdout if result.returncode == 0 else None


def is_ui(path, include, exclude):
    if any(fnmatch.fnmatch(path, pattern) for pattern in exclude):
        return False
    if any(fnmatch.fnmatch(path, pattern) for pattern in include):
        return True
    suffix = Path(path).suffix.lower()
    if suffix in UI_EXTENSIONS:
        return True
    return suffix in SCRIPT_EXTENSIONS and any(hint in path.lower() for hint in UI_PATH_HINTS)


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
        if is_ui(path, config.get("include", []), config.get("exclude", [])):
            changed.append(path)
    if not changed:
        sys.exit(0)
    latest_change = max((root / p).stat().st_mtime for p in changed if (root / p).exists()) if any((root / p).exists() for p in changed) else 0

    skip = root / ".ui-audit" / "SKIP"
    if skip.exists() and skip.stat().st_mtime >= latest_change and skip.read_text(encoding="utf-8").strip():
        respond({"systemMessage": f"ui-audit-gate : audit ignoré à la demande de l'utilisateur ({skip.read_text(encoding='utf-8').strip()[:120]})."})

    reports = sorted((root / ".ui-audit").glob("RUN-*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    fresh = [r for r in reports if r.stat().st_mtime >= latest_change]
    problem = None
    if not fresh:
        problem = "aucun rapport d'audit plus récent que les modifications"
    else:
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            from verify_report import verify

            result = verify(fresh[0].parent)
            if result["status"] != "ok" or not result.get("decision_ecrite"):
                problem = f"rapport {fresh[0].parent.name} incohérent ou sans décision ({'; '.join(result.get('errors', [])[:3]) or 'decision absente'})"
        except Exception as exc:
            problem = f"vérification du rapport impossible ({type(exc).__name__})"
    if problem is None:
        sys.exit(0)

    listed = ", ".join(changed[:8]) + (f" (+{len(changed) - 8})" if len(changed) > 8 else "")
    message = (
        f"ui-audit-gate : des fichiers d'interface ont changé ({listed}) et {problem}. "
        "Avant de déclarer le travail terminé, exécute le skill ui-audit-gate et termine par verify_report.py --apply --render, "
        "ou dis clairement à l'utilisateur que l'audit n'a pas été fait et propose-le. "
        "Si l'utilisateur a explicitement demandé de ne pas auditer, écris sa raison dans .ui-audit/SKIP."
    )
    if mode == "warn" or hook_input.get("stop_hook_active"):
        respond({"systemMessage": message})
    respond({"decision": "block", "reason": message})


if __name__ == "__main__":
    main()
