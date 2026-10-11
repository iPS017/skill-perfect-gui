#!/usr/bin/env python3
"""Keyboard walk: tab order, focus traps, visible indicator, obscured focus,
unreachable elements, closing dialogs with Escape.

Example:
  python3 keyboard_walk.py --url http://localhost:3000/ --viewports laptop --out .ui-audit/RUN-x/keyboard
"""
from pathlib import Path

from _common import (
    add_browser_args, base_parser, browser_session, build_config, config_id, emit, manifest,
    now_iso, prepare_page, resolve_viewports, write_json,
)

MARK_FOCUSABLES_JS = """
() => {
  const selector = 'a[href], area[href], button, input:not([type=hidden]), select, textarea, summary, iframe, [tabindex], [contenteditable=""], [contenteditable=true]';
  const props = ['outlineStyle', 'outlineWidth', 'outlineColor', 'boxShadow', 'borderTopColor', 'borderBottomColor', 'backgroundColor', 'color', 'textDecorationLine'];
  window.__uiagBase = {};
  const list = [];
  let index = 0;
  for (const el of document.querySelectorAll(selector)) {
    if (el.disabled || el.closest('[inert]') || el.getAttribute('tabindex') === '-1') continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const rendered = cs.display !== 'none' && cs.visibility !== 'hidden' && (r.width > 0 || r.height > 0);
    if (!rendered) continue;
    el.dataset.uiagIdx = String(index);
    const base = {};
    for (const p of props) base[p] = cs[p];
    base.after = getComputedStyle(el, '::after').boxShadow + getComputedStyle(el, '::after').opacity;
    base.before = getComputedStyle(el, '::before').boxShadow + getComputedStyle(el, '::before').opacity;
    window.__uiagBase[index] = base;
    list.push({ idx: index, tag: el.tagName.toLowerCase(), visible: r.width > 1 && r.height > 1 && cs.opacity !== '0' });
    index += 1;
  }
  return list;
}
"""

ACTIVE_JS = """
() => {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return { key: 'BODY' };
  const path = (n) => {
    if (n.id) return '#' + CSS.escape(n.id);
    const parts = [];
    for (let x = n; x && x.nodeType === 1 && x !== document.documentElement && parts.length < 5; x = x.parentElement) {
      let part = x.tagName.toLowerCase();
      if (x.id) { parts.unshift('#' + CSS.escape(x.id)); break; }
      const cls = [...x.classList].slice(0, 2);
      if (cls.length) part += '.' + cls.map((c) => CSS.escape(c)).join('.');
      const same = x.parentElement ? [...x.parentElement.children].filter((c) => c.tagName === x.tagName) : [];
      if (same.length > 1) part += `:nth-of-type(${same.indexOf(x) + 1})`;
      parts.unshift(part);
    }
    return parts.join(' > ');
  };
  const selector = path(el);
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  const base = (window.__uiagBase || {})[el.dataset.uiagIdx];
  const props = ['boxShadow', 'borderTopColor', 'borderBottomColor', 'backgroundColor', 'color', 'textDecorationLine', 'outlineColor'];
  const changed = base ? props.filter((p) => base[p] !== cs[p]) : [];
  if (base && base.after !== getComputedStyle(el, '::after').boxShadow + getComputedStyle(el, '::after').opacity) changed.push('::after');
  if (base && base.before !== getComputedStyle(el, '::before').boxShadow + getComputedStyle(el, '::before').opacity) changed.push('::before');
  const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const points = [[0.5, 0.5], [0.25, 0.25], [0.75, 0.25], [0.25, 0.75], [0.75, 0.75]]
    .map(([fx, fy]) => [r.left + r.width * fx, r.top + r.height * fy])
    .filter(([x, y]) => x >= 0 && y >= 0 && x < vw && y < vh);
  let hidden = 0, occluder = null;
  for (const [x, y] of points) {
    const hit = document.elementFromPoint(x, y);
    const label = hit && hit.closest && hit.closest('label');
    if (hit && (hit === el || el.contains(hit) || hit.contains(el) || (label && label.control === el))) continue;
    hidden += 1;
    if (!occluder && hit) occluder = path(hit);
  }
  const inViewport = r.bottom > 0 && r.top < vh && r.right > 0 && r.left < vw;
  const dialog = el.closest('dialog[open], [aria-modal=true], [role=dialog], [role=alertdialog]');
  let name = (el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) || el.innerText || el.value || el.getAttribute('title') || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
  return {
    key: el.dataset.uiagIdx !== undefined ? 'idx:' + el.dataset.uiagIdx : 'sel:' + selector,
    selector, name, tag: el.tagName.toLowerCase(), role: el.getAttribute('role'),
    box: { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) },
    indicator: outline ? 'outline' : (changed.length ? 'style-change:' + changed.join(',') : 'none-detected'),
    in_viewport: inViewport,
    obscured: !inViewport ? 'off-viewport' : (points.length && hidden === points.length ? 'fully-obscured' : (hidden ? 'partially-obscured' : 'visible')),
    occluder,
    in_dialog: dialog ? path(dialog) : null,
  };
}
"""

OPEN_DIALOGS_JS = """
() => [...document.querySelectorAll('dialog[open], [aria-modal=true], [role=dialog], [role=alertdialog]')]
  .filter((d) => { const r = d.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(d).visibility !== 'hidden'; }).length
"""


def detect_cycle(sequence):
    keys = [s["key"] for s in sequence]
    last = keys[-1]
    positions = [i for i, k in enumerate(keys) if k == last]
    if len(positions) < 3:
        return None
    period = positions[-1] - positions[-2]
    if period <= 0 or positions[-2] - positions[-3] != period:
        return None
    window = keys[positions[-2]:positions[-1]]
    if keys[positions[-3]:positions[-2]] != window:
        return None
    return window


def walk(page, max_steps, reverse=False):
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); window.scrollTo(0, 0); }")
    key = "Shift+Tab" if reverse else "Tab"
    sequence = []
    for _ in range(max_steps):
        page.keyboard.press(key)
        page.wait_for_timeout(30)
        info = page.evaluate(ACTIVE_JS)
        sequence.append(info)
        if len(sequence) > 1 and info["key"] == sequence[0]["key"] and info["key"] != "BODY":
            return sequence, "full-cycle", None
        cycle = detect_cycle(sequence)
        if cycle is not None:
            if "BODY" in cycle or (sequence[0]["key"] in cycle):
                return sequence, "full-cycle", None
            return sequence, "loop", cycle
    return sequence, "limit-reached", None


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser, default_viewports="laptop")
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-steps", type=int, default=0, help="0 = number of focusable elements + 15 (max 400)")
    parser.add_argument("--reverse", action="store_true", help="Also walk with Shift+Tab")
    args = parser.parse_args()

    summary = {"tool": "keyboard_walk", "url": args.url, "created": now_iso(), "configs": []}
    with browser_session(args) as (browser, browser_info):
        for viewport in resolve_viewports(args.viewports):
            cfg = build_config(viewport, args)
            cid = config_id(cfg)
            context, page, logs, clock, steps = prepare_page(browser, cfg, args)
            focusables = page.evaluate(MARK_FOCUSABLES_JS)
            max_steps = args.max_steps or min(400, len(focusables) + 15)
            sequence, outcome, loop = walk(page, max_steps)

            issues = []
            reached = {s["key"] for s in sequence}
            if outcome == "loop":
                dialog_scope = {s["in_dialog"] for s in sequence if s["key"] in loop}
                if len(dialog_scope) == 1 and None not in dialog_scope:
                    open_before = page.evaluate(OPEN_DIALOGS_JS)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(150)
                    open_after = page.evaluate(OPEN_DIALOGS_JS)
                    after_escape = page.evaluate(ACTIVE_JS)
                    if open_after >= open_before:
                        issues.append({"controls": ["STK-03", "ACC-03"], "kind": "dialog-not-closable-with-escape", "dialog": next(iter(dialog_scope))})
                    else:
                        issues.append({"controls": ["STK-03"], "kind": "dialog-closed-by-escape-check-focus-return", "focus_after": after_escape.get("selector"), "level": "info"})
                else:
                    issues.append({
                        "controls": ["ACC-03"], "kind": "focus-trap",
                        "loop": [s["selector"] for s in sequence if s["key"] in loop][: len(loop)],
                        "note": "Check that no documented way out exists (WCAG 2.1.2, to confirm).",
                    })
            elif outcome == "limit-reached":
                issues.append({"controls": ["ACC-02"], "kind": "incomplete-walk", "note": f"Cycle not closed within {max_steps} key presses."})

            if outcome == "full-cycle":
                visible_idx = {f"idx:{f['idx']}" for f in focusables if f["visible"]}
                unreachable = sorted(visible_idx - reached, key=lambda k: int(k.split(":")[1]))
                if unreachable:
                    selectors = page.evaluate(
                        "(ids) => ids.map((i) => { const el = document.querySelector(`[data-uiag-idx=\"${i}\"]`); return el ? (el.id ? '#' + el.id : el.outerHTML.slice(0, 120)) : i; })",
                        [k.split(":")[1] for k in unreachable],
                    )
                    issues.append({"controls": ["ACC-02"], "kind": "unreachable-elements", "items": selectors[:25]})

            stops = [s for s in sequence if s["key"] != "BODY"]
            unique_stops = list({s["key"]: s for s in stops}.values())
            for stop in unique_stops:
                if stop["indicator"] == "none-detected":
                    issues.append({"controls": ["ACC-04"], "kind": "focus-without-detected-indicator", "selector": stop["selector"], "box": stop["box"], "confidence": "medium"})
                if stop["obscured"] == "fully-obscured":
                    issues.append({"controls": ["STK-02"], "kind": "focus-fully-obscured", "selector": stop["selector"], "occluder": stop["occluder"], "box": stop["box"]})
                elif stop["obscured"] == "off-viewport":
                    issues.append({"controls": ["STK-02"], "kind": "focus-off-viewport", "selector": stop["selector"], "box": stop["box"]})
                elif stop["obscured"] == "partially-obscured":
                    issues.append({"controls": ["STK-02"], "kind": "focus-partially-obscured", "selector": stop["selector"], "occluder": stop["occluder"], "level": "info"})

            backwards = []
            for prev, cur in zip(stops, stops[1:]):
                if cur["box"]["y"] + cur["box"]["h"] < prev["box"]["y"] - 40 and not (cur["in_dialog"] or prev["in_dialog"]):
                    backwards.append({"from": prev["selector"], "to": cur["selector"]})
            if backwards:
                issues.append({"controls": ["ACC-04"], "kind": "visual-backtracks-to-check", "items": backwards[:15], "level": "info"})

            reverse_result = None
            if args.reverse:
                page.evaluate(MARK_FOCUSABLES_JS)
                reverse_sequence, reverse_outcome, _ = walk(page, max_steps, reverse=True)
                reverse_result = {"outcome": reverse_outcome, "stops": len(reverse_sequence)}

            blocking = [i for i in issues if i.get("level") != "info"]
            report = {
                "config_id": cid,
                "manifest": manifest(cfg, browser_info, args, clock, steps),
                "focusables": len(focusables),
                "outcome": outcome,
                "result": "issues" if blocking else "clean",
                "order": [{"n": n, "selector": s.get("selector", "body (outside focusable elements)"), "name": s.get("name"), "indicator": s.get("indicator"), "obscured": s.get("obscured")} for n, s in enumerate(sequence, 1)],
                "issues": issues,
                "reverse": reverse_result,
                "limitations": "Focus indicator detected by comparing styles (medium confidence); screen reader output not tested.",
            }
            out_dir = Path(args.out) / cid
            write_json(out_dir / "keyboard.json", report)
            summary["configs"].append({"config_id": cid, "report": str(out_dir / "keyboard.json"), "outcome": outcome, "result": report["result"], "issues": [i["kind"] for i in issues]})
            context.close()
    emit(summary)


if __name__ == "__main__":
    main()
