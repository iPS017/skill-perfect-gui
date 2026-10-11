# Detailed workflow

Each step lists its inputs, its actions, its evidence and its exit condition. `$RUN` is the folder created by `init_run.py`.

```text
[1 Frame] -> [2 Before] -> [3 Research] -> [4 Run] -> [5 Inspect]
   -> [6 Record] -> [7 Fix] -> [8 Re-verify] --(findings remain, iterations < limit)--> [7]
   -> [9 Report and decide]
```

If the skill is invoked before coding, steps 1 to 3 come before the implementation. If it is invoked afterwards, the "before" state is rebuilt from git:

```bash
git worktree add ../_ui-audit-before HEAD   # or the revision before the changes
# start the application from this worktree on another port, capture, then:
git worktree remove ../_ui-audit-before
```

## Step 1: Frame

- **Inputs**: request, repository, conversation, diff.
- **Actions**:
  1. `init_run.py --slug <topic>` to create the run.
  2. `probe.py --out "$RUN/capabilities.json"` to probe the capabilities.
  3. `impact_scan.py --out "$RUN/impact.json"` (add `--base <ref>` if the changes are already committed) to get the affected areas, their confidence (`certain`, `probable`, `unknown`) and the suggested level.
  4. Fill in `scope.md` with the goal, main task, user flows (1 to 3), acceptance criteria, constraints found (design system, `browserslist`, accessibility standard), assumptions with their impact if they are wrong.
  5. Find out how to start the application: `package.json`, README, Makefile, docker-compose, scripts. Only ask for the URL or the command after searching.
- **Questions**: only if the answer changes the course of the audit and no reversible choice exists. All in a single message.
- **Exit**: scope frozen, level and justification.

## Step 2: Capture the initial state

```bash
python3 "$SKILL_DIR/scripts/capture.py" --url http://localhost:5173/checkout \
  --viewports P0 --out "$RUN/before" --name checkout --state normal --freeze-time 2026-01-15T10:00:00Z
```

- Capture the same screens and states as those that will be audited afterwards.
- Keep the manifests (`$RUN/before/manifests/*.json`). They pin the conditions to reproduce.
- **Exit**: `baseline=before`, `first-render` or `unavailable`, with its reason.

## Step 3: Research

See `research-protocol.md`. Logging commands:

```bash
python3 "$SKILL_DIR/scripts/research_log.py" "$RUN" query --text "accessible inline form validation pattern" --tool WebSearch --urls URL1 URL2
python3 "$SKILL_DIR/scripts/research_log.py" "$RUN" visit --url URL1 --tool WebFetch
python3 "$SKILL_DIR/scripts/research_log.py" "$RUN" ref --json '{"title":"...","url":"URL1", ...}'
```

## Step 4: Run and capture

- Start the application with the project scripts, in the background if needed. Check that it responds.
- User flow actions go into a JSON file (a list of single-key objects):

```json
[
  {"goto": "/checkout"},
  {"fill": ["#email", "test@example.com"]},
  {"click": "button[type=submit]"},
  {"wait_for": "#confirmation"}
]
```

  Available actions: `goto`, `click`, `fill`, `type`, `press`, `hover`, `focus`, `check`, `select`, `wait`, `wait_for`, `scroll`, `eval`, `set_viewport`.
- Capture each state with `--state <code>` (codes in `configurations.md`).
- Transitions (loading to success, opening and closing a modal, resizing during use) are separate behavioral controls. Check them with actions followed by an inspection, not only with final screenshots.

## Step 5: Inspect and cross-check

```bash
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --viewports P0 --out "$RUN/inspect" --scan-scroll
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --viewports 390x844 --pseudo --out "$RUN/inspect-pseudo"
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --viewports 1280x800 --zoom 2 --out "$RUN/inspect-zoom200"
python3 "$SKILL_DIR/scripts/inspect_page.py" --url URL --actions submit-empty.json --out "$RUN/inspect-errors"
python3 "$SKILL_DIR/scripts/keyboard_walk.py" --url URL --viewports laptop --out "$RUN/keyboard"
python3 "$SKILL_DIR/scripts/resize_probe.py" --url URL --mode state --widths 1366,960,600,390,1366
python3 "$SKILL_DIR/scripts/resize_probe.py" --url URL --mode keyboard --field "#email" --action "button[type=submit]"
```

Reading the results:
- `result: issues` flags candidates. Each candidate is confirmed on the annotated screenshot (`annotated.png`) before it becomes a finding. The alignment and focus visibility heuristics have medium confidence.
- `result: clean` means "nothing detected by this script". It is not proof that no defect exists, and the control only becomes `passed` if its method is fully covered by the script (see the Auto. column in `controls.md`).
- `result: error` or exit code 3 gives `not_verified`, with the reason.
- The accessibility tree (`aria-snapshot.txt`) serves as evidence for ACC-05. It does not replace a real screen reader (ACC-11).

## Step 6: Record and prioritize

- One record `findings/DEF-xxx.json` per finding, possibly with several instances.
- Reproduce twice. If the finding is intermittent, say so and lower the confidence.
- Keep `observed` (facts, measurements) separate from `interpretation` (presumed cause).
- Nature label, severity, priority, confidence, effort: see `severity-and-fixes.md`.

## Step 7: Fix or propose

- One fix record per cause (`severity-and-fixes.md`).
- If the common cause is established, fix the token or the component and list the instances to re-verify.
- Without permission, or outside the scope of the request: propose a diff or a precise description, without applying it.

## Step 8: Re-verify

```bash
python3 "$SKILL_DIR/scripts/capture.py" ... --out "$RUN/after-fix-1"     # same options as the before state
python3 "$SKILL_DIR/scripts/visual_diff.py" --before "$RUN/before" --after "$RUN/after-fix-1" --out "$RUN/diff"
```

- Each difference is qualified: expected (linked to the fix) or regression.
- Rerun the non-regression controls listed in each fix record.
- Limit: 3 attempts by default, 6 iterations per run. Beyond that, status `failed_unresolved`, with `blocking_cause` and `required_action` (product decision, missing information, missing tool, out of scope).

## Step 9: Report and decide

```bash
python3 "$SKILL_DIR/scripts/verify_report.py" "$RUN" --apply --render
```

- Code 0: consistent report. The decision is written and `report.md` is produced.
- Code 1: inconsistencies listed (missing evidence, untraced reference, decision contrary to the rules). Fix the report, never the rules.

## Determinism

| Source of variability | Measure |
|---|---|
| Date and time | `--freeze-time ISO` |
| Animations, transitions, caret | Disabled by default in screenshots (`--keep-motion` to keep them) |
| Fonts | Wait for `document.fonts.ready`. Test the fallback separately by blocking fonts (`{"eval": ...}` or a network tool). |
| Network | Stable test data. Project-side mocks if available. The real network is tested separately. |
| Third-party content | Mask it or replace it with a block of the same size, and say so |
| Rendering | Same machine, same browser and same version between before and after |
