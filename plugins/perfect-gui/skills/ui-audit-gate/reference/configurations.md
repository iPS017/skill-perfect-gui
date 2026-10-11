# States and configurations

## States

| Code | State | How to trigger it |
|---|---|---|
| S-INIT | First render | Cold load |
| S-NORM | Normal, typical data | `config/fixtures/typical` or project data |
| S-HOV | Hover | `hover` action (fine pointer only) |
| S-FOC | Keyboard focus | `keyboard_walk.py` or the action `press: Tab` |
| S-ACT | Pressed | `eval` action dispatching `pointerdown` |
| S-SEL | Selected, checked, open | Interaction |
| S-DIS | Disabled | Business condition |
| S-LOAD | Loading | Delayed response (project mock, throttled network) |
| S-EMPTY | Empty | Empty data |
| S-ERR | Error (field, page, network, server) | Invalid input, 4xx and 5xx mocks, offline |
| S-OK | Success | Complete user flow |
| S-VAL | Validation in progress | Delayed asynchronous validation |
| S-DLG | Dialog or overlay open | Interaction |
| S-INT | Interruption | Background, expiry, network loss, resize |

Transitions to check explicitly: `LOAD -> OK`, `LOAD -> ERR`, `ERR -> correction -> OK`, `NORM -> DLG -> NORM` (focus returned to the trigger), `NORM -> resize or orientation change -> NORM` (state preserved), `OK -> back navigation`, `INT -> resume`.

The control x state crossing follows the "states" column of each control. It is not a full Cartesian product.

## Dimensions not to confuse

| Dimension | Definition |
|---|---|
| CSS viewport | `innerWidth x innerHeight` in CSS pixels. This is what media queries see. |
| DPR | `devicePixelRatio` |
| Capture resolution | Viewport x DPR. Annotated screenshots are at CSS scale (1 px = 1 CSS px). |
| Browser zoom | `--zoom 2` on a 1280 px window gives a 640 px CSS viewport |
| OS scaling | System scaling (not emulated) |
| User text size | Enlarged default font (to be emulated with `eval` on `html { font-size }`, approximate result) |

## Viewports (CSS pixels)

Machine-readable source: `config/viewports.json`. These widths represent **classes**, not devices.

| Priority | ID | Size | Reason |
|---|---|---|---|
| P0 | mobile-narrow | 320 x 640 | Reflow floor (WCAG 1.4.10, to be verified) |
| P0 | mobile | 390 x 844 | Common phone |
| P0 | laptop | 1366 x 768 | Laptop |
| P0 | desktop-md | 1440 x 900 | Large laptop |
| P1 | mobile-large | 430 x 932 | Large phone |
| P1 | mobile-landscape | 844 x 390 | Reduced height |
| P1 | tablet-portrait | 768 x 1024 | Tablet |
| P1 | tablet-portrait-lg | 820 x 1180 | Tablet |
| P1 | tablet-landscape | 1024 x 768 | Landscape tablet |
| P1 | tablet-landscape-lg | 1180 x 820 | Landscape tablet |
| P1 | desktop | 1920 x 1080 | Desktop |
| P2 | small-desktop | 1024 x 640 | Small window |
| P2 | split-half | 960 x 1080 | Split screen |
| P2 | ultrawide | 2560 x 1080 | Line length, stretching |
| P2 | ultrawide-xl | 3440 x 1440 | Ultrawide |
| P2 | short | 1280 x 600 | Low height |
| P2 | phone-landscape-small | 640 x 360 | Small landscape |
| Reflow | reflow | 320 x 256 | Horizontal scrolling |

**Breakpoints.** Extract the project's real breakpoints (media queries, container queries, Tailwind or CSS framework configuration), for example with `grep -rhoE "@media[^{]+" src | sort -u`. For each breakpoint `b` relevant to the scope, test `b-1`, `b` and `b+1` with the longest content, for example `--viewports 767x900,768x900,769x900`.

## Resizing during use

`resize_probe.py --mode state --widths 1366,960,600,390,1366` fills in the fields, then resizes. It checks that the values, the focus, the open dialogs and the page itself (no reload) are preserved. Prepare the desired state with `--actions` (open a modal, go to step 2).

## Foldables

Read `devices.md` before citing a device.

| Class | Description | To check |
|---|---|---|
| F-FLIP-CLOSED | Small external screen of a clamshell foldable | Is a browser available? Minimal content, targets |
| F-FLIP-OPEN | Very tall main screen | Large height, phone width |
| F-BOOK-CLOSED | Narrow, tall external screen | Width sometimes smaller than a regular phone |
| F-BOOK-OPEN | Nearly square internal screen | Mobile / tablet switch, two columns |
| F-HALF-FOLDED | Partially open posture | Only if the posture is exposed to the web |
| F-DUAL-SCREEN | Two screens and a hinge | Viewport segments |

Dimensions come from dated official sources or official emulation profiles, never from memory. Test transitions with `resize_probe.py --mode state --widths <closed>,<open>,<closed>` and check that input, focus, progress and scroll are preserved, with no reload.

Hinge and segments: only test them if the information is exposed to the web and supported by the target browser (media features `horizontal-viewport-segments` and `vertical-viewport-segments`, `env(viewport-segment-*)`, Device Posture API). Check their support at the time of the audit. Otherwise, use `not_applicable` (not exposed) or `not_verified` with `reason_type: real_device`.

## Virtual keyboard, safe areas, browser bars

- `resize_probe.py --mode keyboard --field SEL --action SEL [--ratio 0.55]` reduces the viewport height like a keyboard in resizes-content mode. It checks that the focused field is visible and not covered, and that the primary action can be reached by scrolling the user can actually perform. Scrolling that is only possible by script (an `overflow: hidden` container) counts as a failure.
- Declared limit: the resizes-visual mode (iOS, recent Chrome Android default), the native keyboard and the system bars are not reproduced. Mark them `not_verified` with `reason_type: real_device` if the user flow is mobile.
- Search the code for `100vh` on full-screen elements and for fixed footers near forms.

## Content

`config/fixtures/` provides `edge-text.json` (long texts, words without spaces, URLs, emojis, non-Latin scripts, RTL) and `unexpected.json` (null, negatives, zero, very large numbers, escaped HTML). Inject them through the project's test data or an `eval` action. Pseudo-localization is done in the page (`inspect_page.py --pseudo`, about +40% and accents) or on files (`pseudo_locale.py`).

## Risk-based sampling

```text
1. Baseline (always):
   fundamental controls x affected states x P0
   + main user flow with the keyboard (laptop) + user flow with a coarse pointer (mobile)
2. Critical combinations depending on the impact:
   changed component x variants in use x {320, breakpoints +/-1}
   changed content x {long, pseudo-locale} x {320, 390}
   changed form x {S-ERR, S-LOAD, S-OK} x {keyboard, touch}
   changed overlay x {near the 4 edges, 320} x {open, closing, focus returned}
3. Representative coverage (N2+): one viewport per P1 class x {S-NORM, S-ERR}; each theme x one viewport
4. Deep dive (N3 or finding detected): configurations neighboring the failing one,
   pairwise combinations of theme x language x preference x viewport
5. Write coverage.json: {"executed": [...], "excluded": [{"combination", "reason", "risk"}]}
```

## Fidelity

Each result carries `fidelity: simulation | emulation | real_device`. The following cannot be validated without a real device: native virtual keyboard, physical hinge, touch performance, mobile screen readers, sensors, OS-specific font rendering, system bars.
