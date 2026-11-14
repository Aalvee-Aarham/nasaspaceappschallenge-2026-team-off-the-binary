# Plan 012: Structure the site so each award's evidence is one click away

> **Executor instructions**: Follow this plan step by step. Run every verification. Steps marked **[HUMAN]** need a
> Bangla-speaking team member. If anything in "STOP conditions" occurs, stop and report. When done, update the status
> row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- web/src/pages/shared.tsx web/src/App.tsx web/src/pages/Method.tsx web/src/pages/Home.tsx web/src/pages/Connect.tsx`
> Plan 009 adds `"after"` to `Page`/`PAGES` and a render line in `App.tsx` — expected. Other mismatches: STOP.

## Status

- **Priority**: P1 (presentation is a judging criterion)
- **Effort**: M
- **Risk**: LOW–MED — touches navigation; old links must keep working
- **Depends on**: plan 009 (After MODIS page). Uses results from 004, 005, 010, 011 when present; renders without them.
- **Category**: direction (UX / information architecture)
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

Space Apps judges score impact, creativity, validity, relevance and presentation, and award categories such as Best
Use of Data, Best Use of Technology, Best Use of Science, Galactic Impact, and (at local events) Local Impact. Check
the 2026 Judging & Awards Guide for the exact names. Judges spend minutes per project. Today the top bar has 9
equal entries (Home, Explorer, Early warning, News, Download, Create, Method, Claude MCP, n8n), so the strongest
evidence is buried. After this plan: a 6-entry nav ordered by the story, a "3-minute judge tour" on the home page,
a **Proof** scorecard comparing all nine areas, and a **Bangladesh** page for local impact. Every old `#pg=` link
still opens its page.

## Current state

- `web/src/pages/shared.tsx:5-9` — `Page` union and `PAGES` (the nav list; also used to validate `#pg=` in `App.tsx:20`:
  `const PAGE_IDS = PAGES.map(([k]) => k) as string[];` and `PAGE_IDS.includes(h0.pg)`).
- `web/src/App.tsx:208-216` renders the nav from `PAGES`; `App.tsx:236-246` renders each page by `pg ===`.
- `web/src/pages/Method.tsx` — page "Methodology": steps, satellite figure, per-area evidence (`<Evidence r={region} cls="veg" />`), limitations, credits.
- `web/src/pages/Connect.tsx` exports `Mcp` and `N8n`; `web/src/pages/Data.tsx` exports `Download`, `Create`; `web/src/pages/News.tsx` default `News`.
- `web/src/pages/Home.tsx` (lazy-loaded 3D landing, `export default function Home({ regions, go, openRegion }: PageProps)`),
  sections: `h3d-story` (scroll story, line ~272), then `h3d-flat built` (~466), `h3d-flat heritage` (~476), `h3d-flat wall` (~486).
- `web/src/api.ts`: `api.meta(id)` loads one area's `meta.json`; `RegionItem` has `id`, `name`, `preset`.
- Per-area result fields for the scorecard (all in `meta.json`): `steps[sensor].raw_all_sensors_excess` / `harmonized_excess`,
  `placebo.excess_p05/p95`, `denial.modis_ends_2016.uncalibrated.bias_pct` / `ours_seasonal_eb.bias_pct` / `.spearman` /
  `.interval_coverage_raw` / `.interval_coverage_out_of_sample` (plan 004), `closure.veg_det_D[0].mismatch_pct`,
  `transfer_validation.transferred_from_other_regions.bias_pct`, `warning_backtest.by_day["15"].elevated.pss` (plan 005).
  Optional files: `/data/validation/burned_area.json` (plan 010), `/data/validation/kilns_dhaka.json` (plan 011).
- `data/regions/dhaka-kilns/monthly.json` → `classes.static.hotspots.v` and `classes.veg.hotspots.v` per month.
- Project rules: every number from the pipeline JSON; colour-blind-safe; keyboard reachable; "detections are not
  fires"; never "forecast"; missing news ≠ absence.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Typecheck | `cd web && npx tsc --noEmit` | exit 0 |
| Build | `cd web && npm run build` | exit 0 |
| Run | API `cd server && uvicorn kw.api:app --port 8000`; web `cd web && npm run dev` | localhost:5173 |

## Suggested executor toolkit

- If available: `impeccable` or `emil-design-eng` skill for the tour strip and scorecard polish; `dataviz` for the
  scorecard's colour coding (pass/warn); `mobile-native` for a 390 px check. Match existing `styles.css` tokens.

## Scope

**In scope**: `web/src/pages/shared.tsx`, `web/src/App.tsx`, `web/src/pages/Method.tsx` (add scorecard section at top),
`web/src/pages/Proof.tsx` (create: the scorecard component), `web/src/pages/Bangladesh.tsx` (create),
`web/src/pages/Connect.tsx` (add links to Download, Create, n8n, News), `web/src/pages/Home.tsx` (tour + award tiles),
`web/src/styles.css` (append), `vercel.json` (copy `data/validation` if it exists).
**Out of scope**: server code; the 3D scene (`scene.ts`); removing any page component (hidden pages stay routable).

## Git workflow

Branch `advisor/012-award-structure`; one commit per step (e.g. `Reorder navigation around the story`); no push.

## Steps

### Step 1: Nav of six, every page still routable

In `shared.tsx`:
- Add `"bangladesh"` to `Page`.
- Keep a full list for routing and a short list for the nav:
  ```ts
  export const ALL_PAGES: readonly Page[] = ["home", "explore", "warning", "after", "method", "bangladesh", "mcp", "n8n", "news", "download", "create"];
  export const PAGES: readonly (readonly [Page, string])[] = [
    ["explore", "Explorer"], ["warning", "Early warning"], ["after", "After MODIS"],
    ["method", "Proof"], ["bangladesh", "Bangladesh"], ["mcp", "Connect"],
  ];
  ```
- In `App.tsx` change `const PAGE_IDS = PAGES.map(([k]) => k) as string[];` to `const PAGE_IDS = ALL_PAGES as readonly string[];`
  (import `ALL_PAGES`), and add `{pg === "bangladesh" && <Bangladesh {...pageProps} />}`.

**Verify**: `cd web && npx tsc --noEmit` → only the missing `./pages/Bangladesh` import error (step 4 creates it).

### Step 2: Connect page links to the pages that left the nav

At the top of the `Mcp` component in `Connect.tsx`, add a row of buttons using `go`:
"Download the data" → `go("download")`, "Build your own area" → `go("create")`, "Automate with n8n" → `go("n8n")`,
"News beside the data" → `go("news")`. Use the existing `btn ghost` class.

### Step 3: Proof scorecard (`web/src/pages/Proof.tsx`)

Export `function Scorecard({ regions }: { regions: RegionItem[] })` that loads `api.meta(id)` for every preset
(`regions.filter((r) => r.preset)`; `Promise.all`; show `<div className="skeleton" />` while loading) and renders one
accessible `<table>` (with `<caption>`), one row per area, columns:
1. Raw jump at 2012 (× vs Aqua) — `steps.VIIRS_SNPP.raw_all_sensors_excess`
2. Harmonized jump at 2012 — `steps.VIIRS_SNPP.harmonized_excess`, cell marked "within no-change range" when inside `[placebo.excess_p05, placebo.excess_p95]`
3. Error if MODIS had ended in 2016: uncalibrated → Kiln Watch (`denial…uncalibrated.bias_pct` → `ours_seasonal_eb.bias_pct`)
4. Interval coverage: unwidened / out-of-sample (show "–" when the field is missing)
5. Chain closure (`closure.veg_det_D[0].mismatch_pct`)
6. Borrowed calibration error (`transfer_validation.transferred_from_other_regions.bias_pct`)
7. Early-warning skill, day 15 (`warning_backtest.by_day["15"].elevated.pss`, or "not scored")
If `/data/validation/burned_area.json` loads (fetch with `.catch(() => null)`), add "Burned-area check: 2012 step raw → harmonized".
Under the table: one paragraph on how to read it, and a "Where it falls short" list built from the data (e.g. any
area whose harmonized jump is outside its no-change range). Do not type the numbers anywhere.

In `Method.tsx`, change the `PageHead` title to "Proof" and insert `<section><h2>Nine areas, one scorecard</h2><Scorecard regions={regions} /></section>` as the first section.

**Verify**: `cd web && npx tsc --noEmit` → only the Bangladesh error remains.

### Step 4: Bangladesh page (`web/src/pages/Bangladesh.tsx`)

Default export using `useRegion("dhaka-kilns")`:
- Lead: why Dhaka (raw counts jump `steps.VIIRS_SNPP.raw_all_sensors_excess`×; kilns are small and steady; VIIRS sees them, MODIS mostly cannot).
- Chart (reuse `LineChart` exported by plan 009, or the `Calendar` component pattern): median per calendar month of
  `classes.static.hotspots.v` (kilns, flares, industry) vs `classes.veg.hotspots.v` (vegetation) → kiln season vs crop-fire season.
- Kiln check numbers from `/data/validation/kilns_dhaka.json` if present (precision, recall, lift at 1 km, source); else the existing "likely kilns" caveat.
- "What you can do with it": open the Dhaka calendar (`openRegion("dhaka-kilns")`), set an alert (`go("warning")`), download the CSV (`go("download")`).
- Language toggle EN / বাংলা for this page's text only: keep strings in one object `{ en: {...}, bn: {...} }`;
  set `lang="bn"` on the container when Bangla is active. **[HUMAN]** A Bangla-speaking team member writes or reviews
  every `bn` string; the executor leaves English text with a `// TODO(bn)` marker if no reviewed translation is provided.

**Verify**: `cd web && npx tsc --noEmit` → exit 0; `npm run build` → exit 0

### Step 5: Home — judge tour and award tiles

In `Home.tsx`, directly after the `h3d-story` section, add a `<section className="h3d-flat tour">`:
- Title "See it in three minutes", then an ordered list of 6 buttons, each one line:
  1. "The problem: raw counts jump in 2012" → `openRegion("punjab")` (opens Explorer on Punjab)
  2. "The proof: nine areas, one scorecard" → `go("method")`
  3. "After MODIS: switch satellites off" → `go("after")`
  4. "Early warning, and how often it was right" → `go("warning")`
  5. "Bangladesh: the brick-kiln belt" → `go("bangladesh")`
  6. "Ask it from Claude: 31-tool MCP server" → `go("mcp")`
- Then four tiles labelled with what they prove, not award names, so the page reads well to anyone: "A record that
  survives the end of MODIS" (→ after), "Every number tested" (→ method), "Built on NASA data, queried in place" (→ mcp),
  "Made for Bangladesh's kiln belt" (→ bangladesh).
Buttons must be real `<button>`s (keyboard), with visible focus styles (reuse `.btn`).

**Verify**: `cd web && npx tsc --noEmit && npm run build` → exit 0

### Step 6: Old links and phone width

Open each of `#pg=method`, `#pg=news`, `#pg=download`, `#pg=create`, `#pg=n8n`, `#pg=mcp`, `#pg=after`, `#pg=bangladesh`:
each opens its page. At 390 px width nothing scrolls sideways and the nav wraps or scrolls within itself.

## Test plan

- `tsc` and `vite build` after each step; step 6 manual route check; keyboard pass over the tour buttons and the scorecard table.

## Done criteria

- [ ] `cd web && npx tsc --noEmit` exits 0; `cd web && npm run build` exits 0
- [ ] Nav shows exactly: Explorer, Early warning, After MODIS, Proof, Bangladesh, Connect
- [ ] All 8 old/new `#pg=` links in step 6 open their page
- [ ] `grep -nE "[0-9]+\.[0-9]+%" web/src/pages/Proof.tsx web/src/pages/Bangladesh.tsx` finds no hard-coded result numbers
- [ ] **[HUMAN]** Bangla strings written or reviewed by a native speaker
- [ ] `docs/plans/README.md` row 012 updated

## STOP conditions

- `api.meta` for a preset fails (data missing — check plan 001's integrity test).
- Plan 009's page does not exist yet (do 009 first or drop "After MODIS" from the nav and tour, and report).

## Maintenance notes

- If the official 2026 award names differ, change only the tour/tile wording; the structure holds.
- Keep the nav at six entries; new features go inside pages, not into the top bar.
