#!/usr/bin/env python3
"""Explore a website or web application and inventory everything a user can do:
pages, links, buttons, menus, tabs, toggles, fields, selects, checkboxes, forms, URL parameters,
settings (theme, language, sorting, filters), language variants and CSS breakpoints.

Elements revealed by an interaction (open menu, expanded accordion) are discovered too,
along with the actions needed to reach them. Requests other than GET are blocked.

Example:
  python3 explore_site.py --url http://localhost:3000/ --out ui-scenes/site-map.json --max-pages 40
"""
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from _common import (
    DESTRUCTIVE_PATTERN, SCRIPTS_DIR, SETTING_PATTERN, add_browser_args, base_parser, browser_session,
    build_config, emit, install_mutation_guard, now_iso, open_page, resolve_viewports, run_actions,
    stabilize, write_json,
)

REVEALING_KINDS = {"toggle", "tab", "menu-item", "select"}
CHALLENGE_TITLE = re.compile(r"(just a moment|un instant|attention required|access denied|acc[eè]s refus[ée]|captcha|verify you are human|v[ée]rification)", re.I)


def normalize(url, keep_query=True):
    parsed = urlparse(url)
    query = urlencode(sorted(parse_qsl(parsed.query))) if keep_query else ""
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}" + (f"?{query}" if query else "")


def discover(page, js_source):
    return page.evaluate(js_source, {"destructivePattern": DESTRUCTIVE_PATTERN, "settingPattern": SETTING_PATTERN})


def reveal(page, url, js_source, base, args, budget):
    revealed = []
    known = {c["selector"] for c in base["controls"] if c["visible"]}
    hidden = {c["selector"]: c for c in base["controls"] if not c["visible"]}
    candidates = [c for c in base["controls"] if (c["kind"] in REVEALING_KINDS or (c["kind"] == "action" and hidden)) and c["risk"] == "safe" and c["visible"]][:budget]
    for control in candidates:
        try:
            page.goto(url, wait_until="load")
            stabilize(page, args)
            steps = []
            run_actions(page, [{"click": control["selector"]}], url, steps)
            page.wait_for_timeout(250)
            if normalize(page.url) != normalize(url):
                continue
            after = discover(page, js_source)
        except Exception:
            continue
        for item in after["controls"]:
            if item["selector"] in known or not item["visible"]:
                continue
            known.add(item["selector"])
            item["prerequisites"] = [{"click": control["selector"]}]
            item["revealed_by"] = control["selector"]
            if item["selector"] in hidden:
                base["controls"].remove(hidden.pop(item["selector"]))
            revealed.append(item)
        for form in after["forms"]:
            if form["selector"] not in {f["selector"] for f in base["forms"]} and form["visible"]:
                form["prerequisites"] = [{"click": control["selector"]}]
                base["forms"].append(form)
    return revealed


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser, default_viewports="laptop")
    parser.add_argument("--out", required=True, help="site-map.json file")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--include", help="Regex: paths to explore")
    parser.add_argument("--exclude", default=r"(logout|deconnexion|signout|/admin/delete)", help="Regex: paths to skip")
    parser.add_argument("--reveal-budget", type=int, default=15, help="Toggles opened per page to discover hidden controls")
    parser.add_argument("--max-query-variants", type=int, default=3, help="Variants of the same page with different URL parameters")
    args = parser.parse_args()

    js_source = (SCRIPTS_DIR / "discover.js").read_text(encoding="utf-8")
    start = urlparse(args.url)
    include = re.compile(args.include) if args.include else None
    exclude = re.compile(args.exclude, re.I) if args.exclude else None
    queue = [(args.url, 0, None)]
    visited = set()
    path_variants = {}
    pages = []
    blocked = []
    skipped = []
    external = set()

    with browser_session(args) as (browser, browser_info):
        viewport = resolve_viewports(args.viewports)[0]
        cfg = build_config(viewport, args)
        context, page, logs, clock = open_page(browser, cfg, args)
        install_mutation_guard(context, False, blocked)
        while queue and len(pages) < args.max_pages:
            url, depth, referrer = queue.pop(0)
            key = normalize(url)
            if key in visited:
                continue
            visited.add(key)
            parsed = urlparse(url)
            if exclude and exclude.search(parsed.path):
                skipped.append({"url": url, "reason": "excluded by --exclude"})
                continue
            if include and not include.search(parsed.path):
                skipped.append({"url": url, "reason": "outside --include"})
                continue
            variants = path_variants.setdefault(parsed.path, 0)
            if parsed.query and variants >= args.max_query_variants:
                skipped.append({"url": url, "reason": "too many parameter variants for this path"})
                continue
            path_variants[parsed.path] = variants + 1
            try:
                response = page.goto(url, wait_until="load")
                stabilize(page, args)
            except Exception as exc:
                pages.append({"url": url, "depth": depth, "referrer": referrer, "error": f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"})
                continue
            final = urlparse(page.url)
            if final.netloc != start.netloc:
                skipped.append({"url": url, "reason": f"redirects outside the site ({final.netloc})"})
                continue
            found = discover(page, js_source)
            found["status"] = response.status if response else None
            if (found["status"] or 200) >= 400 or CHALLENGE_TITLE.search(found.get("title") or ""):
                found["access_blocked"] = f"HTTP {found['status']}, title \"{found.get('title')}\""
                found["controls"], found["forms"], found["links"] = [], [], []
                pages.append(found)
                continue
            found["depth"] = depth
            found["referrer"] = referrer
            found["revealed"] = reveal(page, page.url, js_source, found, args, args.reveal_budget) if args.reveal_budget else []
            found["controls"].extend(found.pop("revealed"))
            pages.append(found)
            for link in found["links"]:
                if link["external"]:
                    external.add(link["href"])
                elif depth + 1 <= args.max_depth and normalize(link["href"]) not in visited:
                    queue.append((link["href"], depth + 1, found["url"]))
        context.close()

    remaining = sorted({normalize(u) for u, _, _ in queue} - visited)
    params = {}
    for found in pages:
        for name, values in found.get("params", {}).items():
            params.setdefault(name, [])
            params[name] += [v for v in values if v not in params[name]][:12]
    kinds = {}
    for found in pages:
        for control in found.get("controls", []):
            kinds[control["kind"]] = kinds.get(control["kind"], 0) + 1
    site_map = {
        "tool": "explore_site",
        "created_at": now_iso(),
        "start": args.url,
        "origin": f"{start.scheme}://{start.netloc}",
        "engine": browser_info,
        "exploration_viewport": cfg["viewport_id"],
        "pages": pages,
        "url_params": params,
        "languages": sorted({a["hreflang"] for p in pages for a in p.get("alternates", [])}),
        "dark_scheme_css": any(p.get("supports_dark_scheme") for p in pages),
        "breakpoints": sorted({b for p in pages for b in p.get("breakpoints", [])}),
        "external_links": sorted(external)[:200],
        "not_explored": {"budget_reached": remaining[:200], "ignored": skipped[:200]},
        "blocked_requests": blocked[:100],
        "summary": {
            "pages": len(pages),
            "controls": sum(kinds.values()),
            "by_kind": kinds,
            "forms": sum(len(p.get("forms", [])) for p in pages),
            "remaining_unexplored_pages": len(remaining),
        },
    }
    blocked_pages = [{"url": p["url"], "reason": p["access_blocked"]} for p in pages if p.get("access_blocked")]
    site_map["blocked_pages"] = blocked_pages
    site_map["summary"]["blocked_pages"] = len(blocked_pages)
    if blocked_pages:
        site_map["warning"] = ("Pages refused (HTTP error, bot protection or challenge): their content was not explored. "
                                     "Do not bypass this: explore the development or test environment, or provide a session (--storage-state).")
    write_json(args.out, site_map)
    emit({"tool": "explore_site", "out": str(Path(args.out)), **site_map["summary"], "warning": site_map.get("warning"),
          "languages": site_map["languages"], "breakpoints": site_map["breakpoints"][:20]})


if __name__ == "__main__":
    main()
