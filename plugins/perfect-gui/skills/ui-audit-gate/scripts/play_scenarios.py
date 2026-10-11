#!/usr/bin/env python3
"""Replay the whole scene suite (scenes.json) on each viewport, check every step and
compare screenshots with the baselines. This is the review to run before each republication.

Modes:
  --mode baseline : record the baseline screenshots (first time, or after acceptance)
  --mode review   : replay everything, compare with baselines, detect anomalies, write last-review.json

After a review, accept intended visual changes:
  python3 play_scenarios.py --suite ui-scenes --accept S-0003,S-0010     (or --accept all)
Accept a known anomaly (on explicit user decision):
  python3 play_scenarios.py --suite ui-scenes --accept-anomaly KEY --reason "..." --accepted-by "name"

Example:
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
    "dead-click", "javascript-error", "scroll-locked", "theme-not-adapted", "untranslated-content", "scene-error",
}
SEVERITY = {
    "occlusion": "critical", "horizontal-overflow": "major", "text-overflow": "major", "contrast": "major",
    "form-errors": "major", "accessible-names": "major", "dead-click": "major", "javascript-error": "major",
    "scroll-locked": "major", "theme-not-adapted": "major", "untranslated-content": "major", "scene-error": "major",
    "target-size": "moderate", "images": "moderate", "console-error": "moderate", "escape-does-not-close": "moderate",
    "font-not-loaded": "moderate", "lang-not-updated": "moderate", "alignment": "minor", "style-inconsistency": "minor",
    "control-unavailable-at-viewport": "info", "stale-scene": "moderate", "dark-scheme-ignored": "info", "blocked-request": "info", "external-navigation": "info",
}
CONTROL_IDS = {
    "horizontal-overflow": "GEO-01", "text-overflow": "GEO-03", "occlusion": "STK-01", "target-size": "CTA-03", "contrast": "TXT-01",
    "form-errors": "FRM-03", "alignment": "GEO-02", "images": "COL-05", "accessible-names": "ACC-05", "dead-click": "PAR-08",
    "javascript-error": "ROB-01", "console-error": "ROB-01", "scroll-locked": "STK-08", "theme-not-adapted": "COL-03",
    "untranslated-content": "LOC-02", "lang-not-updated": "ACC-12", "font-not-loaded": "TXT-05", "style-inconsistency": "DS-03",
    "escape-does-not-close": "STK-03", "control-unavailable-at-viewport": "NAV-06", "scene-error": "PAR-01", "stale-scene": "PAR-01",
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
    environment = scene.get("environment") or {}
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
    if last_toggle and label == "closed-by-escape":
        expanded = page.evaluate("(s) => { const el = document.querySelector(s); return el ? el.getAttribute('aria-expanded') : null; }", last_toggle)
    page.evaluate("([x, y]) => window.scrollTo(x, y)", scroll)
    shot = out_dir / viewport_id / f"{scene['id']}-{number}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    masks = [page.locator(selector) for selector in args.mask_selectors]
    page.screenshot(path=str(shot), full_page=True, scale="css", animations="disabled", mask=masks, mask_color="#ff00ff")
    checks = {}
    for name, check in inspection.get("checks", {}).items():
        if name == "form-errors" and not label.startswith("after-submit"):
            continue
        items = [i for i in check.get("items", []) if i.get("candidate", True)]
        if name == "occlusion":
            items = [i for i in items if i.get("state") == "center-covered"]
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
        result["status"] = "unavailable" if timeout and interaction else "error"
        result["error"] = {"step": step, "action": action, "message": message, "timeout": timeout}
        try:
            shot = out_dir / viewport["id"] / f"{scene['id']}-error.png"
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
                results.append({"scene": scene["id"], "viewport": viewport["id"], "status": "error", "error": {"message": f"{type(exc).__name__}: {str(exc)[:200]}"}, "snapshots": [], "effects": []})
            write_json(args.worker_out, {"results": results})
        browser.close()
    write_json(args.worker_out, {"results": results})


def select_scenes(scenes, args):
    if args.scenes:
        wanted = set(args.scenes.split(","))
        scenes = [s for s in scenes if s["id"] in wanted]
    if args.categories:
        wanted = set(args.categories.split(","))
        scenes = [s for s in scenes if s["category"] in wanted]
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
            "key": key, "type": kind, "control": CONTROL_IDS.get(kind), "severity": SEVERITY.get(kind, "moderate"),
            "blocking": kind in BLOCKING and key not in known, "known": known.get(key),
            "scene": result["scene"], "scene_title": scene.get("title"), "viewport": result["viewport"], "config_id": result.get("config_id"),
            "selector": selector, "details": details, "screenshot": screenshot, "snapshot_step": snapshot_n,
            "reproduction": {"page": scene.get("page"), "environment": scene.get("environment"), "actions": scene.get("actions")},
            "_boxes": boxes or [],
        }

    statuses = defaultdict(set)
    for result in results:
        statuses[result["scene"]].add(result["status"])
    unavailable_everywhere = {sid: values == {"unavailable"} for sid, values in statuses.items()}
    page_texts = {}
    for result in results:
        scene = scenes.get(result["scene"], {})
        if scene.get("category") == "page" and result["snapshots"]:
            page_texts[(scene.get("page"), result["viewport"])] = (set(result["snapshots"][0]["consistency"]["texts"]), result["snapshots"][0]["consistency"]["lang"])

    for result in results:
        scene = scenes.get(result["scene"], {})
        if result["status"] in ("error", "unavailable"):
            error = result.get("error", {})
            action = error.get("action") or {}
            kind = "control-unavailable-at-viewport" if result["status"] == "unavailable" else "scene-error"
            if kind == "control-unavailable-at-viewport" and unavailable_everywhere.get(result["scene"]):
                kind = "stale-scene"
            add(kind, result, json.dumps(action, ensure_ascii=False)[:160], error.get("message"), screenshot=error.get("screenshot"))
        for message in result.get("js_errors", []):
            add("javascript-error", result, message[:80], message)
        for message in result.get("console_errors", []):
            if result.get("blocked_requests") and "ERR_FAILED" in message:
                continue
            add("console-error", result, message[:80], message)
        for request in result.get("blocked_requests", []):
            add("blocked-request", result, f"{request['method']} {request['url'][:100]}", "Non-GET request blocked by the guard (use --allow-mutations in a test environment)")
        if result.get("external_navigation"):
            add("external-navigation", result, result["external_navigation"][:120], "The scene left the site")
        for effect in result.get("effects", []):
            if not effect["effect"]:
                add("dead-click", result, effect["selector"], "No DOM, URL or scroll change and no request after the click (dead button or missing visual feedback). Medium confidence: check canvas, clipboard, sound.")
        for shot in result["snapshots"]:
            reference_texts = page_texts.get((scene.get("page"), result["viewport"]), (set(), None))[0]
            for check, items in shot["checks"].items():
                if check == "form-errors":
                    items = [i for i in items if not i.get("text") or i["text"] not in " ".join(reference_texts)]
                for item in items[:5]:
                    add(check, result, item.get("selector") or item.get("kind"), {k: v for k, v in item.items() if k not in ("box",)}, shot["n"], shot["screenshot"], [item["box"]] if item.get("box") else [])
            consistency = shot["consistency"]
            if consistency.get("scroll_locked"):
                add("scroll-locked", result, "body", f"Scroll locked without an open dialog (step \"{shot['label']}\")", shot["n"], shot["screenshot"])
            for island in consistency["theme"].get("light_islands", []):
                add("theme-not-adapted", result, island["selector"], "Large light area in a dark page", shot["n"], shot["screenshot"], [island["box"]])
            if (scene.get("environment") or {}).get("theme") == "dark" and suite.get("dark_scheme_css") and not consistency["theme"]["page_dark"]:
                add("dark-scheme-ignored", result, "body", "The site declares a dark theme but the page stays light", shot["n"], shot["screenshot"])
            for font in consistency.get("fonts", []):
                if font.get("webfont") and font.get("loaded") is False:
                    add("font-not-loaded", result, font["family"], f"Web font declared but not loaded: fallback rendering ({font['sample']})", shot["n"], shot["screenshot"])
            if shot.get("expanded_after_escape") == "true":
                add("escape-does-not-close", result, scene["actions"][-3].get("click_effect") if len(scene["actions"]) >= 3 else None, "aria-expanded stays true after Escape", shot["n"], shot["screenshot"])
            changes_language = (scene.get("environment") or {}).get("locale") or "translation" in scene.get("checks", []) or (scene.get("category") == "setting" and consistency.get("lang"))
            reference = page_texts.get((scene.get("page", "").split("?")[0] if scene.get("category") == "url-param" else scene.get("page"), result["viewport"]))
            if changes_language and reference and scene.get("category") != "page":
                texts = set(consistency["texts"])
                ref_texts, ref_lang = reference
                language_changed = consistency.get("lang") != ref_lang or (scene.get("environment") or {}).get("locale")
                if language_changed and len(texts) >= 8:
                    same = len(texts & ref_texts) / len(texts)
                    if same > 0.5 and consistency.get("lang") != ref_lang:
                        add("untranslated-content", result, f"lang={consistency.get('lang')}", f"{round(same * 100)}% of texts identical to the original language ({ref_lang})", shot["n"], shot["screenshot"])
                if scene.get("category") == "setting" and consistency.get("lang") == ref_lang and len(texts & ref_texts) / max(1, len(texts)) < 0.3:
                    add("lang-not-updated", result, "html[lang]", f"Texts changed language but lang is still {ref_lang}", shot["n"], shot["screenshot"])

    styles = defaultdict(lambda: defaultdict(dict))
    reference_viewport = next((r["viewport"] for r in results if r["viewport"] in ("laptop", "desktop-md", "desktop")), results[0]["viewport"] if results else None)
    for result in results:
        scene = scenes.get(result["scene"], {})
        if result["viewport"] != reference_viewport or scene.get("environment") or scene.get("category") == "setting":
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
                        add("style-inconsistency", result, selector, f"{role}: {prop} = {value} while {dominant_count}/{len(instances)} use {dominant} (page {page})", shot["n"], shot["screenshot"])
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
                changes.append({"scene": result["scene"], "viewport": result["viewport"], "screenshot": str(relative), "diff": str(run_dir / "diff" / relative), **diff,
                                "scene_title": scenes.get(result["scene"], {}).get("title")})

    by_shot = defaultdict(list)
    for item in anomalies.values():
        if item["screenshot"] and item["_boxes"]:
            by_shot[item["screenshot"]].append({**item["_boxes"][0], "level": "critical" if item["severity"] == "critical" else "major"})
    for path, boxes in by_shot.items():
        annotate(path, boxes, str(Path(path).with_suffix("")) + "-annotated.png")
    for item in anomalies.values():
        if item["screenshot"] and item["_boxes"]:
            item["annotated_screenshot"] = str(Path(item["screenshot"]).with_suffix("")) + "-annotated.png"
        item.pop("_boxes", None)
    return list(anomalies.values()), changes, new_shots


def render_review(review, path):
    counts = review["counts"]
    lines = [
        f"# UI scene review: {review['status'].upper()}",
        "",
        f"- Date: {review['date']}; revision: {review['revision']}",
        f"- Scenes: {counts['scenes']} x {len(review['viewports'])} viewports = {counts['executions']} executions ({counts['errors']} with errors)",
        f"- Blocking anomalies: {counts['blocking']}; other: {counts['other']}; known and accepted: {counts['known']}",
        f"- Visual changes to review: {counts['visual_changes']}; new screenshots without baseline: {counts['new_captures']}",
        "",
        "> Automated review: anomalies are candidates backed by measurements. Visual changes must be accepted (intended) or fixed (regressions).",
        "",
    ]
    order = {"critical": 0, "major": 1, "moderate": 2, "minor": 3, "info": 4}
    blocking = sorted([a for a in review["anomalies"] if a["blocking"]], key=lambda a: (order[a["severity"]], a["scene"]))
    others = sorted([a for a in review["anomalies"] if not a["blocking"]], key=lambda a: (order[a["severity"]], a["scene"]))
    for title, items in (("Blocking anomalies", blocking), ("Other anomalies", others)):
        lines += [f"## {title}", ""]
        if not items:
            lines += ["None.", ""]
        grouped = defaultdict(list)
        for item in items:
            grouped[item["type"]].append(item)
        for kind, group in grouped.items():
            lines += [f"### {kind} ({group[0]['severity']}, {group[0]['control']}): {len(group)}", ""]
            for item in group[:40]:
                screenshot = item.get("annotated_screenshot") or item.get("screenshot") or ""
                details = item["details"] if isinstance(item["details"], str) else json.dumps(item["details"], ensure_ascii=False)[:240]
                lines.append(f"- {item['scene']} [{item['viewport']}] `{(item['selector'] or '')[:90]}`: {details} ({screenshot}) key `{item['key']}`")
            if len(group) > 40:
                lines.append(f"- ... {len(group) - 40} more in review.json")
            lines.append("")
    lines += ["## Visual changes compared with baselines", ""]
    if not review["visual_changes"]:
        lines.append("None.")
    for change in review["visual_changes"][:200]:
        lines.append(f"- {change['scene']} [{change['viewport']}] {change['scene_title']}: {round(change['ratio'] * 100, 2)}% of pixels changed{', size changed' if change['size_changed'] else ''} ({change['diff']})")
    lines += ["", "## Not covered by the suite", ""]
    lines += [f"- {n['element']}: {n['reason']}" for n in review.get("not_covered", [])[:60]]
    lines += ["", "To accept intended changes: `play_scenarios.py --suite <folder> --accept S-xxxx,S-yyyy` (or `all`).", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def accept(args):
    suite_dir = Path(args.suite)
    review_path = suite_dir / "last-review.json"
    review = read_json(review_path)
    if not review:
        emit({"status": "error", "error": "no review to accept"}, 1)
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
    review["visual_changes"] = [c for c in review["visual_changes"] if wanted is not None and c["scene"] not in wanted]
    review["counts"]["visual_changes"] = len(review["visual_changes"])
    review.setdefault("acceptances", []).append({"scenes": args.accept, "date": now_iso(), "screenshots": copied})
    review["status"] = status_of(review)
    write_json(review_path, review)
    render_review(review, run_dir / "review.md")
    emit({"tool": "play_scenarios", "accepted": args.accept, "copied_screenshots": copied, "status": review["status"]})


def accept_anomaly(args):
    suite_dir = Path(args.suite)
    if not args.reason or not args.accepted_by:
        emit({"status": "refused", "error": "--reason and --accepted-by are required: only an explicit user decision accepts an anomaly"}, 1)
    known = read_json(suite_dir / "known-issues.json", []) or []
    known = [k for k in known if k["key"] != args.accept_anomaly]
    known.append({"key": args.accept_anomaly, "reason": args.reason, "accepted_by": args.accepted_by, "date": now_iso()})
    write_json(suite_dir / "known-issues.json", known)
    review = read_json(suite_dir / "last-review.json")
    if review:
        for item in review["anomalies"]:
            if item["key"] == args.accept_anomaly:
                item["blocking"] = False
                item["known"] = known[-1]
        review["counts"]["blocking"] = sum(1 for a in review["anomalies"] if a["blocking"])
        review["status"] = status_of(review)
        write_json(suite_dir / "last-review.json", review)
        render_review(review, Path(review["run_dir"]) / "review.md")
    emit({"tool": "play_scenarios", "accepted_anomaly": args.accept_anomaly, "status": review["status"] if review else None})


def status_of(review):
    counts = review["counts"]
    if counts["blocking"]:
        return "failed"
    if counts["errors"] or review.get("partial_selection"):
        return "incomplete"
    if counts["visual_changes"] or (counts["new_captures"] and review["mode"] == "review"):
        return "needs-review"
    return "ok"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", required=True, help="Suite folder (contains scenes.json)")
    parser.add_argument("--url", help="Base URL of the running application (default: origin from scenes.json)")
    parser.add_argument("--mode", choices=["review", "baseline"], default="review")
    parser.add_argument("--viewports", default="mobile,laptop")
    parser.add_argument("--scenes", help="Identifiers to replay (otherwise all)")
    parser.add_argument("--categories", help="Categories to replay (otherwise all)")
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--engine", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--browser-path")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--allow-mutations", action="store_true", help="Let POST/PUT/DELETE through (test environment only)")
    parser.add_argument("--action-timeout", type=int, default=5000)
    parser.add_argument("--effect-ms", type=int, default=500)
    parser.add_argument("--settle-ms", type=int, default=150)
    parser.add_argument("--min-target", type=int, default=24)
    parser.add_argument("--diff-tolerance", type=int, default=16)
    parser.add_argument("--max-diff-ratio", type=float, default=0.001)
    parser.add_argument("--theme", default="light")
    parser.add_argument("--locale", default="en-US")
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--reduced-motion", default="no-preference")
    parser.add_argument("--forced-colors", action="store_true")
    parser.add_argument("--respect-csp", action="store_true")
    parser.add_argument("--storage-state")
    parser.add_argument("--mask", default="", help="Selectors of dynamic areas to mask in screenshots (comma separated), in addition to 'masks' in scenes.json")
    parser.add_argument("--accept", help="Accept the visual changes of these scenes (or all)")
    parser.add_argument("--accept-anomaly", help="Anomaly key to mark as known")
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
        emit({"status": "error", "error": f"{suite_dir / 'scenes.json'} not found: run explore_site.py then generate_scenarios.py"}, 2)
    args.url = args.url or suite.get("origin") or suite.get("source")
    args.mask_selectors = [m.strip() for m in args.mask.split(",") if m.strip()] + list(suite.get("masks", []))

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
        capability_missing("pillow", "Pillow is required to compare screenshots (setup.sh)")

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
            capability_missing("browser", "No launchable browser to replay the scenes", data.get("attempts"))
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
    executed_errors = sum(1 for r in results if r["status"] == "error")
    unavailable = sum(1 for r in results if r["status"] == "unavailable")
    review = {
        "tool": "play_scenarios",
        "mode": args.mode,
        "date": now_iso(),
        "revision": git_revision(),
        "ui_fingerprint": ui_fingerprint(Path.cwd()),
        "scenes_fingerprint": hashlib.sha1((suite_dir / "scenes.json").read_bytes()).hexdigest(),
        "run_dir": str(run_dir),
        "url": args.url,
        "viewports": [v["id"] for v in viewports],
        "partial_selection": bool(args.scenes or args.categories),
        "duration_s": round(time.time() - started, 1),
        "counts": {
            "scenes": len(scenes),
            "executions": len(results),
            "expected_executions": expected,
            "errors": executed_errors + max(0, expected - len(results)),
            "unavailable_controls": unavailable,
            "blocking": sum(1 for a in anomalies if a["blocking"]),
            "other": sum(1 for a in anomalies if not a["blocking"] and not a["known"]),
            "known": sum(1 for a in anomalies if a["known"]),
            "visual_changes": len(changes) if args.mode == "review" else 0,
            "new_captures": len(new_shots) if args.mode == "review" else 0,
        },
        "anomalies": anomalies,
        "visual_changes": changes if args.mode == "review" else [],
        "new_captures": new_shots if args.mode == "review" else [],
        "not_covered": suite.get("not_covered", []),
        "worker_errors": worker_errors,
    }
    review["status"] = status_of(review)
    if args.mode == "baseline" and review["status"] == "needs-review":
        review["status"] = "ok"
    write_json(run_dir / "review.json", review)
    write_json(run_dir / "results.json", results)
    render_review(review, run_dir / "review.md")
    if not review["partial_selection"]:
        write_json(suite_dir / "last-review.json", review)
    emit({
        "tool": "play_scenarios", "mode": args.mode, "status": review["status"], "report": str(run_dir / "review.md"),
        "duration_s": review["duration_s"], **review["counts"],
        "blocking_types": dict(Counter(a["type"] for a in anomalies if a["blocking"])),
        "other_types": dict(Counter(a["type"] for a in anomalies if not a["blocking"])),
    })


if __name__ == "__main__":
    main()
