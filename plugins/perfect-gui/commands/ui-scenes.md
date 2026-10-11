---
description: Perfect GUI scenes - explore the whole website or web app, generate scenes for everything a user can do and review them all (run before every release)
argument-hint: "[url] [explore|review|baseline|accept S-xxxx]"
---

Apply the exploration mode of the `ui-audit-gate` skill (`reference/exploration.md`).

Parameters provided by the user: $ARGUMENTS

1. Find out how to start the application (project scripts), start it if needed, and determine the URL. Otherwise, use the one from the parameters.
2. If `ui-scenes/scenes.json` does not exist, or if the user asks to "explore":
   - `explore_site.py`, then `generate_scenarios.py` (with `--export-playwright tests/ui-scenes.spec.ts` if the project already uses Playwright);
   - then `play_scenarios.py --mode baseline`, first showing the user any baseline screenshots that look wrong.
3. Otherwise, run the full review: `play_scenarios.py --suite ui-scenes --url <URL>`.
4. Present the result:
   - status, number of scenes x viewports;
   - blocking anomalies grouped by type, with the scene, the viewport, the annotated screenshot and the key;
   - visual changes to review;
   - what is not covered.
5. Fix the anomalies within the authorized scope, then rerun the review. Only accept a visual change (`--accept`) if it is intended, and an anomaly (`--accept-anomaly`) only on the user's explicit decision.
6. Only declare the interface ready to publish if the review status is `ok`.
