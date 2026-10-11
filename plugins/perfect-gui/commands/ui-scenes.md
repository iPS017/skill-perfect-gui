---
description: Explore tout le site ou l'application Web, génère les scènes de tout ce qu'un utilisateur peut faire et les revoit toutes (à lancer avant chaque publication)
argument-hint: "[url] [explorer|revoir|reference|accepter S-xxxx]"
---

Applique le mode exploration du skill `ui-audit-gate` (`reference/exploration.md`).

Paramètres fournis par l'utilisateur : $ARGUMENTS

1. Trouve comment lancer l'application (scripts du projet), lance-la si besoin, et détermine l'URL. Sinon, utilise celle des paramètres.
2. Si `ui-scenes/scenes.json` n'existe pas, ou si l'utilisateur demande « explorer » :
   - `explore_site.py`, puis `generate_scenarios.py` (avec `--export-playwright tests/ui-scenes.spec.ts` si le projet utilise déjà Playwright) ;
   - puis `play_scenarios.py --mode baseline`, en montrant d'abord à l'utilisateur les captures de référence qui posent problème.
3. Sinon, lance la revue complète : `play_scenarios.py --suite ui-scenes --url <URL>`.
4. Présente le résultat :
   - statut, nombre de scènes × viewports ;
   - anomalies bloquantes regroupées par type, avec la scène, le viewport, la capture annotée et la clé ;
   - changements visuels à revoir ;
   - ce qui n'est pas couvert.
5. Corrige les anomalies dans le périmètre autorisé, puis relance la revue. N'accepte un changement visuel (`--accept`) que s'il est voulu, et une anomalie (`--accept-anomaly`) que sur décision explicite de l'utilisateur.
6. Ne déclare l'interface prête à publier que si la revue est au statut `ok`.
