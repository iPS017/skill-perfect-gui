# Exploration et revue des scènes avant publication

L'audit par modification (workflow en 9 étapes) vérifie ce qui vient de changer. Ce mode-ci couvre **tout ce qu'un utilisateur peut faire** sur le site ou l'application Web. Il génère une suite de scènes versionnée et la rejoue en entier avant chaque republication.

## Cycle

```text
1. explore_site.py        site réel -> ui-scenes/site-map.json   (inventaire de tout ce qui est faisable)
2. generate_scenarios.py  site-map  -> ui-scenes/scenes.json     (une scène par action, option, paramètre, réglage)
3. play_scenarios.py --mode baseline                              (captures de référence, une fois)
4. avant chaque publication :
   play_scenarios.py      rejoue toutes les scènes sur chaque viewport, compare, détecte
   -> statut ok | a-revoir | echec | incomplet  ->  ui-scenes/last-review.json + runs/<date>/review.md
5. corriger, ou accepter les changements visuels voulus (--accept), puis relancer la revue
6. le hook de pré-publication laisse passer git push, npm publish, vercel, etc. seulement si
   la dernière revue est « ok », complète, et faite sur l'interface exacte qui part
```

Après un changement de structure (nouvelle page, nouveau formulaire), relancer 1 et 2. Les identifiants des scènes existantes ne changent pas. Les nouvelles s'ajoutent et celles qui ont disparu sont listées dans `retirees`.

## Commandes

```bash
SK="$SKILL_DIR/scripts"
python3 "$SK/explore_site.py" --url http://localhost:3000/ --out ui-scenes/site-map.json --max-pages 40
python3 "$SK/generate_scenarios.py" --site-map ui-scenes/site-map.json --out ui-scenes/scenes.json \
        --export-playwright tests/ui-scenes.spec.ts
python3 "$SK/play_scenarios.py" --suite ui-scenes --url http://localhost:3000/ --mode baseline
python3 "$SK/play_scenarios.py" --suite ui-scenes --url http://localhost:3000/ --viewports mobile,laptop --workers 4
python3 "$SK/play_scenarios.py" --suite ui-scenes --accept S-0012,S-0040     # changements visuels voulus
```

Options utiles :
- explore : `--max-pages`, `--max-depth`, `--include` et `--exclude` (regex de chemins), `--reveal-budget` (bascules ouvertes pour trouver les contrôles cachés), `--storage-state` (session connectée) ;
- generate : `--max-options`, `--env-pages`, `--max-scenes` ;
- play : `--viewports` (par défaut mobile,laptop ; N3 : `P0,P1`), `--scenes`, `--categories`, `--workers`, `--allow-mutations`, `--max-diff-ratio`, `--mask` (zones volontairement dynamiques : carrousel, date, publicité).

Les zones dynamiques à masquer en permanence se déclarent aussi dans `scenes.json` (`"masques": [".carousel", "#live-date"]`). Les images en chargement différé sont chargées avant chaque capture. Si une revue contre sa propre référence montre des changements, le contenu n'est pas déterministe : il faut fixer les données de test ou masquer la zone, jamais monter le seuil à l'aveugle. Une page refusée (erreur HTTP, protection anti-robot) est signalée et n'est pas contournée : explorer plutôt l'environnement de développement ou de test.

## Ce que les scènes couvrent

| Catégorie | Scènes générées |
|---|---|
| page | Chargement de chaque page découverte, y compris les variantes de paramètres d'URL |
| controle | Chaque bouton, ancre ou action sûre, avec détection d'effet (bouton mort) |
| bascule | Ouvrir, puis fermer (Échap pour un menu ou un popup, second clic pour un panneau dépliable) |
| onglet, menu | Activation de chaque onglet et de chaque élément de menu |
| liste, case, radio, curseur | Chaque option (échantillon au-delà de `--max-options`), cocher et décocher, bornes min et max |
| formulaire | Envoi vide, valeurs invalides, valeurs valides, contenus très longs |
| parametre-url | Chaque valeur observée, plus une valeur inattendue et une valeur vide |
| reglage | Thème, langue, tri, filtres, unités, etc. (contrôles reconnus comme réglages) |
| environnement | Thème sombre système, mouvement réduit, zoom 200 % (bureau), chaque langue `hreflang` |

Les contrôles cachés qu'une interaction révèle (menu, dialogue, accordéon) sont joués avec l'action qui les révèle.

## Ce que chaque étape vérifie

À chaque `snapshot` : débordement horizontal, texte rogné, superposition (hors modale et superpositions ouvertes), taille des cibles, contraste, erreurs de formulaire, alignement, images, noms accessibles. S'y ajoutent les contrôles de cohérence avec l'environnement :

| Anomalie | Contrôle | Bloquante |
|---|---|---|
| `action-sans-effet` : clic sans changement du DOM, de l'URL, du défilement ni requête | PAR-08 | oui |
| `defilement-bloque` : page impossible à faire défiler sans dialogue ouvert | STK-08 | oui |
| `theme-non-adapte` : grande zone claire dans une page sombre | COL-03 | oui |
| `contenu-non-traduit` : plus de la moitié des textes inchangés après changement de langue | LOC-02 | oui |
| `erreur-javascript` : exception non gérée | ROB-01 | oui |
| `lang-non-mis-a-jour` : textes traduits mais attribut `lang` inchangé | ACC-12 | non |
| `police-non-chargee` : police web déclarée mais rendu de secours | TXT-05 | non |
| `incoherence-style` : un composant diffère de ses semblables sur le site (police, taille, rayon, couleur de lien) | DS-03 | non |
| `fermeture-echap-inoperante` : menu ou popup qui reste ouvert après Échap | STK-03 | non |
| `controle-indisponible-a-ce-viewport` : contrôle introuvable ou non cliquable sur ce viewport | NAV-06 | non (à juger) |
| `theme-sombre-ignore` : le site déclare un thème sombre mais la page reste claire | COL-03 | non |
| `requete-bloquee` : requête POST, PUT ou DELETE bloquée par la garde | - | non |

Chaque capture est comparée à sa référence (`changements_visuels`). Une différence n'est ni bonne ni mauvaise : elle doit être revue. Soit elle est voulue et on l'accepte avec `--accept`, soit c'est une régression et on la corrige.

## Statuts de revue

| Statut | Condition | Publication |
|---|---|---|
| `ok` | Toutes les scènes exécutées, aucune anomalie bloquante, aucun changement visuel non accepté | autorisée |
| `a-revoir` | Changements visuels ou nouvelles captures sans référence | bloquée jusqu'à acceptation ou correction |
| `echec` | Au moins une anomalie bloquante non acceptée | bloquée |
| `incomplet` | Scènes en erreur, sélection partielle (`--scenes`, `--categories`) | bloquée |

Une anomalie bloquante ne s'accepte (`--accept-anomaly CLÉ --reason ... --accepted-by ...`) que sur décision explicite de l'utilisateur. Elle est alors consignée dans `ui-scenes/known-issues.json`. L'agent ne l'accepte jamais de lui-même.

## Sécurité

- Les actions destructives (supprimer, payer, envoyer, se déconnecter, résilier, etc.) ne sont pas générées. Elles sont listées dans `non_couvert`.
- Toutes les requêtes autres que GET, HEAD et OPTIONS sont bloquées pendant l'exploration et la revue, sauf avec `--allow-mutations`, à réserver à un environnement de test avec des données fictives.
- Les sessions connectées passent par `--storage-state`. Aucun mot de passe réel dans les scènes.

## Fichiers de la suite

| Fichier | Versionné | Rôle |
|---|---|---|
| `ui-scenes/scenes.json` | oui | Suite de scènes, identifiants stables |
| `ui-scenes/site-map.json` | oui (conseillé) | Inventaire de ce qui est faisable |
| `ui-scenes/baseline/` | oui (Git LFS si volumineux) | Captures de référence |
| `ui-scenes/known-issues.json` | oui | Anomalies acceptées par l'utilisateur |
| `ui-scenes/runs/` | non (ajouté au `.gitignore`) | Captures, diffs, rapports de chaque revue |
| `ui-scenes/last-review.json` | non | État lu par le hook de pré-publication |
| `tests/ui-scenes.spec.ts` | au choix | Même suite en `@playwright/test` pour la CI (`npx playwright test --update-snapshots` la première fois) |

## Barrière de publication

Le hook `PreToolUse` du plugin intercepte les commandes de publication (`git push`, `npm`, `pnpm`, `yarn` et `bun publish`, `vercel`, `netlify deploy`, `firebase deploy`, `fly deploy`, `wrangler deploy`, `gh release create`, `docker push`, `npm run deploy`, `eas submit`, `fastlane`, etc.). Il refuse la commande si :
- aucune revue complète n'existe ;
- `scenes.json` a changé depuis la revue ;
- un fichier d'interface a changé depuis la revue (empreinte des fichiers suivis et non suivis) ;
- la revue n'est pas au statut `ok`.

Il n'agit que si le projet possède `ui-scenes/scenes.json` (ou le chemin indiqué dans `.ui-audit/config.json > publish_gate.suite`). Réglages : `UI_AUDIT_PUBLISH_GATE=block|ask|off`, ou `publish_gate.mode`. Des commandes supplémentaires se déclarent dans `publish_gate.patterns`.

## Applications non Web

- **Web, PWA, hybride servi en local** (Capacitor, Ionic, React Native Web, Flutter Web, Tauri ou Electron avec leur serveur de développement) : cycle complet, en pointant `--url` vers le serveur de développement.
- **Application native pure** (iOS, Android, desktop) : ces scripts ne la pilotent pas. Le skill peut rédiger la liste des scènes à partir du code (écrans, routes, réglages) et les rejouer de façon assistée, par computer use ou avec les outils de la plateforme (XCUITest, Espresso, UI Automation). Ce sont alors des vérifications assistées, déclarées comme telles dans le rapport, pas une revue automatique.

## Limites

- Une option à la fois : les combinaisons de plusieurs réglages ne sont pas toutes générées. Ajouter à la main les combinaisons critiques dans `scenes.json` (même format, nouvel identifiant).
- Pas de téléversement de fichier, de glisser-déposer ni de geste multi-doigts générés automatiquement.
- Les menus qui ne s'ouvrent qu'au survol ne sont pas découverts. Ils sont listés dans `non_couvert` quand leurs éléments existent mais restent cachés.
- `action-sans-effet` a une confiance moyenne : une action peut agir sur un canvas, le presse-papiers ou le son sans changer le DOM.
- Les captures dépendent du moteur et de la machine : référence et revue doivent tourner dans le même environnement (même navigateur, même OS, idéalement en CI).
