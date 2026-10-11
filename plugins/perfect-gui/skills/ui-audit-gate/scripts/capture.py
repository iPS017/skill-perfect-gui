#!/usr/bin/env python3
"""Reproducible screenshots with a manifest per configuration.

Output: <out>/<config_id>/<name>__<state>.png and <out>/manifests/<config_id>.json

Example:
  python3 capture.py --url http://localhost:5173/ --viewports P0 --out .ui-audit/RUN-x/before --name home --state normal
"""
from pathlib import Path

from _common import (
    add_browser_args, base_parser, browser_session, build_config, config_id, emit, manifest,
    now_iso, prepare_page, read_json, resolve_viewports, safe_name, write_json,
)


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser)
    parser.add_argument("--out", required=True)
    parser.add_argument("--name", default="page", help="Screen name")
    parser.add_argument("--state", default="normal", help="State code (see reference/configurations.md)")
    parser.add_argument("--viewport-only", action="store_true", help="Capture only the visible part")
    parser.add_argument("--selector", help="Capture only this element")
    args = parser.parse_args()

    out_root = Path(args.out)
    captures = []
    failures = []
    with browser_session(args) as (browser, browser_info):
        for viewport in resolve_viewports(args.viewports):
            cfg = build_config(viewport, args)
            cid = config_id(cfg)
            target = out_root / cid / f"{safe_name(args.name)}__{safe_name(args.state)}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                context, page, logs, clock, steps = prepare_page(browser, cfg, args)
                if args.selector:
                    page.locator(args.selector).first.screenshot(path=str(target), animations="disabled")
                else:
                    page.screenshot(path=str(target), full_page=not args.viewport_only, animations="disabled")
                data = manifest(cfg, browser_info, args, clock, steps)
                manifest_path = out_root / "manifests" / f"{cid}.json"
                existing = read_json(manifest_path, {}) or {}
                existing.update({k: v for k, v in data.items() if k != "captures"})
                existing.setdefault("captures", [])
                existing["captures"] = [c for c in existing["captures"] if c["file"] != str(target.relative_to(out_root))]
                existing["captures"].append({"file": str(target.relative_to(out_root)), "screen": args.name, "state": args.state, "selector": args.selector, "created_at": now_iso()})
                write_json(manifest_path, existing)
                captures.append({"config_id": cid, "file": str(target), "manifest": str(manifest_path), "console_errors": len([e for e in logs if e["type"] in ("error", "pageerror")])})
                context.close()
            except Exception as exc:
                failures.append({"config_id": cid, "error": f"{type(exc).__name__}: {str(exc).strip().splitlines()[0][:300] if str(exc).strip() else ''}"})

    status = "ok" if captures and not failures else ("partial" if captures else "failed")
    emit({"tool": "capture", "status": status, "captures": captures, "failures": failures}, 0 if status != "failed" else 3)


if __name__ == "__main__":
    main()
