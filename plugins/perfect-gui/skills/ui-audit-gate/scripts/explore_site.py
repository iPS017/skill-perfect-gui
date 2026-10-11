#!/usr/bin/env python3
"""Explore un site ou une application Web et inventorie tout ce qu'un utilisateur peut faire :
pages, liens, boutons, menus, onglets, bascules, champs, listes, cases, formulaires, paramètres d'URL,
réglages (thème, langue, tri, filtres), variantes de langue et points de rupture CSS.

Les éléments révélés par une interaction (menu ouvert, accordéon déplié) sont découverts aussi,
avec les actions nécessaires pour les atteindre. Les requêtes autres que GET sont bloquées.

Exemple :
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

REVEALING_KINDS = {"bascule", "onglet", "element-menu", "liste"}
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
    candidates = [c for c in base["controls"] if (c["kind"] in REVEALING_KINDS or (c["kind"] == "action" and hidden)) and c["risk"] == "sur" and c["visible"]][:budget]
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
            item["prerequis"] = [{"click": control["selector"]}]
            item["revele_par"] = control["selector"]
            if item["selector"] in hidden:
                base["controls"].remove(hidden.pop(item["selector"]))
            revealed.append(item)
        for form in after["forms"]:
            if form["selector"] not in {f["selector"] for f in base["forms"]} and form["visible"]:
                form["prerequis"] = [{"click": control["selector"]}]
                base["forms"].append(form)
    return revealed


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser, default_viewports="laptop")
    parser.add_argument("--out", required=True, help="Fichier site-map.json")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--include", help="Regex : chemins à explorer")
    parser.add_argument("--exclude", default=r"(logout|deconnexion|signout|/admin/delete)", help="Regex : chemins à ignorer")
    parser.add_argument("--reveal-budget", type=int, default=15, help="Bascules ouvertes par page pour découvrir les contrôles cachés")
    parser.add_argument("--max-query-variants", type=int, default=3, help="Variantes d'une même page avec des paramètres d'URL différents")
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
                skipped.append({"url": url, "raison": "exclu par --exclude"})
                continue
            if include and not include.search(parsed.path):
                skipped.append({"url": url, "raison": "hors --include"})
                continue
            variants = path_variants.setdefault(parsed.path, 0)
            if parsed.query and variants >= args.max_query_variants:
                skipped.append({"url": url, "raison": "trop de variantes de paramètres pour ce chemin"})
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
                skipped.append({"url": url, "raison": f"redirige hors du site ({final.netloc})"})
                continue
            found = discover(page, js_source)
            found["status"] = response.status if response else None
            if (found["status"] or 200) >= 400 or CHALLENGE_TITLE.search(found.get("title") or ""):
                found["acces_bloque"] = f"HTTP {found['status']}, titre « {found.get('title')} »"
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
        "cree_le": now_iso(),
        "depart": args.url,
        "origine": f"{start.scheme}://{start.netloc}",
        "moteur": browser_info,
        "viewport_exploration": cfg["viewport_id"],
        "pages": pages,
        "parametres_url": params,
        "langues": sorted({a["hreflang"] for p in pages for a in p.get("alternates", [])}),
        "theme_sombre_css": any(p.get("supports_dark_scheme") for p in pages),
        "points_de_rupture": sorted({b for p in pages for b in p.get("breakpoints", [])}),
        "liens_externes": sorted(external)[:200],
        "non_explore": {"budget_atteint": remaining[:200], "ignores": skipped[:200]},
        "requetes_bloquees": blocked[:100],
        "resume": {
            "pages": len(pages),
            "controles": sum(kinds.values()),
            "par_type": kinds,
            "formulaires": sum(len(p.get("forms", [])) for p in pages),
            "pages_restantes_non_explorees": len(remaining),
        },
    }
    blocked_pages = [{"url": p["url"], "raison": p["acces_bloque"]} for p in pages if p.get("acces_bloque")]
    site_map["pages_bloquees"] = blocked_pages
    site_map["resume"]["pages_bloquees"] = len(blocked_pages)
    if blocked_pages:
        site_map["avertissement"] = ("Pages refusées (erreur HTTP, protection anti-robot ou défi) : leur contenu n'a pas été exploré. "
                                     "Ne pas contourner : explorer l'environnement de développement ou de test, ou fournir une session (--storage-state).")
    write_json(args.out, site_map)
    emit({"tool": "explore_site", "out": str(Path(args.out)), **site_map["resume"], "avertissement": site_map.get("avertissement"),
          "langues": site_map["langues"], "points_de_rupture": site_map["points_de_rupture"][:20]})


if __name__ == "__main__":
    main()
