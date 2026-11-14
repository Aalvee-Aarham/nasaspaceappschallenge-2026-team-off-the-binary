"""Measured answers to two questions raised in nasa/spaceapps discussion #1786, from the cached FIRMS rows.

1. Scan angle: MODIS pixels grow from 1 km at nadir to about 2 x 4.8 km at the swath edge (VIIRS 375 m to about 0.8 km).
   A ratio of totals absorbs that only if the share of detections seen near the edge stays the same year to year.
   We split each sensor's detections at its own median along-scan pixel size and measure the yearly edge share.
2. Single-sensor detections: how many Aqua MODIS detections have a Suomi-NPP VIIRS detection within about 1 km
   (the 3 x 3 block of 0.01-degree cells) on the same day and pass, and the reverse, with their FRP.

Vegetation-class rows only (type 1-3 dropped, confidence filter as in the build), standard processing,
2012-2020 (both satellites, before Aqua's drift). Writes data/regions/discussion_checks.json.
Run: python scripts/discussion_checks.py   (needs the cache from python -m kw.firms)
"""
import datetime as dt
import json
import statistics as st
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import duckdb  # noqa: E402

from kw.firms import CACHE, CONF_SQL, DATA  # noqa: E402

YEARS = range(2012, 2021)
OUT = DATA / "regions" / "discussion_checks.json"


def rows(con, area):
    files = [(CACHE / area / f"{y}.parquet").as_posix() for y in YEARS if (CACHE / area / f"{y}.parquet").exists()]
    if len(files) < len(YEARS):
        return False
    con.execute(f"""CREATE OR REPLACE TEMP TABLE d AS
        SELECT CASE WHEN sensor = 'MODIS' THEN 'aqua' ELSE 'snpp' END AS s, year(acq_date) AS y, acq_date, daynight,
               scan, frp, CAST(floor(lat * 100) AS INT) AS gy, CAST(floor(lon * 100) AS INT) AS gx
        FROM read_parquet({files})
        WHERE ((sensor = 'MODIS' AND satellite = 'Aqua') OR sensor = 'VIIRS_SNPP')
          AND coalesce(type, 0) NOT IN (1, 2, 3) AND quality <> 'nrt' AND {CONF_SQL}""")
    return True


def scan_check(con):
    out = {}
    for s in ("aqua", "snpp"):
        med = con.execute("SELECT median(scan) FROM d WHERE s = ?", [s]).fetchone()[0]
        yearly = con.execute("SELECT y, avg((scan > ?)::INT), count(*) FROM d WHERE s = ? GROUP BY y ORDER BY y",
                             [med, s]).fetchall()
        shares = [r[1] for r in yearly if r[2] >= 50]  # a year with a handful of detections says nothing
        out[s] = {"median_scan_km": round(med, 3), "years": len(shares),
                  "edge_share_min": round(min(shares), 3) if shares else None,
                  "edge_share_max": round(max(shares), 3) if shares else None,
                  "edge_share_sd_pp": round(100 * st.pstdev(shares), 1) if len(shares) > 1 else None}
    # Yearly Suomi-NPP / Aqua ratio, all pixels and inner/outer halves of each swath
    ma, mv = out["aqua"]["median_scan_km"], out["snpp"]["median_scan_km"]
    rat = con.execute("""SELECT y,
        count(*) FILTER (WHERE s = 'snpp') / nullif(count(*) FILTER (WHERE s = 'aqua'), 0),
        count(*) FILTER (WHERE s = 'snpp' AND scan <= ?) / nullif(count(*) FILTER (WHERE s = 'aqua' AND scan <= ?), 0),
        count(*) FILTER (WHERE s = 'snpp' AND scan > ?) / nullif(count(*) FILTER (WHERE s = 'aqua' AND scan > ?), 0),
        count(*) FILTER (WHERE s = 'aqua')
        FROM d GROUP BY y ORDER BY y""", [mv, ma, mv, ma]).fetchall()
    rat = [r for r in rat if r[4] >= 50 and None not in r[1:4]]

    def cv(v):
        return round(st.pstdev(v) / st.mean(v), 3) if len(v) > 1 and st.mean(v) else None
    out["ratio"] = {"years": [r[0] for r in rat], "all": [round(r[1], 2) for r in rat],
                    "inner": [round(r[2], 2) for r in rat], "outer": [round(r[3], 2) for r in rat],
                    "cv_all": cv([r[1] for r in rat]), "cv_inner": cv([r[2] for r in rat]), "cv_outer": cv([r[3] for r in rat])}
    return out


def match_check(con):
    # Cells within 1 cell (about 1.1 km) of each detection, same day and pass, for the other sensor
    con.execute("""CREATE OR REPLACE TEMP TABLE cells AS
        SELECT DISTINCT s, acq_date, daynight, gy + dy AS gy, gx + dx AS gx
        FROM d, (SELECT unnest([-1, 0, 1]) AS dy), (SELECT unnest([-1, 0, 1]) AS dx)""")
    out = {}
    for s, other in (("aqua", "snpp"), ("snpp", "aqua")):
        n, matched, frp_m, frp_u = con.execute(f"""
            SELECT count(*), count(c.s), median(d.frp) FILTER (WHERE c.s IS NOT NULL), median(d.frp) FILTER (WHERE c.s IS NULL)
            FROM d LEFT JOIN cells c ON c.s = '{other}' AND c.acq_date = d.acq_date AND c.daynight = d.daynight
                                      AND c.gy = d.gy AND c.gx = d.gx
            WHERE d.s = '{s}'""").fetchone()
        out[s] = {"detections": n, "seen_by_other": matched, "share_seen_by_other": round(matched / n, 3) if n else None,
                  "frp_median_matched_mw": round(frp_m, 1) if frp_m is not None else None,
                  "frp_median_alone_mw": round(frp_u, 1) if frp_u is not None else None}
    return out


def main():
    index = json.loads((DATA / "regions" / "index.json").read_text(encoding="utf-8"))["regions"]
    con = duckdb.connect()
    areas = []
    for r in index:
        if not r.get("preset") or not rows(con, r["id"]):
            continue
        areas.append({"id": r["id"], "name": r["name"], "scan": scan_check(con), "match": match_check(con)})
        print(r["id"], "done", flush=True)
    try:
        code = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        code = None
    OUT.write_text(json.dumps({
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "code_version": code,
        "period": [YEARS[0], YEARS[-1]], "filters": "vegetation class (FIRMS type 1-3 dropped), MODIS confidence >= 30, "
        "VIIRS not low, standard processing; Aqua MODIS and Suomi-NPP VIIRS only",
        "match_window": "same acq_date and day/night pass, within the 3 x 3 block of 0.01-degree cells (about 1.1 km)",
        "areas": areas}, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
