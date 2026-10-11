# Workflow détaillé

Chaque étape liste ses entrées, ses actions, ses preuves et sa condition de sortie. `$RUN` est le dossier créé par `init_run.py`.

```text
[1 Cadrer] -> [2 Avant] -> [3 Rechercher] -> [4 Exécuter] -> [5 Inspecter]
   -> [6 Consigner] -> [7 Corriger] -> [8 Revérifier] --(reste des défauts, itérations < limite)--> [7]
   -> [9 Rapporter et décider]
```

Si le skill est invoqué avant le codage, les étapes 1 à 3 précèdent l'implémentation. S'il est invoqué après, l'état « avant » se reconstruit depuis git :

```bash
git worktree add ../_ui-audit-before HEAD   # ou la révision précédant les modifications
# lancer l'application depuis ce worktree sur un autre port, capturer, puis :
git worktree remove ../_ui-audit-before
```

## Étape 1 : Cadrer

- **Entrées** : demande, dépôt, conversation, diff.
- **Actions** :
  1. `init_run.py --slug <sujet>` pour créer le run.
  2. `probe.py --out "$RUN/capabilities.json"` pour sonder les capacités.
  3. `impact_scan.py --out "$RUN/impact.json"` (ajouter `--base <ref>` si les changements sont déjà commités) pour obtenir les zones touchées, leur confiance (`certain`, `probable`, `inconnu`) et le niveau suggéré.
  4. Remplir `scope.md` : objectif, tâche principale, parcours (1 à 3), critères d'acceptation, contraintes trouvées (design system, `browserslist`, référentiel d'accessibilité), hypothèses avec leur impact si elles sont fausses.
  5. Trouver comment lancer l'application : `package.json`, README, Makefile, docker-compose, scripts. Ne demander l'URL ou la commande qu'après avoir cherché.
- **Questions** : seulement si la réponse change le déroulé et qu'aucun choix réversible n'existe. Toutes en un seul message.
- **Sortie** : périmètre figé, niveau et justification.

## Étape 2 : Capturer l'état initial

```bash
python3 "$SKILL_DIR/scripts/capture.py" --url http://localhost:5173/checkout \
  --viewports P0 --out "$RUN/before" --name checkout --state normal --freeze-time 2026-01-15T10:00:00Z
```

- Capturer les mêmes écrans et états que ceux qui seront audités après.
- Garder les manifestes (`$RUN/before/manifests/*.json`). Ils fixent les conditions à reproduire.
- **Sortie** : `baseline=avant`, `first-render` ou `indisponible`, avec sa raison.

## Étape 3 : Rechercher

Voir `research-protocol.md`. Commandes de traçage :

```bash
python3 "$SKILL_DIR/scripts/research_log.py" "$RUN" query --text "accessible inline form validation pattern" --tool WebSearch --urls URL1 URL2
python3 "$SKILL_DIR/scripts/research_log.py" "$RUN" visit --url URL1 --tool WebFetch
python3 "$SKILL_DIR/scripts/research_log.py" "$RUN" ref --json '{"titre":"...","url":"URL1", ...}'
```

## Étape 4 : Exécuter et capturer

- Lancer l'application avec les scripts du projet, en arrière-plan si besoin. Vérifier qu'elle répond.
- Les actions de parcours vont dans un fichier JSON (liste d'objets à une clé) :

```json
[
  {"goto": "/checkout"},
  {"fill": ["#email", "test@example.com"]},
  {"click": "button[type=submit]"},
  {"wait_for": "#confirmation"}
]
```

  Actions disponibles : `goto`, `click`, `fill`, `type`, `press`, `hover`, `focus`, `check`, `select`, `wait`, `wait_for`, `scroll`, `eval`, `set_viewport`.
- Capturer chaque état avec `--state <code>` (codes dans `configurations.md`).
- Les transitions (chargement vers succès, ouverture et fermeture de modale, redimensionnement en cours d'usage) sont des contrôles comportementaux séparés. Les vérifier par des actions suivies d'une inspection, pas seulement par des captures finales.

## Étape 5 : Inspecter et croiser

```bash
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --viewports P0 --out "$RUN/inspect" --scan-scroll
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --viewports 390x844 --pseudo --out "$RUN/inspect-pseudo"
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --viewports 1280x800 --zoom 2 --out "$RUN/inspect-zoom200"
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --actions submit-empty.json --out "$RUN/inspect-errors"
python3 "$SKILL_DIR/scripts/keyboard_walk.py" --url URL --viewports laptop --out "$RUN/keyboard"
python3 "$SKILL_DIR/scripts/resize_probe.py" --url URL --mode state --widths 1366,960,600,390,1366
python3 "$SKILL_DIR/scripts/resize_probe.py" --url URL --mode keyboard --field "#email" --action "button[type=submit]"
```

Lecture des résultats :
- `result: issues` signale des candidats. Chaque candidat se confirme sur la capture annotée (`annotated.png`) avant de devenir un défaut. Les heuristiques d'alignement et de visibilité du focus ont une confiance moyenne.
- `result: clean` signifie « rien détecté par ce script ». Ce n'est pas une preuve d'absence de défaut, et le contrôle ne passe `reussi` que si sa méthode est entièrement couverte par le script (voir la colonne Auto. de `controls.md`).
- `result: error` ou un code de sortie 3 donne `non_verifie`, avec la raison.
- L'arbre d'accessibilité (`aria-snapshot.txt`) sert de preuve pour ACC-05. Il ne remplace pas un lecteur d'écran réel (ACC-11).

## Étape 6 : Consigner et prioriser

- Une fiche `findings/DEF-xxx.json` par défaut, plusieurs instances possibles.
- Reproduire deux fois. Si le défaut est intermittent, l'indiquer et baisser la confiance.
- Séparer `observe` (faits, mesures) et `interpretation` (cause supposée).
- Étiquette de nature, sévérité, priorité, confiance, effort : voir `severity-and-fixes.md`.

## Étape 7 : Corriger ou proposer

- Une fiche de correction par cause (`severity-and-fixes.md`).
- Si la cause commune est établie, corriger le token ou le composant et lister les instances à revérifier.
- Sans autorisation, ou hors du périmètre de la demande : proposer un diff ou une description précise, sans l'appliquer.

## Étape 8 : Revérifier

```bash
python3 "$SKILL_DIR/scripts/capture.py" ... --out "$RUN/after-fix-1"     # mêmes options que l'avant
python3 "$SKILL_DIR/scripts/visual_diff.py" --before "$RUN/before" --after "$RUN/after-fix-1" --out "$RUN/diff"
```

- Chaque différence se qualifie : attendue (liée à la correction) ou régression.
- Relancer les contrôles de non-régression listés dans chaque fiche de correction.
- Limite : 3 tentatives par défaut, 6 itérations par run. Au-delà, statut `echoue_non_resolu`, avec `cause_blocage` et `action_requise` (décision produit, information manquante, outil manquant, hors périmètre).

## Étape 9 : Rapporter et décider

```bash
python3 "$SKILL_DIR/scripts/verify_report.py" "$RUN" --apply --render
```

- Code 0 : rapport cohérent. La décision est écrite et `report.md` est produit.
- Code 1 : incohérences listées (preuve manquante, référence non tracée, décision contraire aux règles). Corriger le rapport, jamais les règles.

## Déterminisme

| Source de variabilité | Mesure |
|---|---|
| Date et heure | `--freeze-time ISO` |
| Animations, transitions, caret | Neutralisées par défaut dans les captures (`--keep-motion` pour les garder) |
| Polices | Attente de `document.fonts.ready`. Tester le repli séparément en bloquant les polices (`{"eval": ...}` ou outil réseau). |
| Réseau | Données de test stables. Mocks côté projet si disponibles. Le réseau réel se teste à part. |
| Contenu tiers | Masquer ou remplacer par un bloc de même taille, et le signaler |
| Rendu | Même machine, même navigateur et même version entre avant et après |
