# Named devices and screen classes

## Rule

No device dimension, availability or capability comes from memory. When a device is named (by the user or in a brief):

1. Find the manufacturer's official page and, if useful, its developer documentation.
2. Record, with the access date: exact name, availability, screen size and resolution, default browser, web capabilities exposed (segments, posture).
3. Convert to CSS pixels only if the source gives the resolution and the scale factor, or if an official emulation profile exists (Playwright or Chrome DevTools device profiles, citing the version). Otherwise, reason by screen class.
4. Log the source with `research_log.py ref`.

If the name matches no verifiable product, the report says so and reasons by screen class. Example: "Apple Duo" matches no product that can be confirmed as established. Microsoft's "Surface Duo" is a distinct dual-screen device, to be related only if a source confirms it and if that was the intent. "Samsung Z Flip" refers to a line of clamshell foldables (Galaxy Z Flip) whose model and generation must be specified and verified.

## Screen classes

| Class | Characteristic | What can be emulated | What requires a device |
|---|---|---|---|
| Narrow mobile | About 320 to 360 CSS px | Width, DPR, touch | Native keyboard, system bars |
| Common or large mobile | About 375 to 430 CSS px | Same | Same |
| Closed clamshell foldable | Small external screen | Size if sourced | Actual availability of a browser on that screen |
| Open clamshell foldable | Very tall screen | Size if sourced | Fold, posture |
| Closed book foldable | Narrow, tall screen | Size if sourced | Switching the active screen |
| Open book foldable | Nearly square, close to a tablet | Size if sourced, width transitions | Hinge, posture, app continuity |
| Dual screen | Two separate surfaces | Segments if the browser exposes them | Physical hinge |
| Tablet | About 768 to 1180 CSS px | Width, orientation | Native keyboard, stylus |

## Fold transitions in emulation

A transition is reproduced as a resize during use:

```bash
python3 "$SKILL_DIR/scripts/resize_probe.py" --url URL --mode state \
  --widths <closed>,<open>,<closed> --height <height> --actions current-state.json
```

The report states `fidelity: emulation` and marks the hinge, the half-folded posture and the physical screen switch `not_verified` with `reason_type: real_device`.
