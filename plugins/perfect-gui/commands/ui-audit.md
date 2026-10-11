---
description: Run the ui-audit-gate UI/UX audit on the current interface changes
argument-hint: "[N1|N2|N3] [url] [scope or instructions]"
---

Run the `ui-audit-gate` skill on the current interface changes, following its 9 steps up to the decision produced by `verify_report.py --apply --render`.

Parameters provided by the user: $ARGUMENTS

- A level (N1, N2 or N3) sets a minimum level. Any downgrade below the computed level must be justified in the report.
- A URL indicates the interface to open. Otherwise, find the start command in the project before asking.
- The rest narrows the scope.

This trigger is explicit: use `--trigger C2` with `init_run.py`.
