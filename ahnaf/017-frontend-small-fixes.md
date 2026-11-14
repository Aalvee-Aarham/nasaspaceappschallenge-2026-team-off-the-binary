# Plan 017: Frontend small fixes from the code scan

> **Executor instructions**: Nine independent small fixes in `web/src`. One commit each; run
> `cd web && npx tsc --noEmit` after every step. If a step's excerpt no longer matches the code, skip it and note it.
> When done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- web/src/`
> Plans 009 and 012 also edit `web/src` (new pages, nav). This plan touches different lines; if they landed first,
> re-find each excerpt by searching for it.

## Status

- **Priority**: P1 for steps 1–3 (wrong numbers or a dead keyboard path a judge can hit), P2 for the rest
- **Effort**: S (each step ≤ 10 lines)
- **Risk**: LOW
- **Depends on**: none
- **Category**: bugs (UI correctness, robustness)
- **Planned at**: commit `1e99c85`, 2026-11-13 (code-scan findings C1/S11, S13, C3, C4, C10, C9, C7, C12, C11; re-read and confirmed. C2 was rejected — see the review)

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Install | `cd web && npm ci` | exit 0 |
| Type check | `cd web && npx tsc --noEmit` | exit 0 |
| Run | `cd web && npm run dev` (API optional: static area files load without it) | page at the printed URL |

Code style to match: one-line handlers, `?.` and `??`, no new dependencies, `className="muted small"` for notes.

## Scope

**In scope**: `web/src/api.ts`, `Record.tsx`, `Timeline.tsx`, `Analyst.tsx`, `App.tsx`, `pages/Connect.tsx`.
**Out of scope**: chart accessibility (C5, C6) and Back-button history (C8) — real but larger; after submission.

## Steps

### Step 1 (C1/S11): "no satellite observing" is drawn as a measured 0 on the raw scale

`web/src/api.ts:212-219`:
```ts
export function pick(b: Block, scale: Scale, cls: Cls): Band & { modelled?: boolean[]; sensors?: string[][] } {
  ...
  const v = cls === "veg" ? b.raw.all_det : b.periods.map((_, i) => SENSORS.reduce((a, s) => a + (b.raw[s]?.static_det[i] ?? 0), 0));
  return { v, lo: v.map(() => null), hi: v.map(() => null) };
}
```
The harmonized scales already hold `null` where nobody observed (e.g. the 2001-W25/W26 Terra outage); the raw branch
returns 0 there. Replace the last two lines with:
```ts
  const raw = cls === "veg" ? b.raw.all_det : b.periods.map((_, i) => SENSORS.reduce((a, s) => a + (b.raw[s]?.static_det[i] ?? 0), 0));
  const v = raw.map((x, i) => (SENSORS.some((s) => (b.coverage[s]?.[i] ?? 0) > 0) ? x : null));
  return { v, lo: v.map(() => null), hi: v.map(() => null) };
```
(`Block.coverage: Record<string, number[]>` is at `api.ts:21`.) Then `web/src/Record.tsx:316-325` `annual` adds
`vals[i] ?? 0` and so counts a hole as zero; mark such a year partial instead:
```ts
    cur.partial ||= b.partial[i] || vals[i] == null;
```
`Timeline.tsx` needs no change (it draws no bar for both 0 and null).

**Verify**: type check passes. In the app, Punjab → Calendar → Week → Raw: 2001 W25/W26 show the hatched
"no data" pattern, not an empty-looking zero cell.

### Step 2 (S13): "not measured" printed as a measured 0%

`web/src/Record.tsx:377` `fmt((wh.inside_interval ?? 0) * 100, 0)` and `:492-493`
`fmt((den.ours_seasonal_eb.interval_coverage_raw ?? 0) * 100, 0)` / `interval_coverage ?? 0`. A missing value
prints "0%". For each, render `—` when the value is null, e.g.
```ts
{wh.inside_interval == null ? "—" : fmt(wh.inside_interval * 100, 0)}
```
Line 377 additionally: `inside_interval` is 1.0 everywhere because the interval is already widened (code-scan
review S4). Lead the sentence with the mean difference and drop the "keeps X% … within the interval" part:
```tsx
<p>Rebuilding {wh.window.join(" to ")} with Suomi-NPP withheld changes the record by {fmt(wh.mean_abs_diff_pct, 1)}% on average over {wh.n} months.</p>
```
**Verify**: type check passes; `grep -n "inside_interval ?? 0" web/src/Record.tsx` → no hits.

### Step 3 (C3): switching Month↔Week leaves the keyboard focus on a key that no longer exists

`web/src/Record.tsx:39` `const [focus, setFocus] = useState<string | null>(p.selected);` is never reset, so after
switching granularity `focus` is a month key in the week grid; `WeekGrid.onKey` does
`const i = p.idx.get(cur ?? ""); if (i === undefined) return;` and the arrow keys stop working. Remount the
calendar when the granularity changes — in `web/src/App.tsx:365` add `key={granularity}` to `<Calendar … />`.

**Verify**: type check passes. In the app: Calendar, press an arrow key, switch to Week, arrow keys move the focus.

### Step 4 (C4): up/down arrows land on the wrong week in 53-week years

`web/src/Record.tsx:153`: `ArrowUp: -52, ArrowDown: 52` moves 52 periods, which is one week off after any ISO
53-week year. Replace the two vertical keys with a same-week lookup; keep left/right as they are:
```ts
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const y = +cur!.slice(0, 4) + (e.key === "ArrowUp" ? -1 : 1), w = cur!.slice(6);
      const t = p.idx.has(`${y}-W${w}`) ? `${y}-W${w}` : `${y}-W52`;  // week 53 has no partner in most years
      if (p.idx.has(t)) p.onFocus(t);
      return;
    }
    const d = ({ ArrowLeft: -1, ArrowRight: 1 } as Record<string, number>)[e.key];
```
**Verify**: type check passes. Week grid: from 2020-W30 ArrowDown → 2021-W30.

### Step 5 (C10): timelapse calls a stale `onMonth`

`web/src/Timeline.tsx:33-43` runs `setInterval` with deps `[p.playing, n]`, so `p.onMonth` / `p.onPlay` are frozen at
play time (App's `onTimelineMonth` closes over `date` and `period`). Keep them in refs like `monthRef`:
```ts
  const cb = useRef({ onMonth: p.onMonth, onPlay: p.onPlay });
  cb.current = { onMonth: p.onMonth, onPlay: p.onPlay };
```
and inside the interval use `cb.current.onPlay(false)` / `cb.current.onMonth(toKey(next))`.

**Verify**: type check passes; press play, change the selected period while it plays: playback follows the new state.

### Step 6 (C9): an analyst question asked while busy is dropped

`web/src/Analyst.tsx:131-132` `const send = async (q: string) => { if (!q.trim() || busy) return;` and `:148-150`
`if (p.seed) { send(p.seed); p.onSeedUsed(); }` clears the seed even when `send` returned early. Change the effect to
wait until not busy:
```ts
  useEffect(() => {
    if (p.seed && !busy) { send(p.seed); p.onSeedUsed(); }
  }, [p.seed, busy]); // eslint-disable-line react-hooks/exhaustive-deps
```
**Verify**: type check passes.

### Step 7 (C7): one failed health call switches the whole app to offline mode for good

`web/src/App.tsx:69-74` — `api.health().then(…).catch(() => setOnline(false));`. A single network hiccup disables
drawing, the analyst and news for the session. Retry once after 3 s before going offline:
```ts
    const ok = (h: Health) => { setHealth(h); setOnline(true); api.warnings().then(setEw).catch(() => undefined); api.outlook().then(setOutlook).catch(() => undefined); };
    api.health().then(ok).catch(() => setTimeout(() => api.health().then(ok).catch(() => setOnline(false)), 3000));
```
Use the health type name that `api.ts` exports (search `health:` in `api.ts`); keep the comment about the outlook.

**Verify**: type check passes.

### Step 8 (C12): place search has no busy state or timeout

`web/src/App.tsx` `doSearch` awaits Nominatim with no timeout. Add a `searching` state, pass
`{ signal: AbortSignal.timeout(8000) }` to that `fetch`, set `searching` true before and false in a `finally`, and
disable the search button while `searching` (find the form that calls `doSearch`). The existing
`catch { setSearchErr("Place search is unavailable right now."); }` already covers the timeout.

**Verify**: type check passes.

### Step 9 (C11 + Connect): small robustness items

- `web/src/Record.tsx:59-83` `cellStyle`, `ariaFor` and `MonthTable` each call `pick(b, p.scale, p.cls)` per cell.
  `Calendar` already has `const s = pick(...)` (line 36). Add `s` to the `gp` object (line 42), add
  `s: ReturnType<typeof pick>` to `GridProps`, and use `p.s` in those three places.
- `web/src/pages/Connect.tsx:62` `navigator.clipboard?.writeText(t).then(...)` has no `.catch`; a refused write
  is an unhandled rejection. Append `.catch(() => undefined)`.

**Verify**: type check passes; `grep -c "pick(b, p.scale, p.cls)" web/src/Record.tsx` → `1` (only `Calendar`'s own
call on line 36 remains).

## Done criteria

- [ ] `cd web && npx tsc --noEmit` exits 0
- [ ] `cd web && npm run build` exits 0
- [ ] Manual: steps 1, 3, 4 checked in the running app
- [ ] `docs/plans/README.md` row 017 updated, listing any skipped step

## STOP conditions

- Step 1: harmonized "hotspots" values in `monthly.json` are not null during the 2001 Terra outage (then the hole
  is somewhere else; report instead of masking).

## Maintenance notes

- After this, a `null` value means "not observed" on every scale; new views should render it as no data, never as 0.
- C5/C6 (screen-reader tables for charts, `role="grid"` on an svg) and C8 (`pushState` + `hashchange`) are the next
  frontend items after the submission.
