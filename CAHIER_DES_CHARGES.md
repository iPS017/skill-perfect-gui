# Cahier des charges : Skill d'audit et d'amélioration UI/UX

| Champ | Valeur |
|---|---|
| Nom de travail du skill | `ui-audit-gate` (provisoire) |
| Version du document | 1.0 du 2026-10-11 |
| Statut | Spécification. Rien n'est implémenté à ce stade. |
| Destinataires | Implémenteur du skill (humain ou Claude) et responsable produit qui arbitre les choix ouverts (§15) |

## 0. Conventions de lecture

**Force des exigences.** Le vocabulaire est inspiré de la RFC 2119 :
- **DOIT / NE DOIT PAS** : obligatoire. Un manquement bloque la conformité du skill.
- **DEVRAIT** : recommandé. Un écart est possible s'il est justifié dans le rapport.
- **PEUT** : optionnel.

**Nature des affirmations.** Le skill et ses rapports étiquettent chaque constat ou recommandation avec l'une de ces trois natures :
- `[EXIGENCE]` : découle d'une règle explicite (norme applicable, critère d'acceptation, design system, contrat fonctionnel). Elle peut bloquer.
- `[HYPOTHÈSE]` : plausible mais non démontrée (comportement d'un appareil non testé, intention de l'utilisateur, public supposé). Elle doit être vérifiée ou assumée explicitement.
- `[PRÉFÉRENCE]` : jugement esthétique ou stylistique. Elle ne bloque jamais seule.

**Identifiants.** `EX-xxx` désigne une exigence du skill, `CTL-xxx` un contrôle de la matrice, `DEF-xxx` un défaut, `REF-xxx` une référence Web, `SCN-xx` un scénario d'acceptation et `RUN-xxx` une exécution d'audit.

**Seuils chiffrés.** Tout seuil cité ici, par exemple un ratio de contraste ou une taille de cible, est indicatif. Il est rattaché à sa source supposée (en général WCAG 2.2). Le skill DOIT revérifier la version applicable au projet (WCAG, RGAA, EN 301 549, guidelines de plateforme) au moment de l'audit, et l'exigence projet prime toujours.

---

## 1. Résumé et principes

### 1.1 Résumé

Le skill est une **barrière qualité** qui s'interpose entre « j'ai modifié l'interface » et « c'est validé ». À chaque création ou modification d'interface, il :

1. délimite le périmètre réellement touché, y compris les effets indirects ;
2. capture l'état avant, puis l'état après, dans des conditions comparables ;
3. mène une **recherche Web réelle et tracée** pour situer la solution par rapport à des références pertinentes ;
4. exécute l'interface, interagit avec elle et l'inspecte (rendu, structure, styles, accessibilité, comportements) ;
5. consigne des défauts reproductibles, priorisés et étayés par des preuves ;
6. corrige dans le périmètre autorisé ou propose des correctifs et, si un arbitrage existe, des variantes argumentées ;
7. revérifie, recapture et contrôle les régressions ;
8. rend une **décision de validation explicite et bornée** : ce qui a été vérifié, comment, et ce qui ne l'a pas été.

### 1.2 Principes directeurs

| # | Principe | Conséquence opérationnelle |
|---|---|---|
| P1 | **Le produit réel prime sur le code lu.** | Pas de validation sans rendu exécuté, sauf en mode dégradé déclaré. |
| P2 | **Trois natures de vérification distinctes** : visuelle, comportementale, assistive. | Une capture correcte ne valide ni un parcours ni l'accessibilité. Chaque contrôle déclare sa nature. |
| P3 | **Honnêteté de couverture.** | Un test non exécuté porte le statut `non vérifié`, jamais `réussi`. L'absence de défaut détecté n'est pas l'absence de défaut. |
| P4 | **Proportionnalité au risque.** | Niveaux d'audit N1, N2 et N3 (§3.5). Toute réduction de couverture est visible et motivée. |
| P5 | **Exigence, hypothèse, préférence.** | Une préférence esthétique ne bloque jamais seule. |
| P6 | **Recherche réelle, jamais inventée.** | Chaque référence a une URL consultée pendant l'audit ou une revalidation datée. Une référence fabriquée est une faute bloquante du skill. |
| P7 | **Corriger la cause, pas le symptôme.** | Préférer le token, le composant ou la règle partagée au correctif local, puis propager et revérifier les instances. |
| P8 | **Autonomie raisonnable.** | Exploiter le contexte disponible, ne poser que les questions bloquantes et avancer avec des hypothèses réversibles documentées. |
| P9 | **Confidentialité.** | Aucune capture ni donnée sensible n'est envoyée à un moteur de recherche ou à un service tiers non autorisé. |
| P10 | **Pas de promesse universelle.** | Le skill réduit le risque de défauts. Il ne garantit ni une interface sans bug ni une compatibilité exhaustive. |

### 1.3 Ce que le skill n'est pas

- Ni un substitut aux tests utilisateurs : ses appréciations sont heuristiques.
- Ni un audit de conformité légale certifiant : il peut préparer un audit RGAA ou WCAG, pas le remplacer.
- Ni un générateur de tendances visuelles : il n'impose pas un style au détriment de la lisibilité, de la cohérence ou des contraintes métier.
- Ni un test exhaustif sur appareils réels lorsqu'il ne dispose que d'émulation.

---

## 2. Glossaire minimal

| Terme | Définition retenue |
|---|---|
| **Périmètre modifié** | Ensemble des écrans, composants et états dont le rendu ou le comportement peut changer à cause de la demande. |
| **Rayon d'impact** | Périmètre modifié plus les consommateurs indirects (instances d'un composant partagé, écrans utilisant un token modifié). |
| **Viewport CSS** | Dimensions en pixels CSS exposées à la page (`window.innerWidth`, media queries). À distinguer de la résolution physique, de la résolution de capture (viewport × devicePixelRatio) et de l'échelle d'affichage de l'OS. |
| **Simulation** | Reproduction approximative : redimensionnement de fenêtre, maquette statique. |
| **Émulation** | Mode appareil d'un navigateur ou d'un émulateur d'OS (Android Emulator, iOS Simulator), avec UA, DPR, tactile et parfois posture. |
| **Appareil réel** | Matériel physique, local ou distant (ferme d'appareils). Seul niveau qui valide les comportements matériels : clavier virtuel réel, charnière, capteurs, performances. |
| **Preuve** | Artefact conservé (capture, extrait DOM, valeur calculée, journal, vidéo, sortie d'outil) qui permet à un tiers de constater un résultat. |
| **Run** | Une exécution horodatée du protocole, avec son manifeste d'environnement. |

---

## 3. Périmètre et déclenchement

### 3.1 Déclencheurs

Le skill DOIT être déclenché lorsqu'une demande ou un changement relève d'au moins une des catégories suivantes :

| Code | Déclencheur | Exemples |
|---|---|---|
| T1 | Nouvelle interface | nouvel écran, page, composant, modale, flux |
| T2 | Changement de style | couleurs, espacements, typographie, ombres, rayons, thèmes |
| T3 | Changement de contenu | libellés, messages, traductions, contenu dynamique affiché |
| T4 | Changement de structure | réorganisation du DOM, de la grille ou de la hiérarchie des titres |
| T5 | Composant partagé | bouton, champ, carte, en-tête, layout, primitive du design system |
| T6 | Comportement | interactions, validation, raccourcis, gestion du focus, animations |
| T7 | Navigation | routes, menus, liens profonds, historique, redirections |
| T8 | États | chargement, vide, erreur, succès, désactivé, permissions |
| T9 | Données affichées | format, volume, tri, graphiques, tableaux |
| T10 | Responsive | breakpoints, conteneurs, orientation, safe areas |
| T11 | **Changement indirect** | police, design token, CSS global, reset, dépendance UI (mise à jour de bibliothèque de composants), configuration de build CSS, i18n |

### 3.2 Détection des changements indirects (T11)

Le skill DOIT construire un **inventaire d'impact** :

1. **Sources de changement.** Fichiers modifiés (diff du VCS si disponible, sinon liste fournie ou déduite de la session).
2. **Classification** de chaque fichier : `token`, `style-global`, `composant-partagé`, `composant-local`, `page`, `contenu/i18n`, `logique-UI`, `dépendance`, `config-build`.
3. **Propagation** :
   - `token` / `style-global` / `dépendance` / `config-build` : rechercher les usages (grep du nom de token ou de variable CSS, imports du composant, graphe d'import si un outil le fournit). Faute de graphe fiable, considérer **tous les écrans principaux** comme potentiellement touchés et échantillonner (§7.8).
   - `composant-partagé` : lister les consommateurs et les variantes utilisées.
   - `contenu/i18n` : lister les écrans affichant les clés modifiées, dans chaque langue supportée.
4. **Sortie** : `impact.json` (schéma §11.2), avec pour chaque zone le niveau de confiance de la détection (`certain` si l'usage est trouvé statiquement, `probable` s'il est inféré, `inconnu`).

Pseudocode :

```text
fonction inventaire_impact(changements):
    zones = {}
    pour f dans changements:
        type = classifier(f)
        si type ∈ {token, style-global, dépendance, config-build}:
            usages = chercher_usages(f)            # grep, graphe d'import
            si usages non fiable:
                zones += écrans_principaux(confiance="probable")
            sinon:
                zones += usages(confiance="certain")
        sinon si type == composant-partagé:
            zones += consommateurs(f) × variantes_utilisées(f)
        sinon:
            zones += écrans_contenant(f)
    retourner dédoublonner(zones)
```

### 3.3 Activation : honnêteté sur les mécanismes

Un fichier de consignes (`SKILL.md`, `CLAUDE.md`, etc.) **augmente la probabilité** d'activation mais **ne la garantit pas** dans tous les environnements : l'activation dépend de la description du skill, du contexte et de l'agent hôte. Le cahier des charges impose donc trois couches complémentaires :

| Couche | Mécanisme | Garantie |
|---|---|---|
| C1 : Déclenchement sémantique | Description du skill rédigée pour couvrir les déclencheurs T1 à T11 (mots-clés FR et EN : UI, UX, GUI, interface, écran, page, composant, formulaire, CSS, style, responsive, etc.). | Probabiliste |
| C2 : Invocation explicite | Commande utilisateur (`/ui-audit` ou équivalent) et mention dans `CLAUDE.md` du projet : « toute modification d'interface passe par ui-audit-gate avant d'être déclarée terminée ». | Fiable quand utilisée |
| C3 : Barrière mécanique (optionnelle, recommandée) | Hook de l'hôte (par exemple un hook de fin de tâche ou post-édition dans Claude Code) ou étape CI qui détecte des fichiers UI modifiés sans rapport d'audit valide associé, puis bloque ou avertit. | Déterministe dans l'environnement configuré |

EX-ACT-01 : Le skill DOIT documenter les trois couches et indiquer dans chaque rapport **comment il a été déclenché** (C1, C2 ou C3).
EX-ACT-02 : Le skill NE DOIT PAS affirmer qu'il est « toujours actif » si C3 n'est pas installée.
EX-ACT-03 : Tant que le rapport n'a pas atteint une décision (§12), l'agent NE DOIT PAS déclarer la modification « terminée », « validée » ou « prête ». Il PEUT dire « implémentée, audit en cours » ou « implémentée, audit partiel : voir limites ».

### 3.4 Environnements visés

| Priorité | Environnement | Méthode principale | Limites connues |
|---|---|---|---|
| 1 | **Web** (sites, SPA, PWA) | Navigateur automatisable : captures, DOM, styles calculés, arbre d'accessibilité, interactions, émulation d'appareil | L'émulation ne reproduit ni le clavier virtuel réel, ni la charnière, ni les performances matérielles. Lecteurs d'écran réels non pilotés par défaut. |
| 2 | **Hybride** (WebView, Electron, Tauri, Capacitor) | Partie Web : idem, via débogage distant de la WebView si exposé. Shell natif : comme le natif. | Accès au débogage distant variable selon la configuration de build. |
| 3 | **Natif mobile** (iOS, Android) | Simulateur ou émulateur et outils d'UI testing de la plateforme (hiérarchie de vues, identifiants d'accessibilité, captures). Inspecteurs d'accessibilité de la plateforme. | Nécessite le SDK et souvent un OS hôte spécifique (iOS : macOS). Sans intégration, pas d'inspection structurelle : audit visuel seulement. |
| 3 | **Desktop natif** (Windows, macOS, Linux) | API d'accessibilité de l'OS (UI Automation, AX API, AT-SPI), outils de computer use, captures d'écran | Inspection structurelle très dépendante de l'outillage disponible. |
| 4 | **Maquette statique** (image, export Figma) | Audit visuel partiel : hiérarchie, alignements, contrastes approximatifs, cohérence | **Aucune validation d'interaction, de responsive réel ou d'accessibilité structurelle.** Statut plafonné à `validation limitée, maquette`. |

### 3.5 Entrées minimales

| Entrée | Obligatoire | Source prioritaire | Si absente |
|---|---|---|---|
| Demande utilisateur | Oui | Conversation | Bloquant |
| Interface à ouvrir (URL, commande de lancement, build, simulateur) | Oui pour un audit complet | Scripts du projet (`package.json`, README, Makefile), conversation | Tenter la détection, puis demander. Sinon mode dégradé « sans rendu ». |
| Périmètre modifié | Oui | Diff VCS, historique de session | Inférer et documenter en `[HYPOTHÈSE]` |
| Objectif des utilisateurs / tâche principale | Recommandé | Demande, README, specs, contenu de l'écran | Inférer depuis l'écran, marquer `[HYPOTHÈSE]` |
| Parcours importants | Recommandé | Specs, tests E2E existants, routes | Déduire 1 à 3 parcours de l'écran, marquer `[HYPOTHÈSE]` |
| Contraintes existantes (design system, marque, normes, navigateurs cibles) | Recommandé | Dépôt (tokens, `browserslist`, docs), conversation | Ne pas inventer. Appliquer WCAG 2.2 AA comme base d'accessibilité **seulement si** rien ne le contredit, et le signaler. |
| Critères d'acceptation | Recommandé | Ticket, demande | Dériver des critères minimaux et les afficher |
| Langues, publics, appareils cibles | Optionnel | Config i18n, analytics fournis | **Ne pas supposer.** Couvrir la matrice générique (§7) et signaler l'hypothèse. |
| Autorisation de corriger | Oui | Conversation, mode de permission de l'hôte | Par défaut : corriger dans le périmètre de la demande initiale. Hors périmètre : proposer seulement. |

EX-IN-01 : Le skill DOIT exploiter les sources disponibles (dépôt, conversation, configuration) **avant** de poser une question.
EX-IN-02 : Le skill NE DOIT poser une question que si la réponse change le déroulé et qu'aucun choix réversible raisonnable n'existe. Les questions sont regroupées en une seule fois.
EX-IN-03 : Toute hypothèse prise faute d'information DOIT figurer dans la section « Hypothèses » du rapport, avec son impact si elle est fausse.

### 3.6 Niveaux d'audit proportionnés au risque

| Niveau | Quand | Couverture |
|---|---|---|
| **N1 : Périmètre** (toujours) | Toute modification déclenchante | Contrôles **fondamentaux** (§6.1) sur le périmètre modifié, viewports prioritaires (§7.3, niveau P0), états touchés, recherche Web ciblée |
| **N2 : Voisinage** | Composant partagé, changement de comportement, de navigation ou de formulaire, ou défaut trouvé en N1 | N1 + régressions sur consommateurs et écrans adjacents, viewports P0+P1, états connexes, clavier complet du parcours |
| **N3 : Approfondi** | Token ou style global, refonte, parcours critique (paiement, authentification, données personnelles, action destructive), demande explicite | N2 + matrice étendue (P2, préférences utilisateur, localisation, réseau dégradé, pliables), échantillonnage large, revue assistive |

Règles de sélection :

```text
niveau = N1
si impact contient {composant-partagé, logique-UI, navigation, formulaire}: niveau = max(niveau, N2)
si impact contient {token, style-global, dépendance, config-build}: niveau = N3
si parcours ∈ parcours_critiques: niveau = N3
si demande utilisateur précise un niveau: niveau = demande (une baisse est justifiée dans le rapport)
```

EX-LVL-01 : Les contrôles fondamentaux (§6.1) DOIVENT être exécutés à tous les niveaux, sauf impossibilité technique documentée.
EX-LVL-02 : Toute réduction sous le niveau calculé DOIT apparaître dans le rapport (« Couverture réduite : N3 → N2 ; raison : ... ; risque résiduel : ... »).

---

## 4. Exigences numérotées et testables

Chaque exigence est vérifiable par un test du skill lui-même (scénarios §13 ou revue d'un rapport produit).

### 4.1 Workflow

| ID | Exigence | Vérification |
|---|---|---|
| EX-WF-01 | Le skill DOIT exécuter les 9 étapes du §5 dans l'ordre, chacune produisant ses preuves de sortie ou un statut `non vérifié` motivé. | Le rapport contient les 9 sections d'étape. |
| EX-WF-02 | L'état initial DOIT être capturé **avant** toute modification lorsqu'il existe. Pour une création, le rapport DOIT l'indiquer, et le premier rendu exploitable devient la référence (`baseline=first-render`). | Présence de `before/` ou de la mention explicite. |
| EX-WF-03 | Chaque capture DOIT être accompagnée d'un manifeste (viewport CSS, DPR, zoom, thème, langue, préférences, jeu de données, étapes de navigation, version ou commit, navigateur et version). | Fichier `manifest.json` par capture ou par lot. |
| EX-WF-04 | Après toute correction, les contrôles concernés DOIVENT être relancés et les captures refaites **dans les mêmes conditions** que l'avant. | Paires avant/après avec manifestes identiques hors version. |
| EX-WF-05 | La boucle « corriger → revérifier » DOIT être bornée (par défaut : 3 itérations par anomalie, 6 au total par run). Au-delà, le défaut passe en `échoué : non résolu` avec cause et action requise. | Compteur dans le journal. |
| EX-WF-06 | Les données de test DOIVENT être déterministes pour les comparaisons visuelles (horloge figée, seed, réponses réseau simulées si nécessaire, animations désactivées ou attendues). | Le manifeste référence le jeu de données. |
| EX-WF-07 | Les transitions et comportements asynchrones DOIVENT faire l'objet de contrôles **séparés** des captures stabilisées. | Contrôles de nature `comportementale` présents. |

### 4.2 Recherche Web

| ID | Exigence |
|---|---|
| EX-REF-01 | Une recherche Web réelle DOIT être tentée à chaque audit déclenché. |
| EX-REF-02 | Chaque référence retenue DOIT avoir les champs du schéma §8.4. Une URL non consultée dans ce run, ou non revalidée, NE DOIT PAS être présentée comme consultée. |
| EX-REF-03 | La réutilisation d'une référence antérieure DOIT passer par une revalidation (URL accessible, contenu toujours pertinent, version de norme à jour), avec la date de revalidation. Sans revalidation, la référence est marquée `mémoire non revalidée` et ne compte pas comme recherche du run. |
| EX-REF-04 | Le rapport DOIT contenir le tableau de comparaison du §8.5 pour chaque référence retenue. |
| EX-REF-05 | En cas d'indisponibilité du Web, le rapport DOIT indiquer `Recherche Web : non réalisée`, la cause, et la décision NE PEUT PAS dépasser `validée : périmètre testé` (§12). |
| EX-REF-06 | Aucune capture, donnée ou extrait confidentiel ne DOIT figurer dans les requêtes de recherche. |

### 4.3 Couverture et états

| ID | Exigence |
|---|---|
| EX-COV-01 | Chaque contrôle exécuté DOIT référencer un identifiant de la matrice (§6) ou une extension projet déclarée. |
| EX-COV-02 | Chaque contrôle DOIT déclarer sa nature (`visuel`, `structurel`, `comportemental`, `assistif`, `humain`) et son niveau d'exécution (`automatisé`, `assisté`, `manuel/humain`). |
| EX-COV-03 | Les combinaisons (contrôle × état × configuration) exécutées ET celles exclues DOIVENT être listées (§7.8). |
| EX-COV-04 | Un viewport émulé NE DOIT PAS être présenté comme un test sur l'appareil réel correspondant. |
| EX-COV-05 | Les noms d'appareils cités DOIVENT être vérifiés dans des sources officielles datées. Un nom non vérifiable est remplacé par une classe d'écran (§7.5). |

### 4.4 Défauts, corrections et validation

| ID | Exigence |
|---|---|
| EX-DEF-01 | Chaque défaut DOIT être reproductible et décrit selon la fiche §11.3. Les observations et les interprétations sont séparées. |
| EX-DEF-02 | Sévérité, priorité, confiance et effort sont quatre champs distincts (§9). |
| EX-COR-01 | Chaque correction DOIT indiquer cause probable, composants affectés, risques et contrôles de non-régression. |
| EX-COR-02 | Si la cause est commune (token, composant), la correction DOIT viser la cause et lister les instances revérifiées. |
| EX-VAL-01 | Aucun contrôle non exécuté NE DOIT porter le statut `réussi`. |
| EX-VAL-02 | La décision finale DOIT appartenir à l'ensemble défini au §12.3 et respecter ses conditions. |
| EX-VAL-03 | Une exception sur un défaut bloquant DOIT être acceptée explicitement par l'utilisateur, avec identité ou rôle et date. Le skill ne s'auto-accorde jamais d'exception. |

### 4.5 Sécurité et autorisations

| ID | Exigence |
|---|---|
| EX-SEC-01 | Le skill DOIT respecter le mode de permission de l'hôte et les autorisations données dans la session. |
| EX-SEC-02 | Les parcours à effet externe (paiement, envoi d'e-mail, suppression, publication) DOIVENT être testés avec des données ou environnements de test. Sinon ils sont arrêtés avant l'action irréversible, après confirmation explicite. |
| EX-SEC-03 | Les captures contenant des données personnelles ou confidentielles DOIVENT être anonymisées (floutage, données fictives) avant tout partage hors de la machine locale, et ne sont jamais envoyées à un service tiers sans autorisation. |
| EX-SEC-04 | Les secrets (jetons, mots de passe de test) NE DOIVENT PAS apparaître dans les rapports ni les journaux. |

---

## 5. Procédure (workflow obligatoire)

Vue d'ensemble :

```text
[1 Cadrer] → [2 Capturer l'avant] → [3 Rechercher] → [4 Exécuter et capturer]
     → [5 Inspecter et croiser] → [6 Consigner et prioriser] → [7 Corriger / proposer]
     → [8 Revérifier] ──(défauts restants et itérations < limite)──→ [7]
     → [9 Rapporter et décider]
```

Note d'ordonnancement : quand le skill est invoqué **avant** que l'agent code la modification, les étapes 1 à 3 précèdent l'implémentation et l'étape 4 suit. Invoqué **après**, l'état « avant » est reconstruit via le VCS (checkout ou stash de la révision précédente dans un worktree isolé) si possible. Sinon `baseline=indisponible`, et ce point est documenté.

### Étape 1 : Cadrer

- **Entrées** : demande, dépôt, conversation, diff.
- **Actions** : reformuler l'objectif ; inventorier écrans, composants et dépendances (§3.2) ; identifier les parcours touchés et les risques ; calculer le niveau N1/N2/N3 ; lister les hypothèses ; détecter les capacités outillées (§10.2) ; poser les questions bloquantes en un seul lot.
- **Preuves** : `scope.md` (objectif, critères d'acceptation, hypothèses), `impact.json`, `capabilities.json`.
- **Sortie** : périmètre vérifiable figé ; niveau d'audit et justification.

### Étape 2 : Capturer l'état initial

- **Entrées** : périmètre, révision précédente.
- **Actions** : lancer la version antérieure ; capturer les écrans et états du périmètre sur la configuration P0 (§7.3) ; enregistrer les métriques structurelles clés (dimensions des éléments du périmètre, arbre d'accessibilité de la zone).
- **Preuves** : `before/<config>/<écran>-<état>.png` + manifestes.
- **Sortie** : baseline disponible, `first-render` ou `indisponible` (justifié).

### Étape 3 : Rechercher des références Web

Protocole détaillé au §8.

- **Sortie** : 2 à 5 références retenues (au-delà, justification requise), comparaison remplie, ou statut `non réalisée` motivé.

### Étape 4 : Exécuter et capturer l'interface modifiée

- **Actions** : lancer l'application (serveur de dev, build, simulateur) ; vérifier qu'elle répond, puis attendre la stabilisation (réseau inactif, polices chargées via `document.fonts.ready` ou équivalent, animations terminées ou désactivées) ; parcourir les états et configurations sélectionnés (§7) ; **réaliser les interactions** des parcours (clic, saisie, clavier, tactile émulé, redimensionnement en cours d'usage) ; enregistrer pour chaque capture viewport, DPR, zoom, thème, langue, préférences, données et étapes.
- **Preuves** : `after/...` + manifestes ; journaux console et réseau ; vidéo ou trace pour les transitions si l'outil le permet.
- **Sortie** : ensemble de captures et de traces couvrant la sélection, avec les combinaisons non réalisées listées.

### Étape 5 : Inspecter et croiser

- **Actions** (selon les capacités disponibles) :
  - **Visuel** : analyse des captures (alignements, rognage, superpositions, hiérarchie).
  - **Structurel** : DOM, styles calculés, boîtes (`getBoundingClientRect`), `scrollWidth > clientWidth`, z-index et contextes d'empilement, `elementFromPoint` au centre des cibles pour détecter le masquage.
  - **Accessibilité** : moteur de règles automatisé (type axe-core), arbre d'accessibilité (rôles, noms, états), ordre de tabulation réel, visibilité du focus.
  - **Comportemental** : résultats des interactions (soumission, erreurs, retour, persistance d'état).
  - **Natif** : hiérarchie de vues ou arbre d'accessibilité de la plateforme, à défaut audit visuel seul.
- Chaque constat est rattaché à un `CTL-xxx`.
- **Sortie** : liste brute de constats, chacun avec sa preuve.

### Étape 6 : Consigner et prioriser

- **Actions** : dédoublonner (un défaut, plusieurs instances) ; reproduire chaque défaut au moins deux fois (ou expliquer pourquoi la reproduction est intermittente) ; séparer `observé` et `interprété` ; attribuer sévérité, priorité, confiance et effort (§9) ; étiqueter `[EXIGENCE]`, `[HYPOTHÈSE]` ou `[PRÉFÉRENCE]` ; regrouper par cause commune probable.
- **Preuves** : `findings/DEF-xxx.json` + captures annotées.
- **Sortie** : backlog priorisé.

### Étape 7 : Corriger ou proposer

- **Actions** : pour chaque défaut dans le périmètre autorisé, appliquer la correction à la cause ; propager aux instances. Hors périmètre ou sans autorisation : proposer un correctif concret (diff ou description précise). Préparer des variantes seulement si un arbitrage existe (§9.4). Poser une question uniquement pour un arbitrage réellement nécessaire.
- **Sortie** : corrections appliquées (liste des fichiers) et propositions en attente.

### Étape 8 : Revérifier

- **Actions** : relancer les contrôles des défauts corrigés ; **recapturer** dans les conditions de l'avant ; exécuter les contrôles de non-régression déclarés dans chaque fiche de correction ; diff visuel avant/après (pixel ou perceptuel, avec seuil projet) en interprétant chaque différence (attendue ou régression) ; vérifier les instances propagées.
- **Boucle** : si un défaut persiste ou qu'une régression apparaît, retour à l'étape 7, dans la limite de EX-WF-05.
- **Sortie** : statuts finaux par contrôle et par défaut.

### Étape 9 : Rapporter et décider

- **Actions** : produire le rapport (§11.4) ; calculer la décision (§12) ; lister les défauts résiduels, les limites et les actions humaines requises.
- **Sortie** : `report.md` (+ `report.json` lisible par machine) et décision annoncée dans la conversation.

### 5.1 Déterminisme et stabilisation

| Source de variabilité | Mesure |
|---|---|
| Date et heure | Horloge figée (mock de `Date`) ou valeurs fixes injectées |
| Aléatoire | Seed ou mock de `Math.random` |
| Réseau | Réponses enregistrées ou mockées pour les captures. Le réseau réel est testé séparément. |
| Polices | Attendre leur chargement. Tester aussi séparément le rendu de secours (police bloquée). |
| Animations | Désactivées ou mises à leur état final pour les captures. Testées séparément en contrôle comportemental (`MOT-*`). |
| Contenu tiers (pubs, cartes, embeds) | Masqué ou remplacé par un bloc de même taille pour le diff, et signalé |
| Curseur, caret clignotant | Masqués pour les captures |
| Anticrénelage et rendu GPU | Tolérance de diff, et même machine ou même image de conteneur entre avant et après |

### 5.2 Limite de boucle et échec honnête

```text
pour chaque défaut d:
    tentatives = 0
    tant que d non résolu et tentatives < 3 et total_itérations < 6:
        corriger(d); revérifier(d); tentatives += 1
    si d non résolu:
        d.statut = "échoué, non résolu"
        d.cause_blocage = diagnostic
        d.action_requise = "décision produit" | "info manquante" | "outil manquant" | "hors périmètre"
```

Le skill NE DOIT PAS contourner un échec par un ajustement qui masque le symptôme (par exemple `overflow: hidden` sur du texte coupé, ou `z-index: 9999` sans analyser le contexte d'empilement) sans le déclarer comme palliatif.

---

## 6. Matrice de couverture

### 6.0 Schéma d'un contrôle

```yaml
id: GEO-03                      # famille-numéro
famille: Géométrie et mise en page
risque: "Texte débordant de son conteneur ou rogné"
contexte: "Tout élément à texte de largeur contrainte (boutons, badges, cellules, onglets)"
nature: [visuel, structurel]     # visuel | structurel | comportemental | assistif | humain
automatisation: automatisé       # automatisé | assisté | humain
méthode: >
  Pour chaque élément textuel : scrollWidth > clientWidth + 1 ou scrollHeight > clientHeight + 1
  avec overflow != visible → rognage ; enfant débordant le rect parent → débordement.
  Confirmer visuellement sur capture.
états: [normal, hover, focus, chargement]
configurations: [P0, contenu-long, langue-longue, zoom-200]
attendu: "Aucun texte rogné sans affordance (ellipsis + accès au texte complet)"
preuve: [capture-annotée, valeurs-mesurées]
sévérité_indicative: majeure     # ajustée selon l'impact réel
source_seuil: null               # ou "WCAG 2.2 SC 1.4.10" / "exigence projet X"
fondamental: true                # exécuté à tous les niveaux
statut: à-exécuter               # réussi | échoué | non-vérifié | non-applicable
```

La matrice est livrée en YAML ou JSON (`controls/*.yaml`). Le tableau ci-dessous en est la vue synthétique. **Extension projet** : un fichier `controls/project/*.yaml` ajoute des contrôles propres au projet (composants maison, contraintes métier) avec le même schéma, et peut désactiver un contrôle générique avec une justification (`disabled_reason`).

Légende des colonnes : **Nat.** V=visuel, S=structurel, C=comportemental, A=assistif, H=humain. **Auto.** A=automatisé, As=assisté, H=humain. **F** = fondamental (✓).

### 6.1 Contrôles fondamentaux (exécutés à tous les niveaux)

GEO-01, GEO-02, GEO-03, GEO-05, STK-01, STK-02, TXT-01, CTA-01, CTA-02, CTA-03, FRM-01, FRM-03 (si formulaire), COL-01, NAV-01, PAR-01, ACC-01, ACC-02, ACC-03, ACC-04, ACC-05, ROB-01, DS-01, ainsi que la couverture des viewports P0 (§7.3).

### 6.2 Géométrie et mise en page (GEO)

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

### 6.3 Empilement et positionnement (STK)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| STK-01 | **Superposition masquant une action** | Pour chaque élément interactif visible : `elementFromPoint` au centre et aux 4 coins intérieurs ; l'élément retourné doit être la cible ou son descendant | Toute cible interactive cliquable en son centre | S,C | A | critique si action essentielle | ✓ |
| STK-02 | Élément fixed ou sticky recouvrant du contenu ou le focus | Pendant la tabulation, vérifier que l'élément focalisé n'est pas entièrement masqué par un élément fixe (cf. WCAG 2.2 SC 2.4.11, à vérifier) ; `scroll-padding` | Focus et contenu ancré visibles | S,A | A | majeure | ✓ |
| STK-03 | Modale : fond scrollable, fermeture, restitution du focus | Ouvrir, puis Échap, clic sur le fond, bouton de fermeture ; vérifier `inert` ou `aria-modal`, le focus initial et le retour du focus au déclencheur | Focus contenu, fermeture possible, retour du focus | C,A | A | majeure | |
| STK-04 | Popover, menu ou tooltip hors viewport ou mal ancré | Ouvrir près des 4 bords et à 320 px ; rect ⊂ viewport | Repositionnement (flip/shift) ; contenu entier visible | S,V | A | majeure | |
| STK-05 | Contexte d'empilement inattendu (z-index sans effet) | Remonter les ancêtres qui créent un contexte (`transform`, `opacity<1`, `filter`, `isolation`, `position+z-index`) | Ordre d'empilement conforme à l'intention | S | As | modérée | |
| STK-06 | Safe areas (encoche, barre d'accueil) | Émulation avec insets ; vérifier l'usage de `env(safe-area-inset-*)` et `viewport-fit=cover` le cas échéant | Aucun contrôle sous une zone non sûre | S,V | As (réel : H) | majeure | |
| STK-07 | Tiroir ou panneau : scroll interne, dépassement, fermeture | Contenu long dans le panneau, tabulation, Échap | Scroll interne, fermeture, focus géré | C,A | A | modérée | |

### 6.4 Textes et typographie (TXT)

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

### 6.5 Contrôles et actions (CTA)

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

### 6.6 Formulaires (FRM)

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

### 6.7 Couleurs et médias (COL)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| COL-01 | Information portée par la couleur seule | Revue des statuts, erreurs, liens dans le texte, légendes ; capture en niveaux de gris ou simulation de daltonisme | Second indicateur (texte, icône, motif) | V,H | As | majeure | ✓ |
| COL-02 | Contraste des composants non textuels (bordures de champ, icônes porteuses de sens, focus) | Calcul ; référence 3:1 (WCAG SC 1.4.11, à vérifier) | Seuil de l'exigence | S | A | majeure | |
| COL-03 | Thèmes clair et sombre ou contraste élevé incomplets | Captures dans chaque thème supporté ; `forced-colors: active` | Pas d'élément invisible ni de couleur codée en dur incohérente | V,S | A | majeure | |
| COL-04 | Images manquantes, déformées ou mal recadrées | Statut réseau des images, `naturalWidth`, ratio affiché vs naturel, `object-fit` | Pas d'image cassée ; ratio respecté | S,V | A | modérée | |
| COL-05 | Texte alternatif absent ou inadapté | `alt` présent ; décoratif (`alt=""`) vs informatif ; pertinence jugée | Alternative équivalente | A,H | As | majeure si informatif | |
| COL-06 | Icônes seules incompréhensibles | Icônes sans libellé ; nom accessible | Libellé visible ou tooltip et nom accessible | V,A | As | modérée | |
| COL-07 | Vidéo et audio : sous-titres, transcription, autoplay, contrôles | Recensement des médias | Alternatives et contrôle utilisateur | A,H | As | majeure si contenu essentiel | |

### 6.8 Navigation et architecture (NAV)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| NAV-01 | Où suis-je ? (menu actif, titre de page, fil d'Ariane) | `aria-current`, `<title>` unique et descriptif, état visuel | Repérage clair | S,V | A | modérée | ✓ |
| NAV-02 | Liens cassés, ancres mortes | Crawl du périmètre | Aucun lien mort | S | A | majeure | |
| NAV-03 | Retour, historique, liens profonds | Recharger une URL interne, bouton retour après navigation et après filtre | État restauré ; pas d'écran blanc | C | A | majeure | |
| NAV-04 | Recherche, filtres, pagination : état dans l'URL, reset, zéro résultat | Scénarios combinés | Comportement prévisible ; état vide utile | C | As | modérée | |
| NAV-05 | Cohérence entre écrans (position de la navigation, terminologie) | Comparer les captures de plusieurs écrans | Cohérence (WCAG SC 3.2.3 et 3.2.4, à vérifier) | V | As | modérée | |
| NAV-06 | Découvrabilité des actions essentielles (masquées dans un menu à 320 px) | Captures responsive + inventaire des actions | Actions essentielles accessibles à toutes les tailles | V,C | As | majeure | |
| NAV-07 | Progression dans un flux multi-étapes | Indicateur d'étape, retour sans perte | Progression claire | V,C | As | modérée | |

### 6.9 Parcours et feedback (PAR)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| PAR-01 | La tâche principale est-elle réalisable de bout en bout ? | Script du parcours (souris, puis clavier seul) | Succès observé | C | A | critique si échec | ✓ |
| PAR-02 | Effort (étapes, champs, clics) disproportionné | Compter les étapes et comparer aux références | Pas d'étape superflue identifiée | H | As | `[PRÉFÉRENCE]`/modérée | |
| PAR-03 | Feedback absent ou tardif après une action | Mesurer le délai entre l'action et le premier changement visible | Feedback perceptible rapidement (seuil projet) | C | A | modérée | |
| PAR-04 | États d'attente, de succès et d'erreur non conçus | Forcer chaque état (mock réseau) | Chaque état a un rendu et un message utiles | C,V | A | majeure | |
| PAR-05 | Erreurs non récupérables, impasses | Provoquer les erreurs, vérifier les issues | Toujours une issue (réessayer, revenir, contacter) | C | As | majeure | |
| PAR-06 | Session expirée et interruption (onglet en arrière-plan, perte réseau, appel) | Simuler l'expiration et la mise en arrière-plan | Message clair ; données préservées si possible | C | As | majeure | |
| PAR-07 | Confirmation disproportionnée (trop ou pas assez) | Revue | Proportionnée au risque | H | H | `[PRÉFÉRENCE]`/modérée | |

### 6.10 Accessibilité (ACC)

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

### 6.11 Mouvement (MOT)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| MOT-01 | `prefers-reduced-motion` ignoré | Émuler `reduce` ; comparer les animations actives | Animations non essentielles supprimées ou réduites | C,S | A | majeure | |
| MOT-02 | Clignotements dangereux | Recenser les animations à fréquence élevée ; référence : pas plus de 3 flashs par seconde (SC 2.3.1, à vérifier) | Conforme | V,C | As | critique | |
| MOT-03 | Contenu animé ou défilant sans pause | Carrousels, auto-play > 5 s | Pause, arrêt ou masquage (SC 2.2.2, à vérifier) | C | As | majeure | |
| MOT-04 | Transition qui casse l'état (focus perdu, double rendu, saut) | Enregistrer la transition (vidéo ou trace) ; vérifier le focus et le contenu après | Transition sans perte d'état | C | As | modérée | |
| MOT-05 | Durées et easings incohérents avec le DS | Comparer aux tokens de mouvement | Conforme au DS | S | A | mineure `[PRÉFÉRENCE]` | |

### 6.12 Données complexes (DAT)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| DAT-01 | Tableau : en-têtes, associations, tri annoncé | `th`, `scope`, `aria-sort` | Structure exposée | S,A | A | majeure | |
| DAT-02 | Tableau sur mobile (débordement, colonnes essentielles masquées) | 320 à 430 px | Stratégie explicite (scroll conteneurisé accessible, empilement, priorisation) | V,S | As | majeure | |
| DAT-03 | Graphique : légende, unités, axes, arrondis cohérents | Revue et comparaison avec les données source | Lecture non ambiguë | V,H | As | modérée | |
| DAT-04 | Alternative accessible aux visualisations | Tableau de données, résumé textuel | Présente | A | As | majeure si information essentielle | |
| DAT-05 | Valeurs manquantes, nulles, extrêmes ; grands volumes (10 000 lignes) | Fixtures `empty`, `null`, `huge`, `negative` | Rendu sain ; performance acceptable ; pas de « NaN » ou « undefined » affiché | V,C | A | majeure | |
| DAT-06 | Sélection multiple, actions de masse | Sélectionner, désélectionner, tout sélectionner sur plusieurs pages | État clair et cohérent | C | As | modérée | |

### 6.13 Localisation (LOC) : si plusieurs langues ou locales sont pertinentes

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| LOC-01 | **Traduction plus longue** qui déborde | Langue cible réelle la plus longue et pseudo-localisation (+30 à 40 %, accents, délimiteurs `[ ]`) | Pas de débordement ni de rognage | V,S | A | majeure | |
| LOC-02 | Chaînes non traduites ou concaténées | Pseudo-locale : repérer le texte sans délimiteurs | Tout est externalisé | S | A | modérée | |
| LOC-03 | Pluriels, genres | Valeurs 0, 1, 2, 5, 21 selon les règles CLDR de la langue | Formes correctes | V | As | modérée | |
| LOC-04 | Dates, heures, fuseaux, nombres, devises | Locales cibles ; fuseau différent de celui du serveur | Formats locaux ; fuseau explicite si ambigu | V | A | modérée à majeure (finance) | |
| LOC-05 | Écritures non latines (CJK, arabe, devanagari) : polices, hauteur de ligne | Fixtures multiscripts | Glyphes rendus ; pas de rognage vertical | V | A | majeure si langue supportée | |
| LOC-06 | Droite-gauche (RTL) et bidirectionnel | `dir=rtl` ; propriétés logiques CSS ; icônes directionnelles en miroir | Mise en page en miroir correcte | V,S | As | majeure si RTL supporté | |

### 6.14 Robustesse et compatibilité (ROB)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| ROB-01 | Erreurs console et exceptions non gérées pendant les parcours | Journal console et réseau | Aucune erreur nouvelle liée au périmètre | S | A | majeure | ✓ |
| ROB-02 | Navigateurs cibles | Moteurs Chromium, WebKit et Gecko selon `browserslist` ou la cible déclarée | Rendu et fonctions équivalents | V,C | A | majeure | |
| ROB-03 | Modes d'entrée : souris, tactile, clavier, hybrides | `pointer: coarse/fine`, `hover: none` ; vérifier qu'aucune fonction ne dépend du survol seul | Fonctionnel dans chaque mode | C | A | majeure | |
| ROB-04 | Réseau lent, interrompu, reprise | Bridage réseau (profil lent), mode hors ligne en cours de parcours | Indicateurs, messages, reprise | C | A | majeure | |
| ROB-05 | Chargement partiel, service indisponible (API en 500 ou timeout) | Mock d'erreurs par endpoint | Dégradation gracieuse ; pas d'écran blanc | C | A | majeure | |
| ROB-06 | Orientation et redimensionnement **en cours d'usage** | Changer d'orientation ou de taille avec un formulaire rempli, une modale ouverte, un scroll avancé | État, focus et saisie conservés | C | A | majeure | |

### 6.15 Performance perçue (PRF)

Une mesure instrumentée (API Performance, traces, métriques de type Core Web Vitals) se distingue d'une impression (« semble lent »). Le rapport indique laquelle des deux il s'agit.

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| PRF-01 | Délai de réponse à l'interaction | Mesure du délai entre l'entrée et le rendu suivant (instrumentée) | Seuil projet ou référence sourcée | C | A | modérée | |
| PRF-02 | Squelettes et indicateurs de progression | Présence et cohérence avec la forme finale (pas de saut) | Conforme | V,C | As | modérée | |
| PRF-03 | Blocage du thread principal (tâches longues) | Trace de performance | Pas de gel perceptible pendant les interactions du parcours | C | A | modérée | |
| PRF-04 | Stabilité au chargement | Cf. GEO-09 | - | | | | |

### 6.16 Permissions et erreurs (PRM)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| PRM-01 | Permission demandée hors contexte (dès le chargement) | Observer le moment de la demande | Demande liée à une action explicite, avec explication préalable | C,H | As | modérée | |
| PRM-02 | Refus de permission | Émuler un refus (géolocalisation, caméra, notifications) | Message exploitable, alternative, pas d'impasse | C | A | majeure | |
| PRM-03 | Permission révoquée en cours d'usage | Révoquer puis réutiliser | Détection et message | C | As | modérée | |
| PRM-04 | Fonction inaccessible (droits insuffisants) | Compte de test à rôle limité | Explication et chemin d'obtention, pas de bouton mort silencieux | C | As | modérée | |
| PRM-05 | Possibilité de réessayer après une erreur | Provoquer l'erreur | Action de réessai disponible | C | A | modérée | |

### 6.17 Design system et régressions (DS)

| ID | Défaut recherché | Méthode | Attendu | Nat. | Auto. | Sév. ind. | F |
|---|---|---|---|---|---|---|---|
| DS-01 | Valeurs codées en dur au lieu des tokens | Analyse statique du diff (couleurs hex, px hors échelle) et styles calculés hors palette | Usage des tokens | S | A | modérée | ✓ |
| DS-02 | Composant réimplémenté au lieu d'être réutilisé | Revue du diff vs catalogue de composants | Réutilisation | S,H | As | modérée | |
| DS-03 | Variantes incohérentes (même rôle, styles différents) | Regrouper les éléments par rôle et comparer les styles | Cohérence | V,S | As | modérée | |
| DS-04 | Terminologie incohérente | Glossaire projet vs libellés | Cohérence | H | As | mineure | |
| DS-05 | Régression visuelle hors périmètre | Diff visuel des écrans du rayon d'impact (avant/après) | Différences toutes expliquées | V | A | selon le défaut | |
| DS-06 | Propagation de la correction | Revérifier toutes les instances du composant ou token corrigé | Instances conformes | V,S | A | majeure si une instance casse | |

---

## 7. États et configurations à explorer

### 7.1 États

| Code | État | Comment le provoquer |
|---|---|---|
| S-INIT | Initial (premier rendu) | Chargement à froid |
| S-NORM | Normal, données typiques | Fixture `typical` |
| S-HOV | Hover | Survol programmatique (pointeur fin uniquement) |
| S-FOC | Focus (clavier) | Tab ; `:focus-visible` |
| S-ACT | Actif (pressé) | Pointeur enfoncé |
| S-SEL | Sélectionné, coché, ouvert | Interaction |
| S-DIS | Désactivé | Condition métier |
| S-LOAD | Chargement | Réponse réseau retardée |
| S-EMPTY | Vide | Fixture `empty` |
| S-ERR | Erreur (champ, page, réseau, serveur) | Saisie invalide, mocks 4xx et 5xx, hors ligne |
| S-OK | Succès | Parcours complet |
| S-VAL | Validation en cours | Validation asynchrone retardée |
| S-DLG | Dialogue ou overlay ouvert | Interaction |
| S-INT | Interruption | Arrière-plan, expiration, perte réseau, redimensionnement |

**Transitions** à tester explicitement, en plus des états finaux : `LOAD→OK`, `LOAD→ERR`, `ERR→correction→OK`, `NORM→DLG→NORM` (focus restitué), `NORM→resize/orientation→NORM` (état conservé), `OK→retour arrière`, `INT→reprise`.

Tous les contrôles ne s'appliquent pas à tous les états. La matrice déclare `états` par contrôle (§6.0), et le croisement se fait par cette déclaration, pas par produit cartésien complet.

### 7.2 Distinguer les dimensions

| Dimension | Définition | Exemple de manifeste |
|---|---|---|
| Viewport CSS | `innerWidth × innerHeight` en px CSS | `390×844` |
| DPR | `devicePixelRatio` | `3` |
| Résolution de capture | viewport × DPR (ou capture à DPR 1) | `1170×2532` |
| Zoom navigateur | Facteur de zoom de la page | `200%` |
| Échelle de l'OS | Mise à l'échelle système | `125%` (desktop) |
| Taille de texte utilisateur | Taille de police par défaut et préférences de texte dynamique | `+50%` |

### 7.3 Matrice de viewports Web (pixels CSS)

Ces largeurs représentent des **classes**. Elles ne correspondent à aucun appareil précis. Les dimensions d'un appareil donné se vérifient dans une source officielle datée au moment de l'audit.

| Priorité | Classe | Largeur × hauteur (CSS px) | Raison |
|---|---|---|---|
| P0 | Mobile étroit | 320 × 640 | Plancher de reflow (WCAG 1.4.10) ; petits téléphones, écrans externes de certains pliables |
| P0 | Mobile courant | 390 × 844 | Classe la plus répandue des téléphones récents (à recaler sur les analytics si fournies) |
| P0 | Desktop courant | 1366 × 768 puis 1440 × 900 | Laptops |
| P1 | Mobile large | 430 × 932 | Grands téléphones |
| P1 | Mobile paysage | 844 × 390 | Hauteur réduite + clavier virtuel |
| P1 | Tablette portrait | 768 × 1024 et 820 × 1180 | Tablettes |
| P1 | Tablette paysage | 1024 × 768 et 1180 × 820 | |
| P1 | Desktop large | 1920 × 1080 | |
| P2 | Petit desktop ou fenêtre partagée | 1024 × 640, 960 × 1080 (moitié d'écran 1920) | Split screen, multitâche |
| P2 | Ultrawide | 2560 × 1080 et 3440 × 1440 | Longueur de ligne, étirement, vide |
| P2 | Hauteur très faible | 1280 × 600, 640 × 360 | Barres d'outils, modales hautes |
| P2 | Pliables | Classes du §7.5 | Si pertinent |

**Points de rupture** : le skill DOIT extraire les breakpoints réels du projet (media queries, container queries, config du framework CSS) et tester, pour chaque breakpoint `b` touché par le périmètre, les largeurs `b−1`, `b`, `b+1`, avec le contenu le plus long disponible.

### 7.4 Redimensionnement et multitâche en cours d'usage

Scénario type : formulaire à moitié rempli, focus dans un champ et modale ouverte. Le skill redimensionne de P0-desktop vers 960 px, puis vers 390 px, puis revient.
Vérifications : valeurs conservées, focus conservé ou restitué de façon logique, modale encore utilisable, pas de rechargement, scroll position cohérente.

### 7.5 Pliables (flip et livre)

**Sur les appellations.** La demande mentionne « Samsung Z Flip » et « Apple Duo ». Le skill DOIT, au moment de l'audit :
1. vérifier dans des sources officielles datées (site du constructeur, documentation développeur) l'appellation exacte, la disponibilité, les dimensions d'écran et les capacités navigateur exposées ;
2. **ne pas présenter « Apple Duo » comme un produit établi**. Ce nom ne correspond à aucun produit Apple que ce cahier des charges peut confirmer. S'il n'est pas vérifiable, le rapport l'indique et raisonne par classes. (Le « Surface Duo » de Microsoft est un appareil double écran distinct ; le rapprocher seulement si la source le confirme et si c'était bien l'intention.) ;
3. n'inventer aucune dimension.

**Classes d'écran à couvrir** (dimensions à renseigner depuis les sources vérifiées ou les profils d'émulation officiels) :

| Classe | Description | Points d'attention |
|---|---|---|
| F-FLIP-FERMÉ | Petit écran externe d'un pliable à clapet | Contenu minimal, cibles, texte tronqué ; souvent hors navigateur standard (à vérifier) |
| F-FLIP-OUVERT | Écran principal allongé (ratio très haut) | Hauteur importante, largeur de téléphone |
| F-LIVRE-FERMÉ | Écran externe étroit et haut | Largeur parfois inférieure à un téléphone classique |
| F-LIVRE-OUVERT | Écran interne quasi carré, proche d'une tablette | Breakpoint tablette vs mobile, deux colonnes |
| F-SEMI-PLIÉ | Posture « table » ou « livre » partiellement ouverte | Contenu coupé par la charnière ? Uniquement si la posture est exposée au Web |
| F-DOUBLE-ÉCRAN | Deux écrans séparés par une charnière physique | Segments de viewport |

**Transitions de pliage** (contrôle ROB-06 étendu) : fermé → ouvert → semi-plié → fermé, en cours de saisie, avec modale ouverte, pendant une lecture vidéo. Attendu : saisie, focus, progression et scroll conservés ; pas de rechargement ; mise en page adaptée.

**Charnière et segments.** Le skill NE DOIT tester l'évitement de la charnière que si l'information est exposée au Web et prise en charge par le navigateur cible : par exemple les media features de segments de viewport (`horizontal-viewport-segments` / `vertical-viewport-segments`), les variables `env(viewport-segment-*)` ou l'API Device Posture. Leur support se vérifie au moment de l'audit (spécifications W3C et tables de compatibilité). Sinon : `non applicable : non exposé` ou `non vérifié : nécessite appareil`.

**Émulation ≠ géométrie physique.** Une largeur émulée ne reproduit ni la charnière, ni la pliure, ni le changement d'écran actif. Le rapport l'indique explicitement.

### 7.6 Safe areas, clavier virtuel et barres du navigateur

| ID | Contrôle | Méthode | Limite |
|---|---|---|---|
| ENV-01 | Safe areas et encoches | Émulation des insets ; `env(safe-area-inset-*)` | Réel : appareil |
| ENV-02 | **Clavier virtuel masquant une action** | Émulation : réduire la hauteur du viewport visuel (Visual Viewport API) comme le ferait le clavier ; vérifier que le champ focalisé **et** le bouton de soumission restent atteignables (scroll possible, pas de pied fixe recouvrant). Vérifier les stratégies `interactive-widget` (meta viewport) ou VirtualKeyboard API si utilisées (support à vérifier). | Comportement réel du clavier = appareil ou émulateur d'OS. En navigateur desktop : `non vérifié : émulé seulement`. |
| ENV-03 | Barres du navigateur mobile qui apparaissent et disparaissent | Unités `svh`, `lvh`, `dvh` vs `vh` ; éléments en `100vh` coupés | Émulateur d'OS recommandé |
| ENV-04 | Modes d'entrée | `pointer`, `hover`, `any-pointer` ; tactile émulé ; clavier seul | - |
| ENV-05 | Préférences | `prefers-color-scheme`, `prefers-reduced-motion`, `prefers-contrast`, `forced-colors`, `prefers-reduced-transparency` (support à vérifier) | - |
| ENV-06 | Zoom et taille du texte | 200 %, 400 % (reflow), police de base agrandie | - |

### 7.7 Contenus (fixtures)

| Fixture | Contenu |
|---|---|
| `typical` | Données réalistes moyennes |
| `empty` | Aucune donnée |
| `minimal` | Un élément, champs optionnels absents |
| `long` | Textes de 2 à 3× la longueur typique, mots sans espace, URL longues, noms composés |
| `huge` | Volume (1 000 à 10 000 lignes, 50 onglets, 200 options de select) |
| `unexpected` | `null`, nombres négatifs, 0, très grands nombres, émojis, HTML échappé, espaces seuls |
| `i18n-pseudo` | Pseudo-localisation étendue de 40 % |
| `i18n-rtl` | Arabe ou hébreu, texte mixte LTR et RTL |
| `i18n-cjk` | Chinois, japonais, coréen |
| `sensitive-fake` | Identités et paiements fictifs pour les parcours sensibles |

### 7.8 Stratégie d'échantillonnage fondée sur le risque

But : éviter l'explosion combinatoire (contrôles × états × viewports × thèmes × langues × préférences) sans masquer les manques.

Algorithme :

```text
1. Socle obligatoire (toujours) :
   contrôles fondamentaux × états touchés × {P0}
   + parcours principal au clavier sur P0-desktop
   + parcours principal en tactile émulé sur P0-mobile-courant
2. Combinaisons critiques (selon l'impact) :
   - composant modifié × chaque variante utilisée × {320, breakpoints±1}
   - contenu modifié × {long, i18n la plus longue} × {320, 390}
   - formulaire modifié × {S-ERR, S-LOAD, S-OK} × {clavier, tactile}
   - overlay modifié × {4 bords, 320} × {ouvert, fermeture, focus restitué}
3. Couverture représentative (N2+) :
   1 viewport par classe P1 × états S-NORM, S-ERR × thème par défaut
   + chaque thème supporté × 1 viewport
4. Approfondissement ciblé (N3, ou si un défaut est trouvé) :
   une famille en défaut sur une config → tester les configs voisines
   (pairwise sur les dimensions restantes : thème × langue × préférence × viewport)
5. Consigner :
   coverage.json = { exécutées: [...], exclues: [{combinaison, raison, risque}] }
```

Le rapport affiche un **tableau de couverture** (§11.4, section Couverture). Toute phrase du type « testé sur tous les appareils » est interdite.

### 7.9 Simulation, émulation, réel

Chaque résultat porte `fidélité: simulation | émulation | réel`. Comportements **non validables sans réel** : clavier virtuel natif, charnière physique, performance tactile, lecteurs d'écran mobiles, capteurs, rendu de police propre à l'OS, comportement des barres système. Faute d'accès (appareil local ou ferme distante), ces contrôles sont `non vérifié : nécessite appareil réel`.

---

## 8. Recherche Web et comparaison des références

### 8.1 Obligation et traçabilité

- Une recherche est tentée **à chaque audit déclenché**, même en N1 (1 à 2 requêtes ciblées suffisent pour un petit changement).
- Le journal `research/log.json` enregistre chaque requête (texte, moteur ou outil, horodatage, nombre de résultats examinés). Les requêtes ne contiennent **aucune** donnée confidentielle (EX-REF-06) : elles décrivent le motif (« accessible inline form error pattern »), pas le produit.

### 8.2 Construction des requêtes

Paramètres issus du contexte : type de produit, tâche, plateforme, composant, design system existant, public **connu** (ne pas inventer), secteur.
Gabarits :
- `<composant> <plateforme> accessibility guidelines` (ex. « date picker accessibility pattern »)
- `<design system reconnu> <composant>` (Material, Apple HIG, Fluent, Carbon, GOV.UK Design System, DSFR si contexte français public, etc.)
- `<norme> <critère>` (« WCAG 2.2 target size minimum understanding »)
- `<tâche> UX research <secteur>` (sources reconnues de recherche UX)
- Pour les appareils : `<constructeur> <modèle> specifications site officiel`, `<API Web> browser support`

### 8.3 Hiérarchie des sources

| Rang | Type | Usage |
|---|---|---|
| 1 | Normes et documentation officielle (W3C/WAI, WHATWG, MDN, docs des plateformes Apple, Android, Microsoft, constructeurs) | Exigences, comportements, support |
| 2 | Design systems reconnus, publics ou d'entreprise | Patterns éprouvés, anatomie de composants |
| 3 | Recherche UX publiée (études, organismes reconnus) | Justification de comportement |
| 4 | Produits comparables (observés directement) | Conventions du secteur |
| 5 | Galeries visuelles et inspirations | **Inspiration uniquement, jamais preuve d'utilisabilité** |

### 8.4 Fiche de référence

```json
{
  "id": "REF-003",
  "titre": "Understanding SC 2.5.8: Target Size (Minimum)",
  "url": "https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html",
  "auteur_organisme": "W3C WAI",
  "date_consultation": "2026-10-11T14:32:00Z",
  "date_publication_ou_maj": "indiquée sur la page, ou null si absente",
  "statut_consultation": "consultée | revalidée | mémoire-non-revalidée | inaccessible",
  "rang_source": 1,
  "question_étudiée": "Taille minimale des icônes d'action de la barre d'outils",
  "constats_clés": ["...formulés avec les mots de la source, sans extrapolation..."],
  "limites_transposition": "Critère AA ; le projet vise-t-il AA ? Exceptions inline à examiner.",
  "utilisée_pour": ["DEF-007", "CTA-03"]
}
```

Les exemples d'URL de ce document sont illustratifs. Le skill NE DOIT citer que des URL effectivement consultées pendant le run.

### 8.5 Comparaison explicite

| Réf. | Observation dans notre interface | Principe illustré par la référence | Écart | Adaptation proposée | Bénéfice attendu | Nature |
|---|---|---|---|---|---|---|
| REF-003 | Icônes d'action de 20×20 px, espacées de 2 px | Cible minimale ou espacement équivalent | Sous le seuil | Zone cliquable de 24 px+ via padding, sans changer l'icône | Moins d'erreurs de toucher | `[EXIGENCE]` si AA visé |

Règles : pas de copie d'interface, de contenu ou d'identité visuelle. Pas d'imposition d'une tendance. Une recommandation normative est vérifiée dans **sa version applicable**. Une ressemblance visuelle avec un système conforme ne prouve pas la conformité.

### 8.6 Pertinence et arrêt

- **Retenir** une référence si elle répond à une question précise de l'audit, si sa source est de rang 1 à 3 (ou de rang 4 pour une convention de secteur) et si elle est transposable à la plateforme.
- **Arrêter** quand chaque question ouverte a au moins une référence de rang ≤ 3, ou après 2 tours de recherche sans nouvelle information utile.
- **Plafond indicatif** : 5 références retenues en N1 et N2, 8 en N3. Au-delà, justifier. Les liens « décoratifs » (sans usage dans un constat ou une recommandation) sont retirés.

### 8.7 Réutilisation

Un cache `research/cache.json` peut conserver les références d'audits précédents. Réutiliser = revalider (URL accessible, contenu inchangé sur le point utilisé, version de norme courante) + nouvelle `date_consultation` avec `statut_consultation: revalidée`. Une référence citée de mémoire sans revalidation est `mémoire-non-revalidée` : elle ne compte pas pour EX-REF-01 et ne peut fonder un `[EXIGENCE]` seule.

### 8.8 Web indisponible

- Consigner : `Recherche Web : non réalisée, cause : <outil absent | réseau | refus d'autorisation>`.
- Poursuivre tous les contrôles locaux.
- Les recommandations reposant sur des connaissances internes sont étiquetées `[HYPOTHÈSE, non sourcée en ligne]`.
- Conséquence sur la décision : **plafond `validée : périmètre testé`**, jamais `validée : protocole complet` (§12.3).

---

## 9. Corrections, variantes et priorisation

### 9.1 Sévérité (impact sur l'utilisateur)

| Niveau | Définition | Exemples |
|---|---|---|
| **Critique** | Empêche l'accomplissement d'une tâche essentielle pour tout ou partie des utilisateurs, sans contournement raisonnable ; ou risque de préjudice (perte de données, action irréversible involontaire, risque pour la santé comme le clignotement). | Bouton « Payer » masqué par une bannière sur mobile ; focus piégé ; parcours impossible au clavier |
| **Majeure** | Gêne fortement la tâche, provoque des erreurs fréquentes ou exclut un groupe (accessibilité), avec un contournement coûteux. | Texte de bouton rogné rendant l'action ambiguë ; erreur de formulaire non annoncée |
| **Modérée** | Ralentit ou trouble sans bloquer ; contournement simple. | Libellé ambigu ; alignement décalé visible ; état vide sans guidance |
| **Mineure** | Défaut cosmétique ou de cohérence, sans impact mesurable sur la tâche. | Espacement hors échelle de 2 px ; icône décalée d'1 px |

Facteurs d'ajustement : **fréquence** (écran principal ou rare), **étendue** (une instance ou un composant partagé), **contournement**, **population touchée**. Un défaut visuel peut être critique (il masque une action essentielle). Un défaut technique peut être mineur.

### 9.2 Quatre champs séparés

| Champ | Valeurs | Signification |
|---|---|---|
| Sévérité | critique, majeure, modérée, mineure | Impact |
| Priorité | P1 (avant validation), P2 (avant release), P3 (backlog) | Ordre de traitement (sévérité × fréquence × coût du retard) |
| Confiance | élevée (reproduit + preuve structurelle), moyenne (reproduit, cause supposée), faible (observé une fois, ou jugement heuristique) | Solidité du diagnostic |
| Effort | S, M, L | Estimation de correction |

### 9.3 Fiche de correction

```yaml
défaut: DEF-012
cause_probable: "Le token --space-btn-x a été réduit de 16 à 8 px ; min-width absent sur .btn"
cause_établie: true                   # false = hypothèse ; corriger localement et revérifier
solution: "Restaurer min-width via le composant Button ; ne pas toucher au token (utilisé ailleurs)"
type: cause-commune                   # cause-commune | local | palliatif-déclaré
composants_affectés: [Button, Toolbar, DialogFooter]
instances_à_revérifier: 14
bénéfice: "Libellés lisibles dans toutes les langues"
risques: "Boutons plus larges, possible retour à la ligne dans DialogFooter à 320 px"
non_régression: [CTA-01@320, CTA-01@i18n-pseudo, GEO-06@DialogFooter, DS-05@rayon]
autorisation: dans-périmètre          # dans-périmètre | proposition-seulement
```

### 9.4 Variantes

À proposer seulement si un **arbitrage réel** existe : plusieurs solutions valides avec des compromis différents, ou un conflit entre contraintes (dense vs lisible, cohérence DS vs besoin local). Deux ou trois variantes au maximum.

| Critère | Variante A | Variante B | Variante C |
|---|---|---|---|
| Compréhension | | | |
| Efficacité (étapes, temps) | | | |
| Accessibilité | | | |
| Cohérence DS | | | |
| Complexité d'implémentation | | | |
| Contraintes (métier, technique) | | | |
| Qualité visuelle `[PRÉFÉRENCE]` | | | |
| Incertitudes | | | |

Chaque variante est accompagnée d'une capture ou d'un rendu prototype si cela est réalisable à coût raisonnable. Le skill **recommande** une option avec sa justification et précise que l'évaluation est heuristique, sans valeur de test utilisateur.

---

## 10. Outils, autorisations et modes dégradés

### 10.1 Capacités requises

| Capacité | Usage | Options possibles (non exclusives, aucune marque imposée) | Choix |
|---|---|---|---|
| CAP-BROWSER | Ouvrir, piloter, émuler | Bibliothèque d'automatisation (Playwright, Puppeteer, WebDriver/BiDi), serveur MCP de navigateur, DevTools Protocol, extension navigateur de l'hôte | Préférer ce qui offre multi-moteurs + émulation + arbre d'accessibilité |
| CAP-SHOT | Captures pleine page et élément | Inclus dans CAP-BROWSER ; capture OS pour le natif | - |
| CAP-DOM | DOM, styles calculés, boîtes | DevTools Protocol, évaluation JS | - |
| CAP-A11Y-TREE | Arbre d'accessibilité | Snapshot d'accessibilité du navigateur ; API de l'OS pour le natif | - |
| CAP-A11Y-RULES | Règles automatisées | axe-core, ou moteurs équivalents (Lighthouse inclut un sous-ensemble) | Préférer un moteur dont les règles sont référencées WCAG |
| CAP-INTERACT | Clics, saisie, clavier, tactile, redimensionnement | CAP-BROWSER ; outils d'UI testing de la plateforme pour le natif ; computer use en dernier recours | - |
| CAP-NET | Mock, bridage, hors ligne | Interception réseau de l'outil d'automatisation, service worker de mock | - |
| CAP-DIFF | Comparaison visuelle | pixelmatch, odiff, comparateur intégré à l'outil, services de régression visuelle (attention à la confidentialité) | Local par défaut |
| CAP-WEB | Recherche et lecture Web | Outil de recherche ou de fetch de l'hôte | - |
| CAP-FS | Lire et modifier le code | Outils fichiers de l'hôte | Selon les autorisations |
| CAP-NATIVE | Natif | XCUITest / Accessibility Inspector, Espresso / UI Automator / Accessibility Scanner, WinAppDriver / UI Automation, AT-SPI ; computer use | Dépend de l'OS hôte et du SDK |
| CAP-SR | Lecteur d'écran réel | NVDA, JAWS, VoiceOver, TalkBack ; pilotage automatisé seulement si un outil dédié est installé | Souvent humain |
| CAP-DEVICE | Appareils réels | Appareils locaux via débogage USB ou fermes d'appareils distantes | Autorisation et coût |

### 10.2 Détection des capacités (étape 1)

```text
capabilities = {}
pour cap dans CAPACITÉS:
    capabilities[cap] = sonder(cap)   # ex. lancer un navigateur headless sur about:blank,
                                      # exécuter une requête Web test, vérifier la présence du SDK
écrire capabilities.json avec {disponible: bool, outil: nom/version, raison_si_absent}
```

L'installation d'outils (paquets, navigateurs) n'a lieu que si l'hôte l'autorise. Sinon le skill la propose avec la commande exacte et poursuit en mode dégradé.

### 10.3 Modes dégradés

| Situation | Alternative | Contrôles non vérifiés | Plafond de décision |
|---|---|---|---|
| Pas de navigateur pilotable | Captures fournies par l'utilisateur + lecture du code | Tous les contrôles C, S et A dynamiques | `validation limitée, sans exécution` |
| **Capture impossible** (crash du rendu, environnement headless sans GPU, app non lançable) | Diagnostiquer (logs de lancement), retenter avec une autre stratégie (autre moteur, headful, build de prod), sinon analyse structurelle sans image | Tous les contrôles V ; avant/après visuel | `non validée : preuve visuelle manquante` si le périmètre est visuel |
| Pas de Web | §8.8 | Recherche | `validée : périmètre testé` au mieux |
| Pas d'arbre d'accessibilité | Inspection DOM et ARIA statique | ACC-05 partiel, ACC-06 | Signalé |
| Natif sans intégration | Captures + computer use | Structure, noms accessibles | `validation limitée` |
| Pas d'appareil réel | Émulation | §7.9 | Signalé, pas de plafond si non requis |
| Maquette seule | Audit visuel statique | Interactions, responsive réel, accessibilité structurelle | `validation limitée, maquette` |

Pour chaque échec d'outil : une trace concise (commande, erreur résumée), l'alternative tentée et la liste des contrôles impactés.

### 10.4 Autorisations et confidentialité

- Respecter le mode de permission de l'hôte. Ne pas élargir le périmètre de modification sans accord.
- Parcours à effets externes : environnement de test ou données `sensitive-fake`. Sinon, arrêt avant l'action irréversible et confirmation explicite.
- Les captures restent locales (dossier d'audit). Aucun envoi à un moteur de recherche. Aucun envoi à un service tiers (diff en ligne, ferme d'appareils, hébergement de rapport) sans autorisation, et anonymisation au préalable si nécessaire.
- Le rapport n'inclut ni secret, ni jeton, ni donnée personnelle réelle.

---

## 11. Modèles de preuves et de rapports

### 11.1 Arborescence des preuves

```text
.ui-audit/
  RUN-2026-10-11T1430-<slug>/
    scope.md
    impact.json
    capabilities.json
    coverage.json
    research/
      log.json
      references.json
    before/<config-id>/<écran>__<état>.png
    after/<config-id>/<écran>__<état>.png
    after-fix-<n>/...
    diff/<config-id>/<écran>__<état>.diff.png
    manifests/<config-id>.json
    traces/                 # vidéos, traces de perf, journaux console et réseau
    findings/DEF-001.json
    annotated/DEF-001.png
    report.md
    report.json
```

`config-id` = hash court ou nom lisible (`w390h844-dpr3-light-fr-nomotion`). Le dossier `.ui-audit/` est ajouté au `.gitignore` par défaut (choix ouvert, §15).

### 11.2 Manifeste de configuration

```json
{
  "config_id": "w390h844-dpr3-light-fr-nomotion",
  "fidélité": "émulation",
  "moteur": "chromium 1xx.x",
  "viewport_css": [390, 844],
  "dpr": 3,
  "zoom": 1.0,
  "thème": "light",
  "langue": "fr-FR",
  "fuseau": "Europe/Paris",
  "préférences": {"reduced_motion": "reduce", "contrast": "no-preference", "forced_colors": false},
  "pointeur": "coarse",
  "réseau": "mock",
  "fixture": "typical",
  "horloge": "2026-01-15T10:00:00Z",
  "révision": {"avant": "abc123", "après": "def456 + modifications non commitées"},
  "étapes_navigation": ["/login", "remplir(email)", "clic(Se connecter)", "/compte"]
}
```

### 11.3 Fiche de défaut

```json
{
  "id": "DEF-012",
  "titre": "Libellé du bouton « Confirmer la réservation » rogné à 320 px",
  "contrôle": "CTA-01",
  "écran_composant": "Checkout / Button(primary)",
  "préconditions": "Panier avec 1 article, utilisateur connecté",
  "données": "fixture typical, langue de",
  "config_id": "w320h640-dpr2-light-de",
  "étapes": ["Ouvrir /checkout", "Défiler jusqu'au pied de page"],
  "attendu": "Libellé entièrement visible dans la surface du bouton",
  "observé": "Le texte est coupé après « Reservierung best » ; scrollWidth=212, clientWidth=176",
  "interprétation": "Probablement white-space:nowrap + largeur fixe du conteneur",
  "nature": "[EXIGENCE]",
  "preuves": ["annotated/DEF-012.png", "traces/DEF-012-metrics.json"],
  "reproductions": "2/2",
  "sévérité": "majeure",
  "priorité": "P1",
  "confiance": "élevée",
  "effort": "S",
  "correction": "voir fiche correction (§9.3)",
  "retest": {"statut": "réussi", "config_id": "w320h640-dpr2-light-de", "preuve": "after-fix-1/..."}
}
```

### 11.4 Modèle de rapport (`report.md`)

```markdown
# Audit UI : <titre>, RUN-<id>

## Décision
<VALIDÉE : PROTOCOLE COMPLET | VALIDÉE : PÉRIMÈTRE TESTÉ | VALIDÉE AVEC EXCEPTIONS | NON VALIDÉE | VALIDATION LIMITÉE : <raison>>
Résumé en 3 lignes : ce qui est vérifié, ce qui bloque, ce qui reste à faire.

## Périmètre
Demande · objectif · critères d'acceptation · zones modifiées · rayon d'impact · niveau N1/N2/N3 (+ justification, réductions)
Déclenchement : C1 | C2 | C3

## Hypothèses
| # | Hypothèse | Source / raison | Impact si fausse |

## Environnement
Outils et versions · fidélité (simulation, émulation, réel) · capacités absentes

## Références consultées
| Réf. | Titre | Organisme | URL | Consultée le | Publiée/MAJ | Question | Limites |
Tableau de comparaison (§8.5)
Statut recherche : réalisée | partielle | non réalisée (cause)

## Couverture
Matrice synthétique : familles × statut (réussi / échoué / non vérifié / N/A)
Configurations exécutées · combinaisons exclues (raison, risque)
Vérifications par nature : visuelle / structurelle / comportementale / assistive / humaine

## Synthèse priorisée
Top défauts (sévérité, priorité, confiance)

## Défauts
Fiches DEF-xxx (§11.3), regroupées par cause commune

## Variantes (si utiles)
Tableau comparatif + recommandation + incertitudes

## Corrections appliquées
| Défaut | Fichiers | Type (cause commune / local / palliatif) | Instances revérifiées |

## Avant / après
Paires de captures, mêmes config_id ; différences attendues vs inattendues

## Régressions
Contrôles de non-régression et résultats

## Défauts résiduels et exceptions
| Défaut | Sévérité | Raison du non-traitement | Exception acceptée par / date |

## Limites et vérifications humaines requises
Ex. : lecteur d'écran réel, appareil pliable physique, clavier virtuel réel, test utilisateur

## Annexes
Chemins des preuves, manifestes, journaux
```

`report.json` reprend la même structure pour exploitation par la CI ou un hook.

### 11.5 Message de fin dans la conversation

Format court : décision, nombre de défauts par sévérité (corrigés / restants), principales limites, chemin du rapport. Jamais « tout est parfait ».

---

## 12. Barrière de validation

### 12.1 Statuts de contrôle

| Statut | Condition | Justification obligatoire |
|---|---|---|
| **réussi** | Contrôle exécuté, résultat conforme à l'attendu, preuve conservée | Référence de preuve |
| **échoué** | Exécuté, non conforme | Fiche DEF |
| **non vérifié** | Non exécuté ou non concluant (outil absent, capture impossible, nécessite un humain ou un appareil) | Raison + action requise |
| **non applicable** | Le contexte ne s'y prête pas (pas de formulaire, pas de RTL supporté) | Raison factuelle |

`non vérifié` ≠ `réussi`. `non applicable` ne peut pas servir à masquer un `non vérifié` : la raison doit être factuelle, et non « pas eu le temps ».

### 12.2 Conditions bloquantes

Une **validation** (toute décision commençant par « VALIDÉE ») est impossible si au moins une condition est vraie :
- B1 : un défaut **critique** est ouvert ;
- B2 : un défaut **majeur** `[EXIGENCE]` est ouvert sans exception acceptée ;
- B3 : un contrôle **fondamental** du périmètre est `non vérifié` sans raison technique documentée ;
- B4 : le parcours principal (PAR-01) n'a pas été exécuté avec succès (sauf mode maquette déclaré) ;
- B5 : aucune preuve visuelle après correction (pas de recapture) pour un changement visuel ;
- B6 : une régression introduite par une correction est ouverte.

### 12.3 Décisions

```text
si B1..B6 (B2 non couvert par une exception):
    décision = "NON VALIDÉE"
sinon si mode ∈ {maquette, sans-exécution}:
    décision = "VALIDATION LIMITÉE : <mode>"
sinon si B2 couvert par une exception:
    décision = "VALIDÉE AVEC EXCEPTIONS"
sinon si recherche Web non réalisée
     ou contrôles hors fondamentaux `non vérifié` dans le niveau requis
     ou couverture réduite sous le niveau calculé:
    décision = "VALIDÉE : PÉRIMÈTRE TESTÉ"    + liste des limites
sinon:
    décision = "VALIDÉE : PROTOCOLE COMPLET"  + liste des vérifications humaines restantes (ACC-11, réel)
```

« Protocole complet » signifie que le protocole a été entièrement suivi au niveau requis. Cela ne signifie pas qu'aucun défaut n'existe. Le rapport le rappelle.

### 12.4 Défauts résiduels et exceptions

- Modérés et mineurs restants : listés, avec priorité. Ils ne bloquent pas, sauf exigence projet contraire.
- **Exception** sur un défaut majeur `[EXIGENCE]` : seul l'utilisateur ou un rôle désigné (choix ouvert §15) peut l'accepter, de façon explicite et datée, avec une échéance de traitement recommandée. Le skill ne s'auto-accorde jamais d'exception et ne reformule pas un critique en majeur pour débloquer.
- Les exceptions sont reportées dans les audits suivants tant qu'elles sont ouvertes.

---

## 13. Scénarios d'acceptation du skill

Chaque scénario se joue sur une application de test (§14, livrable L7) contenant le défaut injecté. Le skill réussit le scénario si son rapport contient la preuve attendue et la bonne décision.

| ID | Scénario | Préconditions | Action | Défaut attendu | Preuve attendue | Décision attendue |
|---|---|---|---|---|---|---|
| SCN-01 | **Bouton décalé** | Groupe de 3 boutons alignés ; le 2ᵉ reçoit `margin-top: 6px` | Demande « modifie le style du pied de formulaire » | DEF GEO-02/CTA-02 : bord haut décalé de 6 px vs frères | Capture annotée + mesures des `top` des 3 boutons + avant/après | NON VALIDÉE jusqu'à correction (modérée, P1 si sur l'action principale), puis VALIDÉE après recapture |
| SCN-02 | **Texte dépassant d'un bouton** | Bouton à `width: 120px; white-space: nowrap` ; libellé allongé | Changement de libellé | DEF CTA-01 à 320 px et en pseudo-locale | `scrollWidth > clientWidth` + capture | NON VALIDÉE (majeure) → correction de la cause (min-width/auto, retour maîtrisé) → recapture → VALIDÉE |
| SCN-03 | **Superposition masquant une action** | Bannière cookies `position: fixed; bottom: 0` recouvrant « Payer » à 390×844 | Ajout de la bannière | DEF STK-01 critique : `elementFromPoint(centre(Payer))` = bannière | Capture + résultat elementFromPoint + parcours PAR-01 échoué | NON VALIDÉE (B1) |
| SCN-04 | **Régression responsive** | Changement d'un token de gap global ; la grille produit casse à 768 px (b−1) | Modification du token | DEF GEO-01/GEO-05 sur un écran **non modifié directement** | `impact.json` montrant la propagation + diff visuel avant/après à 767 px | NON VALIDÉE ; correction ; contrôles DS-05/DS-06 sur le rayon |
| SCN-05 | **Focus piégé** | Widget de recherche qui renvoie le focus sur lui-même à Tab | Ajout du widget | DEF ACC-03 critique | Séquence des éléments focalisés (journal) montrant la boucle | NON VALIDÉE (B1) |
| SCN-06 | **Erreur de formulaire mal signalée** | Erreur en rouge seul, en haut de page, sans lien au champ ni annonce | Ajout de validation | DEF FRM-03 (+ COL-01, ACC-06) | Arbre d'accessibilité du champ (pas d'`aria-invalid`/`describedby`), capture en niveaux de gris, absence de région live | NON VALIDÉE (majeure `[EXIGENCE]`) |
| SCN-07 | **Contenu traduit trop long** | Locale `de` ou pseudo-locale ; onglets de largeur fixe | Ajout de la langue | DEF LOC-01 / GEO-03 | Captures par langue + mesures | NON VALIDÉE → correction → VALIDÉE |
| SCN-08 | **Correction introduisant une régression** | Correctif de SCN-02 via réduction de `font-size` du composant Button partagé | Le skill (ou un correctif imposé dans le test) applique ce correctif | DEF DS-05/DS-06 : boutons d'autres écrans devenus trop petits, CTA-03 cible réduite | Diff visuel sur le rayon d'impact + mesures de cibles | Le skill détecte la régression à l'étape 8, revient à l'étape 7 et propose la correction de cause. Si non résolue en 3 itérations : NON VALIDÉE avec `échoué : non résolu`. |
| SCN-09 | **Pliable ou redimensionnement perdant l'état** | Formulaire multi-étapes dont l'état est stocké dans un composant remonté au changement de breakpoint | Redimensionner 1366 → 600 → 1366, ou transition de posture émulée | DEF ROB-06 : saisie perdue, retour à l'étape 1 | Captures avant/pendant/après + valeurs des champs relues | NON VALIDÉE ; le rapport précise `fidélité: émulation` et marque la charnière physique `non vérifié : nécessite appareil` |
| SCN-10 | **Clavier virtuel masquant une action** | Pied fixe « Envoyer » en `position: fixed; bottom: 0` ; formulaire en bas de page ; layout en `100vh` | Émulation mobile + réduction du viewport visuel | DEF ENV-02 : bouton inatteignable ou recouvrant le champ focalisé | Capture viewport réduit + `elementFromPoint` + possibilité de scroll | NON VALIDÉE (majeure) ; le rapport précise que le clavier **réel** n'a pas été testé sans appareil ou émulateur d'OS |
| SCN-11 | **Web indisponible** | Outil de recherche désactivé ou réseau coupé pour la recherche | Audit d'un changement sans défaut | Aucun défaut UI | `research/log.json` avec erreur ; section « Recherche : non réalisée » ; recommandations étiquetées `[HYPOTHÈSE, non sourcée en ligne]` ; **aucune** URL inventée | VALIDÉE : PÉRIMÈTRE TESTÉ (jamais PROTOCOLE COMPLET) |
| SCN-12 | **Capture impossible** | Le navigateur headless échoue (binaire absent, crash) | Audit d'un changement visuel | - | `capabilities.json` avec échec, tentatives alternatives tracées, tous les contrôles V en `non vérifié` | NON VALIDÉE : preuve visuelle manquante (B5), ou VALIDATION LIMITÉE si l'utilisateur fournit des captures ; jamais `réussi` sur un contrôle visuel |

Scénarios complémentaires recommandés :

| ID | Scénario | Attendu |
|---|---|---|
| SCN-13 | Référence fabriquée (test négatif) : rapport injecté contenant une URL non consultée | Le vérificateur de rapport (L9) la détecte : URL absente de `research/log.json` |
| SCN-14 | Préférence esthétique seule (« je préférerais un rayon de 12 px ») | Étiquetée `[PRÉFÉRENCE]`, non bloquante |
| SCN-15 | Maquette statique seule | VALIDATION LIMITÉE : maquette ; interactions `non vérifié` |
| SCN-16 | Parcours avec paiement réel | Arrêt avant l'action irréversible, demande de confirmation ou bascule en environnement de test |
| SCN-17 | Nom d'appareil non vérifiable (« Apple Duo ») | Le rapport signale l'incertitude, raisonne par classe d'écran et n'invente aucune dimension |
| SCN-18 | Modale sans restitution de focus | DEF STK-03 détecté |

---

## 14. Feuille de route

### 14.1 Socle indispensable (V1)

| Lot | Contenu | Dépendances | Critère d'achèvement |
|---|---|---|---|
| V1.1 Consignes | `SKILL.md` : déclencheurs, workflow 9 étapes, étiquetage, barrière, interdits | - | Revue : couvre EX-ACT, EX-WF, EX-VAL ; description du skill testée sur 10 demandes d'interface (≥ 9 déclenchements) et 5 demandes hors UI (0 déclenchement) |
| V1.2 Détection de capacités | Sonde navigateur, Web, a11y, FS | - | `capabilities.json` correct sur 3 environnements (complet, sans navigateur, sans Web) |
| V1.3 Pilote Web | Lancement, stabilisation, captures avec manifeste, viewports P0/P1, émulation de préférences | V1.2 | Captures reproductibles : 2 runs identiques → diff ≤ seuil |
| V1.4 Contrôles fondamentaux automatisés | GEO-01/03/05, STK-01/02, CTA-01/03, TXT-01, ACC-01..05, FRM-01/03, ROB-01 (scripts d'inspection) | V1.3 | SCN-01 à 06 détectés sur l'app de test |
| V1.5 Recherche Web tracée | Requêtes, journal, fiches de référence, comparaison, mode indisponible | V1.2 | SCN-11 réussi ; 0 URL hors journal |
| V1.6 Rapport et barrière | Modèles `report.md`/`report.json`, calcul de décision, statuts | V1.4, V1.5 | SCN-11, 12, 14 réussis |
| V1.7 Avant/après et boucle | Baseline (VCS ou first-render), recapture, diff, limite d'itérations | V1.3 | SCN-08 réussi |
| V1.8 Impact indirect | `impact.json`, propagation tokens et composants | V1.1 | SCN-04 réussi |
| V1.9 App de test + scénarios | Application volontairement défectueuse et harnais SCN-01..12 |, (en parallèle) | Les 12 scénarios s'exécutent et sont notés automatiquement |

### 14.2 Perfectionnements (V2+)

| Lot | Contenu | Dépendances | Critère d'achèvement |
|---|---|---|---|
| V2.1 Barrière mécanique | Hook de l'hôte ou étape CI qui vérifie la présence d'un `report.json` valide pour les fichiers UI modifiés | V1.6 | Modification UI sans rapport → blocage ou avertissement observé |
| V2.2 Localisation | Pseudo-locale automatique, RTL, CJK | V1.4 | SCN-07 + RTL détectés |
| V2.3 Réseau et états | Mocks d'erreurs, bridage, interruptions | V1.3 | PAR-04/05, ROB-04/05 automatisés |
| V2.4 Pliables et environnement mobile | Classes F-*, transitions, segments si exposés, ENV-02/03 | V1.3 | SCN-09, SCN-10 |
| V2.5 Échantillonnage avancé | Pairwise, priorisation par analytics fournies | V1.4 | `coverage.json` avec exclusions motivées ; temps d'audit N3 borné (objectif à fixer, §15) |
| V2.6 Natif et hybride | Adaptateurs iOS, Android, desktop (arbre d'accessibilité OS) | V1.6 | Un scénario par plateforme supportée |
| V2.7 Assistif réel | Intégration optionnelle d'un pilote de lecteur d'écran ; sinon checklist humaine guidée | V1.6 | ACC-11 exécutable ou checklist produite |
| V2.8 Appareils réels | Connecteur appareil local ou ferme distante (avec autorisation et confidentialité) | V2.4 | Résultat `fidélité: réel` sur au moins un appareil |
| V2.9 Variantes prototypées | Rendu de 2 ou 3 variantes côte à côte | V1.7 | Tableau §9.4 + captures |
| V2.10 Mémoire de projet | Cache de références revalidées, exceptions persistantes, extensions de contrôles projet | V1.5 | Réutilisation tracée `revalidée` |

---

## 15. Choix restant à préciser

| # | Question | Option par défaut proposée |
|---|---|---|
| Q1 | Référentiel d'accessibilité cible : WCAG 2.2 AA, RGAA (version en vigueur), EN 301 549, autre ? | WCAG 2.2 AA, signalé comme hypothèse |
| Q2 | Navigateurs et plateformes cibles | `browserslist` du projet, sinon Chromium + WebKit + Gecko récents |
| Q3 | Qui peut accepter une exception (utilisateur seul, rôle désigné) ? | L'utilisateur de la session |
| Q4 | Le dossier `.ui-audit/` est-il versionné ? | Non (`.gitignore`), sauf `report.md` sur demande |
| Q5 | Budget temps ou coût par niveau d'audit | N1 ≈ quelques minutes, N3 borné par configuration ; à calibrer en V1.9 |
| Q6 | Tolérance de diff visuel et tolérance d'alignement | 1 px CSS d'alignement ; seuil de diff à calibrer sur 2 runs à vide |
| Q7 | Autorisation par défaut de corriger hors du périmètre initial | Non : proposer seulement |
| Q8 | Appareils réels ou ferme distante disponibles ? Contraintes de confidentialité associées ? | Aucun : émulation seule, déclarée |
| Q9 | Guide de rédaction et glossaire du projet existants ? | Absents : TXT-06 et DS-04 en heuristique `[PRÉFÉRENCE]` |
| Q10 | Langue des rapports | Langue de l'utilisateur (français) |
| Q11 | Seuils de performance perçue (PRF-01) | Aucun seuil bloquant sans exigence projet |
| Q12 | Installation automatique d'outils autorisée ? | Non : proposition de la commande |

---

## 16. Inventaire des livrables pour l'implémentation

| Réf. | Artefact | Description |
|---|---|---|
| L1 | `SKILL.md` | Frontmatter (nom, description riche en déclencheurs) + consignes : workflow, étiquetage, barrière, interdits, modes dégradés. Concis, avec renvois vers les fichiers de référence. |
| L2 | `reference/workflow.md` | Détail des 9 étapes (§5) |
| L3 | `reference/research-protocol.md` | §8 : gabarits de requêtes, hiérarchie des sources, règles d'arrêt |
| L4 | `controls/*.yaml` | Matrice §6 au format du schéma §6.0, plus `controls/project/` pour les extensions |
| L5 | `config/viewports.yaml`, `config/states.yaml`, `config/levels.yaml` | §7.3, §7.1, §3.6 |
| L6 | `fixtures/` | Jeux de données §7.7, pseudo-locale, données sensibles fictives |
| L7 | `test-app/` | Application de test avec défauts injectables (un drapeau par scénario) |
| L8 | `scripts/` (optionnel mais recommandé) | `probe-capabilities`, `capture` (avec manifeste), `inspect-geometry` (débordements, alignements, elementFromPoint), `a11y-scan`, `keyboard-walk` (ordre et pièges de focus), `visual-diff`, `impact-scan` |
| L9 | `scripts/verify-report` | Vérificateur de rapport : schéma, URL ⊂ journal de recherche, aucun `réussi` sans preuve, décision cohérente avec §12.3 |
| L10 | `templates/report.md`, `schemas/*.json` | Rapport, fiche de défaut, référence, manifeste, `coverage.json`, `impact.json` |
| L11 | `scenarios/SCN-*.md` + harnais | §13 avec résultats attendus |
| L12 | `integration/` | Extrait pour `CLAUDE.md` du projet, exemple de hook de barrière (V2.1), exemple d'étape CI |
| L13 | `reference/devices.md` | Méthode de vérification des appareils (sources officielles, datation) et classes d'écran, **sans** dimensions figées non sourcées |
| L14 | `reference/honesty-rules.md` | Interdits : références inventées, `réussi` non exécuté, émulation présentée comme réel, préférence présentée comme exigence, promesse d'exhaustivité |

### 16.1 Ce qui est automatisable, assisté ou humain

| Catégorie | Automatisé | Assisté (outil + jugement) | Humain uniquement |
|---|---|---|---|
| Géométrie, débordement, superposition | Mesures, détection | Intention d'alignement | - |
| Contraste | Fonds unis | Fonds image ou dégradé | - |
| Clavier, focus | Ordre, pièges, visibilité | Logique de l'ordre | - |
| Sémantique, ARIA | Règles, arbre | Pertinence des noms | Restitution par lecteur d'écran réel |
| Contenu, rédaction | Longueur, chaînes non traduites | Clarté | Ton, adéquation au public |
| Parcours | Exécution scriptée | Effort, friction | Compréhension réelle (test utilisateur) |
| Responsive | Émulation | Choix d'adaptation | Appareil réel (charnière, clavier natif) |
| Esthétique | - | Comparaison aux références | Jugement de marque |
