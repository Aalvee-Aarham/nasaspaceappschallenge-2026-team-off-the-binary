# Kiln Watch — demo video script

Two cuts. Keep the one the 2026 Project Submission Guide allows (check the length limit first). Every number carries
its source; if a number on screen changes after a rebuild, re-read it from the source and update here first.
Narration is also the English subtitle text.

Sources: **R** = README.md · **M** = `data/regions/<area>/meta.json` · **L** = live site `https://kiln-watch-seven.vercel.app`

## 30-second cut

| # | Time | On screen | Narration / subtitle | Number source |
|---|---|---|---|---|
| 1 | 0–6 s | Explorer on Punjab, raw vs harmonized calendar (`#pg=explore`, Punjab) | "In 2012 a sharper satellite started counting smaller fires. Nothing changed on the ground. The record did." | R "The problem" |
| 2 | 6–14 s | Proof page scorecard (`#pg=method`) | "Kiln Watch puts every satellite on one scale. Raw counts jump up to 10.6 times. Ours stay near 1." | R stats: raw 3.5–10.6×, harmonized 0.93–1.19× |
| 3 | 14–22 s | After MODIS page, press "MODIS ends in 2016" (`#pg=after`) | "Take MODIS away, and the record rebuilt from VIIRS alone still follows what Aqua really saw." | M `denial.modis_ends_2016` (Punjab ρ 0.98 in R results table) |
| 4 | 22–30 s | Live link on screen | "Detections are not fires. Every number comes from NASA FIRMS. kiln-watch-seven.vercel.app" | R footer |

## 2-minute cut

| # | Time | On screen | Narration / subtitle | Number source |
|---|---|---|---|---|
| 1 | 0:00–0:15 | Punjab raw vs harmonized calendar, then `hero.svg` | "In 2012 a sharper satellite started counting smaller fires. Nothing changed on the ground. The record did. In Punjab, raw counts jump 4.5 times; the real change is none." | R results table, Punjab: raw 4.48, harmonized 0.93 |
| 2 | 0:15–0:35 | `steps.svg`, then the method strip (Terra → Aqua ← Suomi-NPP ← NOAA-20 ← NOAA-21) | "Fix: pick one reference, Aqua, and calibrate every other satellite to it. One scale, and a 95% interval on every value." | R "The fix" |
| 3 | 0:35–1:05 | Proof scorecard, all nine areas, then After MODIS: toggle MODIS off, toggle Suomi-NPP withheld | "Proof: we test the record by taking satellites away. Nine areas, one scorecard. Rebuilt from VIIRS alone, Punjab's error falls from plus 470 percent to minus 6." | R results table, Punjab: +469.7% → −5.8% |
| 4 | 1:05–1:20 | After MODIS "Aqua is drifting" chart | "Aqua itself is drifting. From 2023 the record runs on VIIRS alone, so it carries on when MODIS is switched off." | M `aqua_overpass.onset`; R "The fix" (2023) |
| 5 | 1:20–1:35 | Early warning page, backtest line | "Early warning compares this month with every earlier year, and shows how often that rule was right. It never forecasts." | L Warning page (read the day-15 numbers off the page; do not quote one not on screen) |
| 6 | 1:35–1:50 | Bangladesh page, kiln-season chart; then the MCP page and Claude answering | "Built for Bangladesh's brick-kiln belt, where raw counts rise 10.6 times with no change on the ground. And a 33-tool MCP server, so Claude asks Kiln Watch for every number." | R Dhaka raw 10.58; R "33-tool" |
| 7 | 1:50–2:00 | Home page, live link | "Detections are not fires. Every number comes from NASA FIRMS. kiln-watch-seven.vercel.app" | R footer |

## Recording notes

- Record from the live site after 008 (env vars) and this release are deployed, so the Analyst and email work on camera.
- Read the on-screen numbers off the page before recording; they come from the same JSON as the README.
- No team members' personal data on screen (emails, phone numbers). Use a throwaway address for the alert demo.
- Re-record only the shots whose screens changed. Keep this file as the single source of wording.
