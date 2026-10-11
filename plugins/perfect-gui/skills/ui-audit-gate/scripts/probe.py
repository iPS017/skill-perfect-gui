#!/usr/bin/env python3
"""Probes the capabilities actually available and writes capabilities.json.

Web research depends on the host agent's tools (WebSearch, WebFetch): this script cannot probe it.

Example:
  python3 probe.py --out .ui-audit/RUN-x/capabilities.json
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from _common import AXE_VERSION, BROWSER_CACHE, CACHE_DIR, VENV_DIR, app_window_viewports, emit, now_iso, project_config, read_json, system_browser_candidates, venv_python, write_json


def which(*names):
    return {name: shutil.which(name) for name in names if shutil.which(name)}


def probe_playwright(engines):
    try:
        from playwright.sync_api import sync_playwright
        import playwright
    except ImportError:
        return {"available": False, "reason": "playwright module missing", "venv": str(VENV_DIR), "venv_exists": venv_python().exists()}
    from _common import BrowserUnavailable, launch_browser

    version = getattr(playwright, "__version__", "unknown")
    results = {}
    with sync_playwright() as p:
        for engine in engines:
            try:
                browser, info = launch_browser(p, engine, os.environ.get("UI_AUDIT_BROWSER") if engine == "chromium" else None)
                browser.close()
                results[engine] = {"available": True, **info}
            except BrowserUnavailable as exc:
                results[engine] = {"available": False, "attempts": exc.attempts}
    return {"available": any(r["available"] for r in results.values()), "version": version, "engines": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out")
    parser.add_argument("--engines", default="chromium,firefox,webkit")
    parser.add_argument("--no-reexec", action="store_true", help="Do not switch into the venv")
    args = parser.parse_args()

    if not args.no_reexec:
        try:
            import playwright  # noqa: F401
        except ImportError:
            candidate = venv_python()
            if candidate.exists() and Path(sys.prefix).resolve() != VENV_DIR.resolve():
                os.execv(str(candidate), [str(candidate), *sys.argv])

    try:
        import PIL
        pillow = {"available": True, "version": PIL.__version__}
    except ImportError:
        pillow = {"available": False, "reason": "Pillow missing: no visual diff and no annotated screenshot"}

    axe_cache = CACHE_DIR / f"axe-{AXE_VERSION}.min.js"
    git = which("git")
    git_repo = False
    if git:
        git_repo = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True).returncode == 0

    capabilities = {
        "created_at": now_iso(),
        "system": {"os": platform.system(), "version": platform.release(), "python": sys.version.split()[0], "interpreter": sys.executable},
        "CAP-BROWSER": probe_playwright([e.strip() for e in args.engines.split(",") if e.strip()]),
        "CAP-DIFF": pillow,
        "CAP-A11Y-RULES": {
            "available": axe_cache.exists() or bool(os.environ.get("UI_AUDIT_AXE")),
            "cache": str(axe_cache),
            "note": "Downloaded automatically on the first inspect_page.py run if the network allows it (--no-axe to avoid it).",
        },
        "CAP-WEB": {"available": "to-be-determined", "note": "Depends on the host agent's research tools. Record a failure with research_log.py unavailable."},
        "CAP-FS": {"available": True},
        "CAP-VCS": {"git": bool(git), "repository": git_repo},
        "CAP-NATIVE": {
            "ios": which("xcrun", "xcodebuild"),
            "android": which("adb", "emulator"),
            "desktop_linux_atspi": which("accerciser"),
            "note": "Without native tooling, auditing a native application is visual only.",
        },
        "CAP-SR": {
            "detected_readers": which("orca", "nvda", "narrator"),
            "note": "A detected screen reader is not driven automatically: ACC-11 remains a human check.",
        },
        "CAP-DEVICE": {"adb_devices": None},
        "CAP-APP-WINDOW": dict(zip(("viewports", "source"), app_window_viewports())),
        "browser_memory": {"cached": read_json(BROWSER_CACHE, {}) or {}, "system_browsers": system_browser_candidates(),
                           "note": "The first browser that launches is remembered in the cache; no --browser-path needed afterwards."},
        "project_config": project_config(),
    }
    if which("adb"):
        devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[1:]
        capabilities["CAP-DEVICE"]["adb_devices"] = [d for d in devices if d.strip()]

    browser_ok = capabilities["CAP-BROWSER"]["available"]
    capabilities["recommended_mode"] = "full" if browser_ok else "no_execution"
    capabilities["actions"] = [] if browser_ok else [f"Suggest: bash \"{Path(__file__).parent / 'setup.sh'}\" (approval required)"]
    if args.out:
        write_json(args.out, capabilities)
    emit(capabilities)


if __name__ == "__main__":
    main()
