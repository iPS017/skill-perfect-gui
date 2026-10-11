# Matrice des contrôles

Chaque contrôle porte un identifiant stable, utilisé dans `report.json` (`controles[].id`) et dans les fiches de défaut. Les seuils notés « à vérifier » doivent être confirmés dans la version de la norme applicable au projet (WCAG, RGAA, EN 301 549, guidelines de plateforme). L'exigence du projet prime toujours.

## Couverture par les scripts

| Vérification du script | Script | Contrôles alimentés | Couverture |
|---|---|---|---|
| `horizontal-overflow` | inspect_page | GEO-01, ACC-08 (à 320 px ou zoom 400 %) | Complète pour la détection. La cause se confirme visuellement. |
| `text-overflow` | inspect_page | GEO-03, CTA-01, TXT-08, LOC-01 (avec `--pseudo`), TXT-04 (avec `--text-spacing`) | Complète pour le rognage et le débordement de boîtes visibles |
| `occlusion` | inspect_page `--scan-scroll` | STK-01, STK-06 (partiel) | Points échantillonnés (centre et 4 coins). Un élément décoratif transparent au-dessus peut créer un faux positif. |
| `target-size` | inspect_page | CTA-03 | Seuil 24 px avec exception d'espacement, plus avertissement sous le seuil tactile en pointeur grossier |
| `alignment` | inspect_page | GEO-02, CTA-02, CTA-04 | Heuristique, confiance moyenne. Confirmer l'intention sur la capture et dans le design system. |
| `contrast` | inspect_page | TXT-01 | Fonds unis seulement. Fonds image, dégradé ou transparent : liste `needs_assisted`. |
| `form-labels` | inspect_page | FRM-01 | Nom accessible approché. Confirmer avec `aria-snapshot.txt`. |
| `accessible-names` | inspect_page | ACC-05 (partiel) | Noms vides seulement. La pertinence du nom relève d'un jugement humain. |
| `form-errors` | inspect_page avec actions qui déclenchent l'erreur | FRM-03 (partiel) | Liaison et annonce. Proximité et clarté du message : revue visuelle. |
| `images` | inspect_page | COL-05 (partiel), COL-04 | Présence de `alt`, images cassées. Pertinence : humain. |
| `headings` | inspect_page | TXT-02 | Complète pour la structure |
| `document` | inspect_page | NAV-01 (partiel), ACC-12 | Titre et langue |
| `landmarks` | inspect_page | ACC-10 | Présence de `main` et du lien d'évitement |
| `axe` | inspect_page | ACC-01 | Règles axe-core. Les résultats `incomplete` sont à revoir manuellement. |
| `console` | inspect_page | ROB-01 | Erreurs console, exceptions, réponses 4xx et 5xx |
| tabulation | keyboard_walk | ACC-02, ACC-03, ACC-04, STK-02, STK-03 (Échap) | Ordre, pièges, visibilité (heuristique de style), masquage |
| état | resize_probe `--mode state` | ROB-06, FRM-04 (partiel) | Valeurs, focus, rechargement, dialogues ouverts |
| clavier virtuel | resize_probe `--mode keyboard` | ENV-02 | Émulation du mode resizes-content seulement |
| diff visuel | visual_diff | DS-05, DS-06 | Pixel. Chaque différence doit être interprétée. |
| scènes | explore_site, generate_scenarios, play_scenarios | PAR-08, STK-08, COL-03, LOC-02, TXT-05, DS-03, ACC-12, NAV-06, ROB-01, plus les vérifications en page à chaque étape | Une option à la fois ; voir exploration.md |

Les contrôles absents de ce tableau se mènent par revue assistée ou humaine selon leur méthode. Un contrôle n'est `reussi` que si toute sa méthode a été exécutée. Une couverture partielle par script, sans revue complémentaire, donne `non_verifie` avec la partie manquante en raison.

## Extension projet

Un projet peut ajouter des contrôles dans `.ui-audit/controls-project.md`, avec le même format de tableau et un préfixe `PRJ-`. Il peut aussi désactiver un contrôle générique en le listant avec une justification. Le skill lit ce fichier à l'étape 1 s'il existe.

Légende des colonnes : **Nat.** V=visuel, S=structurel, C=comportemental, A=assistif, H=humain. **Auto.** A=automatisé, As=assisté, H=humain. **F** = fondamental (✓).

## Contrôles fondamentaux (exécutés à tous les niveaux, liste machine dans `config/levels.json`)

GEO-01, GEO-02, GEO-03, GEO-05, STK-01, STK-02, TXT-01, CTA-01, CTA-02, CTA-03, FRM-01, FRM-03 (si formulaire), COL-01, NAV-01, PAR-01, ACC-01, ACC-02, ACC-03, ACC-04, ACC-05, ROB-01, DS-01, ainsi que la couverture des viewports P0 (configurations.md).

## Géométrie et mise en page (GEO)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| GEO-01 | Scroll horizontal involontaire | `document.documentElement.scrollWidth > innerWidth` ; identifier l'élément le plus large qui dépasse | Aucun débordement de page, sauf zone de scroll horizontal volontaire et signalée | S,V | A | majeure | ✓ |
| GEO-02 | **Élément décalé ou mal placé** (bouton hors alignement, icône décentrée) | Comparer les bords et centres des éléments frères d'un même groupe (tolérance projet, défaut 1 px CSS) ; comparer aux positions de l'avant et à la grille du design system ; revue visuelle | Alignement sur les lignes de grille ou d'axe attendues ; écarts justifiés par le design | V,S | As | modérée (majeure si l'action principale est concernée) | ✓ |
| GEO-03 | **Texte débordant ou rogné** | `scrollWidth/Height` vs `client*` ; rect enfant hors rect parent ; ellipsis sans accès au texte complet | Pas de rognage ; un tronquage volontaire offre le texte complet (tooltip accessible, expansion) | S,V | A | majeure | ✓ |
| GEO-04 | Espacements incohérents | Extraire marges, paddings et gaps calculés, comparer à l'échelle de tokens | Valeurs issues de l'échelle ; écarts justifiés | S | A | mineure `[PRÉFÉRENCE]` sauf exigence DS | |
| GEO-05 | Tailles minimales et maximales non tenues (éléments écrasés ou étirés) | Mesure des boîtes à min, max et points de rupture ±1 px | Pas d'élément de largeur ou hauteur nulle ou négative ; lignes lisibles | S,V | A | majeure | ✓ |
| GEO-06 | Retour à la ligne indésirable (mot coupé, orphelin dans un bouton, icône séparée de son libellé) | Nombre de lignes par élément (hauteur / line-height) ; capture | Libellés de contrôle sur une ligne ou retour maîtrisé | V,S | As | modérée | |
| GEO-07 | Proportions et densité (zones vides ou surchargées) | Revue heuristique avec les références | Hiérarchie claire | V,H | H | `[PRÉFÉRENCE]` sauf exigence | |
| GEO-08 | Conteneurs imbriqués (cartes dans cartes, double padding) | Profondeur de conteneurs à bordure ou fond | Profondeur justifiée | V,S | As | mineure | |
| GEO-09 | Décalage de mise en page (layout shift) au chargement ou à l'interaction | Mesure des décalages (API Layout Instability si disponible) ; comparaison de captures successives | Pas de déplacement inattendu d'un élément visé par l'utilisateur | C,S | A | majeure si un clic est détourné | |

## Empilement et positionnement (STK)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| STK-01 | **Superposition masquant une action** | Pour chaque élément interactif visible : `elementFromPoint` au centre et aux 4 coins intérieurs ; l'élément retourné doit être la cible ou son descendant | Toute cible interactive cliquable en son centre | S,C | A | critique si action essentielle | ✓ |
| STK-02 | Élément fixed ou sticky recouvrant du contenu ou le focus | Pendant la tabulation, vérifier que l'élément focalisé n'est pas entièrement masqué par un élément fixe (cf. WCAG 2.2 SC 2.4.11, à vérifier) ; `scroll-padding` | Focus et contenu ancré visibles | S,A | A | majeure | ✓ |
| STK-03 | Modale : fond scrollable, fermeture, restitution du focus | Ouvrir, puis Échap, clic sur le fond, bouton de fermeture ; vérifier `inert` ou `aria-modal`, le focus initial et le retour du focus au déclencheur | Focus contenu, fermeture possible, retour du focus | C,A | A | majeure | |
| STK-04 | Popover, menu ou tooltip hors viewport ou mal ancré | Ouvrir près des 4 bords et à 320 px ; rect ⊂ viewport | Repositionnement (flip/shift) ; contenu entier visible | S,V | A | majeure | |
| STK-05 | Contexte d'empilement inattendu (z-index sans effet) | Remonter les ancêtres qui créent un contexte (`transform`, `opacity<1`, `filter`, `isolation`, `position+z-index`) | Ordre d'empilement conforme à l'intention | S | As | modérée | |
| STK-06 | Safe areas (encoche, barre d'accueil) | Émulation avec insets ; vérifier l'usage de `env(safe-area-inset-*)` et `viewport-fit=cover` le cas échéant | Aucun contrôle sous une zone non sûre | S,V | As (réel : H) | majeure | |
| STK-08 | Défilement bloqué après fermeture d'un dialogue, d'un menu ou d'un tiroir | `overflow: hidden` ou `position: fixed` restant sur `body` ou `html` sans dialogue ouvert (`play_scenarios.py`) | Défilement restauré | C,S | A | majeure | |
| STK-07 | Tiroir ou panneau : scroll interne, dépassement, fermeture | Contenu long dans le panneau, tabulation, Échap | Scroll interne, fermeture, focus géré | C,A | A | modérée | |

## Textes et typographie (TXT)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| TXT-01 | Contraste texte/fond insuffisant | Calcul sur les couleurs calculées (et sur pixels si le fond est une image ou un dégradé) ; seuils de référence 4.5:1 et 3:1 pour le grand texte (WCAG 2.2 SC 1.4.3, à vérifier) | Seuils de l'exigence applicable | S,V | A (fond complexe : As) | majeure | ✓ |
| TXT-02 | Hiérarchie de titres incohérente | Séquence `h1..h6` ; un seul `h1` si c'est la convention projet ; correspondance visuelle et sémantique | Hiérarchie sans saut trompeur | S,A | A | modérée | |
| TXT-03 | Longueur de ligne, interlignage, taille de base | Mesure (caractères par ligne, line-height) | Selon le DS ; à défaut, valeur de référence citée et sourcée | S | A | mineure `[PRÉFÉRENCE]` sauf exigence | |
| TXT-04 | Espacement de texte imposé par l'utilisateur casse la mise en page | Injecter les surcharges de WCAG SC 1.4.12 (interlignage 1.5, espacement des paragraphes 2×, lettres 0.12em, mots 0.16em, à vérifier) | Pas de perte de contenu ou de fonction | S,V | A | majeure | |
| TXT-05 | Police de secours ou échec de chargement | Bloquer les requêtes de police ; capture | Mise en page tenue ; pas d'invisibilité prolongée du texte (FOIT) | V,C | A | modérée | |
| TXT-06 | Libellés ambigus, jargon, capitalisation et ponctuation incohérentes | Revue du texte contre le guide de rédaction du projet | Libellés explicites (verbe et objet pour les actions) | H | As | mineure à modérée | |
| TXT-07 | Messages inutiles (« Erreur », « Une erreur est survenue ») | Recenser les messages d'erreur et de statut | Le message dit ce qui s'est passé et quoi faire | H | As | modérée | |
| TXT-08 | Contenus exceptionnellement longs (nom de 80 caractères, mot sans espace, URL) | Jeu de données `fixtures/edge-text` | Pas de débordement (`overflow-wrap`) | V,S | A | majeure | |

## Contrôles et actions (CTA)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| CTA-01 | **Texte dépassant d'un bouton** | GEO-03 appliqué aux éléments à rôle `button` ou `link` stylés en bouton, dans toutes les langues et à 200 % de zoom | Libellé contenu dans la surface | S,V | A | majeure | ✓ |
| CTA-02 | **Bouton décalé ou mal placé** (hors du groupe d'actions, ordre incohérent, action principale peu visible) | GEO-02 + ordre visuel vs ordre DOM + convention de placement du DS et de la plateforme | Placement conforme au DS ; action principale identifiable | V,S | As | modérée à majeure | ✓ |
| CTA-03 | Cible trop petite ou trop rapprochée | Mesurer la boîte cliquable effective (padding inclus) ; référence minimale 24×24 px CSS ou espacement équivalent (WCAG 2.2 SC 2.5.8, à vérifier) ; plateformes tactiles : guidelines de l'OS (à vérifier, souvent plus grandes) | Seuil de l'exigence applicable | S | A | majeure (tactile) | ✓ |
| CTA-04 | Icône mal alignée dans son bouton | Centre de l'icône vs centre de la boîte et baseline du texte | Écart ≤ tolérance | V,S | A | mineure | |
| CTA-05 | État désactivé incompréhensible | Raison exposée ? Alternative ? `aria-disabled` vs `disabled` (focusabilité) | L'utilisateur comprend pourquoi et comment débloquer | C,H | As | modérée | |
| CTA-06 | Double clic ou soumission répétée | Double clic rapide et Entrée répétée sur une soumission ; compter les requêtes | Une seule action ; feedback d'attente | C | A | majeure (critique si paiement) | |
| CTA-07 | Action destructive sans protection | Recenser les actions irréversibles | Confirmation proportionnée ou annulation possible | C,H | As | majeure | |
| CTA-08 | Affordance (un lien ressemble à du texte, un bouton à un label) | Revue visuelle et états hover et focus | Interactif perçu comme tel | V,H | As | modérée | |
| CTA-09 | Raccourcis clavier conflictuels ou non documentés | Lister les raccourcis ; conflits avec le navigateur, l'OS ou les technologies d'assistance ; raccourcis à une seule touche désactivables (WCAG SC 2.1.4, à vérifier) | Pas de conflit ; découvrabilité | C | As | modérée | |
| CTA-10 | Priorité des actions (plusieurs boutons primaires concurrents) | Compter les variantes primaires par vue | Une action principale par contexte, sauf justification | V | As | mineure `[PRÉFÉRENCE]` sauf DS | |

## Formulaires (FRM)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| FRM-01 | Champ sans label accessible ; placeholder utilisé comme label | Arbre d'accessibilité : nom de chaque champ ; présence d'un label visible | Label visible et nom accessible cohérents | S,A | A | majeure | ✓ |
| FRM-02 | Aide et format attendus absents | Revue des champs à format (date, téléphone, IBAN...) | Format indiqué avant la saisie | H,V | As | modérée | |
| FRM-03 | **Erreur mal signalée** (loin du champ, couleur seule, non annoncée, non liée) | Soumettre invalide : message près du champ, `aria-invalid`, lien `aria-describedby`, focus déplacé ou résumé, annonce (région live ou focus), icône ou texte en plus de la couleur | Erreur identifiée, décrite, liée, perceptible sans couleur, annoncée | C,A,V | A+As | majeure | ✓ |
| FRM-04 | Perte des valeurs saisies (erreur serveur, retour arrière, rechargement, changement de taille) | Saisir, provoquer l'événement, comparer | Valeurs conservées (sauf champs sensibles, par choix documenté) | C | A | majeure | |
| FRM-05 | Validation trop précoce ou agressive | Observer la validation à la frappe | Validation au blur ou à la soumission, sauf justification | C,H | As | modérée | |
| FRM-06 | `autocomplete`, types d'entrée et `inputmode` | Vérifier les attributs sur les champs d'identité, adresse, paiement, OTP | Attributs pertinents | S | A | modérée | |
| FRM-07 | Mot de passe : affichage, collage, gestionnaire | Bouton afficher/masquer, collage autorisé, `autocomplete=current-password/new-password` | Pas d'obstacle à la saisie (cf. WCAG 2.2 SC 3.3.8, à vérifier) | C,S | A | majeure | |
| FRM-08 | Upload de fichier : formats, taille, progression, erreur, annulation | Fichiers valides, trop gros, mauvais type, réseau coupé | Feedback et récupération | C | As | modérée | |
| FRM-09 | Saisie redondante | Parcours en plusieurs étapes | Pas de ressaisie inutile (WCAG SC 3.3.7, à vérifier) | C | As | modérée | |
| FRM-10 | Sauvegarde, annulation et reprise d'un brouillon | Quitter au milieu, revenir | Comportement conforme aux attentes déclarées | C | As | modérée | |
| FRM-11 | Masques de saisie bloquants | Collage, effacement, curseur au milieu | Pas de blocage | C | As | modérée | |

## Couleurs et médias (COL)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| COL-01 | Information portée par la couleur seule | Revue des statuts, erreurs, liens dans le texte, légendes ; capture en niveaux de gris ou simulation de daltonisme | Second indicateur (texte, icône, motif) | V,H | As | majeure | ✓ |
| COL-02 | Contraste des composants non textuels (bordures de champ, icônes porteuses de sens, focus) | Calcul ; référence 3:1 (WCAG SC 1.4.11, à vérifier) | Seuil de l'exigence | S | A | majeure | |
| COL-03 | Thèmes clair et sombre ou contraste élevé incomplets | Captures dans chaque thème supporté ; `forced-colors: active` | Pas d'élément invisible ni de couleur codée en dur incohérente | V,S | A | majeure | |
| COL-04 | Images manquantes, déformées ou mal recadrées | Statut réseau des images, `naturalWidth`, ratio affiché vs naturel, `object-fit` | Pas d'image cassée ; ratio respecté | S,V | A | modérée | |
| COL-05 | Texte alternatif absent ou inadapté | `alt` présent ; décoratif (`alt=""`) vs informatif ; pertinence jugée | Alternative équivalente | A,H | As | majeure si informatif | |
| COL-06 | Icônes seules incompréhensibles | Icônes sans libellé ; nom accessible | Libellé visible ou tooltip et nom accessible | V,A | As | modérée | |
| COL-07 | Vidéo et audio : sous-titres, transcription, autoplay, contrôles | Recensement des médias | Alternatives et contrôle utilisateur | A,H | As | majeure si contenu essentiel | |

## Navigation et architecture (NAV)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| NAV-01 | Où suis-je ? (menu actif, titre de page, fil d'Ariane) | `aria-current`, `<title>` unique et descriptif, état visuel | Repérage clair | S,V | A | modérée | ✓ |
| NAV-02 | Liens cassés, ancres mortes | Crawl du périmètre | Aucun lien mort | S | A | majeure | |
| NAV-03 | Retour, historique, liens profonds | Recharger une URL interne, bouton retour après navigation et après filtre | État restauré ; pas d'écran blanc | C | A | majeure | |
| NAV-04 | Recherche, filtres, pagination : état dans l'URL, reset, zéro résultat | Scénarios combinés | Comportement prévisible ; état vide utile | C | As | modérée | |
| NAV-05 | Cohérence entre écrans (position de la navigation, terminologie) | Comparer les captures de plusieurs écrans | Cohérence (WCAG SC 3.2.3 et 3.2.4, à vérifier) | V | As | modérée | |
| NAV-06 | Découvrabilité des actions essentielles (masquées dans un menu à 320 px) | Captures responsive + inventaire des actions | Actions essentielles accessibles à toutes les tailles | V,C | As | majeure | |
| NAV-07 | Progression dans un flux multi-étapes | Indicateur d'étape, retour sans perte | Progression claire | V,C | As | modérée | |

## Parcours et feedback (PAR)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| PAR-01 | La tâche principale est-elle réalisable de bout en bout ? | Script du parcours (souris, puis clavier seul) | Succès observé | C | A | critique si échec | ✓ |
| PAR-02 | Effort (étapes, champs, clics) disproportionné | Compter les étapes et comparer aux références | Pas d'étape superflue identifiée | H | As | `[PRÉFÉRENCE]`/modérée | |
| PAR-03 | Feedback absent ou tardif après une action | Mesurer le délai entre l'action et le premier changement visible | Feedback perceptible rapidement (seuil projet) | C | A | modérée | |
| PAR-04 | États d'attente, de succès et d'erreur non conçus | Forcer chaque état (mock réseau) | Chaque état a un rendu et un message utiles | C,V | A | majeure | |
| PAR-05 | Erreurs non récupérables, impasses | Provoquer les erreurs, vérifier les issues | Toujours une issue (réessayer, revenir, contacter) | C | As | majeure | |
| PAR-06 | Session expirée et interruption (onglet en arrière-plan, perte réseau, appel) | Simuler l'expiration et la mise en arrière-plan | Message clair ; données préservées si possible | C | As | majeure | |
| PAR-08 | Action sans effet (bouton mort) | Clic puis observation : DOM, URL, défilement, requêtes, nouvelle fenêtre (`play_scenarios.py`) | Toute action produit un effet ou un retour perceptible | C | A | majeure | |
| PAR-07 | Confirmation disproportionnée (trop ou pas assez) | Revue | Proportionnée au risque | H | H | `[PRÉFÉRENCE]`/modérée | |

## Accessibilité (ACC)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| ACC-01 | Règles automatisées (moteur de type axe-core ou équivalent) | Exécution sur chaque état capturé | 0 violation sérieuse ou critique ; les autres sont triées | S | A | selon la règle | ✓ |
| ACC-02 | Navigation au clavier complète | Tab, Maj+Tab, Entrée, Espace, flèches dans les widgets composites, Échap | Toutes les fonctions atteignables et activables | C,A | A | critique si une action essentielle est inatteignable | ✓ |
| ACC-03 | **Focus piégé** | Tabuler N fois (N = nombre d'éléments focalisables + 5) et vérifier la sortie de chaque composant ; une modale doit retenir le focus **et** proposer Échap ou fermer | Aucun piège hors modale ; modale fermable (WCAG SC 2.1.2, à vérifier) | C,A | A | critique | ✓ |
| ACC-04 | Focus visible et ordre logique | Capture de chaque arrêt de focus ; contraste de l'indicateur ; ordre vs ordre visuel | Indicateur visible ; ordre cohérent | V,C,A | A+As | majeure | ✓ |
| ACC-05 | Noms, rôles et états accessibles | Arbre d'accessibilité : bouton sans nom, rôle ARIA erroné, `aria-expanded` ou `aria-selected` non synchronisés | Exposition correcte | S,A | A | majeure | ✓ |
| ACC-06 | Annonces dynamiques (toasts, résultats, erreurs) | Régions live ou `role=status/alert` ; déclenchement effectif | Changements importants annoncés (WCAG SC 4.1.3, à vérifier) | S,A | As | majeure | |
| ACC-07 | Zoom 200 % et texte agrandi | Zoom navigateur 200 % ; taille de police de base agrandie | Pas de perte de contenu ni de fonction (SC 1.4.4, à vérifier) | V,S | A | majeure | |
| ACC-08 | Reflow à 320 px CSS de largeur (équivaut à 1280 px à 400 %) | Viewport 320 × 256 pour le contenu à défilement horizontal, 320 de large en général | Pas de scroll 2D, sauf contenus exemptés (SC 1.4.10, à vérifier) | S,V | A | majeure | |
| ACC-09 | Gestes complexes ou glisser-déposer sans alternative | Recenser swipe, pinch, drag | Alternative à pointeur unique (SC 2.5.1 et 2.5.7, à vérifier) | C | As | majeure | |
| ACC-10 | Landmarks et lien d'évitement | `main`, `nav`, `header`, skip link fonctionnel | Structure présente | S | A | modérée | |
| ACC-11 | **Test avec lecteur d'écran réel** (NVDA, JAWS, VoiceOver, TalkBack) | Parcours principal au lecteur d'écran | Restitution compréhensible | A,H | **H** (assisté si un pilote automatisé existe) | - | |
| ACC-12 | Langue de la page et des passages | `lang` présent et correct | Prononciation correcte | S | A | modérée | |

Règle : ACC-11 n'est **jamais** marqué `réussi` sur la seule base de l'arbre d'accessibilité. Sans test réel, statut `non vérifié : nécessite lecteur d'écran`.

## Mouvement (MOT)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| MOT-01 | `prefers-reduced-motion` ignoré | Émuler `reduce` ; comparer les animations actives | Animations non essentielles supprimées ou réduites | C,S | A | majeure | |
| MOT-02 | Clignotements dangereux | Recenser les animations à fréquence élevée ; référence : pas plus de 3 flashs par seconde (SC 2.3.1, à vérifier) | Conforme | V,C | As | critique | |
| MOT-03 | Contenu animé ou défilant sans pause | Carrousels, auto-play > 5 s | Pause, arrêt ou masquage (SC 2.2.2, à vérifier) | C | As | majeure | |
| MOT-04 | Transition qui casse l'état (focus perdu, double rendu, saut) | Enregistrer la transition (vidéo ou trace) ; vérifier le focus et le contenu après | Transition sans perte d'état | C | As | modérée | |
| MOT-05 | Durées et easings incohérents avec le DS | Comparer aux tokens de mouvement | Conforme au DS | S | A | mineure `[PRÉFÉRENCE]` | |

## Données complexes (DAT)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| DAT-01 | Tableau : en-têtes, associations, tri annoncé | `th`, `scope`, `aria-sort` | Structure exposée | S,A | A | majeure | |
| DAT-02 | Tableau sur mobile (débordement, colonnes essentielles masquées) | 320 à 430 px | Stratégie explicite (scroll conteneurisé accessible, empilement, priorisation) | V,S | As | majeure | |
| DAT-03 | Graphique : légende, unités, axes, arrondis cohérents | Revue et comparaison avec les données source | Lecture non ambiguë | V,H | As | modérée | |
| DAT-04 | Alternative accessible aux visualisations | Tableau de données, résumé textuel | Présente | A | As | majeure si information essentielle | |
| DAT-05 | Valeurs manquantes, nulles, extrêmes ; grands volumes (10 000 lignes) | Fixtures `empty`, `null`, `huge`, `negative` | Rendu sain ; performance acceptable ; pas de « NaN » ou « undefined » affiché | V,C | A | majeure | |
| DAT-06 | Sélection multiple, actions de masse | Sélectionner, désélectionner, tout sélectionner sur plusieurs pages | État clair et cohérent | C | As | modérée | |

## Localisation (LOC) : si plusieurs langues ou locales sont pertinentes

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| LOC-01 | **Traduction plus longue** qui déborde | Langue cible réelle la plus longue et pseudo-localisation (+30 à 40 %, accents, délimiteurs `[ ]`) | Pas de débordement ni de rognage | V,S | A | majeure | |
| LOC-02 | Chaînes non traduites ou concaténées | Pseudo-locale : repérer le texte sans délimiteurs | Tout est externalisé | S | A | modérée | |
| LOC-03 | Pluriels, genres | Valeurs 0, 1, 2, 5, 21 selon les règles CLDR de la langue | Formes correctes | V | As | modérée | |
| LOC-04 | Dates, heures, fuseaux, nombres, devises | Locales cibles ; fuseau différent de celui du serveur | Formats locaux ; fuseau explicite si ambigu | V | A | modérée à majeure (finance) | |
| LOC-05 | Écritures non latines (CJK, arabe, devanagari) : polices, hauteur de ligne | Fixtures multiscripts | Glyphes rendus ; pas de rognage vertical | V | A | majeure si langue supportée | |
| LOC-06 | Droite-gauche (RTL) et bidirectionnel | `dir=rtl` ; propriétés logiques CSS ; icônes directionnelles en miroir | Mise en page en miroir correcte | V,S | As | majeure si RTL supporté | |

## Robustesse et compatibilité (ROB)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| ROB-01 | Erreurs console et exceptions non gérées pendant les parcours | Journal console et réseau | Aucune erreur nouvelle liée au périmètre | S | A | majeure | ✓ |
| ROB-02 | Navigateurs cibles | Moteurs Chromium, WebKit et Gecko selon `browserslist` ou la cible déclarée | Rendu et fonctions équivalents | V,C | A | majeure | |
| ROB-03 | Modes d'entrée : souris, tactile, clavier, hybrides | `pointer: coarse/fine`, `hover: none` ; vérifier qu'aucune fonction ne dépend du survol seul | Fonctionnel dans chaque mode | C | A | majeure | |
| ROB-04 | Réseau lent, interrompu, reprise | Bridage réseau (profil lent), mode hors ligne en cours de parcours | Indicateurs, messages, reprise | C | A | majeure | |
| ROB-05 | Chargement partiel, service indisponible (API en 500 ou timeout) | Mock d'erreurs par endpoint | Dégradation gracieuse ; pas d'écran blanc | C | A | majeure | |
| ROB-06 | Orientation et redimensionnement **en cours d'usage** | Changer d'orientation ou de taille avec un formulaire rempli, une modale ouverte, un scroll avancé | État, focus et saisie conservés | C | A | majeure | |

## Performance perçue (PRF)

Une mesure instrumentée (API Performance, traces, métriques de type Core Web Vitals) se distingue d'une impression (« semble lent »). Le rapport indique laquelle des deux il s'agit.

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| PRF-01 | Délai de réponse à l'interaction | Mesure du délai entre l'entrée et le rendu suivant (instrumentée) | Seuil projet ou référence sourcée | C | A | modérée | |
| PRF-02 | Squelettes et indicateurs de progression | Présence et cohérence avec la forme finale (pas de saut) | Conforme | V,C | As | modérée | |
| PRF-03 | Blocage du thread principal (tâches longues) | Trace de performance | Pas de gel perceptible pendant les interactions du parcours | C | A | modérée | |
| PRF-04 | Stabilité au chargement | Cf. GEO-09 | - | | | | |

## Permissions et erreurs (PRM)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| PRM-01 | Permission demandée hors contexte (dès le chargement) | Observer le moment de la demande | Demande liée à une action explicite, avec explication préalable | C,H | As | modérée | |
| PRM-02 | Refus de permission | Émuler un refus (géolocalisation, caméra, notifications) | Message exploitable, alternative, pas d'impasse | C | A | majeure | |
| PRM-03 | Permission révoquée en cours d'usage | Révoquer puis réutiliser | Détection et message | C | As | modérée | |
| PRM-04 | Fonction inaccessible (droits insuffisants) | Compte de test à rôle limité | Explication et chemin d'obtention, pas de bouton mort silencieux | C | As | modérée | |
| PRM-05 | Possibilité de réessayer après une erreur | Provoquer l'erreur | Action de réessai disponible | C | A | modérée | |

## Design system et régressions (DS)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| DS-01 | Valeurs codées en dur au lieu des tokens | Analyse statique du diff (couleurs hex, px hors échelle) et styles calculés hors palette | Usage des tokens | S | A | modérée | ✓ |
| DS-02 | Composant réimplémenté au lieu d'être réutilisé | Revue du diff vs catalogue de composants | Réutilisation | S,H | As | modérée | |
| DS-03 | Variantes incohérentes (même rôle, styles différents) | Regrouper les éléments par rôle et comparer les styles | Cohérence | V,S | As | modérée | |
| DS-04 | Terminologie incohérente | Glossaire projet vs libellés | Cohérence | H | As | mineure | |
| DS-05 | Régression visuelle hors périmètre | Diff visuel des écrans du rayon d'impact (avant/après) | Différences toutes expliquées | V | A | selon le défaut | |
| DS-06 | Propagation de la correction | Revérifier toutes les instances du composant ou token corrigé | Instances conformes | V,S | A | majeure si une instance casse | |

---


## Environnement mobile (ENV)

| ID | Contrôle | Méthode | Limite |
|---|---|---|---|
| ENV-01 | Safe areas et encoches | Émulation des insets, usage de `env(safe-area-inset-*)` et `viewport-fit=cover` | Appareil réel pour confirmer |
| ENV-02 | Clavier virtuel masquant une action | `resize_probe.py --mode keyboard` : champ focalisé et action principale atteignables, non recouverts, sans défilement seulement programmatique | Émulation resizes-content. Le clavier natif, le mode resizes-visual et les barres système demandent un émulateur d'OS ou un appareil. |
| ENV-03 | Barres du navigateur mobile | Recherche de `100vh` sur des éléments plein écran. Préférer `svh`, `lvh` et `dvh` selon l'intention. | Émulateur d'OS recommandé |
| ENV-04 | Modes d'entrée | Viewports `pointer: coarse` et `fine`, clavier seul. Aucune fonction ne doit dépendre du survol seul. | |
| ENV-05 | Préférences utilisateur | `--theme dark`, `--reduced-motion reduce`, `--forced-colors`, contraste élevé si le moteur le permet | |
| ENV-06 | Zoom et taille du texte | `--zoom 2` (200 %), `--zoom 4` avec 1280 px (reflow), police de base agrandie via `eval` | |
