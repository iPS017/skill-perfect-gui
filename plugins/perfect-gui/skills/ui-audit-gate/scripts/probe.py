#!/usr/bin/env python3
"""Sonde les capacités réellement disponibles et écrit capabilities.json.

La recherche Web dépend des outils de l'agent hôte (WebSearch, WebFetch) : ce script ne peut pas la sonder.

Exemple :
  python3 probe.py --out .ui-audit/RUN-x/capabilities.json
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from _common import AXE_VERSION, CACHE_DIR, VENV_DIR, emit, now_iso, venv_python, write_json


def which(*names):
    return {name: shutil.which(name) for name in names if shutil.which(name)}


def probe_playwright(engines):
    try:
        from playwright.sync_api import sync_playwright
        import playwright
    except ImportError:
        return {"disponible": False, "raison": "module playwright absent", "venv": str(VENV_DIR), "venv_existe": venv_python().exists()}
    from _common import BrowserUnavailable, launch_browser

    version = getattr(playwright, "__version__", "inconnue")
    results = {}
    with sync_playwright() as p:
        for engine in engines:
            try:
                browser, info = launch_browser(p, engine, os.environ.get("UI_AUDIT_BROWSER") if engine == "chromium" else None)
                browser.close()
                results[engine] = {"disponible": True, **info}
            except BrowserUnavailable as exc:
                results[engine] = {"disponible": False, "tentatives": exc.attempts}
    return {"disponible": any(r["disponible"] for r in results.values()), "version": version, "moteurs": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out")
    parser.add_argument("--engines", default="chromium,firefox,webkit")
    parser.add_argument("--no-reexec", action="store_true", help="Ne pas basculer dans le venv")
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
        pillow = {"disponible": True, "version": PIL.__version__}
    except ImportError:
        pillow = {"disponible": False, "raison": "Pillow absent : pas de diff visuel ni de capture annotée"}

    axe_cache = CACHE_DIR / f"axe-{AXE_VERSION}.min.js"
    git = which("git")
    git_repo = False
    if git:
        git_repo = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True).returncode == 0

    capabilities = {
        "cree_le": now_iso(),
        "systeme": {"os": platform.system(), "version": platform.release(), "python": sys.version.split()[0], "interpreteur": sys.executable},
        "CAP-BROWSER": probe_playwright([e.strip() for e in args.engines.split(",") if e.strip()]),
        "CAP-DIFF": pillow,
        "CAP-A11Y-RULES": {
            "disponible": axe_cache.exists() or bool(os.environ.get("UI_AUDIT_AXE")),
            "cache": str(axe_cache),
            "note": "Téléchargé automatiquement au premier inspect_page.py si le réseau le permet (--no-axe pour l'éviter).",
        },
        "CAP-WEB": {"disponible": "a-determiner", "note": "Dépend des outils de recherche de l'agent hôte. Consigner l'échec avec research_log.py unavailable."},
        "CAP-FS": {"disponible": True},
        "CAP-VCS": {"git": bool(git), "depot": git_repo},
        "CAP-NATIVE": {
            "ios": which("xcrun", "xcodebuild"),
            "android": which("adb", "emulator"),
            "desktop_linux_atspi": which("accerciser"),
            "note": "Sans outillage natif, l'audit d'une application native est visuel seulement.",
        },
        "CAP-SR": {
            "lecteurs_detectes": which("orca", "nvda", "narrator"),
            "note": "Un lecteur d'écran détecté n'est pas piloté automatiquement : ACC-11 reste une vérification humaine.",
        },
        "CAP-DEVICE": {"adb_appareils": None},
    }
    if which("adb"):
        devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[1:]
        capabilities["CAP-DEVICE"]["adb_appareils"] = [d for d in devices if d.strip()]

    browser_ok = capabilities["CAP-BROWSER"]["disponible"]
    capabilities["mode_recommande"] = "complet" if browser_ok else "sans_execution"
    capabilities["actions"] = [] if browser_ok else [f"Proposer : bash \"{Path(__file__).parent / 'setup.sh'}\" (accord requis)"]
    if args.out:
        write_json(args.out, capabilities)
    emit(capabilities)


if __name__ == "__main__":
    main()
