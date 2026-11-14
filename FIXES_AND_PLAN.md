# NASA Space Apps 2026 Submission Fixes and Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-driven development for every behavior change and perform one fresh whole-branch review before merge. Steps use checkbox syntax for tracking.

**Goal:** Make Kiln Watch scientifically defensible, operationally reliable, locally useful, and presentation-ready for the 2026 NASA Space Apps Challenge targeting **Local Impact, Galactic Impact, Best Use of Data, and Best Use of Technology**.

**Architecture:** Keep the existing deterministic pipeline—NASA FIRMS → DuckDB over remote GeoParquet → empirical-Bayes sensor calibration → committed region JSON → one shared REST/MCP/agent tool layer. Improve the evidence and runtime in place; do not replace the application with a new framework, an opaque model, or a competing data pipeline.

**Tech Stack:** Python 3.12, FastAPI, DuckDB 2.x, MCP Python SDK 1.30, React 19, TypeScript 5.8, Vite 6, MapLibre GL JS, Three.js, GSAP, NASA FIRMS/GIBS/EONET, APAD asset data, NASA MCD64A1 burned area.

**Spec:** [`RESEARCH_AND_BENCHMARKS.md`](RESEARCH_AND_BENCHMARKS.md)

## Global Constraints

- Preserve the existing deterministic calculation path shared by the web app, REST API, MCP server, and Gemini analyst.
- A detection is not a fire, not burned area, and not an event count.
- The Aqua-scale value is a **calibrated estimate**, not a direct MODIS observation after 2002; the VIIRS-native view and raw series remain visible.
- Never replace “not observed” with zero; preserve null/partial/provisional semantics.
- Day and night remain calibrated separately.
- NASA and third-party data must retain attribution, licence, version/date, and provenance.
- Public deployments must not expose unauthenticated state-changing tools.
- No new runtime dependency unless the standard library or an installed dependency cannot do the job.
- No navigation, theme, or core-state rewrite without evidence that it is required.
- A scientific change that alters published values must be measured against the current nine-area outputs before it is accepted.
- Do not infer physical truth from a README claim; competitors’ metrics remain project claims unless rerun.
- The official NASA pre-start rule is a submission blocker requiring written GO-team clarification; code work cannot resolve eligibility.

## Review Focus

These are the failure modes most likely to make a reasonable judge lose trust:

1. A missing satellite observation renders as “zero fires” in a calendar, map, export, or alert.
2. A partial current month or the first five-day ISO-week stub enters a baseline or trend as a complete period.
3. NRT rows without FIRMS `type` are silently described as vegetation fire.
4. The UI calls a calibrated estimate “the number MODIS would have recorded” or calls persistent heat “kilns” without a validated source.
5. A failed upstream source is shown as a completed search with zero reports.
6. A public endpoint allows unbounded builds, arbitrary email confirmation, or destructive writes.
7. A map cell does not reconcile with the calendar total for the same month and area.
8. A screening, confidence, cloud, or observation mask silently changes the estimand.
9. A validation script fails open when a data gate or network source is unavailable.
10. A data rebuild changes published numbers without recording the method/version/fingerprint that produced them.

---

# 1. Adversarial triage summary

The audits were reproduced against the current code and committed outputs. The current implementation is not stale: Punjab reproduces with zero mismatches across the published monthly series. The following classifications are binding for implementation.

## Bucket A — apply immediately

| ID | Verified root cause | Required correction | Primary files |
|---|---|---|---|
| A-API-01 | `POST /api/alerts {}` reaches `len(None)` and returns 500 | Validate the alert target and return 400 | `server/kw/alerts.py`, `server/kw/regions.py` |
| A-API-02 | News cache writes are non-atomic; concurrent readers can parse a truncated file | Temp-file + `os.replace` | `server/kw/news.py` |
| A-API-03 | JSON/CSV responses are uncompressed in the container deployment | Add FastAPI gzip middleware | `server/kw/api.py` |
| A-API-04 | A failed upstream (observed GDELT 429) is never negatively cached; Google/EONET/GDACS calls are serial | Cache failures briefly and fetch independent sources concurrently | `server/kw/news.py`, `server/kw/news_more.py` |
| A-API-05 | `hotspots.csv` materializes the full export in memory (9.5 MB for one month; ~100 MB possible) | Stream chunks from the DuckDB cursor | `server/kw/tools.py`, `server/kw/api.py` |
| A-API-06 | Custom-area builds are unbounded in queue, count, and disk | Cap pending builds/custom areas/cache bytes and return 429 | `server/kw/tools.py`, `server/kw/api.py` |
| A-API-07 | The agent can spend 240 s in an API whose deployment budget is 60 s | Enforce a wall-clock budget and retain deterministic fallback | `server/kw/agent.py` |
| A-API-08 | Public MCP exposes build/email/delete tools | Public MCP is read-only by default; trusted local MCP retains writes | `server/kw/mcp_server.py`, `api/index.py`, `Dockerfile` |
| A-FE-01 | MapLibre is in the initial bundle although the landing page does not use it | Lazy-load the Explorer map and move shared map config out of `Map.tsx` | `web/src/App.tsx`, `web/src/Map.tsx`, new `web/src/mapConfig.ts` |
| A-FE-02 | The landing loader waits for all ~7.4 MB of 3D assets | Hero readiness must not wait for Terra/Suomi models; load them progressively | `web/src/pages/scene.ts` |
| A-FE-03 | A custom area opened on the full Cases page silently switches to the first preset | Resolve the requested area against all regions | `web/src/pages/CasesPage.tsx`, `web/src/pages/shared.tsx` |
| A-FE-04 | API failures are shown as “no cases” or perpetual loading | Preserve and render the actual error separately from an empty success | `web/src/casebook.tsx`, `web/src/CasesPanel.tsx`, `web/src/pages/CasesPage.tsx`, `web/src/pages/Home.tsx` |
| A-FE-05 | Calendar year filtering can leave the keyboard grid with no tab stop | Keep the roving tab stop inside the visible range | `web/src/Record.tsx` |
| A-FE-06 | The weekly SVG grid exposes no active period/value to assistive technology | Add an accessible active-cell summary and proper cell semantics | `web/src/Record.tsx` |
| A-FE-07 | The map sorts 100,720 grid values with a comparator sort during render | Use a numeric `Float64Array` sort | `web/src/Map.tsx` |
| A-FE-08 | Map popup DOM is recreated on every pointer move; the outlook pulse invalidates style at ~25 FPS; visibility toggles rebuild all data | Update popup content only when changed, gate/throttle pulse, separate visibility from data effects | `web/src/Map.tsx` |
| A-FE-09 | Saved alerts poll forever even after they are ready | Poll only while missing/running; expose manual refresh | `web/src/pages/Warning.tsx` |
| A-SCI-01 | The first ISO week is a five-day stub counted as a complete week | Mark it partial or omit it; never baseline it as complete | `server/kw/build.py`, `server/kw/science.py` |
| A-SCI-02 | Per-cell estimates use cell-local weights, so map cells and calendar totals can differ by −50%/+100% | Use the area-level sensor weights for cells so the grid reconciles with the total | `server/kw/build.py`, `server/kw/science.py` |
| A-SCI-03 | `seasonal_mann_kendall` returns a pooled pairwise Sen slope while documenting a seasonal Sen slope | Return the median of per-season Sen slopes; retain the pooled value separately for continuity | `server/kw/science.py` |
| A-SCI-04 | The “uncalibrated” baseline still carries calibration variance | Set calibration variance to zero for the identity estimator | `server/kw/build.py` |
| A-SCI-05 | The 2023 MODIS exclusion is the largest level change but has no transition/placebo test | Publish the acquisition-time/archive transition with the same step/placebo framework | `server/kw/build.py` |
| A-SCI-06 | The MODIS time shift is described as physical orbit drift although Terra moves oppositely and VIIRS does not move | Rename the interpretation to an archive/reported acquisition-time shift while retaining compatibility keys | `server/kw/science.py`, `server/kw/build.py`, data metadata, UI |
| A-SCI-07 | NRT rows have no FIRMS `type`; recent “vegetation” contains unclassified heat anomalies by construction | Publish the unclassified NRT share and disclose it in the estimand/method/UI | `server/kw/build.py`, `server/kw/tools.py`, `web/src/api.ts`, `web/src/Record.tsx` |
| A-SCI-08 | Chain-closure diagnosis does not separate estimator composition bias from data/window drift | Publish composed-pooled and composition-bias diagnostics; do not silently rescale the chain | `server/kw/build.py` |
| A-SCI-09 | Published outputs depend on mutable, uncommitted raw caches | Add per-area input fingerprints (file hashes/count/date range) to provenance | `server/kw/build.py` |
| A-SCI-10 | The Terra→Aqua bridge, confidence asymmetry, interval coverage, static-mask time invariance, and unverified global-path claim are incompletely disclosed | Add exact limitations without changing the headline result | `server/kw/build.py`, `web/src/pages/Method.tsx`, `README.md` |

## Bucket B — major design work included in this implementation

| ID | Design decision | Trade-off / guardrail |
|---|---|---|
| B-VAL-01 | Add an independent NASA burned-area check using MCD64A1 C6.1 COGs accessed through the public Planetary Computer STAC/catalog | It validates correlation/detection density, not fire identity; small-fire regions may correlate poorly. A failed access gate must stop the script rather than fabricate a result. |
| B-VAL-02 | Add the APAD Bangladesh operating-kiln inventory as an independent static-source cross-check and, where reproducible, as a second static signal for Dhaka | The inventory is not FIRMS truth. Keep FIRMS-typed and inventory-linked sources distinguishable; do not report a circular precision number as validation. |
| B-SEC-01 | Public HTTP MCP exposes only read tools; full writes remain available to trusted local/stdio deployments | Document the trusted-write opt-in and remote tool count. Never infer that an exposed token authorizes deletion. |
| B-SCI-01 | Use area-level sensor weights for map-cell estimates so each cell contributes consistently to the area total | Requires rebuilding all nine regions and re-running the reconciliation check. |
| B-SCI-02 | Report the Aqua-scale estimate, VIIRS-native series, and sensor-specific FRP side by side | Do not introduce a new black-box harmonizer. |
| B-AUDIT-01 | Ship a judge-rerunnable audit command that checks data integrity, calibration-table parity, coverage reproduction, and published outputs | Use existing stdlib/pytest-style scripts; no new framework/dependency. |

## Bucket B — explicitly deferred with reasons

| ID | Deferred item | Why it is not safe to fake or rush now |
|---|---|---|
| B-SCI-03 | VZA-stratified calibration | Requires reconstructing scan geometry and stratified overlaps; a rushed implementation can change every published value without a clean hold-out. The limitation will be explicit and the exact algorithm documented in the research report. |
| B-SCI-04 | Regional cloud-free observation denominator | FIRMS location files do not carry valid-pixel/cloud masks. It requires Level-2 swath/fire-mask products and a new denominator estimand. Global observing days will not be relabeled as cloud-free coverage. |
| B-SCI-05 | Nested selection among seasonal-EB, pooled, and identity estimators | Selecting the winner on the published hold-out would leak the test set. A nested temporal/geographic validation design is required before changing the estimator. |
| B-SCI-06 | NASA official Static Thermal Anomalies mask | The official mask is a separate 400 m product plus industrial inventories. Our APAD/FIRMS signals will remain labeled as proxies, not as NASA’s official STA layer. |
| B-DATA-01 | New 7+ GB harmonized global release | The current any-area builder and query-in-place architecture is the differentiator; committing a huge duplicate release increases operational risk and repository weight. A versioned audit/release bundle is the safer first step. |
| B-UX-01 | Bangla-first UI and named field pilot | Translations require native review; a pilot requires a real local operator. Shipping machine translations or invented outcomes would be less honest than leaving a clearly marked next step. |
| B-UX-02 | Visual-theme/navigation redesign | The existing UI is coherent and the audits found no theme-level defect. Changes are limited to evidence visibility, errors, accessibility, and performance. |

---

# 2. Implementation plan

## Task 1 — Scientific contract and first-period correctness

**Files:**
- Modify: `server/kw/science.py`
- Modify: `server/kw/build.py`
- Test: `server/tests/test_science.py`, `server/tests/test_build_rules.py`

**Interfaces:**
- `science.seasonal_mann_kendall(seasons)` returns `sen_per_year` (seasonal median) and `sen_per_year_pooled` (former value).
- `science.combine_details(estimates)` returns `(value, variance, normalized_weights)`; `science.combine` delegates to it without changing its public return shape.
- Build output gains `monthly.nrt_unclassified_share: Num[]` and provenance/method fields listed in Task 3.

- [x] Write failing tests proving a five-day first ISO week is partial/excluded and that seasonal Sen slope is the median of seasonal slopes.
- [x] Run `python server/tests/test_science.py` and `python server/tests/test_build_rules.py`; confirm the new assertions fail for the intended reasons.
- [x] Implement the smallest changes that make those tests pass.
- [x] Add a regression test for the identity estimator carrying zero calibration variance.
- [x] Run both scripts green.

## Task 2 — Exact map-to-area reconciliation

**Files:**
- Modify: `server/kw/build.py`, `server/kw/science.py`
- Test: `server/tests/test_build_rules.py`

- [x] Write a synthetic test where two sensors observe an area and one sees zero in one cell; prove the current cell-local inverse-variance rule does not sum to the area estimate.
- [x] Implement area-level normalized weights in `_grid`; each cell estimate is the same weighted sum used by the area estimate.
- [x] Add a regression test proving monthly cell sums equal the calendar value within floating-point tolerance for the synthetic case.
- [x] Rebuild one area in a temporary location and compare cell/calendar sums before accepting the implementation.
- [x] Run the complete Python script suite.

## Task 3 — Diagnostics, provenance, and honest model scope

**Files:**
- Modify: `server/kw/build.py`, `server/kw/tools.py`
- Modify data only through the rebuild: `data/regions/*/*.json`, `data/regions/calibration_table.csv`
- Test: `server/tests/test_build_rules.py`, `server/tests/test_data_integrity.py`

- [x] Add tests for the acquisition-time transition entry, chain-composition diagnostic fields, NRT-unclassified share, and input fingerprint shape.
- [x] Implement `steps["MODIS_TIME_SHIFT"]` without treating it as a sensor launch; update the step/placebo calculation and UI contract.
- [x] Rename user-facing “orbit drift” language to “MODIS reported acquisition-time/archive shift”; keep old JSON keys only where required for backward compatibility.
- [x] Publish `composition_bias_pct` and `composed_pooled` in closure diagnostics without changing chained point estimates.
- [x] Publish `nrt_unclassified_share` and state that the vegetation series includes untyped NRT heat anomalies outside the static mask.
- [x] Add SHA-256 fingerprints for the input parquet files and `sensor_days.parquet` to `meta.provenance`.
- [x] Update `meta.estimand` to say “calibrated Aqua-scale estimate,” explicitly identify the Terra-only 2000–2002 segment, and keep the VIIRS-native/raw alternatives.
- [x] Disclose the asymmetric confidence filters, interval out-of-sample coverage, time-invariant static mask, and unverified global-path comparison.
- [x] Run the complete Python script suite.

## Task 4 — Backend reliability and public-surface safety

**Files:**
- Modify: `server/kw/api.py`, `server/kw/alerts.py`, `server/kw/regions.py`, `server/kw/tools.py`, `server/kw/news.py`, `server/kw/news_more.py`, `server/kw/agent.py`, `server/kw/mcp_server.py`
- Modify: `api/index.py`, `Dockerfile`, `requirements.txt`, `server/requirements.txt`; create `.dockerignore`
- Test: `server/tests/test_api.py`, `server/tests/test_alerts.py`, new/updated `server/tests/test_build_rules.py` only if no other owner touches those files

- [x] Add HTTP tests: empty alert body is 400; build cap is 429; missing raw cache is an explicit 503; public MCP tool list excludes writes; trusted MCP includes writes.
- [x] Implement atomic news caching and a short negative-cache marker for failed upstreams.
- [x] Parallelize independent latest-news sources and per-language timeline requests; preserve source order and error reporting.
- [x] Add gzip middleware and stream hotspot CSV chunks.
- [x] Bound queued builds, distinct custom areas, and cache bytes; expose a stable status/error message.
- [x] Enforce the agent wall-clock budget and preserve deterministic fallback.
- [x] Make the public MCP read-only by default through `KW_PUBLIC_MCP=1`; trusted local MCP keeps all of them (35 at the time of writing, 38 after the casebook work landed on main).
- [x] Validate chart month, agent history, alert name, and outlook input at their trust boundaries.
- [x] Add `.dockerignore`, pin the tested dependency versions, and ensure the image does not copy the local virtualenv.
- [x] Run all six Python test scripts independently and confirm exit code 0.

## Task 5 — Frontend performance, accessibility, and truthful error states

**Files:**
- Modify/create: `web/src/App.tsx`, `web/src/Map.tsx`, new `web/src/mapConfig.ts`, `web/src/Record.tsx`, `web/src/casebook.tsx`, `web/src/CasesPanel.tsx`, `web/src/pages/CasesPage.tsx`, `web/src/pages/Home.tsx`, `web/src/pages/Warning.tsx`, `web/src/pages/shared.tsx`, `web/src/pages/scene.ts`, `web/src/api.ts`

- [x] Capture a failing pre-change bundle check: the entry chunk contains the MapLibre license marker and the landing manager waits for all three GLBs.
- [x] Move map constants/types to `mapConfig.ts`; lazy-load `Map.tsx` behind `Suspense`; verify direct `#pg=explore` still resolves.
- [x] Separate hero and satellite loading managers; show a graceful model placeholder until later beats’ assets arrive.
- [x] Add the science metadata types and render acquisition-time/NRT/closure diagnostics from data, never hard-coded results.
- [x] Preserve API errors in the Cases UI and Home console; distinguish errors from successful empty responses.
- [x] Fix custom-area Cases selection.
- [x] Fix calendar tab-stop behavior and add weekly active-cell accessibility.
- [x] Replace the grid comparator sort with a `Float64Array` sort.
- [x] Avoid popup recreation, gate/throttle the pulse, and separate layer visibility from source-data effects.
- [x] Gate saved-alert polling by status.
- [x] Run `npm run check` and `npm run build`; inspect the manifest/build output to confirm MapLibre is no longer statically imported by the entry chunk.
- [x] Run a local browser pass at desktop and 390 px: home, method, explorer, custom Cases error path, Week calendar, and alert page; assert zero console errors.

## Task 6 — Independent validation integrations

**Files:**
- Create: `scripts/validation/kilns.py`, `scripts/validation/burned_area.py`
- Create: `data/validation/kilns_dhaka.json`, `data/validation/burned_area.json`
- Create: `data/static_sources/dhaka-kilns-kilns.csv` and attribution metadata
- Modify: `server/kw/build.py` only for the optional APAD static-source signal
- Modify: `web/src/pages/Bangladesh.tsx`, `web/src/pages/Method.tsx`, `web/src/api.ts`, `server/kw/api.py`, `vercel.json`, `Dockerfile`
- Test: focused validation scripts and `server/tests/test_data_integrity.py`

- [x] Implement the APAD downloader with a fixed public URL, licence, retrieval timestamp, SHA-256, bbox filter, and fail-closed behavior.
- [x] Compute inventory/FIRMS overlap at 0.5/1/2 km and random baselines; report null/negative results honestly.
- [ ] Add the APAD inventory as a separate static-source signal for Dhaka, preserving FIRMS-typed versus inventory-linked provenance. — **not done as written; see Deviation 1 below**: the cross-check shows the cells do not land on mapped kilns, so adding the inventory as a second static signal would have invented agreement that the data does not show.
- [x] Rebuild Dhaka and verify the change is explainable in the static/vegetation totals and Method page.
- [x] Implement the MCD64A1 C6.1 reader through public STAC/COG URLs using `uv run --with rasterio`; select intersecting tiles, read only AOI windows, and sum `Burn_Date > 0` pixels.
- [x] Compare monthly harmonized/raw hotspot density with burned area for the seven vegetation-dominated preset areas; publish Spearman and the 2012 step with the known limitations.
- [x] If the MCD64 access or decoding gate fails, stop that validation, report the exact blocker, and do not fabricate or silently omit a result in the UI.
- [x] Make validation JSON available in local, Docker, and Vercel deployments with attribution.

## Task 7 — Rebuild, documentation, and submission narrative

**Files:**
- Regenerate: `data/regions/**`, `data/regions/calibration_table.csv`, `data/regions/index.json`
- Modify: `README.md`, `docs/demo/SUBMISSION.md`, `docs/demo/DECK.md`, `docs/demo/VIDEO_SCRIPT.md`, `CLAUDE.md`, `web/src/pages/Method.tsx`, `web/src/pages/Bangladesh.tsx`

- [x] Rebuild all nine presets from the pinned cache and verify only intended fields/values change.
- [x] Run the transfer-validation pass and regenerate the calibration table.
- [x] Update the README results from generated JSON; remove stale manual numbers.
- [x] Correct the MCP badge/count and distinguish public read-only tools from trusted local tools.
- [x] Replace “orbit drift” with the measured archive/acquisition-time interpretation.
- [x] State that the Aqua-scale value is a calibrated estimate and that recent NRT vegetation includes unclassified heat anomalies.
- [x] Add the MCD64A1/APAD validation only if their scripts completed successfully; otherwise preserve an explicit “not completed” limitation.
- [x] Replace the prior-work disclosure placeholder with the official pre-start rule, a dated work timeline, and a clear request for written GO-team guidance. Do not claim disclosure makes the project eligible.
- [x] Make one repository canonical in README links and mark other public repositories as mirrors only if their actual relationship is known.

## Task 8 — Full verification, review, commit, push, and pull request

- [x] Run every Python script test (`test_science.py`, `test_api.py`, `test_alerts.py`, `test_build_rules.py`, `test_cases.py`, `test_data_integrity.py`) and record exit status/output.
- [x] Run `cd web && npm run check && npm run build`.
- [x] Run the focused validation scripts and data-integrity checks.
- [x] Run the local API + web app and exercise the changed flows in a real browser with console inspection.
- [x] Inspect `git diff --check`, `git status`, and the complete diff for secrets, generated caches, temporary files, and unrelated changes.
- [ ] Dispatch a fresh code-reviewer on the whole branch against `origin/main`; fix every Critical/Important finding with a failing regression test first.
- [ ] Run the full verification suite again after fixes.
- [ ] Commit once with a precise subject and body.
- [ ] Push `feature/nasa-space-apps-2026-submission` to `origin`.
- [ ] Create a pull request to `main` with the award mapping, verification evidence, research links, known limitations, and the eligibility blocker prominently stated.
- [ ] Do not merge the pull request; leave that decision to the team.

---

# 3. Verification matrix

| Area | Command / check | Expected |
|---|---|---|
| Science | `python server/tests/test_science.py` | All assertions pass, exit 0 |
| Build rules | `python server/tests/test_build_rules.py` | All assertions pass, exit 0 |
| API | `python server/tests/test_api.py` | All HTTP assertions pass, exit 0 |
| Alerts | `python server/tests/test_alerts.py` | All assertions pass, exit 0 |
| Cases | `python server/tests/test_cases.py` | All assertions pass, exit 0 |
| Data integrity | `python server/tests/test_data_integrity.py` | All assertions pass, exit 0 |
| TypeScript | `cd web && npm run check` | Exit 0 |
| Production web | `cd web && npm run build` | Exit 0; MapLibre absent from the entry chunk’s static imports |
| Data rebuild | `cd server && python -m kw.build` | Nine presets built; no unexpected class/array shape changes |
| Transfer validation | `cd server && python -m kw.build --transfer-only` | Nine area hold-outs present |
| APAD validation | `python scripts/validation/kilns.py` | Deterministic JSON; source hash/licence recorded |
| Burned area | `uv run --with rasterio python scripts/validation/burned_area.py` | Deterministic JSON or a documented fail-closed gate error |
| Browser | Local API + Vite, Playwright | Changed routes work; no console errors; keyboard paths work |
| Diff hygiene | `git diff --check && git status --short` | No whitespace errors; only intended files |

# 4. Risks and rollback

- **Scientific values change:** tasks 1–3 and the APAD integration alter published outputs. Keep the original branch/base commit, compare every area, and roll back the scientific patch independently from the reliability/UI patch if reconciliation or hold-outs regress.
- **Map reconciliation changes semantics:** area-level weights are the defensible choice, but verify the total and the cell layer before merge.
- **APAD inventory is not truth:** label it as an independent asset cross-check, not field validation; show overlap and null/negative results.
- **MCD64 access may fail:** fail closed and retain the limitation; do not use a different dataset without recording the decision.
- **Public MCP becomes read-only:** trusted local/stdio workflows retain writes; document the change rather than silently reducing functionality.
- **Data rebuild may contact the mutable mirror:** fingerprints and method metadata make the source snapshot explicit.
- **Eligibility remains unresolved:** implementation success does not imply submission eligibility.

# 5. Completion ledger

Update this section as work completes; every task needs command evidence, not an inference.

- [x] Research and benchmark report written and source-checked. — `RESEARCH_AND_BENCHMARKS.md` (567 lines): competitor
  rubrics, NASA science sources, the GO-Team eligibility rule, and the audit that produced the triage table above.
- [x] Task 1 scientific contract/first-period fix complete. — `python server/tests/test_science.py` and
  `python server/tests/test_build_rules.py` exit 0: first ISO week partial, seasonal Sen slope = median of seasonal
  slopes, identity estimator without calibration variance, `combine_details` weights.
- [x] Task 2 map-to-area reconciliation complete. — Cells now use the area's sensor weights; all nine areas rebuilt and
  the map cells sum to the calendar value to within 0.007 hotspots in every month of every area
  (`server/tests/test_data_integrity.py::test_map_cells_reconcile_with_the_calendar`). Grid cell order is now canonical
  (north to south, west to east) so the exposure layer stays aligned across rebuilds.
- [x] Task 3 diagnostics/provenance/model scope complete. — `meta.steps.MODIS_TIME_SHIFT`, `closure[*].composed_pooled`
  and `composition_bias_pct`, `monthly.nrt_unclassified_share`, `provenance.input_fingerprint` (SHA-256 of every cached
  parquet and of `sensor_days.parquet`), and the rewritten estimand/method text.
- [x] Task 4 backend reliability/security complete. — All six Python test scripts exit 0; the HTTP MCP is read-only
  (`KW_PUBLIC_MCP=1`, 34 of the 39 tools) and the trusted local server keeps all 39.
- [x] Task 5 frontend performance/accessibility/error states complete. — `npm run check` and `npm run build` exit 0;
  measured against `origin/main` in a separate worktree, the entry chunk fell from 1,554,240 bytes raw / 443,200 gzip
  to 463,890 / 145,870; MapLibre is in its own lazy chunk (1,055,255 bytes).
- [x] Task 6 independent validations complete. — `scripts/validation/burned_area.py` (NASA MCD64A1 C6.1 through the
  public Planetary Computer catalogue) and `scripts/validation/kilns.py` (APAD Bangladesh brick-kiln inventory) both
  run, fail closed and publish their results with sources, hashes and limitations. **Deviation from the plan, with
  reason:** the APAD inventory was *not* added as a second static signal for Dhaka, because the cross-check shows the
  published persistent-heat cells land on mapped kilns less often than randomly placed cells of the same number
  (2 of 109 cells at 1 km against a random baseline of 8.3%). The honest outcome is a relabelling, not a second signal:
  the class is published as a persistent-heat proxy and the negative result is published with it.
- [x] Task 7 rebuild and submission documentation complete. — All nine areas rebuilt from the pinned cache; the
  transfer validation, `index.json`, `calibration_table.csv`, the README figures and the README results table were
  regenerated from the built files; README, `docs/demo/SUBMISSION.md`, `DECK.md` and `VIDEO_SCRIPT.md` now carry the
  measured archive-shift interpretation, the 34/39 tool split, the validation results and the prior-work disclosure.
- [ ] Task 8 full verification, review, commit, push, and pull request complete.

## Deviations from the plan, and why

1. **The APAD inventory became a cross-check, not a second static signal.** The plan assumed the inventory would
   corroborate the persistent-heat cells. It does not, so the class is relabelled and the negative result is published.
   Inventing a signal that the data does not support would have been the worse outcome.
2. **Published band values now carry four decimals instead of two.** The map cells reconcile with the calendar value
   only if both are rounded the same way; with two decimals, a month with a fraction of a hotspot could differ by 27%.
   Verified against the previous build: the raw series is identical and every harmonized value moves by at most one
   2-decimal rounding step, in all nine areas.
3. **The 2012 step test uses the median across areas.** One baseline year (Alberta 2011) is an exceptional fire year,
   so a per-area ratio is not a robust summary.
4. **Public MCP is read-only over HTTP** (34 of 39 tools); the five state-changing tools stay in a trusted
   local or stdio server. The README, the Connect page and the deck now say so.
5. **VZA stratification, a regional cloud-free denominator, nested estimator selection and the official NASA STA
   mask stay deferred**, exactly as the plan says.
6. **`main`'s new "Is fire near you?" component is loaded lazily here.** `web/src/PlaceRisk.tsx` imports MapLibre
   directly and the Cases page is in the entry graph, so merging `main` put the map library back into the entry chunk
   (1,544,156 bytes, barely under `main`'s 1,554,240). It is now a lazy import like the other two map views, so the
   entry chunk stays at 463,890 bytes.

# 6. Deliberate non-goals

- No replacement harmonizer, black-box model, hardware system, or broad UI redesign.
- No burned-area value is presented as a fire perimeter.
- No unverified field pilot, operator outcome, or Bangla translation is invented.
- No competitor headline metric is adopted without independent verification.
- No public deployment is allowed to expose destructive or email-sending tools without an explicit trusted opt-in.
