# Contracts — the two new features

**Date:** 2026-11-13 · **Status:** design · **Base commit:** `1e99c85`

This is the single reference for every shape either feature touches. The feature docs explain *why*; this file
defines *what*, exactly. When a shape appears in two places, this file wins.

**Convention used throughout:** `null` means *not measured*; it is never replaced by `0`. A value that could not be
obtained is `null` plus a reason string, never a zero that reads as a measurement.

---

## 1. `data/regions/<area>/cases.json`

Written by `kw.cases.build_cases()`. Read by `tools.list_cases()` and `tools.get_case()`.

```jsonc
{
  "built_at": "2026-11-13T20:04:11+00:00",     // ISO 8601 UTC, when the file was written
  "area": "dhaka-kilns",                        // the region id
  "data_through": "2026-11-12",                 // the record's last date, copied from meta.json
  "counts": {                                   // verdict -> number; must sum to len(cases)
    "corroborated": 41, "reported": 12, "satellite_only": 8,
    "agency_only": 3, "abstained": 1, "insufficient": 2
  },
  "sources": [                                  // one entry per witness source; errors are recorded, never hidden
    {
      "name": "NASA EONET",
      "role": "agency",                          // agency | disaster_system | press | burned_area | inventory
      "searched": true,                          // false = deliberately not searched (say why in note)
      "error": null,                             // string when the source failed
      "count": 63,                               // items found; 0 when the source failed
      "note": null,                              // why it was skipped, when searched is false
      "url": "https://eonet.gsfc.nasa.gov/api/v3"  // the endpoint or query that was used
    }
  ],
  "caveat": "A witness that could not see says so. An absent report is not evidence that nothing happened.",
  "cases": [ /* Case[], §1.1 */ ]
}
```

### 1.1 `Case`

```jsonc
{
  "id": "eonet-14211",              // unique within the area. Source-prefixed:
                                    //   "eonet-<id>" | "gdacs-<id>" | "rec-<period>-<cellIndex>"
  "title": "Wildfire in Sylhet",    // the event title, or a generated one for record-derived cases
  "date": "2019-04-12",             // the event's start date (YYYY-MM-DD), or the first day of the period
  "lon": 91.87, "lat": 25.02,       // WGS84 degrees
  "place": "Sylhet",                // nearest named place, or null
  "period": "2019-04",              // the calendar month the case falls in ("YYYY-MM")
  "cell": [25.02, 91.87],           // the 0.1 degree cell's [lat, lon] (the SW corner, as grid.json stores it)
  "cell_index": 1837,               // the index into grid.json's "cells" array
  "witnesses": { /* §1.2 */ },
  "verdict": "corroborated",        // one of the six in §1.3
  "verdict_label": "Two independent witnesses agree",
  "flags": [],                      // e.g. ["cross_family_disagree"]; informational, never changes the verdict
  "note": ""                        // a short human note, only when something needs saying
}
```

### 1.2 `witnesses`

Every key is always present. A witness that could not speak has `"state": "abstain"` and a `"reason"`.

```jsonc
"witnesses": {
  "satellite": {
    "state": "fire",                       // fire | quiet | abstain
    "reason": null,                        // set when state is "abstain"
    "cell_hotspots": 412.3,                // the harmonized value in the case's cell; null when the cell is absent
    "cell_present": true,                  // was the cell present in grid.months[period]?
    "area_hotspots": 1893.4,               // the area total for the period, harmonized
    "ci95": [380.1, 445.0],                // the area total's 95 % interval; null when not available
    "percentile": 99.1,                    // against the same month in other years; null when not available
    "rank": 1, "of_years": 24,             // rank among years; null when not available
    "coverage": 1.0,                       // the area's share of days observed by the best observer
    "sensors": ["VIIRS_SNPP", "MODIS_A"],   // which satellites contributed
    "source": "kiln-watch"
  },

  "cross_family": {
    "state": "fire",                       // fire | quiet | abstain
    "reason": null,                        // e.g. "the region file predates the VIIRS-only series"
    "modis_only": 398.0,                   // the harmonized value from the MODIS satellites alone
    "viirs_only": 421.5,                   // ... and from the VIIRS satellites alone
    "ratio": 0.94,                         // viirs_only / modis_only; null when either is null
    "agrees": true,                        // ratio within 0.8–1.25 — a smoke alarm, not a test
    "source": "kiln-watch"
  },

  "agency": {                              // null when there is no agency witness for this case
    "source": "NASA EONET",
    "date": "2019-04-12",
    "url": "https://eonet.gsfc.nasa.gov/event/14211"
  },

  "disaster_system": {                     // null when there is none
    "source": "GDACS",
    "alert": "orange",                     // green | orange | red
    "severity": "Severe",                  // the GWIS severity text
    "burned_area_ha": 1180,                // GWIS burned area, hectares; null when not published
    "date": "2019-04-10",
    "url": "https://www.gdacs.org/..."
  },

  "press": {                               // null when there is none
    "source": "GDELT DOC",                 // or "Google News RSS" for pre-2017 months
    "count": 14,                           // articles in the case's month matching the place and fire words
    "outlets": ["The Daily Star"],         // up to 5 outlet names
    "sample_urls": ["https://..."],        // up to 5 links
    "query": "(\"Sylhet\") (wildfire OR \"forest fire\" OR blaze)"   // the exact query, for reproducibility
  },

  "burned_area": null,                     // reserved for plan 010 (MCD64A1)
  "inventory": null                        // reserved for plan 011 (kiln inventory)
}
```

### 1.3 Verdicts

| Value | Label | Condition |
|---|---|---|
| `corroborated` | Two independent witnesses agree | satellite `fire` **and** (agency or disaster_system present) |
| `reported` | Reported, not seen by the satellites | satellite `fire` and press only, **or** satellite `quiet` and press present |
| `satellite_only` | Only the satellites saw it | satellite `fire`, no external witness |
| `agency_only` | **The record missed it** | satellite `quiet` and (agency or disaster_system present) |
| `abstained` | The record could not see | satellite `abstain` |
| `insufficient` | Nobody saw anything | satellite `quiet`, no external witness |

`counts` must contain exactly these six keys.

---

## 2. `data/regions/<area>/exposure.json`

Written by `scripts/build_exposure.py`. Read by `tools.exposure()`.

```jsonc
{
  "built_at": "2026-11-13T19:52:41+00:00",
  "area": "dhaka-kilns",
  "bbox": [89.9, 23.4, 90.9, 24.2],
  "deg": 0.1,

  "population": {
    "source": "WorldPop Global 2000-2020 population grid, 1 km aggregated",
    "url": "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/BGD/bgd_ppp_2020_1km_Aggregated.tif",
    "vintage": 2020,
    "method": "area-weighted sum of 1 km source cells into the 0.1 degree grid, computed in degrees",
    "note": "Modelled population, not a census. Not the population on the day of a fire."
  },

  "infrastructure": {
    "hospitals_source": "OpenStreetMap via Overpass API: amenity=hospital|clinic|doctors, healthcare=hospital|clinic",
    "roads_source": "OpenStreetMap via Overpass API: highway=motorway|trunk|primary",
    "queried_at": "2026-11-13T19:41:02+00:00",
    "mirror": "overpass-api.de",
    "caps": {"hospitals": 5000, "roads": 8000},
    "truncated": {"hospitals": false, "roads": false}
  },

  "totals": { "population": 33425932, "hospitals": 214, "major_roads": 2338 },

  "cells": [[23.4, 89.9, 12480], ...],       // [lat, lon, population] — INDEX-PARALLEL with grid.json "cells"

  "hospitals": [
    { "name": "উত্তরা আধুনিক মেডিকেল কলেজ ও হাসপাতাল", "kind": "hospital",
      "lat": 23.79, "lon": 90.39, "cell": [23.7, 90.3], "nearest_fire_km": 0.0 }
  ],

  "roads": [
    { "name": "নবীনগর - চন্দ্রা মহাসড়ক", "kind": "primary",
      "lat": 23.81, "lon": 90.41, "cells": [[23.7, 90.3], [23.8, 90.4]], "nearest_fire_km": 0.0 }
  ],

  "caveat": "Population and infrastructure inside cells where the harmonized record shows fire. A context layer, not an impact estimate: FIRMS gives detections, not a fire perimeter, and there is no smoke or fire-spread model here."
}
```

### 2.1 The index-parallel rule

> `exposure.cells[i]` is the population of `grid.cells[i]`, for every `i`.

`grid.json`'s `cells` array is the authority. The build script reads it verbatim and writes the population in that
order. A self-check asserts `len(exposure.cells) == len(grid.cells)`.

Consequence: a cell's *position* is always `grid.cells[i]`, and its population is `exposure.cells[i][2]`. Neither file
stores the cell's coordinates twice.

### 2.2 `nearest_fire_km`

The great-circle distance from the hospital (or the road's representative point) to the nearest **cell that has had
fire in any month since 2000**. A static area-level statistic, not a per-month distance. `null` when the area has no
fire cell at all.

---

## 3. `meta.json` additions

Three additions, all inside the existing `meta.json`. No new top-level file, no new top-level key.

### 3.1 `method` — two new entries

`meta["method"]` is a `dict[str, str]`; `web/src/Record.tsx:567` renders `Object.entries(m.method)` as the
"Processing steps" list, so new entries appear on the Method page with no UI change.

```python
meta["method"]["witnesses"] = (
    "Each fire case is heard by independent witnesses: the harmonized satellite record, a MODIS-against-VIIRS "
    "cross-check, NASA EONET, GDACS and the press. A witness that could not see says so, so a missing report is "
    "never read as 'no fire'.")
meta["method"]["exposure"] = (
    "Population (WorldPop 2020, 1 km) and infrastructure (OpenStreetMap) inside the 0.1 degree cells where the "
    "record shows fire. A context layer, not an impact estimate: there is no fire perimeter, no smoke and no fire "
    "spread here.")
```

### 3.2 `external_sources` — a new array

```jsonc
"external_sources": [
  { "name": "NASA EONET (Earth Observatory Natural Event Tracker)", "role": "fire case witness",
    "url": "https://eonet.gsfc.nasa.gov/", "vintage": "event list to 2026-11-12", "license": "public domain (NASA)" },
  { "name": "GDACS (European Commission JRC / UN OCHA)", "role": "fire case witness",
    "url": "https://www.gdacs.org/", "vintage": "2026-11-13", "license": "GDACS terms of use" },
  { "name": "WorldPop Global 2000-2020 population grid, 1 km", "role": "population context",
    "url": "https://www.worldpop.org/", "vintage": "2020", "license": "CC BY 4.0" },
  { "name": "OpenStreetMap contributors (Overpass API)", "role": "hospitals and major roads",
    "url": "https://www.openstreetmap.org/copyright", "vintage": "2026-11-13", "license": "ODbL 1.0" }
]
```

`role` is one of `fire case witness` | `population context` | `infrastructure context`. The Method page renders this
array, so the provenance surface stays data-driven rather than hand-typed into the page.

### 3.3 `cases` and `exposure` availability flags

```jsonc
"features": {
  "cases": { "available": true, "built_at": "2026-11-13T20:04:11+00:00", "count": 67 },
  "exposure": { "available": true, "built_at": "2026-11-13T19:52:41+00:00" }
}
```

`available: false` with a `reason` when the file could not be built. The UI hides the tab and says why, rather than
showing an empty table.

---

## 4. HTTP API

All under the existing `/api/regions/{rid}/` prefix. `_guard` (`api.py:48-54`) maps `tools.NotFound` → **404** and
`ValueError` → **400**.

### 4.1 `GET /api/regions/{rid}/cases`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `verdict` | string | all | one of the six verdict values |
| `limit` | int | 50 | clamped to 1–200 |

**200**

```jsonc
{
  "region_id": "dhaka-kilns",
  "as_of": "2026-11-13T20:04:11+00:00",
  "data_through": "2026-11-12",
  "counts": { "corroborated": 41, "reported": 12, "satellite_only": 8, "agency_only": 3, "abstained": 1, "insufficient": 2 },
  "sources": [ /* as stored */ ],
  "caveat": "...",
  "total": 67,
  "cases": [ /* Case[], §1.1 */ ]
}
```

**404** — the area has no `cases.json` (never built).
**400** — an unknown `verdict` value.

### 4.2 `GET /api/regions/{rid}/cases/{case_id}`

**200** — one `Case` (§1.1).
**404** — unknown area or unknown case id.

### 4.3 `GET /api/regions/{rid}/exposure`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `period` | string | all | a calendar month `"YYYY-MM"` |

**200**

```jsonc
{
  "region_id": "dhaka-kilns",
  "period": "2026-11",              // null when the summary is over every cell with fire since 2000
  "fire_cells": 412,
  "population": 1239877,
  "population_source": { /* the population block from exposure.json */ },
  "hospitals": 68,
  "hospital_list": [ /* up to 50 */ ],
  "major_roads": 1240,
  "road_list": [ /* up to 50 */ ],
  "caveat": "..."
}
```

**404** — the area has no `exposure.json`.
**400** — a malformed `period`.

---

## 5. MCP tools

### 5.1 `get_fire_cases`

```python
@mcp.tool(title="Fire cases", annotations=RO)
def get_fire_cases(region_id: str, verdict: str = "", limit: int = 20) -> dict:
    """Fire cases for an area with independent witnesses — the harmonized record, a MODIS-against-VIIRS
    cross-check, NASA EONET, GDACS and the press — and an agreement verdict. verdict='agency_only'
    returns the fires the record does not show. A witness that could not see says so: missing reports
    are never evidence that nothing happened."""
```

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `region_id` | string | required | a built area id |
| `verdict` | string | "" | one of the six; empty means all |
| `limit` | int | 20 | clamped to 1–200 |

Returns the §4.1 payload. `annotations=RO` (`readOnlyHint=True, openWorldHint=False`) is correct: the tool reads
committed JSON and makes no network call.

### 5.2 `get_exposure`

```python
@mcp.tool(title="Exposure in the fire cells", annotations=RO)
def get_exposure(region_id: str, period: str = "") -> dict:
    """Population, hospitals and major roads in the 0.1 degree cells where the harmonized record
    shows fire. A context layer, not an impact estimate: there is no fire perimeter, no smoke and no
    fire spread here, and population is modelled 2020 data (WorldPop)."""
```

Returns the §4.3 payload.

---

## 6. Agent (Gemini) tools

### 6.1 Declarations — appended to `DECLS` in `server/kw/agent.py`

```python
{"name": "fire_cases", "description": "Fire cases with independent witnesses (the harmonized record, a "
 "MODIS-versus-VIIRS cross-check, NASA EONET, GDACS and the press) and an agreement verdict. "
 "verdict='agency_only' returns the fires the record does not show.", "parameters": {"type": "OBJECT",
 "properties": {"region_id": _S, "verdict": _S}, "required": ["region_id"]}},

{"name": "exposure", "description": "Population, hospitals and major roads in the 0.1 degree cells where the "
 "record shows fire. Context, not an impact estimate: population is modelled 2020 data, and there is no "
 "fire perimeter.", "parameters": {"type": "OBJECT", "properties": {"region_id": _S, "period": _period},
 "required": ["region_id"]}},
```

### 6.2 `_RUN` entries — appended to the `_RUN` map

```python
"fire_cases": lambda a: tools.list_cases(a["region_id"], a.get("verdict") or None, int(a.get("limit", 20))),
"exposure": lambda a: tools.exposure(a["region_id"], a.get("period") or None),
```

### 6.3 Two lines in `SYSTEM` (`agent.py:20-39`)

> - A case witness that abstains means the source could not see. Never describe an absent witness as a negative
>   finding.
> - Exposure is context, not impact. Never say who was affected, reached or endangered. Say how many people and
>   facilities lie in the cells where detections were recorded.

---

## 7. Web client — `web/src/api.ts`

### 7.1 Types

```ts
export type WitnessState = "fire" | "quiet" | "abstain";
export type CaseVerdict = "corroborated" | "reported" | "satellite_only" | "agency_only" | "abstained" | "insufficient";

export type CaseWitness = { source: string; state?: WitnessState; reason?: string | null } & Record<string, unknown>;

export type FireCase = {
  id: string; title: string; date: string; lon: number; lat: number; place: string | null;
  period: string; cell: [number, number]; cell_index: number;
  witnesses: {
    satellite: { state: WitnessState; reason: string | null; cell_hotspots: Num; cell_present: boolean;
      area_hotspots: Num; ci95: [Num, Num] | null; percentile: Num; rank: Num; of_years: Num;
      coverage: Num; sensors: string[] };
    cross_family: { state: WitnessState; reason: string | null; modis_only: Num; viirs_only: Num;
      ratio: Num; agrees: boolean };
    agency: CaseWitness | null; disaster_system: CaseWitness | null; press: CaseWitness | null;
  };
  verdict: CaseVerdict; verdict_label: string; flags: string[]; note: string;
};

export type CasesResponse = {
  region_id: string; as_of: string; data_through: string;
  counts: Record<CaseVerdict, number>;
  sources: { name: string; role: string; searched: boolean; error: string | null; count: number; note: string | null; url: string }[];
  caveat: string; total: number; cases: FireCase[];
};

export type ExposureResponse = {
  region_id: string; period: string | null; fire_cells: number; population: number;
  population_source: { source: string; url: string; vintage: number | string; method: string; note: string };
  hospitals: number; hospital_list: { name: string; kind: string; lat: number; lon: number; cell: [number, number]; nearest_fire_km: Num }[];
  major_roads: number; road_list: { name: string; kind: string; lat: number; lon: number; cells: [number, number][]; nearest_fire_km: Num }[];
  caveat: string;
};
```

### 7.2 API calls — added to the `api` object

```ts
cases: (id: string, verdict?: string, limit = 50) =>
  json<CasesResponse>(`/api/regions/${id}/cases${verdict ? `?verdict=${verdict}&limit=${limit}` : `?limit=${limit}`}`),
case: (id: string, caseId: string) => json<FireCase>(`/api/regions/${id}/cases/${caseId}`),
exposure: (id: string, period?: string) =>
  json<ExposureResponse>(`/api/regions/${id}/exposure${period ? `?period=${period}` : ""}`),
```

### 7.3 Rendering rules

- A witness with `state: "abstain"` renders **"could not see"**, never "no fire", never "0".
- A null number renders **"–"** via the existing `fmt()` (`api.ts:231-234`), never `0`.
- `sources[]` with `error` renders the error next to the source name — the same pattern as
  `web/src/Detail.tsx:300-312`.
- The verdict is shown as **text plus colour**, never colour alone.

---

## 8. Error and fallback matrix

| Situation | HTTP | Payload | UI |
|---|---|---|---|
| area has no `cases.json` | 404 | FastAPI's `{"detail": "unknown region '<id>'"}` | the Cases tab is hidden; `meta.features.cases.reason` explains |
| area has no `exposure.json` | 404 | same | the exposure panel shows "not built for this area" |
| unknown `verdict` | 400 | `{"detail": "..."}` | — |
| malformed `period` | 400 | `{"detail": "..."}` | — |
| EONET/GDACS/GDELT failed at build time | 200 | `sources[].error` set, `counts` lower | the source line shows the error; the case list is still shown |
| no satellite observed in the period | 200 | satellite witness `state: "abstain"` | "could not see" |
| Overpass returned nothing for an area | 200 | `truncated.roads: true` or a `sources` error | "OpenStreetMap query failed — roads are missing from this view" |
| the record has no grid cells for a period | 200 | `fire_cells: 0`, `population: 0` | "no fire recorded in this month" — **not** "0 people exposed" |

---

## 9. Backwards compatibility

| Change | Effect on existing consumers |
|---|---|
| `meta["method"]` gains two entries | `Record.tsx:567` renders them automatically — the Method page grows two lines. No other consumer reads `method`. |
| `meta["external_sources"]` added | new key; nothing reads it yet except the Method page |
| `meta["features"]` added | new key; nothing reads it yet except the Explorer tab |
| `monthly.json` gains `classes.veg.viirs_only` | `web/src/api.ts`'s `ClassBlock` type gains an optional field. **Every consumer of `Block` must tolerate its absence** — the files that predate it are still in git and are still served. |
| `news.eonet()` items gain `id`, `start_date`, `end_date` | three additive fields on a dict; the only consumers are `news._search` (which passes items through) and the ReportList UI (which ignores unknown fields) |
| new region files `cases.json`, `exposure.json` | new files; `tools._read` raises `NotFound` for an area that has none, which the API maps to 404 |
| new API routes | additive |
| new MCP tools | additive; `TOOLS` in `web/src/pages/Connect.tsx:5` gains two rows so the tool count shown to judges stays right (31 → 33) |
| new agent tool declarations | additive; the agent's `SYSTEM` prompt mentions them |
