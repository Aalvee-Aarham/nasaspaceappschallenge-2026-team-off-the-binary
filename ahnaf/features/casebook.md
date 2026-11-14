# Feature A — the casebook: every fire, heard by several witnesses

**Date:** 2026-11-13 · **Status:** design · **Base commit:** `1e99c85` · **Depends on:** nothing — the casebook reads
the committed region JSON, so it ships without a rebuild. (Plan 001 has landed, so the area list is the nine presets.)

---

## 1. The problem this solves

Today the product can only ask the question in one direction. `news.match_months` (`news.py:283-317`) walks the
record outward: *for this month, were there reports?* → `corroborated` / `satellite_only` / `reported_typical`.

There is no code path that takes a fire event and asks the record about it. So a fire that NASA EONET and the press
recorded, and that the satellite record shows as quiet, **does not appear anywhere in the product**. For a fire
manager, that is the more important half of the question: the record is the thing under test.

The casebook turns the record into one witness among several and lets the witnesses disagree on the page.

```
        NASA EONET ─────┐
        GDACS      ─────┤
        press      ─────┼──►  case  ──►  verdict
  the record ──────────┤                      │
  (MODIS vs VIIRS) ────┘                      └──►  what is missing, and who says so
```

---

## 2. A case

A **case** is one fire, with a date, a place, and a panel of witnesses.

```jsonc
{
  "id": "eonet-14211",
  "title": "Wildfire in Sylhet",
  "date": "2019-04-12",              // the event's start date
  "lon": 91.87, "lat": 25.02,
  "place": "Sylhet",                 // nearest named place, if known
  "period": "2019-04",               // the record period the case falls in
  "cell": [25.02, 91.87],            // the 0.1 degree cell
  "witnesses": {
    "satellite":    { "state": "fire", "hotspots": 412.3, "ci95": [380.1, 445.0],
                      "percentile": 99.1, "rank": 1, "of_years": 24, "coverage": 1.0,
                      "sensors": ["VIIRS_SNPP", "MODIS_A"], "area_hotspots": 1893.4,
                      "source": "kiln-watch" },
    "cross_family": { "modis_only": 398.0, "viirs_only": 421.5, "ratio": 0.94,
                      "agrees": true, "state": "fire", "source": "kiln-watch" },
    "agency":       { "source": "NASA EONET", "date": "2019-04-12", "url": "https://eonet.gsfc.nasa.gov/..." },
    "disaster_system": { "source": "GDACS", "alert": "orange", "severity": "Severe",
                         "burned_area_ha": 1180, "url": "https://www.gdacs.org/..." },
    "press":        { "source": "GDELT DOC", "count": 14, "outlets": ["The Daily Star"],
                      "sample_urls": ["https://..."], "query": "(\"Sylhet\") (wildfire OR ...)" }
  },
  "verdict": "corroborated",
  "verdict_label": "Two independent witnesses agree",
  "note": ""
}
```

**Witness states.** Every witness is in one of three states, and the distinction is the whole point:

| State | Meaning |
|---|---|
| `fire` | this witness says there was fire |
| `quiet` | this witness says there was no fire, **and it was in a position to see it** |
| `abstain` | this witness could not see (no satellite observed; no source answered) |

`abstain` is never rendered as `quiet`. A missing report is not a negative report.

---

## 3. Case candidates

Three sources of candidates, so cases span the whole record and not just the EONET era (EONET ≈ 2016+, GDACS 2017+).

| Candidate source | Where it comes from | Coverage | Cost |
|---|---|---|---|
| **A — agency events** | NASA EONET `category=wildfires&status=all` inside the area bbox | ~2016→ | 1 request / area |
| **B — disaster-system events** | GDACS `eventlist=WF` inside the area bbox | 2017→ | 1 request / area |
| **C — the record's own unusual months** | the top-N months by percentile in `monthly.json` | 2000→ | 0 requests |

Candidate C is the important one for coverage: it finds the months the *record* says were unusual, and then asks who
else saw them. A candidate from C that no external source confirms is published as `satellite_only` — "the record says
fire; nothing else in the searched sources mentions it". That is a statement about **coverage of the search**, not
about the world.

**Deduplication.** A and B overlap (the same fire can appear in both) and one event can span several months. Each
candidate is keyed by its **cell** (0.1°) and **period** (calendar month). Multiple sources in the same cell-month
become multiple witnesses of one case, not several cases.

**Cap.** `MAX_CASES = 200` per area, ordered by (verdict severity, date). If an area has more, the cap is recorded in
`meta.json` and shown in the UI, so the list is never silently truncated.

---

## 4. The satellite witness

This is the part that has to be exactly right, because it is the witness the project is testing.

### 4.1 Two levels

**Cell level** (where): the harmonized value for the case's 0.1° cell in the case's month, read from `grid.json`.

```python
# grid.json: months[period] is a list of [cell_index, value]; a cell with no fire is ABSENT
rows = {ci: v for ci, v in grid["months"].get(period, [])}
```

Absence is meaningful: a cell absent from `months[period]` had no fire, *provided* coverage was adequate.

**Area level** (how unusual): from `monthly.json` — the harmonized total, its 95 % interval, the percentile and rank
against the same month in other years, the coverage, and the satellites used.

```jsonc
// monthly.json → classes.veg
{
  "hotspots": { "v": [...], "lo": [...], "hi": [...], "sensors": [[...], ...] },
  "history":  { "median": [...], "ratio": [...], "pct": [...], "rank": [...], "n": [...] },
  "viirs_scale": { ... },
  "celldays": { ... },
  "aqua_only": [...]
}
```

### 4.2 Abstention, and why it is different from "quiet"

Coverage lives in `monthly.json` at the **area** level: `coverage[observer][i]` is the share of the period's days that
observer delivered data anywhere on Earth. There is no per-cell coverage, so the cell-level witness inherits the
area's coverage for that period.

```python
def satellite_state(area_cov, cell_value, present_in_grid):
    """Three states, never two."""
    if max(area_cov.values()) == 0:
        return "abstain"            # no satellite observed anywhere in the area that period
    if present_in_grid:
        return "fire" if cell_value > 0 else "quiet"
    return "quiet"                  # the cell was observed and had no fire
```

The `abstain` branch is what makes the record honest in the `2001-W25` / `2001-W26` hole (every observer at zero
coverage in all nine committed region files) and in any future gap.

> **Rule, stated once:** a witness that could not see says `abstain`. Only a witness that could see and saw nothing
> says `quiet`.

### 4.3 The cross-family witness

The satellite witness is not one thing; it is five instruments that are *supposed* to agree. The internal cross-family
witness makes that checkable per month:

- **modis_only** — the harmonized value from the MODIS satellites alone. **Already published**: `aqua_only` in
  `monthly.json` (`build.py:344`).
- **viirs_only** — the same from the VIIRS satellites alone. **Does not exist yet**; it is one line in `_block`:

```python
# server/kw/build.py, in _block(), right after the aqua_only line
aqua_only = _hotspots(agg, keys, cov, cls, cal, set(MODIS_SATS))[0]
viirs_only = _hotspots(agg, keys, cov, cls, cal, set(VIIRS))[0]      # ← new
```

`_active(cov, i, allowed)` filters by `allowed` after choosing (`build.py:66-70`), so `allowed=set(VIIRS)` drops
MODIS and keeps the VIIRS observers. No other change is needed.

> **Compatibility.** `viirs_only` is **optional**. `cases.py` reads it with `.get("viirs_only")`; when it is missing
> the cross-family witness is `abstain` and says why. That is what lets the casebook ship against today's committed
> region files, before any rebuild.

### 4.4 What the cross-family witness says

```python
def cross_family(modis_only, viirs_only, coverage, period):
    if modis_only is None or viirs_only is None:
        return {"state": "abstain", "reason": "the region file predates the VIIRS-only series"}
    if max(coverage.values()) == 0:
        return {"state": "abstain", "reason": "no satellite observed"}
    if modis_only == 0 and viirs_only == 0:
        return {"state": "quiet", "modis_only": 0, "viirs_only": 0, "ratio": None, "agrees": True}
    r = viirs_only / modis_only if modis_only else None
    return {"state": "fire", "modis_only": modis_only, "viirs_only": viirs_only,
            "ratio": round(r, 3) if r else None,
            "agrees": (r is not None and 0.8 <= r <= 1.25)}
```

The `agrees` band (0.8–1.25) is a **judgement band, not a statistical test** — it says "these two families are
within 25 % of each other". It is a smoke alarm for the exact failure mode the plan-003 work is about: the two families
diverging from 2024 onward.

> **Stated honestly in the UI:** "the two instrument families disagree by more than 25 % in this month". Not "the
> record is wrong" — the casebook cannot know which family is right.

---

## 5. Verdict logic

```python
VERDICTS = ("corroborated", "reported", "satellite_only", "agency_only", "abstained", "insufficient")

def verdict(sat, cross, agency, disaster, press):
    """sat: 'fire'|'quiet'|'abstain'.  cross: dict.  agency/disaster: dict|None.  press: dict|None."""
    external = [w for w in (agency, disaster, press) if w]
    strong = [w for w in (agency, disaster) if w]      # an event record, not a mention

    if sat == "abstain":
        return "abstained"                              # the record cannot speak
    if sat == "fire":
        if strong:
            return "corroborated"                       # the record and an event record agree
        if press:
            return "reported"                           # the record and the press agree
        return "satellite_only"                         # no external source mentions it
    # sat == "quiet"
    if strong:
        return "agency_only"                            # ← the reverse direction: the record missed it
    if press:
        return "reported"                               # reported, but the record shows no fire
    return "insufficient"                               # nobody saw anything
```

| Verdict | Plain-language label | Meaning |
|---|---|---|
| `corroborated` | Two independent witnesses agree | The record shows fire and an event record (EONET or GDACS) exists. |
| `reported` | Reported, not seen by the satellites | An event record or the press mentions a fire; the record does not show one in that cell. |
| `satellite_only` | Only the satellites saw it | The record shows fire; nothing in the searched sources mentions it. **Not** "no fire happened". |
| `agency_only` | **The record missed it** | An event record exists; the record shows no fire. The novel one. |
| `abstained` | The record could not see | No satellite observed in that period. The record says nothing. |
| `insufficient` | Nobody saw anything | No fire in the record, no report. |

### 5.1 The `agency_only` cases are the headline

They are the only place in the product where a fire the satellites missed becomes visible. They must be presented
carefully, because **the record can be wrong**:

> *"NASA EONET records a fire here on this date. The harmonized record shows no fire in that cell for that month.
> That is either a fire below the detection threshold or outside the cell, or a gap in the record. The case tells you
> which witness is missing — not which one is wrong."*

The UI shows the satellite witness's **coverage** next to the verdict, so a judge can see whether the record was in a
position to see it.

### 5.2 The `contradicted` flag (an overlay, not a verdict)

Where the satellite witness says `fire` but the external witness records a *much larger* event, or where the two
families disagree, the case carries a flag:

```jsonc
"flags": ["cross_family_disagree", "satellite_far_below_report"]
```

The flags never change the verdict; they add context. `satellite_far_below_report` is a **threshold on the ratio**
between the reported burned area and the harmonized hotspots — which needs a documented conversion and therefore does
**not** ship in v1. Only `cross_family_disagree` ships in v1.

---

## 6. Sources, and what each one costs

### 6.1 NASA EONET (the agency witness)

`news.eonet()` already exists (`news.py:84-101`) but it takes the **last** geometry of an event
(`geo[-1]`, `news.py:92`) and the date of that geometry. A case needs the event's **start date** and a stable id.

```python
# news.py, in eonet(): add three fields to the item dict
{
  "source": "NASA EONET",
  "id": ev.get("id"),                          # ← new
  "title": ev.get("title"),
  "date": (g.get("date") or "")[:10],          # last geometry (kept)
  "start_date": (ev.get("start_date") or "")[:10],   # ← new
  "end_date": (ev.get("end_date") or "")[:10],       # ← new
  "url": ..., "lon": ..., "lat": ...,
}
```

The `id` is the case key for EONET-sourced cases. The URL becomes `https://eonet.gsfc.nasa.gov/event/<id>/`.

### 6.2 GDACS (the disaster-system witness)

`news_more.gdacs(start, end, bbox)` already returns exactly what a case needs: `alert` (alertlevel), `severity`,
`burned_area_ha` (from `severitydata`), `country`, `fromdate`/`to`, `lat`/`lon`, `url`. **No change needed.**

GDACS uses `eventlist=WF` (wildfire). Its burned area comes from GWIS and is in hectares.

### 6.3 The press (the press witness)

Two different mechanisms, because the cost profile differs:

- **Counts for every case month — one request per area.** `news.gdelt_volume(places, langs, start, end)` already
  returns a `{month: article_count}` map from GDELT's `timelinevolraw` mode. One call per area covers 2017→now for
  every month at once. This is the count the case shows.
- **Headlines for one case — one request per case, on demand.** `news_more.google_news(query, lang, start, end)` for
  the case's month and the area's languages. Called only when the user opens the case detail, cached for a year by
  `news._cached`.

For **pre-2017** cases GDELT does not exist (`news.GDELT_START`, `news.py:21`), so the count comes from a Google News
RSS query for that single month in the area's primary language plus English. One query per pre-2017 candidate, never
per year.

> **Google News RSS terms:** personal, non-commercial use of its public RSS feeds (`news_more.py:5`). The project
> already states this on the News page. Keep the request rate modest and cache for a year.

### 6.4 Burned area and the kiln inventory — reserved, not implemented

Plan 010 (MCD64A1) and plan 011 (kiln inventory) become witnesses when they land. The schema reserves them:

```jsonc
"witnesses": {
  "satellite": {...}, "cross_family": {...}, "agency": {...}, "disaster_system": {...}, "press": {...}
  // reserved: "burned_area": {...}, "inventory": {...}
}
```

---

## 7. Storage

`data/regions/<area>/cases.json`, written at build time by `kw.cases.build_cases()`, using the same atomic pattern as
`build.py:820-824`:

```python
tmp = folder / "cases.json.tmp"
tmp.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
os.replace(tmp, folder / "cases.json")
```

Size budget: ≤ 120 KB per area. With 30–60 cases at ~1.5 KB each that is comfortable; the press witness's
`sample_urls` is capped at 5 per case to hold the budget.

**Not committed:** the raw EONET/GDACS/GDELT responses. They are cached under `data/news_cache/` (already gitignored)
with a 365-day TTL, so a rebuild does not re-hit the network.

---

## 8. Runtime surfaces

### 8.1 `server/kw/tools.py`

```python
def list_cases(region_id, verdict=None, limit=50, include_reserved=False):
    """Fire cases for an area with their witnesses. verdict filters: corroborated, reported,
    satellite_only, agency_only, abstained, insufficient."""
    c = _read(region_id, "cases")          # raises NotFound → 404 at the API
    rows = [x for x in c["cases"] if verdict is None or x["verdict"] == verdict]
    return {"region_id": region_id, "as_of": c["built_at"], "counts": c["counts"],
            "sources": c["sources"], "cases": rows[:limit], "total": len(c["cases"])}


def get_case(region_id, case_id):
    """One fire case with every witness."""
    c = _read(region_id, "cases")
    for x in c["cases"]:
        if x["id"] == case_id:
            return x
    raise NotFound(f"no case '{case_id}' in '{region_id}'")


def exposure(region_id, period=None):
    """Population and infrastructure in the cells where the record shows fire. Context, not impact."""
    ...
```

`tools.py` already imports `news`, `science` and `build`; `cases.py` will import `news` in turn. Watch for a
circular import: `news.py` imports `kw.firms`; `tools.py` imports `kw.build`; `build.py` will import `kw.cases`.
**`cases.py` must not import `tools.py`** — it reads the region files directly.

### 8.2 `server/kw/api.py`

```python
@app.get("/api/regions/{rid}/cases")
def cases(rid: str, verdict: str | None = None, limit: int = 50):
    return _guard(tools.list_cases, rid, verdict, min(max(limit, 1), 200))

@app.get("/api/regions/{rid}/cases/{case_id}")
def case_detail(rid: str, case_id: str):
    return _guard(tools.get_case, rid, case_id)
```

`_guard` (`api.py:48-54`) already maps `tools.NotFound` → 404 and `ValueError` → 400, so a missing `cases.json`
becomes a clean 404 rather than a 500.

### 8.3 `server/kw/mcp_server.py`

```python
@mcp.tool(title="Fire cases", annotations=RO)
def get_fire_cases(region_id: str, verdict: str = "", limit: int = 20) -> dict:
    """Fire cases for an area with independent witnesses (the harmonized record, a MODIS-vs-VIIRS cross-check,
    NASA EONET, GDACS and the press) and an agreement verdict. Use verdict='agency_only' for the fires the
    record does not show. Missing reports are never evidence that nothing happened."""
    return tools.list_cases(region_id, verdict or None, max(1, min(limit, 200)))
```

`RO` is `ToolAnnotations(readOnlyHint=True, openWorldHint=False)` (`mcp_server.py:29`). These tools read committed
JSON only — they make no network calls — so `openWorldHint=False` is correct.

### 8.4 `server/kw/agent.py`

Two declarations in `DECLS` and two entries in `_RUN`:

```python
{"name": "fire_cases", "description": "Fire cases with independent witnesses and an agreement verdict; "
 "verdict='agency_only' returns the fires the record does not show.", "parameters": {"type": "OBJECT", "properties":
 {"region_id": _S, "verdict": _S}, "required": ["region_id"]}},

{"name": "exposure", "description": "Population and infrastructure in the cells where the record shows fire. "
 "Context, not an impact estimate.", "parameters": {"type": "OBJECT", "properties": {"region_id": _S}, "required": ["region_id"]}},
```

The `SYSTEM` prompt (`agent.py:20-39`) gains one line, because the model must not describe the record's silence as
evidence:

> - A case witness that abstains means the source could not see. Never describe an absent witness as a negative
>   finding.

---

## 9. The UI — the Cases tab

A fourth tab in the Explorer, next to Calendar / Season / Continuity.

```
┌─ Cases ─────────────────────────────────────────────────────────────────┐
│ 41 cases · 12 reported · 3 the record does not show · data through 2026-11-12 │
│ [corroborated 41] [reported 12] [satellite_only 8] [agency_only 3] [abstained 1] │
├───────────────────────────────────────────────────────────────────────────┤
│ 2019-04-12  Sylhet          satellite 412 ± 33 (99th pct)  [EONET][GDACS]  corroborated │
│ 2021-11-03  Dhaka belt      satellite quiet               [press 14]       reported     │
│ 2024-05-18  Punjab          satellite quiet               [EONET]          agency_only  │
└───────────────────────────────────────────────────────────────────────────┘
```

**Left panel (verdict summary + table).** Verdict chips filter the table. The table shows: date, place, the satellite
witness in one cell (`412 ± 33` / `quiet` / `could not see`), the external witnesses as small chips, and the verdict
as a coloured label. The `agency_only` chip is the one that draws the eye, and it is labelled in words, not colour
alone.

**Right panel (the witness panel)**, opened by clicking a row:

```
  NASA EONET        12 Apr 2019 · wildfire event     [source ↗]
  GDACS             orange alert · 1 180 ha burned   [source ↗]
  The press         14 articles, 3 outlets           [sample ↗]
  ─────────────────────────────────────────────────────────────
  The record        412 hotspots (95%: 380–445) in the 0.1° cell
                    99th percentile of the last 24 Aprils
                    MODIS-only 398 · VIIRS-only 422 · they agree
                    satellites observing: VIIRS Suomi-NPP, Aqua MODIS
  ─────────────────────────────────────────────────────────────
  Verdict: two independent witnesses agree
```

**On the map.** Case points coloured by verdict; the selected case's 0.1° cell outlined; clicking a point opens the
same panel. The existing `grid` source and `statics` source are already there (`Map.tsx:191-206`) — the case layer is
one more GeoJSON source.

**Where the numbers come from.** Every number in the panel is read from `cases.json`, which was computed at build
time from the same committed JSON the calendar uses. The UI computes nothing.

---

## 10. Implementation steps

Each step ends with a verification that must pass before the next.

### Step 1 — `viirs_only` in `_block`

```python
# server/kw/build.py, _block()
aqua_only = _hotspots(agg, keys, cov, cls, cal, set(MODIS_SATS))[0]
viirs_only = _hotspots(agg, keys, cov, cls, cal, set(VIIRS))[0]
```

**Verify:** `python -c "import ast; ast.parse(open('server/kw/build.py').read())"` → no output.
A rebuild is needed for it to appear in the files; until then the witness abstains, which is fine.

### Step 2 — `news.eonet()` keeps the event id and start date

Add `id`, `start_date`, `end_date` to the item dict (`news.py:92-100`).

**Verify:** `python -c "from kw import news; print(len(news.eonet((89.9,23.4,90.9,24.2), __import__('datetime').date(2016,1,1), __import__('datetime').date(2020,1,1), 5)[0]))"` → 5, and each item has a non-null `id`.

### Step 3 — `server/kw/cases.py`

Pure functions, no I/O beyond the cached fetchers:

```python
CASES = "cases.json"

def satellite_state(area_cov, cell_value, present): ...      # §4.2
def cross_family(modis_only, viirs_only, coverage): ...       # §4.4
def verdict(sat, cross, agency, disaster, press): ...         # §5
def candidates(meta, monthly, grid, eonet_items, gdacs_items): ...
def build_cases(region_id, meta, monthly, grid, week=None): ...
```

`build_cases` reads the region files, takes the fetched EONET/GDACS items and the GDELT monthly counts, assembles the
cases, and returns the object to be written.

**Verify:** unit-test `verdict()` for all six outcomes and `satellite_state()` for the three states, in
`server/tests/test_cases.py` (same runner style as `test_science.py`).

### Step 4 — wire it into `build_region`

```python
# server/kw/build.py, in build_region(). The grid is computed ONCE and reused by the casebook.
grid = _grid(con, mkeys, mcov, cals)

for name, obj in (("meta", meta), ("monthly", monthly), ("weekly", weekly),
                  ("grid", grid), ("static", _static_points(con, glob))):
    ...
try:
    from . import cases as cases_mod
    cases = cases_mod.build_cases(region_id, meta, monthly, grid)
except Exception as ex:                      # a network failure must never break a build
    cases = {"built_at": meta["built_at"], "counts": {}, "sources": [],
             "cases": [], "error": str(ex)[:200]}
folder = OUT / region_id
folder.mkdir(parents=True, exist_ok=True)
tmp = folder / "cases.json.tmp"
tmp.write_text(json.dumps(cases, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
os.replace(tmp, folder / "cases.json")
```

**Verify:** `python -m kw.build dhaka-kilns` exits 0 and `data/regions/dhaka-kilns/cases.json` exists with
`counts` summing to `len(cases)`.

### Step 5 — `tools.py`, `api.py`, `mcp_server.py`, `agent.py`

As in §8.

**Verify:** `uvicorn kw.api:app --port 8000` then
`curl -s localhost:8000/api/regions/dhaka-kilns/cases | python -m json.tool | head -40` → JSON;
`curl -s -X POST localhost:8000/mcp ... tools/list` includes `get_fire_cases`.

### Step 6 — the web tab

`web/src/Cases.tsx` (new), `web/src/api.ts` (types + `api.cases`), `web/src/App.tsx` (one tab), `web/src/Map.tsx`
(case layer).

**Verify:** `cd web && npx tsc --noEmit` → exit 0; `npm run build` → exit 0.

### Step 7 — the words

`web/src/pages/Method.tsx` — add a section after "News and events":

> **Fire cases and their witnesses.** Every fire we publish is a case with several independent witnesses: the
> harmonized record, a MODIS-against-VIIRS cross-check, NASA EONET, GDACS and the press. A witness that could not see
> says so. Where an agency recorded a fire the record does not show, the case says that too — absence of a report is
> never evidence of absence.

**Verify:** `cd web && npx tsc --noEmit` → exit 0.

---

## 11. Test plan

`server/tests/test_cases.py` (new, same runner style):

```python
def test_satellite_states():
    assert cases.satellite_state({"MODIS_A": 0.0}, None, False) == "abstain"
    assert cases.satellite_state({"MODIS_A": 1.0}, 12.0, True) == "fire"
    assert cases.satellite_state({"MODIS_A": 1.0}, None, False) == "quiet"

def test_verdicts():
    assert cases.verdict("fire", {}, agency, None, None) == "corroborated"
    assert cases.verdict("fire", {}, None, None, press) == "reported"
    assert cases.verdict("fire", {}, None, None, None) == "satellite_only"
    assert cases.verdict("quiet", {}, agency, None, None) == "agency_only"   # the reverse direction
    assert cases.verdict("abstain", {}, agency, None, None) == "abstained"
    assert cases.verdict("quiet", {}, None, None, None) == "insufficient"

def test_case_file_shape():
    # every shipped cases.json: counts sum to len(cases); every case has a verdict in VERDICTS
    # and a satellite witness with a state in {'fire','quiet','abstain'}
```

Plus, in the web app: the verdict chips filter the table; a case with `verdict: "abstain"` renders "could not see",
never "no fire"; the table is keyboard navigable.

---

## 12. Done criteria

- [ ] `data/regions/<area>/cases.json` exists for all nine presets
- [ ] `counts` sums to `len(cases)` in every file
- [ ] every case's satellite witness has a state in `{fire, quiet, abstain}` and a coverage value
- [ ] at least one `agency_only` case exists somewhere in the nine areas (if none exists, that is a finding, not a bug —
      report it, do not manufacture one)
- [ ] `GET /api/regions/{rid}/cases` → 200 with the documented shape; `?verdict=agency_only` filters
- [ ] `get_fire_cases` appears in the MCP tool list; `tools/call` returns a case with witnesses
- [ ] `cd web && npx tsc --noEmit` → exit 0; `npm run build` → exit 0
- [ ] the Method page states the abstention rule in words
- [ ] the README "Data used" table gains no new row (EONET, GDACS, GDELT and Google News are already listed)

---

## 13. STOP conditions

Stop and report — do not improvise — if:

- A case's satellite witness would have to claim `quiet` while the area's coverage for that period is 0. That means
  the abstention rule is wrong somewhere; fix the rule, never the case.
- The `agency_only` count comes out at zero for every area. Before concluding "no misses", check that the EONET and
  GDACS fetches actually returned events (the `sources[]` array says so). A silent zero is a bug, not a result.
- The EONET or GDACS fetch returns fewer events than the previous build by more than half. A source has probably
  changed its API or rate-limited; check before writing the file.
- `viirs_only` cannot be produced by the one-line change in `_block` (for example if `_active` cannot express
  "VIIRS only"). Report it — do not fake it with `aqua_only`.

---

## 14. Maintenance notes

- The witness roster is a list, not a hard-coded set of branches. Adding burned area (plan 010) means adding one key
  to the witness dict and one rule to `verdict()`.
- The press counts come from one GDELT timeline per area per build. If the area's `places` or `lang` change, the
  counts change with them — they are a function of the query, and the query is stored in `witnesses.press.query`.
- `viirs_only` doubles the size of `monthly.json` if it is stored per class. Store it for the `veg` class only, as the
  static class is dominated by persistent sources.
- If the casebook is ever extended to custom areas, the EONET/GDACS fetch runs per area at build time and the raw
  responses are cached in `data/news_cache/` — the same cache the News page already uses.
