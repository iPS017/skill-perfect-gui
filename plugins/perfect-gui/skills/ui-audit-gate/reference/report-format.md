# Format du rapport et des preuves

## Arborescence d'un run

```text
.ui-audit/
  config.json                 # optionnel : réglages du hook et du projet
  research-cache.json         # références réutilisables (revalidation obligatoire)
  exceptions.json             # exceptions encore ouvertes
  RUN-20261011-1430-checkout/
    scope.md
    impact.json
    capabilities.json
    coverage.json
    research/log.json
    research/references.json
    before/<config_id>/<nom>__<etat>.png
    before/manifests/<config_id>.json
    after/... after-fix-1/... diff/...
    inspect/<config_id>/inspect.json | annotated.png | aria-snapshot.txt
    keyboard/<config_id>/keyboard.json
    findings/DEF-001.json
    report.json
    report.md                 # produit par verify_report.py --render
```

## `report.json`

`init_run.py` crée ce squelette. L'agent le complète, puis `verify_report.py --apply --render` écrit la décision et produit `report.md`.

```json
{
  "run_id": "RUN-20261011-1430-checkout",
  "titre": "Pied de formulaire du checkout",
  "cree_le": "2026-10-11T14:30:00Z",
  "declenchement": "C1 | C2 | C3",
  "demande": "Texte de la demande utilisateur",
  "objectif": "...",
  "criteres_acceptation": ["..."],
  "perimetre": {"zones": ["Checkout/Footer"], "rayon_impact": ["Button (14 instances)"]},
  "niveau": "N2",
  "niveau_calcule": "N2",
  "couverture_reduite": false,
  "justification_reduction": null,
  "mode": "complet | maquette | sans_execution",
  "baseline": "avant | first-render | indisponible",
  "environnement": {"outils": ["playwright 1.x", "chromium 1xx"], "fidelite": "emulation"},
  "hypotheses": [{"hypothese": "...", "source": "...", "impact_si_fausse": "..."}],
  "recherche": {"statut": "realisee | partielle | non_realisee", "cause": null},
  "comparaisons": [{"ref": "REF-001", "observation": "...", "principe": "...", "ecart": "...", "adaptation": "...", "benefice": "...", "nature": "EXIGENCE"}],
  "changement_visuel": true,
  "controles": [
    {"id": "GEO-03", "statut": "reussi", "nature": ["visuel", "structurel"], "configs": ["mobile-..."], "preuves": ["inspect/mobile-.../inspect.json"]},
    {"id": "ACC-11", "statut": "non_verifie", "raison": "Aucun lecteur d'écran disponible", "raison_type": "humain"},
    {"id": "DAT-01", "statut": "non_applicable", "raison": "Aucun tableau dans le périmètre"}
  ],
  "defauts": ["voir la fiche ci-dessous"],
  "corrections": ["voir severity-and-fixes.md"],
  "variantes": [],
  "avant_apres": [{"config_id": "mobile-...", "avant": "before/.../checkout__normal.png", "apres": "after-fix-1/.../checkout__normal.png", "diff": "diff/...png", "commentaire": "Différence attendue : bouton élargi"}],
  "regressions": [{"controle": "DS-05", "resultat": "Aucune différence inattendue sur 6 écrans"}],
  "coverage": "coverage.json",
  "limites": ["Clavier virtuel natif non testé (émulation)"],
  "verifications_humaines": ["ACC-11 lecteur d'écran sur le parcours de paiement"],
  "decision": null
}
```

Valeurs de `decision` : `VALIDEE_PROTOCOLE_COMPLET`, `VALIDEE_PERIMETRE_TESTE`, `VALIDEE_AVEC_EXCEPTIONS`, `NON_VALIDEE`, `VALIDATION_LIMITEE`.

## Fiche de défaut (`defauts[]` ou `findings/DEF-xxx.json`)

```json
{
  "id": "DEF-012",
  "titre": "Libellé « Confirmer la réservation » rogné à 320 px",
  "controle": "CTA-01",
  "ecran_composant": "Checkout / Button(primary)",
  "preconditions": "Panier avec 1 article, utilisateur connecté",
  "donnees": "fixture typical, langue de",
  "config_id": "mobile-narrow-w320h640-z100-light-de-DE-m-chromium",
  "etapes": ["Ouvrir /checkout", "Défiler jusqu'au pied de page"],
  "attendu": "Libellé entièrement visible dans la surface du bouton",
  "observe": "Texte coupé après « Reservierung best » ; scrollWidth=212, clientWidth=176",
  "interpretation": "white-space:nowrap et largeur fixe du conteneur",
  "nature": "EXIGENCE",
  "preuves": ["inspect/mobile-narrow-.../annotated.png", "inspect/mobile-narrow-.../inspect.json"],
  "reproductions": "2/2",
  "severite": "majeure",
  "priorite": "P1",
  "confiance": "elevee",
  "effort": "S",
  "statut": "ouvert | corrige | echoue_non_resolu | accepte_exception",
  "introduit_par_correction": false,
  "retest": {"statut": "reussi", "config_id": "...", "preuves": ["after-fix-1/..."]},
  "exception": null,
  "cause_blocage": null,
  "action_requise": null
}
```

`nature` prend la valeur `EXIGENCE`, `HYPOTHESE` ou `PREFERENCE`. Les défauts peuvent être écrits directement dans `report.json > defauts` ou dans `findings/*.json`. `verify_report.py` fusionne les deux sources par identifiant.

## Manifeste de configuration (`manifests/<config_id>.json`)

Écrit par `capture.py`. Il contient le viewport CSS, le DPR, le zoom, le thème, la locale, le fuseau, les préférences, le pointeur, le moteur et sa version, la fidélité, l'horloge figée, l'URL, les étapes de navigation et la révision git.
