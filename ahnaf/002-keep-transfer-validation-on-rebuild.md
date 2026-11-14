# Plan 002: Rebuilding one area keeps its geographic hold-out result

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/build.py`
> If it changed, compare the "Current state" excerpts against the live code; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (run before plans 003–005 so their rebuilds keep the value)
- **Category**: bug
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

Each preset area's `meta.json` carries `transfer_validation`: a geographic hold-out where the Suomi-NPP→Aqua
calibration is fitted on the *other* preset areas and tested here. It is one of the project's strongest
validation results and the Method page shows it. But it is only computed in `main()` after a full build; any
single-area rebuild (the background refresh in `tools.refresh_if_stale`, or `build_region` called alone) writes
`"transfer_validation": None`. Today Punjab and South-east Australia — the two flagship regions — show `null`.
After this plan, single-area rebuilds keep the previous value, and there is a fast command to recompute it.

## Current state

- `server/kw/build.py:709` `build_region(region_id, info, progress=None, source=None)` builds one area and writes
  `meta.json`. Inside the `meta = {...}` dict (around line 800):
  ```python
          "transfer_validation": None,
  ```
  and later (around line 814):
  ```python
      folder = OUT / region_id
      folder.mkdir(parents=True, exist_ok=True)
  ```
- `server/kw/build.py:825` `transfer_validation(region_ids)` — reads every preset's `monthly.json` and returns
  `{region_id: {...}}`. Pure; depends only on 2012–2020 data.
- `server/kw/build.py:874`:
  ```python
  def main(ids):
      ids = ids or list(PRESETS)
      for rid in ids:
          build_region(rid, PRESETS[rid], lambda y, d, t: print(f"{rid}: {y} ({d}/{t})", flush=True))
          print(f"built {rid}", flush=True)
      built = [p.parent.name for p in OUT.glob("*/meta.json") if p.parent.name in PRESETS]
      tv = transfer_validation(built)
      for rid in built:
          ...  m["transfer_validation"] = tv.get(rid) ...
      write_index()
      write_ratio_table(built)
  ```
- `server/kw/tools.py:380` `refresh_if_stale(rid)` and `start_aoi` call `build_region` alone (never `main`).
- Current data: `python -c "import json;print(json.load(open('data/regions/punjab/meta.json'))['transfer_validation'])"` → `None`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Python env | `cd server && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` | exit 0 |
| Tests | `python server/tests/test_science.py` | all `ok`, exit 0 |
| Recompute transfer only (new) | `cd server && python -m kw.build --transfer-only` | prints `transfer validation: N areas`, exit 0 |

## Scope

**In scope**: `server/kw/build.py` (`build_region` meta assembly, `main`), `data/regions/*/meta.json` (rewritten by step 3).

**Out of scope**: the `transfer_validation()` math; `server/kw/tools.py`; any UI.

## Git workflow

Branch `advisor/002-keep-transfer-validation`; commit style like `Keep transfer validation on single-area rebuilds`;
run `graphify update .` if installed; do not push.

## Steps

### Step 1: Carry the previous value over in `build_region`

Just before the `meta = {` assembly is used to write files (right after `folder = OUT / region_id` /
`folder.mkdir(...)`), add:

```python
    old = folder / "meta.json"
    if old.exists():  # computed across all presets in main(); a single-area rebuild must not erase it
        meta["transfer_validation"] = json.loads(old.read_text(encoding="utf-8")).get("transfer_validation")
```

**Verify**: `python -c "import ast,sys; ast.parse(open('server/kw/build.py').read())"` → no output

### Step 2: Add `--transfer-only` to `main`

At the top of `main(ids)`:

```python
    if ids == ["--transfer-only"]:
        ids = []
        skip_build = True
    else:
        ids, skip_build = ids or list(PRESETS), False
```
and wrap the build loop in `if not skip_build:`. After computing `tv`, print
`print(f"transfer validation: {len(tv)} areas", flush=True)`. Keep `write_index()` and `write_ratio_table(built)`.

**Verify**: `cd server && python -m kw.build --transfer-only` → `transfer validation: 9 areas` (needs no internet).

### Step 3: Confirm the regions now carry the value

**Verify** (repo root):
```bash
python -c "import json,glob;print({f.split('/')[2]: json.load(open(f))['transfer_validation'] is not None for f in glob.glob('data/regions/*/meta.json')})"
```
→ every preset `True`.

## Test plan

No new unit test (I/O-only change). The verification in step 3 is the check; plan 001's
`server/tests/test_data_integrity.py` may gain `test_presets_have_transfer_validation` if plan 001 is already merged.

## Done criteria

- [ ] `python server/tests/test_science.py` exits 0
- [ ] `cd server && python -m kw.build --transfer-only` prints `transfer validation: 9 areas`
- [ ] Step 3 prints `True` for all 9 presets
- [ ] `git status` shows only `server/kw/build.py`, `data/regions/*/meta.json`, `data/regions/index.json`, `data/regions/calibration_table.csv` changed
- [ ] `docs/plans/README.md` row 002 updated

## STOP conditions

- `--transfer-only` reports fewer than 9 areas.
- Any preset's `monthly.json` lacks `raw.MODIS_A` (format drift).

## Maintenance notes

- Plans 003–005 rebuild all presets with `python -m kw.build`, which recomputes transfer validation anyway.
- If the hold-out windows (2012–2016 train, 2017–2020 test) ever change, run `--transfer-only` after.
