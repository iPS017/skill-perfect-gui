#!/usr/bin/env python3
"""Pseudo-localise un fichier de traduction JSON (imbriqué ou plat) en préservant les variables.

Chaque chaîne devient [Ácçéñţš...ẋẋẋ] : environ +40 %, accents, délimiteurs visibles.
Le texte sans délimiteurs à l'écran signale une chaîne non externalisée (LOC-02).

Exemple :
  python3 pseudo_locale.py src/locales/fr.json src/locales/pseudo.json --expansion 0.4
"""
import argparse
import json
import re
from pathlib import Path

ACCENTS = str.maketrans({
    "a": "á", "e": "é", "i": "î", "o": "ö", "u": "ü", "c": "ç", "n": "ñ", "y": "ý", "s": "š", "z": "ž",
    "A": "Å", "E": "É", "I": "Î", "O": "Ö", "U": "Ü", "C": "Ç", "N": "Ñ",
})
PLACEHOLDER = re.compile(r"(\{\{[^}]*\}\}|\{[^{}]*\}|%\([^)]+\)[sdif]|%[sdif@]|\$\{[^}]*\}|<[^>]+>|:[A-Za-z_]\w*|\$t\([^)]*\))")


def pseudo(text, expansion):
    if not text.strip():
        return text
    parts = PLACEHOLDER.split(text)
    converted = "".join(p if PLACEHOLDER.fullmatch(p) else p.translate(ACCENTS) for p in parts)
    visible = sum(len(p) for p in parts if not PLACEHOLDER.fullmatch(p))
    return f"[{converted}{'ẋ' * max(2, round(visible * expansion))}]"


def transform(node, expansion):
    if isinstance(node, str):
        return pseudo(node, expansion)
    if isinstance(node, list):
        return [transform(v, expansion) for v in node]
    if isinstance(node, dict):
        return {k: transform(v, expansion) for k, v in node.items()}
    return node


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--expansion", type=float, default=0.4)
    args = parser.parse_args()
    data = json.loads(Path(args.source).read_text(encoding="utf-8"))
    Path(args.target).write_text(json.dumps(transform(data, args.expansion), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tool": "pseudo_locale", "source": args.source, "target": args.target, "expansion": args.expansion}, ensure_ascii=False))


if __name__ == "__main__":
    main()
