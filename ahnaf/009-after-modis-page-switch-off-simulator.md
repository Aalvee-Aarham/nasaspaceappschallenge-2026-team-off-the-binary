# Plan 009: An "After MODIS" page where judges switch satellites off and watch the record hold

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in "STOP conditions" occurs, stop and report. When
> done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- web/src/pages/shared.tsx web/src/App.tsx web/src/Record.tsx web/src/api.ts`
> Plan 012 also edits `PAGES` and the nav; if 012 already landed, add this page to its new structure (as the
> "After MODIS" entry it names) instead of step 2's list. Other mismatches: STOP.

## Status

- **Priority**: P1 (the strongest "Galactic / global impact" demo)
- **Effort**: M
- **Risk**: LOW — new page, reads existing JSON
- **Depends on**: plan 003 (adds `meta.aqua_overpass`); the page must still render if that field is missing
- **Category**: direction (feature)
- **Planned at**: commit `1e99c85`, 2026-11-13 (revised after the code-scan review: S4)

## Why this matters

NASA's MODIS satellites (Terra, Aqua) are drifting and shutting down, and FIRMS stopped producing Suomi-NPP data on
2 November 2026. Kiln Watch's best evidence that its record survives this is already computed: the
"MODIS-denial" test (pretend MODIS ended in 2016, rebuild 2017–2020 from VIIRS alone, compare with what Aqua really
saw), the "Suomi-NPP withheld" test (2024–2026 without S-NPP), the real S-NPP cut-over (weekly, around its last
day) and, after plan 003, Aqua's measured overpass-time drift. Today this sits in small charts inside the Method
panel. This plan gives it one page with buttons: switch a satellite off and watch raw counts jump while the
harmonized record stays on Aqua's real values. Judges can try it themselves in under a minute.

## Current state

- `web/src/pages/shared.tsx:5-9`:
  ```ts
  export type Page = "home" | "explore" | "warning" | "news" | "download" | "create" | "method" | "mcp" | "n8n";
  export const PAGES: readonly (readonly [Page, string])[] = [
    ["home", "Home"], ["explore", "Explorer"], ["warning", "Early warning"], ["news", "News"], ["download", "Download"],
    ["create", "Create"], ["method", "Method"], ["mcp", "Claude MCP"], ["n8n", "n8n"],
  ];
  ```
  Also exports `PageHead({kicker, title, lead})`, `AreaSelect({regions, value, onChange})`, `useRegion(id)` → `{region, err}`, `PageProps`.
- `web/src/App.tsx:236-246` renders pages: `{pg === "method" && <MethodPage {...pageProps} />}` etc. inside
  `<main className="page" ...><div className="page-in">`. Pages are imported at the top (`import MethodPage from "./pages/Method";`).
- `web/src/pages/Method.tsx` is the exemplar page: `PageHead`, `<section><h2>…</h2>…</section>`, an `AreaSelect`
  with `const id = rid || regions.find((r) => r.preset)?.id || regions[0]?.id || null; const { region, err } = useRegion(id);`.
- `web/src/Record.tsx:217-222` (not exported today):
  ```ts
  type Line = { name: string; color: string; vals: Num[]; dash?: string; wide?: boolean };
  function LineChart({ x, lines, band, logY, marks, label, name, yFmt = (v: number) => fmt(v) }: {
    x: string[]; lines: Line[]; band?: { lo: Num[]; hi: Num[]; color: string }; logY?: boolean; marks?: { at: number; color: string; text: string }[];
    label: string; name: string; yFmt?: (v: number) => string;
  }) {
  ```
  `Record.tsx:424` exports `Gantt({ sensors, through })` (satellite timeline). `SENSOR_COLOR` and `SHORT` come from `./api`.
- `web/src/api.ts` `Meta.denial` (exact shape):
  ```ts
  modis_ends_2016: { train; test; n; ours_seasonal_eb: Metric; baseline_single_ratio: Metric; uncalibrated: Metric; interval_scale: number;
    series?: { periods: string[]; aqua: Num[]; predicted: Num[]; lo: Num[]; hi: Num[] } };
  snpp_withheld: { window; n; inside_interval: Num; mean_abs_diff_pct: Num; series: { periods: string[]; all: Num[]; without_snpp: Num[] } } | null;
  snpp_cutover: { snpp_last_observed: string; periods: string[]; raw_all: number[]; harmonized: Num[]; lo: Num[]; hi: Num[]; partial: boolean[]; sensors: string[][] } | null;
  ```
  `Block` (`region.monthly`) has `periods`, `coverage[observer]`, `raw[observer].det`.
- After plan 003, `meta.aqua_overpass` = `{ years: {"2003": 13.6, …}, n: {...}, baseline_hour: number|null, onset: "YYYY-01"|null, rule: string }`.
- Design rules from the repo: colour-blind-safe palette (existing `SENSOR_COLOR`), every chart has a text label
  (`label` prop → aria), keyboard reachable buttons, plain short sentences, no forecasts, "detections are not fires".

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Install | `cd web && npm ci` | exit 0 |
| Typecheck | `cd web && npx tsc --noEmit` | exit 0 |
| Build | `cd web && npm run build` | exit 0 |
| Run | `cd server && uvicorn kw.api:app --port 8000` and `cd web && npm run dev` | http://localhost:5173/#pg=after |

## Suggested executor toolkit

- If available, use the `emil-design-eng` or `impeccable` skill for the toggle's look, and the `dataviz` skill for chart colours. Keep the existing visual language (dark theme, `styles.css` tokens).

## Scope

**In scope**: `web/src/pages/AfterModis.tsx` (create), `web/src/pages/shared.tsx` (`Page`, `PAGES`),
`web/src/App.tsx` (import + one render line), `web/src/Record.tsx` (add `export` to `LineChart` and `Line` only),
`web/src/api.ts` (`Meta.aqua_overpass` optional field), `web/src/styles.css` (a few classes, appended).
**Out of scope**: server code; any change to chart internals; the Method page.

## Git workflow

Branch `advisor/009-after-modis`; commits like `Add After MODIS page`; `graphify update .` if installed; no push.

## Steps

### Step 1: Export the chart and add the type

- `web/src/Record.tsx`: `export type Line = …` and `export function LineChart(…)`.
- `web/src/api.ts` `Meta`: add `aqua_overpass?: { years: Record<string, number>; n: Record<string, number>; baseline_hour: Num; onset: string | null; rule: string } | null;`

**Verify**: `cd web && npx tsc --noEmit` → exit 0

### Step 2: Register the page

`shared.tsx`: add `"after"` to `Page` and `["after", "After MODIS"]` to `PAGES` right after `["warning", …]`.
`App.tsx`: `import AfterModis from "./pages/AfterModis";` and `{pg === "after" && <AfterModis {...pageProps} />}` next to the Method line.

**Verify**: `cd web && npx tsc --noEmit` → error only about the missing module `./pages/AfterModis` (created next).

### Step 3: Build the page (`web/src/pages/AfterModis.tsx`)

Structure (follow `Method.tsx`):

1. `PageHead kicker="Continuity" title="After MODIS" lead="NASA's MODIS satellites are drifting and shutting down, and Suomi-NPP stopped in November 2026. Switch satellites off and see whether the record still holds."`
2. `AreaSelect` (default first preset).
3. **Section "Switch a satellite off"** — a two-button segmented control (`role="radiogroup"`, buttons with `aria-pressed`):
   - **"MODIS ends in 2016"** → `LineChart` over `denial.modis_ends_2016.series`: lines *What Aqua MODIS saw* (`aqua`, solid) and
     *Rebuilt from VIIRS alone* (`predicted`, dashed) with `band` from `lo`/`hi`; plus a third line *Raw VIIRS detections, not harmonized*
     computed from `region.monthly`: for each period in the series, `Σ raw[s].det[i] for s in VIIRS_SNPP, VIIRS_NOAA20` (use
     the index of the period in `monthly.periods`). Under the chart, three numbers from the metrics, each in one plain sentence:
     raw bias (`uncalibrated.bias_pct`), harmonized bias (`ours_seasonal_eb.bias_pct`), rank agreement (`ours_seasonal_eb.spearman`).
   - **"Suomi-NPP withheld"** (only if `snpp_withheld` is not null) → lines `all` and `without_snpp` over `series.periods`;
     sentence: "Without Suomi-NPP the record moves by {mean_abs_diff_pct}% on average." Do **not** show `inside_interval`:
     it is 1.0 in every area because the published interval is already widened by the rehearsal factor k, so it cannot
     fail and would read as proof (code-scan review, finding S4). If plan 004 has landed, add its out-of-sample
     coverage sentence here instead.
4. **Section "The real switch-off"** (only if `snpp_cutover`): weekly `raw_all` vs `harmonized` with band, mark at the S-NPP last day
   (copy the `marks` pattern used in `Record.tsx` line ~368: index of the first period ≥ the ISO week of `snpp_last_observed`).
5. **Section "Aqua is drifting"** (only if `meta.aqua_overpass?.years`): `LineChart` of local overpass hour by year
   (`yFmt={(v) => `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")}`}`), a mark at the onset year,
   and the sentence: "Aqua's afternoon pass has moved from {baseline} to {latest} local time. From {onset} the record uses VIIRS only, still on the Aqua 2002–2020 scale." If `meta.aqua_overpass.version_change` is set, add: "The MODIS archive also changed algorithm version ({version}) in {from}." Use `onset` (the earlier of the two), not `orbit_onset`, for the mark. Show `rule` in small muted text.
6. **Section "Which satellites, when"**: `<Gantt sensors={meta.sensors} through={meta.data_through} />`.
7. Footer caveat: "Detections are not fires and not burned area. These are tests on past years, not forecasts."

Every number on the page must come from the region JSON; do not hard-code any value or date (S-NPP's end comes from `snpp_cutover.snpp_last_observed`).

**Verify**: `cd web && npx tsc --noEmit` → exit 0; `npm run build` → exit 0

### Step 4: Look at it

Run API + dev server; open `http://localhost:5173/#pg=after`; switch areas (Punjab, Dhaka, SE Australia); toggle both
buttons with the keyboard (Tab, Enter/Space). Check at 390 px width (browser dev tools) that nothing scrolls sideways.

**Verify**: no console errors (browser dev tools); both toggles work by keyboard; charts render for all 9 presets
(Alberta/Dhaka may show "Not enough data for this chart." for some panels — acceptable).

## Test plan

- `tsc` + `vite build` (steps 1–3); manual check (step 4). No unit-test framework exists for the web app; do not add one.

## Done criteria

- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `cd web && npm run build` exits 0
- [ ] `grep -n '"after"' web/src/pages/shared.tsx` matches
- [ ] `grep -nE "[0-9]{2,}\.[0-9]|20(1|2)[0-9]-" web/src/pages/AfterModis.tsx` shows no hard-coded results or dates (only labels like "2016" in button text are allowed)
- [ ] Step 4 checks done
- [ ] `docs/plans/README.md` row 009 updated

## STOP conditions

- `denial.modis_ends_2016.series` is missing in the preset JSON (rebuild needed — report).
- Making the chart work needs changes to `LineChart` internals.

## Maintenance notes

- Plan 012 (site structure) links this page from the home "judge tour" and the Galactic Impact tile.
- If the outlook (`outlook.py`) moves from Aqua to NOAA-20 later, add one sentence here.
