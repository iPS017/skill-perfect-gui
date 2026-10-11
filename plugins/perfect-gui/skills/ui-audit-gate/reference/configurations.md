# États et configurations

## États

| Code | État | Comment le provoquer |
|---|---|---|
| S-INIT | Premier rendu | Chargement à froid |
| S-NORM | Normal, données typiques | `config/fixtures/typical` ou données du projet |
| S-HOV | Survol | Action `hover` (pointeur fin seulement) |
| S-FOC | Focus clavier | `keyboard_walk.py` ou action `press: Tab` |
| S-ACT | Pressé | Action `eval` dispatchant `pointerdown` |
| S-SEL | Sélectionné, coché, ouvert | Interaction |
| S-DIS | Désactivé | Condition métier |
| S-LOAD | Chargement | Réponse retardée (mock projet, réseau bridé) |
| S-EMPTY | Vide | Données vides |
| S-ERR | Erreur (champ, page, réseau, serveur) | Saisie invalide, mocks 4xx et 5xx, hors ligne |
| S-OK | Succès | Parcours complet |
| S-VAL | Validation en cours | Validation asynchrone retardée |
| S-DLG | Dialogue ou overlay ouvert | Interaction |
| S-INT | Interruption | Arrière-plan, expiration, perte réseau, redimensionnement |

Transitions à vérifier explicitement : `LOAD -> OK`, `LOAD -> ERR`, `ERR -> correction -> OK`, `NORM -> DLG -> NORM` (focus restitué au déclencheur), `NORM -> redimensionnement ou orientation -> NORM` (état conservé), `OK -> retour arrière`, `INT -> reprise`.

Le croisement contrôle × état suit la colonne « états » de chaque contrôle. Il ne s'agit pas d'un produit cartésien complet.

## Dimensions à ne pas confondre

| Dimension | Définition |
|---|---|
| Viewport CSS | `innerWidth × innerHeight` en pixels CSS. C'est ce que voient les media queries. |
| DPR | `devicePixelRatio` |
| Résolution de capture | Viewport × DPR. Les captures annotées sont en échelle CSS (1 px = 1 px CSS). |
| Zoom navigateur | `--zoom 2` sur une fenêtre de 1280 px donne un viewport CSS de 640 px |
| Échelle de l'OS | Mise à l'échelle système (non émulée) |
| Taille de texte utilisateur | Police par défaut agrandie (à émuler par `eval` sur `html { font-size }`, résultat approximatif) |

## Viewports (pixels CSS)

Source machine : `config/viewports.json`. Ces largeurs représentent des **classes**, pas des appareils.

| Priorité | Identifiant | Taille | Raison |
|---|---|---|---|
| P0 | mobile-narrow | 320 × 640 | Plancher de reflow (WCAG 1.4.10, à vérifier) |
| P0 | mobile | 390 × 844 | Téléphone courant |
| P0 | laptop | 1366 × 768 | Laptop |
| P0 | desktop-md | 1440 × 900 | Laptop large |
| P1 | mobile-large | 430 × 932 | Grand téléphone |
| P1 | mobile-landscape | 844 × 390 | Hauteur réduite |
| P1 | tablet-portrait | 768 × 1024 | Tablette |
| P1 | tablet-portrait-lg | 820 × 1180 | Tablette |
| P1 | tablet-landscape | 1024 × 768 | Tablette paysage |
| P1 | tablet-landscape-lg | 1180 × 820 | Tablette paysage |
| P1 | desktop | 1920 × 1080 | Bureau |
| P2 | small-desktop | 1024 × 640 | Petite fenêtre |
| P2 | split-half | 960 × 1080 | Écran partagé |
| P2 | ultrawide | 2560 × 1080 | Longueur de ligne, étirement |
| P2 | ultrawide-xl | 3440 × 1440 | Ultrawide |
| P2 | short | 1280 × 600 | Hauteur faible |
| P2 | phone-landscape-small | 640 × 360 | Petit paysage |
| Reflow | reflow | 320 × 256 | Défilement horizontal |

**Points de rupture.** Extraire les breakpoints réels du projet (media queries, container queries, configuration Tailwind ou du framework CSS) avec par exemple `grep -rhoE "@media[^{]+" src | sort -u`. Pour chaque breakpoint `b` qui concerne le périmètre, tester `b-1`, `b` et `b+1` avec le contenu le plus long : `--viewports 767x900,768x900,769x900`.

## Redimensionnement en cours d'usage

`resize_probe.py --mode state --widths 1366,960,600,390,1366` remplit les champs, puis redimensionne. Il vérifie que les valeurs, le focus, les dialogues ouverts et la page elle-même (pas de rechargement) sont conservés. Préparer l'état voulu avec `--actions` (ouvrir une modale, passer à l'étape 2).

## Pliables

Lire `devices.md` avant de citer un appareil.

| Classe | Description | À vérifier |
|---|---|---|
| F-FLIP-FERMÉ | Petit écran externe d'un pliable à clapet | Navigateur disponible ? Contenu minimal, cibles |
| F-FLIP-OUVERT | Écran principal très allongé | Hauteur importante, largeur de téléphone |
| F-LIVRE-FERMÉ | Écran externe étroit et haut | Largeur parfois inférieure à un téléphone classique |
| F-LIVRE-OUVERT | Écran interne quasi carré | Bascule mobile / tablette, deux colonnes |
| F-SEMI-PLIÉ | Posture partiellement ouverte | Seulement si la posture est exposée au Web |
| F-DOUBLE-ÉCRAN | Deux écrans et une charnière | Segments de viewport |

Les dimensions viennent de sources officielles datées ou de profils d'émulation officiels, jamais de la mémoire. Transitions à tester avec `resize_probe.py --mode state --widths <fermé>,<ouvert>,<fermé>` : saisie, focus, progression et scroll conservés, pas de rechargement.

Charnière et segments : ne tester que si l'information est exposée au Web et prise en charge par le navigateur cible (media features `horizontal-viewport-segments` et `vertical-viewport-segments`, `env(viewport-segment-*)`, API Device Posture). Vérifier leur support au moment de l'audit. Sinon : `non_applicable` (non exposé) ou `non_verifie` avec `raison_type: appareil_reel`.

## Clavier virtuel, safe areas, barres du navigateur

- `resize_probe.py --mode keyboard --field SEL --action SEL [--ratio 0.55]` réduit la hauteur du viewport comme un clavier en mode resizes-content. Il vérifie que le champ focalisé est visible et non recouvert, et que l'action principale est atteignable par un défilement que l'utilisateur peut réellement faire. Un défilement possible seulement par script (conteneur `overflow: hidden`) compte comme un échec.
- Limite déclarée : le mode resizes-visual (iOS, Chrome Android par défaut récent), le clavier natif et les barres système ne sont pas reproduits. Les marquer `non_verifie` avec `raison_type: appareil_reel` si le parcours est mobile.
- Rechercher dans le code les `100vh` d'éléments plein écran et les pieds de page fixes près des formulaires.

## Contenus

`config/fixtures/` fournit `edge-text.json` (textes longs, mots sans espace, URL, émojis, scripts non latins, RTL) et `unexpected.json` (null, négatifs, zéro, très grands nombres, HTML échappé). Les injecter via les données de test du projet ou une action `eval`. La pseudo-localisation se fait en page (`inspect_page.py --pseudo`, environ +40 % et des accents) ou sur fichier (`pseudo_locale.py`).

## Échantillonnage fondé sur le risque

```text
1. Socle (toujours) :
   contrôles fondamentaux × états touchés × P0
   + parcours principal au clavier (laptop) + parcours en pointeur grossier (mobile)
2. Combinaisons critiques selon l'impact :
   composant modifié × variantes utilisées × {320, breakpoints ±1}
   contenu modifié × {long, pseudo-locale} × {320, 390}
   formulaire modifié × {S-ERR, S-LOAD, S-OK} × {clavier, tactile}
   overlay modifié × {près des 4 bords, 320} × {ouvert, fermeture, focus restitué}
3. Couverture représentative (N2+) : un viewport par classe P1 × {S-NORM, S-ERR} ; chaque thème × un viewport
4. Approfondissement (N3 ou défaut trouvé) : configurations voisines de celle en défaut,
   combinaisons par paires sur thème × langue × préférence × viewport
5. Écrire coverage.json : {"executees": [...], "exclues": [{"combinaison", "raison", "risque"}]}
```

## Fidélité

Chaque résultat porte `fidelite: simulation | emulation | reel`. Ne sont pas validables sans appareil réel : clavier virtuel natif, charnière physique, performance tactile, lecteurs d'écran mobiles, capteurs, rendu de police propre à l'OS, barres système.
