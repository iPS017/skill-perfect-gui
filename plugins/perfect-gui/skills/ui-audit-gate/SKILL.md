---
name: ui-audit-gate
description: Barrière qualité UI/UX obligatoire avant de déclarer terminée toute création ou modification d'interface (GUI, UI, UX, page, écran, composant, formulaire, navigation, interaction, style, CSS, design token, police, thème, responsive, traduction affichée, états de chargement ou d'erreur). Ouvre le rendu réel, capture avant/après, inspecte géométrie, superpositions, débordements, accessibilité, clavier, formulaires et responsive, fait une recherche Web tracée de références, corrige ou propose des correctifs, puis rend une décision de validation bornée et prouvée. Explore aussi tout un site ou une application Web, génère une scène pour chaque action, option, paramètre et réglage possible, et revoit toutes les scènes avant chaque republication. Use whenever you create, change, restyle, or refactor any user interface, web page, component, form, layout, or design token, before saying the UI work is done; when the user asks for a UI/UX audit, a design review of a rendered page, or a responsive or accessibility check; and when they want to test everything a user can do on a site, generate UI scenarios or regression scenes, or review the UI before publishing, deploying, or pushing.
---

# ui-audit-gate

Ce skill s'interpose entre « l'interface est modifiée » et « c'est validé ». Il ne promet pas une interface sans défaut. Il réduit le risque, prouve ce qui a été vérifié et dit honnêtement ce qui ne l'a pas été.

`SKILL_DIR` désigne le dossier qui contient ce fichier. Les scripts se lancent avec `python3 "$SKILL_DIR/scripts/<script>.py"`. Ils basculent seuls dans le venv `~/.cache/ui-audit-gate/venv` s'il existe. Chaque script affiche du JSON. Le code de sortie 3 signale une capacité manquante, à traduire en contrôles `non_verifie`.

## Règles non négociables

1. **Pas de validation sans rendu réel**, sauf mode dégradé déclaré (maquette, sans exécution).
2. **Un contrôle non exécuté n'est jamais `reussi`.** Statuts possibles : `reussi`, `echoue`, `non_verifie` (avec raison), `non_applicable` (avec raison factuelle).
3. **Trois vérifications distinctes** : visuelle, comportementale, assistive. Une capture correcte ne prouve ni un parcours ni l'accessibilité.
4. **Recherche Web réelle à chaque audit**, tracée dans `research/log.json`. Aucune URL, source ou consultation inventée. Une référence citée de mémoire sans revalidation est `memoire_non_revalidee` et ne compte pas.
5. **Étiqueter chaque constat** : `[EXIGENCE]` (règle explicite applicable), `[HYPOTHÈSE]` (à vérifier), `[PRÉFÉRENCE]` (goût, jamais bloquant seul).
6. **Émulation ≠ appareil réel.** Un viewport émulé n'est pas un test du téléphone. Aucune dimension d'appareil inventée (voir `reference/devices.md`).
7. **Ne pas dire « terminé », « validé » ou « prêt »** tant que l'étape 9 n'a pas produit une décision. Dire plutôt « implémenté, audit en cours ».
8. **Confidentialité** : ni capture, ni donnée, ni nom de produit interne dans les requêtes de recherche. Rien n'est envoyé à un service tiers sans autorisation.
9. **Corriger la cause** (token, composant partagé) plutôt que masquer le symptôme. Un `overflow:hidden` ou un `z-index:9999` posé sans analyse est un palliatif à déclarer comme tel.
10. **Ne jamais s'accorder une exception.** Seul l'utilisateur accepte un défaut majeur résiduel. Un défaut critique ne peut pas être couvert par une exception.

## Quand l'utiliser

Déclencheurs : nouvelle interface ; changement de style, contenu, structure, composant partagé, comportement, navigation, états, données affichées ou responsive ; **changement indirect** (police, token, CSS global, reset, mise à jour d'une bibliothèque UI, configuration de build CSS, fichiers de traduction).

Pas pour : du code purement backend sans effet affiché, ou une question théorique sans interface à examiner. Dans ce dernier cas, proposer l'audit.

## Démarrage

```bash
python3 "$SKILL_DIR/scripts/init_run.py" --slug checkout-footer        # crée .ui-audit/RUN-.../
python3 "$SKILL_DIR/scripts/probe.py" --out "$RUN/capabilities.json"   # capacités réelles
python3 "$SKILL_DIR/scripts/impact_scan.py" --out "$RUN/impact.json"   # périmètre et niveau
```

Si `probe.py` signale l'absence de Playwright, proposer `bash "$SKILL_DIR/scripts/setup.sh"` avec la commande exacte et demander l'accord avant d'installer. Sans accord, passer en mode dégradé (tableau plus bas).

## Workflow obligatoire (9 étapes)

Détail complet, entrées et sorties : `reference/workflow.md`. Chaque étape produit une preuve ou un statut `non_verifie` motivé.

1. **Cadrer.** Reformuler l'objectif et les critères d'acceptation dans `scope.md`. Lancer `impact_scan.py`. Lister les hypothèses. Fixer le niveau (N1, N2 ou N3, voir ci-dessous). Exploiter dépôt et conversation avant de demander quoi que ce soit. Poser en un seul lot les seules questions bloquantes.
2. **Capturer l'avant.** Si l'agent n'a pas encore modifié le code, capturer maintenant. Sinon, reconstruire l'état antérieur dans un worktree isolé (`git worktree add`) et le lancer. Pour une création, noter `baseline=first-render`. Si rien n'est possible, noter `baseline=indisponible` avec la raison.
   `capture.py --url URL --viewports P0 --out "$RUN/before" --name accueil --state normal`
3. **Rechercher.** Protocole : `reference/research-protocol.md`. Utiliser l'outil de recherche Web de l'hôte, puis consigner chaque requête et chaque page ouverte avec `research_log.py`. Retenir 2 à 5 références (8 en N3), remplir le tableau de comparaison, puis s'arrêter selon la règle d'arrêt.
4. **Exécuter et capturer l'après.** Lancer l'application réelle (scripts du projet), attendre la stabilisation et parcourir les états et configurations choisis (`reference/configurations.md`). Réaliser les interactions des parcours (`--actions`).
5. **Inspecter et croiser.**
   - `inspect_page.py` : débordement horizontal, texte rogné, superposition (`--scan-scroll`), taille des cibles, alignement des éléments frères, contraste, labels, noms accessibles, erreurs de formulaire, images, titres, langue, axe-core si disponible, console.
   - `keyboard_walk.py` : ordre de tabulation, pièges de focus, focus visible, focus masqué, éléments inatteignables.
   - `resize_probe.py --mode state` (perte d'état au redimensionnement ou au pliage) et `--mode keyboard` (clavier virtuel émulé).
   - Revue visuelle des captures annotées. Les contrôles sans script sont listés dans `reference/controls.md`.
6. **Consigner et prioriser.** Une fiche par défaut (schéma `schemas/finding.schema.json`), reproduite deux fois, avec l'observé séparé de l'interprété. Sévérité, priorité, confiance et effort sont quatre champs distincts (`reference/severity-and-fixes.md`). Regrouper les défauts par cause commune.
7. **Corriger ou proposer.** Dans le périmètre autorisé, corriger la cause et propager. Hors périmètre, fournir un correctif concret. Proposer 2 ou 3 variantes **seulement** s'il existe un vrai arbitrage, et en recommander une.
8. **Revérifier.** Relancer les contrôles, **recapturer dans les mêmes conditions** (`--out "$RUN/after-fix-1"`), puis `visual_diff.py` avant/après et sur le rayon d'impact. Expliquer chaque différence. Limite : 3 itérations par défaut, 6 par run. Au-delà, marquer `echoue_non_resolu` avec la cause et l'action requise.
9. **Rapporter et décider.** Remplir `report.json`, puis lancer `verify_report.py "$RUN" --apply --render`. Le script calcule la décision selon `reference/validation-gate.md`, refuse un rapport incohérent et produit `report.md`. Annoncer la décision dans la conversation (format plus bas).

## Mode exploration : toutes les scènes, revues avant chaque publication

Quand l'utilisateur veut tester tout ce qu'un utilisateur peut faire, avant une mise en production, ou quand le niveau est N3 sur un site entier, suivre `reference/exploration.md` :

1. `explore_site.py` inventorie les pages, boutons, menus, onglets, bascules, champs, listes, cases, formulaires, paramètres d'URL, réglages (thème, langue, tri, filtres), langues et points de rupture, y compris les contrôles révélés par une interaction.
2. `generate_scenarios.py` en tire `ui-scenes/scenes.json` : une scène par action, option, paramètre, réglage, formulaire (vide, invalide, valide, très long) et environnement (thème sombre, mouvement réduit, zoom, langues). Les identifiants restent stables. `--export-playwright` produit la même suite pour la CI.
3. `play_scenarios.py --mode baseline` enregistre les références. Ensuite, **avant chaque republication**, `play_scenarios.py` rejoue toutes les scènes sur chaque viewport. Il détecte les bugs graphiques et les incohérences avec l'environnement (bouton mort, défilement bloqué, thème mal adapté, contenu non traduit, police de secours, style incohérent entre pages, erreurs JS) et compare chaque capture à sa référence.
4. Corriger, accepter les changements visuels voulus (`--accept`), relancer jusqu'au statut `ok`. Le hook de pré-publication refuse `git push`, `npm publish`, `vercel`, etc. tant que la dernière revue n'est pas `ok` sur l'interface exacte qui part.

Les actions destructives ne sont jamais jouées et les requêtes POST, PUT et DELETE sont bloquées, sauf `--allow-mutations` dans un environnement de test. Ce qui n'est pas couvert (combinaisons multiples, téléversement, glisser-déposer, survol) est listé dans le rapport. Pour une application native pure, les scènes sont rejouées de façon assistée, et déclarées comme telles.

## Niveaux d'audit

| Niveau | Quand | Couverture |
|---|---|---|
| N1 | Toujours | Contrôles fondamentaux (`config/levels.json`) sur le périmètre, viewports P0, états touchés, recherche ciblée |
| N2 | Composant partagé, comportement, navigation, formulaire, ou défaut trouvé en N1 | N1, plus consommateurs et écrans voisins, P0+P1, clavier complet du parcours |
| N3 | Token ou style global, dépendance UI, refonte, parcours critique (paiement, authentification, données personnelles, action destructive) | N2, plus P2, préférences utilisateur, localisation, réseau dégradé, pliables, échantillonnage large |

`impact_scan.py` propose un niveau. Toute baisse est déclarée dans `report.json` (`couverture_reduite`, `justification_reduction`).

## Configurations minimales

- Viewports en pixels CSS : `config/viewports.json` (P0 : 320×640, 390×844, 1366×768, 1440×900). Ajouter les points de rupture réels du projet à `b-1`, `b` et `b+1` (`--viewports 767x900,768x900,769x900`).
- Contenus : `config/fixtures/` (long, vide, inattendu) et pseudo-localisation (`inspect_page.py --pseudo`, `pseudo_locale.py`).
- Préférences : `--theme dark`, `--reduced-motion reduce`, `--forced-colors`, `--zoom 2`, `--text-spacing`.
- Consigner dans `coverage.json` les combinaisons exécutées **et** celles exclues, avec la raison et le risque. Ne jamais écrire « testé sur tous les appareils ».

## Modes dégradés

| Situation | Conduite | Plafond de décision |
|---|---|---|
| Pas de Playwright ni de navigateur | Proposer `setup.sh`. Sinon captures fournies par l'utilisateur et lecture du code. | VALIDATION_LIMITEE (sans_execution) |
| Capture impossible | Diagnostiquer, réessayer avec un autre moteur (`--engine`, `--browser-path`, `--headed`), puis marquer tous les contrôles visuels `non_verifie` | NON_VALIDEE si le changement est visuel (B5) |
| Web indisponible | `research_log.py unavailable --cause ...`, poursuivre les contrôles locaux, étiqueter les recommandations `[HYPOTHÈSE, non sourcée en ligne]` | VALIDEE_PERIMETRE_TESTE au mieux |
| Maquette seule | Audit visuel statique, interactions `non_verifie` | VALIDATION_LIMITEE (maquette) |
| Natif ou hybride | `reference/tools-and-degraded-modes.md` | Selon l'outillage |
| Pas d'appareil réel | Émulation déclarée, contrôles matériels `non_verifie` avec `raison_type: appareil_reel` | Pas de plafond, mais listé |
| Pas de lecteur d'écran | ACC-11 `non_verifie` avec `raison_type: humain` | Listé en vérification humaine |

## Sécurité des parcours

Les actions externes ou irréversibles (paiement, envoi, suppression, publication) se testent avec des données fictives ou un environnement de test. Sinon, s'arrêter avant l'action et demander confirmation. Les secrets ne vont jamais dans les rapports. Anonymiser toute capture qui sort de la machine.

## Barrière mécanique

Le plugin installe deux hooks. Le hook `PreToolUse` bloque les commandes de publication sans revue des scènes valide (voir le mode exploration). Le hook `Stop` bloque une fois la fin du tour si des fichiers d'interface ont changé dans le dépôt git sans `report.json` cohérent et plus récent. Désactivation : `UI_AUDIT_GATE=off|warn` ou `.ui-audit/config.json`. Créer `.ui-audit/SKIP` (avec une raison) **uniquement** si l'utilisateur a explicitement demandé de ne pas auditer. Ne pas affirmer que le skill est « toujours actif » si le hook n'est pas installé.

## Message final dans la conversation

```
Audit UI : <DÉCISION> (RUN-...)
Vérifié : <niveau, configurations, contrôles exécutés>
Défauts : <n critiques / n majeurs / ...> ; corrigés : <n> ; restants : <liste courte>
Non vérifié : <ex. lecteur d'écran réel, pliable physique, clavier natif>
Rapport : .ui-audit/RUN-.../report.md
```

Ne jamais conclure par « tout est parfait ». Ne pas présenter une absence de défaut détecté comme une absence de défaut.

## Fichiers de référence

| Fichier | Contenu | Quand le lire |
|---|---|---|
| `reference/workflow.md` | Étapes détaillées, déterminisme, boucle | Toujours, au premier audit d'une session |
| `reference/controls.md` | Matrice complète des contrôles (identifiants, méthode, attendu, sévérité) | Étape 5 |
| `reference/configurations.md` | États, viewports, pliables, clavier virtuel, échantillonnage | Étapes 4 et 5 |
| `reference/research-protocol.md` | Requêtes, hiérarchie des sources, fiche de référence, arrêt | Étape 3 |
| `reference/severity-and-fixes.md` | Sévérité, priorité, fiche de correction, variantes | Étapes 6 et 7 |
| `reference/validation-gate.md` | Statuts, conditions bloquantes, décisions, exceptions | Étape 9 |
| `reference/tools-and-degraded-modes.md` | Scripts, alternatives, natif, autorisations | Étape 1 ou en cas d'échec d'outil |
| `reference/devices.md` | Vérification des appareils et classes d'écran | Pliables et appareils nommés |
| `reference/report-format.md` | Structure de `report.json`, arborescence des preuves | Étapes 6 et 9 |
| `reference/exploration.md` | Exploration, suite de scènes, revue avant publication, statuts, barrière de publication | Site entier, « tout tester », avant une publication |
