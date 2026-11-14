# Use of AI

The 2026 Space Apps rules ask every submission to describe how AI tools were used.

| Tool | Used for | Data it worked on |
|---|---|---|
| **Claude Fable 5.2** (Anthropic) | Planning: reading the challenge brief, literature and rules review, shaping the method (Aqua as reference, denial tests, accessibility) | Public challenge page, public papers and NASA/NOAA documentation |
| **Gemini Argon** (Google) | Planning: research briefs and the first technical specification | Public challenge page, public papers and NASA/NOAA documentation |
| **Claude Opus via Claude Code** (Anthropic) | Development: wrote the data pipeline, harmonization statistics, API, MCP server and web UI; ran builds and tests | Our source code; public NASA FIRMS detections and the region files built from them |
| **MiniMax M3 via OpenCode** | Development of this release: the audit triage, the scientific corrections, the two independent validation scripts and the submission text | Our source code; public NASA FIRMS detections, NASA MCD64A1 burned area and the public APAD kiln inventory |
| **Gemini Flash** (Google) | Development: writing and reviewing code | Our source code |
| **Gemini 2.5 Flash** (Google, free tier, optional at run time) | In-app analyst: puts the results of deterministic tool calls into words | Pipeline output only (region JSON built from NASA FIRMS). Every tool call is shown to the user |

**What AI did not do.** No AI system produces any number shown in the calendar, charts or downloads. Those come from
`server/kw/build.py` run on NASA FIRMS data, and the two independent checks come from `scripts/validation/`. No
personal or private data was given to any AI tool. The team reviewed the code and results before submission.
