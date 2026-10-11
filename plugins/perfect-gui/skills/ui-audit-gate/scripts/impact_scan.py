#!/usr/bin/env python3
"""Impact inventory: classifies changed files, follows tokens, shared components and translation
keys to their usages, then suggests an audit level (N1, N2, N3).

Without --base: uncommitted changes (staged, unstaged, untracked).
With --base REF: differences between REF and HEAD, plus uncommitted changes.

Example:
  python3 impact_scan.py --out .ui-audit/RUN-x/impact.json
  python3 impact_scan.py --base origin/main --out impact.json
"""
import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath

import time

from _common import emit, load_config, now_iso, project_files, read_json, ui_files, ui_snapshot, write_json

IN_GIT = {}

UI_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".styl", ".pcss", ".html", ".htm", ".vue", ".svelte", ".astro",
                 ".jsx", ".tsx", ".mdx", ".twig", ".erb", ".hbs", ".njk", ".liquid", ".razor", ".cshtml",
                 ".swift", ".kt", ".dart", ".xaml", ".storyboard", ".xib"}
SCRIPT_EXTENSIONS = {".js", ".ts", ".mjs", ".cjs"}
SOURCE_GLOBS = ["*.js", "*.jsx", "*.ts", "*.tsx", "*.vue", "*.svelte", "*.astro", "*.html", "*.css", "*.scss", "*.less", "*.mdx", "*.dart", "*.swift", "*.kt"]
UI_DEPENDENCIES = re.compile(r"(react|vue|svelte|angular|solid|preact|tailwind|bootstrap|mui|chakra|radix|shadcn|headlessui|antd|vuetify|quasar|primereact|mantine|styled-components|emotion|sass|postcss|font|icon|lucide|heroicons)", re.I)

RULES = [
    ("token", re.compile(r"(^|/)(tokens?|design-tokens|theme|themes|variables|vars)(/|\.|-|_)|tailwind\.config|\.tokens\.json$|theme\.(json|js|ts)$", re.I)),
    ("global-style", re.compile(r"(^|/)(global|globals|reset|normalize|base|app|index|main|styles?)\.(css|scss|sass|less|pcss)$|(^|/)styles?/", re.I)),
    ("build-config", re.compile(r"(^|/)(postcss|vite|webpack|next|nuxt|astro|svelte|rollup|babel|tsconfig|angular)\.?(config)?\.(js|cjs|mjs|ts|json)$", re.I)),
    ("dependency", re.compile(r"(^|/)(package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?|pubspec\.yaml|Podfile|build\.gradle(\.kts)?)$")),
    ("i18n", re.compile(r"(^|/)(locales?|i18n|lang|translations?|messages)/|\.(po|pot|xliff|xlf|arb|strings)$", re.I)),
    ("shared-component", re.compile(r"(^|/)(components?/(ui|common|shared|base|core)|ui|design-system|ds|shared|common|primitives|packages/ui)/", re.I)),
    ("navigation", re.compile(r"(^|/)(router|routes|routing|navigation|nav|menu|sidebar|header|layout|layouts)(/|\.)", re.I)),
    ("form", re.compile(r"(form|field|input|select|checkbox|radio|validation|validator)", re.I)),
    ("page", re.compile(r"(^|/)(pages|app|routes|views|screens|templates)/", re.I)),
    ("local-component", re.compile(r"(^|/)components?/", re.I)),
    ("ui-logic", re.compile(r"(^|/)(hooks|composables|stores?|state|directives)/", re.I)),
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
    text = git("diff", "HEAD", "--", path, cwd=cwd) if in_git(cwd) else ""
    if base and in_git(cwd):
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
        kinds.append("local-style")
    is_ui = p.suffix in UI_EXTENSIONS or bool(kinds and kinds != ["dependency"]) or (p.suffix in SCRIPT_EXTENSIONS and bool(kinds))
    if "/res/layout" in path or "/res/values" in path:
        is_ui = True
        kinds.append("global-style" if "/values" in path else "local-component")
    return (kinds or (["local-component"] if p.suffix in UI_EXTENSIONS else [])), is_ui


def in_git(cwd):
    key = str(cwd)
    if key not in IN_GIT:
        IN_GIT[key] = git("rev-parse", "--is-inside-work-tree", cwd=cwd).strip() == "true"
    return IN_GIT[key]


def grep_files(pattern, cwd, fixed=True, exclude=None):
    if in_git(cwd):
        args = ["grep", "--untracked", "-l", "-I", "-F" if fixed else "-E", "-e", pattern, "--", *SOURCE_GLOBS]
        output = git(*args, cwd=cwd)
        return sorted({f for f in output.split() if f != exclude and not f.startswith(".ui-audit/")})
    suffixes = {glob[1:] for glob in SOURCE_GLOBS}
    regex = re.compile(re.escape(pattern) if fixed else pattern)
    found = set()
    for path in project_files(cwd)[0]:
        if path == exclude or PurePosixPath(path).suffix not in suffixes:
            continue
        try:
            if regex.search(Path(cwd, path).read_text(encoding="utf-8", errors="ignore")):
                found.add(path)
        except OSError:
            continue
    return sorted(found)


def changed_without_git(cwd, since_hours):
    snapshot_path = cwd / ".ui-audit" / "snapshot.json"
    snapshot = read_json(snapshot_path, None)
    current = ui_snapshot(cwd)
    if snapshot and since_hours is None:
        before = snapshot.get("files", {})
        changed = sorted(p for p, meta in current["files"].items() if before.get(p, {}).get("sha1") != meta["sha1"])
        return changed, f"snapshot comparison ({snapshot.get('created_at')})", "certain"
    hours = since_hours if since_hours is not None else 24
    limit = time.time() - hours * 3600
    changed = sorted(p for p, meta in current["files"].items() if meta["mtime"] >= limit)
    return changed, f"files modified in the last {hours} h (no git, no snapshot)", "probable"


def propagate(path, kinds, base, cwd):
    usages = []
    notes = []
    text = diff_text(path, base, cwd)
    changed_lines = [line[1:] for line in text.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    if {"token", "global-style"} & set(kinds):
        props = sorted({m for line in changed_lines for m in re.findall(r"(--[A-Za-z0-9_-]+)\s*:", line)})
        scss_vars = sorted({m for line in changed_lines for m in re.findall(r"(\$[A-Za-z][\w-]*)\s*:", line)})
        for name in props[:30]:
            usages += [{"file": f, "via": f"var({name})", "confidence": "certain"} for f in grep_files(f"var({name}", cwd, exclude=path)]
        for name in scss_vars[:30]:
            usages += [{"file": f, "via": name, "confidence": "certain"} for f in grep_files(name, cwd, exclude=path)]
        if not props and not scss_vars:
            notes.append("No variable extracted from the diff: treat all main screens as affected (probable confidence).")
    if {"shared-component", "local-component", "navigation", "form"} & set(kinds):
        stem = PurePosixPath(path).stem
        if stem.lower() in ("index", "style", "styles", "main"):
            stem = PurePosixPath(path).parent.name
        if len(stem) > 2:
            for f in grep_files(rf"(import|require|from)[^\n]*['\"/]{re.escape(stem)}(['\"./]|$)", cwd, fixed=False, exclude=path):
                usages.append({"file": f, "via": f"import {stem}", "confidence": "certain"})
            for f in grep_files(f"<{stem}", cwd, exclude=path):
                usages.append({"file": f, "via": f"<{stem}", "confidence": "probable"})
    if "i18n" in kinds:
        keys = sorted({m for line in changed_lines for m in re.findall(r"\"([\w.-]{3,})\"\s*:", line)})
        for key in keys[:40]:
            usages += [{"file": f, "via": f"key {key}", "confidence": "probable"} for f in grep_files(key, cwd, exclude=path)]
        notes.append("Check every supported language: text lengths differ.")
    if "dependency" in kinds:
        ui_lines = [line.strip() for line in changed_lines if UI_DEPENDENCIES.search(line)]
        if ui_lines:
            notes.append("UI dependencies changed: " + "; ".join(ui_lines[:8]))
        else:
            notes.append("No known UI dependency in the diff (check if needed).")
    unique = {}
    for usage in usages:
        unique.setdefault(usage["file"], usage)
    return list(unique.values()), notes


def suggest_level(entries):
    rules = load_config("levels.json")["rules"]
    kinds = {k for e in entries for k in e["types"]}
    paths = " ".join(e["file"].lower() for e in entries)
    reasons = []
    level = "N1"
    if kinds & set(rules["N2_if_types"]):
        level = "N2"
        reasons.append("types " + ", ".join(sorted(kinds & set(rules["N2_if_types"]))))
    if kinds & set(rules["N3_if_types"]):
        dependency_only = kinds & set(rules["N3_if_types"]) == {"dependency"} and not any("UI dependencies changed" in n for e in entries for n in e["notes"])
        if not dependency_only:
            level = "N3"
            reasons.append("types " + ", ".join(sorted(kinds & set(rules["N3_if_types"]))))
    critical = [w for w in rules["N3_if_paths"] if w in paths]
    if critical:
        level = "N3"
        reasons.append("likely critical flow: " + ", ".join(critical))
    return level, reasons or ["local change"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="Git reference to compare against (branch, commit)")
    parser.add_argument("--root", default=".")
    parser.add_argument("--files", nargs="*", help="Explicit list of files (without git)")
    parser.add_argument("--since-hours", type=float, help="Without git: files modified in the last N hours (default: compare with .ui-audit/snapshot.json, else 24 h)")
    parser.add_argument("--out")
    args = parser.parse_args()

    cwd = Path(args.root).resolve()
    inside = in_git(cwd)
    if args.files:
        files = args.files
        source = "provided list"
    elif inside:
        files = changed_files(args.base, cwd)
        source = f"git (base {args.base})" if args.base else "git (uncommitted)"
    else:
        files, source, detection_confidence = changed_without_git(cwd, args.since_hours)

    entries = []
    for path in files:
        kinds, is_ui = classify(path)
        if not is_ui and "dependency" not in kinds:
            continue
        usages, notes = propagate(path, kinds, args.base, cwd)
        if not inside:
            notes.append("No git: the whole file is treated as changed, so token and key propagation may over-report.")
        entries.append({"file": path, "types": kinds, "usages": usages, "notes": notes})

    level, reasons = suggest_level(entries)
    impacted = sorted({u["file"] for e in entries for u in e["usages"]} | {e["file"] for e in entries})
    global_change = any({"token", "global-style", "build-config"} & set(e["types"]) for e in entries)
    result = {
        "tool": "impact_scan",
        "created_at": now_iso(),
        "source": source,
        "detection_confidence": "certain" if inside or args.files else detection_confidence,
        "changed_files": files,
        "ui_files": entries,
        "impacted_files": impacted,
        "global_change": global_change,
        "suggested_level": level,
        "reasons": reasons,
        "reminder": "If global_change: sample all main screens, static detection does not see everything." if global_change else None,
    }
    if not entries:
        result["note"] = "No interface file detected. Check that the request does not affect the UI some other way (displayed data, API)."
    if args.out:
        write_json(args.out, result)
    emit(result)


if __name__ == "__main__":
    main()
