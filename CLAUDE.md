# Kiln Watch — agent notes

NASA Space Apps 2026 "Harmonization of MODIS and VIIRS Hot Spots". One consistent 2000–present fire record per area.

## Token rule (always)
1. Before reading source files to answer a codebase question, read `graphify-out/GRAPH_REPORT.md` and query the graph
   (`/graphify query "<question>"`). Only open the files it points to.
2. After changing code, rebuild the graph: `graphify update .` (the post-commit hook also does this).
3. Keep durable decisions in memory, not in this file.

## Layout
- `server/kw/firms.py` — reads FIRMS detections from the public Portolan GeoParquet mirror (DuckDB, no key) → `data/cache/<area>/<year>.parquet`
- `server/kw/build.py` — calibration, stitching, validation, outputs `data/regions/<area>/{meta,monthly,weekly,grid,static}.json`
- `server/kw/science.py` — all statistics (stdlib only); tests in `server/tests/test_science.py`
- `server/kw/tools.py` — deterministic query functions shared by `api.py` (FastAPI), `mcp_server.py` (MCP) and `agent.py` (Gemini); downloads are `export_options/export_calendar/export_detections` (one column menu for the Explorer panel, `/api/regions/{id}/export` and MCP `export_data`)
- `server/kw/news.py` — NASA EONET + GDELT DOC (2017+) + optional ReliefWeb ; `news_more.py` adds Google News RSS, GDACS, worldwide feed, free-text place search
- `server/kw/outlook.py` — worldwide 0.5° 30-day outlook from the global aggregate (rule `science.outlook_cell`); Aqua MODIS before its measured drift onset, NOAA-20 on the Aqua scale after it and for the last 30 days (per-cell ratio, held-out error published in the file)
- `server/kw/alerts.py` — email (double opt-in, SMTP env) + n8n alerts; `feedback.py` — contact form → `data/feedback.jsonl`, mailed to `CONTACT_EMAILS` when SMTP is set; `personas.py` — Claude characters (MCP prompts, subagents); `charts.py` — analyst chart specs from pipeline data only
- `server/kw/cases.py` — the casebook: fire cases heard by witnesses (record cell+area, MODIS-vs-VIIRS cross-check, EONET, GDACS, press), verdicts, `data/regions/<area>/cases.json`; `python -m kw.cases [area]` rebuilds it from the committed files
- `scripts/build_exposure.py` — build-time only (needs `rasterio`): WorldPop 2020 + OSM hospitals/schools/roads + ESA WorldCover cropland on the 0.1° grid (`--add` adds schools and farmland to a built file) → `exposure.json`; context, never impact
- `scripts/build_burned.py` — build-time only (needs `earthengine-api`, `EE_PROJECT` in `.env`): MODIS MCD64A1 burn scar per case → `burned_area.json`, applied by `python -m kw.cases <area>`
- `scripts/build_kilns.py` — build-time only (Earth Engine + the raw FIRMS cache): Dhaka kiln inventory (deluair/bangladesh-brick-kilns, CC BY-NC), how little FIRMS sees of it, Black Marble night lights, Sentinel-1 radar contrast (one orbit, both seasons) → `kilns.json`. FIRMS cannot count kilns (measured: no better than random ground); never use it to find them
- `scripts/discussion_checks.py` — scan-angle and MODIS-vs-VIIRS single-sensor checks from the cache (nasa/spaceapps #1786) → `data/regions/discussion_checks.json`, shown on the Questions page
- `server/kw/mcp_server.py` — 40 tools, 4 prompts, resources; also mounted by the API at `/mcp`
- `web/src` — React + MapLibre UI (`App.tsx` shell + hash routing, `Map.tsx`, `Record.tsx` calendar/continuity/method, `Detail.tsx` cell inspector, `Timeline.tsx`, `Analyst.tsx` + `Chart.tsx`, `Loader.tsx` for every slow wait)
- `web/src/pages/` — one file per page: `Warning` (early warning), `News`, `Data` (Download + Create), `Method`, `Questions` (NASA discussion threads, other sources, our limits), `Contact` (feedback form), `Connect` (MCP + n8n); `shared.tsx` has the page list
- Early warning: rule in `science.warning_level`, assembly in `tools.early_warning`/`warnings`; keep it a climatological outlook, never a forecast
- "Is fire near you?" (any place on Earth, top of the Cases & exposure page, `web/src/PlaceRisk.tsx`): `tools.place_risk` behind `GET /api/place-risk` and MCP `check_place_fire_risk`; last 7 days live from the FIRMS mirror, fire months from `data/global/fire_season.parquet` (`python -m kw.globe season`, committed, shipped by Dockerfile and vercel.json), outlook, OpenStreetMap buildings via Overpass (slow: the page asks with `facilities=false` first); rule in `science.place_level`

## Commands
- Build presets: `cd server && python -m kw.firms && python -m kw.build`
- API: `cd server && uvicorn kw.api:app --port 8000` · Web: `cd web && npm run dev`
- Tests: `python server/tests/test_science.py` · Type check: `cd web && npx tsc --noEmit`

## Science guardrails (from the brief review — do not regress)
- Never present synthetic or hand-typed numbers as results; everything comes from the pipeline.
- Missing news ≠ evidence of absence; never label "silent ignition" or "artifact proven".
- Sensor availability is measured from data (`sensor_days`), never hard-coded end dates.
- Detections are not fires and not burned area.
- A witness that could not look (search failed, or the source does not reach back that far: GDELT 2017, GDACS 2021, MCD64A1 to its last month) is `unavailable[...]` with the reason, never "nothing found".
- Never call FIRMS persistent heat sources "kilns": only 6 of 109 in Dhaka sit on a mapped kiln.
- The place level is detections plus history, never a forecast or an official warning; a failed live check is `unknown`, never `low`.
