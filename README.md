# skill-perfect-gui

Plugin Claude Code **perfect-gui**. Il contient le skill `ui-audit-gate`, une barrière qualité UI/UX qui intervient avant qu'une interface créée ou modifiée soit déclarée terminée.

Le skill ouvre le rendu réel et capture l'avant et l'après. Il inspecte la géométrie, les superpositions, les débordements, l'accessibilité, le clavier, les formulaires et le responsive. Il fait une recherche Web tracée de références, corrige ou propose des correctifs, puis rend une décision de validation bornée et prouvée. Il ne promet pas une interface sans défaut : il dit ce qui a été vérifié, comment, et ce qui ne l'a pas été.

## Installation

Dans Claude Code (version 2.1.275 ou plus récente), en une étape :

```
/plugin install perfect-gui --marketplace iPS017/skill-perfect-gui
```

Ou en deux étapes :

```
/plugin marketplace add iPS017/skill-perfect-gui
/plugin install perfect-gui@skill-perfect-gui
```

Redémarrer Claude Code, puis installer les dépendances des scripts (venv dédié dans `~/.cache/ui-audit-gate`) :

```bash
bash ~/.claude/plugins/marketplaces/skill-perfect-gui/plugins/perfect-gui/skills/ui-audit-gate/scripts/setup.sh
```

Le chemin exact dépend de l'installation. Le skill propose lui-même cette commande quand Playwright manque. Un Chrome ou un Edge système suffit. Sinon, `setup.sh` télécharge Chromium. `--with-browsers` ajoute Firefox et WebKit.

Prérequis : Python 3.9 ou plus récent et git. Node n'est pas nécessaire.

## Utilisation

- **Automatique** : le skill se déclenche quand Claude crée ou modifie une interface (page, composant, style, token, formulaire, navigation, traduction affichée, etc.).
- **Explicite** : `/perfect-gui:ui-audit [N1|N2|N3] [url] [périmètre]`.
- **Barrière mécanique** : un hook `Stop` bloque une fois la fin du tour si des fichiers d'interface ont changé dans le dépôt sans rapport d'audit cohérent et plus récent. Pour le désactiver : `UI_AUDIT_GATE=off` (ou `warn`), ou `.ui-audit/config.json` :

```json
{"gate": {"mode": "warn", "include": ["*.tpl"], "exclude": ["docs/*"]}}
```

Les preuves (captures, mesures, rapports) vont dans `.ui-audit/` à la racine du projet audité. Ce dossier est ajouté au `.gitignore` par défaut.

## Contenu

```text
.claude-plugin/marketplace.json        catalogue du dépôt
plugins/perfect-gui/
  .claude-plugin/plugin.json
  skills/ui-audit-gate/
    SKILL.md                           consignes du skill (workflow en 9 étapes, règles, décision)
    reference/                         contrôles, configurations, recherche, sévérité, barrière, outils, appareils, rapport
    config/                            viewports, niveaux et contrôles fondamentaux, jeux de données limites
    scripts/                           capture, inspection, clavier, redimensionnement, diff, impact, recherche, vérification
    schemas/ templates/
  commands/ui-audit.md                 commande /perfect-gui:ui-audit
  hooks/                               hook Stop de barrière
  tests/                               application de test à défauts injectables et scénarios d'acceptation
CAHIER_DES_CHARGES.md                  spécification d'origine
```

## Ce qui est automatisé, assisté ou humain

| Domaine | Automatisé par les scripts | Assisté (outil et jugement) | Humain uniquement |
|---|---|---|---|
| Géométrie, débordements, superpositions | Mesures et détection | Intention d'alignement | |
| Contraste | Fonds unis | Fonds image ou dégradé | |
| Clavier, focus | Ordre, pièges, visibilité, masquage | Logique de l'ordre | |
| Sémantique, ARIA | Règles axe-core, arbre d'accessibilité | Pertinence des noms | Restitution par lecteur d'écran réel |
| Contenu | Longueurs, pseudo-localisation | Clarté | Ton, adéquation au public |
| Parcours | Exécution scriptée | Effort, friction | Compréhension réelle (test utilisateur) |
| Responsive | Émulation de viewports, redimensionnement, clavier virtuel émulé | Choix d'adaptation | Appareil réel (charnière, clavier natif) |
| Esthétique | | Comparaison aux références | Jugement de marque |

## Tests

```bash
python3 plugins/perfect-gui/tests/run_scenarios.py
```

La suite sert une application de test qui contient des défauts injectables. Elle vérifie que les scripts détectent chaque défaut (bouton décalé, texte qui dépasse d'un bouton, superposition qui masque une action, régression responsive, focus piégé, erreur de formulaire mal signalée, traduction trop longue, régression introduite par une correction, perte d'état au redimensionnement, clavier virtuel qui masque une action) sans faux positif sur la version saine. Elle couvre aussi les cas Web indisponible et capture impossible, ainsi que les règles de décision, le journal de recherche, le hook et l'analyse d'impact.
