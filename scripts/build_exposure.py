"""Build the exposure context layer for every preset area.

    pip install rasterio numpy           # build-time only, not in server/requirements.txt
    python scripts/build_exposure.py [area ...]

Writes data/regions/<area>/exposure.json. Downloads are cached in data/cache/exposure/ and are not committed.
Population is WorldPop's modelled 2020 surface; hospitals and roads are an OpenStreetMap snapshot of the query date.
A context layer, not an impact estimate: FIRMS gives detections, not a fire perimeter.
"""
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
REGIONS = ROOT / "data" / "regions"
CACHE = ROOT / "data" / "cache" / "exposure"
FAST = bool(os.environ.get("KW_OSM_FAST"))   # give up quickly when Overpass is down; rerun later, finished boxes are cached
UA = "kiln-watch-exposure/1.0 (open-source fire harmonization app)"
DEG = 0.1
CAPS = {"hospitals": 1500, "roads": 3000}
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]  # not osm.ch: it serves Switzerland only
COUNTRIES = {
    "dhaka-kilns": ["BGD"], "punjab": ["IND"], "la-rioja": ["ARG"], "rondonia": ["BRA"], "alberta": ["CAN"],
    "se-australia": ["AUS"], "n-california": ["USA"], "parana-delta": ["ARG", "PRY"], "niger-delta": ["NGA"],
}
WORLDPOP = "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/{iso}/{iso_l}_ppp_2020_1km_Aggregated.tif"
CAVEAT = ("Population and infrastructure inside cells where the harmonized record shows fire. A context layer, not an "
          "impact estimate: FIRMS gives detections, not a fire perimeter, and there is no smoke or fire-spread model here.")
HOSPITAL_Q = '[out:json][timeout:180];(nwr["amenity"~"^(hospital|clinic|doctors)$"]({s},{w},{n},{e});nwr["healthcare"~"^(hospital|clinic)$"]({s},{w},{n},{e}););out center tags;'
SCHOOL_Q = '[out:json][timeout:180];nwr["amenity"~"^(school|kindergarten)$"]({s},{w},{n},{e});out center tags;'
ROAD_Q = '[out:json][timeout:180];way["highway"~"^(motorway|trunk|primary)$"]({s},{w},{n},{e});out geom tags;'


# ---------------------------------------------------------------- population

def raster_path(iso):
    p = CACHE / f"{iso.lower()}_ppp_2020_1km_Aggregated.tif"
    if not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(WORLDPOP.format(iso=iso, iso_l=iso.lower()), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r, open(str(p) + ".part", "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        os.replace(str(p) + ".part", p)
    return p


def cell_population(ds, lat0, lon0, deg=DEG):
    """Area-weighted sum of the source pixels overlapping one target cell, computed in degrees."""
    t = ds.transform
    px, py = t.a, -t.e                                   # pixel width and height in degrees
    c0, c1 = (lon0 - t.c) / px, (lon0 + deg - t.c) / px
    r0, r1 = (t.f - (lat0 + deg)) / py, (t.f - lat0) / py
    ci0, ci1, ri0, ri1 = math.floor(c0), math.ceil(c1), math.floor(r0), math.ceil(r1)
    ci0, ri0, ci1, ri1 = max(ci0, 0), max(ri0, 0), min(ci1, ds.width), min(ri1, ds.height)
    if ci1 <= ci0 or ri1 <= ri0:
        return 0.0
    a = ds.read(1, window=((ri0, ri1), (ci0, ci1))).astype("float64")
    a[(a < 0) | ~np.isfinite(a)] = 0.0                    # nodata is -99999
    wx = np.clip(np.minimum(np.arange(ci0, ci1) + 1, c1) - np.maximum(np.arange(ci0, ci1), c0), 0, 1)
    wy = np.clip(np.minimum(np.arange(ri0, ri1) + 1, r1) - np.maximum(np.arange(ri0, ri1), r0), 0, 1)
    return float((a * np.outer(wy, wx)).sum())


def brute_force(ds, lat0, lon0, deg=DEG, sub=16):
    """The independent check: cut every source pixel into sub x sub points and give each point to the cell that holds
    it. This converges on the area-weighted answer without sharing its overlap arithmetic. (A plain centre-pixel sum
    would differ by whole pixels wherever a dense pixel straddles the box edge, e.g. Sydney on the se-australia edge.)"""
    t = ds.transform
    c0, c1 = int(math.floor((lon0 - t.c) / t.a)) - 1, int(math.ceil((lon0 + deg - t.c) / t.a)) + 1
    r0, r1 = int(math.floor((t.f - (lat0 + deg)) / -t.e)) - 1, int(math.ceil((t.f - lat0) / -t.e)) + 1
    r0, c0, r1, c1 = max(r0, 0), max(c0, 0), min(r1, ds.height), min(c1, ds.width)
    if r1 <= r0 or c1 <= c0:
        return 0.0                                        # the cell lies outside this country's raster
    a = ds.read(1, window=((r0, r1), (c0, c1))).astype("float64")
    a[(a < 0) | ~np.isfinite(a)] = 0.0
    off = (np.arange(sub) + 0.5) / sub
    lon = t.c + (np.arange(c0, c1)[:, None] + off[None, :]).ravel() * t.a       # sub-point longitudes, pixel-major
    lat = t.f + (np.arange(r0, r1)[:, None] + off[None, :]).ravel() * t.e
    inx, iny = (lon >= lon0) & (lon < lon0 + deg), (lat >= lat0) & (lat < lat0 + deg)
    px, py = np.repeat(np.arange(c1 - c0), sub)[inx], np.repeat(np.arange(r1 - r0), sub)[iny]
    nx, ny = np.bincount(px, minlength=c1 - c0), np.bincount(py, minlength=r1 - r0)   # sub-points per pixel column and row
    return float((a * np.outer(ny, nx)).sum() / sub ** 2)


def population(cells, isos):
    pop = [0.0] * len(cells)
    for iso in isos:
        with rasterio.open(raster_path(iso)) as ds:
            assert ds.crs.to_epsg() == 4326, f"{iso}: CRS is {ds.crs}, expected EPSG:4326"
            assert abs(ds.res[0] - 0.008333333) < 1e-6, f"{iso}: resolution {ds.res}"
            for i, (lat0, lon0) in enumerate(cells):
                pop[i] += cell_population(ds, lat0, lon0)
    return pop


def check_population(bbox, isos):
    """Cross-check on the full rectangle of 0.1 degree cells over the bbox (not the ragged set of fire cells, whose
    outer edge would split source pixels differently in the two methods): area-weighted sum vs centre-pixel sum."""
    w, s_, e, n = bbox
    lattice = [(round(i * DEG, 2), round(j * DEG, 2)) for i in range(math.floor(s_ / DEG), math.ceil(n / DEG))
               for j in range(math.floor(w / DEG), math.ceil(e / DEG))]
    total = brute = 0.0
    for iso in isos:
        with rasterio.open(raster_path(iso)) as ds:
            total += sum(cell_population(ds, la, lo) for la, lo in lattice)
            brute += sum(brute_force(ds, la, lo) for la, lo in lattice)
    return total, brute, abs(total - brute) / brute * 100 if brute else 0.0


# ---------------------------------------------------------------- OpenStreetMap

def overpass(query):
    """One Overpass request with retries and mirror fallback. Raises on failure; never returns a silent empty."""
    key = CACHE / ("overpass-" + hashlib.sha1(query.encode()).hexdigest() + ".json")
    if key.exists() and time.time() - key.stat().st_mtime < 30 * 86400:
        return json.loads(key.read_text(encoding="utf-8")), "cache"
    last = "no attempt"
    for mirror in MIRRORS:
        for wait in ((0,) if FAST else (0, 20)):
            time.sleep(wait)
            try:
                req = urllib.request.Request(mirror, data=urllib.parse.urlencode({"data": query}).encode(), headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=40 if FAST else 150) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if data.get("remark") and not data.get("elements"):
                    last = f"{mirror}: {data['remark'][:120]}"
                    continue
                CACHE.mkdir(parents=True, exist_ok=True)
                key.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data, mirror.split("//")[1].split("/")[0]
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as ex:
                last = f"{mirror}: {ex}"
    raise RuntimeError(last)


def sub_boxes(bbox, limit=1.5):  # limit: degrees per side; roads use smaller boxes (their geometry makes the reply large)
    w, s, e, n = bbox
    nx, ny = math.ceil((e - w) / limit), math.ceil((n - s) / limit)
    return [(s + (n - s) * j / ny, w + (e - w) * i / nx, s + (n - s) * (j + 1) / ny, w + (e - w) * (i + 1) / nx)
            for j in range(ny) for i in range(nx)]


def fetch_osm(template, bbox, limit=1.5):
    """Union of the elements over sub-boxes; every sub-box must succeed or the whole source is reported failed."""
    seen, mirror = {}, None
    for s, w, n, e in sub_boxes(bbox, limit):
        print(f'    overpass sub-box {s:.2f},{w:.2f},{n:.2f},{e:.2f}', flush=True)
        data, mirror = overpass(template.format(s=round(s, 4), w=round(w, 4), n=round(n, 4), e=round(e, 4)))
        for el in data.get("elements", []):
            seen[(el["type"], el["id"])] = el
    return list(seen.values()), mirror


def cell_of(lat, lon):
    return round(math.floor(lat / DEG + 1e-9) * DEG, 2), round(math.floor(lon / DEG + 1e-9) * DEG, 2)


def road_cells(geom):
    """Every 0.1 degree cell a polyline passes through (supercover walk by dense sampling at 1/4 cell)."""
    out, prev = [], None
    for a, b in zip(geom, geom[1:]):
        n = max(1, int(max(abs(b["lat"] - a["lat"]), abs(b["lon"] - a["lon"])) / (DEG / 4)) + 1)
        for k in range(n + 1):
            c = cell_of(a["lat"] + (b["lat"] - a["lat"]) * k / n, a["lon"] + (b["lon"] - a["lon"]) * k / n)
            if c != prev:
                out.append(c)
                prev = c
    return list(dict.fromkeys(out)) or ([cell_of(geom[0]["lat"], geom[0]["lon"])] if geom else [])


# ---------------------------------------------------------------- assembly

def build_area(area):
    grid = json.loads((REGIONS / area / "grid.json").read_text(encoding="utf-8"))
    meta = json.loads((REGIONS / area / "meta.json").read_text(encoding="utf-8"))
    cells = [tuple(c) for c in grid["cells"]]
    assert len(cells) == len(set(cells)), "grid cells must be unique"
    bbox, isos = meta["bbox"], COUNTRIES[area]
    pop = population(cells, isos)
    total = sum(pop)
    assert total > 0, f"{area}: population total is zero, a CRS or nodata problem"
    box_total, brute, diff = check_population(bbox, isos)
    assert diff < 0.1, f"{area}: area-weighted {box_total:.0f} vs centre-pixel {brute:.0f} differ by {diff:.3f}%"
    print(f"  population in fire cells {total:,.0f}; whole-box cross-check differs {diff:.3f}%")

    index = {c: i for i, c in enumerate(cells)}          # only facilities inside a cell that has had fire are kept
    n_hosp, n_clin, n_school = [0] * len(cells), [0] * len(cells), [0] * len(cells)
    named_hosp, roads = [], {}
    errors, mirror, queried = {}, None, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        els, mirror = fetch_osm(HOSPITAL_Q, bbox)
        for el in els:
            lat, lon = (el.get("lat"), el.get("lon")) if el["type"] == "node" else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
            ci = index.get(cell_of(lat, lon)) if lat is not None else None
            if ci is None:
                continue
            tags = el.get("tags", {})
            kind = tags.get("amenity") or tags.get("healthcare") or "hospital"
            if kind == "hospital":
                n_hosp[ci] += 1
                name = tags.get("name:en") or tags.get("name")
                if name:
                    named_hosp.append([name, round(lat, 4), round(lon, 4), ci])
            elif kind in ("clinic", "doctors"):
                n_clin[ci] += 1
    except Exception as ex:  # a failed source is recorded, never rendered as zero
        errors["hospitals"] = str(ex)[:200]
    try:
        els, mirror2 = fetch_osm(ROAD_Q, bbox, 2.0)
        mirror = mirror or mirror2
        for el in els:     # one road = every way sharing a name (or ref) and class; ways without either are not listed
            g, tags = el.get("geometry") or [], el.get("tags", {})
            name = tags.get("name:en") or tags.get("name") or tags.get("ref")
            ids = [index[c] for c in road_cells(g) if c in index] if g and name else []
            if not ids:
                continue
            r = roads.setdefault((name, tags.get("highway")), {"pt": g[len(g) // 2], "cells": set()})
            r["cells"].update(ids)
    except Exception as ex:
        errors["roads"] = str(ex)[:200]
    try:     # schools and kindergartens: counted per cell (no list: there are too many to ship)
        els, mirror3 = fetch_osm(SCHOOL_Q, bbox)
        mirror = mirror or mirror3
        for el in els:
            lat, lon = (el.get("lat"), el.get("lon")) if el["type"] == "node" else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
            ci = index.get(cell_of(lat, lon)) if lat is not None else None
            if ci is not None:
                n_school[ci] += 1
    except Exception as ex:
        errors["schools"] = str(ex)[:200]
    named_hosp.sort(key=lambda h: (h[0].isascii() is False, h[0]))   # English names first, then A to Z: a stable sample
    trunc = {"hospitals": len(named_hosp) > CAPS["hospitals"], "roads": len(roads) > CAPS["roads"]}
    named_hosp = named_hosp[:CAPS["hospitals"]]
    road_rows = [[n, k, round(r["pt"]["lat"], 4), round(r["pt"]["lon"], 4), sorted(r["cells"])] for (n, k), r in list(roads.items())[:CAPS["roads"]]]

    out = {
        "built_at": queried, "area": area, "bbox": bbox, "deg": DEG,
        "population": {
            "source": "WorldPop Global 2000-2020 population grid, 1 km aggregated",
            "url": WORLDPOP.format(iso=isos[0], iso_l=isos[0].lower()) + (f" (+ {', '.join(isos[1:])})" if len(isos) > 1 else ""),
            "vintage": 2020, "method": "area-weighted sum of 1 km source cells into the 0.1 degree grid, computed in degrees",
            "note": "Modelled population, not a census. Not the population on the day of a fire.",
        },
        "infrastructure": {
            "hospitals_source": "OpenStreetMap via Overpass API: amenity=hospital (counted); clinic and doctors, healthcare=clinic (counted apart)",
            "schools_source": "OpenStreetMap via Overpass API: amenity=school|kindergarten (counted per cell)",
            "roads_source": "OpenStreetMap via Overpass API: highway=motorway|trunk|primary, ways with a name or ref, merged by name and class",
            "scope": "Only facilities and roads inside a 0.1 degree cell that has had fire since 2000 are kept, so a distance to fire is 0 by construction.",
            "queried_at": queried, "mirror": mirror, "caps": CAPS, "truncated": trunc, "errors": errors,
        },
        "totals": {"population": round(total), "hospitals": None if "hospitals" in errors else sum(n_hosp),
                   "clinics": None if "hospitals" in errors else sum(n_clin), "schools": None if "schools" in errors else sum(n_school),
                   "major_roads": None if "roads" in errors else len(road_rows)},
        # [lat, lon, population, hospitals, clinics_and_doctors]: INDEX-PARALLEL with grid.json "cells"
        "cell_columns": ["lat", "lon", "population", "hospitals", "clinics", "schools"],
        "cells": [[lat, lon, round(p), h, c, sc] for (lat, lon), p, h, c, sc in zip(cells, pop, n_hosp, n_clin, n_school)],
        "hospital_columns": ["name", "lat", "lon", "cell"], "hospitals": named_hosp,          # named hospitals only: a sample, counts are in cells
        "road_columns": ["name", "kind", "lat", "lon", "cells"], "roads": road_rows,          # cells are indices into grid.json "cells"
        "caveat": CAVEAT,
    }
    assert len(out["cells"]) == len(grid["cells"])
    folder = REGIONS / area
    tmp = folder / "exposure.json.tmp"
    tmp.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    kb = tmp.stat().st_size / 1024
    assert kb <= 600, f"{area}: exposure.json is {kb:.0f} KB, over the 600 KB budget"
    os.replace(tmp, folder / "exposure.json")
    sys.path.insert(0, str(ROOT / "server"))
    from kw import cases  # late import: records the new file in meta.json (features, method text, external sources)
    mp = folder / "meta.json"
    m = cases.annotate_meta(json.loads(mp.read_text(encoding="utf-8")), folder)
    mp.with_suffix(".json.tmp").write_text(json.dumps(m, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(mp.with_suffix(".json.tmp"), mp)
    print(f"  wrote exposure.json {kb:.0f} KB: {sum(n_hosp)} hospitals ({len(named_hosp)} named), {sum(n_clin)} clinics, {sum(n_school)} schools, {len(road_rows)} roads, errors={errors or 'none'}")
    return out


def self_check():
    assert cell_of(23.79, 90.39) == (23.7, 90.3) and cell_of(23.8, 90.4) == (23.8, 90.4)
    assert road_cells([{"lat": 23.71, "lon": 90.31}, {"lat": 23.71, "lon": 90.52}]) == [(23.7, 90.3), (23.7, 90.4), (23.7, 90.5)]


if __name__ == "__main__":
    self_check()
    index = json.loads((REGIONS / "index.json").read_text(encoding="utf-8"))
    areas = sys.argv[1:] or [r["id"] for r in index["regions"] if r.get("preset")]
    for a in areas:
        print(a)
        build_area(a)
