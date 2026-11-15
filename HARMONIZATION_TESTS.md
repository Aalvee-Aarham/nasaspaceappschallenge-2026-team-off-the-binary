# What we tried, and what failed

A failed test is a finding. This file lists every alternative we tested against the published Kiln Watch method, the
checks the record itself failed, and what we decided. Every number comes from a committed file you can regenerate; the
file is named under each test.

**The published method** (`server/kw/science.py`, `server/kw/build.py`): for each pair of satellites, one ratio of
detection totals per calendar month, shrunk toward the all-year ratio by empirical Bayes, day and night separately,
chained onto the Aqua MODIS 2002–2020 scale (Terra → Aqua, Suomi-NPP → Aqua, NOAA-20 → Suomi-NPP, NOAA-21 → NOAA-20).

**How alternatives are judged.** Only on months the calibration never saw. The main test is MODIS denial: pretend MODIS
ended, rebuild the following years from VIIRS alone, and compare with what Aqua really recorded. Two scores, because they
disagree:

- *Total bias*: how far off the whole test period's total is (%).
- *Monthly log error*: mean absolute log error per month, every month weighted the same (0 = perfect).

---

## 1. Alternatives to the calibration

Source: `data/validation/calibration_variants.json`, made by `scripts/validation/calibration_variants.py`
(9 areas; MODIS "ends" after 2015, 2016 or 2017 and the record is rebuilt to 2020).

| Variant | Train to 2015: bias / log error | Train to 2016 | Train to 2017 | Verdict |
|---|---|---|---|---|
| **Published: ratio per calendar month, shrunk** | 11.4% / 0.400 | 8.8% / 0.386 | 11.4% / 0.394 | kept |
| One ratio per area | 9.7% / 0.433 | 7.6% / 0.420 | 10.8% / 0.430 | better totals, clearly worse months |
| Choose per link from a split inside the training years | 9.4% / 0.393 | 7.9% / 0.385 | 11.6% / 0.393 | wins once, ties once, loses once |
| Weight recent training years more (2-year half-life) | 11.5% / 0.402 | 7.9% / 0.382 | 11.3% / 0.395 | no consistent gain |

Bias is the mean absolute total bias over the 9 areas.

**Finding.** A single ratio per area gets the multi-year total slightly closer, but it misses the seasonal shape: its
monthly error is 8–9% higher at every cut-off. The two "best of both" fixes help at one cut-off and not at the others, so
on 9 areas they cannot be told apart from luck. We kept the published method and say plainly that it is not yet better
on totals.

## 2. After MODIS: chain or direct link?

Source: same file, `summary.after_modis_2021_2022`. NOAA-20 alone predicts Aqua for 2021–2022, when Aqua still flew its
old orbit. Every link is fitted on 2018-05 to 2020-12 only.

| Route from NOAA-20 to the Aqua scale | Mean total bias | Monthly log error |
|---|---|---|
| **Published chain, NOAA-20 → Suomi-NPP → Aqua, ratio per month** | 9.3% | **0.345** |
| Direct NOAA-20 → Aqua, ratio per month | 9.4% | 0.373 |
| Geometric mean of the two | 9.9% | 0.354 |
| Published chain, one ratio | 13.0% | 0.373 |
| Direct link, one ratio | 11.9% | 0.373 |

**Finding.** The chain does not "close": fitted over the same months, the direct ratio and the chain disagree by up to
90% at night (`closure` in each `meta.json`). The obvious fix, using the direct link, still predicts held-out Aqua months
worse. So the mismatch stays in the error bars instead of being "fixed" by a route that tests worse. This is also the
strongest evidence for the per-month ratio: after MODIS it beats one ratio on both scores.

## 3. A fire-size term (the main idea in other detection-curve methods)

Source: `transfer_validation.fire_size_term` in each `data/regions/<area>/meta.json`.

MODIS misses small fires, so the VIIRS/MODIS ratio could follow the month's fire mix. We added the month's mean
Suomi-NPP fire power per detection as a term in the Suomi-NPP → Aqua ratio, fitted on 2012–2016 and scored on 2017–2020.
This is the core of detection-curve approaches such as FlameSeek, which model the chance that MODIS detects a fire of a given
fire power.

| | Ratio per month (published) | Plus fire-size term |
|---|---|---|
| Mean monthly log error, 9 areas | **0.459** | 0.460 |
| Areas where it helps | – | 3 of 9 (Fort McMurray 0.789 → 0.700, south-east Australia 0.399 → 0.334, Rondônia 0.304 → 0.291) |
| Worst cases | – | Paraná Delta 0.384 → 0.451, Niger Delta 0.423 → 0.474 |

**Finding.** The size effect is real in big-fire areas, but its slope fitted on 2012–2016 does not hold in 2017–2020
elsewhere. Not adopted. An area-gated version is an open next step, to be judged by the same test.

## 4. One calibration for every area?

Source: `transfer_validation` in each `meta.json` (a calibration fitted on the other areas, applied to this one).

| Area | Bias, calibrated here | Bias, borrowed from other areas |
|---|---|---|
| Dhaka brick-kiln belt | +28.3% | **+215.5%** |
| Fort McMurray | −25.3% | +60.9% |
| Chilecito, La Rioja | −5.7% | +56.2% |
| Northern California | +21.0% | +48.3% |
| South-east Australia | +28.2% | +39.4% |
| Punjab | −5.7% | −12.2% |
| Rondônia | +3.7% | −20.2% |
| Paraná Delta | +36.9% | +9.3% |
| Niger Delta | +3.3% | −1.8% |

**Finding.** The MODIS/VIIRS ratio depends on the place (fire size, cloud, land cover), so one global ratio does not
work. Every new area is calibrated on its own detections. That is why building an area takes 5 to 10 minutes instead of
being instant.

## 5. Checks the record itself failed or only half passed

| Check | Result | Source |
|---|---|---|
| Early warning against a "last month was high" reference, scored only on the days after the 15th | The rule wins in Alberta (0.59 vs 0.22), Punjab (0.38 vs 0.11) and south-east Australia (0.44 vs 0.29), ties in Northern California (0.28 vs 0.26), loses in Paraná (0.47 vs 0.61), Rondônia (0.12 vs 0.29) and the Niger Delta (0.06 vs 0.15) | `warning_backtest.by_day.15` in `meta.json` |
| The same rule scored against the whole month | Looked much better (0.54 to 0.82), because the month includes the 15 days the rule had already seen. We now publish both | same |
| Agreement with NASA burned area (MCD64A1) | Median monthly ρ 0.49 harmonized vs 0.37 raw, but harmonized is at least as good as raw in only 4 of 7 areas. Across 2012, burned area moves ×0.72 while the harmonized record moves ×1.03: unexplained | `data/validation/burned_area.json` |
| Can FIRMS find brick kilns? | No. A VIIRS hotspot lies within 500 m of a mapped kiln for 4.6% of kilns, against 4.2% for random places. Only 6 of 109 FIRMS persistent heat sources sit on a mapped kiln | `data/validation/kilns_dhaka-kilns.json` |
| 95% intervals before widening | Cover only 35% (La Rioja) and 42% (Dhaka) of held-out months: the variance model is wrong in sparse areas. After split-conformal widening and an out-of-sample check, 79% to 100% | `denial.modis_ends_2016` in `meta.json` |
| NOAA-21 step | 0.63 (Rondônia) to 1.34 (La Rioja), wider than Suomi-NPP's 0.93 to 1.18. NOAA-21 arrived while Aqua was drifting, so the two changes are mixed | `steps.VIIRS_NOAA21` in `meta.json` |
| Outlook flag after Aqua | The "above normal" flag from NOAA-20 agrees with Aqua's own on only 41% of cells, though the total is off by +0.9% and the ranking agrees at ρ = 0.84: the two satellites sample different small fires | the outlook build, summarised in the README |

## 6. Checks it passed

Passes count only next to the failures above.

| Check | Result | Source |
|---|---|---|
| Raw jump at Suomi-NPP's arrival (2012) | Raw counts ×3.5 to ×10.6; harmonized ×0.93 to ×1.18 | `steps.VIIRS_SNPP` |
| Placebo steps (fake "launch" dates) | Harmonized excess stays near 1 (Punjab 0.99–1.01, south-east Australia 1.00–1.03, Dhaka 0.84–1.54 with few fires) | `placebo` |
| MODIS denial, uncalibrated vs ours | Uncalibrated VIIRS is off by +470% to +1,767%; ours within 10% in seven of nine areas | `denial.modis_ends_2016` |

## 7. Tried in exploration, not yet in a committed script

- **Shrinkage that accounts for over-dispersed counts** (each month's sampling variance includes the residual variance,
  not only Poisson counting noise). In a local run it changed held-out errors by under 0.01 in log error in every area,
  so the under-shrinkage we suspected is not what limits the method. No published numbers until it is in the script.

## How to rerun

```
cd server
python -m kw.firms && python -m kw.build              # the record and every meta.json test
python ../scripts/validation/calibration_variants.py  # sections 1 and 2 (needs the raw cache from kw.firms)
python ../scripts/validation/burned_area.py           # burned area
python ../scripts/validation/kilns.py                 # kilns
```
