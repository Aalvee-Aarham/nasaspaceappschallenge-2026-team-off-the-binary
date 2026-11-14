# Plan 010: Check the harmonized record against NASA's MODIS burned-area product

> **Executor instructions**: This plan starts with a data-access gate (step 1). If the data cannot be obtained as
> described, STOP and report — do not switch to another dataset on your own. Run every verification. When done,
> update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- data/regions/ scripts/ README.md`
> Data files are expected to have changed (plans 003–006 rebuild them). Only check that `data/regions/<preset>/monthly.json`
> still has `periods`, `partial`, `classes.veg.hotspots.v`, `raw.all_det`, `classes.veg.aqua_only`.

## Status

- **Priority**: P2
- **Effort**: M–L (most of it is data download)
- **Risk**: LOW — adds a separate validation file; no pipeline change
- **Depends on**: plan 003 (validate the corrected record)
- **Category**: direction (independent validation)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

All of Kiln Watch's validation today is internal: the record is checked against Aqua MODIS detections, which are
part of the same system. The strongest competitor (team SHIFT) checks against independent data: GFED4 burned
area and MERRA-2 cloud. NASA's own **MCD64 burned-area product** (MODIS Collection 6.1) gives an independent yardstick
for vegetation fire: burned area is mapped from surface reflectance, not from thermal hotspots. It does not change
when VIIRS arrives in 2012. So if harmonization works, the ratio *hotspots per km² burned* should stay level across
2012 for the harmonized record and jump for raw counts. This is a direct test of the challenge's core question,
using NASA data the judges know.

## Current state

- Per preset, `data/regions/<id>/monthly.json`: `periods` ("YYYY-MM"), `partial` (bool), `classes.veg.hotspots.v`
  (harmonized, Aqua scale), `classes.veg.aqua_only`, `raw.all_det` (raw detections, all satellites).
- `data/regions/<id>/meta.json`: `bbox` = `[west, south, east, north]`, `name`.
- Presets (`server/kw/regions.py` `PRESETS`): `dhaka-kilns`, `punjab`, `la-rioja`, `rondonia`, `alberta`, `se-australia`,
  `n-california`, `parana-delta`, `niger-delta`. **Exclude `dhaka-kilns` and `niger-delta`** from this check: their
  heat is mostly kilns and gas flares, which do not leave burn scars.
- `server/kw/science.py` provides `spearman(a, b)`, `step_ratio(keys, values, partial, transition, window=24, min_side=12)`
  (deseasonalised mean after ÷ before) — reuse them; do not reimplement.
- The repo's rule: every number shown comes from a pipeline run; nothing typed by hand.

## Data source (verify in step 1)

**MCD64CMQ** — "MODIS/Terra+Aqua Burned Area Monthly L3 Global 0.25° CMG", Collection 6.1: one small global HDF4 file
per month, burned area in hectares per 0.25° cell. Access route, host, folder and the public login are given in the
*MODIS Collection 6.1 Burned Area Product User's Guide* (Giglio et al., UMD), section on data distribution. Read the
guide and use exactly what it says. Cite it in the README.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Separate env for this script | `python3 -m venv .venv-val && . .venv-val/bin/activate && pip install pyhdf` | exit 0 (if `pyhdf` fails, try `pip install gdal` only if system GDAL exists; otherwise STOP) |
| Science helpers | the script imports `server/kw/science.py` via `sys.path` | — |

## Scope

**In scope (create)**: `scripts/validation/burned_area.py` (download + reduce + compare), `data/validation/burned_area.json`
(results, committed, small), `README.md` (one subsection), `web/src/pages/Method.tsx` (one short section reading the JSON — optional, see step 5).
**Out of scope**: `server/kw/build.py` (no pipeline change); raw HDF files (never commit them; put them in a gitignored
folder such as `data/cache/mcd64/` — `data/cache/` is already gitignored).

## Git workflow

Branch `advisor/010-burned-area-check`; commits like `Add burned-area validation`; no push.

## Steps

### Step 1 (gate): get one month

Download the MCD64CMQ file for 2015-08 by the route the user guide gives. Open it with `pyhdf.SD` and list its datasets.

**Verify**: a 720 × 1440 burned-area array (0.25° grid, rows from 90°N) is readable, with a documented unit and fill value.
If not → STOP and report what the guide/server actually provides.

### Step 2: Reduce to the 7 areas

Write `scripts/validation/burned_area.py`:
- downloads every month 2003-01 … the last available month into `data/cache/mcd64/` (skip files already present);
- for each area, sums burned area (km²) over 0.25° cells whose centres fall inside the area's `bbox`
  (row = floor((90 − lat)/0.25), col = floor((lon + 180)/0.25));
- writes `{area: {"periods": [...], "burned_km2": [...]}}` into memory.

**Verify**: Punjab's Oct–Nov months are its largest each year; SE Australia 2019-12/2020-01 are its record months.

### Step 3: Compare

For each area, using only months where the record is complete (`partial` false) and burned area > 0:
- `spearman(harmonized, burned)` and `spearman(raw_all_det, burned)` over 2003–2020 (before Aqua drift).
- Ratio series r = hotspots / burned_km2 for (a) harmonized and (b) raw; then `step_ratio(periods, r, partial, "2012-01")`
  for each. Harmonization working = harmonized step close to 1, raw step clearly above 1.
Write `data/validation/burned_area.json`:
```json
{"source": "MCD64CMQ C6.1 (NASA MODIS burned area, 0.25° monthly)", "built_at": "...", "areas": {
  "punjab": {"n_months": 0, "spearman_harmonized": 0, "spearman_raw": 0, "step_2012_harmonized": 0, "step_2012_raw": 0}}}
```
(values from the computation, not these placeholders).

**Verify**: `python -I scripts/validation/burned_area.py` → prints one line per area and writes the file; 7 areas present.

### Step 4: README

Add under "The proof" a short subsection "Checked against NASA burned area" with a table generated from the JSON (print it
with a snippet, paste the output). State plainly where it does not support the record (e.g. small-fire regions
where burned area misses most fires). Add the user guide and product to "References".

### Step 5 (optional, only if plan 012 has not landed yet): show it on the Method page

Fetch `/data/validation/burned_area.json` (copy `data/validation/` into `web/dist/data/validation/` by adding
`&& cp -r ../data/validation dist/data/validation` to `vercel.json` `buildCommand`, after the regions copy), and render a
small table. If plan 012 is already merged, put the table in its Proof scorecard instead.

## Test plan

- Step 2 sanity checks (known fire seasons). Step 3 runs the existing, tested `science` functions.

## Done criteria

- [ ] `data/validation/burned_area.json` exists with 7 areas and all five fields per area
- [ ] No HDF file is tracked: `git ls-files | grep -ci hdf` prints `0`
- [ ] README subsection added with numbers copied from the JSON output
- [ ] `docs/plans/README.md` row 010 updated

## STOP conditions

- Step 1 gate fails.
- Download would exceed 5 GB (report size; the CMG product should be far smaller).
- Burned area is zero for all months in an area (bbox or grid indexing bug).

## Maintenance notes

- MCD64 also depends on MODIS and will end with Terra/Aqua; NASA's VIIRS burned area (VNP64A1) is its successor. Adding
  it later extends the check past 2020 using the same script.
- Burned area ≠ detections: weak correlation in small-fire regions is expected; say so rather than hide it.
