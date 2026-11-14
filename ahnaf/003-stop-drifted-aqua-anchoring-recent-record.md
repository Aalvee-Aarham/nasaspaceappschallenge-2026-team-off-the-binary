# Plan 003: Measure Aqua's orbit drift from the data and run the record on VIIRS after it

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py server/kw/science.py server/tests/ web/src/pages/Method.tsx README.md`
> If any in-scope file changed, compare the "Current state" excerpts with the live code; on a mismatch, STOP.

## Status

- **Priority**: P1 (most important science fix in the project)
- **Effort**: M
- **Risk**: MED — changes every published number from the drift onset to today
- **Depends on**: plan 002 (so the full rebuild keeps transfer validation; not strictly required)
- **Category**: bug (science correctness)
- **Planned at**: commit `1e99c85`, 2026-11-13 (revised the same day after the code-scan review: evidence, weight shares, version rule)

## Why this matters

Kiln Watch publishes one fire record from 2000 to today on the **Aqua MODIS scale**. The calibration defines that
scale on 2002–2020, before Aqua's orbit drifted and before the MODIS archive changed algorithm version. But the
stitching step still uses Aqua as an observer in every later month with **zero calibration error**, so it carries a
large share of the weight. The share was measured on 2026-11-13 from the published files (median per year, daytime):
Punjab ~0.80–0.86 (0.72 in 2026), SE Australia 0.49–0.82, Alberta 0.59–0.96, La Rioja ~0.13. So in fire-dense
areas the recent record mostly follows Aqua; in La Rioja it barely does.

Two things changed Aqua's data after 2020:
1. **Orbit.** Aqua left the A-Train in January 2022; its equator crossing drifted from about 13:35 to about 15:30
   by July 2026 (NASA Aqua status report), which changes what it sees.
2. **Algorithm version.** The FIRMS MODIS archive in this repo switches version on 2023-01-01: `6.03` up to
   2022-12-31, `61.03` from 2023-01-01, `6.1NRT` from 2026-07-01 (see `meta.versions` in any area). The 2002–2020
   calibration was fitted on `6.03` only.

Evidence in this repo's own data (like-for-like: only the calendar months Jan, Feb, Mar, May, Jun, Aug, Sep, Oct,
which both satellites observed in every year 2019–2026, so the month mix is the same each year; per satellite, not
the VIIRS sum, so NOAA-21 joining in 2024 does not show up as a step):
- Punjab, Aqua ÷ NOAA-20 per year 2019→2026: 0.164, 0.173, 0.153, 0.157, **0.122**, 0.118, 0.126, 0.117 — a
  −25% step at **2023**, the year of the version change, then flat.
- Punjab, Aqua ÷ Suomi-NPP per year 2019→2026: 0.178, 0.173, 0.162, 0.162, **0.119**, 0.112, 0.120, 0.119.
- La Rioja 2026: 0.074; Niger Delta 2026: 0.116; Rondônia, Paraná and N. California are roughly stable;
  SE Australia and Alberta are noisy (few months).

Do **not** quote the yearly ratios in `meta.drift` as evidence: that diagnostic compares different month sets in
different years (fixed by plan 015), which inflates the 2026 drop (Punjab Aqua ÷ Suomi-NPP shows 0.131 in 2026
there versus 0.119 like-for-like). An earlier draft of this plan quoted those numbers; they are withdrawn.

The early-warning level is computed from this record, so a "quiet" verdict can be a satellite artifact. The
project's own guardrail (`CLAUDE.md`): "Sensor availability is measured from data … never hard-coded end dates."
So: measure both changes from the data (Aqua's overpass time from the FIRMS timestamps; the first post-2020 MODIS
archive version from the cache), take the **earlier** as the onset, and from that month on build the record from the
VIIRS satellites alone (still on the Aqua 2002–2020 scale, through the existing calibration chain). This also
removes the step that would appear when Aqua is switched off.

## Current state

- `server/kw/build.py:66-70`:
  ```python
  def _active(cov, i, allowed=None):
      """Aqua when it observes, else Terra (only before Aqua or during an Aqua gap); plus every observing VIIRS."""
      use = ["MODIS_A"] if cov["MODIS_A"][i] >= MIN_COVERAGE else (["MODIS_T"] if cov["MODIS_T"][i] >= MIN_COVERAGE else [])
      use += [s for s in VIIRS if cov[s][i] >= MIN_COVERAGE]
      return [s for s in use if allowed is None or s in allowed]
  ```
- `server/kw/build.py:227-229` `_chain`: `to_ref = {REF: ([1.0] * 12, 0.0)}` — Aqua (the reference) has calibration variance 0.
- `server/kw/build.py:272-276` `_series(agg, keys, cov, cls, q, to_ref, allowed=None, k_scale=1.0)` loops
  `for i, k in enumerate(keys):` and calls `_active(cov, i, allowed)`. `k` is the period key: `"YYYY-MM"` or ISO week `"YYYY-Www"`.
- `server/kw/build.py:623-637` `_grid` loops `for (p, gy, gx), per in acc.items():` with `i = idx.get(p)` and calls
  `for s in _active(cov, i)]`. `p` is `"YYYY-MM"`.
- `aqua_only` series are built with `allowed=set(MODIS_SATS)` (`_block`), the MODIS-denial test with `allowed=set(VIIRS)`.
- `server/kw/build.py:39` `_load(con, region_id)` creates DuckDB table `raw` from `data/cache/<area>/*.parquet` with
  columns including `acq_datetime` (TIMESTAMP, UTC), `lon`, `daynight` ('D'/'N'), and `obs` ('MODIS_A', 'MODIS_T', 'VIIRS_SNPP', …).
  The whole-Earth path `_load_global` has no timestamps.
- `server/kw/build.py:874` `main(ids)` builds the presets. The raw cache `data/cache/` is gitignored and filled by
  `python -m kw.firms` (reads the public mirror; no key).
- `server/kw/science.py` — stdlib-only statistics; every public function has a test in `server/tests/test_science.py`.
  Test style (exemplar):
  ```python
  def test_outlook_cell():
      from kw.science import outlook_cell
      hist = [0] * 10 + [20] * 10
      assert outlook_cell(hist, [2] * 20, 2)[0] == "season"
  ```
- `web/src/pages/Method.tsx:19` LIMITS entry: `"Terra to Aqua is the weakest link and is used only for 2000 to 2002. Aqua drifts after about 2021.",`
- Vocabulary to keep: "hotspots", "Aqua MODIS scale", "harmonized", "detections are not fires". Never call anything a forecast.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Python env | `cd server && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` | exit 0 |
| Tests | `python server/tests/test_science.py && python server/tests/test_build_rules.py` | all `ok`, exit 0 |
| Download raw cache (all presets, needs internet, ~10–30 min) | `cd server && python -m kw.firms` | ends with `done <seconds>` |
| Rebuild all presets | `cd server && python -m kw.build` | `built <id>` for 9 areas |
| Web typecheck | `cd web && npm ci && npx tsc --noEmit` | exit 0 |

## Scope

**In scope**:
- `server/kw/science.py` (add `solar_hour`, `drift_onset`)
- `server/kw/build.py` (`AQUA_DRIFT_FROM`, `aqua_overpass()`, `_active`, `_series`, `_grid`, `build_region`, `main`)
- `server/tests/test_science.py` (add tests), `server/tests/test_build_rules.py` (create)
- `data/aqua_overpass.json` (created by the build), `data/regions/**` (rebuilt)
- `web/src/pages/Method.tsx` (one LIMITS line), `README.md` (method bullets + results table numbers)

**Out of scope**:
- `server/kw/outlook.py` — the worldwide outlook also uses Aqua alone; switching it to NOAA-20 is a separate job.
- The calibration windows in `LINKS` — they already stop at 2020; do not change them.
- `_chain` — Aqua stays the reference scale; do not give it a non-zero variance.

## Git workflow

Branch `advisor/003-aqua-drift`; commits like `Measure Aqua overpass drift from FIRMS times` and
`Run the record on VIIRS after Aqua drifts`; run `graphify update .` if installed; do not push.

## Steps

### Step 1: Pure helpers in `science.py`

Add to `server/kw/science.py` (new section `# ---------- orbit drift ----------`):

```python
def solar_hour(utc_hours, lon):
    """Local solar time (hours, 0-24) of an overpass from its UTC time of day and longitude."""
    return (utc_hours + lon / 15.0) % 24


DRIFT_TOL_H = 0.25  # 15 minutes: well above year-to-year noise of a yearly median, well below the ~2 h drift by 2026


def drift_onset(medians, baseline=(2003, 2020), first=2021, tol_h=DRIFT_TOL_H):
    """First year >= `first` whose median overpass hour differs from the baseline years' median by more than tol_h.
    medians: {year: median local solar hour}. Returns (onset_year or None, baseline_hour or None)."""
    base = [h for y, h in medians.items() if baseline[0] <= y <= baseline[1]]
    if len(base) < 5:
        return None, None
    ref = statistics.median(base)
    for y in sorted(medians):
        if y >= first and abs(medians[y] - ref) > tol_h:
            return y, ref
    return None, ref
```

Add tests to `server/tests/test_science.py` (before the `if __name__` block):

```python
def test_solar_hour_and_drift_onset():
    assert abs(sc.solar_hour(12.0, 90.0) - 18.0) < 1e-9
    assert abs(sc.solar_hour(1.0, -45.0) - 22.0) < 1e-9          # wraps below zero
    flat = {y: 13.5 for y in range(2003, 2021)}
    assert sc.drift_onset({**flat, 2021: 13.55, 2022: 13.6, 2023: 13.9})[0] == 2023
    assert sc.drift_onset({**flat, 2021: 13.6})[0] is None       # within tolerance
    assert sc.drift_onset({2021: 15.0}) == (None, None)          # no baseline
```

**Verify**: `python server/tests/test_science.py` → includes `ok test_solar_hour_and_drift_onset`, exit 0

### Step 2: Measure Aqua's overpass hour across the presets

In `server/kw/build.py` add near the other module constants:

```python
AQUA_FILE = DATA / "aqua_overpass.json"
AQUA_DRIFT_FROM = None  # "YYYY-01" from aqua_overpass.json; same global value for every build (orbit property)
```

and a function (put it under `# ---------------- validation ----------------` or a new `# ---- orbit drift ----` header):

```python
def aqua_overpass(region_ids):
    """Median local solar time of Aqua's daytime detections per year, pooled over the preset areas' raw caches,
    and the drift onset. Written to data/aqua_overpass.json so builds without raw caches use the same value."""
    files = [f.as_posix() for rid in region_ids for f in (CACHE / rid).glob("*.parquet")]
    if not files:
        return json.loads(AQUA_FILE.read_text(encoding="utf-8")) if AQUA_FILE.exists() else None
    rows = duckdb.connect().execute(f"""
        SELECT year(acq_datetime) AS y,
               median(((hour(acq_datetime) + minute(acq_datetime) / 60.0 + lon / 15.0) % 24 + 24) % 24) AS h,
               count(*) AS n
        FROM read_parquet({files}) WHERE sensor = 'MODIS' AND left(satellite, 1) = 'A' AND daynight = 'D'
        GROUP BY 1 HAVING count(*) >= 100 ORDER BY 1""").fetchall()
    years = {int(y): float(h) for y, h, _ in rows}
    onset, base = sc.drift_onset(years)
    orbit = None if onset is None else f"{onset}-01"
    # first MODIS archive version (not NRT) that appears only after the 2002-2020 calibration years
    ver = duckdb.connect().execute(f"""
        SELECT version, strftime(min(acq_datetime), '%Y-%m') FROM read_parquet({files})
        WHERE sensor = 'MODIS' AND version NOT LIKE '%NRT' GROUP BY 1
        HAVING min(acq_datetime) >= TIMESTAMP '2021-01-01' ORDER BY 2 LIMIT 1""").fetchone()
    version = ver and {"version": ver[0], "from": ver[1]}
    starts = [x for x in (orbit, version and version["from"]) if x]
    out = {"years": {str(y): round(h, 3) for y, h in years.items()},
           "n": {str(int(y)): int(n) for y, _, n in rows},
           "baseline_hour": None if base is None else round(base, 3),
           "orbit_onset": orbit, "version_change": version,
           "onset": min(starts) if starts else None,
           "rule": f"Onset = the earlier of (a) the first year from 2021 whose median local solar time of Aqua MODIS daytime "
                   f"detections (preset areas pooled) is more than {sc.DRIFT_TOL_H * 60:.0f} minutes from the 2003–2020 "
                   "median, and (b) the first month of a MODIS archive version that appears only after 2020 (the "
                   "calibration was fitted on the earlier version). From the onset the harmonized record uses the "
                   "VIIRS satellites only (still on the Aqua 2002–2020 scale)."}
    AQUA_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
```

Note: the `% 24 + 24) % 24` keeps negative longitudes in 0–24. DuckDB's `%` works on DOUBLE.

**Verify** (after `python -m kw.firms` has filled `data/cache/`):
`cd server && python -c "from kw import build; from kw.regions import PRESETS; import json; print(json.dumps(build.aqua_overpass(list(PRESETS)), indent=1))"`
→ JSON with yearly hours around 13.4–13.8 for 2003–2020, later years rising toward ~15, `"orbit_onset"` a year
between `"2021-01"` and `"2025-01"`, `"version_change"` = `{"version": "61.03", "from": "2023-01"}` (as seen in
`meta.versions` on 2026-11-13), and `"onset"` the earlier of the two (expected `"2023-01"` or earlier).

### Step 3: Exclude drifted Aqua in `_active` (only when VIIRS observes)

Replace `_active` with:

```python
def _active(cov, i, allowed=None, key=None):
    """Aqua when it observes, else Terra (only before Aqua or during an Aqua gap); plus every observing VIIRS.
    From the measured Aqua drift onset, MODIS is left out whenever a VIIRS satellite observes, so the record keeps the
    Aqua 2002-2020 scale through the VIIRS calibration chain instead of following a drifted orbit."""
    viirs = [s for s in VIIRS if cov[s][i] >= MIN_COVERAGE and (allowed is None or s in allowed)]
    drifted = key is not None and AQUA_DRIFT_FROM is not None and key >= AQUA_DRIFT_FROM and viirs
    use = [] if drifted else ["MODIS_A"] if cov["MODIS_A"][i] >= MIN_COVERAGE else (["MODIS_T"] if cov["MODIS_T"][i] >= MIN_COVERAGE else [])
    use += viirs
    return [s for s in use if allowed is None or s in allowed]
```

Why `viirs` is filtered by `allowed`: the `aqua_only` series passes `allowed={MODIS_A, MODIS_T}`; it must keep Aqua
(it is the raw-Aqua comparison line), and the MODIS-denial test passes `allowed=set(VIIRS)` and is unaffected.

String comparison works for both key forms: `"2023-05" >= "2023-01"` and `"2023-W05" >= "2023-01"` are True;
`"2022-W52" >= "2023-01"` is False.

Pass the key from both callers:
- `_series`: `ests, obs = [], _active(cov, i, allowed, k)`
- `_grid`: `for s in _active(cov, i, key=p)]`

**Verify**: `python -c "import ast; ast.parse(open('server/kw/build.py').read())"` → no output

### Step 4: Set `AQUA_DRIFT_FROM` before building

- In `main(ids)`, before the build loop: 
  ```python
  global AQUA_DRIFT_FROM
  ov = aqua_overpass(list(PRESETS))
  AQUA_DRIFT_FROM = (ov or {}).get("onset")
  print(f"Aqua drift onset: {AQUA_DRIFT_FROM}", flush=True)
  ```
- At the top of `build_region(...)` (covers the API's background rebuilds, which never call `main`):
  ```python
  global AQUA_DRIFT_FROM
  if AQUA_FILE.exists():
      AQUA_DRIFT_FROM = json.loads(AQUA_FILE.read_text(encoding="utf-8")).get("onset")
  ```
  Add a `# ponytail:` comment: module global, safe because every build reads the same file; pass it explicitly if builds ever need different onsets.
- In the `meta = {` dict add `"aqua_overpass": json.loads(AQUA_FILE.read_text(encoding="utf-8")) if AQUA_FILE.exists() else None,`
  and in `meta["method"]` add `"aqua_drift": "From the Aqua drift onset (measured, see aqua_overpass) MODIS is left out when any VIIRS satellite observes."`

**Verify**: `python -c "import ast; ast.parse(open('server/kw/build.py').read())"` → no output

### Step 5: Unit test for `_active`

Create `server/tests/test_build_rules.py` (same runner pattern as `test_science.py`; it imports `kw.build`, which needs duckdb from the venv):

```python
"""Run: python server/tests/test_build_rules.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kw import build  # noqa: E402

COV = {s: [1.0] for s in build.OBSERVERS}


def test_active_before_and_after_drift():
    build.AQUA_DRIFT_FROM = "2023-01"
    try:
        assert "MODIS_A" in build._active(COV, 0, key="2022-12")
        assert "MODIS_A" not in build._active(COV, 0, key="2023-01")
        assert "MODIS_A" not in build._active(COV, 0, key="2023-W02")
        assert build._active(COV, 0, set(build.MODIS_SATS), "2024-05") == ["MODIS_A"]   # aqua_only view keeps Aqua
        no_viirs = {**COV, **{s: [0.0] for s in build.VIIRS}}
        assert build._active(no_viirs, 0, key="2024-05") == ["MODIS_A"]               # nothing else observes
    finally:
        build.AQUA_DRIFT_FROM = None


def test_active_without_onset_is_unchanged():
    assert build._active(COV, 0, key="2026-01")[0] == "MODIS_A"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
```

**Verify**: `python server/tests/test_build_rules.py` → `ok test_active_before_and_after_drift`, `ok test_active_without_onset_is_unchanged`

### Step 6: Rebuild every preset

```bash
cd server && python -m kw.firms && python -m kw.build
```
**Verify**: output contains `Aqua drift onset: <YYYY>-01` and `built <id>` for all 9 presets; `data/aqua_overpass.json` exists.

Then check that months after the onset use no MODIS (repo root):
```bash
python - <<'EOF'
import json, glob
on = json.load(open("data/aqua_overpass.json"))["onset"]
for f in sorted(glob.glob("data/regions/*/monthly.json")):
    m = json.load(open(f)); s = m["classes"]["veg"]["hotspots"]["sensors"]
    post = [u for k, u in zip(m["periods"], s) if k >= on and any(x.startswith("VIIRS") for x in u)]
    print(f.split("/")[2], "post-onset months:", len(post), "with MODIS_A:", sum("MODIS_A" in u for u in post))
EOF
```
→ every area prints `with MODIS_A: 0`.

And the denial test (2017–2020, before any onset ≥ 2021) is unchanged: compare
`python -c "import json;print(json.load(open('data/regions/punjab/meta.json'))['denial']['modis_ends_2016']['ours_seasonal_eb'])"`
with the value before your change (`bias_pct -5.8, spearman 0.981`); small differences (<1 point) can come from
the newly downloaded months, larger ones are a STOP.

### Step 7: Update the words

- `web/src/pages/Method.tsx:19` → `"Terra to Aqua is the weakest link and is used only for 2000 to 2002. Aqua's orbit drifts; from the onset measured from its overpass times the record uses VIIRS only, still on the Aqua 2002–2020 scale.",`
- `README.md`, section "The fix", add a bullet after "Which satellites, when?":
  `- **What about Aqua's drift?** Its overpass time is read from the FIRMS timestamps. From the drift onset (<YEAR>) the record runs on VIIRS alone, still on the Aqua 2002–2020 scale, so it carries on unchanged when Aqua is switched off.`
  (replace `<YEAR>` with the onset from `data/aqua_overpass.json`).
- README results table ("Full results table, nine regions"): refresh the numbers from the rebuilt `meta.json` files
  (`steps`, `denial.modis_ends_2016`, `trend`). Print them with a short Python snippet; do not type numbers by hand
  from memory (project rule: never present hand-typed numbers).

**Verify**: `cd web && npx tsc --noEmit` → exit 0

## Test plan

- `test_solar_hour_and_drift_onset` in `server/tests/test_science.py` (step 1).
- `server/tests/test_build_rules.py` (step 5): drift exclusion, the aqua-only view, the no-VIIRS fallback, no-onset behaviour.
- Step 6 data check: no post-onset month uses MODIS_A when VIIRS observed.

## Done criteria

- [ ] `python server/tests/test_science.py` and `python server/tests/test_build_rules.py` exit 0
- [ ] `data/aqua_overpass.json` exists with a non-null `onset`
- [ ] Step 6 check prints `with MODIS_A: 0` for all 9 presets
- [ ] Every `data/regions/<preset>/meta.json` has a non-null `aqua_overpass`
- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `docs/plans/README.md` row 003 updated

## STOP conditions

- Step 2 gives `"orbit_onset": null` or yearly medians outside 12.5–16.5 h (the timestamp or longitude interpretation is wrong, or there is no drift signal — report the yearly table).
- The onset is before 2021 (would touch the calibration windows).
- `"version_change"` names a version that is NOT used in every preset area from that month on (check `meta.versions`
  of each area): then the version rule is not a fleet-wide change; report the table instead of using it.
- The MODIS-denial metrics for Punjab move by more than 1 percentage point of bias.
- `python -m kw.firms` cannot reach the mirror (network) — do not rebuild from partial caches.

## Maintenance notes

- `outlook.py` still uses Aqua alone for the worldwide 30-day outlook; Method.tsx already says so. Moving it to
  NOAA-20 is the next step if time allows.
- Plans 004 (interval coverage), 005 (warning backtest) and 009 (After-MODIS page, which shows the overpass hours from
  `meta.aqua_overpass`) build on this; run them after.
- Reviewer: check that `aqua_only` and the MODIS-denial series still exist for all years, and that the NOAA-21 step
  test (`meta.steps.VIIRS_NOAA21`) is reported, not hidden, even if it changes.
