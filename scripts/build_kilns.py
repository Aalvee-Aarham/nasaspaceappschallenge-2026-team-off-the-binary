"""Kiln evidence for the Dhaka brick-kiln belt: a published kiln inventory, what FIRMS sees of it, and night lights.

FIRMS barely sees kilns (a kiln is a small steady heat source, and MODIS pixels are 1 km), so the kiln layer is built
from independent sources and FIRMS is measured against them, never used to find kilns:

  inventory    Sentinel-2 kiln detections for Bangladesh, dry season 2024-25 (deluair/bangladesh-brick-kilns v0.1.0,
               CC BY-NC 4.0). `skdb_match_id` marks detections that fall on a human-labelled kiln in SentinelKilnDB.
  FIRMS        share of mapped kilns with a VIIRS / MODIS detection within 500 m / 1 km that season, against random
               places far from any kiln, and how many FIRMS persistent heat sources sit on a mapped kiln.
  night lights NASA Black Marble VNP46A2 (Earth Engine): kiln-season (Dec-Feb) against monsoon (Jul-Aug) brightness.
               Kilns fire in the dry months, so lamps and night shifts should raise brightness there.

Build-time only (needs earthengine-api and EE_PROJECT in .env, like build_burned.py). Needs the raw FIRMS cache of the
area (python -m kw.firms). Writes data/regions/dhaka-kilns/kilns.json.   python scripts/build_kilns.py
"""
import datetime as dt
import json
import math
import os
import random
import urllib.request
from pathlib import Path

import duckdb
import ee

ROOT = Path(__file__).resolve().parents[1]
AREA = "dhaka-kilns"
CACHE = ROOT / "data" / "cache" / "kilns"
URL = "https://github.com/deluair/bangladesh-brick-kilns/releases/download/v0.1.0/detections_2024-25.parquet"
SEASON = ("2024-11-01", "2025-04-30")      # the dry season the inventory imagery covers
DRY, WET = ("2024-12-01", "2025-03-01"), ("2025-07-01", "2025-09-01")  # kilns fire Nov-May; the monsoon stops them
URBAN = 15.0                                # nW/cm2/sr in the monsoon: city lights drown a kiln's, so the cell says nothing
NULLS, SEED = 600, 7
RADIUS_V, RADIUS_M = 500, 1000              # metres: VIIRS 375 m pixels, MODIS 1 km pixels


def load_env():
    f = ROOT / ".env"
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def deg(m, lat):
    return m / 111320, m / (111320 * math.cos(math.radians(lat)))


def haversine(a, b):
    p = math.pi / 180
    h = math.sin((b[1] - a[1]) * p / 2) ** 2 + math.cos(a[1] * p) * math.cos(b[1] * p) * math.sin((b[0] - a[0]) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def main():
    load_env()
    folder = ROOT / "data" / "regions" / AREA
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    w, s, e, n = meta["bbox"]
    CACHE.mkdir(parents=True, exist_ok=True)
    inv_file = CACHE / "detections_2024-25.parquet"
    if not inv_file.exists():
        urllib.request.urlretrieve(URL, inv_file)
    con = duckdb.connect()
    inv = con.execute(f"""SELECT lon, lat, type, score, skdb_match_id IS NOT NULL AS labelled
                          FROM read_parquet('{inv_file.as_posix()}') WHERE lon BETWEEN {w} AND {e} AND lat BETWEEN {s} AND {n}
                          ORDER BY score DESC""").fetchall()
    labelled = [r for r in inv if r[4]]
    print(len(inv), "inventory detections in the box,", len(labelled), "on a labelled kiln", flush=True)

    # random places at least 1 km from any mapped kiln: the background FIRMS and night lights are compared with
    rnd, rng = [], random.Random(SEED)
    while len(rnd) < NULLS:
        p = (rng.uniform(w, e), rng.uniform(s, n))
        if all(abs(p[1] - r[1]) > 0.01 or abs(p[0] - r[0]) > 0.012 or haversine(p, r) > 1000 for r in inv):
            rnd.append(p)

    # FIRMS: detections within 500 m (VIIRS) or 1 km (MODIS) of each point during the dry season
    raw = [(ROOT / "data" / "cache" / AREA / f"{y}.parquet").as_posix() for y in (2024, 2025)]
    con.execute(f"""CREATE TABLE det AS SELECT lon, lat, sensor, confidence, confidence_pct FROM read_parquet({raw})
                    WHERE acq_date BETWEEN DATE '{SEASON[0]}' AND DATE '{SEASON[1]}'""")
    pts = [(i, r[0], r[1]) for i, r in enumerate(inv)] + [(len(inv) + i, p[0], p[1]) for i, p in enumerate(rnd)]
    con.execute("CREATE TABLE pts (id INT, lon DOUBLE, lat DOUBLE)")
    con.executemany("INSERT INTO pts VALUES (?, ?, ?)", pts)
    dlat, dlon = deg(RADIUS_V, (s + n) / 2)[0], deg(RADIUS_V, (s + n) / 2)[1]
    mlat, mlon = deg(RADIUS_M, (s + n) / 2)[0], deg(RADIUS_M, (s + n) / 2)[1]
    hit = {r[0]: r[1:] for r in con.execute(f"""
        SELECT p.id,
               count(*) FILTER (WHERE d.sensor <> 'MODIS' AND abs(d.lat - p.lat) < {dlat} AND abs(d.lon - p.lon) < {dlon}) AS v_any,
               count(*) FILTER (WHERE d.sensor <> 'MODIS' AND d.confidence <> 'l' AND abs(d.lat - p.lat) < {dlat} AND abs(d.lon - p.lon) < {dlon}) AS v_ok,
               count(*) FILTER (WHERE d.sensor = 'MODIS' AND abs(d.lat - p.lat) < {mlat} AND abs(d.lon - p.lon) < {mlon}) AS m_any
        FROM pts p JOIN det d ON abs(d.lat - p.lat) < {mlat} AND abs(d.lon - p.lon) < {mlon} GROUP BY p.id""").fetchall()}
    h = lambda i: hit.get(i, (0, 0, 0))  # noqa: E731
    share = lambda ids, j: round(100 * sum(h(i)[j] > 0 for i in ids) / max(1, len(ids)), 1)  # noqa: E731
    lab_ids = [i for i, r in enumerate(inv) if r[4]]
    nul_ids = list(range(len(inv), len(inv) + len(rnd)))
    firms = {"season": list(SEASON), "viirs_radius_m": RADIUS_V, "modis_radius_m": RADIUS_M,
             "mapped_kilns": {"n": len(lab_ids), "viirs_any_pct": share(lab_ids, 0), "viirs_not_low_pct": share(lab_ids, 1), "modis_any_pct": share(lab_ids, 2)},
             "random_places": {"n": len(nul_ids), "viirs_any_pct": share(nul_ids, 0), "viirs_not_low_pct": share(nul_ids, 1), "modis_any_pct": share(nul_ids, 2)},
             "note": "Random places are at least 1 km from every mapped kiln. VIIRS 'low' confidence detections are excluded in the not-low figure, as in the record."}

    # FIRMS persistent heat sources: how many sit on a mapped kiln?
    static = json.loads((folder / "static.json").read_text(encoding="utf-8"))
    near = []
    for pt in static["points"]:
        d = min(haversine((pt[0], pt[1]), (r[0], r[1])) for r in inv)
        near.append(d)
    firms["static_sources"] = {"n": len(near), "within_500m_of_mapped_kiln": sum(d <= 500 for d in near), "within_1km_of_mapped_kiln": sum(d <= 1000 for d in near),
                               "note": "FIRMS persistent heat sources (type 1-3, 0.01 degree cells) against every inventory detection."}

    # Black Marble night lights
    ee.Initialize(project=os.environ["EE_PROJECT"])
    band = "Gap_Filled_DNB_BRDF_Corrected_NTL"
    col = ee.ImageCollection("NASA/VIIRS/002/VNP46A2").select(band)
    img = col.filterDate(*DRY).mean().rename("dry").addBands(col.filterDate(*WET).mean().rename("wet"))
    allpts = [(r[0], r[1]) for r in inv] + rnd + [(p[0], p[1]) for p in static["points"]]
    feats = [ee.Feature(ee.Geometry.Point([x, y]).buffer(250), {"i": i}) for i, (x, y) in enumerate(allpts)]
    got = {}
    for k in range(0, len(feats), 800):
        for f in img.reduceRegions(ee.FeatureCollection(feats[k:k + 800]), ee.Reducer.mean(), 463).getInfo()["features"]:
            got[f["properties"]["i"]] = (f["properties"].get("dry"), f["properties"].get("wet"))
        print("night lights", min(k + 800, len(feats)), "/", len(feats), flush=True)
    ratio = lambda i: (got[i][0] + 0.5) / (got[i][1] + 0.5) if got.get(i) and None not in got[i] else None  # noqa: E731
    rural = lambda i: got.get(i) and got[i][1] is not None and got[i][1] < URBAN  # noqa: E731
    lab_r = [ratio(i) for i in lab_ids if rural(i)]
    nul_r = [ratio(i) for i in nul_ids if rural(i)]
    q75 = pct(nul_r, 0.75)
    night = {"band": f"VNP46A2 {band} (nW/cm2/sr)", "kiln_season": list(DRY), "monsoon": list(WET), "buffer_m": 250, "urban_cutoff": URBAN,
             "ratio": "(dry + 0.5) / (monsoon + 0.5)",
             "mapped_kilns_rural": {"n": len(lab_r), "median_ratio": round(pct(lab_r, 0.5), 3) if lab_r else None,
                                    "above_random_75th_pct": round(100 * sum(r > q75 for r in lab_r) / max(1, len(lab_r)), 1) if lab_r else None},
             "random_rural": {"n": len(nul_r), "median_ratio": round(pct(nul_r, 0.5), 3) if nul_r else None, "p75_ratio": round(q75, 3) if q75 else None},
             "note": "Cells brighter than 15 nW/cm2/sr in the monsoon are left out: city lights drown a kiln's. If kilns had no "
                     "effect, 25% would be above the random 75th percentile. Kilns cluster on the edges of towns, which also "
                     "brighten in the dry season, and random places include empty land, so this is consistent with kilns, "
                     "not proof of them."}

    static_out = []
    base = len(inv) + len(rnd)
    for j, pt in enumerate(static["points"]):
        static_out.append([pt[0], pt[1], pt[2], round(near[j]), None if ratio(base + j) is None else round(ratio(base + j), 2)])
    out = {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "area": AREA, "bbox": meta["bbox"],
           "inventory": {"source": "Bangladesh brick kilns from space (Sentinel-2 detector trained on SentinelKilnDB), dry season 2024-25",
                         "url": "https://github.com/deluair/bangladesh-brick-kilns", "license": "CC BY-NC 4.0",
                         "n_in_area": len(inv), "n_on_labelled_kiln": len(labelled),
                         "precision": "Its audit finds about 8 in 10 detections inside SentinelKilnDB's labelled footprints are kilns and about 2 in 10 outside; "
                                      "'labelled' here means the detection sits on a human-labelled kiln.",
                         "not_seen": "A cold kiln and a working kiln look alike from above, so these are kiln structures, not kilns in operation."},
           "firms": firms, "night_lights": night,
           "fields": ["lon", "lat", "type", "score", "labelled", "viirs_hits", "ntl_dry", "ntl_wet"],
           "kilns": [[round(r[0], 5), round(r[1], 5), r[2], round(r[3], 2), int(r[4]), h(i)[0],
                      None if not got.get(i) or got[i][0] is None else round(got[i][0], 2),
                      None if not got.get(i) or got[i][1] is None else round(got[i][1], 2)] for i, r in enumerate(inv)],
           "static_fields": ["lon", "lat", "detections", "metres_to_mapped_kiln", "night_light_ratio"], "static_sources": static_out,
           "caveat": "Kiln evidence comes from outside FIRMS. FIRMS is shown only to measure how little of the kiln belt it sees."}
    (folder / "kilns.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"firms": firms, "night_lights": night}, indent=1))


if __name__ == "__main__":
    main()
