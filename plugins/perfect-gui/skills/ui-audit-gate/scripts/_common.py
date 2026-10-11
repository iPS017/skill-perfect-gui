import argparse
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

FREEZE_MOTION_CSS = (
    "*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;"
    "animation-iteration-count:1!important;transition-duration:0s!important;"
    "transition-delay:0s!important;caret-color:transparent!important;scroll-behavior:auto!important}"
)


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
        f"Proposer à l'utilisateur : bash \"{SCRIPTS_DIR / 'setup.sh'}\" (installe Playwright et Pillow dans {VENV_DIR})",
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
        return rev.stdout.strip() + (" + modifications non commitées" if dirty.stdout.strip() else "")
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
            raise SystemExit(f"Viewport inconnu : {token} (voir config/viewports.json)")
        selected.extend(matches)
    unique = {}
    for viewport in selected:
        unique.setdefault(viewport["id"], viewport)
    return list(unique.values())


def add_browser_args(parser, default_viewports="P0"):
    parser.add_argument("--url", required=True)
    parser.add_argument("--viewports", default=default_viewports, help="Identifiants, P0/P1/P2 ou LxH, séparés par des virgules")
    parser.add_argument("--theme", default="light", choices=["light", "dark", "no-preference"])
    parser.add_argument("--locale", default="fr-FR")
    parser.add_argument("--timezone", default="Europe/Paris")
    parser.add_argument("--zoom", type=float, default=1.0, help="Zoom navigateur : 2 = 200 %%")
    parser.add_argument("--reduced-motion", default="no-preference", choices=["reduce", "no-preference"])
    parser.add_argument("--forced-colors", action="store_true")
    parser.add_argument("--engine", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--browser-path", help="Exécutable du navigateur (seule tentative si fourni)")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--actions", help="Fichier JSON ou JSON en ligne : liste d'actions à une clé")
    parser.add_argument("--storage-state", help="Fichier d'état de session Playwright (jamais copié dans le run)")
    parser.add_argument("--freeze-time", help="Horloge figée, ISO 8601")
    parser.add_argument("--wait-ms", type=int, default=150)
    parser.add_argument("--keep-motion", action="store_true", help="Ne pas neutraliser animations et transitions")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--respect-csp", action="store_true", help="Ne pas contourner la CSP (les injections du skill peuvent alors échouer)")


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
                "Aucun navigateur lançable. Essayer --engine, --browser-path, ou `playwright install chromium` via setup.sh --with-browsers.",
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
    clock = "non figée"
    if getattr(args, "freeze_time", None):
        try:
            page.clock.set_fixed_time(datetime.fromisoformat(args.freeze_time.replace("Z", "+00:00")))
            clock = args.freeze_time
        except Exception as exc:
            clock = f"non figée (API indisponible : {type(exc).__name__})"
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
        raise SystemExit("--actions doit être une liste JSON d'objets à une clé")
    return actions


def run_actions(page, actions, base_url, log):
    for step in actions:
        if not isinstance(step, dict) or len(step) != 1:
            raise SystemExit(f"Action invalide : {step!r}")
        kind, value = next(iter(step.items()))
        if kind == "goto":
            page.goto(urljoin(base_url, value), wait_until="load")
        elif kind == "click":
            page.click(value)
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
            raise SystemExit(f"Action inconnue : {kind}")
        log.append(step)


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
        "fidelite": "emulation",
        "moteur": f"{browser_info['engine']} {browser_info['version']} ({browser_info['launch']})",
        "viewport_css": [round(cfg["width"] / zoom), round(cfg["height"] / zoom)],
        "fenetre_css": [cfg["width"], cfg["height"]],
        "dpr": cfg["dpr"],
        "zoom": zoom,
        "theme": cfg["theme"],
        "langue": cfg["locale"],
        "fuseau": cfg["timezone"],
        "preferences": {"reduced_motion": cfg["reduced_motion"], "forced_colors": cfg["forced_colors"]},
        "pointeur": cfg["pointer"],
        "animations_neutralisees": not getattr(args, "keep_motion", False),
        "csp_contournee": not getattr(args, "respect_csp", False),
        "horloge": clock,
        "url": args.url,
        "etapes_navigation": steps,
        "revision": git_revision(),
        "cree_le": now_iso(),
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
    palette = {"critique": (200, 0, 40), "majeure": (230, 90, 0), "info": (0, 90, 200)}
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
        return None, "axe-core absent du cache et téléchargement désactivé"
    import urllib.request

    errors = []
    for url in AXE_URLS:
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                source = response.read().decode("utf-8")
            if "axe" not in source[:2000]:
                raise ValueError("contenu inattendu")
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(source, encoding="utf-8")
            return source, url
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}")
    return None, "téléchargement d'axe-core impossible : " + "; ".join(errors)


def base_parser(description):
    return argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
