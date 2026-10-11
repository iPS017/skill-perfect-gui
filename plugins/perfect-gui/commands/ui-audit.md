---
description: Lance l'audit UI/UX ui-audit-gate sur les modifications d'interface en cours
argument-hint: "[N1|N2|N3] [url] [périmètre ou consigne]"
---

Exécute le skill `ui-audit-gate` sur les modifications d'interface en cours, en suivant ses 9 étapes jusqu'à la décision produite par `verify_report.py --apply --render`.

Paramètres fournis par l'utilisateur : $ARGUMENTS

- Un niveau (N1, N2 ou N3) impose un niveau minimal. Une baisse sous le niveau calculé doit être justifiée dans le rapport.
- Une URL indique l'interface à ouvrir. Sinon, trouve la commande de lancement dans le projet avant de demander.
- Le reste précise le périmètre.

Ce déclenchement est explicite : utilise `--trigger C2` avec `init_run.py`.
