# Plan 001: Every area listed in the region index actually exists in the repo

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- server/kw/tools.py server/kw/build.py web/src/api.ts data/regions/index.json`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

Kiln Watch is a NASA Space Apps 2026 entry; judges may clone the repo or open the live site. The committed region
index `data/regions/index.json` lists 15 areas, but 6 of them are custom areas (`aoi-*`) whose folders are
gitignored, so they do not exist in a clone. The home page lists them under "custom areas" and opening one fails
with a 404. The live site only works because it was deployed from a laptop that still had those folders, so the
live site cannot be reproduced from git. After this plan, the index only lists areas that exist, and a fresh
clone shows no dead entries.

## Current state

- `data/regions/index.json` — committed list of areas. Contains these custom entries whose folders are NOT in git:
  `aoi-1855481ab2` (Aweil West, South Sudan), `aoi-884e39f1d4` (Sylhet, Bangladesh), `aoi-9ecb8d4879` ("Cerrado test", Brazil),
  `aoi-a39b5bc52c` (Darlawn, India), `aoi-bb55b29398` (Pabna, Bangladesh), `aoi-bd67ddcaf8` (Bhatwari, India).
- `.gitignore` contains `data/regions/aoi-*/` (custom areas are deliberately not committed).
- `server/kw/build.py:849` `write_index()` — writes `index.json` from every `data/regions/*/meta.json` on disk
  (so it includes any custom area built locally).
- `server/kw/tools.py:43-45`:
  ```python
  def list_regions():
      f = OUT / "index.json"
      return json.loads(f.read_text(encoding="utf-8"))["regions"] if f.exists() else []
  ```
  Used by `/api/regions`, `/api/health`, `/api/warnings` and alerts.
- `server/kw/tools.py` already has `def is_built(rid): return (OUT / rid / "meta.json").exists()`.
- `web/src/api.ts` — `regions: () => json<{ regions: RegionItem[] }>("/data/regions/index.json").then((r) => r.regions),`
  The web app reads the static index file directly, not `/api/regions`.
- Conventions: Python is stdlib-first, short functions, comments explain *why*. TypeScript: functional React, the
  `json<T>()` helper in `web/src/api.ts` for every fetch.

## Commands you will need

| Purpose | Command (from repo root unless noted) | Expected on success |
|---|---|---|
| Python env | `cd server && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` | exit 0 |
| Science tests | `python server/tests/test_science.py` | one `ok test_…` line per test, exit 0 |
| New test | `python server/tests/test_data_integrity.py` | `ok …` lines, exit 0 |
| Web install | `cd web && npm ci` | exit 0 |
| Typecheck | `cd web && npx tsc --noEmit` | exit 0, no output |

## Scope

**In scope**:
- `server/kw/tools.py` (`list_regions` only)
- `web/src/api.ts` (`regions` only)
- `data/regions/index.json` (regenerate)
- `server/tests/test_data_integrity.py` (create)

**Out of scope**:
- `.gitignore` — do NOT start committing `aoi-*` folders (that is a product decision for the team).
- `server/kw/build.py` `write_index()` — locally built custom areas must still appear on the developer's machine.
- Any region JSON other than `index.json`.

## Git workflow

- Branch: `advisor/001-index-integrity`
- Commit message style matches `git log`: short imperative sentence case, e.g. `Drop missing custom areas from the region index`.
- If `graphify` is installed, run `graphify update .` after code changes (project rule in `CLAUDE.md`); if not, skip and say so.
- Do NOT push.

## Steps

### Step 1: Filter `list_regions()` to areas that exist

Change `server/kw/tools.py` `list_regions()` to drop entries whose `meta.json` is missing:

```python
def list_regions():
    f = OUT / "index.json"
    items = json.loads(f.read_text(encoding="utf-8"))["regions"] if f.exists() else []
    return [r for r in items if is_built(r["id"])]  # index may list custom areas built on another machine
```

`is_built` is defined later in the same module; that is fine in Python because it is resolved at call time.

**Verify**: `cd server && python -c "from kw import tools; print(len(tools.list_regions()))"` → `9`

### Step 2: The web app asks the API first, falls back to the static file

In `web/src/api.ts` replace the `regions` entry with:

```ts
regions: () => json<{ regions: RegionItem[] }>("/api/regions")
  .catch(() => json<{ regions: RegionItem[] }>("/data/regions/index.json"))
  .then((r) => r.regions),
```

(`/api/regions` returns `{"regions": [...]}` — see `server/kw/api.py` `regions()`.)

**Verify**: `cd web && npx tsc --noEmit` → exit 0

### Step 3: Regenerate the committed index from committed folders

```bash
cd server && python -c "from kw.build import write_index; write_index()"
```
In this checkout no `aoi-*` folders exist, so the result lists only the 9 presets.

**Verify**: `python -c "import json; r=json.load(open('data/regions/index.json'))['regions']; print(len(r), all(x['preset'] for x in r))"` (from repo root) → `9 True`

### Step 4: Add a data-integrity test

Create `server/tests/test_data_integrity.py`, modelled on `server/tests/test_science.py` (plain `test_*` functions
and the same `if __name__ == "__main__":` runner at the bottom of that file):

- `test_index_entries_exist`: for every entry in `data/regions/index.json`, `data/regions/<id>/meta.json` exists.
- `test_presets_have_all_files`: every preset folder has `meta.json monthly.json weekly.json grid.json static.json`.

Use `Path(__file__).resolve().parents[2] / "data" / "regions"`; stdlib only.

**Verify**: `python server/tests/test_data_integrity.py` → `ok test_index_entries_exist`, `ok test_presets_have_all_files`, exit 0

## Test plan

- New file `server/tests/test_data_integrity.py` (2 tests above). It must fail if someone commits an index that
  lists a missing folder again — check by temporarily adding a fake entry by hand, running it (fails), then reverting.

## Done criteria

- [ ] `python server/tests/test_science.py` exits 0
- [ ] `python server/tests/test_data_integrity.py` exits 0
- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `grep -c '"aoi-' data/regions/index.json` prints `0`
- [ ] Only in-scope files changed (`git status`)
- [ ] `docs/plans/README.md` row 001 updated

## STOP conditions

- `data/regions/aoi-*` folders exist in your checkout (then the team chose to commit them; ask before regenerating).
- `/api/regions` in `server/kw/api.py` does not return `{"regions": [...]}`.
- Step 1 prints a number other than 9 (a preset folder is missing — report which).

## Maintenance notes

- Whoever deploys with `vercel` from a laptop ships whatever `data/regions/` holds locally. Before deploying, run
  `python server/tests/test_data_integrity.py`.
- The team may decide to promote Sylhet and Pabna (Bangladesh) to presets for the local-impact story; that is a
  separate change in `server/kw/regions.py` `PRESETS` plus a build — not part of this plan.
