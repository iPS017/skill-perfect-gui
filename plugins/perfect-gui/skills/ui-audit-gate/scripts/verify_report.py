#!/usr/bin/env python3
"""Vérifie la cohérence d'un rapport d'audit, calcule la décision (reference/validation-gate.md)
et produit report.md.

Codes de sortie : 0 cohérent, 1 incohérences, 2 fichiers manquants.

Exemples :
  python3 verify_report.py .ui-audit/RUN-x
  python3 verify_report.py .ui-audit/RUN-x --apply --render
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_config, now_iso, read_json, write_json  # noqa: E402

DECISIONS = ["VALIDEE_PROTOCOLE_COMPLET", "VALIDEE_PERIMETRE_TESTE", "VALIDEE_AVEC_EXCEPTIONS", "NON_VALIDEE", "VALIDATION_LIMITEE"]
DECISION_LABELS = {
    "VALIDEE_PROTOCOLE_COMPLET": "VALIDÉE : protocole complet",
    "VALIDEE_PERIMETRE_TESTE": "VALIDÉE : périmètre testé seulement",
    "VALIDEE_AVEC_EXCEPTIONS": "VALIDÉE avec exceptions acceptées",
    "NON_VALIDEE": "NON VALIDÉE",
    "VALIDATION_LIMITEE": "VALIDATION LIMITÉE",
}
STATUSES = {"reussi", "echoue", "non_verifie", "non_applicable"}
REASON_TYPES = {"technique", "humain", "appareil_reel", "hors_perimetre", "autre"}
SEVERITIES = {"critique", "majeure", "moderee", "mineure"}
DEFECT_STATUSES = {"ouvert", "corrige", "echoue_non_resolu", "accepte_exception"}
OPEN_STATUSES = {"ouvert", "echoue_non_resolu", "accepte_exception"}
NATURES = {"EXIGENCE", "HYPOTHESE", "PREFERENCE"}
DEFECT_FIELDS = ["id", "titre", "controle", "severite", "priorite", "confiance", "nature", "statut", "attendu", "observe", "preuves"]


def normalize(url):
    parsed = urlparse(url.strip())
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}" + (f"?{parsed.query}" if parsed.query else "")


def exists(run, path):
    p = Path(path)
    return (p if p.is_absolute() else run / p).exists()


def load_defects(run, report):
    merged = {}
    for defect in report.get("defauts", []):
        if isinstance(defect, dict) and defect.get("id"):
            merged[defect["id"]] = defect
    for path in sorted((run / "findings").glob("*.json")) if (run / "findings").exists() else []:
        data = read_json(path)
        if isinstance(data, dict) and data.get("id"):
            merged.setdefault(data["id"], {}).update(data)
    return list(merged.values())


def verify(run):
    run = Path(run)
    report = read_json(run / "report.json")
    if report is None:
        return {"status": "missing", "errors": [f"report.json absent dans {run}"]}
    errors, warnings, blocking, downgrades = [], [], [], []
    levels = load_config("levels.json")
    fundamentals = set(levels["fondamentaux"])
    mode = report.get("mode", "complet")
    limited = mode in ("maquette", "sans_execution")

    controls = {}
    for control in report.get("controles", []):
        cid = control.get("id")
        if not cid:
            errors.append("Contrôle sans identifiant")
            continue
        if cid in controls:
            warnings.append(f"{cid} listé plusieurs fois : la dernière entrée est retenue")
        controls[cid] = control
        status = control.get("statut")
        if status not in STATUSES:
            errors.append(f"{cid} : statut invalide {status!r} (attendu {sorted(STATUSES)})")
            continue
        if status == "reussi":
            proofs = control.get("preuves") or []
            if not proofs:
                errors.append(f"{cid} : 'reussi' sans preuve")
            for proof in proofs:
                if not exists(run, proof):
                    errors.append(f"{cid} : preuve introuvable {proof}")
        if status in ("non_verifie", "non_applicable") and not control.get("raison"):
            errors.append(f"{cid} : '{status}' sans raison")
        if status == "non_verifie" and control.get("raison_type") not in REASON_TYPES:
            errors.append(f"{cid} : raison_type manquant ou invalide (attendu {sorted(REASON_TYPES)})")

    defects = load_defects(run, report)
    defect_controls = {d.get("controle") for d in defects}
    for cid, control in controls.items():
        if control.get("statut") == "echoue" and cid not in defect_controls:
            errors.append(f"{cid} : 'echoue' sans fiche de défaut qui le référence")

    exceptions_used = []
    for defect in defects:
        did = defect.get("id", "?")
        missing = [f for f in DEFECT_FIELDS if defect.get(f) in (None, "", [])]
        if missing:
            errors.append(f"{did} : champs manquants {missing}")
        if defect.get("severite") not in SEVERITIES:
            errors.append(f"{did} : sévérité invalide {defect.get('severite')!r}")
        if defect.get("statut") not in DEFECT_STATUSES:
            errors.append(f"{did} : statut invalide {defect.get('statut')!r}")
        nature = str(defect.get("nature", "")).strip("[]").upper().replace("È", "E").replace("É", "E")
        if nature not in NATURES:
            errors.append(f"{did} : nature invalide {defect.get('nature')!r} (EXIGENCE, HYPOTHESE, PREFERENCE)")
        for proof in defect.get("preuves") or []:
            if not exists(run, proof):
                errors.append(f"{did} : preuve introuvable {proof}")
        status = defect.get("statut")
        if status == "corrige":
            retest = defect.get("retest") or {}
            if retest.get("statut") != "reussi" or not retest.get("preuves"):
                errors.append(f"{did} : 'corrige' sans retest réussi et prouvé")
            for proof in retest.get("preuves") or []:
                if not exists(run, proof):
                    errors.append(f"{did} : preuve de retest introuvable {proof}")
        if status == "echoue_non_resolu" and not (defect.get("cause_blocage") and defect.get("action_requise")):
            errors.append(f"{did} : 'echoue_non_resolu' exige cause_blocage et action_requise")
        if status not in OPEN_STATUSES:
            continue
        severity = defect.get("severite")
        if severity == "critique":
            blocking.append(f"B1 : défaut critique ouvert {did}")
            if status == "accepte_exception":
                errors.append(f"{did} : une exception ne peut pas couvrir un défaut critique")
        elif severity == "majeure" and nature == "EXIGENCE":
            exception = defect.get("exception") or {}
            valid = status == "accepte_exception" and all(exception.get(k) for k in ("acceptee_par", "date", "citation"))
            if valid:
                exceptions_used.append(did)
            else:
                blocking.append(f"B2 : défaut majeur [EXIGENCE] ouvert sans exception valide {did}")
                if status == "accepte_exception":
                    errors.append(f"{did} : exception incomplète (acceptee_par, date, citation de l'utilisateur)")
        if defect.get("introduit_par_correction"):
            blocking.append(f"B6 : régression introduite par une correction, ouverte {did}")

    for cid in sorted(fundamentals):
        control = controls.get(cid)
        if control is None:
            blocking.append(f"B3 : contrôle fondamental absent du rapport {cid}")
        elif control.get("statut") == "non_verifie" and control.get("raison_type") not in ("technique", "humain", "appareil_reel"):
            blocking.append(f"B3 : contrôle fondamental non vérifié sans raison technique {cid}")

    if not limited:
        main_path = controls.get("PAR-01")
        if main_path and main_path.get("statut") == "non_applicable":
            warnings.append("PAR-01 non applicable : justifier dans le rapport")
        elif not main_path or main_path.get("statut") != "reussi":
            blocking.append("B4 : parcours principal (PAR-01) non réussi")

    if report.get("changement_visuel", True) and not limited:
        pairs = [p for p in report.get("avant_apres", []) if p.get("apres") and exists(run, p["apres"])]
        for pair in report.get("avant_apres", []):
            for key in ("avant", "apres", "diff"):
                if pair.get(key) and not exists(run, pair[key]):
                    errors.append(f"avant_apres : fichier introuvable {pair[key]}")
        if not pairs:
            blocking.append("B5 : changement visuel sans capture après (avant/après) existante")
        elif report.get("corrections") and not any("after-fix" in p["apres"] for p in pairs):
            blocking.append("B5 : corrections appliquées sans recapture dans un dossier after-fix-*")

    log = read_json(run / "research" / "log.json", []) or []
    refs = read_json(run / "research" / "references.json", []) or []
    seen = set()
    for entry in log:
        if entry.get("type") == "visit" and entry.get("failed"):
            continue
        for url in entry.get("urls", []) + ([entry["url"]] if entry.get("url") else []):
            seen.add(normalize(url))
    valid_refs = []
    for ref in refs:
        if ref.get("statut_consultation") in ("consultee", "revalidee"):
            if normalize(ref.get("url", "")) not in seen:
                errors.append(f"{ref.get('id', '?')} : URL absente du journal de recherche (référence non tracée ou fabriquée) {ref.get('url')}")
            else:
                valid_refs.append(ref)
    research = report.get("recherche") or {}
    research_status = research.get("statut")
    if research_status not in ("realisee", "partielle", "non_realisee"):
        errors.append(f"recherche.statut invalide {research_status!r}")
    if research_status in ("realisee", "partielle") and not valid_refs:
        errors.append("recherche déclarée réalisée sans aucune référence consultée et tracée")
    if research_status == "non_realisee" and not research.get("cause"):
        errors.append("recherche non réalisée sans cause")
    if research_status != "realisee":
        downgrades.append(f"recherche Web : {research_status}")
    max_refs = levels["max_references"].get(report.get("niveau", "N1"), 5)
    if len(valid_refs) > max_refs:
        warnings.append(f"{len(valid_refs)} références pour un plafond indicatif de {max_refs} : justifier ou retirer les liens décoratifs")
    compared = {c.get("ref") for c in report.get("comparaisons", [])}
    for ref in valid_refs:
        if ref.get("id") not in compared:
            warnings.append(f"{ref.get('id')} retenue sans ligne de comparaison")

    human_checks = []
    for cid, control in controls.items():
        if control.get("statut") != "non_verifie":
            continue
        if control.get("raison_type") in ("humain", "appareil_reel"):
            human_checks.append(f"{cid} ({control.get('raison_type')}) : {control.get('raison')}")
        else:
            downgrades.append(f"{cid} non vérifié ({control.get('raison_type')})")
    if report.get("couverture_reduite"):
        downgrades.append("couverture réduite : " + str(report.get("justification_reduction") or "justification manquante"))
        if not report.get("justification_reduction"):
            errors.append("couverture_reduite sans justification_reduction")
    if not exists(run, report.get("coverage") or "coverage.json"):
        warnings.append("coverage.json absent : lister les combinaisons exécutées et exclues")

    if blocking:
        decision = "NON_VALIDEE"
    elif limited:
        decision = "VALIDATION_LIMITEE"
    elif exceptions_used:
        decision = "VALIDEE_AVEC_EXCEPTIONS"
    elif downgrades:
        decision = "VALIDEE_PERIMETRE_TESTE"
    else:
        decision = "VALIDEE_PROTOCOLE_COMPLET"

    written = report.get("decision")
    if written is None:
        warnings.append("decision absente du rapport (utiliser --apply)")
    elif written not in DECISIONS:
        errors.append(f"decision invalide {written!r}")
    elif written != decision:
        errors.append(f"decision écrite {written} différente de la décision calculée {decision}")

    return {
        "status": "ok" if not errors else "inconsistent",
        "run": str(run),
        "decision_calculee": decision,
        "decision_ecrite": written,
        "bloquants": blocking,
        "baisses": downgrades,
        "exceptions": exceptions_used,
        "verifications_humaines": human_checks,
        "errors": errors,
        "warnings": warnings,
        "defauts": defects,
        "references_valides": valid_refs,
    }


def bullet(items, empty="Aucun."):
    return "\n".join(f"- {i}" for i in items) if items else empty


def render(run, report, result):
    run = Path(run)
    defects = result["defauts"]
    counts = {s: sum(1 for d in defects if d.get("severite") == s) for s in ["critique", "majeure", "moderee", "mineure"]}
    open_counts = {s: sum(1 for d in defects if d.get("severite") == s and d.get("statut") in OPEN_STATUSES) for s in counts}
    controls = report.get("controles", [])
    by_status = {s: [c["id"] for c in controls if c.get("statut") == s] for s in ["reussi", "echoue", "non_verifie", "non_applicable"]}
    lines = [
        f"# Audit UI : {report.get('titre', '')} ({report.get('run_id', run.name)})",
        "",
        f"## Décision : {DECISION_LABELS[result['decision_calculee']]}",
        "",
        f"Défauts : {counts['critique']} critiques, {counts['majeure']} majeurs, {counts['moderee']} modérés, {counts['mineure']} mineurs. "
        f"Encore ouverts : {open_counts['critique']} / {open_counts['majeure']} / {open_counts['moderee']} / {open_counts['mineure']}.",
        "",
        "Conditions bloquantes :",
        bullet(result["bloquants"]),
        "",
        "Ce qui limite la validation :",
        bullet(result["baisses"]),
        "",
        "> Une absence de défaut détecté n'est pas une absence de défaut. Cette décision ne vaut que pour le périmètre, les configurations et les contrôles listés ci-dessous.",
        "",
        "## Périmètre",
        "",
        f"- Demande : {report.get('demande') or 'non renseignée'}",
        f"- Objectif : {report.get('objectif') or 'non renseigné'}",
        f"- Zones : {', '.join(report.get('perimetre', {}).get('zones', [])) or 'non renseignées'}",
        f"- Rayon d'impact : {', '.join(report.get('perimetre', {}).get('rayon_impact', [])) or 'non renseigné'}",
        f"- Niveau : {report.get('niveau')} (calculé : {report.get('niveau_calcule')})" + (f", couverture réduite : {report.get('justification_reduction')}" if report.get("couverture_reduite") else ""),
        f"- Mode : {report.get('mode')} ; baseline : {report.get('baseline')} ; déclenchement : {report.get('declenchement')}",
        "",
        "Critères d'acceptation :",
        bullet(report.get("criteres_acceptation", [])),
        "",
        "## Hypothèses",
        "",
    ]
    hypotheses = report.get("hypotheses", [])
    if hypotheses:
        lines += ["| Hypothèse | Source | Impact si fausse |", "|---|---|---|"]
        lines += [f"| {h.get('hypothese', '')} | {h.get('source', '')} | {h.get('impact_si_fausse', '')} |" for h in hypotheses]
    else:
        lines.append("Aucune.")
    env = report.get("environnement", {})
    lines += ["", "## Environnement", "", f"- Outils : {', '.join(env.get('outils', [])) or 'non renseignés'}", f"- Fidélité : {env.get('fidelite', 'non renseignée')}", ""]
    research = report.get("recherche", {})
    lines += ["## Références consultées", "", f"Statut de la recherche : {research.get('statut')}" + (f" ({research.get('cause')})" if research.get("cause") else ""), ""]
    refs = result["references_valides"]
    if refs:
        lines += ["| Réf. | Titre | Organisme | Consultée le | Publiée ou mise à jour | Question | Limites |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {r['id']} | [{r['titre']}]({r['url']}) | {r.get('auteur_organisme', '')} | {r.get('date_consultation', '')} | {r.get('date_publication_ou_maj') or 'non indiquée'} | {r.get('question_etudiee', '')} | {r.get('limites_transposition', '')} |" for r in refs]
    comparisons = report.get("comparaisons", [])
    if comparisons:
        lines += ["", "| Réf. | Observation | Principe | Écart | Adaptation | Bénéfice | Nature |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {c.get('ref')} | {c.get('observation', '')} | {c.get('principe', '')} | {c.get('ecart', '')} | {c.get('adaptation', '')} | {c.get('benefice', '')} | {c.get('nature', '')} |" for c in comparisons]
    lines += ["", "## Couverture", "", "| Statut | Contrôles |", "|---|---|"]
    lines += [f"| {s} | {', '.join(ids) or '-'} |" for s, ids in by_status.items()]
    coverage = read_json(run / (report.get("coverage") or "coverage.json"), {}) or {}
    lines += ["", f"Combinaisons exécutées : {len(coverage.get('executees', []))} ; exclues : {len(coverage.get('exclues', []))}."]
    for excluded in coverage.get("exclues", [])[:30]:
        if isinstance(excluded, dict):
            lines.append(f"- Exclu : {excluded.get('combinaison')} ; raison : {excluded.get('raison')} ; risque : {excluded.get('risque')}")
    non_verified = [c for c in controls if c.get("statut") == "non_verifie"]
    if non_verified:
        lines += ["", "Non vérifiés :"]
        lines += [f"- {c['id']} ({c.get('raison_type')}) : {c.get('raison')}" for c in non_verified]
    lines += ["", "## Défauts", ""]
    order = {"critique": 0, "majeure": 1, "moderee": 2, "mineure": 3}
    for d in sorted(defects, key=lambda x: (order.get(x.get("severite"), 9), x.get("id", ""))):
        lines += [
            f"### {d.get('id')} : {d.get('titre')}",
            "",
            f"- Contrôle : {d.get('controle')} ; écran ou composant : {d.get('ecran_composant', '')}",
            f"- Sévérité : {d.get('severite')} ; priorité : {d.get('priorite')} ; confiance : {d.get('confiance')} ; effort : {d.get('effort', '')} ; nature : [{d.get('nature')}]",
            f"- Statut : {d.get('statut')}" + (" (régression introduite par une correction)" if d.get("introduit_par_correction") else ""),
            f"- Préconditions : {d.get('preconditions', '')} ; données : {d.get('donnees', '')} ; configuration : {d.get('config_id', '')}",
            "- Étapes : " + " ; ".join(d.get("etapes", [])),
            f"- Attendu : {d.get('attendu')}",
            f"- Observé : {d.get('observe')}",
            f"- Interprétation : {d.get('interpretation', '')}",
            "- Preuves : " + ", ".join(d.get("preuves", [])),
        ]
        if d.get("retest"):
            lines.append(f"- Retest : {d['retest'].get('statut')} ({', '.join(d['retest'].get('preuves', []))})")
        if d.get("exception"):
            e = d["exception"]
            lines.append(f"- Exception acceptée par {e.get('acceptee_par')} le {e.get('date')} : « {e.get('citation')} » ; échéance {e.get('echeance', 'non fixée')}")
        if d.get("cause_blocage"):
            lines.append(f"- Non résolu : {d.get('cause_blocage')} ; action requise : {d.get('action_requise')}")
        lines.append("")
    if not defects:
        lines += ["Aucun défaut consigné.", ""]
    variants = report.get("variantes", [])
    if variants:
        lines += ["## Variantes", "", "```json", json.dumps(variants, ensure_ascii=False, indent=2), "```", ""]
    corrections = report.get("corrections", [])
    lines += ["## Corrections", ""]
    if corrections:
        lines += ["| Défauts | Cause | Solution | Type | Fichiers | Instances revérifiées |", "|---|---|---|---|---|---|"]
        lines += [f"| {', '.join(c.get('defauts', []))} | {c.get('cause_probable', '')} | {c.get('solution', '')} | {c.get('type', '')} | {', '.join(c.get('fichiers', []))} | {c.get('instances_reverifiees', '')} |" for c in corrections]
    else:
        lines.append("Aucune.")
    lines += ["", "## Avant / après", ""]
    pairs = report.get("avant_apres", [])
    if pairs:
        lines += ["| Configuration | Avant | Après | Diff | Commentaire |", "|---|---|---|---|---|"]
        lines += [f"| {p.get('config_id', '')} | {p.get('avant', '')} | {p.get('apres', '')} | {p.get('diff', '')} | {p.get('commentaire', '')} |" for p in pairs]
    else:
        lines.append("Aucune paire.")
    lines += ["", "## Régressions", "", bullet([f"{r.get('controle')} : {r.get('resultat')}" for r in report.get("regressions", [])]), ""]
    lines += ["## Limites et vérifications humaines", "", bullet(report.get("limites", []) + result["verifications_humaines"] + report.get("verifications_humaines", [])), ""]
    if result["warnings"]:
        lines += ["## Avertissements du vérificateur", "", bullet(result["warnings"]), ""]
    lines += [f"_Rapport généré le {now_iso()} par verify_report.py._", ""]
    (run / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return str(run / "report.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    parser.add_argument("--apply", action="store_true", help="Écrire la décision calculée si le reste est cohérent")
    parser.add_argument("--render", action="store_true", help="Produire report.md")
    args = parser.parse_args()

    result = verify(args.run)
    if result["status"] == "missing":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(2)
    run = Path(args.run)
    if args.apply:
        decision_errors = [e for e in result["errors"] if e.startswith("decision")]
        other_errors = [e for e in result["errors"] if not e.startswith("decision")]
        if not other_errors:
            report = read_json(run / "report.json")
            report["decision"] = result["decision_calculee"]
            report["verifie_le"] = now_iso()
            write_json(run / "report.json", report)
            result = verify(args.run)
            result["applied"] = True
        else:
            result["applied"] = False
            result["apply_refused"] = "incohérences à corriger avant d'écrire la décision"
            if decision_errors:
                result["errors"] = other_errors + decision_errors
    if args.render:
        result["report_md"] = render(run, read_json(run / "report.json"), result)
    output = {k: v for k, v in result.items() if k not in ("defauts", "references_valides")}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
