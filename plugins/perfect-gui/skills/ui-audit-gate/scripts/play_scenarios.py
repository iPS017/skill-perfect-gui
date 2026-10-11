#!/usr/bin/env python3
"""Rejoue toute la suite de scènes (scenes.json) sur chaque viewport, contrôle chaque étape et
compare les captures aux références. C'est la revue à lancer avant chaque republication.

Modes :
  --mode baseline : enregistre les captures de référence (première fois, ou après acceptation)
  --mode review   : rejoue tout, compare aux références, détecte les anomalies, écrit last-review.json

Après une revue, accepter des changements visuels voulus :
  python3 play_scenarios.py --suite ui-scenes --accept S-0003,S-0010     (ou --accept all)
Accepter une anomalie connue (sur décision explicite de l'utilisateur) :
  python3 play_scenarios.py --suite ui-scenes --accept-anomaly CLE --reason "..." --accepted-by "nom"

Exemple :
  python3 play_scenarios.py --suite ui-scenes --url http://localhost:3000 --viewports mobile,laptop --workers 4
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from _common import (
    SCRIPTS_DIR, annotate, build_config, config_id, emit, install_mutation_guard, launch_browser,
    BrowserUnavailable, capability_missing, context_options, ensure_playwright, git_revision, now_iso,
    read_json, resolve_viewports, run_actions, safe_name, ui_fingerprint, write_json, FREEZE_MOTION_CSS, LOAD_IMAGES_JS,
)

FAST_CHECKS = ["horizontal-overflow", "text-overflow", "occlusion", "target-size", "contrast", "form-errors", "alignment", "images", "accessible-names"]
BLOCKING = {
    "horizontal-overflow", "text-overflow", "occlusion", "contrast", "form-errors", "accessible-names",
    "action-sans-effet", "erreur-javascript", "defilement-bloque", "theme-non-adapte", "contenu-non-traduit", "scene-en-erreur",
}
SEVERITY = {
    "occlusion": "critique", "horizontal-overflow": "majeure", "text-overflow": "majeure", "contrast": "majeure",
    "form-errors": "majeure", "accessible-names": "majeure", "action-sans-effet": "majeure", "erreur-javascript": "majeure",
    "defilement-bloque": "majeure", "theme-non-adapte": "majeure", "contenu-non-traduit": "majeure", "scene-en-erreur": "majeure",
    "target-size": "moderee", "images": "moderee", "erreur-console": "moderee", "fermeture-echap-inoperante": "moderee",
    "police-non-chargee": "moderee", "lang-non-mis-a-jour": "moderee", "alignment": "mineure", "incoherence-style": "mineure",
    "controle-indisponible-a-ce-viewport": "info", "scene-obsolete": "moderee", "theme-sombre-ignore": "info", "requete-bloquee": "info", "navigation-externe": "info",
}
CONTROL_IDS = {
    "horizontal-overflow": "GEO-01", "text-overflow": "GEO-03", "occlusion": "STK-01", "target-size": "CTA-03", "contrast": "TXT-01",
    "form-errors": "FRM-03", "alignment": "GEO-02", "images": "COL-05", "accessible-names": "ACC-05", "action-sans-effet": "PAR-08",
    "erreur-javascript": "ROB-01", "erreur-console": "ROB-01", "defilement-bloque": "STK-08", "theme-non-adapte": "COL-03",
    "contenu-non-traduit": "LOC-02", "lang-non-mis-a-jour": "ACC-12", "police-non-chargee": "TXT-05", "incoherence-style": "DS-03",
    "fermeture-echap-inoperante": "STK-03", "controle-indisponible-a-ce-viewport": "NAV-06", "scene-en-erreur": "PAR-01", "scene-obsolete": "PAR-01",
}

EFFECT_START_JS = """
() => {
  window.__uiagMutations = 0;
  if (window.__uiagObserver) window.__uiagObserver.disconnect();
  window.__uiagObserver = new MutationObserver((records) => { window.__uiagMutations += records.length; });
  window.__uiagObserver.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  window.__uiagResources = performance.getEntriesByType('resource').length;
  return { url: location.href, scroll: [scrollX, scrollY] };
}
"""
EFFECT_END_JS = """
() => ({ mutations: window.__uiagMutations || 0, resources: performance.getEntriesByType('resource').length - (window.__uiagResources || 0), url: location.href, scroll: [scrollX, scrollY] })
"""


def anomaly_key(kind, scene_id, viewport, selector):
    return hashlib.sha1(f"{kind}|{scene_id}|{viewport}|{selector}".encode("utf-8")).hexdigest()[:12]


def scene_config(viewport, scene, args):
    cfg = build_config(viewport, args)
    environment = scene.get("environnement") or {}
    if environment.get("theme"):
        cfg["theme"] = environment["theme"]
    if environment.get("locale"):
        cfg["locale"] = environment["locale"]
    if environment.get("reduced_motion"):
        cfg["reduced_motion"] = environment["reduced_motion"]
    if environment.get("zoom") and viewport["width"] >= 1024:
        cfg["zoom"] = float(environment["zoom"])
    return cfg


def settle(page, args):
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    try:
        page.add_style_tag(content=FREEZE_MOTION_CSS)
    except Exception:
        pass
    page.wait_for_timeout(args.settle_ms)


def snapshot(page, scene, viewport_id, number, label, out_dir, inspect_js, consistency_js, args, last_toggle):
    try:
        page.evaluate(LOAD_IMAGES_JS)
    except Exception:
        pass
    scroll = page.evaluate("() => [scrollX, scrollY]")
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(60)
    inspection = page.evaluate(inspect_js, {"only": FAST_CHECKS, "minTarget": args.min_target, "touchTarget": 0, "alignTolerance": 1})
    consistency = page.evaluate(consistency_js)
    expanded = None
    if last_toggle and label == "ferme-par-echap":
        expanded = page.evaluate("(s) => { const el = document.querySelector(s); return el ? el.getAttribute('aria-expanded') : null; }", last_toggle)
    page.evaluate("([x, y]) => window.scrollTo(x, y)", scroll)
    shot = out_dir / viewport_id / f"{scene['id']}-{number}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    masks = [page.locator(selector) for selector in args.mask_selectors]
    page.screenshot(path=str(shot), full_page=True, scale="css", animations="disabled", mask=masks, mask_color="#ff00ff")
    checks = {}
    for name, check in inspection.get("checks", {}).items():
        if name == "form-errors" and not label.startswith("apres-envoi"):
            continue
        items = [i for i in check.get("items", []) if i.get("candidat", True)]
        if name == "occlusion":
            items = [i for i in items if i.get("state") == "centre-masque"]
        if check.get("result") == "issues" and items:
            checks[name] = items[:10]
    return {
        "n": number, "label": label, "screenshot": str(shot), "url": page.url, "checks": checks,
        "consistency": consistency, "expanded_after_escape": expanded,
    }


def play_scene(browser, scene, viewport, args, inspect_js, consistency_js, out_dir):
    cfg = scene_config(viewport, scene, args)
    context = browser.new_context(**context_options(cfg, args))
    context.set_default_timeout(args.action_timeout)
    blocked = []
    install_mutation_guard(context, args.allow_mutations, blocked)
    page = context.new_page()
    js_errors, console_errors = [], []
    page.on("pageerror", lambda e: js_errors.append(str(e)[:300]))
    page.on("console", lambda m: console_errors.append(m.text[:300]) if m.type == "error" and "favicon" not in (m.location or {}).get("url", "") else None)
    result = {"scene": scene["id"], "viewport": viewport["id"], "config_id": config_id(cfg), "snapshots": [], "effects": [], "status": "ok"}
    origin = urlparse(args.url)
    number = 0
    last_toggle = None
    started = time.time()
    try:
        for step, action in enumerate(scene["actions"]):
            (kind, value), = action.items()
            if kind == "goto":
                page.goto(urljoin(args.url, value), wait_until="load", timeout=max(args.action_timeout, 20000))
                settle(page, args)
            elif kind == "snapshot":
                number += 1
                result["snapshots"].append(snapshot(page, scene, viewport["id"], number, value, out_dir, inspect_js, consistency_js, args, last_toggle))
            elif kind == "click_effect":
                last_toggle = value
                before = page.evaluate(EFFECT_START_JS)
                blocked_before = len(blocked)
                pages_before = len(context.pages)
                page.click(value)
                page.wait_for_timeout(args.effect_ms)
                after = page.evaluate(EFFECT_END_JS) if not page.is_closed() else {"mutations": 1}
                effect = (after.get("mutations", 0) > 0 or after.get("resources", 0) > 0 or after.get("url") != before["url"]
                          or after.get("scroll") != before["scroll"] or len(blocked) > blocked_before or len(context.pages) > pages_before)
                result["effects"].append({"step": step, "selector": value, "effect": effect, "details": after})
                settle(page, args)
            else:
                run_actions(page, [action], args.url, [])
                settle(page, args)
            if urlparse(page.url).netloc and urlparse(page.url).netloc != origin.netloc:
                result["external_navigation"] = page.url
                break
    except Exception as exc:
        message = str(exc).strip().splitlines()[0][:300] if str(exc).strip() else type(exc).__name__
        timeout = "Timeout" in type(exc).__name__ or "Timeout" in message
        interaction = isinstance(action, dict) and any(k in action for k in ("click", "click_effect", "fill", "select", "check", "hover", "focus"))
        result["status"] = "indisponible" if timeout and interaction else "erreur"
        result["error"] = {"step": step, "action": action, "message": message, "timeout": timeout}
        try:
            shot = out_dir / viewport["id"] / f"{scene['id']}-erreur.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(shot), scale="css")
            result["error"]["screenshot"] = str(shot)
        except Exception:
            pass
    result["js_errors"] = js_errors[:10]
    result["console_errors"] = console_errors[:10]
    result["blocked_requests"] = blocked[:10]
    result["duration_s"] = round(time.time() - started, 2)
    context.close()
    return result


def run_worker(args):
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    suite = read_json(Path(args.suite) / "scenes.json")
    scenes = select_scenes(suite["scenes"], args)
    viewports = resolve_viewports(args.viewports)
    jobs = [(s, v) for v in viewports for s in scenes]
    jobs = jobs[args.worker_index::args.worker_count]
    inspect_js = (SCRIPTS_DIR / "inspect.js").read_text(encoding="utf-8")
    consistency_js = (SCRIPTS_DIR / "consistency.js").read_text(encoding="utf-8")
    out_dir = Path(args.worker_shots)
    results = []
    with sync_playwright() as playwright:
        try:
            browser, _ = launch_browser(playwright, args.engine, args.browser_path, not args.headed)
        except BrowserUnavailable as exc:
            write_json(args.worker_out, {"fatal": "browser", "attempts": exc.attempts})
            return
        for scene, viewport in jobs:
            try:
                results.append(play_scene(browser, scene, viewport, args, inspect_js, consistency_js, out_dir))
            except Exception as exc:
                results.append({"scene": scene["id"], "viewport": viewport["id"], "status": "erreur", "error": {"message": f"{type(exc).__name__}: {str(exc)[:200]}"}, "snapshots": [], "effects": []})
            write_json(args.worker_out, {"results": results})
        browser.close()
    write_json(args.worker_out, {"results": results})


def select_scenes(scenes, args):
    if args.scenes:
        wanted = set(args.scenes.split(","))
        scenes = [s for s in scenes if s["id"] in wanted]
    if args.categories:
        wanted = set(args.categories.split(","))
        scenes = [s for s in scenes if s["categorie"] in wanted]
    return scenes


def compare(baseline, current, diff_path, tolerance):
    from PIL import Image, ImageChops

    before = Image.open(baseline).convert("RGB")
    after = Image.open(current).convert("RGB")
    width, height = min(before.width, after.width), min(before.height, after.height)
    mask = ImageChops.difference(before.crop((0, 0, width, height)), after.crop((0, 0, width, height))).convert("L").point(lambda v: 255 if v > tolerance else 0)
    changed = mask.histogram()[255]
    ratio = changed / float(max(1, width * height))
    size_changed = before.size != after.size
    if changed or size_changed:
        base = after.crop((0, 0, width, height)).convert("L").convert("RGB")
        overlay = Image.composite(Image.new("RGB", base.size, (230, 0, 50)), base, mask)
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        overlay.save(diff_path)
    return {"ratio": round(ratio, 5), "size_changed": size_changed, "before_size": list(before.size), "after_size": list(after.size)}


def analyse(results, suite, args, run_dir, suite_dir):
    scenes = {s["id"]: s for s in suite["scenes"]}
    known = {k["key"]: k for k in (read_json(suite_dir / "known-issues.json", []) or [])}
    anomalies = {}

    def add(kind, result, selector, details, snapshot_n=None, screenshot=None, boxes=None):
        key = anomaly_key(kind, result["scene"], result["viewport"], selector or "")
        if key in anomalies:
            return
        scene = scenes.get(result["scene"], {})
        anomalies[key] = {
            "key": key, "type": kind, "controle": CONTROL_IDS.get(kind), "severite": SEVERITY.get(kind, "moderee"),
            "bloquant": kind in BLOCKING and key not in known, "connue": known.get(key),
            "scene": result["scene"], "titre_scene": scene.get("titre"), "viewport": result["viewport"], "config_id": result.get("config_id"),
            "selecteur": selector, "details": details, "capture": screenshot, "etape_capture": snapshot_n,
            "reproduction": {"page": scene.get("page"), "environnement": scene.get("environnement"), "actions": scene.get("actions")},
            "_boxes": boxes or [],
        }

    statuses = defaultdict(set)
    for result in results:
        statuses[result["scene"]].add(result["status"])
    unavailable_everywhere = {sid: values == {"indisponible"} for sid, values in statuses.items()}
    page_texts = {}
    for result in results:
        scene = scenes.get(result["scene"], {})
        if scene.get("categorie") == "page" and result["snapshots"]:
            page_texts[(scene.get("page"), result["viewport"])] = (set(result["snapshots"][0]["consistency"]["texts"]), result["snapshots"][0]["consistency"]["lang"])

    for result in results:
        scene = scenes.get(result["scene"], {})
        if result["status"] in ("erreur", "indisponible"):
            error = result.get("error", {})
            action = error.get("action") or {}
            kind = "controle-indisponible-a-ce-viewport" if result["status"] == "indisponible" else "scene-en-erreur"
            if kind == "controle-indisponible-a-ce-viewport" and unavailable_everywhere.get(result["scene"]):
                kind = "scene-obsolete"
            add(kind, result, json.dumps(action, ensure_ascii=False)[:160], error.get("message"), screenshot=error.get("screenshot"))
        for message in result.get("js_errors", []):
            add("erreur-javascript", result, message[:80], message)
        for message in result.get("console_errors", []):
            if result.get("blocked_requests") and "ERR_FAILED" in message:
                continue
            add("erreur-console", result, message[:80], message)
        for request in result.get("blocked_requests", []):
            add("requete-bloquee", result, f"{request['method']} {request['url'][:100]}", "Requête non GET bloquée par la garde (utiliser --allow-mutations en environnement de test)")
        if result.get("external_navigation"):
            add("navigation-externe", result, result["external_navigation"][:120], "La scène a quitté le site")
        for effect in result.get("effects", []):
            if not effect["effect"]:
                add("action-sans-effet", result, effect["selector"], "Aucun changement du DOM, de l'URL, du défilement ni requête après le clic (bouton mort ou retour visuel absent). Confiance moyenne : vérifier canvas, presse-papiers, son.")
        for shot in result["snapshots"]:
            reference_texts = page_texts.get((scene.get("page"), result["viewport"]), (set(), None))[0]
            for check, items in shot["checks"].items():
                if check == "form-errors":
                    items = [i for i in items if not i.get("text") or i["text"] not in " ".join(reference_texts)]
                for item in items[:5]:
                    add(check, result, item.get("selector") or item.get("kind"), {k: v for k, v in item.items() if k not in ("box",)}, shot["n"], shot["screenshot"], [item["box"]] if item.get("box") else [])
            consistency = shot["consistency"]
            if consistency.get("scroll_locked"):
                add("defilement-bloque", result, "body", f"Défilement bloqué sans dialogue ouvert (étape « {shot['label']} »)", shot["n"], shot["screenshot"])
            for island in consistency["theme"].get("light_islands", []):
                add("theme-non-adapte", result, island["selector"], "Grande zone claire dans une page sombre", shot["n"], shot["screenshot"], [island["box"]])
            if (scene.get("environnement") or {}).get("theme") == "dark" and suite.get("theme_sombre_css") and not consistency["theme"]["page_dark"]:
                add("theme-sombre-ignore", result, "body", "Le site déclare un thème sombre mais la page reste claire", shot["n"], shot["screenshot"])
            for font in consistency.get("fonts", []):
                if font.get("webfont") and font.get("loaded") is False:
                    add("police-non-chargee", result, font["family"], f"Police web déclarée mais non chargée : rendu de secours ({font['sample']})", shot["n"], shot["screenshot"])
            if shot.get("expanded_after_escape") == "true":
                add("fermeture-echap-inoperante", result, scene["actions"][-3].get("click_effect") if len(scene["actions"]) >= 3 else None, "aria-expanded reste true après Échap", shot["n"], shot["screenshot"])
            changes_language = (scene.get("environnement") or {}).get("locale") or "traduction" in scene.get("verifie", []) or (scene.get("categorie") == "reglage" and consistency.get("lang"))
            reference = page_texts.get((scene.get("page", "").split("?")[0] if scene.get("categorie") == "parametre-url" else scene.get("page"), result["viewport"]))
            if changes_language and reference and scene.get("categorie") != "page":
                texts = set(consistency["texts"])
                ref_texts, ref_lang = reference
                language_changed = consistency.get("lang") != ref_lang or (scene.get("environnement") or {}).get("locale")
                if language_changed and len(texts) >= 8:
                    same = len(texts & ref_texts) / len(texts)
                    if same > 0.5 and consistency.get("lang") != ref_lang:
                        add("contenu-non-traduit", result, f"lang={consistency.get('lang')}", f"{round(same * 100)} % des textes identiques à la langue d'origine ({ref_lang})", shot["n"], shot["screenshot"])
                if scene.get("categorie") == "reglage" and consistency.get("lang") == ref_lang and len(texts & ref_texts) / max(1, len(texts)) < 0.3:
                    add("lang-non-mis-a-jour", result, "html[lang]", f"Les textes ont changé de langue mais lang vaut toujours {ref_lang}", shot["n"], shot["screenshot"])

    styles = defaultdict(lambda: defaultdict(dict))
    reference_viewport = next((r["viewport"] for r in results if r["viewport"] in ("laptop", "desktop-md", "desktop")), results[0]["viewport"] if results else None)
    for result in results:
        scene = scenes.get(result["scene"], {})
        if result["viewport"] != reference_viewport or scene.get("environnement") or scene.get("categorie") == "reglage":
            continue
        for shot in result["snapshots"]:
            for role, entries in shot["consistency"]["styles"].items():
                for entry in entries:
                    styles[role][(scenes.get(result["scene"], {}).get("page"), entry["selector"])] = (entry["signature"], result, shot)
    style_findings = []
    for role, instances in styles.items():
        if len(instances) < 5:
            continue
        properties = next(iter(instances.values()))[0].keys()
        for prop in properties:
            counter = Counter(sig[prop] for sig, _, _ in instances.values())
            dominant, dominant_count = counter.most_common(1)[0]
            if dominant_count / len(instances) < 0.6:
                continue
            for value, count in counter.items():
                if value == dominant or count > max(2, len(instances) * 0.1):
                    continue
                for (page, selector), (sig, result, shot) in instances.items():
                    if sig[prop] == value:
                        add("incoherence-style", result, selector, f"{role} : {prop} = {value} alors que {dominant_count}/{len(instances)} utilisent {dominant} (page {page})", shot["n"], shot["screenshot"])
                        style_findings.append(selector)

    baseline_dir = suite_dir / "baseline"
    changes, new_shots = [], []
    for result in results:
        for shot in result["snapshots"]:
            relative = Path(shot["screenshot"]).relative_to(run_dir / "captures")
            reference = baseline_dir / relative
            if not reference.exists():
                new_shots.append(str(relative))
                continue
            diff = compare(reference, shot["screenshot"], run_dir / "diff" / relative, args.diff_tolerance)
            if diff["size_changed"] or diff["ratio"] > args.max_diff_ratio:
                changes.append({"scene": result["scene"], "viewport": result["viewport"], "capture": str(relative), "diff": str(run_dir / "diff" / relative), **diff,
                                "titre_scene": scenes.get(result["scene"], {}).get("titre")})

    by_shot = defaultdict(list)
    for item in anomalies.values():
        if item["capture"] and item["_boxes"]:
            by_shot[item["capture"]].append({**item["_boxes"][0], "level": "critique" if item["severite"] == "critique" else "majeure"})
    for path, boxes in by_shot.items():
        annotate(path, boxes, str(Path(path).with_suffix("")) + "-annote.png")
    for item in anomalies.values():
        if item["capture"] and item["_boxes"]:
            item["capture_annotee"] = str(Path(item["capture"]).with_suffix("")) + "-annote.png"
        item.pop("_boxes", None)
    return list(anomalies.values()), changes, new_shots


def render_review(review, path):
    counts = review["compteurs"]
    lines = [
        f"# Revue des scènes UI : {review['statut'].upper()}",
        "",
        f"- Date : {review['date']} ; révision : {review['revision']}",
        f"- Scènes : {counts['scenes']} × {len(review['viewports'])} viewports = {counts['executions']} exécutions ({counts['erreurs']} en erreur)",
        f"- Anomalies bloquantes : {counts['bloquantes']} ; autres : {counts['autres']} ; connues acceptées : {counts['connues']}",
        f"- Changements visuels à revoir : {counts['changements_visuels']} ; nouvelles captures sans référence : {counts['nouvelles_captures']}",
        "",
        "> Revue automatique : les anomalies sont des candidats étayés par des mesures. Les changements visuels doivent être acceptés (voulus) ou corrigés (régressions).",
        "",
    ]
    order = {"critique": 0, "majeure": 1, "moderee": 2, "mineure": 3, "info": 4}
    blocking = sorted([a for a in review["anomalies"] if a["bloquant"]], key=lambda a: (order[a["severite"]], a["scene"]))
    others = sorted([a for a in review["anomalies"] if not a["bloquant"]], key=lambda a: (order[a["severite"]], a["scene"]))
    for title, items in (("Anomalies bloquantes", blocking), ("Autres anomalies", others)):
        lines += [f"## {title}", ""]
        if not items:
            lines += ["Aucune.", ""]
        grouped = defaultdict(list)
        for item in items:
            grouped[item["type"]].append(item)
        for kind, group in grouped.items():
            lines += [f"### {kind} ({group[0]['severite']}, {group[0]['controle']}) : {len(group)}", ""]
            for item in group[:40]:
                capture = item.get("capture_annotee") or item.get("capture") or ""
                details = item["details"] if isinstance(item["details"], str) else json.dumps(item["details"], ensure_ascii=False)[:240]
                lines.append(f"- {item['scene']} [{item['viewport']}] `{(item['selecteur'] or '')[:90]}` : {details} ({capture}) clé `{item['key']}`")
            if len(group) > 40:
                lines.append(f"- ... {len(group) - 40} de plus dans review.json")
            lines.append("")
    lines += ["## Changements visuels par rapport aux références", ""]
    if not review["changements_visuels"]:
        lines.append("Aucun.")
    for change in review["changements_visuels"][:200]:
        lines.append(f"- {change['scene']} [{change['viewport']}] {change['titre_scene']} : {round(change['ratio'] * 100, 2)} % de pixels changés{' , taille modifiée' if change['size_changed'] else ''} ({change['diff']})")
    lines += ["", "## Non couvert par la suite", ""]
    lines += [f"- {n['element']} : {n['raison']}" for n in review.get("non_couvert", [])[:60]]
    lines += ["", "Pour accepter des changements voulus : `play_scenarios.py --suite <dossier> --accept S-xxxx,S-yyyy` (ou `all`).", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def accept(args):
    suite_dir = Path(args.suite)
    review_path = suite_dir / "last-review.json"
    review = read_json(review_path)
    if not review:
        emit({"status": "error", "error": "aucune revue à accepter"}, 1)
    run_dir = Path(review["run_dir"])
    wanted = None if args.accept == "all" else set(args.accept.split(","))
    copied = 0
    for shot in (run_dir / "captures").rglob("*.png"):
        scene_id = shot.stem.rsplit("-", 1)[0]
        if wanted is not None and scene_id not in wanted:
            continue
        target = suite_dir / "baseline" / shot.relative_to(run_dir / "captures")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shot, target)
        copied += 1
    review["changements_visuels"] = [c for c in review["changements_visuels"] if wanted is not None and c["scene"] not in wanted]
    review["compteurs"]["changements_visuels"] = len(review["changements_visuels"])
    review.setdefault("acceptations", []).append({"scenes": args.accept, "date": now_iso(), "captures": copied})
    review["statut"] = status_of(review)
    write_json(review_path, review)
    render_review(review, run_dir / "review.md")
    emit({"tool": "play_scenarios", "accepted": args.accept, "captures_copiees": copied, "statut": review["statut"]})


def accept_anomaly(args):
    suite_dir = Path(args.suite)
    if not args.reason or not args.accepted_by:
        emit({"status": "refused", "error": "--reason et --accepted-by sont obligatoires : seule une décision explicite de l'utilisateur accepte une anomalie"}, 1)
    known = read_json(suite_dir / "known-issues.json", []) or []
    known = [k for k in known if k["key"] != args.accept_anomaly]
    known.append({"key": args.accept_anomaly, "raison": args.reason, "acceptee_par": args.accepted_by, "date": now_iso()})
    write_json(suite_dir / "known-issues.json", known)
    review = read_json(suite_dir / "last-review.json")
    if review:
        for item in review["anomalies"]:
            if item["key"] == args.accept_anomaly:
                item["bloquant"] = False
                item["connue"] = known[-1]
        review["compteurs"]["bloquantes"] = sum(1 for a in review["anomalies"] if a["bloquant"])
        review["statut"] = status_of(review)
        write_json(suite_dir / "last-review.json", review)
        render_review(review, Path(review["run_dir"]) / "review.md")
    emit({"tool": "play_scenarios", "anomalie_acceptee": args.accept_anomaly, "statut": review["statut"] if review else None})


def status_of(review):
    counts = review["compteurs"]
    if counts["bloquantes"]:
        return "echec"
    if counts["erreurs"] or review.get("selection_partielle"):
        return "incomplet"
    if counts["changements_visuels"] or (counts["nouvelles_captures"] and review["mode"] == "review"):
        return "a-revoir"
    return "ok"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", required=True, help="Dossier de la suite (contient scenes.json)")
    parser.add_argument("--url", help="URL de base de l'application lancée (défaut : origine de scenes.json)")
    parser.add_argument("--mode", choices=["review", "baseline"], default="review")
    parser.add_argument("--viewports", default="mobile,laptop")
    parser.add_argument("--scenes", help="Identifiants à rejouer (sinon toutes)")
    parser.add_argument("--categories", help="Catégories à rejouer (sinon toutes)")
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--engine", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--browser-path")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--allow-mutations", action="store_true", help="Laisser passer POST/PUT/DELETE (environnement de test uniquement)")
    parser.add_argument("--action-timeout", type=int, default=5000)
    parser.add_argument("--effect-ms", type=int, default=500)
    parser.add_argument("--settle-ms", type=int, default=150)
    parser.add_argument("--min-target", type=int, default=24)
    parser.add_argument("--diff-tolerance", type=int, default=16)
    parser.add_argument("--max-diff-ratio", type=float, default=0.001)
    parser.add_argument("--theme", default="light")
    parser.add_argument("--locale", default="fr-FR")
    parser.add_argument("--timezone", default="Europe/Paris")
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--reduced-motion", default="no-preference")
    parser.add_argument("--forced-colors", action="store_true")
    parser.add_argument("--respect-csp", action="store_true")
    parser.add_argument("--storage-state")
    parser.add_argument("--mask", default="", help="Sélecteurs de zones dynamiques à masquer dans les captures (séparés par des virgules), en plus de 'masques' dans scenes.json")
    parser.add_argument("--accept", help="Accepter les changements visuels de ces scènes (ou all)")
    parser.add_argument("--accept-anomaly", help="Clé d'anomalie à marquer connue")
    parser.add_argument("--reason")
    parser.add_argument("--accepted-by")
    parser.add_argument("--worker-index", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-count", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", help=argparse.SUPPRESS)
    parser.add_argument("--worker-shots", help=argparse.SUPPRESS)
    args = parser.parse_args()

    suite_dir = Path(args.suite)
    suite = read_json(suite_dir / "scenes.json")
    if suite is None:
        emit({"status": "error", "error": f"{suite_dir / 'scenes.json'} introuvable : lancer explore_site.py puis generate_scenarios.py"}, 2)
    args.url = args.url or suite.get("origine") or suite.get("source")
    args.mask_selectors = [m.strip() for m in args.mask.split(",") if m.strip()] + list(suite.get("masques", []))

    if args.accept:
        accept(args)
    if args.accept_anomaly:
        accept_anomaly(args)
    if args.worker_out:
        run_worker(args)
        return

    ensure_playwright()
    try:
        import PIL  # noqa: F401
    except ImportError:
        capability_missing("pillow", "Pillow est requis pour comparer les captures (setup.sh)")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = suite_dir / "runs" / run_id
    shots_dir = run_dir / "captures"
    shots_dir.mkdir(parents=True, exist_ok=True)
    scenes = select_scenes(suite["scenes"], args)
    viewports = resolve_viewports(args.viewports)
    workers = max(1, min(args.workers, len(scenes) * len(viewports)))
    started = time.time()
    processes = []
    passthrough = []
    for flag in ("viewports", "scenes", "categories", "engine", "browser_path", "action_timeout", "effect_ms", "settle_ms", "min_target", "mask",
                 "theme", "locale", "timezone", "zoom", "reduced_motion", "storage_state", "url"):
        value = getattr(args, flag)
        if value not in (None, ""):
            passthrough += [f"--{flag.replace('_', '-')}", str(value)]
    for flag in ("headed", "allow_mutations", "forced_colors", "respect_csp"):
        if getattr(args, flag):
            passthrough.append(f"--{flag.replace('_', '-')}")
    for index in range(workers):
        out = run_dir / f"worker-{index}.json"
        command = [sys.executable, __file__, "--suite", str(suite_dir), *passthrough, "--worker-index", str(index), "--worker-count", str(workers), "--worker-out", str(out), "--worker-shots", str(shots_dir)]
        processes.append((subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True), out))
    results, worker_errors = [], []
    for process, out in processes:
        _, stderr = process.communicate()
        data = read_json(out, {}) or {}
        if data.get("fatal"):
            capability_missing("browser", "Aucun navigateur lançable pour rejouer les scènes", data.get("attempts"))
        if process.returncode != 0:
            worker_errors.append(stderr[-800:])
        results.extend(data.get("results", []))

    expected = len(scenes) * len(viewports)
    if args.mode == "baseline":
        baseline = suite_dir / "baseline"
        if baseline.exists() and not args.scenes and not args.categories:
            shutil.rmtree(baseline)
        for shot in shots_dir.rglob("*.png"):
            target = baseline / shot.relative_to(shots_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(shot, target)

    anomalies, changes, new_shots = analyse(results, suite, args, run_dir, suite_dir)
    executed_errors = sum(1 for r in results if r["status"] == "erreur")
    unavailable = sum(1 for r in results if r["status"] == "indisponible")
    review = {
        "tool": "play_scenarios",
        "mode": args.mode,
        "date": now_iso(),
        "revision": git_revision(),
        "empreinte_ui": ui_fingerprint(Path.cwd()),
        "empreinte_scenes": hashlib.sha1((suite_dir / "scenes.json").read_bytes()).hexdigest(),
        "run_dir": str(run_dir),
        "url": args.url,
        "viewports": [v["id"] for v in viewports],
        "selection_partielle": bool(args.scenes or args.categories),
        "duree_s": round(time.time() - started, 1),
        "compteurs": {
            "scenes": len(scenes),
            "executions": len(results),
            "executions_attendues": expected,
            "erreurs": executed_errors + max(0, expected - len(results)),
            "controles_indisponibles": unavailable,
            "bloquantes": sum(1 for a in anomalies if a["bloquant"]),
            "autres": sum(1 for a in anomalies if not a["bloquant"] and not a["connue"]),
            "connues": sum(1 for a in anomalies if a["connue"]),
            "changements_visuels": len(changes) if args.mode == "review" else 0,
            "nouvelles_captures": len(new_shots) if args.mode == "review" else 0,
        },
        "anomalies": anomalies,
        "changements_visuels": changes if args.mode == "review" else [],
        "nouvelles_captures": new_shots if args.mode == "review" else [],
        "non_couvert": suite.get("non_couvert", []),
        "erreurs_workers": worker_errors,
    }
    review["statut"] = status_of(review)
    if args.mode == "baseline" and review["statut"] == "a-revoir":
        review["statut"] = "ok"
    write_json(run_dir / "review.json", review)
    write_json(run_dir / "results.json", results)
    render_review(review, run_dir / "review.md")
    if not review["selection_partielle"]:
        write_json(suite_dir / "last-review.json", review)
    emit({
        "tool": "play_scenarios", "mode": args.mode, "statut": review["statut"], "rapport": str(run_dir / "review.md"),
        "duree_s": review["duree_s"], **review["compteurs"],
        "types_bloquants": dict(Counter(a["type"] for a in anomalies if a["bloquant"])),
        "types_autres": dict(Counter(a["type"] for a in anomalies if not a["bloquant"])),
    })


if __name__ == "__main__":
    main()
