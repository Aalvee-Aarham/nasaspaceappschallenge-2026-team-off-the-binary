# Plan 015: The drift diagnostic compares the same months every year

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving on. If anything in "STOP conditions" occurs, stop and report. When done, update the status row
> for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py web/src/Record.tsx`
> Compare `_drift` with the excerpt below; on a mismatch, STOP.

## Status

- **Priority**: P1 (plan 003 and the After MODIS page show this diagnostic to judges as evidence of drift)
- **Effort**: S
- **Risk**: LOW (diagnostic only; no harmonized value changes)
- **Depends on**: none for the code. Land before plan 003's rebuild so one rebuild covers it.
- **Category**: bug (science correctness of a published diagnostic)
- **Planned at**: commit `1e99c85`, 2026-11-13 (from code-scan finding S6, verified)

## Why this matters

`meta.drift` holds, per year, the ratio of what one satellite saw to another (e.g. Aqua ÷ Suomi-NPP), summed over
the months both observed. Different years have different co-observed months (gaps, the current partial year), and
fire is strongly seasonal, so the yearly ratio moves when the **month mix** changes, not only when a satellite drifts.
Measured on 2026-11-13: Punjab Aqua ÷ Suomi-NPP shows 0.131 for 2026 in `meta.drift`, but 0.119 when every year uses
the same months (flat since 2023: 0.178, 0.173, 0.162, 0.162, 0.119, 0.112, 0.120, 0.119 for 2019–2026). The
diagnostic overstated the 2026 drop and hid that the step happened in 2023.

## Current state

- `server/kw/build.py:473-486`:
  ```python
  def _drift(block, keys):
      """Yearly ratio of what one satellite sees to another, from co-observed months. A flat line that bends after
      ~2020 is the signature of Terra/Aqua orbit drift."""
      out = {}
      for a, b in (("MODIS_A", "VIIRS_SNPP"), ("MODIS_T", "MODIS_A"), ("VIIRS_NOAA20", "VIIRS_SNPP")):
          yrs = {}
          for i, k in enumerate(keys):
              ca, cb = block["coverage"][a][i], block["coverage"][b][i]
              if ca >= TRAIN_COVERAGE and cb >= TRAIN_COVERAGE:
                  d = yrs.setdefault(int(k[:4]), [0.0, 0.0])
                  d[0] += block["raw"][a]["det"][i] / ca
                  d[1] += block["raw"][b]["det"][i] / cb
          out[f"{a}/{b}"] = [[y, _r(x / z, 4)] for y, (x, z) in sorted(yrs.items()) if z > 0]
      return out
  ```
  Called once: `build.py:795` `"drift": _drift(monthly, mkeys)` with monthly keys `"YYYY-MM"`.
- Consumers (keep the output shape `{pair: [[year, ratio], ...]}`):
  - `web/src/Record.tsx:351` `const drift = Object.entries(m.drift).filter(([, v]) => v.length > 2);`
  - `web/src/api.ts:58` type `drift: Record<string, [number, number][]>;`
  - `server/kw/tools.py:122` passes `drift` through.

## Scope

**In scope**: `server/kw/build.py` (`_drift`, and one line in `meta["method"]`), `server/tests/test_build_rules.py`
(create it if plan 003 has not; same runner pattern as `server/tests/test_science.py`).
**Out of scope**: the output shape, the frontend, the pairs list.

## Steps

### Step 1: Restrict every year to a common month set

Replace `_drift` with:
```python
def _drift(block, keys, min_months=6):
    """Yearly ratio of what one satellite sees to another. Like for like: every year uses the same calendar months,
    those both satellites observed in every year that has at least min_months co-observed months; years missing any
    of them are left out. A flat line that bends is the signature of orbit drift or a processing change."""
    out = {}
    for a, b in (("MODIS_A", "VIIRS_SNPP"), ("MODIS_T", "MODIS_A"), ("VIIRS_NOAA20", "VIIRS_SNPP")):
        both = {}
        for i, k in enumerate(keys):
            ca, cb = block["coverage"][a][i], block["coverage"][b][i]
            if ca >= TRAIN_COVERAGE and cb >= TRAIN_COVERAGE:
                both.setdefault(int(k[:4]), {})[int(k[5:7])] = (block["raw"][a]["det"][i] / ca, block["raw"][b]["det"][i] / cb)
        full = [ms for ms in both.values() if len(ms) >= min_months]
        common = set.intersection(*(set(ms) for ms in full)) if full else set()
        if len(common) < 4:  # too few shared months to compare years fairly
            out[f"{a}/{b}"] = []
            continue
        rows = []
        for y, ms in sorted(both.items()):
            if common <= set(ms):
                x, z = sum(ms[m][0] for m in common), sum(ms[m][1] for m in common)
                if z > 0:
                    rows.append([y, _r(x / z, 4)])
        out[f"{a}/{b}"] = rows
    return out
```
An empty list is safe: `Record.tsx` filters pairs with `v.length > 2`.

In the `meta["method"]` dict (search `"method": {` in `build_region`) add:
`"drift": "Yearly satellite-to-satellite ratios use the same calendar months in every year, so a changing month mix cannot look like drift."`

### Step 2: Test

In `server/tests/test_build_rules.py` add (create the file with the header below if it does not exist):
```python
"""Run: python server/tests/test_build_rules.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kw import build  # noqa: E402


def test_drift_uses_same_months_every_year():
    keys = [f"{y}-{m:02d}" for y in (2020, 2021) for m in range(1, 13)]
    sats = ("MODIS_A", "VIIRS_SNPP", "MODIS_T", "VIIRS_NOAA20")
    cov = {s: [1.0] * 24 for s in sats}
    for i in range(18, 24):  # 2021 Jul-Dec not observed
        cov["MODIS_A"][i] = 0.0
    # ratio 0.1 in Jan-Jun and 0.5 in Jul-Dec, identical in both years
    a = [10.0 if (i % 12) < 6 else 50.0 for i in range(24)]
    raw = {s: {"det": [100.0] * 24} for s in sats}
    raw["MODIS_A"]["det"] = a
    out = build._drift({"coverage": cov, "raw": raw}, keys)["MODIS_A/VIIRS_SNPP"]
    assert out == [[2020, 0.1], [2021, 0.1]], out   # old code: 2020 -> 0.3, 2021 -> 0.1 (a fake 'drift')


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
```
(If the file exists, add only the test function.)

**Verify**: `python server/tests/test_build_rules.py` → `ok test_drift_uses_same_months_every_year`, exit 0
(needs the server venv with duckdb: `cd server && . .venv/bin/activate`).

### Step 3: Rebuild with plan 003

No separate rebuild. Plan 003 step 6 publishes this. After it, check (repo root):
```bash
python3 -c "import json;print(json.load(open('data/regions/punjab/meta.json'))['drift']['MODIS_A/VIIRS_SNPP'][-8:])"
```
→ 2019–2026 values close to 0.178, 0.173, 0.162, 0.162, 0.119, 0.112, 0.120, 0.119 (small differences from newly
downloaded months are fine).

## Done criteria

- [ ] `python server/tests/test_build_rules.py` exits 0
- [ ] After the rebuild, every preset's `meta.drift` has the same three pair keys as before
- [ ] `cd web && npx tsc --noEmit` exits 0 (no type change expected)
- [ ] `docs/plans/README.md` row 015 updated

## STOP conditions

- A pair that had more than 10 years before the change has fewer than 5 after it in a fire-dense area (Punjab,
  Rondônia): the common month set is too strict there; report the per-year month sets instead of loosening the rule.

## Maintenance notes

- Plan 003's README and After MODIS text should quote these like-for-like ratios, never the old ones.
- The pair list does not include NOAA-21 (joined 2024); add `("VIIRS_NOAA21", "VIIRS_NOAA20")` once it has 3+ full years.
