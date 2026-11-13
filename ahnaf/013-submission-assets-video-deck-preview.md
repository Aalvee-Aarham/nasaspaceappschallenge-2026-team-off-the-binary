# Plan 013: Submission package — demo video, slides, link previews, rules check

> **Executor instructions**: Most of this plan is writing and recording. An executor model writes the files in steps
> 1–4; steps marked **[HUMAN]** are for the team (recording, uploading, rules). Never put team members' personal data
> (emails, phone numbers) in any file. When done, update the status row for this plan in `docs/plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 1e99c85..HEAD -- web/index.html README.md docs/`
> README is expected to have changed (plans 003–005, 010, 011). Read its current "The proof" and "Where it still falls
> short" sections before writing the script: the script must use the README's current numbers.

## Status

- **Priority**: P1 (a demo is mandatory; deadline Sunday 15 November 2026, 23:59 local time)
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans 003, 005, 009, 012 for the final numbers and screens (draft the script now, record last)
- **Category**: docs / presentation
- **Planned at**: commit `1e99c85`, 2026-11-13

## Why this matters

Every Space Apps submission needs a project demo: a video with English subtitles or an English slide deck (check the
2026 Project Submission Guide for the length and format limits). Presentation is scored as heavily as each other
criterion. The repo has a strong README but no video, no deck and no link-preview tags, so a shared link shows no
image. One competitor (FireLens) ships a video, a script and a deck. Also, the 2026 hackathon runs 14–15 November
while this repo already has commits, a live site and a concept repo from October. The team must check the rules on
prior work and disclose it.

## Current state

- `web/index.html` has `<title>` and `<meta name="description">` but no Open Graph / Twitter tags.
- `docs/readme/` has figures and screenshots (`app-home.jpg`, `app-calendar.jpg`, `app-globe.jpg`, `app-warning.jpg`,
  `app-mcp.jpg`, `hero.svg`, `steps.svg`, `denial.svg`, …); `scripts/readme_figures.mjs` regenerates SVG figures from data.
- `AI_USE.md` documents AI use (required by the 2026 rules) — keep it current.
- Live site: `https://kiln-watch-seven.vercel.app`.

## Scope

**In scope (create/edit)**: `web/index.html` (meta tags), `web/public/og.jpg` (copy of an existing screenshot, 1200×630),
`docs/demo/VIDEO_SCRIPT.md`, `docs/demo/DECK.md`, `docs/demo/SUBMISSION.md`, `README.md` (one "Demo" link line), `AI_USE.md` (update if new AI tools were used).
**Out of scope**: app code beyond `index.html`.

## Steps

### Step 1: Link previews

In `web/index.html` `<head>` add:
```html
<meta property="og:title" content="Kiln Watch — one fire record from 2000 to today" />
<meta property="og:description" content="NASA MODIS and VIIRS hotspots on one tested scale, with an early warning and a 31-tool MCP server." />
<meta property="og:image" content="https://kiln-watch-seven.vercel.app/og.jpg" />
<meta property="og:url" content="https://kiln-watch-seven.vercel.app" />
<meta name="twitter:card" content="summary_large_image" />
```
Create `web/public/og.jpg` at 1200×630 from `docs/readme/app-home.jpg` (any image tool already on the machine, e.g.
`ffmpeg -i docs/readme/app-home.jpg -vf "scale=1200:-2,crop=1200:630" web/public/og.jpg`; if none is available, copy
the file unchanged and note it).

**Verify**: `cd web && npm run build && ls dist/og.jpg` → file exists

### Step 2: Video script (`docs/demo/VIDEO_SCRIPT.md`)

Target length: whatever the 2026 guide allows (write a 30-second cut and a 2-minute cut; the team keeps the one that fits).
Story in this order, one shot per line with on-screen action, narration and the English subtitle text:
1. Hook (5 s): "In 2012 a sharper satellite started counting smaller fires. Nothing changed on the ground. The record did." — raw vs harmonized Punjab calendar.
2. Fix (10 s): one scale (Aqua), one interval on every value.
3. Proof (15 s): Proof scorecard; switch MODIS off on the After MODIS page.
4. Use (15 s): early warning with its backtest line; Bangladesh kiln page; Claude answering through MCP.
5. Close (5 s): live link, "Detections are not fires. Every number comes from NASA FIRMS."
Use only numbers that appear in the current README or on the live site; write next to each number where it comes from.

### Step 3: Slide deck outline (`docs/demo/DECK.md`)

At most 7 slides, one idea each: Problem · Why now (MODIS/S-NPP ending) · Method in one picture · Proof (scorecard) ·
After MODIS · Early warning + Bangladesh · Try it (live link, MCP, repo). Speaker notes under each. The team may build
the actual slides from this in any tool.

### Step 4: Submission text (`docs/demo/SUBMISSION.md`)

Fields the Space Apps project page asks for (check the 2026 guide for exact fields and limits): project name, high-level
summary (≤ 1 paragraph), how it addresses the challenge, NASA data used (copy the table from README "Data used"),
other data, AI use (summarise `AI_USE.md`), demo link, live link, repo link, team (names and roles as in the README only).

### Step 5 [HUMAN]: Rules and prior work

Read the 2026 Participant FAQ, Terms & Conditions and Project Submission Guide on spaceappschallenge.org. Confirm:
(a) whether work before 14 November is allowed and how to disclose it; (b) all six members are registered at the
same local event; (c) demo format and length; (d) the exact 2026 award categories. If prior work must be disclosed,
add one honest sentence to `docs/demo/SUBMISSION.md` and the README (e.g. "Built on our October concept; the
harmonization pipeline, validation and app were developed in the run-up to and during the hackathon").

### Step 6 [HUMAN]: Record and upload

Record the chosen cut from the live site (after plans 008/009/012 are deployed), burn in English subtitles, upload
(YouTube unlisted or as the guide says), and put the link in `README.md` and `docs/demo/SUBMISSION.md`.

## Done criteria

- [ ] `web/dist/og.jpg` exists after build; `grep -c 'og:' web/index.html` ≥ 4
- [ ] `docs/demo/VIDEO_SCRIPT.md`, `DECK.md`, `SUBMISSION.md` exist; every number in them has a source note
- [ ] **[HUMAN]** rules checked (step 5) and video uploaded (step 6)
- [ ] `docs/plans/README.md` row 013 updated

## STOP conditions

- The 2026 guide forbids work done before the event in a way that affects this project — stop everything and tell the whole team.

## Maintenance notes

- Re-record only the shots whose screens changed; keep the narration file as the single source of wording.
