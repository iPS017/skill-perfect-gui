# perfect-gui

Plugin Claude Code qui fournit le skill `ui-audit-gate`, les commandes `/perfect-gui:ui-audit` (audit d'une modification) et `/perfect-gui:ui-scenes` (exploration de tout le site et revue de toutes les scènes avant publication), un hook `Stop` et un hook de pré-publication.

```
/plugin install perfect-gui --marketplace iPS017/skill-perfect-gui
```

Voir le [README du dépôt](../../README.md) pour l'installation et l'utilisation, et [SKILL.md](skills/ui-audit-gate/SKILL.md) pour le fonctionnement du skill.

## Variables d'environnement

| Variable | Effet |
|---|---|
| `UI_AUDIT_GATE` | `block` (par défaut), `warn` ou `off` pour le hook Stop |
| `UI_AUDIT_PUBLISH_GATE` | `block` (par défaut), `ask` ou `off` pour la barrière avant publication |
| `UI_AUDIT_VENV` | Emplacement du venv (par défaut `~/.cache/ui-audit-gate/venv`) |
| `UI_AUDIT_CACHE` | Dossier de cache (venv, axe-core) |
| `UI_AUDIT_BROWSER` | Exécutable de navigateur à essayer en premier |
| `UI_AUDIT_AXE` | Copie locale de `axe.min.js` |

## Limites connues

- Les vérifications automatiques produisent des candidats à confirmer sur la capture annotée. L'alignement et la visibilité du focus sont des heuristiques de confiance moyenne.
- Le clavier virtuel est émulé en mode resizes-content seulement. Le clavier natif, la charnière des pliables et les lecteurs d'écran réels demandent un appareil ou un humain. Le rapport les marque comme non vérifiés.
- La CSP de la page est contournée pendant l'inspection pour permettre l'injection des scripts de mesure (`--respect-csp` pour l'éviter).
- Applications natives : sans outillage de plateforme, l'audit est visuel seulement.
