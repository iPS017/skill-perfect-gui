#!/usr/bin/env python3
"""Log in once and save the Playwright session state, so every other script can open logged-in views.

The login actions come from .ui-audit/views.json ("login": [...]) or --actions. Secrets are never
written in files: use "${env:NAME}" placeholders, resolved from environment variables at run time.

Example .ui-audit/views.json:
  {"login": [{"fill": ["#email", "${env:UI_AUDIT_USER}"]}, {"fill": ["#password", "${env:UI_AUDIT_PASSWORD}"]},
             {"click": "role=button[name=\\"Sign in\\"]"}, {"wait_for": "role=navigation"}],
   "views": {"skin": [{"click": "role=tab[name=\\"Skin\\"]"}]}}

  UI_AUDIT_USER=test UI_AUDIT_PASSWORD=... python3 login.py --url http://localhost:1420/
Then set "storage_state": ".ui-audit/auth/state.json" in .ui-audit/config.json (done automatically with --remember).
"""
import json
import os
import re
from pathlib import Path

from _common import (
    add_browser_args, base_parser, browser_session, build_config, emit, load_actions, now_iso, open_page,
    project_config, project_root, read_json, resolve_viewports, run_actions, stabilize, write_json,
)

PLACEHOLDER = re.compile(r"\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_secrets(value, missing):
    if isinstance(value, str):
        def replace(match):
            name = match.group(1)
            if name not in os.environ:
                missing.add(name)
                return ""
            return os.environ[name]
        return PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [resolve_secrets(v, missing) for v in value]
    if isinstance(value, dict):
        return {k: resolve_secrets(v, missing) for k, v in value.items()}
    return value


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser, default_viewports="laptop")
    parser.add_argument("--out", default=".ui-audit/auth/state.json", help="Where to save the session state (keep it out of git)")
    parser.add_argument("--remember", action="store_true", help="Record storage_state in .ui-audit/config.json")
    args = parser.parse_args()

    root = project_root()
    views_file = root / (project_config().get("views_file") or ".ui-audit/views.json")
    actions = load_actions(args.actions) if args.actions else (read_json(views_file, {}) or {}).get("login")
    if not actions:
        emit({"status": "error", "error": f"No login actions: pass --actions or add \"login\" to {views_file}"}, 2)
    missing = set()
    actions = resolve_secrets(actions, missing)
    if missing:
        emit({"status": "error", "error": "Missing environment variables for the login placeholders", "missing": sorted(missing)}, 2)

    args.storage_state = None
    args.fresh_session = True
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    with browser_session(args) as (browser, browser_info):
        cfg = build_config(resolve_viewports(args.viewports)[0], args)
        context, page, logs, clock = open_page(browser, cfg, args)
        page.goto(args.url, wait_until="load")
        stabilize(page, args)
        steps = []
        try:
            run_actions(page, actions, args.url, steps)
            stabilize(page, args)
        except Exception as exc:
            shot = root / ".ui-audit" / "auth" / "login-failure.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot))
            emit({"status": "error", "error": f"Login actions failed at step {len(steps) + 1}: {str(exc).splitlines()[0][:200]}", "screenshot": str(shot)}, 1)
        out.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(out))
        context.close()
    try:
        out.chmod(0o600)
    except OSError:
        pass
    if args.remember:
        config_path = root / ".ui-audit" / "config.json"
        config = read_json(config_path, {}) or {}
        config["storage_state"] = os.path.relpath(out, root)
        write_json(config_path, config)
    state = json.loads(out.read_text(encoding="utf-8"))
    emit({
        "tool": "login", "status": "ok", "state": str(out), "created_at": now_iso(), "engine": browser_info["launch"],
        "cookies": len(state.get("cookies", [])), "origins_with_storage": len(state.get("origins", [])),
        "remembered": bool(args.remember),
        "reminder": "The state file holds live session tokens: keep it in .ui-audit/ (git-ignored) and never attach it to a report.",
    })


if __name__ == "__main__":
    main()
