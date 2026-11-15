"""Would another calibration be more accurate? Held-out tests of the alternatives we considered.

    cd server && python ../scripts/validation/calibration_variants.py

Reads the raw FIRMS cache (data/cache, as kw.build does) and scores, on months the calibration never saw:

A. After MODIS: NOAA-20 alone predicting Aqua MODIS in 2021-2022 (before Aqua's measured drift onset), fitted on
   2018-05..2020-12. The published chain (NOAA-20 -> Suomi-NPP -> Aqua) against a direct NOAA-20 -> Aqua link and
   the geometric mean of the two, each with the ratio per calendar month or one ratio.
B. The MODIS-denial test (rebuild from VIIRS alone after MODIS "ends") with three training cut-offs, 2015, 2016 and
   2017, for: the published ratio per calendar month (shrunk), one ratio per area, a per-link choice between the two
   from a held-out split inside the training years, and recency-weighted totals (two-year half-life).

Metrics: bias of the test-period total (%) and mean absolute log error per month (every month weighs the same).
Fail-closed: an area without a raw cache stops the script with the reason; nothing is written.
Writes data/validation/calibration_variants.json. Nothing in the published record changes.
"""
import datetime as dt
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
import duckdb  # noqa: E402

from kw import build as B, science as sc  # noqa: E402
from kw.firms import CACHE  # noqa: E402
from kw.regions import PRESETS  # noqa: E402

OUT = ROOT / "data" / "validation" / "calibration_variants.json"
CUTOFFS = ("2015-12", "2016-12", "2017-12")
MODES = ("per_month", "one_ratio", "chosen_per_link", "recency_weighted")


def _prev(k):
    y, m = int(k[:4]), int(k[5:7])
    return f"{y - (m == 1)}-{12 if m == 1 else m - 1:02d}"


def _fit(agg, keys, cov, q, src, ref, a, b, mode):
    P = lambda x, y: B._pairs(agg, keys, cov, "veg", q, src, ref, x, y)
    pairs = P(a, b)
    if mode == "recency_weighted":   # ratio of weighted totals, half-life two years back from the window end
        ks = [k for i, k in enumerate(keys) if a <= k <= b and cov[src][i] >= B.TRAIN_COVERAGE and cov[ref][i] >= B.TRAIN_COVERAGE]
        yb = int(b[:4]) + int(b[5:7]) / 12
        w = [0.5 ** ((yb - (int(k[:4]) + int(k[5:7]) / 12)) / 2) for k in ks]
        pairs = [(m, r * x, s * x) for (m, r, s), x in zip(pairs, w)]
    f = sc.ratio_calibration(pairs)
    if mode == "chosen_per_link" and f["calibrated"]:   # inner split: first 60% of the window fits, last 40% scores
        ks = [k for k in keys if a <= k <= b]
        cut = ks[int(len(ks) * 0.6)]
        tr, te = sc.ratio_calibration(P(a, _prev(cut))), P(cut, b)
        if tr["calibrated"] and te:
            err = lambda pred: statistics.fmean(abs(p - r) for p, (_, r, _) in zip(pred, te))
            if err([tr["pooled"] * s for _, _, s in te]) <= err([tr["beta"][m - 1] * s for m, _, s in te]):
                f = {**f, "beta": [f["pooled"]] * 12}
    return f


def _load(rid):
    if not (CACHE / rid).exists():
        sys.exit(f"no raw FIRMS cache for {rid} in {CACHE}: run `python -m kw.firms` first")
    con = duckdb.connect()
    B._load_aqua_onset()
    B._load(con, rid)
    through = con.execute(f"SELECT max(acq_date) FROM read_parquet('{B.sensor_days().as_posix()}')").fetchone()[0]
    start = dt.date.fromisoformat(B.SENSOR_START["MODIS"])
    keys = sc.periods(start, through)
    cov, _ = B._coverage(con, keys, False, through, first=start)
    return B._aggregate(con, False), keys, cov


def _score(pred, truth):
    return {"bias_pct": sc.metrics(pred, truth)["bias_pct"], "log_mae": sc.log_mae(pred, truth), "n": len(truth)}


def after_modis(agg, keys, cov):
    idx = [i for i, k in enumerate(keys) if "2021-01" <= k <= "2022-12"
           and cov["MODIS_A"][i] >= B.TRAIN_COVERAGE and cov["VIIRS_NOAA20"][i] >= B.TRAIN_COVERAGE]
    truth = [0.0] * len(idx)
    pred = {f"{r}/{k}": [0.0] * len(idx) for r in ("chain", "direct", "mean") for k in ("per_month", "one_ratio")}
    for q in ("det_D", "det_N"):
        P = lambda s, r, a, b: sc.ratio_calibration(B._pairs(agg, keys, cov, "veg", q, s, r, a, b))
        s2a, n2s, n2a = P("VIIRS_SNPP", "MODIS_A", "2012-02", "2020-12"), P("VIIRS_NOAA20", "VIIRS_SNPP", "2018-05", "2020-12"), \
            P("VIIRS_NOAA20", "MODIS_A", "2018-05", "2020-12")
        for j, i in enumerate(idx):
            m = sc.calendar_month(keys[i])
            src = B._value(agg, "veg", "VIIRS_NOAA20", keys[i], q)[0] / cov["VIIRS_NOAA20"][i]
            truth[j] += B._value(agg, "veg", "MODIS_A", keys[i], q)[0] / cov["MODIS_A"][i]
            for k, g in (("per_month", lambda f: f["beta"][m - 1]), ("one_ratio", lambda f: f["pooled"])):
                c, d = g(n2s) * g(s2a), g(n2a)
                pred[f"chain/{k}"][j] += c * src
                pred[f"direct/{k}"][j] += d * src
                pred[f"mean/{k}"][j] += math.sqrt(c * d) * src
    return {k: _score(p, truth) for k, p in pred.items()}


def denial(agg, keys, cov, end, mode):
    cfg = {}
    for q in ("det_D", "det_N"):
        fits = {src: _fit(agg, keys, cov, q, src, ref, full[0], min(full[1] or keys[-2], end if ref == "MODIS_A" else "2020-12"), mode)
                for src, ref, full, *_ in B.LINKS}
        cfg[q] = {"to_ref": B._chain(fits, "pooled" if mode == "one_ratio" else "beta")}
    idx = [i for i, k in enumerate(keys) if f"{int(end[:4]) + 1}-01" <= k <= "2020-12" and cov["MODIS_A"][i] >= B.TRAIN_COVERAGE]
    truth = [sum(B._value(agg, "veg", "MODIS_A", keys[i], f"det_{dn}")[0] for dn in B.DN) / cov["MODIS_A"][i] for i in idx]
    v, *_ = B._hotspots(agg, keys, cov, "veg", cfg, set(B.VIIRS))
    return _score([v[i] or 0.0 for i in idx], truth)


def _summary(rows):
    return {"median_abs_bias_pct": round(statistics.median(abs(r["bias_pct"]) for r in rows), 1),
            "mean_abs_bias_pct": round(statistics.fmean(abs(r["bias_pct"]) for r in rows), 1),
            "mean_log_mae": round(statistics.fmean(r["log_mae"] for r in rows), 3)}


def main():
    areas = {}
    for rid in PRESETS:
        agg, keys, cov = _load(rid)
        areas[rid] = {"after_modis": after_modis(agg, keys, cov),
                      "denial": {end: {mode: denial(agg, keys, cov, end, mode) for mode in MODES} for end in CUTOFFS}}
        print(f"{rid} done", flush=True)
    first = next(iter(areas.values()))
    try:
        code = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        code = None
    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "script": "scripts/validation/calibration_variants.py", "code_version": code,
        "question": "Would another calibration be more accurate than the published one, on months it never saw?",
        "summary": {
            "after_modis_2021_2022": {k: _summary([a["after_modis"][k] for a in areas.values()]) for k in first["after_modis"]},
            "denial": {end: {mode: _summary([a["denial"][end][mode] for a in areas.values()]) for mode in MODES} for end in CUTOFFS},
        },
        "areas": areas,
        "published_method": "chain/per_month and per_month: the ratio per calendar month, shrunk toward one ratio by empirical Bayes",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    os.replace(tmp, OUT)
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
