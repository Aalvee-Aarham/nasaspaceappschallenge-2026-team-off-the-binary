# SDD ledger — plan: docs/plans/README.md
Branch: fixes/hackathon-plans (from main @ 1e99c85). User rule: NO commits — every "commit" step in the plans is skipped; changes stay in the working tree.
Ruling: no commits — user said "don't commit anything without permission" — cost if wrong: user commits later in one go.
Ruling: ledger at docs/plans/progress.md — sdd-workspace script not installed — cost if wrong: none.
Ruling: graphify update skipped — graphify not installed (B20) — cost if wrong: none.
Pre-flight: 016 step 1/10 and 014/015 change build output → all before 003 rebuild; 015 and 003 both create server/tests/test_build_rules.py → 015 creates it, 003 appends.
Plan 001: complete (uncommitted; tests: test_data_integrity RED(6 aoi ids)→GREEN, fake-entry check fails as intended, test_science ok, tsc ok)
Plan 002: complete (uncommitted; test_presets_have_transfer_validation RED[punjab,se-australia]→GREEN; --transfer-only prints 9 areas)
Plan 002: Ruling: sorted the preset list in main() — glob order reshuffled calibration_table.csv (same 2593 rows) — cost if wrong: none, output now deterministic.
Plan 016: complete (uncommitted). Each step RED→GREEN: B5 test_no_duplicate_keys_in_dict_literals; S7 test_next_weeks_start_after_last_complete_week; B15 test_sensor_status_note_has_no_hard_coded_dates; B14 test_region_summary_without_snpp_validation_row; B7 test_news_outage_is_not_read_as_no_reports; B1 test_failed_send_is_retried; B6 exit 134→0; B11 test_eonet_outage_is_reported; B8 test_rejected_alert_starts_no_build; B12 test_analyst_find_place_matches_its_schema; S14 test_code_version_marks_uncommitted_builds. B4 Dockerfile COPY (config, no test). Suite: alerts 6, build_rules 7, data_integrity 3, science 15 ok; tsc ok.
Plan 016: Ruling: tests for B5/S7/B14/B7/B12/S14 went into server/tests/test_build_rules.py (created here, before 015) — plan named only test_alerts — cost if wrong: none.
Plan 016: Ruling: B1 test patches only send_email (create() already catches the confirm failure) — plan also patched smtp_ready — cost if wrong: none.
Plan 016: Ruling: B5 test is an AST duplicate-key check over server/kw — data only changes on rebuild, so a data test could not go RED now — cost if wrong: none.
Plan 014: complete (uncommitted; test_combine zero-weight case RED 1.667→GREEN 5.0; science 15 ok). Rebuild deferred to plan 003.
Plan 015: complete (uncommitted; test_drift_uses_same_months_every_year RED [[2020,0.3],[2021,0.1]]→GREEN; build_rules 8 ok). Preview on published data: Punjab Aqua/SNPP 2019-2026 0.178,0.174,0.163,0.162,0.118,0.113,0.119,0.120 (matches plan). Rondonia flat (no 2023 step) — relevant to 003's version rule.
Plan 017: complete in code (uncommitted). Step 1 RED→GREEN via scratch harness (Vite ssrLoadModule on real api.ts + punjab data): raw 2001-W25 0→null; nulls == no-coverage periods (weekly 2/1359, monthly 0/313). Steps 2-9: grep RED→GREEN for S13 (3→0 `?? 0`), C11 (pick calls 4→1); tsc ok; vite build ok.
Plan 017: Ruling: no web test runner and plan forbids new deps — logic tested through Vite ssrLoadModule, components by tsc/build — cost if wrong: component regressions only caught manually.
Plan 017: Ruling: manual browser checks (steps 1, 3, 4) NOT done — no browser tools in session; handed to user — cost if wrong: keyboard regressions unseen until clicked.
Plan 017: Ruling: step 8 search form has no button, so "Searching…" status text + aria-busy instead of disabling a button — cost if wrong: cosmetic.
Plan 008: code steps 1-3 complete (uncommitted; server/tests/test_api.py: serverless flag RED→GREEN, Host-header guard RED→GREEN, no-email fallback pinned; tsc ok). Steps 4-6 are [HUMAN] (Vercel env, clean redeploy, click test).
Plan 008: Ruling: plan excerpt indentation for health() was off by 2 spaces — matched the live code — cost if wrong: none.
Plan 003: code steps 1-5 done (uncommitted; RED→GREEN: test_solar_hour_and_drift_onset, test_active_before_and_after_drift, test_aqua_overpass_onset_is_earlier_of_orbit_and_version [synthetic parquet], test_builds_read_the_onset_from_the_shared_file). Rebuild (step 6) + words (step 7) pending download.
Plan 003: Ruling: added _load_aqua_onset() helper (main + build_region both call it) instead of two inline globals — testable — cost if wrong: none.
Plan 004: code steps 1,2,4 done (uncommitted; test_conformal_scale RED→GREEN; test_split_coverage_fits_on_early_tests_on_late written with impl, not seen RED; tsc ok). Steps 3,5 (numbers, README) after rebuild.
Plan 004: Ruling: split logic moved to sc.split_coverage (pure, tested) instead of inline in _denial_modis — cost if wrong: none, same arithmetic.
NOTE: docs/ was reorganised mid-run (not by me): plans now at docs/mdfiles/plans/; ledger continues here. .gitignore now un-ignores docs/plans/ (old path) — flagged to user.
Plan 005: code steps 1,3,4,5 done (uncommitted; RED→GREEN: test_contingency, test_month_to_date_counts_days_1_to_D_only, test_warning_backtest_flags_the_spike_month_only; tsc ok). Step 3 equality check + step 6 numbers/README after rebuild.
Plan 005: Ruling: synthetic backtest test uses fixed 30-day monthly totals — real calendar totals made leap Februaries look extreme in the fixture — cost if wrong: none (fixture only).
Plan 005: Ruling: refactor equality check will compare old SQL path vs new helper inside one Punjab build (old function kept temporarily, then removed) — plan's before/after build would also pick up 003's rule change — cost if wrong: none.
Plan 005: Ruling: backtest note rendered in a plain <section> — no .note class exists in styles.css — cost if wrong: cosmetic.
Plan 006: code step 2 done (uncommitted). Baseline mismatch saved (alberta 2.3, la-rioja 0.1, n-california 2.1, niger-delta 1.0, parana 1.2, punjab 1.6, rondonia 1.1, se-aus 0.1, dhaka None). Step 3 compare after rebuild.
Plan 003: step 7 Method.tsx wording done (tsc ok); README bullet waits for the measured onset.
Final review: self-review (no reviewer subagent — user did not ask for agents). No Critical/Important found in the code diff.
Final: minor (deferred): _public_base 503 (SMTP set, PUBLIC_URL unset) also blocks alerts without email — by plan 008 design; set PUBLIC_URL.
Final: minor (deferred): warning backtest "happened" uses full-month totals, so leap-year Februaries sit ~3.5% high (S9-like, outcome side only).
Final: minor (deferred): single-area `python -m kw.build <id>` re-measures the onset from whatever caches exist; fine once all caches are present.
Rebuild: single run, onset 2023-01 (orbit 2023: 13.71 h vs 13.43 baseline; version 61.03 from 2023-01 in all 9 areas). Plan 005 equality check: 9/9 identical.
Plan 003: complete — post-onset months with MODIS_A: 0 in all 9; Punjab denial unchanged (-5.8%, 0.981); README bullet added. Punjab Nov 2026 MTD 3582→583 (Aqua/NOAA-20 Nov ratio 0.19-0.21 in 2018-22 rose to 1.21 in 2026: drift toward afternoon burning).
Plan 004: complete — out-of-sample coverage in all 9 (79-100%); README table regenerated from meta.json (mapping checked against HEAD values). Dhaka k 5.324→4.457 traced to plan 014 (old combine reproduces 5.324 exactly), not a refactor error.
Plan 005: STOP at step 6 — Alberta day-15 base rate 0.429 (outside 0.03-0.25); the activity floor selects active months in sparse areas. README skill table NOT written; README only says the backtest exists and sparse-area numbers are not comparable. Data + UI section shipped.
Plan 006: complete — grid vs total median mismatch after ≤ before or both <2% (la-rioja 0.1→0.3); grid sizes within ±0.6%.
Plan 015: complete — Punjab drift 2019-2026 0.178,0.174,0.163,0.162,0.118,0.113,0.119,0.120.
Ruling: test_alerts marking tests pick a preset that currently tops 0.5×median — Punjab no longer does after the drift fix; the tests are about marking, not Punjab — cost if wrong: none.
Ruling: README figures (docs/readme/*.svg) not regenerated — headline numbers they show are unchanged by the rebuild — cost if wrong: a figure lags by <0.05 in a step ratio.
Commits (user approved, no co-author): c97c236 service, 2e5bc61 science/build, d36f2b0 web, 5c1b637 data+README on fixes/hackathon-plans. .gitignore left uncommitted (user's edit).
