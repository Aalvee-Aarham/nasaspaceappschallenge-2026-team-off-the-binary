"""Independent cross-check: do the published persistent-heat cells match the mapped brick kilns?

    python scripts/validation/kilns.py [region_id]        # default: dhaka-kilns

Compares the area's published FIRMS persistent-heat ("static") cells with the APAD inventory of
operating Bangladesh brick kilns (asset-data-igp, CC BY 4.0). The inventory is an independent
asset list, not FIRMS truth, and the test is a placement test: the observed cells are compared with
randomly placed cells of the same number in the same area, so "matches a kiln" is measured against
"would match by chance".

Fail-closed: if the inventory cannot be downloaded or parsed, or the area has no published cells, the
script stops with the exact blocker and writes no output. A negative result is written out in full.

Writes data/validation/kilns_<region>.json. Attribution travels with the numbers.
"""
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGIONS = ROOT / "data" / "regions"
OUT = ROOT / "data" / "validation"

APAD_URL = "https://assetdata-igp.s3.amazonaws.com/asset_igp_csvs/Brick_kilns_BAN_coal.csv"
APAD_SOURCE = {
    "name": "APAD / IGP asset-data-igp: Bangladesh brick kilns (Brick_kilns_BAN_coal.csv)",
    "url": APAD_URL,
    "registry": "https://registry.opendata.aws/asset-data-igp-brick-kilns-ban/",
    "licence": "CC BY 4.0",
    "licence_url": "https://creativecommons.org/licenses/by/4.0/",
}
RADII_KM = (0.5, 1.0, 2.0)
TRIALS = 400          # random placements of the same size in the same area
SEED = 20261114       # fixed, so the baseline is reproducible
EARTH_KM = 6371.0088


def fail(msg):
    print(f"kilns.py: {msg}", file=sys.stderr)
    sys.exit(1)


def bbox_area_km2(bbox):
    """Account for latitude: a degree of longitude shrinks by cos(mid-latitude)."""
    w, s, e, n = bbox
    return (e - w) * (n - s) * (111.32 ** 2) * math.cos(math.radians((s + n) / 2))


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


def fetch_inventory():
    """Download the APAD inventory; every failure stops the script."""
    req = urllib.request.Request(APAD_URL, headers={"User-Agent": "kiln-watch-validation/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        fail(f"cannot download the APAD inventory ({e}); no result written")
    text = raw.decode("utf-8-sig")
    if not text.startswith("id,lat,lon"):
        fail("the APAD download does not look like the expected CSV; no result written")
    rows = list(csv.DictReader(text.splitlines()))
    if not rows or "lat" not in rows[0] or "lon" not in rows[0]:
        fail("the APAD CSV has no lat/lon columns; no result written")
    return raw, rows


def in_area(lat, lon, bbox):
    w, s, e, n = bbox
    return s <= lat <= n and w <= lon <= e


def main():
    region_id = sys.argv[1] if len(sys.argv) > 1 else "dhaka-kilns"
    index = json.loads((REGIONS / "index.json").read_text())
    area = next((r for r in index["regions"] if r["id"] == region_id), None)
    if area is None:
        fail(f"unknown region '{region_id}'")
    bbox = area["bbox"]
    w, s, e, n = bbox
    area_km2 = bbox_area_km2(bbox)

    static_path = REGIONS / region_id / "static.json"
    if not static_path.exists():
        fail(f"no published static-source layer for '{region_id}'; build the region first")
    static = json.loads(static_path.read_text())
    cells = [(p[0], p[1]) for p in static["points"]]      # lon, lat
    if not cells:
        fail(f"'{region_id}' has no published persistent-heat cells; nothing to check")

    raw, rows = fetch_inventory()
    source = dict(APAD_SOURCE, retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                  sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), rows=len(rows))
    operating = [r for r in rows if (r.get("status") or "").strip().lower() == "operating"]
    if not operating:
        fail("the APAD inventory has no operating kilns; no result written")
    kilns = [(float(r["lat"]), float(r["lon"])) for r in operating]
    inside = [k for k in kilns if in_area(k[0], k[1], bbox)]
    if not inside:
        fail(f"the APAD inventory has no operating kilns inside the '{region_id}' bbox; no result written")

    results = []
    for radius in RADII_KM:
        matched_cells = 0
        matched_kilns = set()
        for clon, clat in cells:
            for i, (klat, klon) in enumerate(inside):
                if haversine_km(clat, clon, klat, klon) <= radius:
                    matched_cells += 1
                    matched_kilns.add(i)
                    break
        precision = matched_cells / len(cells)
        recall = len(matched_kilns) / len(inside)

        rng = random.Random(SEED)
        p_samples, r_samples = [], []
        for _ in range(TRIALS):
            pts = [(s + rng.random() * (n - s), w + rng.random() * (e - w)) for _ in cells]
            hits = sum(1 for plat, plon in pts
                       if any(haversine_km(plat, plon, klat, klon) <= radius for klat, klon in inside))
            p_samples.append(hits / len(pts))
            covered = {i for plat, plon in pts
                       for i, (klat, klon) in enumerate(inside)
                       if haversine_km(plat, plon, klat, klon) <= radius}
            r_samples.append(len(covered) / len(inside))
        p_samples.sort()
        r_samples.sort()
        base_p = p_samples[len(p_samples) // 2]
        base_r = r_samples[len(r_samples) // 2]
        results.append({
            "radius_km": radius,
            "published_cells": len(cells),
            "cells_matching_a_kiln": matched_cells,
            "precision": round(precision, 4),
            "inventory_kilns_in_area": len(inside),
            "kilns_matching_a_cell": len(matched_kilns),
            "recall": round(recall, 4),
            "random_baseline_precision": round(base_p, 4),
            "random_baseline_precision_p95": round(p_samples[int(0.95 * (len(p_samples) - 1))], 4),
            "random_baseline_recall": round(base_r, 4),
            "random_baseline_recall_p95": round(r_samples[int(0.95 * (len(r_samples) - 1))], 4),
            "better_than_chance": bool(precision > p_samples[int(0.95 * (len(p_samples) - 1))]),
        })

    # Optional second view: the underlying typed detections, when the local FIRMS cache is present.
    per_detection = {"status": "skipped", "reason": "no local FIRMS cache for this area"}
    cache = ROOT / "data" / "cache" / region_id
    if cache.exists() and list(cache.glob("*.parquet")):
        try:
            import duckdb
            con = duckdb.connect()
            files = sorted(str(p) for p in cache.glob("*.parquet"))
            con.execute("CREATE TABLE d AS SELECT * FROM read_parquet(?)", [files])
            by_type = {}
            for t, n in con.execute("SELECT type, count(*) FROM d GROUP BY 1").fetchall():
                dets = con.execute("SELECT lat, lon FROM d WHERE type IS NOT DISTINCT FROM ? GROUP BY 1, 2", [t]).fetchall()
                hits = sum(1 for lat, lon in dets
                           if any(haversine_km(lat, lon, klat, klon) <= 1.0 for klat, klon in inside))
                by_type[str(t)] = {"detections": n, "within_1km_of_a_kiln": hits,
                                   "share_within_1km": round(hits / n, 4) if n else None}
            per_detection = {"status": "computed", "radius_km": 1.0, "by_firms_type": by_type,
                             "type_meaning": {"0": "presumed vegetation fire", "1": "active volcano",
                                              "2": "other static land source", "3": "offshore",
                                              "None": "near-real-time rows carry no type"}}
        except Exception as e:                       # a broken cache must not fake a result
            per_detection = {"status": "failed", "reason": f"{type(e).__name__}: {e}"}

    if not any(r["better_than_chance"] for r in results):
        verdict = ("The published persistent-heat cells do not coincide with the mapped kilns better "
                   "than randomly placed cells of the same number would. The static layer is a "
                   "persistent-heat proxy, not a kiln inventory, and must not be read as confirmed kilns.")
    else:
        verdict = ("At least one radius puts the published persistent-heat cells on mapped kilns more "
                   "often than chance. The agreement is partial and does not validate the class as a "
                   "kiln inventory.")

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "script": "scripts/validation/kilns.py",
        "question": "Do the area's published persistent-heat cells correspond to mapped brick kilns?",
        "area": {"id": region_id, "name": area["name"], "bbox": bbox, "area_km2": round(area_km2, 1)},
        "firms_layer": {"file": f"data/regions/{region_id}/static.json", "cells": len(cells),
                        "note": static.get("note")},
        "inventory": source,
        "method": {
            "test": "placement test: observed cells versus random cells of the same number in the same bbox",
            "radii_km": list(RADII_KM),
            "trials": TRIALS,
            "seed": SEED,
            "distance": "great-circle (haversine)",
        },
        "results": results,
        "per_detection_view": per_detection,
        "verdict": verdict,
        "limitations": [
            "The APAD inventory is an asset list with modelled attributes and positions; it is not "
            "field-verified ground truth and it is not FIRMS truth either.",
            "A match inside one radius does not identify what the heat source is; the two sources can "
            "coincide without one causing the other.",
            "FIRMS detections in this area are sparse and concentrated, so the static layer is a small "
            "sample of the area's heat sources.",
            "A negative result here does not prove that no kilns are detected; it shows that this "
            "published layer cannot be called a kiln inventory.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"kilns_{region_id}.json.tmp"
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    os.replace(tmp, OUT / f"kilns_{region_id}.json")
    print(f"kilns.py: wrote {OUT / f'kilns_{region_id}.json'}")
    for r in results:
        print(f"  R={r['radius_km']}km precision={r['precision']:.4f} (random {r['random_baseline_precision']:.4f}) "
              f"recall={r['recall']:.4f} (random {r['random_baseline_recall']:.4f})")


if __name__ == "__main__":
    main()
