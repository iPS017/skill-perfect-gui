import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
CONFIG_DIR = SKILL_DIR / "config"
CACHE_DIR = Path(os.environ.get("UI_AUDIT_CACHE", Path.home() / ".cache" / "ui-audit-gate"))
VENV_DIR = Path(os.environ.get("UI_AUDIT_VENV", CACHE_DIR / "venv"))
EXIT_CAPABILITY_MISSING = 3
AXE_VERSION = "4.10.2"
AXE_URLS = [
    f"https://cdnjs.cloudflare.com/ajax/libs/axe-core/{AXE_VERSION}/axe.min.js",
    f"https://cdn.jsdelivr.net/npm/axe-core@{AXE_VERSION}/axe.min.js",
]

DESTRUCTIVE_PATTERN = (
    r"(supprim|effac|delete|erase|remove|retirer|vider|purge|pay|payer|paiement|achet|buy|purchase|checkout|commander|order now|place order|"
    r"valider (la |ma )?commande|confirmer (l'achat|le paiement|la commande)|confirm (purchase|payment|order)|envoyer|send|publier|publish|"
    r"d[ée]connex|logout|log out|sign out|se d[ée]connecter|d[ée]sinscri|unsubscribe|r[ée]silier|"
    r"cancel subscription|transf[ée]r|reset|r[ée]initialis|archive|bannir|ban )"
)
SETTING_PATTERN = (
    r"(th[eè]me|mode sombre|mode clair|sombre|clair|dark|light|langue|language|lang|locale|devise|currency|"
    r"taille du texte|text size|font|police|contraste|contrast|densit[ée]|density|affichage|display|vue|view|tri|sort|"
    r"filtr|filter|unit[ée]|pays|country|r[ée]gion|fuseau|timezone)"
)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
LOAD_IMAGES_JS = """
async () => {
  document.querySelectorAll('img[loading=lazy], iframe[loading=lazy]').forEach((node) => { node.loading = 'eager'; });
  const pending = [...document.images].filter((img) => !img.complete);
  await Promise.all(pending.map((img) => new Promise((done) => { img.addEventListener('load', done, { once: true }); img.addEventListener('error', done, { once: true }); setTimeout(done, 3000); })));
  await Promise.all([...document.images].filter((img) => img.complete && img.naturalWidth && img.decode).map((img) => img.decode().catch(() => null)));
  return pending.length;
}
"""

FREEZE_MOTION_CSS = (
    "*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;"
    "animation-iteration-count:1!important;transition-duration:0s!important;"
    "transition-delay:0s!important;caret-color:transparent!important;scroll-behavior:auto!important}"
)


UI_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".styl", ".pcss", ".html", ".htm", ".vue", ".svelte", ".astro",
                 ".jsx", ".tsx", ".mdx", ".twig", ".erb", ".hbs", ".njk", ".liquid", ".razor", ".cshtml",
                 ".swift", ".dart", ".xaml", ".storyboard", ".xib"}
UI_PATH_HINTS = ("components/", "component/", "pages/", "views/", "screens/", "layouts/", "ui/", "styles/", "theme",
                 "tokens", "locales/", "i18n/", "res/layout", "res/values", "public/", "static/", "assets/")
UI_SCRIPT_EXTENSIONS = {".js", ".ts", ".mjs", ".kt", ".json", ".svg", ".woff", ".woff2", ".ttf", ".otf"}
AUDIT_DIRS = (".ui-audit/", "ui-scenes/")


def is_ui_path(path, include=(), exclude=()):
    if path.startswith(AUDIT_DIRS) or any(fnmatch.fnmatch(path, pattern) for pattern in exclude):
        return False
    if any(fnmatch.fnmatch(path, pattern) for pattern in include):
        return True
    suffix = Path(path).suffix.lower()
    if suffix in UI_EXTENSIONS:
        return True
    if suffix not in UI_SCRIPT_EXTENSIONS:
        return False
    lowered = "/" + path.lower()
    return any(f"/{hint}" in lowered for hint in UI_PATH_HINTS)


def ui_fingerprint(root, include=(), exclude=()):
    try:
        listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if listed.returncode != 0:
        return None
    digest = hashlib.sha1()
    for path in sorted(p for p in listed.stdout.splitlines() if is_ui_path(p, include, exclude)):
        target = Path(root) / path
        if target.is_file():
            digest.update(path.encode("utf-8"))
            digest.update(hashlib.sha1(target.read_bytes()).digest())
    return digest.hexdigest()


class BrowserUnavailable(Exception):
    def __init__(self, attempts):
        super().__init__("; ".join(attempts))
        self.attempts = attempts


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(data, code=0):
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(code)


def capability_missing(capability, hint, details=None):
    emit(
        {"status": "capability-missing", "capability": capability, "hint": hint, "details": details or []},
        EXIT_CAPABILITY_MISSING,
    )


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_config(name):
    return read_json(CONFIG_DIR / name)


def venv_python():
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_playwright():
    try:
        import playwright.sync_api  # noqa: F401
        return
    except ImportError:
        pass
    candidate = venv_python()
    already_in_venv = Path(sys.prefix).resolve() == VENV_DIR.resolve()
    if candidate.exists() and not already_in_venv:
        os.execv(str(candidate), [str(candidate), *sys.argv])
    capability_missing(
        "playwright",
        f"Suggest to the user: bash \"{SCRIPTS_DIR / 'setup.sh'}\" (installs Playwright and Pillow into {VENV_DIR})",
    )


def ensure_module(module, capability, hint):
    try:
        __import__(module)
        return
    except ImportError:
        pass
    candidate = venv_python()
    if candidate.exists() and Path(sys.prefix).resolve() != VENV_DIR.resolve():
        os.execv(str(candidate), [str(candidate), *sys.argv])
    capability_missing(capability, hint)


def git_revision(cwd=None):
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, timeout=5)
        if rev.returncode != 0:
            return None
        return rev.stdout.strip() + (" + uncommitted changes" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_viewports(spec):
    catalog = load_config("viewports.json")["viewports"]
    selected = []
    for token in [t.strip() for t in spec.split(",") if t.strip()]:
        size = re.fullmatch(r"(\d+)x(\d+)", token)
        if size:
            width, height = int(size[1]), int(size[2])
            selected.append({
                "id": f"{width}x{height}", "width": width, "height": height, "dpr": 1,
                "pointer": "coarse" if width < 768 else "fine", "priority": "custom",
            })
            continue
        matches = [v for v in catalog if v["id"] == token or v["priority"] == token]
        if not matches:
            raise SystemExit(f"Unknown viewport: {token} (see config/viewports.json)")
        selected.extend(matches)
    unique = {}
    for viewport in selected:
        unique.setdefault(viewport["id"], viewport)
    return list(unique.values())


def add_browser_args(parser, default_viewports="P0"):
    parser.add_argument("--url", required=True)
    parser.add_argument("--viewports", default=default_viewports, help="Comma-separated ids, P0/P1/P2 or WxH")
    parser.add_argument("--theme", default="light", choices=["light", "dark", "no-preference"])
    parser.add_argument("--locale", default="en-US")
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--zoom", type=float, default=1.0, help="Browser zoom: 2 = 200%%")
    parser.add_argument("--reduced-motion", default="no-preference", choices=["reduce", "no-preference"])
    parser.add_argument("--forced-colors", action="store_true")
    parser.add_argument("--engine", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--browser-path", help="Browser executable (only attempt when provided)")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--actions", help="JSON file or inline JSON: list of single-key actions")
    parser.add_argument("--storage-state", help="Playwright session state file (never copied into the run)")
    parser.add_argument("--freeze-time", help="Frozen clock, ISO 8601")
    parser.add_argument("--wait-ms", type=int, default=150)
    parser.add_argument("--keep-motion", action="store_true", help="Do not disable animations and transitions")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--respect-csp", action="store_true", help="Do not bypass the CSP (the skill's injections may then fail)")


def build_config(viewport, args):
    return {
        "viewport_id": viewport["id"],
        "width": viewport["width"],
        "height": viewport["height"],
        "dpr": viewport.get("dpr", 1),
        "pointer": viewport.get("pointer", "fine"),
        "zoom": args.zoom or 1.0,
        "theme": args.theme,
        "locale": args.locale,
        "timezone": args.timezone,
        "reduced_motion": args.reduced_motion,
        "forced_colors": bool(args.forced_colors),
        "engine": args.engine,
    }


def config_id(cfg):
    motion = "rm" if cfg["reduced_motion"] == "reduce" else "m"
    parts = [
        cfg["viewport_id"], f"w{cfg['width']}h{cfg['height']}", f"z{int(round(cfg['zoom'] * 100))}",
        cfg["theme"], cfg["locale"], motion,
    ]
    if cfg["forced_colors"]:
        parts.append("fc")
    parts.append(cfg["engine"])
    return re.sub(r"[^A-Za-z0-9_.-]", "_", "-".join(parts))


def launch_browser(playwright, engine="chromium", browser_path=None, headless=True):
    browser_type = getattr(playwright, engine)
    if browser_path:
        attempts = [{"executable_path": browser_path}]
    else:
        attempts = []
        env_path = os.environ.get("UI_AUDIT_BROWSER")
        if env_path:
            attempts.append({"executable_path": env_path})
        attempts.append({})
        if engine == "chromium":
            attempts += [{"channel": "chrome"}, {"channel": "msedge"}]
    errors = []
    for options in attempts:
        try:
            browser = browser_type.launch(headless=headless, **options)
            label = options.get("executable_path") or options.get("channel") or "playwright-bundled"
            return browser, {"engine": engine, "launch": label, "version": browser.version}
        except Exception as exc:
            first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            errors.append(f"{options or 'bundled'}: {first_line[:240]}")
    raise BrowserUnavailable(errors)


@contextmanager
def browser_session(args):
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            browser, info = launch_browser(playwright, args.engine, args.browser_path, not args.headed)
        except BrowserUnavailable as exc:
            capability_missing(
                "browser",
                "No launchable browser. Try --engine, --browser-path, or `playwright install chromium` via setup.sh --with-browsers.",
                exc.attempts,
            )
        try:
            yield browser, info
        finally:
            browser.close()


def context_options(cfg, args):
    zoom = cfg["zoom"] or 1.0
    options = {
        "viewport": {"width": max(1, round(cfg["width"] / zoom)), "height": max(1, round(cfg["height"] / zoom))},
        "device_scale_factor": cfg["dpr"] * zoom,
        "color_scheme": cfg["theme"],
        "reduced_motion": cfg["reduced_motion"],
        "forced_colors": "active" if cfg["forced_colors"] else "none",
        "locale": cfg["locale"],
        "timezone_id": cfg["timezone"],
        "has_touch": cfg["pointer"] == "coarse",
        "bypass_csp": not getattr(args, "respect_csp", False),
    }
    if cfg["pointer"] == "coarse" and cfg["engine"] == "chromium":
        options["is_mobile"] = True
    if getattr(args, "storage_state", None):
        options["storage_state"] = args.storage_state
    return options


def open_page(browser, cfg, args):
    context = browser.new_context(**context_options(cfg, args))
    context.set_default_timeout(args.timeout_ms)
    page = context.new_page()
    logs = []
    def ignored(url):
        return url.split("?")[0].endswith("/favicon.ico")

    def on_console(message):
        location = (message.location or {}).get("url", "")
        if message.type in ("error", "warning") and not ignored(location):
            logs.append({"type": message.type, "text": message.text[:500], "source": location[:300]})

    page.on("console", on_console)
    page.on("pageerror", lambda e: logs.append({"type": "pageerror", "text": str(e)[:500]}))
    page.on("requestfailed", lambda r: None if ignored(r.url) else logs.append({"type": "requestfailed", "text": f"{r.method} {r.url[:300]}"}))
    page.on("response", lambda r: logs.append({"type": f"http-{r.status}", "text": r.url[:300]}) if r.status >= 400 and not ignored(r.url) else None)
    clock = "not frozen"
    if getattr(args, "freeze_time", None):
        try:
            page.clock.set_fixed_time(datetime.fromisoformat(args.freeze_time.replace("Z", "+00:00")))
            clock = args.freeze_time
        except Exception as exc:
            clock = f"not frozen (API unavailable: {type(exc).__name__})"
    return context, page, logs, clock


def stabilize(page, args):
    try:
        page.wait_for_load_state("networkidle", timeout=min(args.timeout_ms, 10000))
    except Exception:
        pass
    try:
        page.evaluate("() => document.fonts ? document.fonts.ready.then(() => true) : true")
    except Exception:
        pass
    try:
        page.evaluate(LOAD_IMAGES_JS)
    except Exception:
        pass
    if not getattr(args, "keep_motion", False):
        try:
            page.add_style_tag(content=FREEZE_MOTION_CSS)
        except Exception:
            page.evaluate(
                "(css) => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); }",
                FREEZE_MOTION_CSS,
            )
    page.wait_for_timeout(args.wait_ms)


def load_actions(value):
    if not value:
        return []
    path = Path(value)
    text = path.read_text(encoding="utf-8") if path.exists() else value
    actions = json.loads(text)
    if not isinstance(actions, list):
        raise SystemExit("--actions must be a JSON list of single-key objects")
    return actions


def run_actions(page, actions, base_url, log):
    for step in actions:
        if not isinstance(step, dict) or len(step) != 1:
            raise SystemExit(f"Invalid action: {step!r}")
        kind, value = next(iter(step.items()))
        if kind == "goto":
            page.goto(urljoin(base_url, value), wait_until="load")
        elif kind in ("click", "click_effect"):
            page.click(value)
        elif kind in ("snapshot", "note"):
            pass
        elif kind == "click_optional":
            target = page.locator(value).first
            if target.count() and target.is_visible():
                target.click(timeout=3000)
        elif kind == "fill":
            page.fill(value[0], value[1])
        elif kind == "type":
            page.locator(value[0]).press_sequentially(value[1])
        elif kind == "press":
            page.keyboard.press(value)
        elif kind == "hover":
            page.hover(value)
        elif kind == "focus":
            page.focus(value)
        elif kind == "check":
            page.check(value)
        elif kind == "select":
            page.select_option(value[0], value[1])
        elif kind == "wait":
            page.wait_for_timeout(int(value))
        elif kind == "wait_for":
            page.wait_for_selector(value)
        elif kind == "scroll":
            page.evaluate("([x, y]) => window.scrollTo(x, y)", value)
        elif kind == "eval":
            page.evaluate(value)
        elif kind == "set_viewport":
            page.set_viewport_size({"width": int(value[0]), "height": int(value[1])})
        else:
            raise SystemExit(f"Unknown action: {kind}")
        log.append(step)


def install_mutation_guard(target, allow, journal):
    def handle(route):
        request = route.request
        if allow or request.method in SAFE_METHODS:
            route.continue_()
            return
        journal.append({"method": request.method, "url": request.url[:300]})
        route.abort()

    target.route("**/*", handle)


def prepare_page(browser, cfg, args):
    context, page, logs, clock = open_page(browser, cfg, args)
    steps = [{"goto": args.url}]
    page.goto(args.url, wait_until="load")
    run_actions(page, load_actions(args.actions), args.url, steps)
    stabilize(page, args)
    return context, page, logs, clock, steps


def manifest(cfg, browser_info, args, clock, steps):
    zoom = cfg["zoom"] or 1.0
    return {
        "config_id": config_id(cfg),
        "fidelity": "emulation",
        "engine": f"{browser_info['engine']} {browser_info['version']} ({browser_info['launch']})",
        "viewport_css": [round(cfg["width"] / zoom), round(cfg["height"] / zoom)],
        "window_css": [cfg["width"], cfg["height"]],
        "dpr": cfg["dpr"],
        "zoom": zoom,
        "theme": cfg["theme"],
        "locale": cfg["locale"],
        "timezone": cfg["timezone"],
        "preferences": {"reduced_motion": cfg["reduced_motion"], "forced_colors": cfg["forced_colors"]},
        "pointer": cfg["pointer"],
        "animations_disabled": not getattr(args, "keep_motion", False),
        "csp_bypassed": not getattr(args, "respect_csp", False),
        "clock": clock,
        "url": args.url,
        "navigation_steps": steps,
        "revision": git_revision(),
        "created_at": now_iso(),
    }


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "page"


def annotate(screenshot_path, boxes, out_path):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    image = Image.open(screenshot_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    palette = {"critical": (200, 0, 40), "major": (230, 90, 0), "info": (0, 90, 200)}
    for number, box in enumerate(boxes, 1):
        color = palette.get(box.get("level"), (200, 0, 40))
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        draw.rectangle([x, y, x + max(w, 1), y + max(h, 1)], outline=color, width=3)
        label_y = max(0, y - 16)
        draw.rectangle([x, label_y, x + 22, label_y + 15], fill=color)
        draw.text((x + 4, label_y + 2), str(number), fill=(255, 255, 255))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return str(out_path)


def load_axe(allow_download=True):
    env_path = os.environ.get("UI_AUDIT_AXE")
    if env_path and Path(env_path).exists():
        return Path(env_path).read_text(encoding="utf-8"), env_path
    cached = CACHE_DIR / f"axe-{AXE_VERSION}.min.js"
    if cached.exists():
        return cached.read_text(encoding="utf-8"), str(cached)
    if not allow_download:
        return None, "axe-core missing from cache and download disabled"
    import urllib.request

    errors = []
    for url in AXE_URLS:
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                source = response.read().decode("utf-8")
            if "axe" not in source[:2000]:
                raise ValueError("unexpected content")
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(source, encoding="utf-8")
            return source, url
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}")
    return None, "could not download axe-core: " + "; ".join(errors)


def base_parser(description):
    return argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
