"""Burned-area witness for the casebook: MODIS MCD64A1 (Collection 6.1) burned area around every case.

Build-time only (needs `pip install earthengine-api`, a one-off `earthengine authenticate`, and EE_PROJECT in .env).
The committed data/regions/<area>/burned_area.json carries the result, so the live demo needs no Earth Engine.

For each (0.1 degree case cell, month) in cases.json it sums the area MCD64A1 mapped as burned inside the case cell and
its 8 neighbours (about 33 km square) in that calendar month. Then re-run `python -m kw.cases <area>` to apply it.

    python scripts/build_burned.py [area ...]
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

import ee

ROOT = Path(__file__).resolve().parents[1]
REGIONS = ROOT / "data" / "regions"
PAD = 0.1  # one cell of padding on every side: the 3x3 block around the case cell


def load_env():
    f = ROOT / ".env"
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def month_end(p):
    y, m = int(p[:4]), int(p[5:7])
    return f"{y + m // 12}-{m % 12 + 1:02d}-01"


def main(areas):
    load_env()
    ee.Initialize(project=os.environ["EE_PROJECT"])
    col = ee.ImageCollection("MODIS/061/MCD64A1")
    last = dt.datetime.fromtimestamp(col.aggregate_max("system:time_start").getInfo() / 1000, dt.timezone.utc)
    through = f"{last.year}-{last.month:02d}"
    print("MCD64A1 published through", through, flush=True)
    for area in areas:
        cases = json.loads((REGIONS / area / "cases.json").read_text(encoding="utf-8"))
        want = {}
        for c in cases["cases"]:
            if "2000-11" <= c["period"] <= through:
                want[f"{c['cell'][0]},{c['cell'][1]}|{c['period']}"] = (c["cell"], c["period"])
        feats = [ee.Feature(ee.Geometry.Rectangle([lo - PAD, la - PAD, lo + 2 * PAD, la + 2 * PAD], proj="EPSG:4326", geodesic=False),
                            {"key": k, "start": p + "-01", "end": month_end(p)}) for k, ((la, lo), p) in want.items()]

        def one(f):
            img = col.filterDate(f.get("start"), f.get("end")).select("BurnDate").max().gt(0)
            km2 = img.multiply(ee.Image.pixelArea()).reduceRegion(ee.Reducer.sum(), f.geometry(), 500, maxPixels=1e9, bestEffort=True)
            return f.set("km2", ee.Number(km2.get("BurnDate")).divide(1e6))

        res = ee.FeatureCollection(feats).map(one).getInfo()["features"]
        table = {r["properties"]["key"]: round(r["properties"]["km2"] or 0, 2) for r in res}
        out = {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "area": area, "through": through,
               "source": "MODIS/061/MCD64A1 via Google Earth Engine", "cells": table,
               "note": "km2 mapped as burned (BurnDate > 0) in the case cell and its 8 neighbours during the case month. "
                       "MCD64A1 mapping is guided by MODIS active fires, so it is not fully independent of the hotspot record."}
        (REGIONS / area / "burned_area.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        print(area, len(table), "cases checked,", sum(v > 0 for v in table.values()), "with burn scars", flush=True)


if __name__ == "__main__":
    idx = json.loads((REGIONS / "index.json").read_text(encoding="utf-8"))["regions"]
    main(sys.argv[1:] or [r["id"] for r in idx if r.get("preset")])
