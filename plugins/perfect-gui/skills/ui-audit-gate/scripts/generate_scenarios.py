#!/usr/bin/env python3
"""Generate the scene suite from site-map.json: everything a user can do,
one scene per action, option, parameter or setting, plus the environment variants.

Identifiers (S-0001...) stay stable between two generations: an existing scene keeps its
number, new ones are added, and those that disappeared are listed as removed.

Examples:
  python3 generate_scenarios.py --site-map ui-scenes/site-map.json --out ui-scenes/scenes.json
  python3 generate_scenarios.py --site-map ui-scenes/site-map.json --out ui-scenes/scenes.json --export-playwright tests/ui-scenes.spec.ts
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from _common import load_config, now_iso, read_json, write_json

EDGE = load_config("fixtures/edge-text.json")
CATEGORY_ORDER = ["page", "control", "toggle", "tab", "menu", "select", "checkbox", "radio", "range",
                  "form", "url-param", "setting", "environment"]
NAME_HINTS = [
    (r"(pr[ée]nom|first)", "Alex"), (r"(nom|name|last)", "Alex Martin"), (r"(ville|city)", "London"),
    (r"(code ?postal|zip|postcode)", "SW1A 1AA"), (r"(adresse|address|rue|street)", "12 High Street"),
    (r"(soci[ée]t[ée]|company|entreprise)", "Example Ltd"), (r"(pays|country)", "United Kingdom"),
    (r"(message|comment|description|bio)", "UI audit test message."), (r"(search|recherche|q$|query)", "test"),
]


def path_of(url):
    parsed = urlparse(url)
    return (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")


def valid_value(field):
    kind = field["type"]
    label = f"{field.get('name') or ''} {field.get('label') or ''}".lower()
    if kind == "email":
        return "test.ui@example.com"
    if kind == "tel":
        return "+442071234567"
    if kind == "url":
        return "https://example.com"
    if kind == "password":
        return "Uiag-Test-2026!"
    if kind == "number":
        low = float(field["min"]) if field.get("min") not in (None, "") else 1
        return str(int(low) if low.is_integer() else low)
    if kind == "date":
        return "2026-01-15"
    if kind == "time":
        return "10:30"
    if kind == "datetime-local":
        return "2026-01-15T10:30"
    if kind == "month":
        return "2026-01"
    if kind == "color":
        return "#336699"
    for pattern, value in NAME_HINTS:
        if re.search(pattern, label):
            return value
    return "Test text"


def invalid_value(field):
    kind = field["type"]
    if kind == "email":
        return "not-an-email"
    if kind == "url":
        return "not a url"
    if kind == "tel":
        return "abc"
    if kind == "number":
        if field.get("max") not in (None, ""):
            return str(float(field["max"]) + 1).rstrip("0").rstrip(".")
        return "-1"
    if field.get("pattern"):
        return "!!!"
    if field.get("minlength"):
        return "a"
    return None


def long_value(field):
    if field["type"] == "email":
        return EDGE["long_email"]
    if field["type"] in ("number", "date", "time", "datetime-local", "month", "color", "range"):
        return None
    if field.get("maxlength"):
        return ("Donaudampfschiff" * 20)[: field["maxlength"] + 5]
    return EDGE["long_de"] + " " + EDGE["no_space_word"]


def fill_actions(fields, mode):
    actions = []
    for field in fields:
        if not field.get("visible", True):
            continue
        if field["tag"] == "select":
            options = [o for o in field.get("options") or [] if o["value"] != ""]
            if mode != "empty" and options:
                actions.append({"select": [field["selector"], options[0]["value"]]})
            continue
        if field["type"] in ("checkbox", "radio"):
            if mode != "empty" and field.get("required"):
                actions.append({"check": field["selector"]})
            continue
        if field["type"] in ("file", "range", "hidden"):
            continue
        if mode == "empty":
            actions.append({"fill": [field["selector"], ""]})
            continue
        value = valid_value(field)
        if mode == "invalid":
            value = invalid_value(field) or value
        if mode == "long":
            value = long_value(field) or value
        actions.append({"fill": [field["selector"], value]})
    return actions


class SceneBook:
    def __init__(self, previous):
        self.previous = {s["key"]: s["id"] for s in previous.get("scenes", [])}
        self.next_number = max([int(s["id"].split("-")[1]) for s in previous.get("scenes", [])] or [0]) + 1
        self.scenes = []
        self.skipped = []
        self.keys = set()

    def add(self, category, title, page, actions, risk="safe", environment=None, checks=None, key_extra=""):
        key_source = json.dumps([category, page, key_extra or actions, environment or {}], ensure_ascii=False, sort_keys=True)
        key = hashlib.sha1(key_source.encode("utf-8")).hexdigest()[:16]
        if key in self.keys:
            return
        self.keys.add(key)
        scene_id = self.previous.get(key)
        if not scene_id:
            scene_id = f"S-{self.next_number:04d}"
            self.next_number += 1
        self.scenes.append({
            "id": scene_id, "key": key, "category": category, "title": title, "page": page,
            "risk": risk, "environment": environment or {}, "actions": actions, "checks": checks or ["render"],
        })

    def skip(self, what, reason):
        self.skipped.append({"element": what, "reason": reason})


def build(site_map, args):
    previous = read_json(args.out, {}) or {}
    book = SceneBook(previous)
    pages = [p for p in site_map["pages"] if not p.get("error") and not p.get("access_blocked")]
    for blocked_page in site_map.get("blocked_pages", []):
        book.skip(blocked_page["url"], f"page refused during exploration: {blocked_page['reason']}")
    explored_paths = set()
    for found in pages:
        page = path_of(found["url"])
        goto = {"goto": page}
        book.add("page", f"Load {page}", page, [goto, {"snapshot": "load"}], checks=["render", "console"])
        bare_path = urlparse(found["url"]).path
        if bare_path in explored_paths:
            continue
        explored_paths.add(bare_path)

        for control in found.get("controls", []):
            name = control["name"] or control["selector"]
            prerequisites = control.get("prerequisites", [])
            label = f"\"{name[:50]}\" ({control['kind']}) on {page}"
            if control["risk"] in ("destructive", "download"):
                book.skip(label, f"{control['risk']} risk: test in a test environment with --allow-mutations")
                continue
            if control["kind"] in ("field", "file"):
                continue
            if not control.get("visible", True) and not prerequisites:
                book.skip(label, "hidden element that no explored interaction reveals (hover menu, special state)")
                continue
            base = [goto, *prerequisites]
            if control["kind"] == "toggle":
                popup = control.get("haspopup") not in (None, "", "false")
                closing = [{"press": "Escape"}, {"snapshot": "closed-by-escape"}] if popup else [{"click_optional": control["selector"]}, {"snapshot": "closed"}]
                book.add("toggle", f"Open then close {label}", page,
                         base + [{"click_effect": control["selector"]}, {"snapshot": "open"}, *closing],
                         checks=["render", "effect", "closing", "scroll"])
            elif control["kind"] == "tab":
                book.add("tab", f"Activate tab {label}", page, base + [{"click_effect": control["selector"]}, {"snapshot": "tab-active"}], checks=["render", "effect"])
            elif control["kind"] == "menu-item":
                book.add("menu", f"Choose {label}", page, base + [{"click_effect": control["selector"]}, {"snapshot": "after-choice"}], checks=["render", "effect"])
            elif control["kind"] == "select" and control.get("field"):
                options = [o for o in control["field"].get("options") or [] if o["value"] != ""]
                chosen = options if len(options) <= args.max_options else options[:2] + [options[len(options) // 2]] + options[-1:]
                if len(options) > args.max_options:
                    book.skip(label, f"{len(options)} options: sample of {len(chosen)} (first, middle, last)")
                for option in chosen:
                    category = "setting" if control.get("setting") else "select"
                    book.add(category, f"Option \"{option['label'][:40]}\" of {label}", page,
                             base + [{"select": [control["selector"], option["value"]]}, {"wait": 300}, {"snapshot": f"option-{option['value'][:20]}"}],
                             checks=["render", "consistency"], key_extra=f"{control['selector']}={option['value']}")
            elif control["kind"] in ("checkbox", "switch"):
                category = "setting" if control.get("setting") else "checkbox"
                book.add(category, f"Check then uncheck {label}", page,
                         base + [{"click_effect": control["selector"]}, {"snapshot": "on"}, {"click_optional": control["selector"]}, {"snapshot": "off"}],
                         checks=["render", "effect", "consistency"])
            elif control["kind"] == "radio":
                category = "setting" if control.get("setting") else "radio"
                book.add(category, f"Choose {label}", page, base + [{"click": control["selector"]}, {"wait": 300}, {"snapshot": "chosen"}], checks=["render", "consistency"])
            elif control["kind"] == "range":
                field = control.get("field") or {}
                for bound in ("min", "max"):
                    if field.get(bound) not in (None, ""):
                        book.add("range", f"Range {label} at {bound}", page,
                                 base + [{"fill": [control["selector"], field[bound]]}, {"snapshot": f"range-{bound}"}], checks=["render"], key_extra=f"{control['selector']}:{bound}")
            elif control["kind"] in ("action", "anchor", "option", "reset"):
                category = "setting" if control.get("setting") else "control"
                book.add(category, f"Activate {label}", page, base + [{"click_effect": control["selector"]}, {"snapshot": "after-action"}], checks=["render", "effect", "consistency"])

        for form in found.get("forms", []):
            if not form.get("fields") and not form.get("submit"):
                continue
            label = f"form \"{(form['name'] or form['selector'])[:40]}\" on {page}"
            if not form.get("visible", True) and not form.get("prerequisites"):
                book.skip(label, "hidden form that no explored interaction reveals")
                continue
            base = [goto, *form.get("prerequisites", [])]
            risk = "mutation" if form["risk"] in ("mutation", "destructive") else "safe"
            if form["risk"] == "destructive" and not args.allow_destructive:
                book.skip(label, "destructive form: input scenes only, no submission")
            submit = [{"click": form["submit"]}] if form.get("submit") and (form["risk"] != "destructive" or args.allow_destructive) else [{"press": "Enter"}] if form["risk"] != "destructive" else []
            for mode, title in (("empty", "empty submit"), ("invalid", "invalid values"), ("valid", "valid values"), ("long", "very long content")):
                actions = base + fill_actions(form["fields"], mode)
                if mode == "long":
                    actions += [{"snapshot": "long-input"}]
                actions += submit + [{"wait": 400}, {"snapshot": f"after-submit-{mode}"}]
                book.add("form", f"{label}: {title}", page, actions, risk=risk, checks=["render", "form-errors", "effect"], key_extra=f"{form['selector']}:{mode}")

    first_page = path_of(pages[0]["url"]) if pages else "/"
    sample_pages = [path_of(p["url"]) for p in pages[: args.env_pages]]
    for name, values in site_map.get("url_params", {}).items():
        target = next((p for p in pages if name in dict(parse_qsl(urlparse(p["url"]).query))), pages[0] if pages else None)
        base_path = urlparse(target["url"]).path if target else "/"
        for value in values[: args.max_options] + ["unexpected-value-<>&", ""]:
            query = urlencode({name: value})
            book.add("url-param", f"URL parameter {name}={value[:30]!r}", f"{base_path}?{query}",
                     [{"goto": f"{base_path}?{query}"}, {"snapshot": "param"}], checks=["render", "console"], key_extra=f"{name}={value}")

    environments = [({"theme": "dark"}, "system dark theme"), ({"reduced_motion": "reduce"}, "reduced motion"), ({"zoom": 2}, "200% zoom")]
    environments += [({"locale": lang}, f"language {lang}") for lang in site_map.get("languages", [])[:6]]
    for page in sample_pages:
        for environment, title in environments:
            book.add("environment", f"{page} with {title}", page, [{"goto": page}, {"snapshot": "environment"}], environment=environment, checks=["render", "consistency"])
    for found in pages:
        for alternate in found.get("alternates", [])[:6]:
            page = path_of(alternate["href"])
            book.add("environment", f"{alternate['hreflang']} version of {path_of(found['url'])}", page, [{"goto": page}, {"snapshot": "language"}],
                     checks=["render", "translation"], key_extra=f"hreflang:{alternate['href']}")

    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    book.scenes.sort(key=lambda s: (order.get(s["category"], 99), s["id"]))
    if args.max_scenes and len(book.scenes) > args.max_scenes:
        for scene in book.scenes[args.max_scenes:]:
            book.skip(f"{scene['id']} {scene['title']}", f"--max-scenes budget {args.max_scenes} reached")
        book.scenes = book.scenes[: args.max_scenes]
    removed = [{"id": sid, "key": key} for key, sid in book.previous.items() if key not in book.keys]
    book.scenes.sort(key=lambda s: s["id"])
    return {
        "version": 1,
        "generated_at": now_iso(),
        "source": site_map.get("start"),
        "origin": site_map.get("origin"),
        "breakpoints": site_map.get("breakpoints", []),
        "languages": site_map.get("languages", []),
        "dark_scheme_css": site_map.get("dark_scheme_css", False),
        "scenes": book.scenes,
        "not_covered": book.skipped + [
            {"element": "combinations of several settings at once", "reason": "one option at a time (one-factor-at-a-time); combine critical settings by hand if needed"},
            {"element": "file uploads, drag and drop, multi-finger gestures", "reason": "not generated automatically"},
            {"element": "external links", "reason": f"{len(site_map.get('external_links', []))} off-site links not followed"},
        ],
        "removed": removed,
        "summary": {
            "scenes": len(book.scenes),
            "by_category": {c: sum(1 for s in book.scenes if s["category"] == c) for c in CATEGORY_ORDER if any(s["category"] == c for s in book.scenes)},
            "not_covered": len(book.skipped),
            "new": sum(1 for s in book.scenes if s["key"] not in book.previous),
            "removed": len(removed),
        },
    }


def to_playwright(suite, allow_mutations):
    lines = [
        "import { test, expect, type Page } from '@playwright/test';",
        "",
        f"const BASE = process.env.UI_BASE_URL ?? {json.dumps(suite.get('origin') or 'http://localhost:3000')};",
        "",
        "async function checkScene(page: Page, name: string) {",
        "  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);",
        "  expect(overflow, 'unintended horizontal scroll').toBeLessThanOrEqual(1);",
        "  await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });",
        "}",
        "",
        "test.describe('UI scenes generated by ui-audit-gate', () => {",
        "  test.beforeEach(async ({ page }) => {",
    ]
    if not allow_mutations:
        lines.append("    await page.route('**/*', (route) => (['GET', 'HEAD', 'OPTIONS'].includes(route.request().method()) ? route.continue() : route.abort()));")
    lines += ["  });", ""]
    for scene in suite["scenes"]:
        environment = scene.get("environment") or {}
        options = []
        if environment.get("theme"):
            options.append(f"colorScheme: {json.dumps(environment['theme'])}")
        if environment.get("reduced_motion"):
            options.append(f"reducedMotion: {json.dumps(environment['reduced_motion'])}")
        if environment.get("locale"):
            options.append(f"locale: {json.dumps(environment['locale'])}")
        title = json.dumps(f"{scene['id']} {scene['title']}"[:180], ensure_ascii=False)
        if options:
            lines.append(f"  test.describe(() => {{ test.use({{ {', '.join(options)} }});")
        lines.append(f"  test({title}, async ({{ page }}) => {{")
        lines.append("    const errors: string[] = [];")
        lines.append("    page.on('pageerror', (error) => errors.push(String(error)));")
        shot = 0
        for action in scene["actions"]:
            (kind, value), = action.items()
            if kind == "goto":
                lines.append(f"    await page.goto(BASE + {json.dumps(value, ensure_ascii=False)});")
            elif kind in ("click", "click_effect"):
                lines.append(f"    await page.locator({json.dumps(value, ensure_ascii=False)}).first().click();")
            elif kind == "click_optional":
                lines.append(f"    if (await page.locator({json.dumps(value, ensure_ascii=False)}).first().isVisible()) await page.locator({json.dumps(value, ensure_ascii=False)}).first().click();")
            elif kind == "fill":
                lines.append(f"    await page.locator({json.dumps(value[0], ensure_ascii=False)}).first().fill({json.dumps(str(value[1]), ensure_ascii=False)});")
            elif kind == "select":
                lines.append(f"    await page.locator({json.dumps(value[0], ensure_ascii=False)}).first().selectOption({json.dumps(value[1], ensure_ascii=False)});")
            elif kind == "check":
                lines.append(f"    await page.locator({json.dumps(value, ensure_ascii=False)}).first().check();")
            elif kind == "press":
                lines.append(f"    await page.keyboard.press({json.dumps(value, ensure_ascii=False)});")
            elif kind == "hover":
                lines.append(f"    await page.locator({json.dumps(value, ensure_ascii=False)}).first().hover();")
            elif kind == "wait":
                lines.append(f"    await page.waitForTimeout({int(value)});")
            elif kind == "snapshot":
                shot += 1
                shot_name = json.dumps(scene["id"] + "-" + str(shot))
                lines.append(f"    await checkScene(page, {shot_name});")
        lines.append("    expect(errors).toEqual([]);")
        lines.append("  });")
        if options:
            lines.append("  });")
        lines.append("")
    lines.append("});")
    return "\n".join(lines) + "\n"


def ignore_run_artifacts(suite_dir):
    import subprocess

    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=suite_dir, capture_output=True, text=True)
    if top.returncode != 0:
        return "not a git repository"
    root = Path(top.stdout.strip())
    try:
        relative = suite_dir.resolve().relative_to(root).as_posix()
    except ValueError:
        return "suite outside the repository"
    wanted = [f"{relative}/runs/", f"{relative}/last-review.json"]
    gitignore = root / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    missing = [w for w in wanted if w not in lines]
    if missing:
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(("\n" if lines and lines[-1].strip() else "") + "\n".join(missing) + "\n")
        return "added: " + ", ".join(missing)
    return "already ignored"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site-map", required=True)
    parser.add_argument("--out", required=True, help="scenes.json file (updated while keeping identifiers)")
    parser.add_argument("--max-options", type=int, default=12, help="Beyond this, sample the options of a select")
    parser.add_argument("--env-pages", type=int, default=5, help="Pages replayed in each environment variant")
    parser.add_argument("--max-scenes", type=int, default=0, help="Cap (0 = none); the surplus is listed as not covered")
    parser.add_argument("--allow-destructive", action="store_true", help="Also generate destructive submissions (test environment only)")
    parser.add_argument("--export-playwright", help="Also write a @playwright/test test file (.spec.ts)")
    args = parser.parse_args()

    site_map = read_json(args.site_map)
    suite = build(site_map, args)
    write_json(args.out, suite)
    ignore_note = ignore_run_artifacts(Path(args.out).parent)
    result = {"tool": "generate_scenarios", "out": args.out, **suite["summary"], "gitignore": ignore_note}
    if args.export_playwright:
        target = Path(args.export_playwright)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_playwright(suite, False), encoding="utf-8")
        result["playwright"] = str(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
