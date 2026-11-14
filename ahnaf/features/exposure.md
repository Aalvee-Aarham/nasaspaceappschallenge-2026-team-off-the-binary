# Feature B — exposure context: who and what lies in the cells where the record shows fire

**Date:** 2026-11-13 · **Status:** design · **Base commit:** `1e99c85` · **Depends on:** nothing (the grid is
committed today) · **Runs:** `scripts/build_exposure.py`, build time only.

---

## 1. The claim this feature makes, and the one it must not make

**It makes:** *"In the cells where the harmonized record shows fire, there are about N people, H hospitals and R major
roads."*

**It must not make:** any statement about people being affected, endangered, or reached by fire.

The reason is in the data, not in the caution. FIRMS gives **detections** — a hot pixel in one overpass — and the
project's own Method page says so on every screen: *"Detections are not fires and not burned area."* There is no
perimeter here. A 0.1° cell with 400 hotspots does not mean the fire reached across that 11 km cell; it means hot
pixels were detected somewhere in it. There is no fire-spread model, no smoke model, no ignition model, no weather.

So the honest framing, which must appear on the page and in the data:

> **Potentially exposed, not an impact estimate.** This is the population and infrastructure that lie in the cells
> where satellite detections were recorded. It is not a fire perimeter, it says nothing about smoke or fire spread,
> and it is not a prediction of who is affected.

And because seven of the nine preset areas are brick-kiln belts, deltas and rural fire regions, the framing must be
**where a responder should look** — never a list of who is vulnerable.

---

## 2. Architecture in one paragraph

The fire geometry already exists: `data/regions/<area>/grid.json` publishes the harmonized record on a 0.1° grid,
per month, per cell. The exposure feature joins **two static context layers** onto that grid — population and
infrastructure — at build time, and stores the result as `data/regions/<area>/exposure.json`. At runtime the API
joins `exposure.json` to `grid.json` for whatever month the user is looking at. **No new geometry, no new cell size,
no new projection, and nothing heavy at runtime.**

```
build time (once)                                   runtime (every request)
──────────────────                                   ─────────────────────
WorldPop 1 km raster ──┐                            exposure.json ──┐
   (234 MB, 9 files)   ├─► scripts/build_exposure.py ──► exposure.json │
Overpass hospitals   ──┤        │                                     ├─► tools.exposure()
Overpass major roads ──┘        │                                     │      joins with grid.json
                                 └─► aggregates onto the 0.1° grid       ▼
                                    stores per-cell population      api.py → web/src
                                    + per-hospital cell
                                    + per-road cells crossed
```

**Everything the web app needs is a static JSON file.** Overpass is never called at query time, the raster is never
read at query time, and `rasterio` never enters the runtime image.

---

## 3. Sources

### 3.1 Population — WorldPop Global 2000–2020, 1 km, 2020

Verified during design:

| Property | Value |
|---|---|
| URL pattern | `https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/<ISO3>/<iso3>_ppp_2020_1km_Aggregated.tif` |
| Key | none |
| Raster | EPSG:4326, 0.0083333° (1 km), float32, nodata −99999 |
| Size, nine countries | **234 MB total** — BGD 0.9 · PRY 2.4 · NGA 5.1 · IND 19.1 · ARG 19.0 · BRA 45.8 · CAN 42.6 · AUS 46.7 · USA 52.7 |
| Read time | seconds per country with `rasterio` |

The area → country mapping, from the preset bboxes in `server/kw/regions.py`:

| Area | bbox | Country |
|---|---|---|
| `dhaka-kilns` | 89.9, 23.4, 90.9, 24.2 | BGD |
| `punjab` | 73.8, 29.5, 77.6, 32.6 | IND |
| `la-rioja` | −68.6, −30.0, −66.6, −28.2 | ARG |
| `rondonia` | −64.5, −11.8, −61.0, −8.5 | BRA |
| `alberta` | −113.5, 55.5, −110.0, 58.5 | CAN |
| `se-australia` | 146.5, −38.0, 151.0, −33.5 | AUS |
| `n-california` | −123.5, 38.5, −120.0, 41.5 | USA |
| `parana-delta` | −61.0, −34.4, −58.4, −32.0 | **ARG + PRY** (the delta is on the border) |
| `niger-delta` | 5.5, 4.3, 7.8, 6.2 | NGA |

> **Why 1 km and not 100 m.** The published grid is 0.1° (≈ 11 km). A 100 m raster would multiply the download by
> roughly 100× to resolve detail that a 11 km cell cannot represent anyway. 1 km is also the resolution at which
> WorldPop publishes a single global mosaic, which keeps the method identical for every area — one method, one
> vintage, one caveat.

> **Why the unconstrained product.** `Global_2000_2020_1km` is the modelled (unconstrained) surface; the
> `Global_2000_2020_Constrained` variant for 2019–2020 is only published as a 200 m product. The unconstrained 1 km
> surface is used for every area so the method is uniform, and the difference is stated in the output. Swap in the
> constrained surface per country later if there is time — it changes only the numbers in `cells[2]`, not the code.

### 3.2 Hospitals — OpenStreetMap via Overpass

```overpassql
[out:json][timeout:180];
(
  nwr["amenity"~"^(hospital|clinic|doctors)$"]({s},{w},{n},{e});
  nwr["healthcare"~"^(hospital|clinic)$"]({s},{w},{n},{e});
);
out center tags;
```

Measured on the Dhaka belt box: **2171 elements in 38.9 s.** The filter deliberately excludes `pharmacy`, `dentist`
and the bare `healthcare=*` tag (which returned 830 pharmacies and 116 dentists and would inflate the count with
places that are not care facilities).

### 3.3 Major roads — OpenStreetMap via Overpass

```overpassql
[out:json][timeout:180];
way["highway"~"^(motorway|trunk|primary)$"]({s},{w},{n},{e});
out center tags;
```

Measured on the Dhaka belt box: **2338 elements in 37.3 s**, 1707 of them named. Named roads matter — a road with a
name is a thing a responder can be told about; an unnamed one is not.

### 3.4 Why OSM and not a "roads dataset"

The project already cites OpenStreetMap and uses Nominatim for place names and OpenFreeMap for the base map. Adding
Overpass is one more OSM query against the same licence and the same attribution line. There is no key, no account, no
licence negotiation. Overpass does have a fair-use policy, which §7 handles.

### 3.5 What is *not* used, and why

| Rejected source | Why |
|---|---|
| HDX Health Facilities | needs an HDX API key; OSM covers the same ground with better coordinates |
| WHO Global Health Observatory | needs a key; slower; less complete |
| Sentinel / road network datasets | Earth Engine or a licence; the project has no cloud pipeline |
| GDELT / ACLED for "exposure" | event data, not exposure; that is the casebook's job |
| Any "vulnerability index" | would need an index, a methodology, and a licence — out of scope, and it is exactly the framing risk §1 warns about |

---

## 4. Aggregation

### 4.1 Population onto the 0.1° grid

Both grids are axis-aligned in degrees, so the overlap of a source cell and a target cell is a rectangle
intersection — no GDAL zonal statistics, no polygon rasterisation, no projection juggling.

For each target cell (`[lat0, lat1] × [lon0, lon1]`) and each overlapping source cell with population `p`:

```
fraction = overlap_lon_deg / source_lon_deg  ×  overlap_lat_deg / source_lat_deg
contribution = p × fraction
```

Because both grids are in degrees, the cosine-of-latitude factor is constant across one target cell (it varies by
< 0.2 % inside a 0.1° cell), so weighting in degrees is equivalent to weighting in projected area.

> **The WorldPop grid origin is not aligned to the 0.1° grid** (for Bangladesh it is offset by ≈ 0.8 of a source
> pixel), so a plain centre-based count would systematically bias individual cells by a few per cent. The area-weighted
> method above removes that. Area totals are the robust number; per-cell values are the ones that carry the caveat.

**Verify the method against a known value:** aggregate the Dhaka belt bbox by brute force over source cells and
compare with the area-weighted sum. They must agree to within 0.1 %.

### 4.2 Infrastructure onto the grid

- **Hospitals** are points: each gets the index of the 0.1° cell that contains it. A hospital exactly on a cell
  boundary goes to the cell whose SW corner is the floor of its coordinates — the same rule the grid uses
  (`build.py:642`: `cells.append([_r(gy * GRID_DEG, 2), _r(gx * GRID_DEG, 2)])`).
- **Roads** are lines: each gets the list of cells it passes through, computed by walking the vertices and adding
  every cell the segment crosses (simple supercover walk on the 0.1° grid — no geometry library needed).

Both joins are computed **once at build time**, so the runtime join is a set intersection.

### 4.3 Distance to fire

Each hospital and each road gets `nearest_fire_km`: the great-circle distance to the nearest **cell that has ever
had fire** (any month in `grid.json`). This is a static, area-level statistic — "this hospital is 3.2 km from the
closest cell where fire has been detected since 2000" — and it is labelled as such. It is *not* recomputed per month;
doing that would need the geometry at runtime, which the design deliberately avoids.

### 4.4 No road geometry in the committed JSON

The base map already draws roads (OpenFreeMap renders OSM), so storing 2338 road geometries would duplicate the map
at roughly 600 KB per area for no visual gain. The JSON stores the road's **name, class, representative point and the
cells it crosses**. The UI lists them and highlights the cells; it does not draw them.

> **Upgrade path:** if a judge asks for the roads drawn, the geometry can be added back as a separate, optional
> `roads_geo.json` that the map fetches only when the layer is switched on.

---

## 5. The output file

`data/regions/<area>/exposure.json`:

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
    "caps": {"hospitals": 5000, "roads": 8000},
    "truncated": {"hospitals": false, "roads": false}
  },
  "totals": {"population": 33425932, "hospitals": 214, "major_roads": 2338},
  "cells": [[23.4, 89.9, 12480], ...],            // [lat, lon, population]
  "hospitals": [
    {"name": "উত্তরা আধুনিক মেডিকেল কলেজ ও হাসপাতাল", "kind": "hospital",
     "lat": 23.79, "lon": 90.39, "cell": [23.7, 90.3], "nearest_fire_km": 0.0}
  ],
  "roads": [
    {"name": "নবীনগর - চন্দ্রা মহাসড়ক", "kind": "primary",
     "lat": 23.81, "lon": 90.41, "cells": [[23.7, 90.3], [23.8, 90.4]], "nearest_fire_km": 0.0}
  ],
  "caveat": "Population and infrastructure inside cells where the harmonized record shows fire. A context layer, not an impact estimate: FIRMS gives detections, not a fire perimeter, and there is no smoke or fire-spread model here."
}
```

**Size budget:** ≤ 600 KB per area. With the road-geometry decision above, a typical area lands at 100–250 KB. The
`truncated` flags exist so a capped area says so rather than pretending to be complete.

**Not committed:** the WorldPop GeoTIFFs (234 MB) and the raw Overpass responses. Both are cached under
`data/cache/exposure/` (gitignored).

---

## 6. The runtime join

`server/kw/exposure.py` is deliberately thin — it reads JSON and joins.

```python
def exposure(region_id, period=None):
    """Population and infrastructure in the cells where the harmonized record shows fire.

    period: a calendar month ('YYYY-MM'). With it, the fire cells are that month's cells.
    Without it, the summary is over every cell that has had fire since 2000.
    """
    ex = _read(region_id, "exposure")
    grid = _read(region_id, "grid")
    if period:
        rows = grid["months"].get(period, [])
        fire = {ci for ci, _ in rows}
    else:
        fire = {ci for rows in grid["months"].values() for ci, _ in rows}
    cells = {tuple(c[:2]): c for c in ex["cells"]}
    pop = sum(cells[cell]["population"] for cell in cells if cell in fire)   # via the index map
    hospitals = [h for h in ex["hospitals"] if tuple(h["cell"]) in fire]
    roads = [r for r in ex["roads"] if any(tuple(c) in fire for c in r["cells"])]
    return {
        "region_id": region_id, "period": period,
        "fire_cells": len(fire),
        "population": pop,
        "hospitals": len(hospitals), "hospital_list": hospitals[:50],
        "major_roads": len(roads), "road_list": roads[:50],
        "population_source": ex["population"], "caveat": ex["caveat"],
    }
```

The join is a set intersection over a few thousand items: microseconds. The population sum must be computed from the
same index map the grid uses, so `cells` in `exposure.json` and `cells` in `grid.json` must be **indexed identically** —
the build script must derive the exposure cell list from `grid.json`, never from its own raster walk. That is a hard
rule and it is why `exposure.json` stores `cells` as a list parallel to the grid's cell index.

> **Index-parallel rule.** `grid.json`'s `cells` array and `exposure.json`'s `cells` array must be in the same order,
> so `exposure.cells[i]` is the population of `grid.cells[i]`. The build script reads `grid.json`, takes its cell list
> verbatim, and writes the population in that order. A self-check asserts `len(exposure.cells) == len(grid.cells)`.

---

## 7. The build script

`scripts/build_exposure.py` — **build time only**, not in `server/requirements.txt`.

```python
"""Build the exposure context layer for every preset area.

    pip install rasterio                 # build-time only
    python scripts/build_exposure.py [area ...]

Writes data/regions/<area>/exposure.json. Downloads are cached in data/cache/exposure/ and are not committed.
The world population raster is modelled 2020 data; the OpenStreetMap queries are a snapshot of the query date.
"""
```

### Steps

| Step | What | Verify |
|---|---|---|
| 1 | Download the country's WorldPop raster into `data/cache/exposure/` (skip if present) | file exists and `rasterio.open()` reports EPSG:4326 |
| 2 | Read `grid.json` for the area; build the cell index map | `len(grid["cells"]) == len(set(grid["cells"]))` |
| 3 | Area-weighted population per grid cell | brute-force cross-check agrees to < 0.1 % on one area |
| 4 | Overpass: hospitals for the area bbox | returns ≥ 1 element; `amenity=pharmacy` count is 0 |
| 5 | Overpass: major roads for the area bbox | returns ≥ 1 element; names present |
| 6 | Assign each hospital to a cell; compute the cells each road crosses | every hospital's cell is in `grid["cells"]` |
| 7 | `nearest_fire_km` for each hospital and road | no negative values; a hospital in a fire cell gets 0.0 |
| 8 | Write `exposure.json` (atomic write, `os.replace`) | `json.load` succeeds; `len(cells) == len(grid["cells"])` |

### Overpass politeness and failure handling

- **One request per source per area**, with the area bbox. Two areas never run concurrently.
- **Retry**: three attempts, 10 s / 30 s / 60 s backoff, on 429 and 504.
- **Split large boxes**: if the bbox is wider than 2°, split into 2×2 sub-boxes and union the results. Overpass times
  out on a 3.5° × 3° box (alberta) more often than on 1° boxes.
- **Cache the raw response** in `data/cache/exposure/overpass-<hash>.json` for 30 days. A failed fetch never destroys
  a good cached file.
- **A failed source is recorded, not hidden**: `infrastructure.truncated` and a `sources[]` entry with the error, and
  the UI says "OpenStreetMap query failed — hospitals are missing from this view", never "0 hospitals".

---

## 8. The UI

The exposure panel lives **inside the Cases tab**, not in a separate page: it uses the same Explorer map, the same
period selector and the same grid overlay, so it costs one panel rather than a second map, a second legend and a
second nav entry.

```
┌─ Exposure ────────────────────────────────────────────────────────────────┐
│ November 2026 · the cells where the record shows fire                      │
│                                                                             │
│  412 fire cells   ·   ~1.24 million people   ·   68 hospitals   ·  1 240 roads│
│                                                                             │
│  ⚠ Population and infrastructure inside cells where satellite detections   │
│    were recorded. Not a fire perimeter, not an impact estimate.             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Nearest hospitals to a fire cell                                           │
│  উত্তরা আধুনিক মেডিকেল কলেজ ও হাসপাতাল   hospital   0.0 km   23.79, 90.39  │
│  কুমিল্লা মেডিকেল সার্ভিস সেন্টার        clinic    0.3 km   23.81, 90.37  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Major roads crossing a fire cell                                           │
│  নবীনগর - চন্দ্রা মহাসড়ক                primary   0.0 km                 │
│  ঢাকা-ময়মনসিংহ মহাসড়ক                 primary   0.4 km                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Map overlays** (`web/src/Map.tsx`), all off by default:

| Layer | Source | Paint |
|---|---|---|
| Population in the fire cells | the existing `grid` source, repainted | a second fill layer over the fire cells, with a population ramp (a *separate* ramp from the inferno fire ramp — fire and people must not share a colour scale) |
| Hospitals | a new GeoJSON source | a distinct marker (a cross or a square, not the fire circle) |
| Fire cells | the existing `grid` source | an outline layer, so the cells that carry fire are visible even when the population layer is off |

**Colour discipline.** The fire ramp is Inferno (`api.ts:248`). Population gets its own single-hue sequential ramp.
Two different quantities never share a scale. The hospital marker is a shape, not a colour, so it is distinguishable
without colour vision.

**The numbers must come from the API**, not from the browser: `api.exposure(id, period)` → the panel renders. The
browser computes no sums — the same rule as the rest of the app.

---

## 9. Runtime surfaces

### `server/kw/tools.py`

```python
def exposure(region_id, period=None):
    """Population and infrastructure in the cells where the harmonized record shows fire.
    A context layer, not an impact estimate."""
```

### `server/kw/api.py`

```python
@app.get("/api/regions/{rid}/exposure")
def exposure(rid: str, period: str | None = None):
    return _guard(tools.exposure, rid, period)
```

### `server/kw/mcp_server.py`

```python
@mcp.tool(title="Exposure in the fire cells", annotations=RO)
def get_exposure(region_id: str, period: str = "") -> dict:
    """Population, hospitals and major roads in the 0.1 degree cells where the harmonized record shows fire.
    A context layer, not an impact estimate: there is no fire perimeter, no smoke and no fire spread here.
    Population is modelled 2020 data (WorldPop)."""
    return tools.exposure(region_id, period or None)
```

### `server/kw/agent.py`

```python
{"name": "exposure", "description": "Population, hospitals and major roads in the cells where the record shows "
 "fire. Context, not an impact estimate: population is modelled 2020 data, and there is no fire perimeter.",
 "parameters": {"type": "OBJECT", "properties": {"region_id": _S, "period": _period}, "required": ["region_id"]}},
```

And one line in `SYSTEM`:

> - Exposure is context, not impact. Never say who was affected, reached or endangered. Say how many people and
>   facilities lie in the cells where detections were recorded.

---

## 10. Method page wording

`web/src/pages/Method.tsx` — a new section, and one new entry in `LIMITS`:

> **What is in the fire cells.** Population (WorldPop 2020, 1 km) and infrastructure (OpenStreetMap) inside the 0.1°
> cells where the record shows fire. This is a context layer: FIRMS gives detections, not a fire perimeter, so nothing
> here says the fire reached a place, and nothing here models smoke or fire spread. Population is modelled 2020 data.

And in `LIMITS`:

> "Exposure is a static context layer joined to the 0.1° grid. Population is WorldPop's modelled 2020 surface, not a
> census; hospitals and roads are an OpenStreetMap snapshot from the query date. No fire perimeter, no smoke, no fire
> spread and no impact estimate."

---

## 11. Test plan

`server/tests/test_exposure.py` (new):

```python
def test_exposure_file_shape():
    # every shipped exposure.json: len(cells) == len(grid.json cells); every hospital cell is a grid cell;
    # every road's cells are grid cells; population totals are non-negative; sources are named.

def test_exposure_join():
    # tools.exposure(rid, period) returns the population of exactly the cells in grid["months"][period]
    # and counts only the hospitals and roads in those cells.
```

Plus, in the script:

```python
def test_area_weighted_matches_bruteforce():
    # brute-force centre-of-source-cell summation vs the area-weighted method, on one small bbox:
    # they must agree to within 0.1 %.
```

Web: the exposure panel must render "–" (not "0") when a source failed, and the caveat block must be present
whenever any number in the panel is shown.

---

## 12. Done criteria

- [ ] `data/regions/<area>/exposure.json` exists for all nine presets
- [ ] `len(exposure.cells) == len(grid.cells)` for every area
- [ ] every hospital's `cell` and every road's `cells` are cells that exist in `grid.json`
- [ ] the population total for an area equals the sum of its cells
- [ ] `GET /api/regions/{rid}/exposure` → 200; `?period=2024-11` returns only that month's cells
- [ ] `get_exposure` appears in the MCP tool list
- [ ] `cd web && npx tsc --noEmit` → exit 0; `npm run build` → exit 0
- [ ] the caveat text is visible in the UI and in the API payload
- [ ] the README "Data used" table gains two rows: WorldPop and OpenStreetMap (Overpass), with their licences

---

## 13. STOP conditions

Stop and report — do not improvise — if:

- The area-weighted population disagrees with the brute-force check by more than 0.1 %. The aggregation is wrong; do
  not ship a number you cannot reconcile.
- A downloaded raster reports a CRS other than EPSG:4326, or a resolution other than 0.0083333°. The method depends on
  both grids being axis-aligned in degrees.
- Overpass returns a `remark` or an error for two or more areas. Do not write a file that silently says "0 hospitals".
- The population total for an area comes out as zero while the raster clearly has data. That is a CRS or nodata
  problem, not an empty area.
- Any area's `exposure.json` exceeds 600 KB. Something is wrong with the cell list; fix it rather than raising the
  budget.

---

## 14. Maintenance notes

- **Refresh cadence.** Population changes every few years; OSM changes daily. Rebuild the exposure layer when the
  grid changes (plan 006) or when OSM is refreshed — not on every record rebuild. The `built_at` field says when.
- **The population vintage must never drift from the README.** If WorldPop publishes a new release, rebuild all nine
  areas in one pass so the method stays uniform across the areas.
- **New preset areas** need a country added to the mapping table in the script and a run of the script. The script
  asserts that the area's bbox intersects each listed country's extent and fails loudly otherwise.
- **The cap values** (`hospitals: 5000`, `roads: 8000`) exist so a pathological box cannot produce a 50 MB file. When
  a cap bites, `truncated` is set and the UI says so.
- **Overpass mirror rotation.** `overpass-api.de` is the main instance; `overpass.kumi.systems` and
  `overpass.osm.ch` are alternatives. Use the fallback when the main one times out, and record which one answered in
  `infrastructure.queried_at`.
