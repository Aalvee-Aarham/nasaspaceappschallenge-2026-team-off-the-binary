# Plan 014: A satellite that saw nothing gets a fair weight in `science.combine`

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the expected
> result before moving on. If anything in "STOP conditions" occurs, stop and report. When done, update the status row
> for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/science.py server/tests/test_science.py`
> If `combine` changed, compare it with the excerpt below; on a mismatch, STOP.

## Status

- **Priority**: P2 (real bug, small measured impact; costs nothing if it rides the plan-003 rebuild)
- **Effort**: S
- **Risk**: LOW (one line; changes only periods where one satellite read 0 and another read more than 0)
- **Depends on**: none for the code. Do the code before plan 003's rebuild so one rebuild covers both.
- **Category**: bug (science correctness)
- **Planned at**: commit `1e99c85`, 2026-11-13 (from code-scan finding S1, verified)

## Why this matters

`combine` weights each satellite's estimate by the inverse of its variance, with the counting (Poisson) variance
evaluated at the **pooled mean** so that a satellite reading low does not earn extra weight. The zero case skips that
rule: when a satellite counted 0, its counting variance is the floor value instead of the variance at the pooled
mean, so it gets a much larger weight than a satellite that read the mean. The record is pulled toward zero in
exactly the sparse periods where one satellite missed a small fire.

Measured on the published data (2026-11-13, reconstruction of `monthly.json` matched to ≤0.02% median error): only one
published month with a value ≥5 changes by more than 20% (Niger Delta 2026-11, partial month, 5.6 → 8.3). So the
impact is low today, but it is a stated rule ("variances are evaluated at the pooled mean") that the code breaks.

## Current state

- `server/kw/science.py:96-112`:
  ```python
  def combine(estimates):
      """Inverse-variance mean of per-sensor estimates already in reference units.

      estimates: (value, sigma2_rel, counting_var) per sensor. Variances are evaluated at the pooled mean, so a
      sensor that happens to read low does not earn extra weight (a known bias of naive Poisson weighting).
      Returns (value, variance) or None when no sensor observed the period.
      """
      if not estimates:
          return None
      mu = statistics.fmean(v for v, _, _ in estimates)
      weights = []
      for v, s2, cv in estimates:
          counting = cv * (mu / v) if v > 0 else cv
          weights.append(1.0 / max(mu * mu * s2 + counting, 1e-9))
      W = sum(weights)
      return sum(w * e[0] for w, e in zip(weights, estimates)) / W, 1.0 / W
  ```
- The caller `server/kw/build.py` `_series` builds each tuple as `(b * x / c, s2, b * b * cv / (c * c))` where
  `x, cv = _value(...)` and `_value` returns `(v, max(v, 1.0))`. So for a count `x > 0`, `cv_tuple = b·v/c` and the
  pooled-mean rule gives `b·mu/c`. For `x == 0`, `cv_tuple = b²/c²`, so `sqrt(cv_tuple) = b/c` and the pooled-mean
  value is `sqrt(cv_tuple) · mu`. No tuple change is needed.
- Test exemplar, `server/tests/test_science.py:46-53`:
  ```python
  def test_combine():
      assert sc.combine([]) is None
      y, var = sc.combine([(10.0, 0.0, 10.0)])
      assert y == 10.0 and abs(var - 10.0) < 1e-9
      ...
      y, _ = sc.combine([(0.0, 0.0, 1.0), (0.0, 0.05, 0.1)])  # all-zero cell stays zero, no division error
      assert y == 0.0
  ```

## Scope

**In scope**: `server/kw/science.py` (`combine`, one line + docstring line), `server/tests/test_science.py` (`test_combine`).
**Out of scope**: `build.py` (do not change the tuple layout), `_grid` (plan 006 moves it onto `combine`; it then
inherits this fix), any data file by hand.

## Steps

### Step 1: Fix the zero branch

Replace the line
```python
        counting = cv * (mu / v) if v > 0 else cv
```
with
```python
        # zero count: cv = (b/c)^2 from the max(x, 1) floor, so the variance at the pooled mean is sqrt(cv) * mu
        counting = cv * (mu / v) if v > 0 else (math.sqrt(cv) * mu if mu > 0 else cv)
```
`math` is already imported in `science.py`.

### Step 2: Test

Add to `test_combine` (before its last line is fine):
```python
    y, _ = sc.combine([(0.0, 0.0, 1.0), (10.0, 0.0, 10.0)])  # a zero reading weighs the same as one at the mean
    assert abs(y - 5.0) < 1e-9
```
Before the fix this returns ~1.67.

**Verify**: `python server/tests/test_science.py` → `ok test_combine` and every other test `ok`, exit 0.

### Step 3: Rebuild (only together with plan 003)

Do not run a separate rebuild. Plan 003 step 6 (`cd server && python -m kw.firms && python -m kw.build`) publishes
this change too. If plan 003 is skipped, run `cd server && python -m kw.build` once after this plan.

## Done criteria

- [ ] `python server/tests/test_science.py` exits 0 and includes `ok test_combine`
- [ ] `grep -n "math.sqrt(cv) \* mu" server/kw/science.py` → one hit
- [ ] `docs/plans/README.md` row 014 updated

## STOP conditions

- `_value` in `build.py` no longer returns `max(v, 1.0)` as the variance (the derivation above no longer holds).
- After the rebuild, any preset's full-year total moves by more than 2% (the measured impact is far smaller; a big
  change means something else changed).

## Maintenance notes

- If the counting variance ever gets an overdispersion factor, carry it into the zero branch too.
- Quantities that are not counts (FRP) can be in (0, 1); for them the old floor behaviour is unchanged.
