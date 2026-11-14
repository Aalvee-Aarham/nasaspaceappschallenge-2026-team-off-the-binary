# Verification, rollout and risk

**Date:** 2026-11-13 · **Status:** design · **Base commit:** `1e99c85`

How to know the two features are right, how to ship them without breaking what already works, and what could go
wrong. The risk register in `README.md` §6 is the summary; this file is the operational detail.

---

## 1. The verification ladder

Four levels. Each one is cheap and each one catches a different class of mistake. Run them in order — the expensive
ones are only worth running if the cheap ones pass.

| Level | What it checks | Cost | When |
|---|---|---|---|
| **L1 — unit** | the verdict function, the witness states, the cell arithmetic | seconds | every change |
| **L2 — data** | the shipped JSON files: shape, index-parallelism, internal consistency | ~1 min | after every build |
| **L3 — service** | the HTTP and MCP surfaces, against a running API | ~2 min | after every change to `tools.py` / `api.py` |
| **L4 — live** | the deployed demo: the tab renders, the numbers match the JSON | ~10 min | before the freeze and after every redeploy |

---

## 2. L1 — unit tests

New file `server/tests/test_cases.py`, same runner style as `server/tests/test_science.py`
(`python server/tests/test_cases.py` prints `ok <name>` per test and exits 0).

```python
def test_satellite_states():
    assert cases.satellite_state({"MODIS_A": 0.0}, None, False) == "abstain"
    assert cases.satellite_state({"MODIS_A": 1.0}, 12.0, True) == "fire"
    assert cases.satellite_state({"MODIS_A": 1.0}, None, False) == "quiet"

def test_verdicts_all_six():
    agency = {"source": "NASA EONET"}
    press = {"source": "GDELT DOC", "count": 3}
    assert cases.verdict("fire", {}, agency, None, None) == "corroborated"
    assert cases.verdict("fire", {}, None, None, press) == "reported"
    assert cases.verdict("fire", {}, None, None, None) == "satellite_only"
    assert cases.verdict("quiet", {}, agency, None, None) == "agency_only"
    assert cases.verdict("abstain", {}, agency, None, None) == "abstained"
    assert cases.verdict("quiet", {}, None, None, None) == "insufficient"

def test_abstain_beats_quiet():
    # an absent witness must never turn into a negative finding
    assert cases.verdict("abstain", {}, None, None, None) == "abstained"

def test_cross_family_agreement_band():
    assert cases.cross_family(100, 105, {"MODIS_A": 1.0})["agrees"] is True
    assert cases.cross_family(100, 160, {"MODIS_A": 1.0})["agrees"] is False
    assert cases.cross_family(None, 160, {"MODIS_A": 1.0})["state"] == "abstain"
```

New file `server/tests/test_exposure.py`:

```python
def test_exposure_file_shape():
    # for every shipped exposure.json:
    #   len(cells) == len(grid.json cells)
    #   every hospital cell is in the grid's cells
    #   every road's cells are in the grid's cells
    #   totals.population == sum(cells[2])
    #   population and infrastructure blocks name their source

def test_exposure_join():
    # tools.exposure(rid, period) counts exactly the cells in grid["months"][period]
```

**Exit criteria:** `python server/tests/test_science.py && python server/tests/test_cases.py &&
python server/tests/test_exposure.py` → all `ok`, exit 0.

> **Note on the runner.** These tests import `kw.cases` and `kw.tools`, which import `duckdb`. Run them in the venv
> (`server/requirements.txt` is installed), not with a bare `python3`. `test_science.py` itself stays
> duckdb-free — that is why it can run anywhere.

---

## 3. L2 — data checks over the shipped files

A single script that can be run after every build. Put it in `scripts/check_features.py` so it is repeatable and so
the judge can run it too.

```python
"""Check the shipped casebook and exposure files. Run: python scripts/check_features.py"""
import json, glob, sys

VERDICTS = {"corroborated", "reported", "satellite_only", "agency_only", "abstained", "insufficient"}
STATES = {"fire", "quiet", "abstain"}
fail = 0

def bad(msg):
    global fail
    print("FAIL:", msg); fail += 1

for f in sorted(glob.glob("data/regions/*/cases.json")):
    area = f.split("/")[-2]
    c = json.load(open(f))
    g = json.load(open(f"data/regions/{area}/grid.json"))
    if sum(c["counts"].values()) != len(c["cases"]):
        bad(f"{area}: counts {c['counts']} do not sum to {len(c['cases'])} cases")
    if set(c["counts"]) != VERDICTS:
        bad(f"{area}: counts keys {set(c['counts'])} != {VERDICTS}")
    seen = set()
    for x in c["cases"]:
        if x["id"] in seen: bad(f"{area}: duplicate case id {x['id']}")
        seen.add(x["id"])
        if x["verdict"] not in VERDICTS: bad(f"{area}: bad verdict {x['verdict']}")
        sat = x["witnesses"]["satellite"]
        if sat["state"] not in STATES: bad(f"{area}: bad satellite state {sat['state']}")
        if sat["state"] == "quiet" and sat["coverage"] == 0:
            bad(f"{area}: case {x['id']} says quiet with zero coverage — must abstain")
        if x["verdict"] == "agency_only" and sat["state"] != "quiet":
            bad(f"{area}: case {x['id']} is agency_only but the satellite state is {sat['state']}")
        if x["period"] not in g["months"] and x["witnesses"]["satellite"]["cell_present"]:
            bad(f"{area}: case {x['id']} claims a cell in {x['period']}, which is not in the grid")
    for s in c["sources"]:
        if s["error"] and s["count"]:
            bad(f"{area}: source {s['name']} has both an error and a count")

for f in sorted(glob.glob("data/regions/*/exposure.json")):
    area = f.split("/")[-2]
    e = json.load(open(f))
    g = json.load(open(f"data/regions/{area}/grid.json"))
    if len(e["cells"]) != len(g["cells"]):
        bad(f"{area}: {len(e['cells'])} exposure cells vs {len(g['cells'])} grid cells")
    grid_cells = {tuple(c) for c in g["cells"]}
    for h in e["hospitals"]:
        if tuple(h["cell"]) not in grid_cells: bad(f"{area}: hospital {h['name']} in a cell outside the grid")
    for r in e["roads"]:
        for cell in r["cells"]:
            if tuple(cell) not in grid_cells: bad(f"{area}: road {r['name']} crosses a cell outside the grid")
    if e["totals"]["population"] != sum(c[2] for c in e["cells"]):
        bad(f"{area}: population total != sum of cells")
    for h in e["hospitals"]:
        if h["nearest_fire_km"] is not None and h["nearest_fire_km"] < 0:
            bad(f"{area}: negative nearest_fire_km")

print("FAILURES:", fail)
sys.exit(1 if fail else 0)
```

Three of these checks are the ones that matter most, because they encode the guardrails:

- `counts` must sum to `len(cases)` — no silent truncation.
- **A case may never say `quiet` while the coverage is zero** — that is the abstention rule, enforced on the data.
- `agency_only` requires the satellite state to be `quiet` — the verdict and the witness must agree.

---

## 4. L3 — service checks

```bash
cd server && uvicorn kw.api:app --port 8000 &
sleep 3

# the casebook
curl -s localhost:8000/api/regions/dhaka-kilns/cases | python -m json.tool | head -30
curl -s "localhost:8000/api/regions/dhaka-kilns/cases?verdict=agency_only" | python -m json.tool | head -20
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/regions/dhaka-kilns/cases/does-not-exist   # 404

# the exposure layer
curl -s "localhost:8000/api/regions/dhaka-kilns/exposure?period=2024-11" | python -m json.tool | head -30

# the MCP surface
curl -s -X POST localhost:8000/mcp -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m json.tool | grep -c get_fire_cases
```

**Exit criteria:** every 200 has the documented shape; the 404 case is a 404 and not a 500; the MCP tool list
contains `get_fire_cases` and `get_exposure`.

---

## 5. L4 — live checks

Against the deployed demo, after the redeploy:

| Check | How | Expected |
|---|---|---|
| the Cases tab renders | open `/#pg=explore&r=dhaka-kilns`, click **Cases** | a table with the six verdict chips and a non-zero count |
| the witness panel opens | click a row | every witness row shows its source, and the satellite row shows a number or "could not see" |
| the reverse direction is visible | filter to `agency_only` | either cases, or an explicit "none in this area" — never a blank table |
| the exposure panel shows the caveat | switch to the Exposure panel | the caveat text is visible without scrolling past it |
| the numbers match the JSON | pick a case; compare the panel's number with `curl /api/regions/<id>/cases` | identical |
| the map overlays switch on and off | toggle population / hospitals | the map does not throw, and the legend updates |
| the offline path still works | stop the API; reload | the app degrades to the preset areas, as before |
| the console is clean | open the browser console | no errors, no unhandled rejections |

---

## 6. Regression risk — what could break what already works

| Change | Can break | How to catch it |
|---|---|---|
| `meta["method"]` gains entries | the Method page layout | `npx tsc --noEmit` + a look at the Method page |
| `monthly.json` gains `viirs_only` | any consumer that iterates the class block | `npx tsc --noEmit`; the type must be **optional** (`viirs_only?: Num[]`) so pre-existing files still type-check |
| `news.eonet()` items gain fields | the ReportList UI, `news._search` | `python server/tests/test_science.py`; one manual report search |
| `build_region` now writes `cases.json` | **the build itself** — a network failure must not fail a build | deliberately break the network and run `python -m kw.build dhaka-kilns` → must exit 0 with `cases.error` set |
| a new Explorer tab | the tab bar layout on a narrow screen; the `Record.tsx` focus bug (finding C3) becomes reachable on the new tab too | check at 1280×720 and at 390 px |
| `Connect.tsx` tool count | the "31 tools" number in the README badge and on the page | `TOOLS` in `Connect.tsx` gains two rows → the page computes `nTools` from that list → it becomes 33. The **README badge must be updated to 33** or the two will disagree. |
| `scripts/build_exposure.py` | nothing at runtime — it is not imported by the app | confirm `grep -rn "exposure" server/kw/` shows only `tools.py`'s reader |

> **The README badge is a real trap.** `README.md:17` says "MCP-31 tools" and `web/src/pages/Connect.tsx:63` computes
> the number from its own list. Adding two MCP tools makes the page say 33 and the badge say 31. Change the badge in
> the same commit that adds the tools.

---

## 7. Rollout order

The features must be shipped in an order where each step leaves the app working.

| Step | Ships | Leaves the app working because |
|---|---|---|
| 1 | `scripts/build_exposure.py` + the nine `exposure.json` files | nothing in the app reads them yet |
| 2 | `tools.exposure()` + `GET /api/regions/{rid}/exposure` + the MCP tool + the agent tool | the data is already there; the API is additive |
| 3 | the exposure panel in the Cases tab (which is a placeholder until then) | the tab exists with a heading and the panel |
| 4 | `news.eonet()`'s three new fields | additive |
| 5 | `kw/cases.py` + the nine `cases.json` files | nothing reads them yet |
| 6 | `tools.list_cases()` + `get_case()` + the API routes + the MCP tool + the agent tool | additive |
| 7 | the Cases tab UI | the last piece |
| 8 | the Method page wording, the README rows, the badge | copy only |

Steps 1–3 and 4–7 are independent and can run in parallel by two people.

### Rollback

Every step is revertible by deleting the new files and reverting the diff:

```bash
# if the exposure layer misbehaves
rm data/regions/*/exposure.json
# revert the API/MCP/agent/web additions for exposure only
git checkout -- server/kw/api.py server/kw/mcp_server.py server/kw/agent.py web/src/api.ts web/src/App.tsx
```

The exposure layer is the safer of the two to drop: it is additive, its data is external, and no published number
depends on it. **The casebook should not be rolled back** once it is in front of judges — a feature that has been shown
and then disappears reads as a broken build.

---

## 8. Risk register — expanded

The trigger column is the thing to watch for; the response is what to do when it fires.

| # | Risk | Trigger | Response |
|---|---|---|---|
| R1 | the casebook publishes the record's own bugs as verdicts | an `agency_only` case turns out to be a record bug rather than a missed fire | **Mitigated: the `combine` zero-weight fix has landed** (`science.py:108`), so the satellite witness no longer follows sensors that observed nothing. If a new class of record bug appears, fix the record — do not soften the verdict. The casebook exists to find exactly these. |
| R2 | EONET / GDACS coverage is thin before 2016 | `counts` shows almost no cases before 2016 | Expected. The record-derived candidates carry the early years. Say so in the UI: "external witnesses start in 2016". |
| R3 | Overpass rate-limits | a `sources[].error` on two or more areas | The script retries with backoff and falls back to a mirror. If it still fails, the areas are recorded as missing and the UI says so. **Never write "0 hospitals".** |
| R4 | the population raster is presented as current | any copy that says "people affected" | The caveat text is in three places (the API payload, the UI panel, the Method page). Search the diff for "affected" before shipping. |
| R5 | the exposure layer reads as a targeting list | any copy that names a specific community as "at risk" | Frame as "where a responder should look". The research lead reviews the wording before step 3. |
| R6 | repository bloat | `exposure.json` > 600 KB for an area | Something is wrong with the cell list. The road-geometry decision (§4.4 of `exposure.md`) keeps this in check; if it still trips, cap and record it. |
| R7 | nothing points at the features | the tab is not in the nav, the Method page does not mention it, the README has no row | Step 8 is a checklist item with three named places, not a nicety. |
| R8 | Google News refuses the historical queries | a `sources[].error` on the press witness for pre-2017 cases | The press witness abstains; the case still stands on the other witnesses. |
| R9 | the casebook is slow to build | the rebuild takes > 10 min | The EONET/GDACS/GDELT responses are cached for a year in `data/news_cache/`; only the first build after the cache expires pays. |
| R10 | the agent misdescribes a witness | a Gemini answer that says "no reports, so no fire" | The two `SYSTEM` lines (contracts §6.3). Add a regression case to the analyst's test prompts. |

---

## 9. Pre-submission checklist

Run the whole ladder, then:

- [ ] `cd server && python -m pytest tests -q` (or the three runners) → all pass, exit 0
- [ ] `python scripts/check_features.py` → `FAILURES: 0`, exit 0
- [ ] `cd web && npx tsc --noEmit` → exit 0
- [ ] `cd web && npm run build` → exit 0
- [ ] every number on the Cases tab and the Exposure panel traces to a committed JSON file
- [ ] the verdict counts on screen match `cases.json` exactly
- [ ] the abstention rule is visible in the UI (a case that says "could not see" exists somewhere and renders in words)
- [ ] the README "Data used" table has rows for WorldPop and OpenStreetMap, with licences
- [ ] the README MCP badge matches the tool count on the Connect page
- [ ] the Method page has the witnesses and exposure sections, with the caveats in full
- [ ] `git status` shows no stray files; `data/cache/exposure/` is gitignored
- [ ] the live demo passes the L4 table
