# Kiln Watch — slide deck outline (7 slides)

One idea per slide. Build the slides in any tool; speaker notes are the narration. Numbers and sources: see
`VIDEO_SCRIPT.md` (R = README.md, M = meta.json).

## 1. Problem
**Title:** "In 2012 the record jumped. The fires did not."
- Visual: `docs/readme/hero.svg`.
- Notes: A sharper satellite (Suomi-NPP VIIRS) counts smaller fires. Raw hotspot counts jump 3.5 to 10.6 times across nine areas (R). Anyone reading the raw record sees a trend that is the satellite fleet changing.

## 2. Why now
**Title:** "The satellites that anchored the record are ending."
- Visual: `docs/readme/sensors.svg`.
- Notes: Aqua's overpass drifted and its archive changed version in 2023; Suomi-NPP's last data is dated 2 Nov 2026 (R, read from data). A record tied to one instrument breaks when it goes.

## 3. Method in one picture
**Title:** "One reference scale, a 95% interval on every value."
- Visual: the flowchart in R "The fix" (Terra → Aqua ← Suomi-NPP ← NOAA-20 ← NOAA-21).
- Notes: Ratio of totals per calendar month, day and night apart, shrunk by empirical Bayes. Aqua is the reference because its orbit is the only one flown continuously. No black box.

## 4. Proof
**Title:** "We test it by taking satellites away."
- Visual: Proof page scorecard (`#pg=method`), nine areas.
- Notes: Harmonized steps 0.93 to 1.19 against raw 3.5 to 10.6 (R). Say where it falls short too: Punjab under-corrects, Paraná Delta is off by +27%, Northern California out-of-sample coverage is 79% (R "Where it still falls short").

## 5. After MODIS
**Title:** "Switch MODIS off. The record holds."
- Visual: After MODIS page (`#pg=after`) with the toggle on "MODIS ends in 2016".
- Notes: Rebuilt from VIIRS alone, 2017–2020 follows what Aqua saw (Punjab ρ 0.98, error +469.7% raw → −5.8%, R). From 2023 the live record runs on VIIRS only, still on the Aqua scale.

## 6. Early warning and Bangladesh
**Title:** "Used where it matters."
- Visual: Early warning page; Bangladesh page kiln-season chart.
- Notes: Early warning is a climatological outlook with its backtest shown; never a forecast. Dhaka's brick-kiln belt: raw counts rise 10.6 times when VIIRS arrives (R). Kilns are kept as their own "likely kilns" class, not yet checked against an inventory.

## 7. Try it
**Title:** "kiln-watch-seven.vercel.app"
- Visual: QR of the live link; repo link; MCP badge.
- Notes: 31-tool MCP server for Claude, open API, n8n workflows. Detections are not fires and not burned area. Built on NASA FIRMS; AI use is disclosed in `AI_USE.md`.
