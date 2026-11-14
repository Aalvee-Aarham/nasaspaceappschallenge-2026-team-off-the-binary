"""Schools, hospitals, clinics, care homes and fire stations for the Explorer map layer.

The box is cut into 0.25 degree tiles. Each tile comes from OpenStreetMap (Overpass) once and is cached on disk for a
week. Overpass takes 5-50 s and sometimes fails, so tiles load in a small background pool and the endpoint answers at
once with what is ready; `loading` counts the rest and the client asks again. A failed tile is listed in `failed`,
never returned as an empty place. While a tile inside a preset area loads (or after it failed), that area's
build-time list stands in, marked `partial`: it holds only the named hospitals and schools in cells with fire, capped.
"""
import json
import math
import os
import tempfile
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, wait

from . import news, tools
from .regions import PRESETS

TILE = 0.25
MAX_SIDE = 1.0           # degrees per side after snapping to tiles; the UI asks people to zoom in before this
TTL = 7 * 86400
RETRY_S = 30             # a failed tile is reported, then fetched again on a request after this long
CACHE = news.CACHE / "facilities"     # inside the git-ignored news cache
_pool = ThreadPoolExecutor(max_workers=2)   # ponytail: public Overpass allows ~2 slots per IP; a queue is the limit
_jobs = {}               # (iy, ix) -> Future; successful jobs are dropped (the disk cache serves them)
_asked = {}              # (iy, ix) -> last time a request wanted it
_failed_at = {}          # (iy, ix) -> when its last fetch failed
_lock = threading.Lock()


def _query(s, w, n, e):
    return (f'[out:json][timeout:40][bbox:{s:.4f},{w:.4f},{n:.4f},{e:.4f}];'
            f'(nwr["amenity"~"^({"|".join(tools.PLACE_KINDS)})$"];nwr["healthcare"~"^(hospital|clinic)$"];'
            f'nwr["social_facility"="nursing_home"];);out center tags {tools.FACILITY_CAP};')


def _parse(els):
    out = []
    for el in els:
        t = el.get("tags", {})
        la, lo = (el.get("lat"), el.get("lon")) if el["type"] == "node" else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        kind = (tools.PLACE_KINDS.get(t.get("amenity")) or tools.PLACE_KINDS.get(t.get("healthcare"))
                or ("care_home" if t.get("social_facility") == "nursing_home" else None))
        if la is not None and kind:
            out.append([round(la, 5), round(lo, 5), kind, t.get("name:en") or t.get("name") or ""])
    return out


def _disk(t):
    try:
        f = CACHE / f"{t[0]}_{t[1]}.json"
        if time.time() - f.stat().st_mtime < TTL:
            return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _tile(t):
    """One tile from Overpass (mirrors in turn), written to disk. None when nobody waits for it any more (the view
    moved on), so a long pan does not queue stale tiles. Raises when every mirror failed; failures are not cached."""
    if time.time() - _asked.get(t, 0) > 15:   # clients poll every 4 s while a tile loads
        return None
    iy, ix = t
    f = CACHE / f"{iy}_{ix}.json"
    q = _query(iy * TILE, ix * TILE, (iy + 1) * TILE, (ix + 1) * TILE)
    errs = []
    for url in tools.OVERPASS:
        try:
            d = json.loads(news._get(url, timeout=tools.OVERPASS_DEADLINE_S + 5, data=urllib.parse.urlencode({"data": q}).encode()))
        except Exception as ex:  # noqa: BLE001 - try the next mirror, then report
            errs.append(f"{url.split('/')[2]}: {str(ex)[:100]}")
            continue
        if "error" in (d.get("remark") or "").lower():   # timed out: the reply is incomplete
            errs.append(f"{url.split('/')[2]}: {d['remark'][:100]}")
            continue
        els = d.get("elements", [])
        val = {"items": _parse(els), "truncated": len(els) >= tools.FACILITY_CAP}
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=CACHE, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(val, fh, ensure_ascii=False)
            os.replace(tmp, f)
        except OSError:   # read-only disk or a concurrent writer: the answer still stands
            pass
        return val
    _failed_at[t] = time.time()
    raise RuntimeError("OpenStreetMap (Overpass) did not answer: " + "; ".join(errs))


def _job(t):
    with _lock:
        _asked[t] = time.time()
        j = _jobs.get(t)
        if j is None or (j.done() and (j.exception() is None and j.result() is None
                                       or j.exception() and time.time() - _failed_at.get(t, 0) > RETRY_S)):
            j = _jobs[t] = _pool.submit(_tile, t)
        return j


def _preset(t):
    """Build-time list of the preset area holding this tile, or None. Partial by construction (see module doc)."""
    s, w = t[0] * TILE, t[1] * TILE
    for rid, p in PRESETS.items():
        bw, bs, be, bn = p["bbox"]
        if not (bw <= w + TILE / 2 <= be and bs <= s + TILE / 2 <= bn):
            continue
        try:
            ex = tools._read(rid, "exposure")
        except tools.NotFound:
            return None
        inside = lambda la, lo: s <= la < s + TILE and w <= lo < w + TILE  # noqa: E731
        return ([[la, lo, "hospital", nm] for nm, la, lo, _ in ex.get("hospitals", []) if inside(la, lo)]
                + [[la, lo, "school", nm] for nm, la, lo, _, _k in ex.get("schools", []) if inside(la, lo)])
    return None


def facilities(west, south, east, north):
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("box must be west < east, south < north, in degrees")
    x0, x1 = math.floor(west / TILE), math.ceil(east / TILE)
    y0, y1 = math.floor(south / TILE), math.ceil(north / TILE)
    if (x1 - x0) * TILE > MAX_SIDE or (y1 - y0) * TILE > MAX_SIDE:
        raise ValueError(f"zoom in: schools and hospitals load for at most {MAX_SIDE:g}° × {MAX_SIDE:g}° at a time")
    tiles = [(iy, ix) for iy in range(y0, y1) for ix in range(x0, x1)]
    if tools.SERVERLESS:   # the function freezes after replying, so a background fetch never finishes: wait for it here
        wait([_job(t) for t in tiles if _disk(t) is None], timeout=50)   # Vercel maxDuration is 60 s
    items, loading, failed, partial, truncated = [], 0, set(), False, False
    for t in tiles:
        v = _disk(t)   # cached tiles are read here, never queued behind slow fetches
        fu = None if v else _job(t)
        if fu and fu.done() and not fu.exception() and fu.result():
            v = fu.result()
            with _lock:
                _jobs.pop(t, None)
                _asked.pop(t, None)
        if v:
            items += v["items"]
            truncated = truncated or v["truncated"]
            continue
        if fu.done() and fu.exception():
            failed.add(str(fu.exception())[:240])
        else:
            loading += 1
        stand = _preset(t)
        if stand is not None:
            items += stand
            partial = True
    return {"box": [x0 * TILE, y0 * TILE, x1 * TILE, y1 * TILE], "columns": ["lat", "lon", "kind", "name"],
            "items": items, "tiles": len(tiles), "loading": loading, "failed": sorted(failed), "partial": partial,
            "truncated": truncated,
            "source": "OpenStreetMap via Overpass (amenity school, kindergarten, college, university, hospital, clinic, "
                      "doctors, nursing_home, fire_station; healthcare hospital, clinic), cached a week",
            "note": ("While loading, or if OpenStreetMap failed, the area's build-time list stands in: named hospitals and "
                     "schools in cells with fire only.") if partial else None}


if __name__ == "__main__":   # self-check without the network: parsing and the zoom guard
    assert _parse([{"type": "node", "lat": 1, "lon": 2, "tags": {"amenity": "doctors", "name": "A"}},
                   {"type": "way", "center": {"lat": 3, "lon": 4}, "tags": {"social_facility": "nursing_home"}},
                   {"type": "node", "lat": 5, "lon": 6, "tags": {"amenity": "bench"}}]) == [[1, 2, "clinic", "A"], [3, 4, "care_home", ""]]
    try:
        facilities(75, 30, 77, 31)
        raise AssertionError("big box accepted")
    except ValueError:
        pass
    print("ok")
