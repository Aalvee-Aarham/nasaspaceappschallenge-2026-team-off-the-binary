# Plan 007: Explain the chain-closure mismatch (investigation, no code change)

> **Executor instructions**: This is an investigation. You write one report file and change no code. Follow the
> steps, run every command, and write what you find. If anything in "STOP conditions" occurs, stop and report.
> When done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py`
> Plans 003–006 change `build.py`; the `LINKS`/`CLOSURE` constants and `_calibrate` must be unchanged — if they
> differ from the excerpts below, STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (read-only)
- **Depends on**: plan 003 (investigate the rebuilt data)
- **Category**: investigation (science)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

NOAA-20 reaches the Aqua scale through a chain: NOAA-20 → Suomi-NPP → Aqua. Over 2018-05 to 2020-12 the project also
fits NOAA-20 → Aqua directly and reports the mismatch (`meta.closure`). Day-time vegetation mismatch:
Dhaka −33.6%, Punjab +18.3%, Niger Delta +16.9%, N California −12.8%, La Rioja +12.1%; others within ±4%. The
build adds the mismatch to the error, so intervals stay honest. But a judge who opens the Method panel will ask why
two routes to the same scale disagree by a third. The leading hypothesis is that the Aqua ÷ Suomi-NPP ratio is not
constant over 2012–2020 (the calibration assumes it is per calendar month): the composed chain uses the 2012–2020
average, the direct link uses only 2018–2020. This plan tests that and recommends a fix. It changes no code.

## Current state

- `server/kw/build.py:49-58`:
  ```python
  LINKS = [
      ("MODIS_T", "MODIS_A", ("2002-08", "2020-12"), ("2002-08", "2011-12"), ("2012-01", "2020-12")),
      ("VIIRS_SNPP", "MODIS_A", ("2012-02", "2020-12"), ("2012-02", "2016-12"), ("2017-01", "2020-12")),
      ("VIIRS_NOAA20", "VIIRS_SNPP", ("2018-05", None), ("2018-05", "2021-12"), ("2022-01", None)),
      ("VIIRS_NOAA21", "VIIRS_NOAA20", ("2024-02", None), ("2024-02", "2024-12"), ("2025-01", None)),
  ]
  CLOSURE = [("VIIRS_NOAA20", "MODIS_A", ("2018-05", "2020-12")), ("VIIRS_NOAA21", "VIIRS_SNPP", ("2024-02", None))]
  ```
- `meta.json` per area: `closure` (`{"veg_det_D": [{"sensor","reference","window","direct","composed","mismatch_pct","n"}], ...}`),
  `drift` (`{"MODIS_A/VIIRS_SNPP": [[year, ratio], ...], ...}`), `calibration` (per-link `beta[12]`, `pooled`).
- `monthly.json`: `periods`, `coverage[observer][i]`, `raw[observer]["det_D"|"det_N"][i]`.
- `server/kw/science.py:ratio_calibration(pairs)` — pairs `(calendar_month, ref_value, src_value)`, returns `beta`, `pooled`, `sigma2`, `tau2`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Python | `cd server && . .venv/bin/activate` | — |
| Run your analysis script | `python -I <your scratch dir>/closure.py` | prints tables |

## Scope

**In scope (create only)**: `docs/investigations/chain-closure.md`; a throwaway script in your scratch directory (not committed).
**Out of scope**: every file under `server/`, `web/`, `data/`.

## Steps

### Step 1: Year-by-year ratios

For each preset area, from `monthly.json`, for months where both satellites' coverage ≥ 0.9, compute per year the
day-time ratio of totals: Aqua ÷ S-NPP (2012–2020), S-NPP ÷ NOAA-20 (2018–2026), Aqua ÷ NOAA-20 (2018–2020)
(each count divided by its coverage, as `_pairs` does in `build.py`). Print a table per area.

### Step 2: Predict the mismatch from step 1

For each area: predicted mismatch = (Aqua÷S-NPP over 2018-05…2020-12) ÷ (Aqua÷S-NPP over 2012-02…2020-12) − 1.
Compare with the reported `closure.veg_det_D[0].mismatch_pct`. Print both columns.

### Step 3: Test the hypothesis

The hypothesis holds if the predicted and reported mismatches agree in sign for ≥ 7 of 9 areas and their rank
correlation is ≥ 0.7 (`statistics.correlation` on ranks; `kw.science.spearman` does this).

### Step 4: Write the report

`docs/investigations/chain-closure.md` with: the question, the two tables (copied from script output — never
retyped), the hypothesis verdict, and a recommendation chosen from:
- **A** (hypothesis holds, ratio trends steadily): fit S-NPP → Aqua on 2016–2020 only (closer to NOAA-20's era), and
  re-run the MODIS-denial test to see the cost. Effort S in `LINKS`.
- **B** (hypothesis holds, ratio jumps at a known collection change): split the link at that date.
- **C** (hypothesis fails): keep the current method; the mismatch is already in the error. Explain what else could
  cause it (e.g. NOAA-20 low-confidence night-time behaviour, the static mask).
Include the exact numbers that justify the choice.

## Done criteria

- [ ] `docs/investigations/chain-closure.md` exists with both tables, a verdict and one recommendation (A, B or C)
- [ ] `git status` shows only that file added
- [ ] `docs/plans/README.md` row 007 updated

## STOP conditions

- Fewer than 20 co-observed months 2018–2020 in more than 3 areas (too little data to conclude — report counts).
- You feel the need to change `LINKS` — that is a separate plan; write the recommendation instead.

## Maintenance notes

- If recommendation A or B is adopted, rerun plans 004 and 005 checks after the rebuild; both depend on the calibration.
