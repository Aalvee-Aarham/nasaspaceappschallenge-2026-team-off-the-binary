# Plan 004: Report interval coverage on months the widening factor never saw

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py server/kw/science.py web/src/Record.tsx web/src/api.ts README.md`
> Plan 003 is expected to have changed `build.py` (`_active`, `aqua_overpass`). Only `_denial_modis` matters here:
> if its body differs from the excerpt below, STOP.

## Status

- **Priority**: P1
- **Effort**: S–M
- **Risk**: LOW — adds a reported number; production intervals are unchanged
- **Depends on**: plan 003 (rebuild once, after the record fix)
- **Category**: bug (validation honesty)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

Every harmonized value has a 95% interval. The MODIS-denial test (calibrate Suomi-NPP on 2012–2016, rebuild
2017–2020 from VIIRS alone, compare with what Aqua saw) measures how often the intervals contain the truth, then
**widens** them by a factor `k` chosen so 95% of those same months fall inside. The README results table then
reports "96%" coverage in all nine regions. That number holds by construction (the README says so in small
print), and a scientist judge will read it as circular. The honest, unwidened coverage is 35% (La Rioja), 42%
(Dhaka), 58% (Alberta) … 94% (Punjab), and `k` reaches 5.3. This plan adds a split check: fit `k` on 2017–2018,
report coverage on 2019–2020. Production intervals keep using `k` from all four years.

## Current state

- `server/kw/build.py:364` `_denial_modis(agg, keys, cov, cls, last_full)`. Relevant lines (380–396):
  ```python
          if key == "beta":
              z = [abs(t - v[i]) / math.sqrt(var[i]) for t, i in zip(truth, idx) if v[i] is not None and var[i]]
              m["interval_coverage_raw"] = _r(sum(x <= 1.96 for x in z) / len(z), 3) if z else None
              result["series"] = {...}
          result[name] = m
      # Conformal-style widening: scale intervals so 95% of held-out months fall inside.
      k = max(1.0, sorted(z)[min(len(z) - 1, math.ceil(0.95 * len(z)) - 1)] / 1.96) if len(z) >= 10 else 1.0
      result["interval_scale"] = _r(k, 3)
      if "series" in result:
          ...
          result["ours_seasonal_eb"]["interval_coverage"] = _r(sum(x <= 1.96 * k for x in z) / len(z), 3) if z else None
      return result, k
  ```
  `idx` = indices of months `"2017-01"`…`"2020-12"` where Aqua coverage ≥ 0.9; `keys[i]` is the `"YYYY-MM"` key.
- `server/kw/science.py` — stdlib statistics; tests in `server/tests/test_science.py` (plain `test_*` functions; see `test_metrics`).
- `web/src/api.ts:26`: `export type Metric = { n: number; bias_pct?: Num; mae?: number; rmse?: number; spearman?: Num; interval_coverage?: Num; interval_coverage_raw?: Num };`
- `web/src/Record.tsx:492-493` (Method panel):
  ```tsx
          Before widening, the 95% intervals contained the observed value in {fmt((den.ours_seasonal_eb.interval_coverage_raw ?? 0) * 100, 0)}% of months.
          {den.interval_scale > 1 ? ` Every interval that uses VIIRS is therefore widened ×${den.interval_scale.toFixed(2)}, which gives ${fmt((den.ours_seasonal_eb.interval_coverage ?? 0) * 100, 0)}% coverage.` : " No widening was needed."}
  ```
- `README.md` "Full results table, nine regions" has a column `95% interval coverage` and the sentence
  "The 96% coverage holds by construction: intervals are widened to reach 95% on that test."

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Python env | `cd server && . .venv/bin/activate` (create as in plan 003 if missing) | — |
| Tests | `python server/tests/test_science.py` | all `ok`, exit 0 |
| Rebuild presets | `cd server && python -m kw.build` | `built <id>` ×9 (raw cache from `python -m kw.firms` must exist) |
| Typecheck | `cd web && npx tsc --noEmit` | exit 0 |

## Scope

**In scope**: `server/kw/science.py` (add `conformal_scale`), `server/kw/build.py` (`_denial_modis` only),
`server/tests/test_science.py`, `web/src/api.ts` (`Metric` type), `web/src/Record.tsx` (the sentence above),
`README.md` (results table + its note), `data/regions/**` (rebuilt).

**Out of scope**: the production interval factor (keep `k` from all of 2017–2020); `_combine`/variance model;
any other validation function.

## Git workflow

Branch `advisor/004-honest-coverage`; commit like `Report out-of-sample interval coverage`; `graphify update .` if installed; no push.

## Steps

### Step 1: `conformal_scale` in `science.py`

```python
def conformal_scale(z, level=0.95, base=1.96, min_n=10):
    """Split-conformal widening: the smallest k >= 1 such that a share `level` of |error|/sd values lie within
    base * k. Fewer than min_n values: 1.0 (no evidence to widen)."""
    if len(z) < min_n:
        return 1.0
    zs = sorted(z)
    return max(1.0, zs[min(len(zs) - 1, math.ceil(level * len(zs)) - 1)] / base)
```
Test in `server/tests/test_science.py`:
```python
def test_conformal_scale():
    assert sc.conformal_scale([0.5] * 20) == 1.0                 # already inside: never shrink
    z = [i / 10 for i in range(1, 101)]                          # 0.1 … 10.0
    k = sc.conformal_scale(z)
    assert abs(k - 9.5 / 1.96) < 1e-9 and sum(x <= 1.96 * k + 1e-9 for x in z) / len(z) >= 0.95
    assert sc.conformal_scale([5.0] * 9) == 1.0                  # too few values
```
**Verify**: `python server/tests/test_science.py` → includes `ok test_conformal_scale`

### Step 2: Keep keys with the z-scores and add the split check

In `_denial_modis`:
1. Replace the `z = [...]` line with
   ```python
               zk = [(keys[i], abs(t - v[i]) / math.sqrt(var[i])) for t, i in zip(truth, idx) if v[i] is not None and var[i]]
               z = [x for _, x in zk]
   ```
2. Replace the `k = max(1.0, ...)` line with `k = sc.conformal_scale(z)` (same value as before — the formula is identical).
3. After the `if "series" in result:` block, add:
   ```python
       fit = [x for kk, x in zk if kk <= "2018-12"]
       test = [x for kk, x in zk if kk >= "2019-01"]
       if len(fit) >= 10 and test:
           k_fit = sc.conformal_scale(fit)
           result["out_of_sample"] = {"fit": ["2017-01", "2018-12"], "test": ["2019-01", "2020-12"], "k_fit": _r(k_fit, 3),
                                      "n_test": len(test), "coverage": _r(sum(x <= 1.96 * k_fit for x in test) / len(test), 3)}
           result["ours_seasonal_eb"]["interval_coverage_out_of_sample"] = result["out_of_sample"]["coverage"]
   ```
   (`zk` is defined inside the `if key == "beta":` branch, which always runs first in the loop, so it exists here.)

**Verify**: `python -c "import ast; ast.parse(open('server/kw/build.py').read())"` → no output

### Step 3: Rebuild and read the numbers

```bash
cd server && python -m kw.build
cd .. && python - <<'EOF'
import json, glob
for f in sorted(glob.glob("data/regions/*/meta.json")):
    d = json.load(open(f))["denial"]["modis_ends_2016"]; e = d["ours_seasonal_eb"]
    print(f.split("/")[2], "raw", e.get("interval_coverage_raw"), "widened(in-sample)", e.get("interval_coverage"),
          "out-of-sample", e.get("interval_coverage_out_of_sample"), "k", d.get("interval_scale"))
EOF
```
**Verify**: 9 lines, each with a non-null `out-of-sample` value between 0 and 1.

### Step 4: Show it in the app

- `web/src/api.ts` `Metric`: add `interval_coverage_out_of_sample?: Num`.
- `web/src/Record.tsx` after the "widened … coverage." sentence add:
  ```tsx
  {den.ours_seasonal_eb.interval_coverage_out_of_sample != null && ` Tested on months the widening never saw (factor fitted on 2017–2018, checked on 2019–2020): ${fmt(den.ours_seasonal_eb.interval_coverage_out_of_sample * 100, 0)}% coverage.`}
  ```
**Verify**: `cd web && npx tsc --noEmit` → exit 0

### Step 5: README table

Replace the column `95% interval coverage` with two columns: `Interval coverage, unwidened` and
`Interval coverage, out of sample` filled from step 3's output (copy the printed numbers; never type them from
memory). Replace the sentence "The 96% coverage holds by construction…" with:
"Intervals are widened so 95% of the 2017–2020 test months fall inside. To check that this is not circular, the
widening is also fitted on 2017–2018 alone and tested on 2019–2020: that is the out-of-sample column."
If any region's out-of-sample coverage is below 85%, add it to "Where it still falls short" in plain words.

## Test plan

- `test_conformal_scale` (step 1). The refactor of `k` must not change it: after the rebuild,
  `interval_scale` for regions whose data did not change should equal the pre-plan value (Punjab was 1.06 before plan 003).

## Done criteria

- [ ] `python server/tests/test_science.py` exits 0 with `ok test_conformal_scale`
- [ ] Every preset `meta.json` has `denial.modis_ends_2016.out_of_sample.coverage`
- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `grep -n "holds by construction" README.md` returns nothing
- [ ] `docs/plans/README.md` row 004 updated

## STOP conditions

- `zk` has fewer than 10 values for 2017–2018 in more than 2 regions (the split is too thin; report counts).
- `interval_scale` changes for a region whose input data did not change (refactor error).

## Maintenance notes

- Low unwidened coverage (35–60% in four regions) means `sigma2` misses year-to-year variation in the
  satellite ratio. A follow-up could add a between-year variance term to `science.ratio_calibration`, estimated like
  `tau2`. Not done here: it changes every interval and needs its own validation.
- Plan 012's Proof page shows these three coverage numbers side by side.
