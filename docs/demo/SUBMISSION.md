# Kiln Watch — submission text

Fill each field from the 2026 Project Submission Guide (exact field names and limits: check the guide). Text below is
draft wording for the team to edit.

> **Before anything else — read this.** The GO Team has said in writing that "working ahead of the hackathon can lead
> to disqualification" and that teams should refrain from starting on their projects until the official 14–15 November
> hackathon, and that a project built and published before then should be started again from scratch rather than
> extended. Kiln Watch has public traces from before 14 November. **That is an unresolved eligibility risk that code
> cannot fix**, and disclosure does not make it go away. The team must ask the GO Team, in writing, what may be
> submitted, and record the answer, before submitting. See the last section of this file.

**Project name:** Kiln Watch

**High-level summary:** Kiln Watch puts NASA's MODIS and VIIRS fire detections on one consistent scale, so a place's
fire record from 2000 to today does not jump when satellites arrive or are retired. Every value carries a 95% interval
and is tested by taking satellites away, in nine regions. Two kinds of independent check publish their results, pass or
fail: record-level checks (NASA MCD64A1 burned area, an APAD kiln inventory) and per-case witnesses (burn scars, a
Sentinel-2 kiln map, Black Marble night lights). On top of the record it offers an early warning that compares the
current month with every earlier year (never a forecast), and an MCP server so Claude can answer from the same numbers.

**How it addresses the challenge (Harmonization of MODIS and VIIRS Hot Spots):** Aqua MODIS is the reference scale. Terra,
Suomi-NPP, NOAA-20 and NOAA-21 are calibrated to it by monthly ratios with empirical-Bayes shrinkage, day and night
apart. Which satellites flew when is measured from the data, not typed in. The MODIS archive's 2023 change in reported
acquisition time and product version is measured from the data, and from then the record runs on VIIRS alone. The "After
MODIS" page lets anyone switch satellites off and see the record hold.

**NASA data used:** copy the table under "NASA data" in the README ("Data used"), including MCD64A1 burned area, used as
an independent check.

**Other data:** copy "Other datasets" from the README (GDACS, GDELT, Google News RSS, OpenFreeMap, OpenStreetMap,
WorldPop, the APAD Bangladesh brick-kiln inventory, ReliefWeb optional).

**Independent checks (run by `scripts/validation/`, fail closed, results published):**

- **NASA MCD64A1 burned area.** The harmonized monthly record is compared with burned area in seven vegetation-dominated
  areas. The raw detection count jumps when VIIRS arrives in 2012; burned area, which is built from MODIS alone, does
  not. That is the clearest evidence that the jump was an instrument change and not a change on the ground.
- **APAD Bangladesh brick-kiln inventory.** The published persistent-heat cells are compared with 4,760 operating kilns
  and with randomly placed cells of the same number. They do not land on mapped kilns more often than chance, so the
  class is published as a persistent-heat proxy and not as a kiln inventory. The negative result is published with its
  source, hash and limitations.

**Use of AI:** summarise `AI_USE.md`. No AI system produces any number shown; numbers come from `server/kw/build.py` run on NASA FIRMS data. No personal data was given to an AI tool.

**Demo video:** `TODO` (upload per step 6, then paste the link here and in the README)

**Live site:** https://kiln-watch-seven.vercel.app

**Repository:** the project's GitHub repository (link as in the team's submission form). The canonical submission
repository is `Aalvee-Aarham/nasaspaceappschallenge-2026-team-off-the-binary`.

**Team (names and roles as in the README):**
Aalvee Aarham: AI Systems Architect & Project Lead · Israt Jahan Arna: Frontend Engineering Lead · Sajid Alam Chowdhury Omee: Backend Systems Engineer · Nazifa Jahan: Research & Innovation Lead · Maruf Hasan Tawhid: Data Acquisition & Data Analyst · Muhammad Ahnaf Sarker: Lead AI/ML Developer

## Prior work and eligibility — the one thing code cannot settle

**The rule, in the GO Team's own words** (discussion #1827, answered by the GO Team on 5 November 2026):

> "We appreciate the enthusiasm of participants, but we ask that teams refrain from starting on their projects until
> the start of the official November 14-15 hackathon (Saturday, 9am local time of your Local Event; if Universal
> Event, start time is Saturday, 9am of the Team Owner's area of residence). Working ahead of the hackathon can lead to
> disqualification. However, before the hackathon starts, you may select a challenge to work on, review the resources,
> research the topic, and form your team based on the skills you think are needed."

In the same thread the GO Team says a project developed and published before the hackathon should be started again from
scratch rather than extended, and that disclosure is not permission: "I would not recommend submitting the pre-existing
platform as your hackathon solution without written approval from the Global Organizing Team."

**What exists before 14 November (verifiable, not a claim):**

| Date | Fact |
|---|---|
| 5 Nov 2026 | The GO Team publishes the pre-start rule (#1827). |
| 13 Nov 2026 | This repository's first commit (`108ff22`, "Initial commit"), and every earlier commit in its history. |
| 13 Nov 2026 | The live site `kiln-watch-seven.vercel.app` is deployed and serving. |
| 14 Nov 2026 | The official hackathon starts. |
| 14–15 Nov 2026 | The official hackathon window. |

**What we are asking, and what we will do with the answer.** We have opened a discussion with the GO Team and asked for
written guidance on exactly three things: (1) whether this project may be submitted at all, (2) whether the work done
before 14 November may be reused as a foundation, and (3) if not, what a compliant submission by this team should be.
**This file will record the GO Team's answer verbatim once received, and the submission will be built to match it.**

Until that answer exists, the honest position is: this project's eligibility is unconfirmed, and no amount of
engineering changes that. The team should be prepared to submit a genuinely new implementation built during 14–15
November, using this repository's research, method and NASA data sources as the starting point rather than as the
finished product.
