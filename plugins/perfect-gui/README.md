# perfect-gui

Claude Code plugin that provides the `ui-audit-gate` skill, the `/perfect-gui:ui-audit` command (audit of a change) and the `/perfect-gui:ui-scenes` command (exploration of the whole site and review of all scenes before publishing), a `Stop` hook and a pre-publish hook.

```
/plugin install perfect-gui --marketplace iPS017/skill-perfect-gui
```

See the [repository README](../../README.md) for installation and usage, and [SKILL.md](skills/ui-audit-gate/SKILL.md) for how the skill works. The original specification, `CAHIER_DES_CHARGES.md` at the repository root, is written in French.

## Environment variables

| Variable | Effect |
|---|---|
| `UI_AUDIT_GATE` | `block` (default), `warn` or `off` for the Stop hook |
| `UI_AUDIT_PUBLISH_GATE` | `block` (default), `ask` or `off` for the pre-publish gate |
| `UI_AUDIT_VENV` | Location of the venv (default `~/.cache/ui-audit-gate/venv`) |
| `UI_AUDIT_CACHE` | Cache folder (venv, axe-core) |
| `UI_AUDIT_BROWSER` | Browser executable to try first |
| `UI_AUDIT_AXE` | Local copy of `axe.min.js` |

## Known limitations

- Automated checks produce candidates to confirm on the annotated screenshot. Alignment and focus visibility are medium-confidence heuristics.
- The virtual keyboard is emulated in resizes-content mode only. The native keyboard, the hinge of foldable devices and real screen readers need a device or a human. The report marks them as not verified.
- The page CSP is bypassed during inspection so the measurement scripts can be injected (use `--respect-csp` to avoid this).
- Native applications: without platform tooling, the audit is visual only.
