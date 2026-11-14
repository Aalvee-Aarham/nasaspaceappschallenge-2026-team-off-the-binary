# Kiln Watch — new features: architecture overview

**Date:** 2026-11-13 · **Status:** design, not yet implemented · **Base commit:** `1e99c85`
**Scope:** two features added on top of the harmonized record —

1. **The casebook** — every fire case, heard by several independent *witnesses*, with an agreement verdict.
2. **Exposure context** — who and what lies in the cells where the record shows fire.

These docs are design and architecture, not executor plans. They are written against the code as it stands at
`1e99c85`; the **Current state** blocks quote exact lines so a reader can detect drift immediately.

---

## 1. Document set

| File | What it answers |
|---|---|
| `README.md` (this) | shared architecture, the data flow, the decisions, the build order, the risks |
| `casebook.md` | the witnesses feature end to end: case generation, witness roster, verdict logic, storage, UI, surfaces |
| `exposure.md` | the exposure feature end to end: sources, aggregation, storage, UI, surfaces |
| `contracts.md` | every JSON / HTTP / MCP / agent contract in one place, with worked examples |
| `verification.md` | test plan, self-checks, acceptance criteria, rollout and rollback, the risk register |

Read `README.md` and `contracts.md` first; the two feature docs are then independent.

---

## 2. The one-paragraph version

Kiln Watch publishes a harmonized fire record. Two things are missing from it. First, the record is only ever
*asserted*: the product can ask "do the reports agree with the satellites?" but it has no code path that asks the
reverse — **a fire the agencies recorded and the satellites missed is invisible**. Second, the record says *how much
fire*, never *who and what is there*. The casebook fixes the first by turning every fire into a case with a panel of
independent witnesses and a five-way verdict; the exposure context fixes the second by joining the record's 0.1°
fire grid to population, hospitals and major roads.

---

## 3. Shared architecture

### 3.1 The rule that governs both features: data ships, the runtime does not compute

Everything in this project already works this way. The pipeline writes JSON into `data/regions/<area>/`, and the web
app reads it over HTTP as a static file. Both new features obey the same rule:

```
build time (network, heavy deps)            runtime (no new deps)
─────────────────────────────               ─────────────────────
scripts/build_exposure.py  ──► exposure.json ─┐
kw.cases: EONET/GDACS/GDELT ──► cases.json   ─┤─► /data/regions/<area>/*.json
build.py (_block, _grid)    ──► monthly.json ─┘        │
                                                        ▼
                                          tools.py → api.py / mcp_server.py / agent.py → web/src
```

**Consequences worth stating up front:**

- `rasterio` (for the population raster) is used **only** in `scripts/build_exposure.py`. It does **not** enter
  `server/requirements.txt` and does **not** enter the Docker image's runtime path.
- The web app never waits on Overpass, EONET, GDACS, GDELT or the population raster. Those are fetched once and
  cached as JSON. The live demo's request latency is unchanged.
- Nothing in either feature requires a rebuild of the *record*. The casebook reads `monthly.json`, `weekly.json`,
  `grid.json` and `meta.json`, which are all committed today. The exposure layer reads `grid.json` only.

### 3.2 The grid is the join key

`data/regions/<area>/grid.json` already publishes the harmonized record on a 0.1° grid:

```jsonc
{
  "deg": 0.1,
  "cells": [[lat, lon], ...],          // SW corner of each cell, in degrees
  "months": { "2026-11": [[cell_index, value], ...], ... },
  "unit": "vegetation hotspots per 0.1° cell, Aqua MODIS scale",
  "note": "Per-cell values use the area's calibration; uncertainty is reported for area totals only."
}
```

Both features join to **this grid**. Neither introduces a second geometry model, a second cell size, or a second
projection. A cell that has no fire is simply **absent** from `months[period]` — that absence is meaningful and is
used as a witness signal (see `casebook.md` §4).

### 3.3 Module layout

```
server/kw/
  cases.py       NEW  build-time case assembly + verdict logic (pure, stdlib + the existing news helpers)
  exposure.py    NEW  runtime readers for exposure.json (thin; the aggregation lives in scripts/)
  build.py       EDIT one line in _block (viirs_only), plus the call that writes cases.json
  tools.py       EDIT list_cases(), get_case(), exposure() — the shared deterministic layer
  api.py         EDIT three GET endpoints
  mcp_server.py  EDIT two tools
  agent.py       EDIT two tool declarations + the _RUN map
  news.py        EDIT eonet() keeps the event start date (one extra field)
scripts/
  build_exposure.py  NEW  download + aggregate + write exposure.json (build-time only)
web/src/
  Cases.tsx      NEW  the Cases tab: verdict table + witness panel + exposure panel
  api.ts         EDIT types + four api calls
  App.tsx        EDIT one tab
  Map.tsx        EDIT exposure overlays (population fill, hospitals, roads, case points)
```

**`server/kw/exposure.py` is deliberately thin.** All the expensive work (raster aggregation, Overpass queries)
happens in `scripts/build_exposure.py` at build time. At runtime the module only reads JSON and joins it to the
record. This is the same split the project already uses for `build.py` (pipeline) vs `tools.py` (queries).

### 3.4 Where new data appears in the existing files

No new top-level region files are needed for the casebook beyond `cases.json`. Two existing structures gain entries:

**`meta.json` → `method`** (a `dict[str, str]`). `web/src/Record.tsx:567` renders `Object.entries(m.method)` as the
"Processing steps" list, so a new entry appears on the Method page automatically:

```python
meta["method"]["witnesses"] = "Each fire case is heard by independent witnesses: the harmonized satellite record, a "
    "cross-family check (MODIS-only vs VIIRS-only for the same month), NASA EONET, GDACS and the press. The satellite "
    "witness abstains where no satellite observed, so a missing report is never read as 'no fire'."
meta["method"]["exposure"] = "Population (WorldPop 2020, 1 km) and infrastructure (OpenStreetMap) inside the 0.1 degree "
    "cells where the record shows fire. A context layer, not an impact estimate: there is no fire perimeter, no smoke "
    "and no fire spread here."
```

**`meta.json` → `external_sources`** (a new array, `[]` when nothing was built):

```python
meta["external_sources"] = [
  {"name": "WorldPop Global 2000-2020 population grid (1 km, 2020)", "role": "population context",
   "url": "https://www.worldpop.org/", "vintage": "2020", "license": "CC BY 4.0"},
  {"name": "OpenStreetMap (Overpass API)", "role": "hospitals and major roads", "url": "https://www.openstreetmap.org/copyright",
   "vintage": "query date", "license": "ODbL"},
]
```

This keeps the provenance surface **data-driven**, so the Method page can render it instead of hand-typing new
credits into `Method.tsx` — the project rule from `CLAUDE.md` ("never present hand-typed numbers").

### 3.5 Fault tolerance: a network failure must never break a build

`build.py` currently has exactly one network call (`_collection_updated()`, `build.py:81-87`) and it is already
wrapped in a try/except that returns `None`. The casebook adds three more network sources. The rule:

> **Every witness source is optional. A build with no network produces a valid `cases.json` with an empty case list
> and an `errors` map — never a failed build.**

This mirrors the per-source error capture already in `news._run` (`news.py:186-199`), which is what lets the UI show
"GDACS: not searched — rate-limited" instead of silently showing zero.

```jsonc
// cases.json
{
  "built_at": "2026-11-13T20:04:11+00:00",
  "area": "dhaka-kilns",
  "counts": {"corroborated": 41, "reported": 12, "satellite_only": 8, "agency_only": 3, "abstained": 1, "insufficient": 2},
  "sources": [
    {"name": "NASA EONET", "role": "agency", "searched": true, "error": null, "count": 63},
    {"name": "GDACS", "role": "disaster_system", "searched": true, "error": null, "count": 12},
    {"name": "GDELT DOC", "role": "press", "searched": true, "error": "rate-limited by the provider", "count": 0},
    {"name": "Google News RSS", "role": "press", "searched": false, "error": null, "count": 0,
     "note": "not searched: the case list was built from the record only"}
  ],
  "cases": [ ... ]
}
```

The UI reads `sources` and shows a per-source line, exactly like `web/src/Detail.tsx:300-312` does for report sources.

---

## 4. Decisions taken (and why)

| Decision | Choice | Why |
|---|---|---|
| Where the witnesses live | Independent **data** sources + an internal cross-family check | Human testimony needs consent, moderation and a personal-data posture this project has explicitly avoided (`AI_USE.md`: "No personal or private data was given to any AI tool"). Data witnesses are reproducible and citable. |
| Case candidates | EONET events ∪ GDACS events ∪ the record's own unusually high months | EONET and GDACS only start around 2016–2017; the third source keeps cases spanning 2000→today. |
| Satellite witness granularity | Per **cell** (the grid) plus per **area** (the monthly block) | The grid answers "where", the area block answers "how unusual". Both are already published. |
| Abstention | A witness that cannot speak says so | This is the semantic the whole project needs and currently gets wrong in one place (`news.assess`, finding B7). "No observer" ≠ "nothing happened". |
| Verdict set | 5–6 outcomes including `agency_only` | The reverse direction is the novel part; nothing in the product today asks it. |
| Population | WorldPop Global 2000–2020, **1 km**, 2020 | Verified: 234 MB for all nine countries, key-free, reads in seconds. 100 m would multiply the download for no gain at 0.1°. |
| Hospitals, roads | OpenStreetMap via Overpass | The project is already OSM-based (Nominatim, OpenFreeMap) and cites it. Overpass needs no key. |
| Exposure scope | **Static context** per area; the record supplies the time axis | Time-varying exposure (who is exposed *this month*) needs the record joined per month per cell — doable, but it is a second rebuild of the whole join and it is the thing to cut if the window closes. |
| Population aggregation | Centre-based sum of 1 km cells into the 0.1° cell | At 1 km source and 0.1° target a target cell holds ~121 source cells, so the edge error is ~1 %. The method is stated in the output; exact area-weighting is the upgrade. |
| Runtime dependencies | **None** | `server/requirements.txt` unchanged except for what `cases.py` needs — and it needs nothing new, since `news.py` already does the fetching. |
| Build order | Exposure first (independent of the record), then the casebook | Exposure is 250 lines and unblocks immediately; the casebook can also ship without a rebuild. |

---

## 5. Build order

Two people can work these in parallel on Friday evening; the two features share no module.

```
Friday evening
  Person A ── scripts/build_exposure.py
               ├─ download 9 WorldPop country files (234 MB)      ~4 min
               ├─ aggregate to the 0.1° grid per area             ~2 min
               ├─ Overpass: hospitals + major roads, 9 areas      ~7 min
               └─ write data/regions/<area>/exposure.json        9 files

  Person B ── server/kw/cases.py
               ├─ EONET events per area                          ~1 min
               ├─ GDACS events per area                          ~2 min
               ├─ GDELT timeline (1 request/area)                 ~1 min
               ├─ assemble cases + verdicts from the EXISTING committed JSON
               └─ write data/regions/<area>/cases.json           9 files

Saturday
  one rebuild (003 + 004 + 005 + 006 + S1 + S4 + S8) → refreshes cases.json with
  the corrected record and adds viirs_only to every region file
  → re-run scripts/build_exposure.py if the grid changed (plan 006 changes it)

Saturday evening
  Person A ── tools.py / api.py / mcp_server.py / agent.py wiring for exposure
  Person B ── tools.py / api.py / mcp_server.py / agent.py wiring for cases
  both    ── web/src/Cases.tsx, api.ts, App.tsx tab, Map.tsx overlays

Sunday
  Method page wording, README "Data used" rows, click test, numbers refresh
```

**The casebook does not need the rebuild.** It reads committed JSON. The Saturday rebuild *upgrades* it (it adds the
cross-family witness and corrects the record the satellite witness quotes). If the rebuild slips, the casebook still
ships and still works — with the cross-family witness abstaining, stated in the output.

**Plan 006 (grid weighting) changes the grid**, which changes the cell witness and the population join. Run
`scripts/build_exposure.py` after plan 006, not before, if both land.

---

## 6. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | The casebook publishes the record's own bugs as case verdicts (e.g. the S1 zero-weight months become `contradicted` cases) | certain | high | Fix S1 before shipping. The casebook is a *diagnostic*; it should find real problems, but a judge should not meet the bug before the fix. |
| R2 | EONET / GDACS coverage is thin before 2016 | certain | medium | The record's own unusual months supply the early cases; the press witness carries them. |
| R3 | Overpass rate-limits or times out on the larger boxes (n-california 3°×3°, alberta 3.5°×3°) | medium | medium | Split into sub-boxes, retry with backoff, cache the JSON in git so a failed query never breaks the demo, and record the failure in `sources[].error`. |
| R4 | The population raster is modelled 2020 data and is presented as if it were 2026 | medium | high | Label the vintage everywhere it appears; never compute a "population affected" number, only "population in cells where fire was detected". |
| R5 | The exposure layer reads as a targeting list | low | high | Framing copy is fixed in `exposure.md` §6 and must be reviewed by the research lead before it ships. Seven of nine areas are kiln belts, deltas and rural fire regions. |
| R6 | `cases.json` + `exposure.json` bloat the repository | low | medium | Budget: ≤ 400 KB per area for exposure, ≤ 120 KB for cases. Cap hospitals/roads and record the cap in the output. |
| R7 | The two features land but nothing points at them | medium | high | One Explorer tab, one line in the Method page, one row in the README's "For the judges" table, one badge on the home page. Plan 012 owns the site structure. |
| R8 | Google News RSS refuses the historical month queries (personal-use policy) | low | low | One query per candidate month, never per year per place. Cache for a year. If it fails, the press witness abstains. |

---

## 7. What these features do **not** do

- No fire perimeter, burn scar or burned area. FIRMS gives detections, not a footprint. (Burned area is plan 010's
  MCD64A1, and it would be a *witness*, not a perimeter.)
- No smoke, no fire spread, no ignition model, no forecast.
- No "population affected", no vulnerability index, no casualty or damage estimate.
- No human testimony, no user-generated content, no personal data.
- No change to the harmonization method, the calibration, the record itself, or any published number.
- No new runtime dependency, and no change to `server/requirements.txt` beyond what is already needed.

---

## 8. Related work in the repo

The team's own plan set lives in `docs/mdfiles/plans/` (17 plans + an index + a progress log). The two
features below sit alongside it.

| Plan | Relationship | State |
|---|---|---|
| 001 — drop dead custom areas from the index | The casebook's `region_id` list comes from `tools.list_regions()`; do 001 first so the casebook ships for nine areas, not fifteen | **landed** |
| 002 — keep transfer validation on a single-area rebuild | — | **landed** |
| 014 — fair weight for a satellite that saw nothing | The satellite witness's weight; landed before the 003 rebuild, so the casebook inherits it | **landed** |
| 015 — like-for-like drift diagnostic | The cross-family witness is independent of it, but the record the witness quotes is | **landed** |
| 016 — backend small fixes | The API/tooling patterns these features extend | **landed** |
| 017 — frontend small fixes | The Cases tab must not repeat the raw-scale hole, the focus bug or the missing `.catch` | **landed (code)** |
| 003 — measure Aqua drift and the 2023 MODIS version change | Changes every published value the satellite witness quotes; the casebook must be rebuilt after it | open |
| 004 — out-of-sample interval coverage | Changes the CI the satellite witness reports | open |
| 005 — backtest the early-warning rule | — | open |
| 006 — weight map cells like area totals | Changes `grid.json`, hence the cell witness and the exposure join | open |
| 009 — after MODIS, switch satellites off | — | open |
| 010 — burned area (MCD64A1) | Becomes a **witness**; the schema reserves the slot | open, P2 |
| 011 — Dhaka kiln inventory | Becomes a **witness** for the static class | open, P2 |
| 012 — structure the site around the awards | Owns where the Cases tab and the exposure section sit in the nav | open |
| 013 — submission assets | Needs a screenshot of the Cases tab | open |

---

## 9. State of the working tree when these docs were written

The team has been landing fixes from the code scan in parallel with this design. **These are already done — do not
re-implement them:**

| Landed | Where |
|---|---|
| The `combine` zero-weight fix (a sensor that detected nothing no longer outvotes one that did) | `science.py:108` — `counting = cv * (mu / v) if v > 0 else (math.sqrt(cv) * mu if mu > 0 else cv)` |
| `_drift` on a common month set (like-for-like across years) | `build.py` — `_drift(block, keys, min_months=6)` |
| `transfer_validation` carried forward on a single-area rebuild | `build.py` — `meta["transfer_validation"] = json.loads(old.read_text(...))` |
| `provenance.source` no longer overwritten by a duplicate dict key | `build.py` |
| `data/sensor_days.parquet` copied into the Docker image | `Dockerfile` |
| The alert store marks a notification only **after** delivery | `alerts.py` — `check(token, once, mark=True)` and the new `_mark()` |
| The alert limits are checked **before** a build is started | `alerts.py` — `_check_limits()` |
| A failed EONET fetch is reported, not rendered as silence | `alerts.py` — `events_error` |
| `find_place` moved into the tool layer, so the agent and the MCP server agree | `tools.py`, `mcp_server.py` |
| The dead `aoi-*` areas removed from the index; the web app reads `/api/regions` first | `data/regions/index.json`, `web/src/api.ts` |
| `code_version` recorded with `git describe --always --dirty` | `build.py` |

**Still needed for these two features** (nothing else in the repo does them):

| Still to do | Where |
|---|---|
| `viirs_only` — the VIIRS-only harmonized series, one line in `_block` | `build.py` — `casebook.md` §4.3, Step 1 |
| EONET items keep the event `id` and `start_date` | `news.py` — `casebook.md` §6.1, Step 2 |
| `kw/cases.py` | new module |
| `scripts/build_exposure.py` | new script |
| the runtime readers, endpoints, tools and UI | `casebook.md` §8–9, `exposure.md` §6–8 |

> **Correction carried over from the review of the scan** (`docs/mdfiles/code-scan-review-2026-11-13.md`): the
> `combine` zero-weight fix is simpler than the scan proposed and needs **no tuple change** — `sqrt(cv) * mu` in the
> zero branch. `casebook.md` does not depend on that detail, but the cross-family witness does depend on the
> published `aqua_only` and `viirs_only` series, which are separate from it.

**Consequence for risk R1** (the casebook publishing the record's own bugs): the `combine` fix has landed, so the
worst known failure of the satellite witness is closed. The casebook can ship.
