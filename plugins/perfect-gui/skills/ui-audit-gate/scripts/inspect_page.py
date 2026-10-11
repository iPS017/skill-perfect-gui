#!/usr/bin/env python3
"""Automatic in-page checks: overflows, overlaps, targets, alignment,
contrast, labels, accessible names, form errors, images, headings, language, axe-core, console.

Results are candidates to confirm on the annotated screenshot, not verdicts.

Example:
  python3 inspect_page.py --url http://localhost:3000/ --viewports P0 --out .ui-audit/RUN-x/inspect --scan-scroll
"""
from pathlib import Path

from _common import (
    SCRIPTS_DIR, add_browser_args, annotate, base_parser, browser_session, build_config, config_id,
    emit, load_axe, manifest, now_iso, prepare_page, resolve_viewports, write_json,
)

PSEUDO_JS = """
(scope) => {
  const accents = {a:'á',e:'é',i:'î',o:'ö',u:'ü',c:'ç',n:'ñ',y:'ý',s:'š',z:'ž',A:'Å',E:'É',I:'Î',O:'Ö',U:'Ü',C:'Ç',N:'Ñ'};
  const root = scope ? document.querySelector(scope) : document.body;
  if (!root) return 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => n.textContent.trim() && !n.parentElement.closest('script,style,noscript,code,pre,textarea') ? 1 : 2,
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const text = node.textContent;
    const core = text.trim();
    const padding = 'ẋ'.repeat(Math.max(2, Math.round(core.length * 0.4)));
    const accented = core.replace(/[a-zA-Z]/g, (ch) => accents[ch] || ch);
    node.textContent = text.replace(core, `[${accented}${padding}]`);
  }
  for (const input of root.querySelectorAll('input[type=submit], input[type=button]')) {
    input.value = `[${input.value}${'ẋ'.repeat(Math.max(2, Math.round(input.value.length * 0.4)))}]`;
  }
  return nodes.length;
}
"""

TEXT_SPACING_CSS = (
    "*{line-height:1.5!important;letter-spacing:0.12em!important;word-spacing:0.16em!important}"
    "p{margin-bottom:2em!important}"
)

AXE_RUN_JS = """
async (scope) => {
  const context = scope ? document.querySelector(scope) : document;
  const result = await axe.run(context, { resultTypes: ['violations', 'incomplete'] });
  const pick = (v) => ({ id: v.id, impact: v.impact, help: v.help, helpUrl: v.helpUrl,
    tags: v.tags.filter((t) => t.startsWith('wcag')), count: v.nodes.length,
    nodes: v.nodes.slice(0, 8).map((n) => ({ target: n.target, summary: (n.failureSummary || '').slice(0, 300) })) });
  return { version: axe.version, violations: result.violations.map(pick), incomplete: result.incomplete.map(pick) };
}
"""

BOX_CHECKS = ["horizontal-overflow", "text-overflow", "occlusion", "target-size", "alignment", "spacing", "contrast", "form-labels", "accessible-names", "form-errors"]


def luminance(rgb):
    channels = []
    for value in rgb[:3]:
        v = value / 255
        channels.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def verify_contrast_on_pixels(check, screenshot):
    try:
        from PIL import Image
    except ImportError:
        return
    if not check or check.get("result") != "issues" or not screenshot:
        return
    image = Image.open(screenshot).convert("RGB")
    confirmed, resolved = [], []
    for item in check.get("items", []):
        box = item.get("box")
        if not box or box["w"] < 2 or box["h"] < 2:
            confirmed.append(item)
            continue
        region = image.crop((box["x"], box["y"], min(image.width, box["x"] + box["w"]), min(image.height, box["y"] + box["h"])))
        text = tuple(int(item["color"][i:i + 2], 16) for i in (1, 3, 5))
        counts = {}
        for n, color in (region.getcolors(maxcolors=region.width * region.height) or []):
            key = tuple(c // 8 * 8 for c in color)
            counts[key] = counts.get(key, 0) + n
        backgrounds = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if sum(abs(c[i] - text[i]) for i in range(3)) > 60]
        if not backgrounds:
            confirmed.append(item)
            continue
        measured = round(contrast_ratio(text, backgrounds[0]), 2)
        item["pixel_background"] = "#%02x%02x%02x" % backgrounds[0]
        item["pixel_ratio"] = measured
        if measured + 0.05 >= item["required"]:
            item["kind"] = "resolved-by-pixels"
            resolved.append(item)
        else:
            confirmed.append(item)
    check["items"] = confirmed
    check["resolved_by_pixels"] = resolved
    check["result"] = "issues" if confirmed else "clean"
    if resolved:
        check["note"] = ("Computed colors missed a layer (overlay, clip-path, gradient, image); these items were re-measured on the "
                         "screenshot pixels and pass. Confirm visually if the background is not uniform.")


def scan_occlusion(page, js_source, opts):
    height = page.evaluate("() => document.documentElement.scrollHeight")
    viewport_height = page.evaluate("() => window.innerHeight")
    positions = sorted({*range(0, max(1, height - viewport_height + 1), max(1, int(viewport_height * 0.6))), max(0, height - viewport_height)})[:25]
    seen = {}
    for y in positions:
        page.evaluate("(y) => window.scrollTo(0, y)", y)
        page.wait_for_timeout(60)
        result = page.evaluate(js_source, {**opts, "only": ["occlusion"], "allOcclusion": True})
        for item in result["checks"]["occlusion"]["items"]:
            if not item["center_in_viewport"]:
                continue
            entry = seen.setdefault(item["selector"], {"selector": item["selector"], "name": item["name"], "box": item["box"], "positions": 0, "masked": 0, "occluders": set()})
            entry["positions"] += 1
            if item["state"] == "center-covered":
                entry["masked"] += 1
                if item["occluder"]:
                    entry["occluders"].add(f"{item['occluder']} ({item['occluder_position']})")
    page.evaluate("() => window.scrollTo(0, 0)")
    items = []
    for entry in seen.values():
        if not entry["masked"]:
            continue
        entry["occluders"] = sorted(entry["occluders"])
        entry["state"] = "covered-at-every-position" if entry["masked"] == entry["positions"] else "covered-at-some-positions"
        items.append(entry)
    items.sort(key=lambda e: (e["state"] != "covered-at-every-position", e["selector"]))
    return {
        "controls": ["STK-01", "STK-06"],
        "result": "issues" if any(i["state"] == "covered-at-every-position" for i in items) else "clean",
        "mode": "scan",
        "scroll_positions": positions,
        "note": "covered-at-some-positions is often normal (sticky header while scrolling); covered-at-every-position means the action is never clickable.",
        "items": items,
    }


def collect_boxes(checks):
    boxes = []
    for name in BOX_CHECKS:
        check = checks.get(name) or {}
        if check.get("result") != "issues":
            continue
        for item in check.get("items", []):
            if "box" in item and item.get("candidate", True):
                boxes.append({**item["box"], "level": "critical" if name == "occlusion" else "major", "check": name, "selector": item.get("selector")})
    return boxes[:60]


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser)
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--scope", help="CSS selector limiting the checks")
    parser.add_argument("--only", help="Comma-separated checks to run")
    parser.add_argument("--pseudo", action="store_true", help="Pseudo-localize the page text (+40%%, accents)")
    parser.add_argument("--text-spacing", action="store_true", help="Inject the WCAG 1.4.12 text spacing")
    parser.add_argument("--scan-scroll", action="store_true", help="Look for overlaps at several scroll positions")
    parser.add_argument("--min-target", type=int, default=24)
    parser.add_argument("--touch-target", type=int, default=44, help="Indicative touch guideline for coarse pointers, 0 to disable")
    parser.add_argument("--align-tolerance", type=float, default=1.0)
    parser.add_argument("--min-gap", type=float, default=4.0, help="Minimum gap in CSS px between neighboring blocks of a row (spacing check)")
    parser.add_argument("--skip-link-threshold", type=int, default=6, help="Below this number of focusable elements before main, a missing skip link is only reported as info")
    parser.add_argument("--no-axe", action="store_true")
    parser.add_argument("--no-screenshot", action="store_true")
    args = parser.parse_args()

    js_source = (SCRIPTS_DIR / "inspect.js").read_text(encoding="utf-8")
    out_root = Path(args.out)
    summary = {"tool": "inspect_page", "url": args.url, "created": now_iso(), "configs": []}
    axe_source, axe_origin = (None, "disabled (--no-axe)") if args.no_axe else load_axe()

    with browser_session(args) as (browser, browser_info):
        for viewport in resolve_viewports(args.viewports):
            cfg = build_config(viewport, args)
            cid = config_id(cfg)
            out_dir = out_root / cid
            out_dir.mkdir(parents=True, exist_ok=True)
            context, page, logs, clock, steps = prepare_page(browser, cfg, args)
            variants = []
            if args.pseudo:
                variants.append(f"pseudo-localization ({page.evaluate(PSEUDO_JS, args.scope)} nodes)")
            if args.text_spacing:
                page.add_style_tag(content=TEXT_SPACING_CSS)
                variants.append("WCAG 1.4.12 text spacing")
            if variants:
                page.wait_for_timeout(100)

            opts = {
                "scope": args.scope,
                "only": [c.strip() for c in args.only.split(",")] if args.only else None,
                "minTarget": args.min_target,
                "touchTarget": args.touch_target if cfg["pointer"] == "coarse" else 0,
                "alignTolerance": args.align_tolerance,
                "minGap": args.min_gap,
                "skipLinkThreshold": args.skip_link_threshold,
            }
            result = page.evaluate(js_source, opts)
            if "error" in result:
                emit({"status": "error", "error": result["error"]}, 1)
            checks = result["checks"]
            if args.scan_scroll and (not opts["only"] or "occlusion" in opts["only"]):
                checks["occlusion"] = scan_occlusion(page, js_source, opts)

            if axe_source and (not opts["only"] or "axe" in opts["only"]):
                try:
                    page.evaluate(axe_source + "\n;true")
                    axe = page.evaluate(AXE_RUN_JS, args.scope)
                    serious = [v for v in axe["violations"] if v["impact"] in ("serious", "critical")]
                    checks["axe"] = {"controls": ["ACC-01"], "result": "issues" if axe["violations"] else "clean", "serious_or_critical": len(serious), "source": axe_origin, **axe}
                except Exception as exc:
                    checks["axe"] = {"controls": ["ACC-01"], "result": "error", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            elif not opts["only"] or "axe" in (opts["only"] or []):
                checks["axe"] = {"controls": ["ACC-01"], "result": "error", "error": axe_origin}

            relevant_logs = [entry for entry in logs if entry["type"] in ("error", "pageerror", "requestfailed") or entry["type"].startswith("http-")]
            checks["console"] = {"controls": ["ROB-01"], "result": "issues" if relevant_logs else "clean", "items": relevant_logs[:40]}

            try:
                aria = page.locator(args.scope or "body").aria_snapshot()
                (out_dir / "aria-snapshot.txt").write_text(aria, encoding="utf-8")
                aria_path = str(out_dir / "aria-snapshot.txt")
            except Exception as exc:
                aria_path = f"unavailable ({type(exc).__name__})"

            screenshot = annotated = None
            if not args.no_screenshot:
                screenshot = out_dir / "page.png"
                page.screenshot(path=str(screenshot), full_page=True, scale="css", animations="disabled")
                verify_contrast_on_pixels(checks.get("contrast"), screenshot)
                boxes = collect_boxes(checks)
                annotated = annotate(screenshot, boxes, out_dir / "annotated.png") if boxes else None
                if boxes:
                    write_json(out_dir / "annotations.json", [{"n": i, **b} for i, b in enumerate(boxes, 1)])

            report = {
                "config_id": cid,
                "manifest": manifest(cfg, browser_info, args, clock, steps),
                "variants": variants,
                "viewport": result["viewport"],
                "document_height": result["document_height"],
                "checks": checks,
                "screenshot": str(screenshot) if screenshot else None,
                "annotated": annotated,
                "aria_snapshot": aria_path,
            }
            write_json(out_dir / "inspect.json", report)
            summary["configs"].append({
                "config_id": cid,
                "report": str(out_dir / "inspect.json"),
                "annotated": annotated,
                "checks": {name: {"result": c.get("result"), "items": len(c.get("items", c.get("violations", [])))} for name, c in checks.items()},
            })
            context.close()

    summary["issues"] = sorted({name for c in summary["configs"] for name, r in c["checks"].items() if r["result"] == "issues"})
    summary["reminder"] = "Candidates to confirm visually. 'clean' = nothing detected by this script, not proof that there is no defect."
    emit(summary)


if __name__ == "__main__":
    main()
