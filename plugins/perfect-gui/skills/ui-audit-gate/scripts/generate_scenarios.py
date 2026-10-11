#!/usr/bin/env python3
"""Génère la suite de scènes à partir de site-map.json : tout ce qu'un utilisateur peut faire,
une scène par action, option, paramètre ou réglage, plus les variantes d'environnement.

Les identifiants (S-0001...) restent stables entre deux générations : une scène existante garde son
numéro, les nouvelles sont ajoutées, celles qui ont disparu sont listées comme retirées.

Exemples :
  python3 generate_scenarios.py --site-map ui-scenes/site-map.json --out ui-scenes/scenes.json
  python3 generate_scenarios.py --site-map ui-scenes/site-map.json --out ui-scenes/scenes.json --export-playwright tests/ui-scenes.spec.ts
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

from _common import load_config, now_iso, read_json, write_json

EDGE = load_config("fixtures/edge-text.json")
CATEGORY_ORDER = ["page", "controle", "bascule", "onglet", "menu", "liste", "case", "radio", "curseur",
                  "formulaire", "parametre-url", "reglage", "environnement"]
NAME_HINTS = [
    (r"(pr[ée]nom|first)", "Camille"), (r"(nom|name|last)", "Camille Martin"), (r"(ville|city)", "Lyon"),
    (r"(code ?postal|zip|postcode)", "69001"), (r"(adresse|address|rue|street)", "12 rue de la République"),
    (r"(soci[ée]t[ée]|company|entreprise)", "Exemple SARL"), (r"(pays|country)", "France"),
    (r"(message|comment|description|bio)", "Message de test de l'audit UI."), (r"(search|recherche|q$|query)", "test"),
]


def path_of(url):
    parsed = urlparse(url)
    return (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")


def valid_value(field):
    kind = field["type"]
    label = f"{field.get('name') or ''} {field.get('label') or ''}".lower()
    if kind == "email":
        return "test.ui@example.com"
    if kind == "tel":
        return "+33123456789"
    if kind == "url":
        return "https://example.com"
    if kind == "password":
        return "Uiag-Test-2026!"
    if kind == "number":
        low = float(field["min"]) if field.get("min") not in (None, "") else 1
        return str(int(low) if low.is_integer() else low)
    if kind == "date":
        return "2026-01-15"
    if kind == "time":
        return "10:30"
    if kind == "datetime-local":
        return "2026-01-15T10:30"
    if kind == "month":
        return "2026-01"
    if kind == "color":
        return "#336699"
    for pattern, value in NAME_HINTS:
        if re.search(pattern, label):
            return value
    return "Texte de test"


def invalid_value(field):
    kind = field["type"]
    if kind == "email":
        return "pas-un-email"
    if kind == "url":
        return "pas une url"
    if kind == "tel":
        return "abc"
    if kind == "number":
        if field.get("max") not in (None, ""):
            return str(float(field["max"]) + 1).rstrip("0").rstrip(".")
        return "-1"
    if field.get("pattern"):
        return "!!!"
    if field.get("minlength"):
        return "a"
    return None


def long_value(field):
    if field["type"] == "email":
        return EDGE["email_long"]
    if field["type"] in ("number", "date", "time", "datetime-local", "month", "color", "range"):
        return None
    if field.get("maxlength"):
        return ("Donaudampfschiff" * 20)[: field["maxlength"] + 5]
    return EDGE["long_de"] + " " + EDGE["mot_sans_espace"]


def fill_actions(fields, mode):
    actions = []
    for field in fields:
        if not field.get("visible", True):
            continue
        if field["tag"] == "select":
            options = [o for o in field.get("options") or [] if o["value"] != ""]
            if mode != "vide" and options:
                actions.append({"select": [field["selector"], options[0]["value"]]})
            continue
        if field["type"] in ("checkbox", "radio"):
            if mode != "vide" and field.get("required"):
                actions.append({"check": field["selector"]})
            continue
        if field["type"] in ("file", "range", "hidden"):
            continue
        if mode == "vide":
            actions.append({"fill": [field["selector"], ""]})
            continue
        value = valid_value(field)
        if mode == "invalide":
            value = invalid_value(field) or value
        if mode == "long":
            value = long_value(field) or value
        actions.append({"fill": [field["selector"], value]})
    return actions


class SceneBook:
    def __init__(self, previous):
        self.previous = {s["key"]: s["id"] for s in previous.get("scenes", [])}
        self.next_number = max([int(s["id"].split("-")[1]) for s in previous.get("scenes", [])] or [0]) + 1
        self.scenes = []
        self.skipped = []
        self.keys = set()

    def add(self, category, title, page, actions, risk="sur", environment=None, checks=None, key_extra=""):
        key_source = json.dumps([category, page, key_extra or actions, environment or {}], ensure_ascii=False, sort_keys=True)
        key = hashlib.sha1(key_source.encode("utf-8")).hexdigest()[:16]
        if key in self.keys:
            return
        self.keys.add(key)
        scene_id = self.previous.get(key)
        if not scene_id:
            scene_id = f"S-{self.next_number:04d}"
            self.next_number += 1
        self.scenes.append({
            "id": scene_id, "key": key, "categorie": category, "titre": title, "page": page,
            "risque": risk, "environnement": environment or {}, "actions": actions, "verifie": checks or ["rendu"],
        })

    def skip(self, what, reason):
        self.skipped.append({"element": what, "raison": reason})


def build(site_map, args):
    previous = read_json(args.out, {}) or {}
    book = SceneBook(previous)
    pages = [p for p in site_map["pages"] if not p.get("error") and not p.get("acces_bloque")]
    for blocked_page in site_map.get("pages_bloquees", []):
        book.skip(blocked_page["url"], f"page refusée à l'exploration : {blocked_page['raison']}")
    explored_paths = set()
    for found in pages:
        page = path_of(found["url"])
        goto = {"goto": page}
        book.add("page", f"Chargement de {page}", page, [goto, {"snapshot": "chargement"}], checks=["rendu", "console"])
        bare_path = urlparse(found["url"]).path
        if bare_path in explored_paths:
            continue
        explored_paths.add(bare_path)

        for control in found.get("controls", []):
            name = control["name"] or control["selector"]
            prerequisites = control.get("prerequis", [])
            label = f"« {name[:50]} » ({control['kind']}) sur {page}"
            if control["risk"] in ("destructif", "telechargement"):
                book.skip(label, f"risque {control['risk']} : à tester dans un environnement de test avec --allow-mutations")
                continue
            if control["kind"] in ("champ", "fichier"):
                continue
            if not control.get("visible", True) and not prerequisites:
                book.skip(label, "élément caché qu'aucune interaction explorée ne révèle (menu au survol, état particulier)")
                continue
            base = [goto, *prerequisites]
            if control["kind"] == "bascule":
                popup = control.get("haspopup") not in (None, "", "false")
                closing = [{"press": "Escape"}, {"snapshot": "ferme-par-echap"}] if popup else [{"click_optional": control["selector"]}, {"snapshot": "referme"}]
                book.add("bascule", f"Ouvrir puis fermer {label}", page,
                         base + [{"click_effect": control["selector"]}, {"snapshot": "ouvert"}, *closing],
                         checks=["rendu", "effet", "fermeture", "defilement"])
            elif control["kind"] == "onglet":
                book.add("onglet", f"Activer l'onglet {label}", page, base + [{"click_effect": control["selector"]}, {"snapshot": "onglet-actif"}], checks=["rendu", "effet"])
            elif control["kind"] == "element-menu":
                book.add("menu", f"Choisir {label}", page, base + [{"click_effect": control["selector"]}, {"snapshot": "apres-choix"}], checks=["rendu", "effet"])
            elif control["kind"] == "liste" and control.get("field"):
                options = [o for o in control["field"].get("options") or [] if o["value"] != ""]
                chosen = options if len(options) <= args.max_options else options[:2] + [options[len(options) // 2]] + options[-1:]
                if len(options) > args.max_options:
                    book.skip(label, f"{len(options)} options : échantillon de {len(chosen)} (premières, milieu, dernière)")
                for option in chosen:
                    category = "reglage" if control.get("setting") else "liste"
                    book.add(category, f"Option « {option['label'][:40]} » de {label}", page,
                             base + [{"select": [control["selector"], option["value"]]}, {"wait": 300}, {"snapshot": f"option-{option['value'][:20]}"}],
                             checks=["rendu", "coherence"], key_extra=f"{control['selector']}={option['value']}")
            elif control["kind"] in ("case", "interrupteur"):
                category = "reglage" if control.get("setting") else "case"
                book.add(category, f"Cocher et décocher {label}", page,
                         base + [{"click_effect": control["selector"]}, {"snapshot": "active"}, {"click_optional": control["selector"]}, {"snapshot": "desactive"}],
                         checks=["rendu", "effet", "coherence"])
            elif control["kind"] == "radio":
                category = "reglage" if control.get("setting") else "radio"
                book.add(category, f"Choisir {label}", page, base + [{"click": control["selector"]}, {"wait": 300}, {"snapshot": "choisi"}], checks=["rendu", "coherence"])
            elif control["kind"] == "curseur":
                field = control.get("field") or {}
                for bound in ("min", "max"):
                    if field.get(bound) not in (None, ""):
                        book.add("curseur", f"Curseur {label} à {bound}", page,
                                 base + [{"fill": [control["selector"], field[bound]]}, {"snapshot": f"curseur-{bound}"}], checks=["rendu"], key_extra=f"{control['selector']}:{bound}")
            elif control["kind"] in ("action", "ancre", "option", "reinitialisation"):
                category = "reglage" if control.get("setting") else "controle"
                book.add(category, f"Activer {label}", page, base + [{"click_effect": control["selector"]}, {"snapshot": "apres-action"}], checks=["rendu", "effet", "coherence"])

        for form in found.get("forms", []):
            if not form.get("fields") and not form.get("submit"):
                continue
            label = f"formulaire « {(form['name'] or form['selector'])[:40]} » sur {page}"
            if not form.get("visible", True) and not form.get("prerequis"):
                book.skip(label, "formulaire caché qu'aucune interaction explorée ne révèle")
                continue
            base = [goto, *form.get("prerequis", [])]
            risk = "mutation" if form["risk"] in ("mutation", "destructif") else "sur"
            if form["risk"] == "destructif" and not args.allow_destructive:
                book.skip(label, "formulaire destructif : scènes de saisie seulement, sans soumission")
            submit = [{"click": form["submit"]}] if form.get("submit") and (form["risk"] != "destructif" or args.allow_destructive) else [{"press": "Enter"}] if form["risk"] != "destructif" else []
            for mode, title in (("vide", "envoi vide"), ("invalide", "valeurs invalides"), ("valide", "valeurs valides"), ("long", "contenus très longs")):
                actions = base + fill_actions(form["fields"], mode)
                if mode == "long":
                    actions += [{"snapshot": "saisie-longue"}]
                actions += submit + [{"wait": 400}, {"snapshot": f"apres-envoi-{mode}"}]
                book.add("formulaire", f"{label} : {title}", page, actions, risk=risk, checks=["rendu", "erreurs-formulaire", "effet"], key_extra=f"{form['selector']}:{mode}")

    first_page = path_of(pages[0]["url"]) if pages else "/"
    sample_pages = [path_of(p["url"]) for p in pages[: args.env_pages]]
    for name, values in site_map.get("parametres_url", {}).items():
        target = next((p for p in pages if name in dict(parse_qsl(urlparse(p["url"]).query))), pages[0] if pages else None)
        base_path = urlparse(target["url"]).path if target else "/"
        for value in values[: args.max_options] + ["valeur-inattendue-<>&", ""]:
            query = urlencode({name: value})
            book.add("parametre-url", f"Paramètre {name}={value[:30]!r}", f"{base_path}?{query}",
                     [{"goto": f"{base_path}?{query}"}, {"snapshot": "parametre"}], checks=["rendu", "console"], key_extra=f"{name}={value}")

    environments = [({"theme": "dark"}, "thème sombre système"), ({"reduced_motion": "reduce"}, "mouvement réduit"), ({"zoom": 2}, "zoom 200 %")]
    environments += [({"locale": lang}, f"langue {lang}") for lang in site_map.get("langues", [])[:6]]
    for page in sample_pages:
        for environment, title in environments:
            book.add("environnement", f"{page} en {title}", page, [{"goto": page}, {"snapshot": "environnement"}], environment=environment, checks=["rendu", "coherence"])
    for found in pages:
        for alternate in found.get("alternates", [])[:6]:
            page = path_of(alternate["href"])
            book.add("environnement", f"Version {alternate['hreflang']} de {path_of(found['url'])}", page, [{"goto": page}, {"snapshot": "langue"}],
                     checks=["rendu", "traduction"], key_extra=f"hreflang:{alternate['href']}")

    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    book.scenes.sort(key=lambda s: (order.get(s["categorie"], 99), s["id"]))
    if args.max_scenes and len(book.scenes) > args.max_scenes:
        for scene in book.scenes[args.max_scenes:]:
            book.skip(f"{scene['id']} {scene['titre']}", f"budget --max-scenes {args.max_scenes} atteint")
        book.scenes = book.scenes[: args.max_scenes]
    removed = [{"id": sid, "key": key} for key, sid in book.previous.items() if key not in book.keys]
    book.scenes.sort(key=lambda s: s["id"])
    return {
        "version": 1,
        "genere_le": now_iso(),
        "source": site_map.get("depart"),
        "origine": site_map.get("origine"),
        "points_de_rupture": site_map.get("points_de_rupture", []),
        "langues": site_map.get("langues", []),
        "theme_sombre_css": site_map.get("theme_sombre_css", False),
        "scenes": book.scenes,
        "non_couvert": book.skipped + [
            {"element": "combinaisons de plusieurs réglages à la fois", "raison": "une option à la fois (one-factor-at-a-time) ; combiner les réglages critiques à la main si nécessaire"},
            {"element": "téléversement de fichiers, glisser-déposer, gestes multi-doigts", "raison": "non générés automatiquement"},
            {"element": "liens externes", "raison": f"{len(site_map.get('liens_externes', []))} liens hors du site non suivis"},
        ],
        "retirees": removed,
        "resume": {
            "scenes": len(book.scenes),
            "par_categorie": {c: sum(1 for s in book.scenes if s["categorie"] == c) for c in CATEGORY_ORDER if any(s["categorie"] == c for s in book.scenes)},
            "non_couvert": len(book.skipped),
            "nouvelles": sum(1 for s in book.scenes if s["key"] not in book.previous),
            "retirees": len(removed),
        },
    }


def to_playwright(suite, allow_mutations):
    lines = [
        "import { test, expect, type Page } from '@playwright/test';",
        "",
        f"const BASE = process.env.UI_BASE_URL ?? {json.dumps(suite.get('origine') or 'http://localhost:3000')};",
        "",
        "async function checkScene(page: Page, name: string) {",
        "  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);",
        "  expect(overflow, 'défilement horizontal involontaire').toBeLessThanOrEqual(1);",
        "  await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.01 });",
        "}",
        "",
        "test.describe('Scènes UI générées par ui-audit-gate', () => {",
        "  test.beforeEach(async ({ page }) => {",
    ]
    if not allow_mutations:
        lines.append("    await page.route('**/*', (route) => (['GET', 'HEAD', 'OPTIONS'].includes(route.request().method()) ? route.continue() : route.abort()));")
    lines += ["  });", ""]
    for scene in suite["scenes"]:
        environment = scene.get("environnement") or {}
        options = []
        if environment.get("theme"):
            options.append(f"colorScheme: {json.dumps(environment['theme'])}")
        if environment.get("reduced_motion"):
            options.append(f"reducedMotion: {json.dumps(environment['reduced_motion'])}")
        if environment.get("locale"):
            options.append(f"locale: {json.dumps(environment['locale'])}")
        title = json.dumps(f"{scene['id']} {scene['titre']}"[:180], ensure_ascii=False)
        if options:
            lines.append(f"  test.describe(() => {{ test.use({{ {', '.join(options)} }});")
        lines.append(f"  test({title}, async ({{ page }}) => {{")
        lines.append("    const errors: string[] = [];")
        lines.append("    page.on('pageerror', (error) => errors.push(String(error)));")
        shot = 0
        for action in scene["actions"]:
            (kind, value), = action.items()
            if kind == "goto":
                lines.append(f"    await page.goto(BASE + {json.dumps(value, ensure_ascii=False)});")
            elif kind in ("click", "click_effect"):
                lines.append(f"    await page.locator({json.dumps(value, ensure_ascii=False)}).first().click();")
            elif kind == "click_optional":
                lines.append(f"    if (await page.locator({json.dumps(value, ensure_ascii=False)}).first().isVisible()) await page.locator({json.dumps(value, ensure_ascii=False)}).first().click();")
            elif kind == "fill":
                lines.append(f"    await page.locator({json.dumps(value[0], ensure_ascii=False)}).first().fill({json.dumps(str(value[1]), ensure_ascii=False)});")
            elif kind == "select":
                lines.append(f"    await page.locator({json.dumps(value[0], ensure_ascii=False)}).first().selectOption({json.dumps(value[1], ensure_ascii=False)});")
            elif kind == "check":
                lines.append(f"    await page.locator({json.dumps(value, ensure_ascii=False)}).first().check();")
            elif kind == "press":
                lines.append(f"    await page.keyboard.press({json.dumps(value, ensure_ascii=False)});")
            elif kind == "hover":
                lines.append(f"    await page.locator({json.dumps(value, ensure_ascii=False)}).first().hover();")
            elif kind == "wait":
                lines.append(f"    await page.waitForTimeout({int(value)});")
            elif kind == "snapshot":
                shot += 1
                shot_name = json.dumps(scene["id"] + "-" + str(shot))
                lines.append(f"    await checkScene(page, {shot_name});")
        lines.append("    expect(errors).toEqual([]);")
        lines.append("  });")
        if options:
            lines.append("  });")
        lines.append("")
    lines.append("});")
    return "\n".join(lines) + "\n"


def ignore_run_artifacts(suite_dir):
    import subprocess

    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=suite_dir, capture_output=True, text=True)
    if top.returncode != 0:
        return "pas un dépôt git"
    root = Path(top.stdout.strip())
    try:
        relative = suite_dir.resolve().relative_to(root).as_posix()
    except ValueError:
        return "suite hors du dépôt"
    wanted = [f"{relative}/runs/", f"{relative}/last-review.json"]
    gitignore = root / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    missing = [w for w in wanted if w not in lines]
    if missing:
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(("\n" if lines and lines[-1].strip() else "") + "\n".join(missing) + "\n")
        return "ajouté : " + ", ".join(missing)
    return "déjà ignoré"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site-map", required=True)
    parser.add_argument("--out", required=True, help="Fichier scenes.json (mis à jour en gardant les identifiants)")
    parser.add_argument("--max-options", type=int, default=12, help="Au-delà, échantillonner les options d'une liste")
    parser.add_argument("--env-pages", type=int, default=5, help="Pages rejouées dans chaque variante d'environnement")
    parser.add_argument("--max-scenes", type=int, default=0, help="Plafond (0 = aucun) ; le surplus est listé comme non couvert")
    parser.add_argument("--allow-destructive", action="store_true", help="Générer aussi les soumissions destructives (environnement de test uniquement)")
    parser.add_argument("--export-playwright", help="Écrire aussi un fichier de tests @playwright/test (.spec.ts)")
    args = parser.parse_args()

    site_map = read_json(args.site_map)
    suite = build(site_map, args)
    write_json(args.out, suite)
    ignore_note = ignore_run_artifacts(Path(args.out).parent)
    result = {"tool": "generate_scenarios", "out": args.out, **suite["resume"], "gitignore": ignore_note}
    if args.export_playwright:
        target = Path(args.export_playwright)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(to_playwright(suite, False), encoding="utf-8")
        result["playwright"] = str(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
