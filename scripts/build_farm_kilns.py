"""Brick kilns near farmland, all of Bangladesh: the data behind the farmer check on the Bangladesh page.

    uv run --with rasterio --with numpy python scripts/build_farm_kilns.py

Build time only (needs rasterio). Reads three public sources and writes data/global/kilns_bd.json (committed):
  - APAD / IGP asset-data-igp Bangladesh brick-kiln inventory (CC BY 4.0): every kiln's position and division
  - ESA WorldCover 10 m 2021 (CC BY 4.0), class 40 Cropland, at the ~74 m overview: cropland share within 1 km of each kiln
  - Natural Earth 1:50m admin-0 (public domain): the Bangladesh outline, so a place outside it never reads "0 kilns"

FIRMS is not used: NASA's fire product cannot find kilns (measured, see data/regions/dhaka-kilns/kilns.json).
Fail-closed: a source that cannot be read stops the script and nothing is written.
"""
import datetime as dt
import json
import math
import os
import random
import statistics
import sys
import urllib.request
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent / "validation"))
from kilns import APAD_SOURCE, fetch_inventory, haversine_km  # noqa: E402  (same download, same checks)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "global" / "kilns_bd.json"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson"
WORLDCOVER = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
CROPLAND, WC_OVERVIEW, RADIUS_KM = 40, 2, 1.0


def fail(msg):
    print(f"build_farm_kilns.py: {msg}", file=sys.stderr)
    sys.exit(1)


def outline():
    """Bangladesh as a list of rings [[lon, lat], ...], from Natural Earth."""
    try:
        with urllib.request.urlopen(urllib.request.Request(NE_URL, headers={"User-Agent": "kiln-watch-build/1.0"}), timeout=120) as r:
            fc = json.load(r)
    except OSError as e:
        fail(f"cannot download Natural Earth ({e}); nothing written")
    f = next((f for f in fc["features"] if f["properties"].get("ADM0_A3") == "BGD"), None)
    if not f:
        fail("Bangladesh is missing from Natural Earth; nothing written")
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [[[round(x, 4), round(y, 4)] for x, y in ring] for poly in polys for ring in poly]


def cropland_share(kilns):
    """Share of ESA WorldCover cropland pixels within RADIUS_KM of each kiln (0-100). A disc that crosses a tile edge
    is measured on its part inside the tile (ponytail: a few edge kilns; read the neighbour tile if that ever matters)."""
    out = [None] * len(kilns)
    by_tile = {}
    for i, k in enumerate(kilns):
        by_tile.setdefault((math.floor(k["lat"] / 3) * 3, math.floor(k["lon"] / 3) * 3), []).append(i)
    for (la, lo), idx in sorted(by_tile.items()):
        tile = f"N{la:02d}E{lo:03d}"
        try:
            ds = rasterio.open("/vsicurl/" + WORLDCOVER.format(tile=tile), overview_level=WC_OVERVIEW)
        except rasterio.errors.RasterioIOError as e:
            fail(f"cannot read WorldCover tile {tile} ({e}); nothing written")
        with ds:
            t = ds.transform
            crop = ds.read(1) == CROPLAND
            print(f"  {tile}: {len(idx)} kilns, {ds.width}x{ds.height} px of {t.a * 111320:.0f} m")
        ry = RADIUS_KM / 111.32 / t.a
        for i in idx:
            k = kilns[i]
            rx = ry / math.cos(math.radians(k["lat"]))
            c, r = (k["lon"] - t.c) / t.a, (t.f - k["lat"]) / -t.e
            r0, r1 = max(0, int(r - ry)), min(crop.shape[0], int(r + ry) + 2)
            c0, c1 = max(0, int(c - rx)), min(crop.shape[1], int(c + rx) + 2)
            yy, xx = np.mgrid[r0:r1, c0:c1]
            disc = ((yy + 0.5 - r) / ry) ** 2 + ((xx + 0.5 - c) / rx) ** 2 <= 1
            out[i] = round(100 * float(crop[r0:r1, c0:c1][disc].mean())) if disc.any() else None
    return out


def cross_check(kilns):
    """Where both maps exist (the Dhaka box): how many APAD kilns sit on a kiln seen in Sentinel-2 imagery (the
    deluair map in kilns.json), against random places; and how many Sentinel-2 kilns APAD has. Seeded, re-runnable."""
    p = ROOT / "data" / "regions" / "dhaka-kilns" / "kilns.json"
    if not p.exists():
        return {"status": "skipped", "reason": "data/regions/dhaka-kilns/kilns.json is not built"}
    k = json.loads(p.read_text(encoding="utf-8"))
    w, s, e, n = k["bbox"]
    s2 = [(r[1], r[0]) for r in k["kilns"]]                       # lat, lon of every Sentinel-2 detection
    s2_labelled = [(r[1], r[0]) for r in k["kilns"] if r[4]]
    apad = [(x["lat"], x["lon"]) for x in kilns if s <= x["lat"] <= n and w <= x["lon"] <= e]

    def near(pt, pts, km):
        return any(haversine_km(pt[0], pt[1], q[0], q[1]) <= km for q in pts)
    rnd = random.Random(20261115)
    rand = [(s + rnd.random() * (n - s), w + rnd.random() * (e - w)) for _ in range(2000)]
    pct = lambda pts, ref, km: round(100 * sum(near(x, ref, km) for x in pts) / len(pts), 1)
    return {"status": "ok", "area": "dhaka-kilns", "bbox": k["bbox"], "reference": k["inventory"]["source"],
            "apad_in_area": len(apad), "s2_labelled_in_area": len(s2_labelled), "random_places": len(rand), "seed": 20261115,
            "apad_within_300m_of_s2_pct": pct(apad, s2, 0.3), "random_within_300m_of_s2_pct": pct(rand, s2, 0.3),
            "s2_labelled_with_apad_within_500m_pct": pct(s2_labelled, apad, 0.5),
            "note": ("Most APAD positions sit on a kiln seen from space, but some do not, and APAD lists about half of the "
                     "kilns in the Sentinel-2 map: a count from it is a floor, not the full number.")}


def main():
    _, rows = fetch_inventory()
    tons = lambda v: round(float(str(v).replace(",", "")), 1) if str(v).strip() else None   # "8,886.81" style numbers
    kilns = [{"lat": float(r["lat"]), "lon": float(r["lon"]), "div": r["state"].strip(),
              "pm25": tons(r.get("pm25_t_yr", "")), "so2": tons(r.get("so2_t_yr", ""))} for r in rows
             if r.get("status", "").strip() == "operating"]
    if not kilns:
        fail("the APAD inventory has no operating kilns; nothing written")
    rings = outline()
    crop = cropland_share(kilns)
    divs = sorted({k["div"] for k in kilns})
    by_div = {d: sum(k["div"] == d for k in kilns) for d in divs}
    shares = [c for c in crop if c is not None]
    east = max(k["lon"] for k in kilns)
    out = {
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "inventory": {**APAD_SOURCE, "n": len(kilns), "by_division": by_division_sorted(by_div),
                      "east_edge_lon": round(east, 2),
                      "coverage": (f"The inventory lists kilns only west of about {east:.1f}° E, in {len(divs)} of Bangladesh's 8 "
                                   f"divisions ({', '.join(divs)}). Chattogram and Sylhet divisions and the east of Dhaka "
                                   "division have no kilns in it: not covered, not free of kilns."),
                      "caveat": ("An asset list with modelled attributes and positions, not field-verified. It shows where "
                                 "kilns stand, not whether one is firing today.")},
        "cross_check": cross_check(kilns),
        "cropland": {"source": "ESA WorldCover 10 m 2021 v200, class 40 (Cropland), read at the ~74 m overview (CC BY 4.0)",
                     "url": "https://esa-worldcover.org", "radius_km": RADIUS_KM,
                     "method": "share of cropland pixels in a 1 km disc around each kiln",
                     "kilns_with_half_or_more": sum(c >= 50 for c in shares), "kilns_measured": len(shares),
                     "median_pct": statistics.median(shares) if shares else None},
        "boundary": {"source": "Natural Earth 1:50m admin-0 countries v5.1.2 (public domain)", "url": NE_URL, "rings": rings},
        "emissions": {"source": "APAD modelled estimates per kiln: capacity times an emission factor for the kiln type "
                                "(fixed-chimney or zigzag); not measured at the kiln", "unit": "tonnes per year",
                      "pm25_total": round(sum(k["pm25"] or 0 for k in kilns)), "so2_total": round(sum(k["so2"] or 0 for k in kilns))},
        "fields": ["lat", "lon", "cropland_pct_1km", "division", "pm25_t_yr", "so2_t_yr"],
        "divisions": divs,
        "kilns": [[round(k["lat"], 5), round(k["lon"], 5), c, divs.index(k["div"]), k["pm25"], k["so2"]] for k, c in zip(kilns, crop)],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, OUT)
    cl = out["cropland"]
    print(f"wrote {OUT.relative_to(ROOT)} {OUT.stat().st_size / 1024:.0f} KB: {len(kilns)} kilns, "
          f"{cl['kilns_with_half_or_more']} of {cl['kilns_measured']} with cropland on half or more of the land within 1 km")


def by_division_sorted(d):
    return dict(sorted(d.items(), key=lambda x: -x[1]))


if __name__ == "__main__":
    main()
