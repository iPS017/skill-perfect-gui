# Outils, autorisations et modes dégradés

## Scripts fournis

| Script | Rôle | Dépendances |
|---|---|---|
| `init_run.py` | Crée `.ui-audit/RUN-<date>-<slug>/`, les squelettes et l'entrée `.gitignore` | stdlib |
| `probe.py` | Sonde les capacités (Python, Playwright, moteurs, Pillow, axe, git, SDK natifs, lecteurs d'écran) | stdlib, Playwright optionnel |
| `impact_scan.py` | Classe les fichiers modifiés, propage tokens, composants et clés i18n, suggère un niveau | git |
| `capture.py` | Captures et manifestes par configuration | Playwright |
| `inspect_page.py` | Vérifications automatiques en page, capture annotée, arbre d'accessibilité, axe | Playwright, Pillow optionnel, axe optionnel |
| `keyboard_walk.py` | Parcours au clavier | Playwright |
| `resize_probe.py` | Perte d'état au redimensionnement, clavier virtuel émulé | Playwright |
| `visual_diff.py` | Diff pixel avant/après | Pillow |
| `pseudo_locale.py` | Pseudo-localisation de fichiers JSON | stdlib |
| `research_log.py` | Journal de recherche et fiches de référence | stdlib |
| `verify_report.py` | Cohérence du rapport, décision, rendu de `report.md` | stdlib |
| `setup.sh` | Crée le venv et installe Playwright et Pillow (avec accord) | python3, réseau |

Options communes aux scripts de navigateur : `--url`, `--viewports` (identifiants, `P0`, `P1`, `P2` ou `LxH`), `--theme light|dark`, `--locale`, `--timezone`, `--zoom`, `--reduced-motion reduce|no-preference`, `--forced-colors`, `--engine chromium|firefox|webkit`, `--browser-path`, `--headed`, `--actions` (fichier ou JSON), `--storage-state` (session authentifiée), `--freeze-time`, `--wait-ms`.

Lancement du navigateur, dans l'ordre : `--browser-path` s'il est donné (seule tentative), sinon `UI_AUDIT_BROWSER`, le Chromium de Playwright, puis Chrome, puis Edge installés.

## Installation

```bash
bash "$SKILL_DIR/scripts/setup.sh"                  # venv ~/.cache/ui-audit-gate/venv + playwright + pillow
bash "$SKILL_DIR/scripts/setup.sh" --with-browsers  # télécharge aussi Chromium, Firefox et WebKit de Playwright
```

Toujours demander l'accord avant d'installer, et donner la commande exacte. axe-core se télécharge une fois depuis cdnjs, ou jsDelivr en secours, vers `~/.cache/ui-audit-gate/`. `--no-axe` désactive ce téléchargement. `UI_AUDIT_AXE=/chemin/axe.min.js` utilise une copie locale.

## Alternatives selon l'environnement

| Capacité | Premier choix | Alternatives |
|---|---|---|
| Navigateur pilotable | Scripts Playwright | Outil navigateur de l'hôte (MCP Chrome DevTools, extension navigateur, computer use) en reproduisant manuellement les mêmes mesures |
| Règles d'accessibilité | axe-core via `inspect_page.py` | Lighthouse (sous-ensemble), extension axe dans un navigateur réel |
| Diff visuel | `visual_diff.py` (local) | Outil de régression visuelle du projet. Un service en ligne seulement avec autorisation et sans données sensibles. |
| Natif iOS | XCUITest, Accessibility Inspector (macOS et Xcode requis) | Captures et computer use |
| Natif Android | Espresso ou UI Automator, `adb shell uiautomator dump`, Accessibility Scanner | Captures et computer use |
| Desktop Windows | UI Automation (Inspect.exe, Accessibility Insights) | Computer use |
| Desktop macOS | API AX (Accessibility Inspector) | Computer use |
| Desktop Linux | AT-SPI (Accerciser) | Computer use |
| Hybride (WebView, Electron, Tauri, Capacitor) | Débogage distant de la WebView, puis scripts Web | Comme le natif pour le shell |
| Lecteur d'écran | NVDA, JAWS, VoiceOver, TalkBack par un humain | Pilote automatisé seulement s'il est installé et configuré |
| Appareils réels | Appareil local en débogage USB | Ferme d'appareils distante, avec autorisation et anonymisation |

Ne jamais supposer qu'un outil inspecte une application native ou pilote un lecteur d'écran sans intégration adaptée. Sans inspection structurelle, l'audit natif est visuel, et les contrôles structurels et assistifs sont `non_verifie`.

## Modes dégradés

| Situation | Alternative | Contrôles non vérifiés | Plafond |
|---|---|---|---|
| Pas de navigateur pilotable | Captures fournies par l'utilisateur, lecture du code | Tous les contrôles comportementaux, structurels dynamiques et assistifs | VALIDATION_LIMITEE (`mode: sans_execution`) |
| Capture impossible | Diagnostic (journal de lancement), autre moteur, `--headed`, build de production. Sinon analyse structurelle sans image. | Contrôles visuels, avant/après | NON_VALIDEE si le changement est visuel |
| Pas de Web | `research_log.py unavailable` | Recherche | VALIDEE_PERIMETRE_TESTE |
| Pas d'arbre d'accessibilité | Inspection du DOM et d'ARIA | ACC-05 partiel, ACC-06 | Signalé |
| Natif sans intégration | Captures et computer use | Structure, noms accessibles | VALIDATION_LIMITEE |
| Pas d'appareil réel | Émulation déclarée | Comportements matériels | Listé |
| Maquette seule | Audit visuel statique | Interactions, responsive réel, accessibilité structurelle | VALIDATION_LIMITEE (`mode: maquette`) |

Pour chaque échec d'outil : une trace concise (commande, erreur résumée), l'alternative tentée et la liste des contrôles touchés, dans `report.json > limites`.

## Autorisations et confidentialité

- Respecter le mode de permission de l'hôte. Ne pas élargir le périmètre des modifications sans accord.
- Parcours à effet externe : environnement de test ou données fictives. Sinon, arrêt avant l'action irréversible et confirmation explicite.
- Les captures restent dans `.ui-audit/`, qui est dans `.gitignore` par défaut. Rien n'est envoyé à un moteur de recherche ni à un service tiers sans autorisation. Anonymiser avant tout partage.
- Aucun secret dans les rapports, les manifestes ou les journaux. `--storage-state` pointe vers un fichier local qui n'est jamais copié dans le run.
