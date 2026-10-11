# Control matrix

Each control has a stable ID, used in `report.json` (`controls[].id`) and in the finding records. Thresholds marked "to be verified" must be confirmed in the version of the standard that applies to the project (WCAG, RGAA, EN 301 549, platform guidelines). The project's requirement always takes precedence.

## Coverage by the scripts

| Script check | Script | Controls fed | Coverage |
|---|---|---|---|
| `horizontal-overflow` | inspect_page | GEO-01, ACC-08 (at 320 px or 400% zoom) | Complete for detection. The cause is confirmed visually. |
| `text-overflow` | inspect_page | GEO-03, CTA-01, TXT-08, LOC-01 (with `--pseudo`), TXT-04 (with `--text-spacing`) | Complete for clipping and overflow of visible boxes |
| `occlusion` | inspect_page `--scan-scroll` | STK-01, STK-06 (partial) | Sampled points (center and 4 corners). A transparent decorative element on top can cause a false positive. |
| `spacing` | inspect_page | GEO-04, GEO-02 | Gap between the visible content of neighboring blocks of a row (default minimum 4 px, `--min-gap`). Joined segmented controls are ignored. Combine with `--viewports sweep:...` to find the width where blocks collide. |
| flows | flow_run | PAR-01, FRM-03, ACC-02 (with `--keyboard-only`), PAR-04, PAR-05 (with `set_offline` or `--network`) | Complete for the scripted steps and assertions only |
| `target-size` | inspect_page | CTA-03 | 24 px threshold with the spacing exception, plus a warning below the touch guideline for coarse pointers |
| `alignment` | inspect_page | GEO-02, CTA-02, CTA-04 | Heuristic, medium confidence. Confirm the intent on the screenshot and in the design system. |
| `contrast` | inspect_page | TXT-01 | Solid backgrounds only. Image, gradient or transparent backgrounds go to the `needs_assisted` list. |
| `form-labels` | inspect_page | FRM-01 | Approximate accessible name. Confirm with `aria-snapshot.txt`. |
| `accessible-names` | inspect_page | ACC-05 (partial) | Empty names only. Whether a name is meaningful is a human judgment. |
| `form-errors` | inspect_page with actions that trigger the error | FRM-03 (partial) | Linking and announcement. Proximity and clarity of the message need a visual review. |
| `images` | inspect_page | COL-05 (partial), COL-04 | Presence of `alt`, broken images. Relevance is a human judgment. |
| `headings` | inspect_page | TXT-02 | Complete for the structure |
| `document` | inspect_page | NAV-01 (partial), ACC-12 | Title and language |
| `landmarks` | inspect_page | ACC-10 | Presence of `main` and of the skip link |
| `axe` | inspect_page | ACC-01 | axe-core rules. `incomplete` results must be reviewed manually. |
| `console` | inspect_page | ROB-01 | Console errors, exceptions, 4xx and 5xx responses |
| tabbing | keyboard_walk | ACC-02, ACC-03, ACC-04, STK-02, STK-03 (Escape) | Order, traps, visibility (style heuristic), obscuring |
| state | resize_probe `--mode state` | ROB-06, FRM-04 (partial) | Values, focus, reload, open dialogs |
| virtual keyboard | resize_probe `--mode keyboard` | ENV-02 | Emulation of the resizes-content mode only |
| visual diff | visual_diff | DS-05, DS-06 | Pixel level. Each difference must be interpreted. |
| scenes | explore_site, generate_scenarios, play_scenarios | PAR-08, STK-08, COL-03, LOC-02, TXT-05, DS-03, ACC-12, NAV-06, ROB-01, plus the in-page checks at every step | One option at a time; see exploration.md |

Controls missing from this table are carried out by assisted or human review according to their method. A control is only `passed` if its whole method has been executed. Partial coverage by a script, without a complementary review, gives `not_verified` with the missing part as the reason.

## Project extension

A project can add controls in `.ui-audit/controls-project.md`, with the same table format and a `PRJ-` prefix. It can also disable a generic control by listing it with a justification. The skill reads this file at step 1 if it exists.

Column legend: **Nat.** V=visual, S=structural, C=behavioral, A=assistive, H=human. **Auto.** A=automated, As=assisted, H=human. **F** = fundamental (✓).

## Fundamental controls (run at every level, machine-readable list in `config/levels.json`)

GEO-01, GEO-02, GEO-03, GEO-05, STK-01, STK-02, TXT-01, CTA-01, CTA-02, CTA-03, FRM-01, FRM-03 (if there is a form), COL-01, NAV-01, PAR-01, ACC-01, ACC-02, ACC-03, ACC-04, ACC-05, ROB-01, DS-01, plus coverage of the P0 viewports (configurations.md).

## Geometry and layout (GEO)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| GEO-01 | Unintended horizontal scroll | `document.documentElement.scrollWidth > innerWidth`; identify the widest element that overflows | No page overflow, except an intentional and signposted horizontal scroll area | S,V | A | major | ✓ |
| GEO-02 | **Misaligned or misplaced element** (button out of alignment, off-center icon) | Compare the edges and centers of sibling elements in the same group (project tolerance, default 1 CSS px); compare with the before positions and with the design system grid; visual review | Aligned on the expected grid lines or axes; offsets justified by the design | V,S | As | moderate (major if the primary action is affected) | ✓ |
| GEO-03 | **Overflowing or clipped text** | `scrollWidth/Height` compared with `client*` values; child rect outside the parent rect; ellipsis without access to the full text | No clipping; intentional truncation offers the full text (accessible tooltip, expansion) | S,V | A | major | ✓ |
| GEO-04 | Inconsistent spacing | Extract computed margins, paddings and gaps, compare with the token scale | Values taken from the scale; offsets justified | S | A | minor `[PREFERENCE]` unless a DS requirement | |
| GEO-05 | Minimum and maximum sizes not respected (squashed or stretched elements) | Measure boxes at min, max and at breakpoints +/-1 px | No element with zero or negative width or height; readable lines | S,V | A | major | ✓ |
| GEO-06 | Unwanted line wrapping (broken word, orphan in a button, icon separated from its label) | Number of lines per element (height / line-height); screenshot | Control labels on one line or controlled wrapping | V,S | As | moderate | |
| GEO-07 | Proportions and density (empty or overloaded areas) | Heuristic review against the references | Clear hierarchy | V,H | H | `[PREFERENCE]` unless a requirement | |
| GEO-08 | Nested containers (cards inside cards, double padding) | Depth of containers with a border or background | Justified depth | V,S | As | minor | |
| GEO-09 | Layout shift on load or on interaction | Measure the shifts (Layout Instability API if available); compare successive screenshots | No unexpected movement of an element the user is aiming at | C,S | A | major if a click is diverted | |

## Stacking and positioning (STK)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| STK-01 | **Overlap hiding an action** | For each visible interactive element: `elementFromPoint` at the center and at the 4 inner corners; the returned element must be the target or one of its descendants | Every interactive target clickable at its center | S,C | A | critical if the action is essential | ✓ |
| STK-02 | Fixed or sticky element covering content or focus | While tabbing, check that the focused element is not fully hidden by a fixed element (see WCAG 2.2 SC 2.4.11, to be verified); `scroll-padding` | Focus and anchored content visible | S,A | A | major | ✓ |
| STK-03 | Modal: scrollable background, closing, focus restoration | Open, then Escape, click on the backdrop, close button; check `inert` or `aria-modal`, the initial focus and the return of focus to the trigger | Focus contained, closing possible, focus returned | C,A | A | major | |
| STK-04 | Popover, menu or tooltip outside the viewport or badly anchored | Open near the 4 edges and at 320 px; rect inside the viewport | Repositioning (flip/shift); whole content visible | S,V | A | major | |
| STK-05 | Unexpected stacking context (z-index with no effect) | Walk up the ancestors that create a context (`transform`, `opacity<1`, `filter`, `isolation`, `position+z-index`) | Stacking order matches the intent | S | As | moderate | |
| STK-06 | Safe areas (notch, home indicator) | Emulation with insets; check the use of `env(safe-area-inset-*)` and `viewport-fit=cover` where relevant | No control under an unsafe area | S,V | As (real device: H) | major | |
| STK-08 | Scrolling locked after closing a dialog, menu or drawer | `overflow: hidden` or `position: fixed` left on `body` or `html` with no dialog open (`play_scenarios.py`) | Scrolling restored | C,S | A | major | |
| STK-07 | Drawer or panel: internal scroll, overflow, closing | Long content in the panel, tabbing, Escape | Internal scroll, closing, focus managed | C,A | A | moderate | |

## Text and typography (TXT)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| TXT-01 | Insufficient text/background contrast | Calculation on the computed colors (and on pixels if the background is an image or a gradient); reference thresholds 4.5:1, and 3:1 for large text (WCAG 2.2 SC 1.4.3, to be verified) | Thresholds of the applicable requirement | S,V | A (complex background: As) | major | ✓ |
| TXT-02 | Inconsistent heading hierarchy | `h1..h6` sequence; a single `h1` if that is the project convention; visual and semantic match | Hierarchy without misleading skips | S,A | A | moderate | |
| TXT-03 | Line length, line height, base size | Measurement (characters per line, line-height) | Per the DS; otherwise a cited and sourced reference value | S | A | minor `[PREFERENCE]` unless a requirement | |
| TXT-04 | User-imposed text spacing breaks the layout | Inject the WCAG SC 1.4.12 overrides (line height 1.5, paragraph spacing 2x, letters 0.12em, words 0.16em, to be verified) | No loss of content or function | S,V | A | major | |
| TXT-05 | Fallback font or loading failure | Block font requests; screenshot | Layout holds; no prolonged invisible text (FOIT) | V,C | A | moderate | |
| TXT-06 | Ambiguous labels, jargon, inconsistent capitalization and punctuation | Review of the text against the project's writing guide | Explicit labels (verb and object for actions) | H | As | minor to moderate | |
| TXT-07 | Useless messages ("Error", "An error occurred") | List the error and status messages | The message says what happened and what to do | H | As | moderate | |
| TXT-08 | Exceptionally long content (80-character name, word without spaces, URL) | `fixtures/edge-text` dataset | No overflow (`overflow-wrap`) | V,S | A | major | |

## Controls and actions (CTA)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| CTA-01 | **Text overflowing a button** | GEO-03 applied to elements with the `button` role, or `link` styled as a button, in every language and at 200% zoom | Label contained within the surface | S,V | A | major | ✓ |
| CTA-02 | **Misaligned or misplaced button** (outside the action group, inconsistent order, primary action hard to see) | GEO-02 + visual order vs DOM order + DS and platform placement conventions | Placement consistent with the DS; primary action identifiable | V,S | As | moderate to major | ✓ |
| CTA-03 | Target too small or too close | Measure the effective clickable box (padding included); minimum reference 24x24 CSS px or equivalent spacing (WCAG 2.2 SC 2.5.8, to be verified); touch platforms: OS guidelines (to be verified, often larger) | Threshold of the applicable requirement | S | A | major (touch) | ✓ |
| CTA-04 | Icon misaligned within its button | Icon center vs box center and text baseline | Offset within tolerance | V,S | A | minor | |
| CTA-05 | Incomprehensible disabled state | Is the reason exposed? Is there an alternative? `aria-disabled` vs `disabled` (focusability) | The user understands why and how to unlock it | C,H | As | moderate | |
| CTA-06 | Double click or repeated submission | Fast double click and repeated Enter on a submission; count the requests | A single action; waiting feedback | C | A | major (critical for payment) | |
| CTA-07 | Unprotected destructive action | List the irreversible actions | Proportionate confirmation or undo available | C,H | As | major | |
| CTA-08 | Affordance (a link looks like text, a button like a label) | Visual review and hover and focus states | Interactive elements perceived as such | V,H | As | moderate | |
| CTA-09 | Conflicting or undocumented keyboard shortcuts | List the shortcuts; conflicts with the browser, the OS or assistive technologies; single-key shortcuts can be turned off (WCAG SC 2.1.4, to be verified) | No conflict; discoverability | C | As | moderate | |
| CTA-10 | Action priority (several competing primary buttons) | Count the primary variants per view | One primary action per context, unless justified | V | As | minor `[PREFERENCE]` unless DS | |

## Forms (FRM)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| FRM-01 | Field without an accessible label; placeholder used as a label | Accessibility tree: name of each field; presence of a visible label | Visible label and accessible name consistent | S,A | A | major | ✓ |
| FRM-02 | Missing help and expected format | Review of fields with a format (date, phone, IBAN...) | Format stated before input | H,V | As | moderate | |
| FRM-03 | **Poorly reported error** (far from the field, color only, not announced, not linked) | Submit invalid data: message near the field, `aria-invalid`, `aria-describedby` link, focus moved or summary, announcement (live region or focus), icon or text in addition to color | Error identified, described, linked, perceivable without color, announced | C,A,V | A+As | major | ✓ |
| FRM-04 | Loss of entered values (server error, back navigation, reload, resize) | Enter values, trigger the event, compare | Values preserved (except sensitive fields, by documented choice) | C | A | major | |
| FRM-05 | Validation too early or too aggressive | Observe validation while typing | Validation on blur or on submit, unless justified | C,H | As | moderate | |
| FRM-06 | `autocomplete`, input types and `inputmode` | Check the attributes on identity, address, payment and OTP fields | Relevant attributes | S | A | moderate | |
| FRM-07 | Password: show, paste, password manager | Show/hide button, paste allowed, `autocomplete=current-password/new-password` | No obstacle to input (see WCAG 2.2 SC 3.3.8, to be verified) | C,S | A | major | |
| FRM-08 | File upload: formats, size, progress, error, cancel | Valid files, too large, wrong type, network cut | Feedback and recovery | C | As | moderate | |
| FRM-09 | Redundant entry | Multi-step flow | No unnecessary re-entry (WCAG SC 3.3.7, to be verified) | C | As | moderate | |
| FRM-10 | Saving, cancelling and resuming a draft | Leave halfway, come back | Behavior matches the stated expectations | C | As | moderate | |
| FRM-11 | Blocking input masks | Paste, delete, cursor in the middle | No blocking | C | As | moderate | |

## Color and media (COL)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| COL-01 | Information conveyed by color alone | Review of statuses, errors, links in text, legends; grayscale screenshot or color blindness simulation | Second indicator (text, icon, pattern) | V,H | As | major | ✓ |
| COL-02 | Contrast of non-text components (field borders, meaningful icons, focus) | Calculation; reference 3:1 (WCAG SC 1.4.11, to be verified) | Threshold of the requirement | S | A | major | |
| COL-03 | Incomplete light and dark themes or high contrast | Screenshots in each supported theme; `forced-colors: active` | No invisible element and no inconsistent hard-coded color | V,S | A | major | |
| COL-04 | Missing, distorted or badly cropped images | Network status of images, `naturalWidth`, displayed vs natural ratio, `object-fit` | No broken image; ratio respected | S,V | A | moderate | |
| COL-05 | Missing or unsuitable alternative text | `alt` present; decorative (`alt=""`) vs informative; relevance judged | Equivalent alternative | A,H | As | major if informative | |
| COL-06 | Incomprehensible icon-only controls | Icons without a label; accessible name | Visible label or tooltip, and accessible name | V,A | As | moderate | |
| COL-07 | Video and audio: captions, transcript, autoplay, controls | Inventory of the media | Alternatives and user control | A,H | As | major if the content is essential | |

## Navigation and architecture (NAV)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| NAV-01 | Where am I? (active menu, page title, breadcrumb) | `aria-current`, unique and descriptive `<title>`, visual state | Clear orientation | S,V | A | moderate | ✓ |
| NAV-02 | Broken links, dead anchors | Crawl of the scope | No dead link | S | A | major | |
| NAV-03 | Back, history, deep links | Reload an internal URL, back button after navigation and after filtering | State restored; no blank screen | C | A | major | |
| NAV-04 | Search, filters, pagination: state in the URL, reset, zero results | Combined scenarios | Predictable behavior; useful empty state | C | As | moderate | |
| NAV-05 | Consistency across screens (navigation position, terminology) | Compare screenshots of several screens | Consistency (WCAG SC 3.2.3 and 3.2.4, to be verified) | V | As | moderate | |
| NAV-06 | Discoverability of essential actions (hidden in a menu at 320 px) | Responsive screenshots + inventory of actions | Essential actions reachable at every size | V,C | As | major | |
| NAV-07 | Progress in a multi-step flow | Step indicator, going back without loss | Clear progress | V,C | As | moderate | |

## User flows and feedback (PAR)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| PAR-01 | Can the main task be completed end to end? | Scripted user flow (mouse, then keyboard only) | Success observed | C | A | critical on failure | ✓ |
| PAR-02 | Disproportionate effort (steps, fields, clicks) | Count the steps and compare with the references | No superfluous step identified | H | As | `[PREFERENCE]`/moderate | |
| PAR-03 | Missing or late feedback after an action | Measure the delay between the action and the first visible change | Feedback perceptible quickly (project threshold) | C | A | moderate | |
| PAR-04 | Loading, success and error states not designed | Force each state (network mock) | Each state has a useful rendering and message | C,V | A | major | |
| PAR-05 | Unrecoverable errors, dead ends | Trigger the errors, check the ways out | Always a way out (retry, go back, contact) | C | As | major | |
| PAR-06 | Expired session and interruption (background tab, network loss, call) | Simulate expiry and backgrounding | Clear message; data preserved if possible | C | As | major | |
| PAR-08 | Action with no effect (dead button) | Click then observe: DOM, URL, scrolling, requests, new window (`play_scenarios.py`) | Every action produces a perceptible effect or response | C | A | major | |
| PAR-07 | Disproportionate confirmation (too much or too little) | Review | Proportionate to the risk | H | H | `[PREFERENCE]`/moderate | |

## Accessibility (ACC)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| ACC-01 | Automated rules (axe-core type engine or equivalent) | Run on every captured state | 0 serious or critical violations; the others are triaged | S | A | depends on the rule | ✓ |
| ACC-02 | Full keyboard navigation | Tab, Shift+Tab, Enter, Space, arrows in composite widgets, Escape | Every function reachable and operable | C,A | A | critical if an essential action is unreachable | ✓ |
| ACC-03 | **Focus trap** | Tab N times (N = number of focusable elements + 5) and check the exit from each component; a modal must keep the focus **and** offer Escape or a close control | No trap outside modals; modal can be closed (WCAG SC 2.1.2, to be verified) | C,A | A | critical | ✓ |
| ACC-04 | Visible focus and logical order | Screenshot of each focus stop; indicator contrast; order vs visual order | Visible indicator; consistent order | V,C,A | A+As | major | ✓ |
| ACC-05 | Accessible names, roles and states | Accessibility tree: button without a name, wrong ARIA role, `aria-expanded` or `aria-selected` out of sync | Correct exposure | S,A | A | major | ✓ |
| ACC-06 | Dynamic announcements (toasts, results, errors) | Live regions or `role=status/alert` elements; actual triggering | Important changes announced (WCAG SC 4.1.3, to be verified) | S,A | As | major | |
| ACC-07 | 200% zoom and enlarged text | Browser zoom at 200%; enlarged base font size | No loss of content or function (SC 1.4.4, to be verified) | V,S | A | major | |
| ACC-08 | Reflow at 320 CSS px width (equivalent to 1280 px at 400%) | 320 x 256 viewport for horizontally scrolling content, 320 wide in general | No 2D scrolling, except exempt content (SC 1.4.10, to be verified) | S,V | A | major | |
| ACC-09 | Complex gestures or drag and drop without an alternative | List swipe, pinch, drag | Single-pointer alternative (SC 2.5.1 and 2.5.7, to be verified) | C | As | major | |
| ACC-10 | Landmarks and skip link | `main`, `nav`, `header`, working skip link | Structure present | S | A | moderate | |
| ACC-11 | **Test with a real screen reader** (NVDA, JAWS, VoiceOver, TalkBack) | Main user flow with the screen reader | Understandable output | A,H | **H** (assisted if an automated driver exists) | - | |
| ACC-12 | Language of the page and of passages | `lang` present and correct | Correct pronunciation | S | A | moderate | |

Rule: ACC-11 is **never** marked `passed` on the basis of the accessibility tree alone. Without a real test, the status is `not_verified: requires a screen reader`.

## Motion (MOT)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| MOT-01 | `prefers-reduced-motion` ignored | Emulate `reduce` mode; compare the active animations | Non-essential animations removed or reduced | C,S | A | major | |
| MOT-02 | Dangerous flashing | List high-frequency animations; reference: no more than 3 flashes per second (SC 2.3.1, to be verified) | Compliant | V,C | As | critical | |
| MOT-03 | Animated or scrolling content without pause | Carousels, autoplay > 5 s | Pause, stop or hide (SC 2.2.2, to be verified) | C | As | major | |
| MOT-04 | Transition that breaks state (lost focus, double render, jump) | Record the transition (video or trace); check focus and content afterwards | Transition without state loss | C | As | moderate | |
| MOT-05 | Durations and easings inconsistent with the DS | Compare with the motion tokens | Consistent with the DS | S | A | minor `[PREFERENCE]` | |

## Complex data (DAT)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| DAT-01 | Table: headers, associations, announced sorting | `th`, `scope`, `aria-sort` | Structure exposed | S,A | A | major | |
| DAT-02 | Table on mobile (overflow, essential columns hidden) | 320 to 430 px | Explicit strategy (accessible contained scroll, stacking, prioritization) | V,S | As | major | |
| DAT-03 | Chart: consistent legend, units, axes, rounding | Review and comparison with the source data | Unambiguous reading | V,H | As | moderate | |
| DAT-04 | Accessible alternative to visualizations | Data table, text summary | Present | A | As | major if the information is essential | |
| DAT-05 | Missing, null, extreme values; large volumes (10,000 rows) | Fixtures `empty`, `null`, `huge`, `negative` | Sound rendering; acceptable performance; no "NaN" or "undefined" displayed | V,C | A | major | |
| DAT-06 | Multiple selection, bulk actions | Select, deselect, select all across several pages | Clear and consistent state | C | As | moderate | |

## Localization (LOC): if several languages or locales are relevant

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| LOC-01 | **Longer translation** that overflows | Longest real target language and pseudo-localization (+30 to 40%, accents, `[ ]` delimiters) | No overflow or clipping | V,S | A | major | |
| LOC-02 | Untranslated or concatenated strings | Pseudo-locale: spot text without delimiters | Everything is externalized | S | A | moderate | |
| LOC-03 | Plurals, genders | Values 0, 1, 2, 5, 21 according to the language's CLDR rules | Correct forms | V | As | moderate | |
| LOC-04 | Dates, times, time zones, numbers, currencies | Target locales; time zone different from the server's | Local formats; explicit time zone if ambiguous | V | A | moderate to major (finance) | |
| LOC-05 | Non-Latin scripts (CJK, Arabic, Devanagari): fonts, line height | Multi-script fixtures | Glyphs rendered; no vertical clipping | V | A | major if the language is supported | |
| LOC-06 | Right-to-left (RTL) and bidirectional | `dir=rtl`; CSS logical properties; directional icons mirrored | Correct mirrored layout | V,S | As | major if RTL is supported | |

## Robustness and compatibility (ROB)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| ROB-01 | Console errors and unhandled exceptions during user flows | Console and network log | No new error related to the scope | S | A | major | ✓ |
| ROB-02 | Target browsers | Chromium, WebKit and Gecko engines according to `browserslist` or the declared target | Equivalent rendering and functions | V,C | A | major | |
| ROB-03 | Input modes: mouse, touch, keyboard, hybrid | `pointer: coarse/fine`, `hover: none`; check that no function depends on hover alone | Functional in each mode | C | A | major | |
| ROB-04 | Slow, interrupted, resumed network | Network throttling (slow profile), offline mode during a user flow | Indicators, messages, recovery | C | A | major | |
| ROB-05 | Partial loading, unavailable service (API returning 500 or timing out) | Error mocks per endpoint | Graceful degradation; no blank screen | C | A | major | |
| ROB-06 | Orientation change and resizing **during use** | Change orientation or size with a filled form, an open modal, a scrolled page | State, focus and input preserved | C | A | major | |

## Perceived performance (PRF)

An instrumented measurement (Performance API, traces, Core Web Vitals type metrics) is distinct from an impression ("feels slow"). The report states which of the two it is.

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| PRF-01 | Interaction response delay | Measure the delay between input and the next render (instrumented) | Project threshold or sourced reference | C | A | moderate | |
| PRF-02 | Skeletons and progress indicators | Presence and consistency with the final shape (no jump) | Compliant | V,C | As | moderate | |
| PRF-03 | Main thread blocking (long tasks) | Performance trace | No perceptible freeze during the user flow interactions | C | A | moderate | |
| PRF-04 | Stability on load | See GEO-09 | - | | | | |

## Permissions and errors (PRM)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| PRM-01 | Permission requested out of context (right on load) | Observe when the request happens | Request tied to an explicit action, with a prior explanation | C,H | As | moderate | |
| PRM-02 | Permission denied | Emulate a denial (geolocation, camera, notifications) | Actionable message, alternative, no dead end | C | A | major | |
| PRM-03 | Permission revoked during use | Revoke then use again | Detection and message | C | As | moderate | |
| PRM-04 | Inaccessible function (insufficient rights) | Test account with a limited role | Explanation and a way to obtain access, no silent dead button | C | As | moderate | |
| PRM-05 | Ability to retry after an error | Trigger the error | Retry action available | C | A | moderate | |

## Design system and regressions (DS)

| ID | Defect sought | Method | Expected | Nat. | Auto. | Ind. sev. | F |
|---|---|---|---|---|---|---|---|
| DS-01 | Hard-coded values instead of tokens | Static analysis of the diff (hex colors, px off the scale) and computed styles outside the palette | Tokens used | S | A | moderate | ✓ |
| DS-02 | Component reimplemented instead of reused | Review of the diff against the component catalog | Reuse | S,H | As | moderate | |
| DS-03 | Inconsistent variants (same role, different styles) | Group elements by role and compare the styles | Consistency | V,S | As | moderate | |
| DS-04 | Inconsistent terminology | Project glossary vs labels | Consistency | H | As | minor | |
| DS-05 | Visual regression outside the scope | Visual diff of the screens in the impact radius (before/after) | Every difference explained | V | A | depends on the defect | |
| DS-06 | Propagation of the fix | Re-verify every instance of the fixed component or token | Instances compliant | V,S | A | major if an instance breaks | |

---


## Mobile environment (ENV)

| ID | Control | Method | Limit |
|---|---|---|---|
| ENV-01 | Safe areas and notches | Emulation of the insets, use of `env(safe-area-inset-*)` and `viewport-fit=cover` | Real device needed to confirm |
| ENV-02 | Virtual keyboard hiding an action | `resize_probe.py --mode keyboard` checks that the focused field and the primary action are reachable, not covered, and not reachable only by programmatic scrolling | Emulation of resizes-content. The native keyboard, the resizes-visual mode and the system bars require an OS emulator or a device. |
| ENV-03 | Mobile browser bars | Look for `100vh` on full-screen elements. Prefer `svh`, `lvh` and `dvh` depending on the intent. | OS emulator recommended |
| ENV-04 | Input modes | `pointer: coarse` and `fine` viewports, keyboard only. No function may depend on hover alone. | |
| ENV-05 | User preferences | `--theme dark`, `--reduced-motion reduce`, `--forced-colors`, high contrast if the engine supports it | |
| ENV-06 | Zoom and text size | `--zoom 2` (200%), `--zoom 4` with 1280 px (reflow), enlarged base font via `eval` | |
