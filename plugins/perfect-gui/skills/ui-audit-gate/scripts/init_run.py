#!/usr/bin/env python3
"""Crée un dossier d'audit .ui-audit/RUN-<date>-<slug>/ avec ses squelettes.

Exemple :
  python3 init_run.py --slug checkout-footer --level N2 --trigger C2
"""
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

from _common import SKILL_DIR, emit, now_iso, safe_name, write_json


def ensure_gitignore(root):
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "git indisponible"
    if top.returncode != 0:
        return "pas un dépôt git"
    gitignore = Path(top.stdout.strip()) / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if any(line.strip() in (".ui-audit", ".ui-audit/", "/.ui-audit", "/.ui-audit/") for line in lines):
        return "déjà ignoré"
    with gitignore.open("a", encoding="utf-8") as handle:
        handle.write(("\n" if lines and lines[-1].strip() else "") + "# Preuves d'audit UI (captures locales)\n.ui-audit/\n")
    return f"ajouté à {gitignore}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--root", default=".", help="Racine du projet audité")
    parser.add_argument("--title", default="")
    parser.add_argument("--level", default="N1", choices=["N1", "N2", "N3"])
    parser.add_argument("--mode", default="complet", choices=["complet", "maquette", "sans_execution"])
    parser.add_argument("--trigger", default="C1", choices=["C1", "C2", "C3"], help="C1 sémantique, C2 commande explicite, C3 hook ou CI")
    parser.add_argument("--no-gitignore", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_name(args.slug)}"
    run = root / ".ui-audit" / run_id
    for sub in ["before", "after", "inspect", "keyboard", "diff", "findings", "research", "traces"]:
        (run / sub).mkdir(parents=True, exist_ok=True)

    scope_template = (SKILL_DIR / "templates" / "scope.md").read_text(encoding="utf-8")
    (run / "scope.md").write_text(scope_template.replace("{{RUN_ID}}", run_id).replace("{{DATE}}", now_iso()), encoding="utf-8")
    write_json(run / "research" / "log.json", [])
    write_json(run / "research" / "references.json", [])
    write_json(run / "coverage.json", {"executees": [], "exclues": []})
    write_json(run / "report.json", {
        "run_id": run_id,
        "titre": args.title or args.slug,
        "cree_le": now_iso(),
        "declenchement": args.trigger,
        "demande": "",
        "objectif": "",
        "criteres_acceptation": [],
        "perimetre": {"zones": [], "rayon_impact": []},
        "niveau": args.level,
        "niveau_calcule": args.level,
        "couverture_reduite": False,
        "justification_reduction": None,
        "mode": args.mode,
        "baseline": "avant",
        "environnement": {"outils": [], "fidelite": "emulation"},
        "hypotheses": [],
        "recherche": {"statut": "non_realisee", "cause": "pas encore effectuée"},
        "comparaisons": [],
        "changement_visuel": True,
        "controles": [],
        "defauts": [],
        "corrections": [],
        "variantes": [],
        "avant_apres": [],
        "regressions": [],
        "coverage": "coverage.json",
        "limites": [],
        "verifications_humaines": [],
        "decision": None,
    })
    gitignore = "non modifié (--no-gitignore)" if args.no_gitignore else ensure_gitignore(root)
    emit({"tool": "init_run", "run": str(run), "run_id": run_id, "gitignore": gitignore,
          "suite": "probe.py --out RUN/capabilities.json puis impact_scan.py --out RUN/impact.json"})


if __name__ == "__main__":
    main()
