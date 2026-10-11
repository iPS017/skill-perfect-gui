# Web research protocol

## Obligation

A search is attempted on every triggered audit. At N1, one or two targeted queries are enough. Every query and every opened page is logged with `research_log.py`. A reference only counts if its URL was accessed (or revalidated) in this run.

## Confidentiality

Queries describe an interface pattern, never the product: "accessible inline form error pattern", not "internal ACME checkout form error". No screenshot, no customer name, no internal URL, no personal data. `research_log.py query` rejects queries that contain email addresses, local or private hosts, or strings that look like tokens, unless `--force` is passed after checking.

## Building the queries

Parameters taken from the context: product type, task, platform, component, existing design system, **known** audience (do not invent one), industry.

Templates:
- `<component> accessibility pattern` ("date picker accessibility pattern")
- `<recognized design system> <component>` (Material, Apple HIG, Fluent, Carbon, GOV.UK Design System, DSFR for a French public service, etc.)
- `<standard> <criterion> understanding` ("WCAG 2.2 target size minimum understanding")
- `<task> usability research` (recognized UX research sources)
- Devices: `<manufacturer> <model> specifications`, then the official page
- Web API support: `<API> browser compatibility` (MDN, compatibility tables)

## Source hierarchy

| Rank | Type | Use |
|---|---|---|
| 1 | Standards and official documentation (W3C/WAI, WHATWG, MDN, Apple, Android, Microsoft and manufacturer documentation) | Requirements, behaviors, support |
| 2 | Recognized design systems | Proven patterns, component anatomy |
| 3 | Published UX research | Justification of a behavior |
| 4 | Comparable products observed | Industry conventions |
| 5 | Visual galleries | Inspiration only, never proof of usability |

## Logging

```bash
R="$SKILL_DIR/scripts/research_log.py"
python3 $R "$RUN" query --text "WCAG 2.2 focus not obscured understanding" --tool WebSearch --urls https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
python3 $R "$RUN" visit --url https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html --tool WebFetch
python3 $R "$RUN" ref --json '{
  "title": "Understanding SC 2.4.11: Focus Not Obscured (Minimum)",
  "url": "https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html",
  "author_organization": "W3C WAI",
  "published_or_updated": null,
  "access_status": "accessed",
  "source_rank": 1,
  "question": "Can the fixed footer hide the focus?",
  "key_points": ["..."],
  "transfer_limits": "AA criterion; check that the project targets AA.",
  "used_for": ["DEF-003"]
}'
python3 $R "$RUN" unavailable --cause "no search tool in this environment"
```

`ref` rejects an `accessed` or `revalidated` reference whose URL appears in no query or visit of the run. The access date is taken from the visit.

## Mandatory comparison

For each reference kept, one row in `report.json > comparisons`.

| Field | Content |
|---|---|
| `ref` | REF-xxx |
| `observation` | What our interface shows (measurement, screenshot) |
| `principle` | What the reference establishes, in its own terms |
| `gap` | Difference observed |
| `adaptation` | Proposed change, adapted to our context |
| `benefit` | Expected benefit |
| `nature` | `[REQUIREMENT]`, `[HYPOTHESIS]` or `[PREFERENCE]` |

Rules: do not copy an interface, its content or its identity. Do not impose a trend at the expense of readability, consistency or business constraints. A normative recommendation is checked in its applicable version. Resemblance to a compliant system does not prove compliance.

## Relevance and stopping

- Keep a reference if it answers a specific audit question, if it is rank 1 to 3 (rank 4 for an industry convention) and if it transfers to the platform.
- Stop when each open question has at least one rank 1 to 3 reference, or after two rounds without new information.
- Indicative ceiling: 5 references at N1 and N2, 8 at N3. Beyond that, justify. Remove links that support no finding.

## Reuse

`.ui-audit/research-cache.json` keeps the references from previous runs. To reuse one, reopen the URL (WebFetch), log the visit, then call `ref` with `"access_status": "revalidated"`. A reference cited without revalidation carries `memory_not_revalidated`. It does not count as research for the run and never supports a `[REQUIREMENT]` on its own.

## Web unavailable

Run `research_log.py unavailable --cause ...`, then set `report.json > research.status = "not_done"` with the cause. Continue the local controls. Label recommendations drawn from internal knowledge `[HYPOTHESIS, not sourced online]`. The decision is capped at `VALIDATED_TESTED_SCOPE`.
