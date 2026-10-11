#!/usr/bin/env python3
"""Diff pixel entre deux dossiers de captures (mêmes chemins relatifs).

Chaque différence doit ensuite être qualifiée : attendue (liée à la correction) ou régression.

Exemple :
  python3 visual_diff.py --before .ui-audit/RUN-x/before --after .ui-audit/RUN-x/after-fix-1 --out .ui-audit/RUN-x/diff
"""
import argparse
from pathlib import Path

from _common import emit, ensure_module, now_iso


def compare(before_path, after_path, out_path, tolerance):
    from PIL import Image, ImageChops

    before = Image.open(before_path).convert("RGB")
    after = Image.open(after_path).convert("RGB")
    entry = {"before_size": list(before.size), "after_size": list(after.size)}
    width, height = min(before.width, after.width), min(before.height, after.height)
    if before.size != after.size:
        entry["size_mismatch"] = True
    cropped_before = before.crop((0, 0, width, height))
    cropped_after = after.crop((0, 0, width, height))
    mask = ImageChops.difference(cropped_before, cropped_after).convert("L").point(lambda v: 255 if v > tolerance else 0)
    changed = mask.histogram()[255]
    entry["changed_pixels"] = changed
    entry["changed_ratio"] = round(changed / float(width * height), 6) if width and height else 0
    entry["bbox"] = list(mask.getbbox()) if changed else None
    if changed or before.size != after.size:
        base = cropped_after.convert("L").convert("RGB")
        red = Image.new("RGB", base.size, (230, 0, 50))
        overlay = Image.composite(red, Image.blend(base, cropped_after, 0.35), mask)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        overlay.save(out_path)
        entry["diff_image"] = str(out_path)
    entry["status"] = "taille-differente" if before.size != after.size else ("change" if changed else "identique")
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--tolerance", type=int, default=16, help="Écart par canal ignoré (anticrénelage)")
    parser.add_argument("--max-ratio", type=float, default=0.0, help="Ratio de pixels changés toléré avant de signaler")
    args = parser.parse_args()
    ensure_module("PIL", "pillow", "Installer Pillow (setup.sh) ou comparer les captures visuellement")

    before_root, after_root, out_root = Path(args.before), Path(args.after), Path(args.out)
    before_files = {p.relative_to(before_root) for p in before_root.rglob("*.png")}
    after_files = {p.relative_to(after_root) for p in after_root.rglob("*.png")}
    results = []
    for rel in sorted(before_files | after_files):
        if rel not in after_files:
            results.append({"file": str(rel), "status": "absent-apres"})
            continue
        if rel not in before_files:
            results.append({"file": str(rel), "status": "absent-avant"})
            continue
        entry = compare(before_root / rel, after_root / rel, out_root / rel, args.tolerance)
        entry["file"] = str(rel)
        entry["signale"] = entry["status"] == "taille-differente" or entry["changed_ratio"] > args.max_ratio
        results.append(entry)

    flagged = [r for r in results if r.get("signale") or r["status"].startswith("absent")]
    emit({
        "tool": "visual_diff", "created": now_iso(), "compared": len(results), "flagged": len(flagged),
        "result": "issues" if flagged else "clean",
        "rappel": "Qualifier chaque différence : attendue ou régression. Conditions de capture identiques requises (manifestes).",
        "items": results,
    })


if __name__ == "__main__":
    main()
