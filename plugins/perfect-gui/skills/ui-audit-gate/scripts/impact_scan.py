#!/usr/bin/env python3
"""Inventaire d'impact : classe les fichiers modifiés, propage tokens, composants partagés et clés
de traduction vers leurs usages, puis suggère un niveau d'audit (N1, N2, N3).

Sans --base : modifications non commitées (indexées, non indexées, non suivies).
Avec --base REF : différences entre REF et HEAD, plus le non commité.

Exemple :
  python3 impact_scan.py --out .ui-audit/RUN-x/impact.json
  python3 impact_scan.py --base origin/main --out impact.json
"""
import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath

from _common import emit, load_config, now_iso, write_json

UI_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".styl", ".pcss", ".html", ".htm", ".vue", ".svelte", ".astro",
                 ".jsx", ".tsx", ".mdx", ".twig", ".erb", ".hbs", ".njk", ".liquid", ".razor", ".cshtml",
                 ".swift", ".kt", ".dart", ".xaml", ".storyboard", ".xib"}
SCRIPT_EXTENSIONS = {".js", ".ts", ".mjs", ".cjs"}
SOURCE_GLOBS = ["*.js", "*.jsx", "*.ts", "*.tsx", "*.vue", "*.svelte", "*.astro", "*.html", "*.css", "*.scss", "*.less", "*.mdx", "*.dart", "*.swift", "*.kt"]
UI_DEPENDENCIES = re.compile(r"(react|vue|svelte|angular|solid|preact|tailwind|bootstrap|mui|chakra|radix|shadcn|headlessui|antd|vuetify|quasar|primereact|mantine|styled-components|emotion|sass|postcss|font|icon|lucide|heroicons)", re.I)

RULES = [
    ("token", re.compile(r"(^|/)(tokens?|design-tokens|theme|themes|variables|vars)(/|\.|-|_)|tailwind\.config|\.tokens\.json$|theme\.(json|js|ts)$", re.I)),
    ("style-global", re.compile(r"(^|/)(global|globals|reset|normalize|base|app|index|main|styles?)\.(css|scss|sass|less|pcss)$|(^|/)styles?/", re.I)),
    ("config-build", re.compile(r"(^|/)(postcss|vite|webpack|next|nuxt|astro|svelte|rollup|babel|tsconfig|angular)\.?(config)?\.(js|cjs|mjs|ts|json)$", re.I)),
    ("dependance", re.compile(r"(^|/)(package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|pubspec\.yaml|Podfile|build\.gradle(\.kts)?)$")),
    ("i18n", re.compile(r"(^|/)(locales?|i18n|lang|translations?|messages)/|\.(po|pot|xliff|xlf|arb|strings)$", re.I)),
    ("composant-partage", re.compile(r"(^|/)(components?/(ui|common|shared|base|core)|ui|design-system|ds|shared|common|primitives|packages/ui)/", re.I)),
    ("navigation", re.compile(r"(^|/)(router|routes|routing|navigation|nav|menu|sidebar|header|layout|layouts)(/|\.)", re.I)),
    ("formulaire", re.compile(r"(form|field|input|select|checkbox|radio|validation|validator)", re.I)),
    ("page", re.compile(r"(^|/)(pages|app|routes|views|screens|templates)/", re.I)),
    ("composant-local", re.compile(r"(^|/)components?/", re.I)),
    ("logique-ui", re.compile(r"(^|/)(hooks|composables|stores?|state|directives)/", re.I)),
]


def git(*args, cwd="."):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def changed_files(base, cwd):
    files = set()
    if base:
        files |= set(git("diff", "--name-only", f"{base}...HEAD", cwd=cwd).split())
    files |= set(git("diff", "--name-only", "HEAD", cwd=cwd).split())
    files |= set(git("ls-files", "--others", "--exclude-standard", cwd=cwd).split())
    return sorted(f for f in files if not f.startswith(".ui-audit/"))


def diff_text(path, base, cwd):
    text = git("diff", "HEAD", "--", path, cwd=cwd)
    if base:
        text += git("diff", f"{base}...HEAD", "--", path, cwd=cwd)
    if not text and Path(cwd, path).exists():
        try:
            text = "".join("+" + line for line in Path(cwd, path).read_text(encoding="utf-8", errors="ignore").splitlines(True))
        except OSError:
            text = ""
    return text


def classify(path):
    p = PurePosixPath(path)
    kinds = [kind for kind, pattern in RULES if pattern.search(path)]
    if p.suffix in (".css", ".scss", ".sass", ".less", ".styl", ".pcss") and not kinds:
        kinds.append("style-local")
    is_ui = p.suffix in UI_EXTENSIONS or bool(kinds and kinds != ["dependance"]) or (p.suffix in SCRIPT_EXTENSIONS and bool(kinds))
    if "/res/layout" in path or "/res/values" in path:
        is_ui = True
        kinds.append("style-global" if "/values" in path else "composant-local")
    return (kinds or (["composant-local"] if p.suffix in UI_EXTENSIONS else [])), is_ui


def grep_files(pattern, cwd, fixed=True, exclude=None):
    args = ["grep", "--untracked", "-l", "-I", "-F" if fixed else "-E", "-e", pattern, "--", *SOURCE_GLOBS]
    output = git(*args, cwd=cwd)
    return sorted({f for f in output.split() if f != exclude and not f.startswith(".ui-audit/")})


def propagate(path, kinds, base, cwd):
    usages = []
    notes = []
    text = diff_text(path, base, cwd)
    changed_lines = [line[1:] for line in text.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    if {"token", "style-global"} & set(kinds):
        props = sorted({m for line in changed_lines for m in re.findall(r"(--[A-Za-z0-9_-]+)\s*:", line)})
        scss_vars = sorted({m for line in changed_lines for m in re.findall(r"(\$[A-Za-z][\w-]*)\s*:", line)})
        for name in props[:30]:
            usages += [{"fichier": f, "via": f"var({name})", "confiance": "certain"} for f in grep_files(f"var({name}", cwd, exclude=path)]
        for name in scss_vars[:30]:
            usages += [{"fichier": f, "via": name, "confiance": "certain"} for f in grep_files(name, cwd, exclude=path)]
        if not props and not scss_vars:
            notes.append("Aucune variable extraite du diff : considérer tous les écrans principaux comme touchés (confiance probable).")
    if {"composant-partage", "composant-local", "navigation", "formulaire"} & set(kinds):
        stem = PurePosixPath(path).stem
        if stem.lower() in ("index", "style", "styles", "main"):
            stem = PurePosixPath(path).parent.name
        if len(stem) > 2:
            for f in grep_files(rf"(import|require|from)[^\n]*['\"/]{re.escape(stem)}(['\"./]|$)", cwd, fixed=False, exclude=path):
                usages.append({"fichier": f, "via": f"import {stem}", "confiance": "certain"})
            for f in grep_files(f"<{stem}", cwd, exclude=path):
                usages.append({"fichier": f, "via": f"<{stem}", "confiance": "probable"})
    if "i18n" in kinds:
        keys = sorted({m for line in changed_lines for m in re.findall(r"\"([\w.-]{3,})\"\s*:", line)})
        for key in keys[:40]:
            usages += [{"fichier": f, "via": f"clé {key}", "confiance": "probable"} for f in grep_files(key, cwd, exclude=path)]
        notes.append("Vérifier chaque langue supportée : les longueurs diffèrent.")
    if "dependance" in kinds:
        ui_lines = [line.strip() for line in changed_lines if UI_DEPENDENCIES.search(line)]
        if ui_lines:
            notes.append("Dépendances UI modifiées : " + "; ".join(ui_lines[:8]))
        else:
            notes.append("Aucune dépendance UI reconnue dans le diff (vérifier si besoin).")
    unique = {}
    for usage in usages:
        unique.setdefault(usage["fichier"], usage)
    return list(unique.values()), notes


def suggest_level(entries):
    rules = load_config("levels.json")["regles"]
    kinds = {k for e in entries for k in e["types"]}
    paths = " ".join(e["fichier"].lower() for e in entries)
    reasons = []
    level = "N1"
    if kinds & set(rules["N2_si_types"]):
        level = "N2"
        reasons.append("types " + ", ".join(sorted(kinds & set(rules["N2_si_types"]))))
    if kinds & set(rules["N3_si_types"]):
        dependency_only = kinds & set(rules["N3_si_types"]) == {"dependance"} and not any("Dépendances UI modifiées" in n for e in entries for n in e["notes"])
        if not dependency_only:
            level = "N3"
            reasons.append("types " + ", ".join(sorted(kinds & set(rules["N3_si_types"]))))
    critical = [w for w in rules["N3_si_chemins"] if w in paths]
    if critical:
        level = "N3"
        reasons.append("parcours critique probable : " + ", ".join(critical))
    return level, reasons or ["changement local"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="Référence git de comparaison (branche, commit)")
    parser.add_argument("--root", default=".")
    parser.add_argument("--files", nargs="*", help="Liste explicite de fichiers (sans git)")
    parser.add_argument("--out")
    args = parser.parse_args()

    cwd = Path(args.root).resolve()
    inside = git("rev-parse", "--is-inside-work-tree", cwd=cwd).strip() == "true"
    if args.files:
        files = args.files
        source = "liste fournie"
    elif inside:
        files = changed_files(args.base, cwd)
        source = f"git (base {args.base})" if args.base else "git (non commité)"
    else:
        emit({"tool": "impact_scan", "status": "capability-missing", "capability": "git",
              "hint": "Pas de dépôt git : fournir --files ou déduire le périmètre de la session (confiance : inconnu)."}, 3)

    entries = []
    for path in files:
        kinds, is_ui = classify(path)
        if not is_ui and "dependance" not in kinds:
            continue
        usages, notes = propagate(path, kinds, args.base, cwd) if inside else ([], ["Propagation impossible sans git"])
        entries.append({"fichier": path, "types": kinds, "usages": usages, "notes": notes})

    level, reasons = suggest_level(entries)
    impacted = sorted({u["fichier"] for e in entries for u in e["usages"]} | {e["fichier"] for e in entries})
    global_change = any({"token", "style-global", "config-build"} & set(e["types"]) for e in entries)
    result = {
        "tool": "impact_scan",
        "cree_le": now_iso(),
        "source": source,
        "fichiers_modifies": files,
        "fichiers_ui": entries,
        "zones_impactees": impacted,
        "changement_global": global_change,
        "niveau_suggere": level,
        "raisons": reasons,
        "rappel": "Si changement_global : échantillonner tous les écrans principaux, la détection statique ne voit pas tout." if global_change else None,
    }
    if not entries:
        result["note"] = "Aucun fichier d'interface détecté. Vérifier que la demande ne touche pas l'UI par un autre biais (données affichées, API)."
    if args.out:
        write_json(args.out, result)
    emit(result)


if __name__ == "__main__":
    main()
