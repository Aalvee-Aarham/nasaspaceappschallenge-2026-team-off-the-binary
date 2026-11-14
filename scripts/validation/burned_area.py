"""Independent NASA check: does the harmonized record track physical burned area?

    uv run --with rasterio --with numpy --with planetary-computer python scripts/validation/burned_area.py

Reads NASA MCD64A1 Collection 6.1 burned area (Burn_Date > 0) from the public Planetary Computer
STAC catalogue and compares it with the published monthly record of every vegetation-dominated
preset area: the harmonized Aqua-scale estimate and the raw all-sensor detection count.

The point of the test is the 2012 step. MCD64A1 is an independent change-detection product built
from MODIS alone, so burned area must not jump when VIIRS joins in 2012. If the raw detection count
jumps and burned area does not, the jump was an instrument change, not a change on the ground.

Fail-closed: if the catalogue, a COG or a window cannot be read, the script stops with the exact
blocker and writes no output. Partial results are never published.

Writes data/validation/burned_area.json. Attribution travels with the numbers.
"""
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import numpy as np
    import planetary_computer
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
except ImportError as e:                                    # the gates need these; say exactly what is missing
    print(f"burned_area.py: needs rasterio, numpy and planetary-computer ({e}); "
          f"run with `uv run --with rasterio --with numpy --with planetary-computer`", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[2]
REGIONS = ROOT / "data" / "regions"
OUT = ROOT / "data" / "validation"
CACHE = ROOT / "data" / "cache" / "validation"

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "modis-64A1-061"
ASSET = "Burn_Date"
PIXEL_M = 463.31271652791725          # MCD64A1 sinusoidal grid spacing, from the COG transform


def bbox_area_km2(bbox):
    """Account for latitude: a degree of longitude shrinks by cos(mid-latitude)."""
    w, s, e, n = bbox
    return (e - w) * (n - s) * (111.32 ** 2) * math.cos(math.radians((s + n) / 2))
AREA_IDS = ("alberta", "la-rioja", "n-california", "parana-delta", "punjab", "rondonia", "se-australia")
FIRST_YEAR, LAST_YEAR = 2003, 2024    # complete years covering the MODIS era and the 2012 VIIRS step
WORKERS = 8
BATCH = 24            # months written to the cache per batch, so a crash loses little
SOURCE = {
    "name": "NASA MCD64A1 Collection 6.1 burned area (Burn_Date)",
    "collection": COLLECTION,
    "catalogue": f"{STAC}/collections/{COLLECTION}",
    "product_page": "https://lpdaac.usgs.gov/products/mcd64a1v061/",
    "licence": "NASA data are openly available; cite the LP DAAC and the MCD64A1 product team",
}
STEP_YEAR = 2012          # VIIRS Suomi-NPP joins the record
STEP_BASE_YEARS = (2009, 2010, 2011)


def fail(msg):
    print(f"burned_area.py: {msg}", file=sys.stderr)
    sys.exit(1)


def stac_search(bbox, dt_range):
    # ask for the fields we use: the full item is a megabyte per year of answers and the search times out
    body = {"collections": [COLLECTION], "bbox": list(bbox), "datetime": dt_range, "limit": 2000,
            "fields": {"include": ["id", "properties.start_datetime", f"assets.{ASSET}.href"]}}
    req = urllib.request.Request(f"{STAC}/search", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "kiln-watch-validation/1.0"}, method="POST")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    fail(f"the MCD64A1 catalogue could not be searched ({last}); no result written")


def burned_for_month(items, bbox):
    """Burned km2 in `bbox` for one month, summed over the tiles that cover it."""
    total = 0
    seen = 0
    for f in items:
        href = planetary_computer.sign(f["assets"][ASSET]["href"])
        # a GDAL environment per thread: sharing one dataset across threads crashes the process
        with rasterio.Env(), rasterio.open(href, sharing=False) as src:
            tb = transform_bounds("EPSG:4326", src.crs, *bbox)
            win = from_bounds(*tb, src.transform)
            if win.width <= 0 or win.height <= 0:
                continue
            arr = src.read(1, window=win)
            total += int(((arr > 0) & (arr < 255)).sum())
            seen += 1
    if not seen:
        raise RuntimeError("no MCD64A1 tile covers the area for this month")
    return total * (PIXEL_M ** 2) / 1e6


def spearman(xs, ys):
    """Spearman rho with average ranks for ties."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def load_months():
    index = json.loads((REGIONS / "index.json").read_text())
    out = {}
    for region in index["regions"]:
        if region["id"] not in AREA_IDS:
            continue
        monthly = json.loads((REGIONS / region["id"] / "monthly.json").read_text())
        series = {}
        for i, period in enumerate(monthly["periods"]):
            if monthly["partial"][i]:
                continue                       # a partial month is not a period to compare
            series[period] = {
                "harmonized": monthly["classes"]["veg"]["hotspots"]["v"][i],
                "raw": monthly["raw"]["all_det"][i],
            }
        out[region["id"]] = {"name": region["name"], "bbox": region["bbox"], "series": series}
    missing = [a for a in AREA_IDS if a not in out]
    if missing:
        fail(f"no published region data for {', '.join(missing)}; build the regions first")
    return out


def main():
    regions = load_months()
    months = [f"{y}-{m:02d}" for y in range(FIRST_YEAR, LAST_YEAR + 1) for m in range(1, 13)]
    CACHE.mkdir(parents=True, exist_ok=True)

    burned = {}
    gaps = {}
    for area_id, area in regions.items():
        cache_path = CACHE / f"burned_area_{area_id}.json"
        saved = json.loads(cache_path.read_text()) if cache_path.exists() else {"months": {}, "gaps": []}
        # a cache from another bbox or window must not be mixed into this comparison
        if saved.get("bbox") not in (None, area["bbox"]) or saved.get("window") not in (None, [FIRST_YEAR, LAST_YEAR]):
            fail(f"the cached burned area for {area_id} was read for a different bbox or window; delete "
                 f"{cache_path} and run again")
        cached = saved["months"]
        w, s, e, n = area["bbox"]
        todo = [m for m in months if m not in cached]
        if not todo:
            burned[area_id], gaps[area_id] = cached, saved.get("gaps", [])
            print(f"burned_area.py: {area_id} cached", flush=True)
            continue
        print(f"burned_area.py: {area_id}: {len(todo)} months", flush=True)
        found = stac_search(area["bbox"], f"{FIRST_YEAR}-01-01/{LAST_YEAR + 1}-01-01").get("features", [])
        catalogue = {}
        for f in found:
            start = (f.get("properties", {}).get("start_datetime") or "")[:7]
            catalogue.setdefault(start, []).append(f)
        # The Planetary Computer mirror is missing some product months (2023-09 and 2024-07 are gone for
        # every area). They are recorded, not silently dropped: a month without burned area cannot be
        # compared, and a long gap would make the comparison meaningless.
        missing = [m for m in months if not catalogue.get(m)]
        if len(missing) > 0.1 * len(months):
            fail(f"the MCD64A1 catalogue is missing {len(missing)} of {len(months)} months for {area_id} "
                 f"(first: {missing[0]}); no result written")
        if missing:
            print(f"burned_area.py: {area_id}: {len(missing)} month(s) missing from the catalogue "
                  f"({', '.join(missing[:4])}{'...' if len(missing) > 4 else ''})", flush=True)
        todo = [m for m in todo if catalogue.get(m)]
        if not todo:
            if not cached:
                fail(f"no MCD64A1 month could be read for {area_id}; no result written")
            burned[area_id], gaps[area_id] = cached, missing
            print(f"burned_area.py: {area_id} cached ({len(cached)} months)", flush=True)
            continue

        def one(m):
            return m, burned_for_month(catalogue[m], area["bbox"])

        gaps[area_id] = missing
        try:
            with ThreadPoolExecutor(WORKERS) as ex:
                for i in range(0, len(todo), BATCH):
                    for m, value in ex.map(one, todo[i:i + BATCH]):
                        cached[m] = round(value, 3)
                    tmp = cache_path.with_suffix(".tmp")
                    tmp.write_text(json.dumps({"bbox": area["bbox"], "window": [FIRST_YEAR, LAST_YEAR], "months": cached, "gaps": gaps[area_id]}, indent=1, sort_keys=True))
                    os.replace(tmp, cache_path)
                    print(f"burned_area.py: {area_id}: {min(i + BATCH, len(todo))}/{len(todo)} months", flush=True)
        except Exception as e:
            fail(f"reading MCD64A1 for {area_id} failed ({type(e).__name__}: {e}); no result written")
        tmp = cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"bbox": area["bbox"], "window": [FIRST_YEAR, LAST_YEAR], "months": cached, "gaps": gaps[area_id]}, indent=1, sort_keys=True))
        os.replace(tmp, cache_path)
        burned[area_id] = cached

    per_area = {}
    for area_id, area in regions.items():
        rows = []
        for m in months:
            if m not in area["series"] or m not in burned[area_id]:
                continue
            km2 = burned[area_id][m]
            series = area["series"][m]
            rows.append({"period": m, "burned_km2": km2,
                         "harmonized": series["harmonized"], "raw": series["raw"]})
        if len(rows) < 0.9 * len(months):
            fail(f"only {len(rows)} comparable months for {area_id}; no result written")
        w, s, e, n = area["bbox"]
        area_km2 = bbox_area_km2(area["bbox"])
        for r in rows:
            r["burned_per_km2"] = round(r["burned_km2"] / area_km2, 8)
            r["harmonized_per_km2"] = round(r["harmonized"] / area_km2, 8)
            r["raw_per_km2"] = round(r["raw"] / area_km2, 8)
        rho_h = spearman([r["harmonized_per_km2"] for r in rows], [r["burned_per_km2"] for r in rows])
        rho_r = spearman([r["raw_per_km2"] for r in rows], [r["burned_per_km2"] for r in rows])
        per_area[area_id] = {
            "name": area["name"], "bbox": area["bbox"], "area_km2": round(area_km2, 1),
            "months": len(rows), "first": rows[0]["period"], "last": rows[-1]["period"],
            "months_missing_from_catalogue": gaps.get(area_id, []),
            "spearman_harmonized_vs_burned": round(rho_h, 3) if rho_h is not None else None,
            "spearman_raw_vs_burned": round(rho_r, 3) if rho_r is not None else None,
            "total_burned_km2": round(sum(r["burned_km2"] for r in rows), 1),
            "months_with_burned_area": sum(1 for r in rows if r["burned_km2"] > 0),
            "series": rows,
        }

    # the 2012 step: the same calendar months in 2012 against the same months in the earlier years
    step = {}
    for area_id, area in per_area.items():
        series = {r["period"]: r for r in area["series"]}

        def mean_of(periods, key):
            vals = [series[p][key] for p in periods if p in series]
            return sum(vals) / len(vals) if vals else None
        step_months = [f"2012-{m:02d}" for m in range(1, 13)]
        base = []
        for y in STEP_BASE_YEARS:
            base.append([f"{y}-{m:02d}" for m in range(1, 13)])
        entry = {}
        for key in ("raw_per_km2", "harmonized_per_km2", "burned_per_km2"):
            now = mean_of(step_months, key)
            before = mean_of([p for group in base for p in group], key)
            entry[key] = {"in_2012": round(now, 8) if now is not None else None,
                          "mean_of_same_months_2009_2011": round(before, 8) if before else None,
                          "ratio": round(now / before, 3) if now and before else None}
        step[area_id] = entry

    def median(vals):
        vals = sorted(v for v in vals if v is not None)
        if not vals:
            return None
        n = len(vals)
        return round(vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2, 3)

    summary = {
        "median_spearman_harmonized_vs_burned": median(
            [a["spearman_harmonized_vs_burned"] for a in per_area.values()]),
        "median_spearman_raw_vs_burned": median(
            [a["spearman_raw_vs_burned"] for a in per_area.values()]),
        "areas_harmonized_at_least_as_good_as_raw": sum(
            1 for a in per_area.values()
            if a["spearman_harmonized_vs_burned"] is not None and a["spearman_raw_vs_burned"] is not None
            and a["spearman_harmonized_vs_burned"] >= a["spearman_raw_vs_burned"]),
        "areas_compared": len(per_area),
        "median_step_2012_raw": median([s["raw_per_km2"]["ratio"] for s in step.values()]),
        "median_step_2012_harmonized": median([s["harmonized_per_km2"]["ratio"] for s in step.values()]),
        "median_step_2012_burned_area": median([s["burned_per_km2"]["ratio"] for s in step.values()]),
    }
    if summary["median_step_2012_burned_area"] is None:
        fail("the 2012 step could not be computed; no result written")

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "script": "scripts/validation/burned_area.py",
        "question": "Does the harmonized record track physical burned area, and is the 2012 jump an instrument change?",
        "source": SOURCE,
        "window": {"first": months[0], "last": months[-1], "months": len(months)},
        "areas": list(AREA_IDS),
        "method": {
            "burned_area": "MCD64A1 C6.1 Burn_Date > 0 pixels inside the area bbox, 500 m sinusoidal grid",
            "compared": "harmonized Aqua-scale hotspots per km2 and raw all-sensor detections per km2",
            "correlation": "Spearman rho over the monthly series (average ranks for ties)",
            "step_test": f"mean of the twelve calendar months of {STEP_YEAR} against the same months of "
                         f"{', '.join(str(y) for y in STEP_BASE_YEARS)}",
            "partial_months": "months the publisher marked partial are excluded",
        },
        "summary": summary,
        "step_2012": step,
        "catalogue_gaps": {k: v for k, v in gaps.items() if v},
        "per_area": {k: {kk: vv for kk, vv in v.items() if kk != "series"} for k, v in per_area.items()},
        "series": {k: v["series"] for k, v in per_area.items()},
        "limitations": [
            "The Planetary Computer mirror is missing a few MCD64A1 product months (2023-09 and 2024-07 "
            "for most areas); those months are listed in catalogue_gaps and left out of the comparison.",
            "Burned area measures physical extent, not detections: one large burn and many small burns "
            "give the same hotspot count but very different burned area.",
            "MCD64A1 is itself a MODIS change-detection product, so it shares MODIS's view of what burns "
            "and misses small and agricultural fires.",
            "Detection counts also depend on cloud, smoke and overpass geometry, which burned area does not.",
            "A correlation between two monthly series is evidence of agreement, not proof that either "
            "counts fires, and burned area is not a fire perimeter.",
            "The 2012 step compares 2012 with 2009–2011 in the same calendar months. An exceptional year in "
            "the baseline moves that ratio a long way (Alberta's 2011), which is why the median across areas "
            "is the number to read, not the per-area one.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "burned_area.json.tmp"
    tmp.write_text(json.dumps(out, indent=1))
    os.replace(tmp, OUT / "burned_area.json")
    print(f"burned_area.py: wrote {OUT / 'burned_area.json'}")
    print(f"  median spearman harmonized vs burned: {summary['median_spearman_harmonized_vs_burned']}")
    print(f"  median spearman raw vs burned:        {summary['median_spearman_raw_vs_burned']}")
    print(f"  2012 step: raw x{summary['median_step_2012_raw']}, "
          f"harmonized x{summary['median_step_2012_harmonized']}, "
          f"burned area x{summary['median_step_2012_burned_area']}")


if __name__ == "__main__":
    main()
