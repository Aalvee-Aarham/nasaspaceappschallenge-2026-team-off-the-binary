# Plan 006: Map cells combine satellites the same way the area totals do

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py`
> Plan 003 changes the `_active(...)` call in `_grid` to `_active(cov, i, key=p)`; anything else in `_grid` differing
> from the excerpt below is a STOP.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW — affects only `grid.json` (map colours), not the calendar or validation
- **Depends on**: plan 003
- **Category**: bug (consistency)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

The calendar's area totals combine satellites with an inverse-variance mean (`science.combine`), day and night
separately. The 0.1° map cells instead take a plain mean of each satellite's calibrated estimate. When Aqua and
VIIRS disagree, the map and the calendar tell different stories, and a careful judge who sums the map gets a
different number from the calendar. After this plan both use the same rule, so cell sums track the area total closely.

## Current state

`server/kw/build.py:623-645` `_grid(con, keys, cov, cals)`:
```python
    for (p, gy, gx), per in acc.items():
        i = idx.get(p)
        if i is None:
            continue
        m = sc.calendar_month(p)
        ests = [sum(cals["veg"][f"det_{dn}"]["to_ref"][s][0][m - 1] * per.get(s, {}).get(dn, 0) for dn in DN) / cov[s][i]
                for s in _active(cov, i)]          # plan 003 makes this _active(cov, i, key=p)
        val = statistics.fmean(ests) if ests else 0.0
        if val <= 0:
            continue
```
`per` is `{observer: {"D": n, "N": n}}`. The area-total rule, from `_series` (same file):
```python
            x, cv = _value(agg, cls, s, k, q)          # x = count, cv = max(count, 1)
            b, s2 = to_ref[s][0][m - 1], to_ref[s][1]
            ests.append((b * x / c, s2, b * b * cv / (c * c)))
        res = sc.combine(ests)                         # -> (value, variance) or None
```
`cals["veg"][f"det_{dn}"]["to_ref"]` is `{observer: (beta[12], sigma2)}`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `python server/tests/test_science.py` | all `ok` |
| Rebuild presets (raw cache required) | `cd server && python -m kw.build` | `built …` ×9 |

## Scope

**In scope**: `server/kw/build.py` (`_grid` only), `data/regions/*/grid.json` (rebuilt).
**Out of scope**: `science.combine`, `_series`, the grid file format (keys `deg`, `cells`, `months`, `unit`, `note` must stay).

## Git workflow

Branch `advisor/006-grid-weights`; commit `Weight map cells like area totals`; `graphify update .` if installed; no push.

## Steps

### Step 1: Measure the mismatch before

```bash
python - <<'EOF' > /tmp/kw_grid_before.txt
import json, glob, statistics
for f in sorted(glob.glob("data/regions/*/grid.json")):
    r = f.split("/")[2]; g = json.load(open(f)); mo = json.load(open(f"data/regions/{r}/monthly.json"))
    tot = dict(zip(mo["periods"], mo["classes"]["veg"]["hotspots"]["v"]))
    d = [abs(sum(v for _, v in cells) - tot[p]) / tot[p] for p, cells in g["months"].items() if tot.get(p) and tot[p] > 50]
    print(r, round(100 * statistics.median(d), 1) if d else None)
EOF
cat /tmp/kw_grid_before.txt
```
(Use a scratch directory instead of `/tmp` if your environment provides one.)

### Step 2: Replace the plain mean

```python
        val = 0.0
        for dn in DN:
            to_ref = cals["veg"][f"det_{dn}"]["to_ref"]
            ests = []
            for s in _active(cov, i, key=p):
                b, s2, c, x = to_ref[s][0][m - 1], to_ref[s][1], cov[s][i], per.get(s, {}).get(dn, 0)
                ests.append((b * x / c, s2, b * b * max(x, 1) / (c * c)))  # same terms as _series
            res = sc.combine(ests)
            val += res[0] if res else 0.0
        if val <= 0:
            continue
```
Delete the old `ests = [...]` and `val = statistics.fmean(...)` lines.

**Verify**: `python -c "import ast; ast.parse(open('server/kw/build.py').read())"` → no output

### Step 3: Rebuild and compare

`cd server && python -m kw.build`, then rerun the step-1 snippet into `/tmp/kw_grid_after.txt` and
`paste /tmp/kw_grid_before.txt /tmp/kw_grid_after.txt`.

**Verify**: for each area the after median % is ≤ the before median % (or both under 2%).

## Test plan

Covered by step 3 (data-level). `science.combine` already has `test_combine`.

## Done criteria

- [ ] `python server/tests/test_science.py` exits 0
- [ ] Step 3 comparison holds for all 9 areas
- [ ] `git status` shows only `server/kw/build.py` and `data/regions/**` changed
- [ ] `docs/plans/README.md` row 006 updated

## STOP conditions

- Any area's after-median mismatch is higher than before by more than 1 point.
- `grid.json` size grows by more than 20% (unexpected new cells).

## Maintenance notes

- Cells still use the area's calibration (stated in the `note` field). Keep the note.
