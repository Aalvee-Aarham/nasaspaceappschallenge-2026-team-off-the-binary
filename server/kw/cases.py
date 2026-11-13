"""The casebook: every fire case heard by independent witnesses, with an agreement verdict.

Witnesses: the harmonized record (cell and area), a MODIS-only vs VIIRS-only cross-check, NASA EONET, GDACS and the
press. A witness that could not see says "abstain"; only a witness that could see and saw nothing says "quiet". A
missing report is never read as "no fire". Pure functions below; `build_cases` does the (optional) network fetching.

Reads the region files directly. Must not import `tools` (tools imports build, build imports this lazily).

    python -m kw.cases [area ...]   # rebuild cases.json from the committed region files (needs network for witnesses)
"""
import datetime as dt
import hashlib
import json
import math
import os
import sys

from . import news
from .firms import DATA

OUT = DATA / "regions"
OBSERVERS = ("MODIS_A", "MODIS_T", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21")
GRID_DEG = 0.1
MAX_CASES = 100
UNUSUAL_MONTHS = 12          # the record's own most unusual months, so cases span 2000 to today, not just the EONET era
AGREE_BAND = (0.8, 1.25)     # a judgement band for "the two instrument families agree", not a statistical test
FAINT = 1.0                  # a cell value below one Aqua-scale hotspot is flagged, never hidden
PRE_GDELT_QUERIES = 10       # Google News queries for months before GDELT coverage, at most per area
CAVEAT = "A witness that could not see says so. An absent report is not evidence that nothing happened."

VERDICTS = ("corroborated", "reported", "satellite_only", "agency_only", "abstained", "insufficient")
LABELS = {
    "corroborated": "Two independent witnesses agree",
    "reported": "Reported, not seen by the satellites",
    "satellite_only": "Only the satellites saw it",
    "agency_only": "The record missed it",
    "abstained": "The record could not see",
    "insufficient": "Nobody saw anything",
}
SEVERITY = {v: i for i, v in enumerate(("agency_only", "corroborated", "reported", "abstained", "satellite_only", "insufficient"))}


# ---------------------------------------------------------------- pure logic

def satellite_state(area_cov, cell_value, present_in_grid):
    """fire | quiet | abstain. Abstain when no satellite observed anywhere in the area that period."""
    if max(area_cov.values(), default=0) <= 0:
        return "abstain"
    if present_in_grid:
        return "fire" if (cell_value or 0) > 0 else "quiet"
    return "quiet"                                      # the cell was observed and had no fire


def cross_family(modis_only, viirs_only, coverage):
    if modis_only is None or viirs_only is None:
        return {"state": "abstain", "reason": "the region file predates the VIIRS-only series", "modis_only": modis_only,
                "viirs_only": viirs_only, "ratio": None, "agrees": None, "source": "kiln-watch"}
    if max(coverage.values(), default=0) <= 0:
        return {"state": "abstain", "reason": "no satellite observed", "modis_only": None, "viirs_only": None,
                "ratio": None, "agrees": None, "source": "kiln-watch"}
    if modis_only == 0 and viirs_only == 0:
        return {"state": "quiet", "reason": None, "modis_only": 0, "viirs_only": 0, "ratio": None, "agrees": True, "source": "kiln-watch"}
    r = viirs_only / modis_only if modis_only else None
    return {"state": "fire", "reason": None, "modis_only": modis_only, "viirs_only": viirs_only,
            "ratio": round(r, 3) if r is not None else None,
            "agrees": r is not None and AGREE_BAND[0] <= r <= AGREE_BAND[1], "source": "kiln-watch"}


def verdict(sat, cross, agency, disaster, press):
    """sat: fire|quiet|abstain. agency/disaster/press: a witness dict or None."""
    strong = [w for w in (agency, disaster) if w]       # an event record, not a mention
    if sat == "abstain":
        return "abstained"                              # the record cannot speak
    if sat == "fire":
        return "corroborated" if strong else "reported" if press else "satellite_only"
    if strong:
        return "agency_only"                            # the reverse direction: the record missed it
    return "reported" if press else "insufficient"


def cell_of(lat, lon):
    return round(math.floor(lat / GRID_DEG + 1e-9) * GRID_DEG, 2), round(math.floor(lon / GRID_DEG + 1e-9) * GRID_DEG, 2)


def _at(seq, i):
    return seq[i] if seq and i is not None and i < len(seq) else None


def satellite_witness(monthly, grid_months, cell_lookup, cell, period):
    """Both levels for one cell-month: the grid cell (where) and the area total (how unusual)."""
    i = monthly["periods"].index(period)
    cov = {o: monthly["coverage"][o][i] for o in OBSERVERS if o in monthly["coverage"]}
    veg = monthly["classes"]["veg"]
    rows = {ci: v for ci, v in grid_months.get(period, [])}
    ci = cell_lookup.get(cell)
    present = ci is not None and ci in rows
    cell_value = rows.get(ci) if present else None
    state = satellite_state(cov, cell_value, present)
    h, hist = veg["hotspots"], veg["history"]
    lo, hi = _at(h.get("lo"), i), _at(h.get("hi"), i)
    w = {
        "state": state, "reason": "no satellite observed in the area that month" if state == "abstain" else None,
        "cell_hotspots": cell_value, "cell_present": present, "area_hotspots": _at(h["v"], i),
        "ci95": [lo, hi] if lo is not None and hi is not None else None,
        "percentile": _at(hist.get("pct"), i), "rank": _at(hist.get("rank"), i), "of_years": _at(hist.get("n"), i),
        "coverage": max(cov.values(), default=None), "sensors": _at(h.get("sensors"), i) or [], "source": "kiln-watch",
    }
    cf = cross_family(_at(veg.get("aqua_only"), i), _at(veg.get("viirs_only"), i), cov)
    return w, cf, ci


def make_case(cid, title, date, lat, lon, place, period, cell, witnesses, ci, note=""):
    sat, cf = witnesses["satellite"], witnesses["cross_family"]
    v = verdict(sat["state"], cf, witnesses["agency"], witnesses["disaster_system"], witnesses["press"])
    flags = []
    if cf["state"] == "fire" and cf["agrees"] is False:
        flags.append("cross_family_disagree")
    if sat["state"] == "fire" and (sat["cell_hotspots"] or 0) < FAINT:
        flags.append("faint_cell_signal")
    return {"id": cid, "title": title, "date": date, "lon": lon, "lat": lat, "place": place, "period": period,
            "cell": list(cell), "cell_index": ci, "witnesses": witnesses, "verdict": v, "verdict_label": LABELS[v],
            "flags": flags, "note": note}


def _w(sat, cf, agency=None, disaster=None, press=None):
    return {"satellite": sat, "cross_family": cf, "agency": agency, "disaster_system": disaster, "press": press,
            "burned_area": None, "inventory": None}      # the last two are reserved for plans 010 and 011


def assemble(area, meta, monthly, grid, eonet_items, gdacs_items, press_counts, press_query, pre_press=None):
    """Cases from already-fetched witnesses. press_counts: {YYYY-MM: articles} or None when GDELT was unavailable."""
    cells = [tuple(c) for c in grid["cells"]]
    lookup = {c: i for i, c in enumerate(cells)}
    periods = set(monthly["periods"])
    bbox = meta["bbox"]
    inside = lambda lat, lon: bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]
    by_key = {}

    def press_for(period):
        if pre_press and period in pre_press:
            return pre_press[period]
        n = (press_counts or {}).get(period)
        if n:
            return {"source": "GDELT DOC", "count": n, "outlets": [], "sample_urls": [], "query": press_query}
        return None

    def slot(period, lat, lon, title, date, ident):
        cell = cell_of(lat, lon)
        key = (cell, period)
        if key not in by_key:
            sat, cf, ci = satellite_witness(monthly, grid["months"], lookup, cell, period)
            by_key[key] = {"ident": ident, "title": title, "date": date, "lat": lat, "lon": lon, "cell": cell, "ci": ci,
                           "period": period, "sat": sat, "cf": cf, "agency": None, "disaster": None, "n_events": 0}
        return by_key[key]

    for ev in sorted(eonet_items, key=lambda e: e.get("start_date") or e.get("date") or ""):
        d = ev.get("start_date") or ev.get("date") or ""
        if ev.get("lat") is None or ev.get("lon") is None or d[:7] not in periods or not inside(ev["lat"], ev["lon"]):
            continue
        eid = str(ev.get("id") or "").replace("EONET_", "") or hashlib.sha1(f"{ev.get('title')}{d}".encode()).hexdigest()[:8]
        s = slot(d[:7], ev["lat"], ev["lon"], ev.get("title") or "Wildfire event", d, f"eonet-{eid}")
        s["n_events"] += 1
        if s["agency"] is None:
            s["agency"] = {"source": "NASA EONET", "date": d, "url": f"https://eonet.gsfc.nasa.gov/api/v3/events/{ev['id']}" if ev.get("id") else ev.get("url")}
    for g in gdacs_items:
        d = g.get("date") or ""
        if g.get("lat") is None or d[:7] not in periods or not inside(g["lat"], g["lon"]):
            continue
        s = slot(d[:7], g["lat"], g["lon"], g.get("title") or "GDACS wildfire", d, "gdacs-" + hashlib.sha1(f"{g.get('title')}{d}{g['lat']}".encode()).hexdigest()[:8])
        if s["disaster"] is None:
            s["disaster"] = {"source": "GDACS", "alert": (g.get("alert") or "").lower() or None, "severity": g.get("severity"),
                             "burned_area_ha": g.get("burned_area_ha"), "date": d, "url": g.get("url")}

    cases = []
    for s in by_key.values():
        note = f"{s['n_events']} NASA EONET events fall in this cell and month; the earliest is shown." if s["n_events"] > 1 else ""
        cases.append(make_case(s["ident"], s["title"], s["date"], s["lat"], s["lon"], None, s["period"], s["cell"],
                               _w(s["sat"], s["cf"], s["agency"], s["disaster"], press_for(s["period"])), s["ci"], note))

    # The record's own most unusual complete months: found without any outside source, so they reach back to 2000.
    veg = monthly["classes"]["veg"]
    covered = {c["period"] for c in cases}
    ranked = sorted((i for i, p in enumerate(monthly["periods"])
                     if not monthly["partial"][i] and veg["history"]["pct"][i] is not None and (veg["hotspots"]["v"][i] or 0) > 0
                     and (veg["history"]["n"][i] or 0) >= 10),
                    key=lambda i: (-veg["history"]["pct"][i], -(veg["hotspots"]["v"][i] or 0)))
    for i in ranked[:UNUSUAL_MONTHS]:
        p = monthly["periods"][i]
        rows = grid["months"].get(p) or []
        if p in covered or not rows:
            continue
        ci, _ = max(rows, key=lambda r: r[1])
        cell = cells[ci]
        sat, cf, _ = satellite_witness(monthly, grid["months"], lookup, cell, p)
        lat, lon = cell[0] + GRID_DEG / 2, cell[1] + GRID_DEG / 2
        cases.append(make_case(f"rec-{p}-{ci}", f"One of the record's most unusual months in {meta['name']}", f"{p}-01", round(lat, 3), round(lon, 3),
                               meta["name"], p, cell, _w(sat, cf, press=press_for(p)), ci,
                               "Found by the record itself. The cell shown is the one with the most hotspots that month."))

    # Cap: newest first within a verdict; "the record missed it" gets at most two fifths so a month with dozens of
    # small agency incidents cannot push every other kind of case out of the list.
    newest = sorted(cases, key=lambda c: c["date"], reverse=True)
    miss = [c for c in newest if c["verdict"] == "agency_only"]
    rest = sorted((c for c in newest if c["verdict"] != "agency_only"), key=lambda c: SEVERITY[c["verdict"]])
    room = MAX_CASES * 2 // 5
    picked = miss[:room] + rest[:MAX_CASES - len(miss[:room])]
    picked += miss[room:][:MAX_CASES - len(picked)]
    kept = sorted(picked, key=lambda c: c["date"], reverse=True)
    found = {v: sum(1 for c in cases if c["verdict"] == v) for v in VERDICTS}
    counts = {v: sum(1 for c in kept if c["verdict"] == v) for v in VERDICTS}
    return kept, counts, len(cases) > len(kept), len(cases), found


# ---------------------------------------------------------------- fetching and storage

def _source(role, **kw):
    return {"name": kw["name"], "role": role, "searched": kw.get("searched", True), "error": kw.get("error"),
            "count": kw.get("count", 0), "note": kw.get("note"), "url": kw.get("url")}


def build_cases(region_id, meta, monthly, grid, fetch=True):
    """Fetch the outside witnesses (each optional) and assemble. A network failure never raises."""
    sources, eonet_items, gdacs_items, press_counts, query, pre_press = [], [], [], None, None, {}
    start, end = dt.date(2000, 11, 1), dt.date.fromisoformat(meta["data_through"])
    places, langs = meta.get("places") or [meta["name"]], meta.get("lang") or ["en"]
    if fetch:
        s, items = news._run("NASA EONET", "agency", lambda: news.eonet(meta["bbox"], start, end, 500), f"cases-eonet:{meta['bbox']}:{end}", end)
        eonet_items = items
        sources.append(_source("agency", name="NASA EONET", error=s["error"], count=s["count"], url=s.get("url")))
        from . import news_more
        s, items = news._run("GDACS", "disaster", lambda: news_more.gdacs(max(start, dt.date(2017, 1, 1)), end, meta["bbox"]),
                             f"cases-gdacs:{meta['bbox']}:{end}", end)
        gdacs_items = items
        sources.append(_source("disaster_system", name="GDACS", error=s["error"], count=s["count"], url=s.get("url")))
        s, res = news._run("GDELT DOC", "press", lambda: news.gdelt_volume(places, langs, max(start, news.GDELT_START), end),
                           f"cases-gdelt:{places}:{langs}:{end}", end)
        if not s["error"]:
            press_counts, query = res, s.get("query")
        sources.append(_source("press", name="GDELT DOC", error=s["error"], count=sum((press_counts or {}).values()),
                               url=s.get("url"), note="monthly article counts for the area's place names and fire words, 2017 onward"))
    else:
        for name, role in (("NASA EONET", "agency"), ("GDACS", "disaster_system"), ("GDELT DOC", "press")):
            sources.append(_source(role, name=name, searched=False, note="not searched: the case list was built from the record only"))

    kept, counts, capped, total, found = assemble(region_id, meta, monthly, grid, eonet_items, gdacs_items, press_counts, query, pre_press)

    # Months before GDELT: one Google News query per record-derived case, never per year.
    if fetch:
        from . import news_more
        done, errs = 0, []
        for c in kept:
            if c["period"] >= str(news.GDELT_START)[:7] or c["witnesses"]["press"] or done >= PRE_GDELT_QUERIES or not news_more.google_on():
                continue
            done += 1
            y, m = int(c["period"][:4]), int(c["period"][5:])
            a = dt.date(y, m, 1)
            b = (a.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
            lang = langs[0] if langs[0] in news_more.GN_LOCALE else "en"
            pl = " OR ".join(f'"{p}"' for p in places[:4])
            try:
                items, url, q = news._cached(f"cases-gn:{places}:{lang}:{a}", news._ttl(b),
                                             lambda lang=lang, pl=pl, a=a, b=b: news_more.google_news(f"({pl}) ({news_more.GN_WORDS[lang]})", lang, a, b))
                if items:
                    c["witnesses"]["press"] = {"source": "Google News RSS", "count": len(items),
                                               "outlets": list(dict.fromkeys(i["outlet"] for i in items if i.get("outlet")))[:5],
                                               "sample_urls": [i["url"] for i in items if i.get("url")][:5], "query": q}
                    old = c["verdict"]
                    c["verdict"] = verdict(c["witnesses"]["satellite"]["state"], c["witnesses"]["cross_family"], c["witnesses"]["agency"],
                                           c["witnesses"]["disaster_system"], c["witnesses"]["press"])
                    c["verdict_label"] = LABELS[c["verdict"]]
                    if old != c["verdict"]:
                        counts[old] -= 1
                        counts[c["verdict"]] += 1
            except Exception as ex:
                errs.append(str(ex)[:120])
        sources.append(_source("press", name="Google News RSS", searched=done > 0, count=done - len(errs), error=errs[0] if errs else None,
                               note="one query per record-derived case before 2017 (before GDELT coverage); counts queries answered"))
    if capped:
        sources.append(_source("agency", name="case list", count=total, note=f"capped at {MAX_CASES} of {total} cases found ({', '.join(f'{v} {n}' for v, n in found.items() if n)}); newest first, 'record missed it' limited to two fifths"))
    return {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "area": region_id,
            "data_through": meta["data_through"], "counts": counts, "found": found, "sources": sources, "caveat": CAVEAT, "cases": kept}


EXTERNAL = {
    "cases": [
        {"name": "NASA EONET (Earth Observatory Natural Event Tracker)", "role": "fire case witness", "url": "https://eonet.gsfc.nasa.gov/",
         "license": "public domain (NASA)"},
        {"name": "GDACS (European Commission JRC / UN OCHA)", "role": "fire case witness", "url": "https://www.gdacs.org/",
         "license": "GDACS terms of use"},
    ],
    "exposure": [
        {"name": "WorldPop Global 2000-2020 population grid, 1 km", "role": "population context", "url": "https://www.worldpop.org/",
         "license": "CC BY 4.0"},
        {"name": "OpenStreetMap contributors (Overpass API)", "role": "infrastructure context", "url": "https://www.openstreetmap.org/copyright",
         "license": "ODbL 1.0"},
    ],
}
METHOD = {
    "witnesses": ("Each fire case is heard by independent witnesses: the harmonized satellite record, a MODIS-against-VIIRS "
                  "cross-check, NASA EONET, GDACS and the press. A witness that could not see says so, so a missing report is "
                  "never read as 'no fire'."),
    "exposure": ("Population (WorldPop 2020, 1 km) and infrastructure (OpenStreetMap) inside the 0.1 degree cells where the "
                 "record shows fire. A context layer, not an impact estimate: there is no fire perimeter, no smoke and no fire "
                 "spread here."),
}


def annotate_meta(meta, folder):
    """Record what the case and exposure files provide, so the UI and Method page are data-driven."""
    feats, ext = {}, []
    for name in ("cases", "exposure"):
        f = folder / f"{name}.json"
        if f.exists():
            obj = json.loads(f.read_text(encoding="utf-8"))
            feats[name] = {"available": True, "built_at": obj.get("built_at")}
            if name == "cases":
                feats[name]["count"] = len(obj.get("cases", []))
            meta.setdefault("method", {})["witnesses" if name == "cases" else "exposure"] = METHOD["witnesses" if name == "cases" else "exposure"]
            ext += [{**e, "vintage": (obj.get("built_at") or "")[:10]} for e in EXTERNAL[name]]
        else:
            feats[name] = {"available": False, "reason": "not built for this area"}
    meta["features"] = feats
    meta["external_sources"] = ext
    return meta


def write_cases(folder, cases):
    tmp = folder / "cases.json.tmp"
    tmp.write_text(json.dumps(cases, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, folder / "cases.json")


def rebuild_area(area, fetch=True):
    """cases.json from the committed region files, then refresh meta.json's feature flags."""
    folder = OUT / area
    rd = lambda n: json.loads((folder / f"{n}.json").read_text(encoding="utf-8"))
    meta, monthly, grid = rd("meta"), rd("monthly"), rd("grid")
    cases = build_cases(area, meta, monthly, grid, fetch)
    write_cases(folder, cases)
    meta = annotate_meta(meta, folder)
    tmp = folder / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, folder / "meta.json")
    return cases


if __name__ == "__main__":
    index = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    for a in sys.argv[1:] or [r["id"] for r in index["regions"] if r.get("preset")]:
        c = rebuild_area(a)
        print(a, c["counts"], [f"{s['name']}: {s['error'] or s['count']}" for s in c["sources"]])
