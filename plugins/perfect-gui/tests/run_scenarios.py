#!/usr/bin/env python3
"""Scénarios d'acceptation du skill ui-audit-gate.

Sert l'application de test (tests/fixture-app) avec des défauts injectables (?scn=01,03),
lance les scripts du skill et vérifie qu'ils détectent chaque défaut, sans faux positif sur la
version saine. Vérifie aussi la barrière de décision, le journal de recherche, le hook et l'analyse d'impact.

Usage : python3 tests/run_scenarios.py [--only SCN-03,SCN-11] [--keep]
Prérequis : Playwright et Pillow (scripts/setup.sh), un navigateur Chromium ou Chrome.
"""
import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = TESTS_DIR.parent
SCRIPTS = PLUGIN_DIR / "skills" / "ui-audit-gate" / "scripts"
HOOK = PLUGIN_DIR / "hooks" / "gate_hook.py"
FUNDAMENTALS = json.loads((PLUGIN_DIR / "skills" / "ui-audit-gate" / "config" / "levels.json").read_text(encoding="utf-8"))["fondamentaux"]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Harness:
    def __init__(self, work):
        self.work = Path(work)
        handler = functools.partial(QuietHandler, directory=str(TESTS_DIR / "fixture-app"))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/index.html"

    def url(self, scenario=None):
        return f"{self.base}?scn={scenario}" if scenario else self.base

    def script(self, name, *args, env=None, stdin=None):
        command = [sys.executable, str(SCRIPTS / name), *map(str, args)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, env={**os.environ, **(env or {})}, input=stdin)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = {"raw_stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}
        return result.returncode, data

    def inspect(self, out, scenario=None, viewports="laptop", *extra):
        code, data = self.script("inspect_page.py", "--url", self.url(scenario), "--viewports", viewports, "--out", self.work / out, "--no-axe", *extra)
        if code != 0:
            raise AssertionError(f"inspect_page code {code} : {json.dumps(data, ensure_ascii=False)[:600]}")
        reports = [json.loads(Path(c["report"]).read_text(encoding="utf-8")) for c in data["configs"]]
        return reports

    def keyboard(self, out, scenario=None, viewports="laptop"):
        code, data = self.script("keyboard_walk.py", "--url", self.url(scenario), "--viewports", viewports, "--out", self.work / out)
        if code != 0:
            raise AssertionError(f"keyboard_walk code {code} : {data}")
        return [json.loads(Path(c["report"]).read_text(encoding="utf-8")) for c in data["configs"]]

    def resize(self, scenario, *args):
        code, data = self.script("resize_probe.py", "--url", self.url(scenario), *args)
        if code != 0:
            raise AssertionError(f"resize_probe code {code} : {data}")
        return data["configs"][0]


def check(report, name):
    return report["checks"][name]


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def make_run(h, name, **overrides):
    root = h.work / name
    root.mkdir(parents=True, exist_ok=True)
    code, data = h.script("init_run.py", "--slug", name, "--root", root, "--no-gitignore")
    expect(code == 0, f"init_run a échoué : {data}")
    run = Path(data["run"])
    evidence = run / "inspect" / "preuve.json"
    evidence.write_text("{}", encoding="utf-8")
    for folder in ("before", "after-fix-1", "after"):
        (run / folder).mkdir(exist_ok=True)
        (run / folder / "page.png").write_bytes(b"png")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["controles"] = [{"id": cid, "statut": "reussi", "preuves": ["inspect/preuve.json"]} for cid in FUNDAMENTALS]
    report["avant_apres"] = [{"config_id": "laptop", "avant": "before/page.png", "apres": "after/page.png"}]
    report["recherche"] = {"statut": "non_realisee", "cause": "test"}
    report.update(overrides)
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return run


def add_valid_reference(h, run):
    url = "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html"
    h.script("research_log.py", run, "query", "--text", "WCAG 2.2 target size minimum understanding", "--tool", "WebSearch", "--urls", url)
    h.script("research_log.py", run, "visit", "--url", url, "--tool", "WebFetch")
    code, data = h.script("research_log.py", run, "ref", "--json", json.dumps({
        "titre": "Understanding SC 2.5.8", "url": url, "auteur_organisme": "W3C WAI", "statut_consultation": "consultee",
        "rang_source": 1, "question_etudiee": "Taille des cibles", "limites_transposition": "AA",
    }))
    expect(code == 0, f"ref refusée : {data}")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["recherche"] = {"statut": "realisee", "cause": None}
    report["comparaisons"] = [{"ref": data["id"], "observation": "o", "principe": "p", "ecart": "e", "adaptation": "a", "benefice": "b", "nature": "EXIGENCE"}]
    (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def verify(h, run, *flags):
    code, data = h.script("verify_report.py", run, *flags)
    return code, data


def defect(**fields):
    base = {"id": "DEF-001", "titre": "t", "controle": "GEO-02", "severite": "mineure", "priorite": "P3", "confiance": "moyenne",
            "nature": "PREFERENCE", "statut": "ouvert", "attendu": "a", "observe": "o", "preuves": ["inspect/preuve.json"]}
    base.update(fields)
    return base


def scn_base(h):
    reports = h.inspect("base", None, "P0", "--scan-scroll")
    noisy = ["horizontal-overflow", "text-overflow", "occlusion", "target-size", "alignment", "contrast", "form-labels",
             "accessible-names", "form-errors", "images", "headings", "document", "landmarks", "console"]
    for report in reports:
        bad = {n: check(report, n)["items"][:2] for n in noisy if check(report, n)["result"] != "clean"}
        expect(not bad, f"faux positifs sur la version saine ({report['config_id']}) : {json.dumps(bad, ensure_ascii=False)[:800]}")
        expect(not check(report, "target-size")["warnings"], f"avertissements de cible inattendus : {check(report, 'target-size')['warnings'][:2]}")
    keyboard = h.keyboard("base-kb")[0]
    expect(keyboard["outcome"] == "cycle-complet" and keyboard["result"] == "clean", f"clavier version saine : {keyboard['outcome']} {keyboard['issues']}")
    return f"{len(reports)} configurations propres, {keyboard['focusables']} éléments focalisables parcourus"


def scn_01(h):
    report = h.inspect("scn01", "01", "laptop", "--only", "alignment")[0]
    items = check(report, "alignment")["items"]
    expect(any(i["selector"] == "#share-button" and i["ecart_px"] >= 5 for i in items), f"bouton décalé non détecté : {items}")
    return f"#share-button décalé de {next(i['ecart_px'] for i in items if i['selector'] == '#share-button')} px"


def scn_02(h):
    report = h.inspect("scn02", "02", "mobile-narrow", "--only", "text-overflow")[0]
    items = check(report, "text-overflow")["items"]
    hit = [i for i in items if i["selector"] == "#submit-booking"]
    expect(hit and hit[0]["kind"] == "rogne", f"texte rogné non détecté : {items}")
    return f"libellé rogné ({hit[0]['metrics']['scrollWidth']} > {hit[0]['metrics']['clientWidth']} px)"


def scn_03(h):
    report = h.inspect("scn03", "03", "mobile", "--only", "occlusion", "--scan-scroll")[0]
    items = check(report, "occlusion")["items"]
    pay = [i for i in items if i["selector"] == "#pay-button"]
    expect(pay and pay[0]["state"] == "masque-a-toutes-les-positions", f"superposition non détectée : {items}")
    expect(check(report, "occlusion")["result"] == "issues", "résultat attendu : issues")
    return f"#pay-button masqué par {pay[0]['occluders']}"


def scn_04(h):
    broken = h.inspect("scn04", "04", "767x900,768x900", "--only", "horizontal-overflow")
    by_width = {r["viewport"]["width"]: check(r, "horizontal-overflow") for r in broken}
    expect(by_width[767]["result"] == "issues" and by_width[767]["causes_page_scroll"], f"régression à 767 px non détectée : {by_width[767]}")
    expect(by_width[768]["result"] == "clean", f"faux positif à 768 px : {by_width[768]['items'][:2]}")
    healthy = check(h.inspect("scn04-base", None, "767x900", "--only", "horizontal-overflow")[0], "horizontal-overflow")
    expect(healthy["result"] == "clean", "faux positif sur la version saine à 767 px")
    return f"débordement de {by_width[767]['page_scroll_width'] - by_width[767]['viewport_width']} px à 767, rien à 768"


def scn_05(h):
    report = h.keyboard("scn05", "05")[0]
    traps = [i for i in report["issues"] if i["kind"] == "piege-de-focus"]
    expect(traps, f"piège non détecté : {report['outcome']} {report['issues']}")
    return f"boucle sur {traps[0]['boucle']}"


def scn_06(h):
    submit = json.dumps([{"click": "#submit-booking"}])
    broken = check(h.inspect("scn06", "06", "laptop", "--only", "form-errors", "--actions", submit)[0], "form-errors")
    expect(broken["result"] == "issues" and any(i["kind"] == "message-non-lie-et-non-annonce" for i in broken["items"]), f"erreur mal signalée non détectée : {broken}")
    healthy = check(h.inspect("scn06-base", None, "laptop", "--only", "form-errors", "--actions", submit)[0], "form-errors")
    expect(healthy["result"] == "clean" and healthy["invalid_fields"] == 1, f"version saine : {healthy}")
    return "message « Erreur » non lié ni annoncé ; version saine conforme"


def scn_07(h):
    plain = check(h.inspect("scn07", "07", "laptop", "--only", "text-overflow")[0], "text-overflow")
    expect(plain["result"] == "clean", f"les libellés français devraient tenir : {plain['items'][:2]}")
    pseudo = check(h.inspect("scn07-pseudo", "07", "laptop", "--only", "text-overflow", "--pseudo")[0], "text-overflow")
    tabs = [i for i in pseudo["items"] if "tab" in i["selector"]]
    expect(tabs, f"débordement en traduction longue non détecté : {pseudo['items'][:3]}")
    healthy = check(h.inspect("scn07-base", None, "laptop", "--only", "text-overflow", "--pseudo")[0], "text-overflow")
    expect(healthy["result"] == "clean", f"faux positif en pseudo-locale sur la version saine : {healthy['items'][:2]}")
    return f"{len(tabs)} onglets rognés en pseudo-locale"


def scn_08(h):
    broken = check(h.inspect("scn08", "08", "mobile", "--only", "target-size")[0], "target-size")
    flagged = broken["items"] + broken["warnings"]
    expect(any("btn" in i["selector"] or i["selector"].startswith("#") for i in flagged), f"cibles réduites non signalées : {broken}")
    for folder, scenario in (("before", None), ("after", "08")):
        code, data = h.script("capture.py", "--url", h.url(scenario), "--viewports", "mobile", "--out", h.work / "scn08-diff" / folder, "--name", "page")
        expect(code == 0, f"capture impossible : {data}")
    code, diff = h.script("visual_diff.py", "--before", h.work / "scn08-diff" / "before", "--after", h.work / "scn08-diff" / "after", "--out", h.work / "scn08-diff" / "diff")
    expect(code == 0 and diff["result"] == "issues", f"diff visuel sans différence : {diff}")
    return f"{len(flagged)} cibles signalées, diff visuel : {diff['items'][0]['status']}"


def scn_09(h):
    broken = h.resize("09", "--mode", "state", "--viewports", "laptop", "--widths", "current,600,current")
    lost = [i for i in broken["issues"] if i["kind"] == "valeurs-perdues"]
    expect(lost, f"perte d'état non détectée : {broken['issues']}")
    healthy = h.resize(None, "--mode", "state", "--viewports", "laptop", "--widths", "current,600,current")
    expect(healthy["result"] == "clean", f"faux positif : {healthy['issues']}")
    return f"valeurs perdues à {lost[0]['width']} px : {[i['selector'] for i in lost[0]['items']]}"


def scn_10(h):
    args = ["--mode", "keyboard", "--viewports", "mobile", "--field", "#email", "--action", "#submit-booking"]
    broken = h.resize("10", *args)
    expect(any(i["kind"] == "action-atteignable-seulement-par-script" for i in broken["issues"]), f"clavier virtuel : {broken}")
    healthy = h.resize(None, *args)
    expect(healthy["result"] == "clean", f"faux positif : {healthy['issues']}")
    return "action cachée dans un conteneur overflow:hidden quand le clavier réduit la hauteur"


def scn_11(h):
    run = make_run(h, "scn11")
    code, data = verify(h, run, "--apply", "--render")
    expect(code == 0 and data["decision_calculee"] == "VALIDEE_PERIMETRE_TESTE", f"décision attendue VALIDEE_PERIMETRE_TESTE : {data}")
    expect((run / "report.md").exists(), "report.md absent")
    code, logged = h.script("research_log.py", run, "unavailable", "--cause", "outil absent")
    expect(code == 0, "journal unavailable")
    return "Web indisponible : décision plafonnée à VALIDEE_PERIMETRE_TESTE"


def scn_12(h):
    code, data = h.script("capture.py", "--url", h.url(), "--viewports", "laptop", "--out", h.work / "scn12", "--browser-path", "/nonexistent/browser")
    expect(code == 3 and data.get("status") == "capability-missing", f"échec de capture mal signalé : code {code} {data}")
    expect(not list((h.work / "scn12").rglob("*.png")), "aucune capture ne devait exister")
    run = make_run(h, "scn12", avant_apres=[])
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    for control in report["controles"]:
        if control["id"] in ("GEO-02", "CTA-02"):
            control.update({"statut": "non_verifie", "raison": "capture impossible", "raison_type": "technique", "preuves": []})
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run, "--apply")
    expect(data["decision_calculee"] == "NON_VALIDEE" and any(b.startswith("B5") for b in data["bloquants"]), f"B5 attendu : {data}")
    return "capture impossible : capability-missing, puis NON_VALIDEE (B5)"


def scn_13(h):
    run = make_run(h, "scn13")
    code, data = h.script("research_log.py", run, "ref", "--json", json.dumps({
        "titre": "Inventée", "url": "https://example.org/jamais-vue", "auteur_organisme": "?", "statut_consultation": "consultee",
        "rang_source": 1, "question_etudiee": "?", "limites_transposition": "?",
    }))
    expect(code == 1 and data["status"] == "refused", f"référence non vue acceptée : {data}")
    (run / "research" / "references.json").write_text(json.dumps([{"id": "REF-001", "titre": "x", "url": "https://example.org/jamais-vue", "statut_consultation": "consultee"}]), encoding="utf-8")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["recherche"] = {"statut": "realisee"}
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run)
    expect(code == 1 and any("non tracée" in e for e in data["errors"]), f"référence fabriquée non détectée : {data}")
    code, data = h.script("research_log.py", run, "query", "--text", "erreur formulaire pour jean.dupont@acme-interne.fr sur localhost")
    expect(code == 1 and data["status"] == "refused", "requête sensible acceptée")
    return "référence non vue refusée, rapport invalide, requête sensible refusée"


def scn_14(h):
    run = make_run(h, "scn14", defauts=[defect()])
    add_valid_reference(h, run)
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["controles"].append({"id": "ACC-11", "statut": "non_verifie", "raison": "pas de lecteur d'écran", "raison_type": "humain"})
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run, "--apply", "--render")
    expect(code == 0 and data["decision_calculee"] == "VALIDEE_PROTOCOLE_COMPLET", f"préférence ne doit pas bloquer : {data}")
    expect(data["verifications_humaines"], "ACC-11 doit être listé en vérification humaine")
    return "préférence mineure non bloquante ; ACC-11 listé pour un humain"


def scn_gate_rules(h):
    run = make_run(h, "rules-critical", defauts=[defect(severite="critique", nature="EXIGENCE", controle="STK-01")])
    code, data = verify(h, run, "--apply")
    expect(data["decision_calculee"] == "NON_VALIDEE", f"critique : {data['decision_calculee']}")
    exception = {"acceptee_par": "utilisateur", "date": "2026-10-11", "citation": "on livre quand même, je corrigerai demain"}
    run = make_run(h, "rules-exception", defauts=[defect(severite="majeure", nature="EXIGENCE", statut="accepte_exception", exception=exception)])
    add_valid_reference(h, run)
    code, data = verify(h, run, "--apply")
    expect(data["decision_calculee"] == "VALIDEE_AVEC_EXCEPTIONS", f"exception : {data['decision_calculee']} {data['errors']}")
    run = make_run(h, "rules-mock", mode="maquette")
    code, data = verify(h, run, "--apply")
    expect(data["decision_calculee"] == "VALIDATION_LIMITEE", f"maquette : {data['decision_calculee']}")
    run = make_run(h, "rules-fix", corrections=[{"defauts": ["DEF-001"]}])
    code, data = verify(h, run, "--apply")
    expect(any("after-fix" in b for b in data["bloquants"]), f"recapture après correction exigée : {data['bloquants']}")
    run = make_run(h, "rules-fake-pass")
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    report["controles"][0]["preuves"] = ["inspect/inexistant.png"]
    report["decision"] = "VALIDEE_PROTOCOLE_COMPLET"
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    code, data = verify(h, run)
    expect(code == 1 and any("preuve introuvable" in e for e in data["errors"]), "réussite sans preuve acceptée")
    expect(any("différente de la décision calculée" in e for e in data["errors"]), "décision surévaluée acceptée")
    return "critique, exception, maquette, recapture, preuve absente, décision surévaluée"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def scn_hook(h):
    repo = h.work / "hook-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "app.css").write_text("body{color:#000}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "app.css").write_text("body{color:#111}\n")

    def hook(extra=None, env=None):
        payload = json.dumps({"cwd": str(repo), "stop_hook_active": False, **(extra or {})})
        result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, env={**os.environ, **(env or {})}, timeout=60)
        return json.loads(result.stdout) if result.stdout.strip() else None

    blocked = hook()
    expect(blocked and blocked.get("decision") == "block", f"le hook devait bloquer : {blocked}")
    again = hook({"stop_hook_active": True})
    expect(again and "systemMessage" in again and "decision" not in again, f"pas de second blocage : {again}")
    expect(hook(env={"UI_AUDIT_GATE": "off"}) is None, "UI_AUDIT_GATE=off doit désactiver")
    time.sleep(1.1)
    code, data = h.script("init_run.py", "--slug", "hook", "--root", repo)
    run = Path(data["run"])
    (run / "inspect" / "preuve.json").write_text("{}")
    (run / "after").mkdir(exist_ok=True)
    (run / "after" / "page.png").write_bytes(b"png")
    report = json.loads((run / "report.json").read_text())
    report["controles"] = [{"id": cid, "statut": "reussi", "preuves": ["inspect/preuve.json"]} for cid in FUNDAMENTALS]
    report["avant_apres"] = [{"apres": "after/page.png"}]
    report["recherche"] = {"statut": "non_realisee", "cause": "test"}
    (run / "report.json").write_text(json.dumps(report))
    still = hook()
    expect(still and still.get("decision") == "block", "rapport sans décision : le hook doit encore bloquer")
    h.script("verify_report.py", run, "--apply")
    expect(hook() is None, f"rapport cohérent : le hook doit laisser passer ({hook()})")
    return "bloque, ne bloque pas deux fois, se désactive, laisse passer après un rapport cohérent"


def scn_impact(h):
    repo = h.work / "impact-repo"
    (repo / "src" / "components" / "ui").mkdir(parents=True)
    (repo / "src" / "pages").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    (repo / "src" / "tokens.css").write_text(":root { --space-btn: 16px; }\n")
    (repo / "src" / "components" / "ui" / "Button.tsx").write_text("export const Button = () => <button style={{padding: 'var(--space-btn)'}} />;\n")
    (repo / "src" / "pages" / "Home.tsx").write_text("import { Button } from '../components/ui/Button';\nexport default () => <Button />;\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "src" / "tokens.css").write_text(":root { --space-btn: 8px; }\n")
    code, data = h.script("impact_scan.py", "--root", repo)
    expect(code == 0 and data["niveau_suggere"] == "N3", f"niveau attendu N3 : {data.get('niveau_suggere')} {data.get('raisons')}")
    expect("src/components/ui/Button.tsx" in data["zones_impactees"], f"propagation du token manquante : {data['zones_impactees']}")
    return "token modifié : N3, Button.tsx détecté comme consommateur"


def scn_pseudo(h):
    source = h.work / "fr.json"
    source.write_text(json.dumps({"hello": "Bonjour {name}", "nested": {"count": "%d éléments"}}), encoding="utf-8")
    target = h.work / "pseudo.json"
    code, data = h.script("pseudo_locale.py", source, target)
    out = json.loads(target.read_text(encoding="utf-8"))
    expect(code == 0 and "{name}" in out["hello"] and out["hello"].startswith("[") and "%d" in out["nested"]["count"], f"pseudo-locale : {out}")
    return out["hello"]


SCENARIOS = [
    ("BASE", "Version saine sans faux positif", scn_base),
    ("SCN-01", "Bouton décalé", scn_01),
    ("SCN-02", "Texte dépassant d'un bouton", scn_02),
    ("SCN-03", "Superposition masquant une action", scn_03),
    ("SCN-04", "Régression responsive", scn_04),
    ("SCN-05", "Focus piégé", scn_05),
    ("SCN-06", "Erreur de formulaire mal signalée", scn_06),
    ("SCN-07", "Contenu traduit trop long", scn_07),
    ("SCN-08", "Correction introduisant une régression", scn_08),
    ("SCN-09", "Redimensionnement perdant l'état", scn_09),
    ("SCN-10", "Clavier virtuel masquant une action", scn_10),
    ("SCN-11", "Web indisponible", scn_11),
    ("SCN-12", "Capture impossible", scn_12),
    ("SCN-13", "Référence fabriquée et requête sensible", scn_13),
    ("SCN-14", "Préférence esthétique non bloquante", scn_14),
    ("GATE", "Règles de décision", scn_gate_rules),
    ("HOOK", "Hook Stop", scn_hook),
    ("IMPACT", "Analyse d'impact", scn_impact),
    ("PSEUDO", "Pseudo-localisation de fichier", scn_pseudo),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    wanted = set(args.only.split(",")) if args.only else None
    work = Path(tempfile.mkdtemp(prefix="ui-audit-tests-"))
    harness = Harness(work)
    failures = 0
    for sid, title, func in SCENARIOS:
        if wanted and sid not in wanted:
            continue
        started = time.time()
        try:
            detail = func(harness)
            status = "OK"
        except Exception as exc:
            failures += 1
            status = "ÉCHEC"
            detail = str(exc) if isinstance(exc, AssertionError) else traceback.format_exc(limit=3)
        print(f"{status:5} {sid:7} {title} ({time.time() - started:.1f} s)\n      {detail}", flush=True)
    harness.server.shutdown()
    if args.keep or failures:
        print(f"\nArtefacts : {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    print(f"\n{'Tous les scénarios passent' if not failures else f'{failures} scénario(s) en échec'}.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
