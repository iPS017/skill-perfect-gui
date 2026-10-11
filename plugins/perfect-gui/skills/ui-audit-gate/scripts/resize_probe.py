#!/usr/bin/env python3
"""Behaviour when the available space changes.

--mode state    : fills the fields, resizes (rotation, folding, split screen) and checks
                  that values, focus, open dialogs and the page are preserved.
--mode keyboard : emulates a virtual keyboard by reducing the viewport height (resizes-content model)
                  and checks that the focused field and the primary action stay reachable.

Examples:
  python3 resize_probe.py --url URL --mode state --widths 1366,960,600,390,1366
  python3 resize_probe.py --url URL --mode keyboard --viewports mobile --field "#email" --action "#submit"
"""
from _common import (
    add_browser_args, base_parser, browser_session, build_config, config_id, emit, manifest,
    now_iso, prepare_page, resolve_viewports,
)

FIELDS_JS = """
(scope) => {
  const root = scope ? document.querySelector(scope) : document.body;
  const sel = 'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=file]):not([type=image]):not([disabled]), textarea:not([disabled]), select:not([disabled])';
  return [...root.querySelectorAll(sel)].filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  }).map((el, i) => {
    el.dataset.uiagField = String(i);
    return {
      i,
      selector: el.id ? '#' + CSS.escape(el.id) : (el.name ? `${el.tagName.toLowerCase()}[name="${el.name}"]` : `[data-uiag-field="${i}"]`),
      kind: el.tagName.toLowerCase() === 'select' ? 'select' : (['checkbox', 'radio'].includes(el.type) ? 'check' : 'text'),
      type: el.type,
    };
  });
}
"""

STATE_JS = """
(fields) => {
  const values = fields.map((f) => {
    const el = document.querySelector(f.selector);
    if (!el) return { selector: f.selector, present: false };
    return { selector: f.selector, present: true, value: f.kind === 'check' ? el.checked : el.value };
  });
  const active = document.activeElement;
  const dialogs = [...document.querySelectorAll('dialog[open], [aria-modal=true], [role=dialog]')]
    .filter((d) => d.getBoundingClientRect().width > 0).length;
  return {
    marker: window.__uiagMarker === 'present',
    values,
    active: active && active !== document.body ? (active.id ? '#' + active.id : active.tagName.toLowerCase() + (active.name ? `[name="${active.name}"]` : '')) : null,
    dialogs,
    scrollY: Math.round(window.scrollY),
    width: document.documentElement.clientWidth,
  };
}
"""

KEYBOARD_CHECK_JS = """
([fieldSel, actionSel]) => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const describe = (n) => n ? (n.id ? '#' + n.id : n.tagName.toLowerCase() + (n.className && typeof n.className === 'string' ? '.' + n.className.trim().split(/\\s+/).slice(0, 2).join('.') : '')) : null;
  const status = (el) => {
    const r = el.getBoundingClientRect();
    const inside = r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw;
    const cx = Math.min(Math.max(r.left + r.width / 2, 0), vw - 1), cy = Math.min(Math.max(r.top + r.height / 2, 0), vh - 1);
    const hit = document.elementFromPoint(cx, cy);
    const free = !!hit && (hit === el || el.contains(hit) || (hit.closest('label') && hit.closest('label').control === el));
    return { inside, free, occluder: free ? null : describe(hit), rect: { top: Math.round(r.top), bottom: Math.round(r.bottom) } };
  };
  const field = document.querySelector(fieldSel);
  const action = document.querySelector(actionSel);
  if (!field || !action) return { error: `not found: ${!field ? fieldSel : actionSel}` };
  const fieldState = status(field);
  const scrollers = [];
  for (let a = action.parentElement; a && a !== document.documentElement; a = a.parentElement) {
    const cs = getComputedStyle(a);
    if (cs.overflowY !== 'visible') scrollers.push({ el: a, mode: cs.overflowY, top: a.scrollTop });
  }
  action.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  const programmaticOnly = scrollers.filter((s) => s.el.scrollTop !== s.top && ['hidden', 'clip'].includes(s.mode)).map((s) => describe(s.el));
  const actionState = status(action);
  return {
    viewport_height: vh,
    field: fieldState,
    action: { ...actionState, programmatic_only_scroll: programmaticOnly },
  };
}
"""


def state_mode(page, args, cfg):
    fields = page.evaluate(FIELDS_JS, args.scope)
    for field in fields:
        try:
            if field["kind"] == "text":
                value = "2026-01-15" if field["type"] == "date" else ("42" if field["type"] == "number" else ("uiag@example.com" if field["type"] == "email" else f"uiag{field['i']}"))
                page.fill(field["selector"], value)
            elif field["kind"] == "check":
                page.check(field["selector"])
            elif field["kind"] == "select":
                page.evaluate("(s) => { const el = document.querySelector(s); if (el.options.length > 1) { el.selectedIndex = el.options.length - 1; el.dispatchEvent(new Event('change', { bubbles: true })); } }", field["selector"])
        except Exception as exc:
            field["fill_error"] = type(exc).__name__
    if fields:
        page.focus(fields[-1]["selector"])
    page.evaluate("() => { window.__uiagMarker = 'present'; }")
    reference = page.evaluate(STATE_JS, fields)
    widths = [int(w) if w != "current" else cfg["width"] for w in args.widths.split(",")]
    height = args.height or cfg["height"]
    timeline = []
    issues = []
    for width in widths:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(args.settle_ms)
        snapshot = page.evaluate(STATE_JS, fields)
        lost = [
            {"selector": ref["selector"], "before": ref.get("value"), "after": now.get("value") if now["present"] else "element missing"}
            for ref, now in zip(reference["values"], snapshot["values"])
            if ref["present"] and (not now["present"] or now["value"] != ref["value"])
        ]
        step = {"width": width, "height": height, "values_lost": lost, "page_reloaded": not snapshot["marker"], "focus": snapshot["active"], "dialogs": snapshot["dialogs"]}
        timeline.append(step)
        if lost:
            issues.append({"controls": ["ROB-06", "FRM-04"], "kind": "values-lost", "width": width, "items": lost})
        if not snapshot["marker"]:
            issues.append({"controls": ["ROB-06"], "kind": "page-reloaded", "width": width})
        if reference["active"] and snapshot["active"] != reference["active"]:
            issues.append({"controls": ["ROB-06"], "kind": "focus-lost", "width": width, "before": reference["active"], "after": snapshot["active"]})
        if snapshot["dialogs"] < reference["dialogs"]:
            issues.append({"controls": ["ROB-06"], "kind": "dialog-closed", "width": width})
        if not snapshot["marker"]:
            break
    return {"fields": len(fields), "reference": reference, "timeline": timeline, "issues": issues}


def keyboard_mode(page, args, cfg):
    field = args.field
    if not field:
        fields = page.evaluate(FIELDS_JS, args.scope)
        texts = [f for f in fields if f["kind"] == "text"]
        if not texts:
            return {"error": "no text field found, specify --field"}
        field = texts[-1]["selector"]
    action = args.action or page.evaluate(
        "(s) => { const f = document.querySelector(s); const form = f && f.form; const b = form && form.querySelector('[type=submit], button:not([type])'); return b ? (b.id ? '#' + b.id : null) : null; }",
        field,
    )
    if not action:
        return {"error": "primary action not found, specify --action"}
    full_height = cfg["height"]
    reduced = max(120, round(full_height * args.ratio))
    page.focus(field)
    page.set_viewport_size({"width": page.viewport_size["width"], "height": reduced})
    page.wait_for_timeout(args.settle_ms)
    page.focus(field)
    check = page.evaluate(KEYBOARD_CHECK_JS, [field, action])
    page.set_viewport_size({"width": page.viewport_size["width"], "height": full_height})
    if "error" in check:
        return check
    issues = []
    if not (check["field"]["inside"] and check["field"]["free"]):
        issues.append({"controls": ["ENV-02"], "kind": "focused-field-hidden", "detail": check["field"]})
    if check["action"]["programmatic_only_scroll"]:
        issues.append({"controls": ["ENV-02"], "kind": "action-reachable-only-by-script", "containers": check["action"]["programmatic_only_scroll"]})
    elif not (check["action"]["inside"] and check["action"]["free"]):
        issues.append({"controls": ["ENV-02"], "kind": "action-hidden-or-off-screen", "detail": check["action"]})
    return {
        "field": field, "action": action, "full_height": full_height, "reduced_height": reduced, "check": check, "issues": issues,
        "fidelity": "emulation (resizes-content): native keyboard, resizes-visual mode and system bars not reproduced",
    }


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser, default_viewports="laptop")
    parser.add_argument("--mode", required=True, choices=["state", "keyboard"])
    parser.add_argument("--scope", help="Selector limiting the filled fields")
    parser.add_argument("--widths", default="current,960,600,390,current", help="Successive widths in CSS px (current = initial width)")
    parser.add_argument("--height", type=int, default=0)
    parser.add_argument("--field", help="Field to focus (keyboard mode)")
    parser.add_argument("--action", help="Primary action to reach (keyboard mode)")
    parser.add_argument("--ratio", type=float, default=0.55, help="Share of the height left with the keyboard open")
    parser.add_argument("--settle-ms", type=int, default=350)
    parser.add_argument("--out", help="Also write the result to this JSON file (for summarize.py)")
    args = parser.parse_args()

    summary = {"tool": "resize_probe", "mode": args.mode, "url": args.url, "created": now_iso(), "configs": []}
    with browser_session(args) as (browser, browser_info):
        for viewport in resolve_viewports(args.viewports):
            cfg = build_config(viewport, args)
            context, page, logs, clock, steps = prepare_page(browser, cfg, args)
            outcome = state_mode(page, args, cfg) if args.mode == "state" else keyboard_mode(page, args, cfg)
            outcome["result"] = "error" if "error" in outcome else ("issues" if outcome["issues"] else "clean")
            summary["configs"].append({"config_id": config_id(cfg), "manifest": manifest(cfg, browser_info, args, clock, steps), **outcome})
            context.close()
    if args.out:
        from _common import write_json
        write_json(args.out, summary)
    emit(summary)


if __name__ == "__main__":
    main()
