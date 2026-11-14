# Kiln Watch — submission text

Fill each field from the 2026 Project Submission Guide (exact field names and limits: check the guide). Text below is
draft wording for the team to edit.

**Project name:** Kiln Watch

**High-level summary:** Kiln Watch puts NASA's MODIS and VIIRS fire detections on one consistent scale, so a place's
fire record from 2000 to today does not jump when satellites arrive or are retired. Every value carries a 95% interval
and is tested by taking satellites away, in nine regions. On top of the record it offers an early warning that compares
the current month with every earlier year (never a forecast), and a 38-tool MCP server so Claude can answer from the
same numbers.

**How it addresses the challenge (Harmonization of MODIS and VIIRS Hot Spots):** Aqua MODIS is the reference scale. Terra,
Suomi-NPP, NOAA-20 and NOAA-21 are calibrated to it by monthly ratios with empirical-Bayes shrinkage, day and night
apart. Which satellites flew when is measured from the data, not typed in. Aqua's 2023 overpass drift and MODIS version
change are measured, and from then the record runs on VIIRS alone. The "After MODIS" page lets anyone switch satellites
off and see the record hold.

**NASA data used:** copy the table under "NASA data" in the README ("Data used").

**Other data:** copy "Other datasets" from the README (GDACS, GDELT, Google News RSS, OpenFreeMap, OpenStreetMap, ReliefWeb optional).

**Use of AI:** summarise `AI_USE.md`. No AI system produces any number shown; numbers come from `server/kw/build.py` run on NASA FIRMS data. No personal data was given to an AI tool.

**Demo video:** `TODO` (upload per step 6, then paste the link here and in the README)

**Live site:** https://kiln-watch-seven.vercel.app

**Repository:** the project's GitHub repository (link as in the team's submission form)

**Team (names and roles as in the README):**
Aalvee Aarham: AI Systems Architect & Project Lead · Israt Jahan Arna: Frontend Engineering Lead · Sajid Alam Chowdhury Omee: Backend Systems Engineer · Nazifa Jahan: Research & Innovation Lead · Maruf Hasan Tawhid: Data Acquisition & Data Analyst · Muhammad Ahnaf Sarker: Lead AI/ML Developer

**Prior work disclosure [HUMAN — decide after reading the rules]:** The repository has commits and a live site from before
14 November, and a concept from October. Read the 2026 Participant FAQ and Terms & Conditions and confirm whether and
how prior work must be disclosed. If it must, add one honest sentence here and in the README, for example: "Built on our
October concept; the harmonization pipeline, validation and app were developed in the run-up to and during the hackathon."
