# Plan 011: Check the "likely kilns" in Dhaka against a mapped kiln inventory

> **Executor instructions**: Step 1 is a data gate. If no inventory with a usable licence can be obtained as described,
> STOP and report. Run every verification. When done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- data/regions/dhaka-kilns/static.json README.md`
> The file may have been rebuilt; only check it still has `points` and `columns` with `lon`, `lat` first.

## Status

- **Priority**: P2 (Local Impact)
- **Effort**: M
- **Risk**: LOW — separate validation file
- **Depends on**: none
- **Category**: direction (local validation)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

The team is from Bangladesh, and Dhaka's brick-kiln belt is its home case. VIIRS sees thousands of small, steady kiln
fires that MODIS mostly misses: a 10.6× false jump in raw counts. Kiln Watch separates these "persistent heat sources"
from vegetation fire using FIRMS's own `type` flag, but the README and map label them "likely kilns: not yet checked
against a kiln inventory". Checking them against independently mapped kilns turns that caveat into a measured
result. It is the most concrete thing the project can tell Bangladesh's Department of Environment, which licenses
kilns.

## Current state

- `data/regions/dhaka-kilns/static.json`:
  `{"points": [[lon, lat, detections, first_year, last_year, active_years, mean_frp_mw, modis_detections], ...],
    "columns": ["lon","lat","detections","first_year","last_year","active_years","mean_frp_mw","modis_detections"], "note": "..."}`
  Each point is a 0.01° cell (≈1.1 km) FIRMS attributes mainly to static sources.
- `data/regions/dhaka-kilns/meta.json` → `bbox` `[west, south, east, north]`.
- `README.md` has the line: `Labelled "likely kilns": the cells are not yet checked against a kiln inventory. That check is next.`
- `server/kw/build.py` `_static_points` writes the note "Not validated against an independent kiln or industry inventory …".

## Data sources (choose in step 1, in this order)

1. A published Bangladesh brick-kiln inventory from peer-reviewed work, e.g. the satellite-derived kiln map in
   Lee et al. (2021, *PNAS*, "Scalable deep learning to identify brick kilns and aid regulatory capacity"). Use it only if
   its data are downloadable and the licence allows redistribution of derived statistics; cite it.
2. OpenStreetMap features tagged `man_made=kiln` (and `industrial=brickyard`) inside the bbox, via the public Overpass API
   (ODbL; attribute "© OpenStreetMap contributors"). Send no personal data; use a generic User-Agent such as `kiln-watch-validation`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Run script | `python -I scripts/validation/kilns.py` | prints metrics, writes JSON |

## Scope

**In scope (create)**: `scripts/validation/kilns.py`, `data/validation/kilns_dhaka.json`; edit `README.md` (the
"likely kilns" line and a short result), and optionally the note text in `server/kw/build.py` `_static_points` (only the
`note` string, only if precision ≥ 0.5 — see step 4).
**Out of scope**: the static-source mask logic; other regions; committing the raw inventory if its licence forbids it.

## Git workflow

Branch `advisor/011-kiln-check`; commit `Check Dhaka heat sources against a kiln inventory`; no push.

## Steps

### Step 1 (gate): get kiln locations

Obtain kiln points (lon, lat) inside the Dhaka bbox from source 1 or 2. Save them under `data/cache/kilns/` (gitignored).
**Verify**: at least 200 kiln points inside the bbox; print the count and source. Fewer → STOP (inventory too sparse to judge).

### Step 2: Match

In `scripts/validation/kilns.py` (stdlib only: `json`, `math`, `random`):
- distance in km with the haversine formula;
- **precision** = share of static cells (`static.json` points with `active_years >= 3`) that have a kiln within 1.0 km;
- **recall** = share of inventory kilns with a static cell within 1.0 km;
- **baseline**: repeat precision for the same number of random points drawn uniformly inside the bbox (seed 42,
  1000 repeats; report mean and 95th percentile) → **lift** = precision ÷ baseline mean.
Also report the same three numbers at 0.5 km and 2 km.

**Verify**: script prints precision, recall, baseline, lift for 0.5/1/2 km, and writes `data/validation/kilns_dhaka.json`
`{"source": ..., "licence": ..., "n_kilns": ..., "n_cells": ..., "by_radius_km": {"1.0": {"precision":…, "recall":…, "baseline":…, "lift":…}, …}}`.

### Step 3: Kiln season check (sanity)

From `data/regions/dhaka-kilns/monthly.json`, print the median share of static-class hotspots per calendar month
(`classes.static.hotspots.v`). Kiln season in Bangladesh is roughly November–April; record what the data show (do not edit if different).

### Step 4: Words

- Replace the README "likely kilns … That check is next." line with one sentence giving precision, recall and lift at
  1 km and the source (numbers copied from the script output).
- If precision at 1 km ≥ 0.5 and lift ≥ 3, update the `note` in `_static_points` to mention the check. Otherwise keep
  "likely" wording and say in the README why.

## Test plan

- Add an `assert` self-check at the bottom of `kilns.py` for the haversine function (Dhaka→Chattogram ≈ 213 km ± 5).

## Done criteria

- [ ] `data/validation/kilns_dhaka.json` exists with the fields above
- [ ] README line updated with numbers from the output
- [ ] No raw inventory file is tracked (`git status`)
- [ ] `docs/plans/README.md` row 011 updated

## STOP conditions

- Step 1 gate fails, or the inventory's licence is unclear.
- Precision is below the random baseline (report it; do not hide it — the team decides the wording).

## Maintenance notes

- Plan 012's Bangladesh page shows these numbers. If the team later promotes Sylhet or Pabna to presets, rerun with their bboxes.
