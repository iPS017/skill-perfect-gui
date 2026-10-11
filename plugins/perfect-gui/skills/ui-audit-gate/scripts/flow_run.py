#!/usr/bin/env python3
"""Run user flows with assertions and automatic evidence (PAR-01, FRM-03, ACC-02 and any scripted journey).

A flows file holds one or more flows. Each step is either an action (same kinds as --actions: goto, click,
fill, press, tab_to, upload, set_offline, view, wait_for...) or an assertion:
  expect_visible SEL | expect_hidden SEL | expect_text [SEL, TEXT] | expect_attr [SEL, ATTR, VALUE]
  expect_url SUBSTRING | expect_focus SEL | expect_count [SEL, N] | expect_no_console_error true
  screenshot LABEL
Prefer role selectors: role=tab[name="Skin"], role=button[name="Sign in"]. A text= selector can hit a
hidden heading instead of the control.

Example flows.json:
  {"flows": [{"name": "wrong password", "view": "login-screen", "steps": [
      {"fill": ["role=textbox[name=\\"Password\\"]", "wrong"]}, {"press": "Enter"},
      {"expect_visible": "role=alert"}, {"expect_attr": ["#password", "aria-invalid", "true"]},
      {"expect_focus": "#password"}, {"screenshot": "error-shown"}]}]}

  python3 flow_run.py --url http://localhost:1420/ --flows flows.json --out .ui-audit/RUN-x/flows
  python3 flow_run.py ... --keyboard-only     (refuses click and hover steps: proves the flow works with the keyboard)
"""
import json
from pathlib import Path

from _common import (
    add_browser_args, base_parser, browser_session, build_config, config_id, emit, manifest, now_iso,
    open_page, read_json, resolve_viewports, run_actions, safe_name, stabilize, write_json,
)

POINTER_ACTIONS = {"click", "click_effect", "click_optional", "hover", "check"}
ASSERTIONS = {"expect_visible", "expect_hidden", "expect_text", "expect_attr", "expect_url", "expect_focus", "expect_count", "expect_no_console_error", "screenshot"}


def assert_step(page, kind, value, logs, shot_dir, flow_id, index):
    if kind == "expect_visible":
        page.locator(value).first.wait_for(state="visible", timeout=5000)
        return f"{value} visible"
    if kind == "expect_hidden":
        page.locator(value).first.wait_for(state="hidden", timeout=5000)
        return f"{value} hidden"
    if kind == "expect_text":
        text = page.locator(value[0]).first.inner_text(timeout=5000)
        if value[1] not in text:
            raise AssertionError(f"text of {value[0]} is {text[:120]!r}, expected to contain {value[1]!r}")
        return f"{value[0]} contains {value[1]!r}"
    if kind == "expect_attr":
        actual = page.locator(value[0]).first.get_attribute(value[1], timeout=5000)
        if actual != value[2]:
            raise AssertionError(f"{value[0]}[{value[1]}] is {actual!r}, expected {value[2]!r}")
        return f"{value[0]}[{value[1]}] = {value[2]!r}"
    if kind == "expect_url":
        if value not in page.url:
            raise AssertionError(f"URL is {page.url}, expected to contain {value}")
        return f"URL contains {value}"
    if kind == "expect_focus":
        focused = page.locator(value).first.evaluate("(el) => el === document.activeElement || el.contains(document.activeElement)")
        if not focused:
            active = page.evaluate("() => { const a = document.activeElement; return a ? a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') : null; }")
            raise AssertionError(f"focus is on {active}, expected {value}")
        return f"focus on {value}"
    if kind == "expect_count":
        count = page.locator(value[0]).count()
        if count != int(value[1]):
            raise AssertionError(f"{value[0]} matches {count} elements, expected {value[1]}")
        return f"{value[0]} x {value[1]}"
    if kind == "expect_no_console_error":
        errors = [entry for entry in logs if entry["type"] in ("error", "pageerror")]
        if errors:
            raise AssertionError(f"{len(errors)} console errors: {errors[0]['text'][:160]}")
        return "no console error"
    if kind == "screenshot":
        path = shot_dir / f"{flow_id}-{index:02d}-{safe_name(str(value))}.png"
        page.screenshot(path=str(path), animations="disabled")
        return str(path)
    raise AssertionError(f"unknown assertion {kind}")


def run_flow(browser, flow, cfg, args, out_dir, browser_info):
    flow_id = safe_name(flow.get("name", "flow"))
    shot_dir = out_dir / config_id(cfg) / "screens"
    shot_dir.mkdir(parents=True, exist_ok=True)
    context, page, logs, clock = open_page(browser, cfg, args)
    url = flow.get("url") or args.url
    page.goto(url, wait_until="load")
    stabilize(page, args)
    steps_log, results, status = [], [], "passed"
    steps = ([{"view": flow["view"]}] if flow.get("view") else []) + flow.get("steps", [])
    for index, step in enumerate(steps, 1):
        (kind, value), = step.items()
        entry = {"n": index, "step": step}
        try:
            if args.keyboard_only and kind in POINTER_ACTIONS:
                raise AssertionError(f"pointer action '{kind}' in keyboard-only mode: use tab_to and press")
            if kind in ASSERTIONS:
                entry["checked"] = assert_step(page, kind, value, logs, shot_dir, flow_id, index)
            else:
                run_actions(page, [step], url, steps_log)
                page.wait_for_timeout(args.step_wait_ms)
            entry["status"] = "passed"
        except Exception as exc:
            entry["status"] = "failed"
            entry["error"] = str(exc).strip().splitlines()[0][:300] if str(exc).strip() else type(exc).__name__
            failure = shot_dir / f"{flow_id}-{index:02d}-failure.png"
            try:
                page.screenshot(path=str(failure), animations="disabled")
                entry["screenshot"] = str(failure)
            except Exception:
                pass
            status = "failed"
            results.append(entry)
            break
        results.append(entry)
    final = shot_dir / f"{flow_id}-final.png"
    try:
        page.screenshot(path=str(final), animations="disabled")
    except Exception:
        final = None
    report = {
        "flow": flow.get("name"), "status": status, "keyboard_only": args.keyboard_only, "config_id": config_id(cfg),
        "manifest": manifest(cfg, browser_info, args, clock, [{"goto": url}, *[r["step"] for r in results]]),
        "steps": results, "final_screenshot": str(final) if final else None,
        "console": [entry for entry in logs if entry["type"] in ("error", "pageerror")][:20],
    }
    context.close()
    return report


def main():
    parser = base_parser(__doc__)
    add_browser_args(parser, default_viewports="laptop")
    parser.add_argument("--flows", required=True, help="JSON file: {\"flows\": [...]} or a single flow object")
    parser.add_argument("--only", help="Comma-separated flow names")
    parser.add_argument("--out", required=True)
    parser.add_argument("--keyboard-only", action="store_true")
    parser.add_argument("--step-wait-ms", type=int, default=150)
    args = parser.parse_args()

    data = read_json(args.flows)
    if data is None:
        data = json.loads(args.flows)
    flows = data.get("flows", [data]) if isinstance(data, dict) else data
    if args.only:
        wanted = set(args.only.split(","))
        flows = [f for f in flows if f.get("name") in wanted]
    out_dir = Path(args.out)
    reports = []
    with browser_session(args) as (browser, browser_info):
        for viewport in resolve_viewports(args.viewports):
            cfg = build_config(viewport, args)
            for flow in flows:
                reports.append(run_flow(browser, flow, cfg, args, out_dir, browser_info))
    write_json(out_dir / "flows.json", {"tool": "flow_run", "created_at": now_iso(), "flows": reports})
    failed = [r for r in reports if r["status"] != "passed"]
    emit({
        "tool": "flow_run", "result": "issues" if failed else "clean", "report": str(out_dir / "flows.json"),
        "passed": len(reports) - len(failed), "failed": len(failed),
        "failures": [{"flow": r["flow"], "config_id": r["config_id"], "step": r["steps"][-1]["n"], "error": r["steps"][-1].get("error"),
                      "screenshot": r["steps"][-1].get("screenshot")} for r in failed],
    })


if __name__ == "__main__":
    main()
