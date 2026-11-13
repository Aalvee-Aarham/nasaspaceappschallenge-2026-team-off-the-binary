# Plan 005: Backtest the early-warning rule on 20 years and show its hit rate

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py server/kw/science.py server/kw/tools.py web/src/pages/Warning.tsx web/src/api.ts README.md`
> Plans 003/004 change `build.py` elsewhere. If `_window_current` differs from the excerpt below, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW–MED — refactors the function behind the live month-to-date number (guarded by an equality check)
- **Depends on**: plan 003 (backtest the corrected record)
- **Category**: direction (validation of a headline feature)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

"Early warning" is a headline feature (its own page, email and n8n alerts), and the challenge brief and judges
care about it. The rule is simple and printed on the page: partway through a month, compare the month-to-date
harmonized hotspots with the same days in earlier years; ≥90th percentile = *elevated*, ≥75th = *watch*. The README
admits it "has not been backtested". This plan runs the rule as if it were day 10 and day 15 of every month
2006–last full year, then checks how the month actually ended. That gives a hit rate (probability of detection),
false-alarm ratio and Peirce skill score per area. With those numbers the claim is checked, not just stated.
It stays a climatological outlook (the project rule: never a forecast).

## Current state

- `server/kw/build.py:494` `_window_current(con, through, cals, k_scale)` — the live month-to-date comparison:
  ```python
  def _window_current(con, through, cals, k_scale):
      """Month-to-date compared fairly: the same days of the same month in every earlier year."""
      M, D = through.month, through.day
      rows = con.execute(f"""SELECT year(acq_date), obs, daynight, sum(n) FROM d WHERE cls = 'veg'
                             AND month(acq_date) = {M} AND day(acq_date) <= {D} GROUP BY ALL""").fetchall()
      days = con.execute(f"""SELECT sensor, year(acq_date), count(*) FROM read_parquet('{sensor_days().as_posix()}')
                             WHERE month(acq_date) = {M} AND day(acq_date) <= {D} GROUP BY ALL""").fetchall()
      years = list(range(2001 if M < 11 else 2000, through.year + 1))
      keys = [f"{y}-{M:02d}" for y in years]
      agg = {}
      for y, obs, dn, n in rows:
          agg.setdefault(("veg", obs, f"{y}-{M:02d}"), {"det_D": 0, "det_N": 0})[f"det_{dn}"] += n
      dmap = {(s, y): n for s, y, n in days}
      cov = {s: [min(1.0, dmap.get((s, y), 0) / D) for y in years] for s in OBSERVERS}
      v, var, _, _ = _hotspots(agg, keys, cov, "veg", cals["veg"], None, k_scale)
      cur, prior = v[-1], [(y, x) for y, x in zip(years[:-1], v[:-1]) if x is not None]
      ...   # (the rest builds the result dict from cur, prior, var)
  ```
- In `build_region` (around line 740) the order is: `steps, placebo = ...`, `last_year = ...`, `season = ...`,
  `current = _window_current(con, through, cals, k_scale)`, then the `meta = {` dict with `"current": current,`.
- `monthly["classes"]["veg"]["hotspots"]["v"]`, `monthly["periods"]`, `monthly["partial"]` — the full-month harmonized record.
- `server/kw/science.py:WARNING_RULE` and `warning_level(pct_month, pct_week, typical_year_total, n_prior, month_scale)`:
  not scored when `n_prior < 10`, typical year < 100 hotspots, or `month_scale < 5`; `pct_month >= 90` elevated;
  `>= 75` watch. `percentile_rank(value, others)` gives ties half weight.
- `server/kw/tools.py:254` `early_warning(region_id)` returns the dict the Warning page shows (keys `level`,
  `headline`, `month`, `rule`, `caveat`, …).
- `web/src/pages/Warning.tsx:319` `function Detail(...)` renders one area: header, `<div className="tiles">` with
  `<Tile label=… value=… sub=… />` items, `<Weeks w={w} />`, the alert form, and `<p className="muted small">{w.caveat}</p>`.
- `web/src/api.ts:102` `export type Warning = { ... }`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Tests | `python server/tests/test_science.py` | all `ok`, exit 0 |
| Rebuild one preset (raw cache must exist; reuse within 6 h) | `cd server && python -m kw.build punjab` | `built punjab` |
| Rebuild all | `cd server && python -m kw.build` | `built …` ×9 |
| Typecheck | `cd web && npx tsc --noEmit` | exit 0 |

## Scope

**In scope**: `server/kw/science.py` (add `contingency`), `server/kw/build.py` (`_daily_veg`, `_month_to_date`,
`_window_current`, `_warning_backtest`, `build_region`), `server/tests/test_science.py`, `server/kw/tools.py`
(`early_warning` adds one key), `web/src/api.ts` (`Warning` type), `web/src/pages/Warning.tsx` (`Detail`),
`README.md` ("Where it still falls short" + one short results paragraph), `data/regions/**`.

**Out of scope**: the rule thresholds themselves (do not tune them to the backtest — that would be fitting to the
test); `outlook.py`; the weekly part of the rule (not backtested here; say so).

## Git workflow

Branch `advisor/005-warning-backtest`; commits like `Backtest the early-warning rule`; `graphify update .` if installed; no push.

## Steps

### Step 1: `contingency` in `science.py`

```python
def contingency(pairs):
    """Skill of yes/no warnings. pairs: (warned, happened) booleans. POD = hit rate, FAR = false-alarm ratio,
    POFD = false-alarm rate, PSS = Peirce skill score (POD - POFD; 0 = no better than chance, 1 = perfect)."""
    h = sum(w and e for w, e in pairs); m = sum(e and not w for w, e in pairs)
    f = sum(w and not e for w, e in pairs); c = sum(not w and not e for w, e in pairs)
    pod = h / (h + m) if h + m else None
    pofd = f / (f + c) if f + c else None
    return {"n": len(pairs), "hits": h, "misses": m, "false_alarms": f, "correct_negatives": c,
            "base_rate": round((h + m) / len(pairs), 3) if pairs else None,
            "pod": None if pod is None else round(pod, 3),
            "far": round(f / (h + f), 3) if h + f else None,
            "pss": None if pod is None or pofd is None else round(pod - pofd, 3)}
```
Test:
```python
def test_contingency():
    r = sc.contingency([(True, True)] * 6 + [(False, True)] * 2 + [(True, False)] * 2 + [(False, False)] * 90)
    assert (r["hits"], r["misses"], r["false_alarms"], r["correct_negatives"]) == (6, 2, 2, 90)
    assert r["pod"] == 0.75 and r["far"] == 0.25 and abs(r["pss"] - (0.75 - 2 / 92)) < 1e-3
    assert sc.contingency([])["pod"] is None
```
**Verify**: `python server/tests/test_science.py` → `ok test_contingency`

### Step 2: Record today's live number (baseline for the refactor)

```bash
cd server && python -m kw.build punjab
python -c "import json;print(json.load(open('../data/regions/punjab/meta.json'))['current'])" > /tmp/kw_current_before.txt
```
(Use your scratch directory instead of `/tmp` if your environment provides one.)

### Step 3: Refactor `_window_current` onto a reusable month-to-date helper

Add above `_window_current`:

```python
def _daily_veg(con):
    """Vegetation detections per day, satellite and day/night, and the days each satellite observed (one query each)."""
    rows = con.execute("SELECT acq_date, obs, daynight, sum(n) FROM d WHERE cls = 'veg' GROUP BY ALL").fetchall()
    days = con.execute(f"SELECT sensor, acq_date FROM read_parquet('{sensor_days().as_posix()}')").fetchall()
    return rows, days


def _month_to_date(daily, M, D, years, cals, k_scale):
    """Harmonized vegetation hotspots for days 1..D of month M in each of `years`: the early-warning comparison."""
    rows, days = daily
    yset, keys, agg, cnt = set(years), [f"{y}-{M:02d}" for y in years], {}, {}
    for d, obs, dn, n in rows:
        if d.month == M and d.day <= D and d.year in yset:
            agg.setdefault(("veg", obs, f"{d.year}-{M:02d}"), {"det_D": 0, "det_N": 0})[f"det_{dn}"] += n
    for s, d in days:
        if d.month == M and d.day <= D and d.year in yset:
            cnt[(s, d.year)] = cnt.get((s, d.year), 0) + 1
    cov = {s: [min(1.0, cnt.get((s, y), 0) / D) for y in years] for s in OBSERVERS}
    v, var, _, _ = _hotspots(agg, keys, cov, "veg", cals["veg"], None, k_scale)
    return keys, v, var
```
Then change `_window_current` to:
```python
def _window_current(con, through, cals, k_scale, daily=None):
    """Month-to-date compared fairly: the same days of the same month in every earlier year."""
    M, D = through.month, through.day
    years = list(range(2001 if M < 11 else 2000, through.year + 1))
    keys, v, var = _month_to_date(daily or _daily_veg(con), M, D, years, cals, k_scale)
    cur, prior = v[-1], [(y, x) for y, x in zip(years[:-1], v[:-1]) if x is not None]
    ...   # keep every remaining line of the original function unchanged
```
(`d` rows' `acq_date` comes back from DuckDB as `datetime.date`, so `.month/.day/.year` work.)

**Verify**: `cd server && python -m kw.build punjab && python -c "import json;print(json.load(open('../data/regions/punjab/meta.json'))['current'])" | diff - /tmp/kw_current_before.txt`
→ no output (identical). If they differ, STOP.

### Step 4: `_warning_backtest`

```python
def _warning_backtest(daily, monthly, cals, k_scale, last_year, check_days=(10, 15), first=2006):
    """Run the month-to-date rule as if it were day D of every past month, then score it against how that month ended
    (full-month percentile against earlier full months). Calibration uses all years, so this tests the rule, not the
    calibration. Weekly part of the rule not included."""
    keys, vals, part = monthly["periods"], monthly["classes"]["veg"]["hotspots"]["v"], monthly["partial"]
    full = {k: x for k, x, p in zip(keys, vals, part) if x is not None and not p}
    totals = {}
    for k, x in full.items():
        totals.setdefault(int(k[:4]), []).append(x)
    typical = statistics.median([sum(x) for x in totals.values() if len(x) == 12] or [0])
    if typical < 100:
        return {"scored": False, "reason": "a typical year has fewer than 100 hotspots (the rule does not score here)"}
    out = {"scored": True, "first_year": first, "last_year": last_year, "by_day": {}}
    for D in check_days:
        cases = []
        for M in range(1, 13):
            years = list(range(2001 if M < 11 else 2000, last_year + 1))
            _, v, _ = _month_to_date(daily, M, D, years, cals, k_scale)
            for j, y in enumerate(years):
                key = f"{y}-{M:02d}"
                prior_mtd = [v[i] for i in range(j) if v[i] is not None]
                prior_full = [full[f"{years[i]}-{M:02d}"] for i in range(j) if f"{years[i]}-{M:02d}" in full]
                if y < first or v[j] is None or key not in full or len(prior_mtd) < 10 or len(prior_full) < 10:
                    continue
                if max(v[j], statistics.median(prior_mtd)) < 5:
                    continue  # same floor as science.warning_level
                cases.append((sc.percentile_rank(v[j], prior_mtd), sc.percentile_rank(full[key], prior_full)))
        out["by_day"][str(D)] = {
            "elevated": sc.contingency([(a >= 90, b >= 90) for a, b in cases]),
            "watch_or_above": sc.contingency([(a >= 75, b >= 75) for a, b in cases]),
        }
    return out
```

In `build_region`, replace `current = _window_current(con, through, cals, k_scale)` with
```python
    daily = _daily_veg(con)
    current = _window_current(con, through, cals, k_scale, daily)
```
and add to the `meta = {` dict: `"warning_backtest": _warning_backtest(daily, monthly, cals, k_scale, last_year),`

**Verify**: `cd server && python -m kw.build punjab && python -c "import json;print(json.dumps(json.load(open('../data/regions/punjab/meta.json'))['warning_backtest'], indent=1))"`
→ `"scored": true`, `by_day` with keys `"10"` and `"15"`, each `n` > 150, `pss` printed (any value — do not tune).

### Step 5: Serve it with the warning

`server/kw/tools.py` `early_warning`: add to the returned dict `"backtest": m.get("warning_backtest"),`.
`web/src/api.ts` `Warning` type: add
```ts
  backtest?: { scored: boolean; reason?: string; first_year?: number; last_year?: number;
    by_day?: Record<string, Record<"elevated" | "watch_or_above", { n: number; hits: number; misses: number; false_alarms: number; correct_negatives: number; base_rate: Num; pod: Num; far: Num; pss: Num }>> } | null;
```
`web/src/pages/Warning.tsx` `Detail`: after `<Weeks w={w} />` insert a small section:
```tsx
{w.backtest?.scored && w.backtest.by_day?.["15"] && (() => { const e = w.backtest!.by_day!["15"].elevated; return (
  <div className="note">
    <h3>Has this rule worked here before?</h3>
    <p>Run on the 15th of every month from {w.backtest!.first_year} to {w.backtest!.last_year}: of the {e.hits + e.misses} months that
      ended in the top tenth, the rule had already flagged {e.hits} ({fmt((e.pod ?? 0) * 100, 0)}%). Of its {e.hits + e.false_alarms} "elevated" flags,
      {" "}{e.false_alarms} were false alarms. Skill score {e.pss ?? "–"} (0 = chance, 1 = perfect).</p>
  </div>); })()}
```
Reuse existing classes; check `web/src/styles.css` for an existing note/callout class name and use it instead of
`note` if one exists (search for `className="note"` or `.note`). `fmt` is already imported in Warning.tsx.

**Verify**: `cd web && npx tsc --noEmit` → exit 0

### Step 6: Rebuild all, write the README lines

`cd server && python -m kw.build`. Then print a table (area, day-15 elevated POD, FAR, PSS, n) with a short Python
snippet over `data/regions/*/meta.json`. In `README.md`, replace "and the early-warning rule has not been
backtested" with one sentence + a small table built from that output (copy printed numbers only). If any area's
PSS ≤ 0, say so plainly under "Where it still falls short".

## Test plan

- `test_contingency` (step 1).
- Refactor equality check (step 3) — the live month-to-date result must be byte-identical.
- Sanity: the base rate of `elevated` should be about 0.10 (top tenth by construction); print it in step 6 and
  STOP if any area is outside 0.03–0.25.

## Done criteria

- [ ] `python server/tests/test_science.py` exits 0
- [ ] Step 3 diff is empty
- [ ] Every preset `meta.json` has `warning_backtest` (`scored` true or a `reason`)
- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `grep -n "not been backtested" README.md` returns nothing
- [ ] `docs/plans/README.md` row 005 updated

## STOP conditions

- Step 3 diff is not empty.
- A build takes more than 3× its previous time (the per-day loop is too slow; report timings).
- Base rate check fails (see Test plan).

## Maintenance notes

- Never retune the 75/90 thresholds on these results without a separate hold-out period; note that in any PR.
- If plan 010 (fire-weather or burned-area context) lands, the same `contingency` helper can score whether that
  signal adds skill.
