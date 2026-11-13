# Review of `docs/code-scan-2026-11-13.md`

Reviewed 2026-11-13 against commit `1e99c85`. Every finding was re-read in the code. The science findings were
re-measured: the published `data/regions/*/monthly.json` values were rebuilt from the raw per-satellite counts with
the repo's own rules (median error ≤ 0.02%), and the proposed fixes were run on that rebuild.

**Verdict in one line:** the scan is good and mostly right. It overstates two things (S1 severity; S2's evidence),
gets one fix backwards (S4), has one false crash (C2), and its cross-reference to `plans/` is partly wrong. The
confirmed gaps are now plans 014–017 in `docs/plans/`, and plans 003 and 009 were corrected.

Verdicts: **CONFIRMED** (real, as described) · **DOWNGRADED** (real, smaller than stated) · **CORRECTED** (real, but
the evidence or fix in the scan is wrong) · **REJECTED** · **PLANNED** (already in a plan) · **DEFER** (real; not
worth doing before the submission).

## A. Harmonization science

| # | Scan severity | Verdict | Evidence / what changes | Plan |
|---|---|---|---|---|
| S1 `combine` zero-reading weight | CRITICAL | **DOWNGRADED → LOW** | Bug is real (`science.py:108`, zero branch skips the pooled-mean rule). Measured impact: one published month with value ≥ 5 moves > 20% (Niger Delta 2026-11, partial: 5.6 → 8.3). The scan's Alberta example included Terra, which `_active` does not use when Aqua observes. Simpler fix than the scan's: no tuple change, `sqrt(cv)·mu` in the zero branch. | 014 (new) |
| S2 record is Aqua-dominated; families diverge from 2024 | CRITICAL | **CORRECTED** | The 2024 divergence is mostly NOAA-21 joining the VIIRS sum. Per satellite on a fixed month set, Punjab Aqua ÷ NOAA-20 steps −25% in **2023** (0.157 → 0.122), the month the MODIS archive switches from `6.03` to `61.03`. Aqua's day weight share is measured, not "almost all": Punjab ~0.80–0.86, SE Australia 0.49–0.82, Alberta 0.59–0.96, La Rioja ~0.13. Underlying concern (recent record follows a changed Aqua) stands. | 003 (revised: version rule + corrected evidence) |
| S3 coverage 96% is by construction | IMPORTANT | **CONFIRMED** | Interval widened by k fitted on the same months it is scored on. | 004 |
| S4 rehearsal too lenient | IMPORTANT | **CORRECTED** | Real symptom (`inside_interval` = 1.0 everywhere), wrong fix: adding `var_full` makes the test *more* lenient. The k-widened interval cannot fail, so the number carries no information. Lead with `mean_abs_diff_pct`; don't show `inside_interval`. | 009 (revised), 017 step 2 |
| S5 map cells ≠ area estimator | IMPORTANT | **CONFIRMED** | | 006 |
| S6 `_drift` month mix | IMPORTANT | **CONFIRMED** | Punjab Aqua ÷ S-NPP 2026: 0.131 published vs 0.119 like-for-like; flat since 2023. The old plan 003 quoted the inflated numbers; withdrawn. | 015 (new) |
| S7 next-four-weeks anchor | IMPORTANT | **CONFIRMED** (small) | `tools._next_weeks` uses the partial week, `build._season` the last complete week; the Warning tile shows both. | 016 step 2 |
| S8 single-area rebuild drops `transfer_validation` | IMPORTANT | **CONFIRMED** | | 002 |
| S9 leap-February denominator | MODERATE | **REJECTED** | Coverage normalisation divides by observed days, so leap-Feb compares fairly. | — |
| S10 first weekly period coverage | MODERATE | **REJECTED** | 5/7 is the right coverage for that week. | — |
| S11 two-week hole drawn as zero | MODERATE | **CONFIRMED** (minor) | Same root cause as C1 (raw branch of `pick`, `annual`'s `?? 0`). | 017 step 1 |
| S12 ISO week 53 folded into 52 | MODERATE | **CONFIRMED, by design** | Documented (`ponytail:` comments); sums, does not overwrite. | — |
| S13 `?? 0` shows "0%" for missing | MODERATE | **CONFIRMED** (minor) | `Record.tsx:377, 492, 493`. | 017 step 2 |
| S14 numbers not traceable to a commit | MODERATE | **CONFIRMED** | 8 of 9 areas `unversioned`; `rev-parse` also mislabels dirty builds. Use `git describe --always --dirty`. | 016 step 10 |

## B. Service layer, API, deployment

| # | Scan severity | Verdict | Note | Plan |
|---|---|---|---|---|
| B1 failed send marked as delivered | CRITICAL | **CONFIRMED** (matters once SMTP is on) | Marking moved after `send_email`; n8n poll keeps marking on poll. | 016 step 6 |
| B2 links from `Host` header | CRITICAL | **CONFIRMED** | | 008 |
| B3 index lists 6 missing areas | CRITICAL | **CONFIRMED** | | 001 |
| B4 Docker omits `sensor_days.parquet` | CRITICAL | **DOWNGRADED → LOW** | Real (file is tracked, Dockerfile skips it), but the demo runs on Vercel, not Docker. One `COPY` line. | 016 step 10 |
| B5 duplicate `provenance.source` | CRITICAL | **DOWNGRADED → MODERATE** | Real and visible ("Source: detections"); one-word rename. | 016 step 1 |
| B6 `test_alerts` exits 134 | IMPORTANT | **CONFIRMED** | Reproduced: all asserts pass, then exit 134. With `KW_SERVERLESS=1` it exits 0, so the cause is `check` → `refresh_if_stale` starting a DuckDB thread. Set `tools.SERVERLESS = True` in the test. | 016 step 10 |
| B7 news outage reads as "no reports" | IMPORTANT | **CONFIRMED** | Breaks the "missing news ≠ absence" guardrail. | 016 step 5 |
| B8 build starts before limit checks | IMPORTANT | **CONFIRMED** | Moving the checks first is enough for the hackathon; a queue cap is DEFER. | 016 step 8 |
| B9 evidence/CSV download inside a request | IMPORTANT | **DEFER** | Real on Vercel; bounded by the 60 s budget. | — |
| B10 outlook rebuild inline under a lock | IMPORTANT | **DEFER** | | — |
| B11 EONET failure renders as nothing | IMPORTANT | **CONFIRMED** | | 016 step 7 |
| B12 agent `find_place` contract | IMPORTANT | **CONFIRMED** | Shared `tools.find_place` for MCP and the analyst. | 016 step 9 |
| B13 alerts store across workers | IMPORTANT | **DEFER** | Single worker in every documented run command. | — |
| B14 `StopIteration` → 500 | MODERATE | **CONFIRMED** (trivial) | | 016 step 4 |
| B15 hard-coded S-NPP end in prose | MODERATE | **CONFIRMED** | Breaks "sensor availability is measured from data". | 016 step 3 |
| B16 news-cache growth | MODERATE | **DEFER** | | — |
| B17 CORS `*` on state-changing routes | MODERATE | **REJECTED** | No cookies or ambient credentials; the token is the credential. By design. | — |
| B18 DuckDB connections not closed | MODERATE | **DEFER** | | — |
| B19 news logic needs DuckDB to import | MODERATE | **CONFIRMED, LOW** | `test_science.py` fails without duckdb (news → firms import). Use the venv. | — |
| B20 CLAUDE.md token rule points at missing tools | MODERATE | **CONFIRMED** | No `graphify-out/`, graphify not installed, no hook. The team should either install it or soften the rule in `CLAUDE.md` (their file; not changed here). | — |
| B21–B24 | MINOR | **DEFER** | | — |

## C. Frontend

| # | Scan severity | Verdict | Note | Plan |
|---|---|---|---|---|
| C1 raw scale draws "not observed" as 0 | CRITICAL | **DOWNGRADED → MODERATE** | Real (2001-W25/W26 Terra outage); one view, one scale. | 017 step 1 |
| C2 Copy button crashes on non-secure origin | CRITICAL | **REJECTED** | `navigator.clipboard?.writeText(t).then(...)`: optional chaining short-circuits the whole chain, so no TypeError. Only a missing `.catch` (`Connect.tsx:62`). | 017 step 9 |
| C3 calendar focus not reset on Month↔Week | CRITICAL | **DOWNGRADED → IMPORTANT** | Real: keyboard path dies after switching. `key={granularity}` fixes it. | 017 step 3 |
| C4 ±52 arrows in 53-week years | IMPORTANT | **CONFIRMED** | | 017 step 4 |
| C5 charts not exposed to screen readers | IMPORTANT | **DEFER** (after submission) | | — |
| C6 `role="grid"` on `<svg>` | IMPORTANT | **DEFER** | | — |
| C7 one failed health call → offline forever | IMPORTANT | **CONFIRMED** | Retry once before going offline. | 017 step 7 |
| C8 `replaceState`, no `hashchange` | IMPORTANT | **DEFER** | Back button leaves the site; fixing it touches every navigation path. | — |
| C9 seeded analyst question dropped when busy | MODERATE | **CONFIRMED** | | 017 step 6 |
| C10 stale `onMonth` in timelapse | MODERATE | **CONFIRMED** | | 017 step 5 |
| C11 `pick()` per cell | MODERATE | **CONFIRMED** (perf, minor) | | 017 step 9 |
| C12 place search: no busy state, no timeout | MODERATE | **CONFIRMED** | | 017 step 8 |

## Errors in the scan's cross-reference (section 8)

- It says plan 008 covers B4 (Docker) and C7 (health). It does not; both are now in 016/017.
- It says plan 009 covers S4. It did not; plan 009 is now revised for S4.
- It counts 14 plans; there were 13 plus the index. There are now 17 (`docs/plans/README.md`).

## Corrections to our own plans after this review

- **Plan 003**: the evidence paragraph quoted `meta.drift` ratios that S6 shows are not like-for-like, and said Aqua
  gets "almost all the weight". Both replaced with measured numbers. The onset rule now also uses the first MODIS
  archive version that appears after 2020 (`61.03` from 2023-01-01), taking the earlier of that and the measured
  overpass drift.
- **Plan 009**: no longer shows `inside_interval`; shows the version change next to the overpass chart.

## Not re-checked

B9, B10, B13, B16, B18, B21–B24 were read only as far as needed to call them DEFER. C5/C6 were not re-audited.
Nothing was run against the live site in this review.

## Note on `docs/` being ignored

The local `.gitignore` change (uncommitted) ignores `docs/`. Tracked files in `docs/readme/` stay tracked, but
**new** files under `docs/` are ignored — including the deliverables of plan 007 (`docs/investigations/`) and plan
013 (`docs/demo/`), and any new README figure. Before those plans run, the team should either change the rule to
```
docs/*
!docs/readme/
!docs/demo/
!docs/investigations/
```
or write those deliverables elsewhere. Executors working in a fresh worktree also will not see `docs/plans/`; hand
them the plan file directly.
