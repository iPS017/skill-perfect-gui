#!/usr/bin/env python3
"""Acceptance scenarios for the ui-audit-gate skill.

Serves the test application (tests/fixture-app) with injectable defects (?scn=01,03),
runs the skill scripts and checks that they detect each defect, with no false positive on the
healthy version. Also checks the decision gate, the research log, the hook and the impact analysis.

Usage: python3 tests/run_scenarios.py [--only SCN-03,SCN-11] [--keep]
Requirements: Playwright and Pillow (scripts/setup.sh), a Chromium or Chrome browser.
"""
import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = TESTS_DIR.parent
SCRIPTS = PLUGIN_DIR / "skills" / "ui-audit-gate" / "scripts"
HOOK = PLUGIN_DIR / "hooks" / "gate_hook.py"
FUNDAMENTALS = json.loads((PLUGIN_DIR / "skills" / "ui-audit-gate" / "config" / "levels.json").read_text(encoding="utf-8"))["fundamental"]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class DefectHandler(QuietHandler):
    def do_GET(self):
        path = self.translate_path(self.path)
        if path.endswith("/"):
            path += "index.html"
        if path.endswith(".html") and Path(path).exists():
            body = Path(path).read_bytes().replace(b"<head>", b"<head><script>window.UIAG_DEFECTS=true</script>", 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def serve(directory, handler_class=QuietHandler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler_class, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class Harness:
    def __init__(self, work):
        self.work = Path(work)
        self.server, origin = serve(TESTS_DIR / "fixture-app")
        self.base = f"{origin}/index.html"
        self.site_server, self.site = serve(TESTS_DIR / "fixture-site")
        self.broken_server, self.broken_site = serve(TESTS_DIR / "fixture-site", DefectHandler)

    def url(self, scenario=None):
        return f"{self.base}?scn={scenario}" if scenario else self.base

    def script(self, name, *args, env=None, stdin=None):
        command = [sys.executable, str(SCRIPTS / name), *map(str, args)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, env={**os.environ, **(env or {})}, input=stdin)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = {"raw_stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}
        return result.returncode, data

    def inspect(self, out, scenario=None, viewports="laptop", *extra):
        code, data = self.script("inspect_page.py", "--url", self.url(scenario), "--viewports", viewports, "--out", self.work / out, "--no-axe", *extra)
        if code != 0:
            raise AssertionError(f"inspect_page code {code}: {json.dumps(data, ensure_ascii=False)[:600]}")
        reports = [json.loads(Path(c["report"]).read_text(encoding="utf-8")) for c in data["configs"]]
        return reports

    def keyboard(self, out, scenario=None, viewports="laptop"):
        code, data = self.script("keyboard_walk.py", "--url", self.url(scenario), "--viewports", viewports, "--out", self.work / out)
        if code != 0:
            raise AssertionError(f"keyboard_walk code {code}: {data}")
        return [json.loads(Path(c["report"]).read_text(encoding="utf-8")) for c in data["configs"]]

    def resize(self, scenario, *args):
        code, data = self.script("resize_probe.py", "--url", self.url(scenario), *args)
        if code != 0:
            raise AssertionError(f"resize_probe code {code}: {data}")
        return data["configs"][0]


def check(report, name):
    return report["checks"][name]


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def make_run(h, name, **overrides):
    root = h.work / name
    root.mkdir(parents=True, exist_ok=True)
    code, data = h.script("init_run.py", "--slug", name, "--root", root, "--no-gitignore")
    expect(code == 0, f"init_run failed: {data}")
    run = Path(data["run"])
    evidence = run / "inspect" / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    for folder in ("before", "after-fix-1", "after"):
        (run / folder).mkdir(exist_ok=True)
        (run / folder / "page.png").write_bytes(b"png")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["controls"] = [{"id": cid, "status": "passed", "evidence": ["inspect/evidence.json"]} for cid in FUNDAMENTALS]
    report["before_after"] = [{"config_id": "laptop", "before": "before/page.png", "after": "after/page.png"}]
    report["research"] = {"status": "not_done", "cause": "test"}
    report.update(overrides)
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def add_valid_reference(h, run):
    url = "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html"
    h.script("research_log.py", run, "query", "--text", "WCAG 2.2 target size minimum understanding", "--tool", "WebSearch", "--urls", url)
    h.script("research_log.py", run, "visit", "--url", url, "--tool", "WebFetch")
    code, data = h.script("research_log.py", run, "ref", "--json", json.dumps({
        "title": "Understanding SC 2.5.8", "url": url, "author_organization": "W3C WAI", "access_status": "accessed",
        "source_rank": 1, "question": "Target size", "transfer_limits": "AA",
    }))
    expect(code == 0, f"ref refused: {data}")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["research"] = {"status": "done", "cause": None}
    report["comparisons"] = [{"ref": data["id"], "observation": "o", "principle": "p", "gap": "e", "adaptation": "a", "benefit": "b", "nature": "REQUIREMENT"}]
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def verify(h, run, *flags):
    code, data = h.script("verify_report.py", run, *flags)
    return code, data


def defect(**fields):
    base = {"id": "DEF-001", "title": "t", "control": "GEO-02", "severity": "minor", "priority": "P3", "confidence": "medium",
            "nature": "PREFERENCE", "status": "open", "expected": "a", "observed": "o", "evidence": ["inspect/evidence.json"]}
    base.update(fields)
    return base


def scn_base(h):
    reports = h.inspect("base", None, "P0", "--scan-scroll")
    noisy = ["horizontal-overflow", "text-overflow", "occlusion", "target-size", "alignment", "contrast", "form-labels",
             "accessible-names", "form-errors", "images", "headings", "document", "landmarks", "console"]
    for report in reports:
        bad = {n: check(report, n)["items"][:2] for n in noisy if check(report, n)["result"] != "clean"}
        expect(not bad, f"false positives on the healthy version ({report['config_id']}): {json.dumps(bad, ensure_ascii=False)[:800]}")
        expect(not check(report, "target-size")["warnings"], f"unexpected target warnings: {check(report, 'target-size')['warnings'][:2]}")
    keyboard = h.keyboard("base-kb")[0]
    expect(keyboard["outcome"] == "full-cycle" and keyboard["result"] == "clean", f"keyboard on the healthy version: {keyboard['outcome']} {keyboard['issues']}")
    return f"{len(reports)} clean configurations, {keyboard['focusables']} focusable elements walked"


def scn_01(h):
    report = h.inspect("scn01", "01", "laptop", "--only", "alignment")[0]
    items = check(report, "alignment")["items"]
    expect(any(i["selector"] == "#share-button" and i["offset_px"] >= 5 for i in items), f"offset button not detected: {items}")
    return f"#share-button offset by {next(i['offset_px'] for i in items if i['selector'] == '#share-button')} px"


def scn_02(h):
    report = h.inspect("scn02", "02", "mobile-narrow", "--only", "text-overflow")[0]
    items = check(report, "text-overflow")["items"]
    hit = [i for i in items if i["selector"] == "#submit-booking"]
    expect(hit and hit[0]["kind"] == "clipped", f"clipped text not detected: {items}")
    return f"label clipped ({hit[0]['metrics']['scrollWidth']} > {hit[0]['metrics']['clientWidth']} px)"


def scn_03(h):
    report = h.inspect("scn03", "03", "mobile", "--only", "occlusion", "--scan-scroll")[0]
    items = check(report, "occlusion")["items"]
    pay = [i for i in items if i["selector"] == "#pay-button"]
    expect(pay and pay[0]["state"] == "covered-at-every-position", f"overlay not detected: {items}")
    expect(check(report, "occlusion")["result"] == "issues", "expected result: issues")
    return f"#pay-button covered by {pay[0]['occluders']}"


def scn_04(h):
    broken = h.inspect("scn04", "04", "767x900,768x900", "--only", "horizontal-overflow")
    by_width = {r["viewport"]["width"]: check(r, "horizontal-overflow") for r in broken}
    expect(by_width[767]["result"] == "issues" and by_width[767]["causes_page_scroll"], f"regression at 767 px not detected: {by_width[767]}")
    expect(by_width[768]["result"] == "clean", f"false positive at 768 px: {by_width[768]['items'][:2]}")
    healthy = check(h.inspect("scn04-base", None, "767x900", "--only", "horizontal-overflow")[0], "horizontal-overflow")
    expect(healthy["result"] == "clean", "false positive on the healthy version at 767 px")
    return f"{by_width[767]['page_scroll_width'] - by_width[767]['viewport_width']} px overflow at 767, nothing at 768"


def scn_05(h):
    report = h.keyboard("scn05", "05")[0]
    traps = [i for i in report["issues"] if i["kind"] == "focus-trap"]
    expect(traps, f"trap not detected: {report['outcome']} {report['issues']}")
    return f"loop on {traps[0]['loop']}"


def scn_06(h):
    submit = json.dumps([{"click": "#submit-booking"}])
    broken = check(h.inspect("scn06", "06", "laptop", "--only", "form-errors", "--actions", submit)[0], "form-errors")
    expect(broken["result"] == "issues" and any(i["kind"] == "unlinked-unannounced-message" for i in broken["items"]), f"poorly reported error not detected: {broken}")
    healthy = check(h.inspect("scn06-base", None, "laptop", "--only", "form-errors", "--actions", submit)[0], "form-errors")
    expect(healthy["result"] == "clean" and healthy["invalid_fields"] == 1, f"healthy version: {healthy}")
    return '"Error" message neither linked nor announced; healthy version compliant'


def scn_07(h):
    plain = check(h.inspect("scn07", "07", "laptop", "--only", "text-overflow")[0], "text-overflow")
    expect(plain["result"] == "clean", f"English labels should fit: {plain['items'][:2]}")
    pseudo = check(h.inspect("scn07-pseudo", "07", "laptop", "--only", "text-overflow", "--pseudo")[0], "text-overflow")
    tabs = [i for i in pseudo["items"] if "tab" in i["selector"]]
    expect(tabs, f"long translation overflow not detected: {pseudo['items'][:3]}")
    healthy = check(h.inspect("scn07-base", None, "laptop", "--only", "text-overflow", "--pseudo")[0], "text-overflow")
    expect(healthy["result"] == "clean", f"pseudo-locale false positive on the healthy version: {healthy['items'][:2]}")
    return f"{len(tabs)} tabs clipped in pseudo-locale"


def scn_08(h):
    broken = check(h.inspect("scn08", "08", "mobile", "--only", "target-size")[0], "target-size")
    flagged = broken["items"] + broken["warnings"]
    expect(any("btn" in i["selector"] or i["selector"].startswith("#") for i in flagged), f"shrunk targets not reported: {broken}")
    for folder, scenario in (("before", None), ("after", "08")):
        code, data = h.script("capture.py", "--url", h.url(scenario), "--viewports", "mobile", "--out", h.work / "scn08-diff" / folder, "--name", "page")
        expect(code == 0, f"capture failed: {data}")
    code, diff = h.script("visual_diff.py", "--before", h.work / "scn08-diff" / "before", "--after", h.work / "scn08-diff" / "after", "--out", h.work / "scn08-diff" / "diff")
    expect(code == 0 and diff["result"] == "issues", f"visual diff without difference: {diff}")
    return f"{len(flagged)} targets reported, visual diff: {diff['items'][0]['status']}"


def scn_09(h):
    broken = h.resize("09", "--mode", "state", "--viewports", "laptop", "--widths", "current,600,current")
    lost = [i for i in broken["issues"] if i["kind"] == "values-lost"]
    expect(lost, f"state loss not detected: {broken['issues']}")
    healthy = h.resize(None, "--mode", "state", "--viewports", "laptop", "--widths", "current,600,current")
    expect(healthy["result"] == "clean", f"false positive: {healthy['issues']}")
    return f"values lost at {lost[0]['width']} px: {[i['selector'] for i in lost[0]['items']]}"


def scn_10(h):
    args = ["--mode", "keyboard", "--viewports", "mobile", "--field", "#email", "--action", "#submit-booking"]
    broken = h.resize("10", *args)
    expect(any(i["kind"] == "action-reachable-only-by-script" for i in broken["issues"]), f"virtual keyboard: {broken}")
    healthy = h.resize(None, *args)
    expect(healthy["result"] == "clean", f"false positive: {healthy['issues']}")
    return "action hidden in an overflow:hidden container when the keyboard reduces the height"


def scn_11(h):
    run = make_run(h, "scn11")
    code, data = verify(h, run, "--apply", "--render")
    expect(code == 0 and data["computed_decision"] == "VALIDATED_TESTED_SCOPE", f"expected decision VALIDATED_TESTED_SCOPE: {data}")
    expect((run / "report.md").exists(), "report.md missing")
    code, logged = h.script("research_log.py", run, "unavailable", "--cause", "tool missing")
    expect(code == 0, "unavailable log entry")
    return "Web unavailable: decision capped at VALIDATED_TESTED_SCOPE"


def scn_12(h):
    code, data = h.script("capture.py", "--url", h.url(), "--viewports", "laptop", "--out", h.work / "scn12", "--browser-path", "/nonexistent/browser")
    expect(code == 3 and data.get("status") == "capability-missing", f"capture failure poorly reported: code {code} {data}")
    expect(not list((h.work / "scn12").rglob("*.png")), "no screenshot should exist")
    run = make_run(h, "scn12", before_after=[])
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    for control in report["controls"]:
        if control["id"] in ("GEO-02", "CTA-02"):
            control.update({"status": "not_verified", "reason": "capture failed", "reason_type": "technical", "evidence": []})
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run, "--apply")
    expect(data["computed_decision"] == "NOT_VALIDATED" and any(b.startswith("B5") for b in data["blocking"]), f"B5 expected: {data}")
    return "capture failed: capability-missing, then NOT_VALIDATED (B5)"


def scn_13(h):
    run = make_run(h, "scn13")
    code, data = h.script("research_log.py", run, "ref", "--json", json.dumps({
        "title": "Made up", "url": "https://example.org/never-seen", "author_organization": "?", "access_status": "accessed",
        "source_rank": 1, "question": "?", "transfer_limits": "?",
    }))
    expect(code == 1 and data["status"] == "refused", f"unseen reference accepted: {data}")
    (run / "research" / "references.json").write_text(json.dumps([{"id": "REF-001", "title": "x", "url": "https://example.org/never-seen", "access_status": "accessed"}]), encoding="utf-8")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["research"] = {"status": "done"}
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run)
    expect(code == 1 and any("not traced" in e for e in data["errors"]), f"fabricated reference not detected: {data}")
    code, data = h.script("research_log.py", run, "query", "--text", "form error for jean.dupont@acme-interne.fr on localhost")
    expect(code == 1 and data["status"] == "refused", "sensitive query accepted")
    return "unseen reference refused, report invalid, sensitive query refused"


def scn_14(h):
    run = make_run(h, "scn14", findings=[defect()])
    add_valid_reference(h, run)
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["controls"].append({"id": "ACC-11", "status": "not_verified", "reason": "no screen reader", "reason_type": "human"})
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run, "--apply", "--render")
    expect(code == 0 and data["computed_decision"] == "VALIDATED_FULL_PROTOCOL", f"a preference must not block: {data}")
    expect(data["human_checks"], "ACC-11 must be listed as a human check")
    return "minor preference not blocking; ACC-11 listed for a human"


def scn_gate_rules(h):
    run = make_run(h, "rules-critical", findings=[defect(severity="critical", nature="REQUIREMENT", control="STK-01")])
    code, data = verify(h, run, "--apply")
    expect(data["computed_decision"] == "NOT_VALIDATED", f"critical: {data['computed_decision']}")
    exception = {"accepted_by": "user", "date": "2026-10-11", "quote": "ship it anyway, I will fix it tomorrow"}
    run = make_run(h, "rules-exception", findings=[defect(severity="major", nature="REQUIREMENT", status="accepted_exception", exception=exception)])
    add_valid_reference(h, run)
    code, data = verify(h, run, "--apply")
    expect(data["computed_decision"] == "VALIDATED_WITH_EXCEPTIONS", f"exception: {data['computed_decision']} {data['errors']}")
    run = make_run(h, "rules-mock", mode="mockup")
    code, data = verify(h, run, "--apply")
    expect(data["computed_decision"] == "LIMITED_VALIDATION", f"mockup: {data['computed_decision']}")
    run = make_run(h, "rules-fix", fixes=[{"findings": ["DEF-001"]}])
    code, data = verify(h, run, "--apply")
    expect(any("after-fix" in b for b in data["blocking"]), f"re-capture after fix required: {data['blocking']}")
    run = make_run(h, "rules-fake-pass")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["controls"][0]["evidence"] = ["inspect/missing.png"]
    report["decision"] = "VALIDATED_FULL_PROTOCOL"
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run)
    expect(code == 1 and any("evidence not found" in e for e in data["errors"]), "pass without evidence accepted")
    expect(any("differs from the computed decision" in e for e in data["errors"]), "overstated decision accepted")
    return "critical, exception, mockup, re-capture, missing evidence, overstated decision"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def scn_hook(h):
    repo = h.work / "hook-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "app.css").write_text("body{color:#000}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "app.css").write_text("body{color:#111}\n")

    def hook(extra=None, env=None):
        payload = json.dumps({"cwd": str(repo), "stop_hook_active": False, **(extra or {})})
        result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=60)
        return json.loads(result.stdout) if result.stdout.strip() else None

    blocked = hook()
    expect(blocked and blocked.get("decision") == "block", f"the hook should block: {blocked}")
    again = hook({"stop_hook_active": True})
    expect(again and "systemMessage" in again and "decision" not in again, f"no second block: {again}")
    expect(hook(env={"UI_AUDIT_GATE": "off"}) is None, "UI_AUDIT_GATE=off must disable")
    time.sleep(1.1)
    code, data = h.script("init_run.py", "--slug", "hook", "--root", repo)
    run = Path(data["run"])
    (run / "inspect" / "evidence.json").write_text("{}")
    (run / "after").mkdir(exist_ok=True)
    (run / "after" / "page.png").write_bytes(b"png")
    report = json.loads((run / "report.json").read_text())
    report["controls"] = [{"id": cid, "status": "passed", "evidence": ["inspect/evidence.json"]} for cid in FUNDAMENTALS]
    report["before_after"] = [{"after": "after/page.png"}]
    report["research"] = {"status": "not_done", "cause": "test"}
    (run / "report.json").write_text(json.dumps(report))
    still = hook()
    expect(still and still.get("decision") == "block", "report without a decision: the hook must still block")
    h.script("verify_report.py", run, "--apply")
    expect(hook() is None, f"consistent report: the hook must let it through ({hook()})")
    return "blocks, does not block twice, can be disabled, lets through after a consistent report"


def scn_impact(h):
    repo = h.work / "impact-repo"
    (repo / "src" / "components" / "ui").mkdir(parents=True)
    (repo / "src" / "pages").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "src" / "tokens.css").write_text(":root { --space-btn: 16px; }\n")
    (repo / "src" / "components" / "ui" / "Button.tsx").write_text("export const Button = () => <button style={{padding: 'var(--space-btn)'}} />;\n")
    (repo / "src" / "pages" / "Home.tsx").write_text("import { Button } from '../components/ui/Button';\nexport default () => <Button />;\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "src" / "tokens.css").write_text(":root { --space-btn: 8px; }\n")
    code, data = h.script("impact_scan.py", "--root", repo)
    expect(code == 0 and data["suggested_level"] == "N3", f"expected level N3: {data.get('suggested_level')} {data.get('reasons')}")
    expect("src/components/ui/Button.tsx" in data["impacted_files"], f"token propagation missing: {data['impacted_files']}")
    return "token changed: N3, Button.tsx detected as a consumer"


def scn_pseudo(h):
    source = h.work / "en.json"
    source.write_text(json.dumps({"hello": "Hello {name}", "nested": {"count": "%d items"}}), encoding="utf-8")
    target = h.work / "pseudo.json"
    code, data = h.script("pseudo_locale.py", source, target)
    out = json.loads(target.read_text(encoding="utf-8"))
    expect(code == 0 and "{name}" in out["hello"] and out["hello"].startswith("[") and "%d" in out["nested"]["count"], f"pseudo-locale: {out}")
    return out["hello"]


def scn_explore(h):
    suite = h.work / "ui-scenes"
    code, data = h.script("explore_site.py", "--url", f"{h.site}/index.html", "--out", suite / "site-map.json")
    expect(code == 0 and data["pages"] >= 4, f"exploration: {data}")
    code, data = h.script("generate_scenarios.py", "--site-map", suite / "site-map.json", "--out", suite / "scenes.json", "--export-playwright", suite / "ui-scenes.spec.ts")
    expect(code == 0 and data["scenes"] >= 30, f"generation: {data}")
    scenes = json.loads((suite / "scenes.json").read_text(encoding="utf-8"))
    titles = " ".join(s["title"] for s in scenes["scenes"])
    expect("Delete my account" not in titles and any("Delete my account" in n["element"] for n in scenes["not_covered"]), "the destructive action must be excluded and listed")
    close = [s for s in scenes["scenes"] if '"Close"' in s["title"]]
    expect(close and close[0]["actions"][1] == {"click": "#contact-button"}, f"the Close button must be preceded by opening the dialog: {close[:1]}")
    expect({"page", "control", "toggle", "tab", "form", "url-param", "setting", "environment"} <= set(data["by_category"]), f"categories: {data['by_category']}")
    spec = (suite / "ui-scenes.spec.ts").read_text(encoding="utf-8")
    expect("toHaveScreenshot" in spec and spec.count("test(") == data["scenes"], "incomplete Playwright export")
    ids_before = [s["id"] for s in scenes["scenes"]]
    h.script("generate_scenarios.py", "--site-map", suite / "site-map.json", "--out", suite / "scenes.json")
    ids_after = [s["id"] for s in json.loads((suite / "scenes.json").read_text(encoding="utf-8"))["scenes"]]
    expect(ids_before == ids_after, "scene identifiers must stay stable")

    code, data = h.script("play_scenarios.py", "--suite", suite, "--url", f"{h.site}/", "--mode", "baseline", "--workers", "2")
    expect(code == 0 and data["status"] == "ok", f"baseline on the healthy version: {data}")
    code, healthy = h.script("play_scenarios.py", "--suite", suite, "--url", f"{h.site}/", "--workers", "2")
    expect(healthy["status"] == "ok" and healthy["blocking"] == 0 and healthy["visual_changes"] == 0, f"review of the healthy version: {healthy}")
    code, broken = h.script("play_scenarios.py", "--suite", suite, "--url", f"{h.broken_site}/", "--workers", "2")
    expected = {"horizontal-overflow", "dead-click", "scroll-locked", "theme-not-adapted", "untranslated-content", "javascript-error"}
    found = set(broken["blocking_types"])
    expect(broken["status"] == "failed" and expected <= found, f"missing defects: {expected - found}; found: {broken['blocking_types']}")
    expect("style-inconsistency" in broken["other_types"] and broken["visual_changes"] > 0, f"style and visual diff: {broken}")
    code, accepted = h.script("play_scenarios.py", "--suite", suite, "--accept", "all")
    expect(accepted["status"] == "failed", "accepting visual changes must not clear blocking anomalies")
    return f"{data['scenes']} scenes x 2 viewports; healthy: ok; broken: {sum(broken['blocking_types'].values())} blocking anomalies ({', '.join(sorted(found))})"


def scn_publish(h):
    repo = h.work / "publish-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "app.css").write_text("body{color:#000}\n")
    suite = repo / "ui-scenes"
    suite.mkdir()
    (suite / "scenes.json").write_text(json.dumps({"scenes": [{"id": "S-0001"}]}))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    sys.path.insert(0, str(SCRIPTS))
    from _common import ui_fingerprint
    import hashlib

    def review(status):
        (suite / "last-review.json").write_text(json.dumps({
            "mode": "review", "status": status, "counts": {"blocking": 0 if status == "ok" else 3, "visual_changes": 0},
            "ui_fingerprint": ui_fingerprint(repo), "scenes_fingerprint": hashlib.sha1((suite / "scenes.json").read_bytes()).hexdigest(),
        }))

    def hook(command, env=None):
        payload = json.dumps({"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": command}})
        result = subprocess.run([sys.executable, str(PLUGIN_DIR / "hooks" / "prepublish_hook.py")], input=payload, capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=60)
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout.strip() else "allow"

    expect(hook("git push origin main") == "deny", "without a review, publishing must be blocked")
    review("ok")
    expect(hook("git push origin main") == "allow", "valid review: publishing allowed")
    expect(hook("ls -la") == "allow", "ordinary command not affected")
    (repo / "app.css").write_text("body{color:#111}\n")
    expect(hook("npm publish") == "deny", "UI changed after the review: block expected")
    review("ok")
    expect(hook("vercel --prod") == "allow", "review redone: allowed")
    review("failed")
    expect(hook("git push") == "deny", "failed review: block expected")
    expect(hook("git push", {"UI_AUDIT_PUBLISH_GATE": "ask"}) == "ask", "ask mode")
    expect(hook("git push", {"UI_AUDIT_PUBLISH_GATE": "off"}) == "allow", "off mode")
    return "blocks without a review, after a UI change and on failure; allows a valid review; ask and off modes"


def scn_ui_paths(h):
    sys.path.insert(0, str(SCRIPTS))
    from _common import is_ui_path

    cases = {
        "plugins/perfect-gui/skills/ui-audit-gate/config/levels.json": False,
        "plugins/perfect-gui/skills/ui-audit-gate/scripts/discover.js": False,
        "build/gui/bundle.js": False,
        "src/api/server.ts": False,
        "src/ui/Button.ts": True,
        "src/theme.json": True,
        "app/components/card.js": True,
        "public/logo.svg": True,
        "src/styles/main.css": True,
    }
    wrong = {path: is_ui_path(path) for path, expected in cases.items() if is_ui_path(path) != expected}
    expect(not wrong, f"misclassified paths: {wrong}")
    return "path hints match whole segments only (perfect-gui/ is not ui/)"


SCENARIOS = [
    ("BASE", "Healthy version without false positives", scn_base),
    ("SCN-01", "Offset button", scn_01),
    ("SCN-02", "Text overflowing a button", scn_02),
    ("SCN-03", "Overlay covering an action", scn_03),
    ("SCN-04", "Responsive regression", scn_04),
    ("SCN-05", "Focus trap", scn_05),
    ("SCN-06", "Poorly reported form error", scn_06),
    ("SCN-07", "Translated content too long", scn_07),
    ("SCN-08", "Fix introducing a regression", scn_08),
    ("SCN-09", "Resize losing state", scn_09),
    ("SCN-10", "Virtual keyboard hiding an action", scn_10),
    ("SCN-11", "Web unavailable", scn_11),
    ("SCN-12", "Capture failed", scn_12),
    ("SCN-13", "Fabricated reference and sensitive query", scn_13),
    ("SCN-14", "Non-blocking aesthetic preference", scn_14),
    ("GATE", "Decision rules", scn_gate_rules),
    ("HOOK", "Stop hook", scn_hook),
    ("IMPACT", "Impact analysis", scn_impact),
    ("PSEUDO", "File pseudo-localisation", scn_pseudo),
    ("EXPLORE", "Exploration, generation and review of scenes", scn_explore),
    ("PUBLISH", "Pre-publish gate", scn_publish),
    ("UIPATHS", "UI file detection", scn_ui_paths),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    wanted = set(args.only.split(",")) if args.only else None
    work = Path(tempfile.mkdtemp(prefix="ui-audit-tests-"))
    harness = Harness(work)
    failures = 0
    for sid, title, func in SCENARIOS:
        if wanted and sid not in wanted:
            continue
        started = time.time()
        try:
            detail = func(harness)
            status = "OK"
        except Exception as exc:
            failures += 1
            status = "FAIL"
            detail = str(exc) if isinstance(exc, AssertionError) else traceback.format_exc(limit=3)
        print(f"{status:5} {sid:7} {title} ({time.time() - started:.1f} s)\n      {detail}", flush=True)
    for server in (harness.server, harness.site_server, harness.broken_server):
        server.shutdown()
    if args.keep or failures:
        print(f"\nArtifacts: {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    print(f"\n{'All scenarios pass' if not failures else f'{failures} scenario(s) failed'}.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
