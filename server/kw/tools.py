"""Deterministic query functions shared by the REST API, the MCP server and the Gemini agent.

Every number these return is read from build outputs or computed from cached NASA FIRMS rows — never generated.
"""
import datetime as dt
import functools
import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import duckdb

from . import cases, news
from . import science as sc
from .build import OUT, build_region, write_index
from .firms import BASE as FIRMS_BASE, CACHE, CONF_SQL, LIVE_TTL_S, SENSORS, connect, fetch_year
from .regions import PRESETS, validate_bbox


SERVERLESS = bool(os.environ.get("KW_SERVERLESS"))  # set by api/index.py (Vercel): read-only snapshot, no long jobs


class NotFound(Exception):
    pass


class TooManyRequests(Exception):
    pass


class Unavailable(Exception):
    pass


MAX_PENDING_BUILDS = 4
MAX_CUSTOM_AREAS = 20
MAX_CUSTOM_CACHE_BYTES = 2 * 1024 ** 3


def _custom_cache_bytes():
    return sum(f.stat().st_size for d in CACHE.glob("aoi-*") for f in d.rglob("*") if f.is_file())


def _read(region_id, name):
    f = OUT / region_id / f"{name}.json"
    if "/" in region_id or "\\" in region_id or ".." in region_id or not f.exists():
        raise NotFound(f"unknown region '{region_id}'")
    return _read_cached(str(f), f.stat().st_mtime)


@functools.lru_cache(maxsize=64)
def _read_cached(path, _mtime):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_regions():
    f = OUT / "index.json"
    items = json.loads(f.read_text(encoding="utf-8"))["regions"] if f.exists() else []
    return [r for r in items if is_built(r["id"])]  # index may list custom areas built on another machine


def region_summary(region_id):
    m = _read(region_id, "meta")
    val = next((v for v in m["validation"]["veg_det_D"] if v["sensor"] == "VIIRS_SNPP"), None)
    strip = lambda d: {k: v for k, v in (d or {}).items() if k != "series"}  # noqa: E731
    return {
        "id": m["id"], "name": m["name"], "country": m["country"], "bbox": m["bbox"], "story": m.get("story"),
        "data_through": m["data_through"], "unit": m["estimand"]["primary"], "answers": m["answers"]["sentences"],
        "current_period": m.get("current"), "trend_2003_2020": m["trend"]["2003-2020"], "trend_full": m["trend"]["full"],
        "steps": m["steps"], "placebo_steps": m.get("placebo"),
        "modis_denial_test": strip(m["denial"]["modis_ends_2016"]), "snpp_withheld_test": strip(m["denial"]["snpp_withheld"]),
        "snpp_to_aqua_daytime_holdout": val, "transfer_validation": m.get("transfer_validation"),
        "season": {k: (m["season"] or {}).get(k) for k in ("median", "trend", "next_4_weeks_share_pct", "year_to_date")},
        "totals": m["totals"], "satellites_last_observed": {s: v["last"] for s, v in m["sensors"].items()},
    }


def _block(region_id, granularity):
    if granularity not in ("month", "week"):
        raise ValueError("granularity must be 'month' or 'week'")
    return _read(region_id, "monthly" if granularity == "month" else "weekly")


RAW_OBS = ("MODIS_T", "MODIS_A", *[s for s in SENSORS if s != "MODIS"])


def _period_row(b, i, cls="veg"):
    c = b["classes"][cls]
    pick = lambda s: {"value": s["v"][i], "ci95": [s["lo"][i], s["hi"][i]]}  # noqa: E731
    h = c["history"]
    return {
        "period": b["periods"][i], "partial": b["partial"][i], "provisional": b["provisional"][i],
        "hotspots_aqua_scale": pick(c["hotspots"]),
        "hotspots_viirs_scale": {**pick(c["viirs_scale"]), "modelled": c["viirs_scale"]["modelled"][i]},
        "fire_celldays_aqua_scale": pick(c["celldays"]),
        "aqua_only_hotspots": c["aqua_only"][i],
        "vs_history": {"median_same_period": h["median"][i], "ratio_to_median": h["ratio"][i],
                       "percentile": h["pct"][i], "rank": h["rank"][i], "of_years": h["n"][i],
                       "recent_weighted": {"median": h.get("wmedian", [None] * (i + 1))[i], "ratio": h.get("wratio", [None] * (i + 1))[i],
                                           "percentile": h.get("wpct", [None] * (i + 1))[i], "half_life_years": sc.HALF_LIFE_YEARS}},
        "satellites_used": c["hotspots"]["sensors"][i],
        "coverage": {s: b["coverage"][s][i] for s in b["coverage"]},
        "raw_detections": {s: b["raw"][s]["det"][i] for s in RAW_OBS},
        "raw_detections_all_satellites": b["raw"]["all_det"][i],
        "static_source_hotspots_aqua_scale": b["classes"]["static"]["hotspots"]["v"][i],
        "nrt_share": b["nrt_share"][i],
        "nrt_unclassified_share": (b.get("nrt_unclassified_share") or [None] * len(b["periods"]))[i],
    }


def get_period(region_id, period, cls="veg"):
    b = _block(region_id, "week" if "-W" in period else "month")
    if period not in b["periods"]:
        raise NotFound(f"period '{period}' not in record ({b['periods'][0]} … {b['periods'][-1]})")
    return _period_row(b, b["periods"].index(period), cls)


def get_calendar(region_id, granularity="month", start=None, end=None, cls="veg"):
    b = _block(region_id, granularity)
    rows = [_period_row(b, i, cls) for i, p in enumerate(b["periods"])
            if (not start or p >= start) and (not end or p <= end)]
    return {"region": region_id, "granularity": granularity, "class": cls, "rows": rows}


def find_anomalies(region_id, granularity="month", min_percentile=90.0, top_n=10):
    """Periods ranking highest against the same month/week in other years (percentile, then ratio to median)."""
    b = _block(region_id, granularity)
    h = b["classes"]["veg"]["history"]
    idx = [i for i, p in enumerate(h["pct"]) if p is not None and p >= min_percentile]
    idx.sort(key=lambda i: (-h["pct"][i], -(h["ratio"][i] or 0)))
    return [_period_row(b, i) for i in idx[:top_n]]


def audit(region_id):
    m = _read(region_id, "meta")
    return {k: m.get(k) for k in ("estimand", "method", "calibration", "closure", "validation", "transfer_validation",
                                  "denial", "interval_scale", "steps", "placebo", "trend", "drift", "frp_distribution",
                                  "filter_sensitivity", "versions", "provenance", "sensors")}


def _cache_files(region_id, bbox, a, b):
    files = []
    for y in range(a.year, b.year + 1):
        f = CACHE / region_id / f"{y}.parquet"
        if not f.exists():
            if SERVERLESS:  # a serverless read must not download a year of FIRMS rows inside the request
                raise Unavailable("the raw detection cache is not on this server; run the API where data/cache is present")
            f.parent.mkdir(parents=True, exist_ok=True)
            fetch_year(connect(), bbox, y, f)
        files.append(f.as_posix())
    return files


def _detections(con, region_id, bbox, a, b):
    mask = (OUT / region_id / "mask.parquet").as_posix()
    con.execute(f"""CREATE OR REPLACE TABLE e AS
        SELECT r.*, CASE WHEN r.type IN (1,2,3) THEN 'static' WHEN r.type = 0 THEN 'veg'
                         WHEN k.fy IS NOT NULL THEN 'static' ELSE 'veg' END AS cls, {CONF_SQL} AS conf_ok
        FROM (SELECT *, floor(lat * 100)::INT AS fy, floor(lon * 100)::INT AS fx
              FROM read_parquet({_cache_files(region_id, bbox, a, b)})) r
        LEFT JOIN read_parquet('{mask}') k USING (fy, fx)
        WHERE acq_date BETWEEN DATE '{a}' AND DATE '{b}'""")


def evidence(region_id, period):
    """Detections behind one calendar cell, straight from the cached FIRMS rows."""
    m = _read(region_id, "meta")
    a, b = sc.period_bounds(period)
    con = duckdb.connect()
    _detections(con, region_id, m["bbox"], a, b)
    daily = con.execute("""SELECT acq_date::VARCHAR, sensor, cls, count(*), round(sum(frp), 1) FROM e WHERE conf_ok
                           GROUP BY ALL ORDER BY 1""").fetchall()
    top = con.execute("""SELECT strftime(acq_datetime, '%Y-%m-%d %H:%M'), satellite, sensor, daynight, quality, version,
                                cls, lat, lon, round(frp, 1), confidence, scan, track
                         FROM e WHERE conf_ok ORDER BY frp DESC NULLS LAST LIMIT 25""").fetchall()
    split = con.execute("SELECT cls, daynight, quality, count(*) FROM e WHERE conf_ok GROUP BY ALL").fetchall()
    peak = con.execute("""SELECT acq_date::VARCHAR, count(*) FROM e WHERE conf_ok AND cls = 'veg'
                          GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").fetchone()
    dropped = con.execute("SELECT count(*) FILTER (WHERE NOT conf_ok), count(*) FROM e").fetchone()
    w, s, e_, n = m["bbox"]
    day = peak[0] if peak else str(a)
    cx, cy = (w + e_) / 2, (s + n) / 2
    return {
        "region": region_id, "period": period, "start": str(a), "end": str(b),
        "daily": [{"date": d, "sensor": se, "class": c, "detections": k, "frp_mw": f} for d, se, c, k, f in daily],
        "top_detections": [dict(zip(("time_utc", "satellite", "sensor", "daynight", "quality", "version", "class",
                                     "lat", "lon", "frp_mw", "confidence", "scan", "track"), r)) for r in top],
        "split": [{"class": c, "daynight": dn, "quality": q, "detections": k} for c, dn, q, k in split],
        "peak_day": peak and {"date": peak[0], "detections": peak[1]},
        "low_confidence_excluded": {"excluded": dropped[0], "of": dropped[1]},
        "links": {
            "firms_map": f"https://firms.modaps.eosdis.nasa.gov/map/#d:{day}..{day};@{cx:.2f},{cy:.2f},8.0z",
            "worldview": (f"https://worldview.earthdata.nasa.gov/?v={w},{s},{e_},{n}&t={day}"
                          "&l=VIIRS_NOAA20_Thermal_Anomalies_375m_All,MODIS_Combined_Thermal_Anomalies_All,"
                          "VIIRS_NOAA20_CorrectedReflectance_TrueColor,Coastlines_15m"),
        },
        "note": "Coordinates are pixel centres, not fire locations. Low-confidence detections are excluded, as in "
                "the calendar.",
    }


def hotspots_csv(region_id, start, end):
    """The detections behind the calendar, streamed in chunks: FIRMS columns plus satellite, static-source flag and version."""
    m = _read(region_id, "meta")
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if b < a or (b - a).days > 366:
        raise ValueError("date range must be 1–366 days")
    con = duckdb.connect()
    _detections(con, region_id, m["bbox"], a, b)
    cur = con.execute("""SELECT lat AS latitude, lon AS longitude, strftime(acq_datetime, '%Y-%m-%d') AS acq_date,
                                strftime(acq_datetime, '%H%M') AS acq_time, satellite, sensor, confidence, version, quality,
                                frp, daynight, scan, track, type, cls = 'static' AS static_source,
                                conf_ok AS used_in_calendar
                         FROM e ORDER BY acq_datetime""")
    cols = [d[0] for d in cur.description]

    def rows():
        try:
            yield ",".join(cols) + "\n"
            while chunk := cur.fetchmany(10_000):
                for row in chunk:
                    yield ",".join("" if v is None else str(v) for v in row) + "\n"
        finally:
            con.close()

    return rows()


def reports(region_id, period):
    m = _read(region_id, "meta")
    hist = None
    try:
        hist = get_period(region_id, period)["vs_history"]
    except NotFound:
        pass
    return news.reports(m, period, hist)


def timeline_reports(region_id, start, end):
    """News/event reports for a month range ('YYYY-MM'..'YYYY-MM'), each month matched against the record."""
    if not all(len(x) == 7 and x[4] == "-" for x in (start, end)) or start > end:
        raise ValueError("start and end must be 'YYYY-MM' months with start <= end")
    b, m = _block(region_id, "month"), _read(region_id, "meta")
    h, v = b["classes"]["veg"]["history"], b["classes"]["veg"]["hotspots"]["v"]
    wp, wr = h.get("wpct") or [None] * len(v), h.get("wratio") or [None] * len(v)
    months = [{"period": p, "value": v[i], "percentile": h["pct"][i], "recent_percentile": wp[i], "ratio": h["ratio"][i],
               "recent_ratio": wr[i], "rank": h["rank"][i], "of_years": h["n"][i], "partial": b["partial"][i]}
              for i, p in enumerate(b["periods"]) if start <= p <= end]
    if not months:
        raise NotFound(f"no months between {start} and {end} in the record")
    from . import agent  # late import: agent imports this module
    classify = agent.classify_headlines if agent.available() else None
    return news.timeline(m, sc.period_bounds(months[0]["period"])[0], sc.period_bounds(months[-1]["period"])[1], months,
                         weekly=_block(region_id, "week"), classify=classify)


# ---------- early warning ----------

LEVELS = ("elevated", "watch", "normal", "quiet", "insufficient")


def _next_weeks(b, k=4):
    """Typical total of the next k weeks (10th/50th/90th percentile over earlier years) and the weeks themselves."""
    h = b["classes"]["veg"]["hotspots"]["v"]
    pos = {p: i for i, p in enumerate(b["periods"])}
    last = max((i for i, p in enumerate(b["partial"]) if not p), default=len(b["periods"]) - 1)  # as the season card
    y0, w0 = int(b["periods"][last][:4]), int(b["periods"][last][6:])
    weeks = [((w0 + j - 1) % 52 + 1, y0 + (w0 + j - 1) // 52) for j in range(1, k + 1)]  # ponytail: skips ISO week 53
    sums = []
    for dy in range(1, y0 - int(b["periods"][0][:4]) + 1):
        idx = [pos.get(f"{y - dy}-W{w:02d}") for w, y in weeks]
        if all(i is not None and h[i] is not None and not b["partial"][i] for i in idx):
            sums.append(sum(h[i] for i in idx))
    q = sc.quantiles(sums, 11) if len(sums) >= 8 else None
    return {"weeks": [f"W{w:02d}" for w, _ in weeks], "years_used": len(sums),
            "p10": q and round(q[1]), "median": q and round(q[5]), "p90": q and round(q[9])}


def early_warning(region_id):
    """Climatological outlook: this month and recent weeks against the same days in earlier years, plus the usual
    next four weeks. Deterministic and explainable; not a forecast and not an official alert."""
    m, wk = _read(region_id, "meta"), _read(region_id, "weekly")
    cur, season = m.get("current"), m.get("season")
    prior = [v for _, v in (cur or {}).get("prior", [])]
    pct_m = sc.percentile_rank(cur["value"], prior) if cur else None
    hist = wk["classes"]["veg"]["history"]
    recent = [{"period": p, "value": wk["classes"]["veg"]["hotspots"]["v"][i], "percentile": hist["pct"][i],
               "median": hist["median"][i], "partial": wk["partial"][i]}
              for i, p in enumerate(wk["periods"]) if i >= len(wk["periods"]) - 12]
    complete = [r for r in recent if not r["partial"] and r["percentile"] is not None]
    pct_w = complete[-1]["percentile"] if complete else None
    typical = sorted(y["total"] for y in (season or {}).get("years", []))
    typical_total = typical[len(typical) // 2] if typical else 0
    scale = max(cur["value"], cur["median"]) if cur else 0
    level = sc.warning_level(pct_m, pct_w, typical_total, len(prior), scale)
    nxt = _next_weeks(wk)
    ytd = (season or {}).get("year_to_date")
    share = (season or {}).get("next_4_weeks_share_pct")
    age = (dt.date.today() - dt.date.fromisoformat(m["data_through"])).days
    head = {
        "insufficient": ("Not scored: too few hotspots at this time of year to rank this month against earlier ones."
                         if typical_total >= 100 and len(prior) >= 10 else
                         "Not scored: a typical year here has fewer than 100 hotspots, or fewer than 10 earlier years exist."),
        "elevated": f"{cur and cur['sentence']} That is in the top tenth of earlier years.",
        "watch": f"{cur and cur['sentence']} Above normal, not yet in the top tenth.",
        "normal": f"{cur and cur['sentence']} Within the normal range.",
        "quiet": f"{cur and cur['sentence']} Among the quietest for this time of year.",
    }[level]
    return {
        "region_id": region_id, "name": m["name"], "country": m["country"], "level": level, "headline": head,
        "as_of": m["data_through"], "stale": age > 7, "rule": sc.WARNING_RULE,
        "month": cur and {"period": cur["period"], "days": cur["days"], "value": cur["value"], "ci95": [cur["lo"], cur["hi"]],
                          "median_same_days": cur["median"], "percentile": pct_m, "rank": cur["rank"],
                          "of_years": cur["n_prior"] + 1},
        "latest_complete_week_percentile": pct_w, "recent_weeks": recent,
        "next_4_weeks": {**nxt, "usual_share_of_year_pct": share},
        "year_to_date": ytd,
        "backtest": m.get("warning_backtest"),
        "caveat": "Climatological outlook from harmonized satellite detections. It compares with earlier years and "
                  "does not forecast weather, fire behaviour or burned area. Not an official alert; detections are "
                  "not confirmed fires. Recent days may be near-real-time and are provisional.",
    }


def warnings(min_level=None):
    """Early-warning status for every area, most serious first. min_level keeps that level and worse."""
    if min_level is not None and min_level not in LEVELS[:3]:
        raise ValueError("min_level must be elevated, watch or normal")
    out, as_of = [], None
    for r in list_regions():
        try:
            w = early_warning(r["id"])
            as_of = max(as_of or "", w["as_of"])
        except (NotFound, KeyError, StopIteration):
            continue  # area built before a field existed; skipped, not guessed
        if min_level is None or LEVELS.index(w["level"]) <= LEVELS.index(min_level):
            bt = w.get("backtest") or {}
            e = (bt.get("by_day") or {}).get("15", {}).get("elevated") if bt.get("scored") else None
            out.append({k: w[k] for k in ("region_id", "name", "country", "level", "headline", "as_of", "stale")}
                       | {"percentile": (w["month"] or {}).get("percentile"), "next_4_weeks_median": w["next_4_weeks"]["median"],
                          # how the same rule did on the 15th of every earlier month here (pod: share of top-tenth months it
                          # had flagged; far: share of its flags that were wrong; pss: 0 = chance, 1 = perfect)
                          "backtest": {k: e.get(k) for k in ("pod", "far", "pss", "n")} if e else None,
                          "backtest_reason": None if e else bt.get("reason") or "not backtested"})
    out.sort(key=lambda a: (LEVELS.index(a["level"]), -(a["percentile"] or 0)))
    return {"as_of": as_of, "count": len(out), "alerts": out,
            "rule": sc.WARNING_RULE, "disclaimer": "Climatological outlook, not a forecast or an official alert."}


def active_events():
    """Open NASA EONET wildfire events, each tagged with the Kiln Watch area it falls inside (if any)."""
    areas = list_regions()
    out = []
    for e in news.open_wildfires():
        hit = next((a["id"] for a in areas if a["bbox"][1] <= e["lat"] <= a["bbox"][3]
                    and (a["bbox"][0] <= e["lon"] <= a["bbox"][2] if a["bbox"][0] <= a["bbox"][2]
                         else e["lon"] >= a["bbox"][0] or e["lon"] <= a["bbox"][2])), None)
        out.append({**e, "region_id": hit})
    return {"source": "NASA EONET (open wildfire events)", "count": len(out), "events": out,
            "note": "Events are what agencies and media reported to EONET. Few events does not mean few fires."}

# ---------- custom areas ----------

_jobs, _jobs_lock, _build_slots = {}, threading.Lock(), threading.Semaphore(2)


def aoi_id(bbox):
    w, s, e, n = validate_bbox(bbox)
    return "aoi-" + hashlib.sha1(f"{w:.2f},{s:.2f},{e:.2f},{n:.2f}".encode()).hexdigest()[:10]


def start_aoi(bbox, name=None):
    bbox = validate_bbox(bbox)
    rid = aoi_id(bbox)
    with _jobs_lock:
        job = _jobs.get(rid)
        if job and job["status"] == "running":
            return {"id": rid, **job}
        if (OUT / rid / "meta.json").exists():
            return {"id": rid, "status": "ready"}
        if SERVERLESS:  # a build runs for minutes in a background thread; serverless functions freeze after replying
            raise ValueError("Building a new area takes a few minutes, longer than this hosted demo allows. The prebuilt "
                             "areas all work here; run Kiln Watch with Docker (see the README) to build any place.")
        running = sum(j.get("status") == "running" for j in _jobs.values())
        if running >= MAX_PENDING_BUILDS:
            raise TooManyRequests(f"the build queue is full ({running}/{MAX_PENDING_BUILDS}); try again later")
        custom = [d for d in CACHE.glob("aoi-*") if d.is_dir()]
        if len(custom) >= MAX_CUSTOM_AREAS:
            raise TooManyRequests(f"this server keeps at most {MAX_CUSTOM_AREAS} custom areas; delete one first")
        if _custom_cache_bytes() >= MAX_CUSTOM_CACHE_BYTES:
            raise TooManyRequests("custom-area storage is full; delete an old custom area first")
        _jobs[rid] = {"status": "running", "done": 0, "total": 0, "stage": "queued", "error": None}

    def run():
        with _build_slots:
            try:
                w, s, e, n = bbox
                place = news.reverse_geocode((s + n) / 2, ((w + e) / 2) if w <= e else ((w + e + 360) / 2 - 360))
                info = {"name": name or place.get("name") or f"Custom area {rid[4:]}", "country": place.get("country"),
                        "bbox": bbox, "places": place.get("places", []), "lang": place.get("lang", ["en"]),
                        "story": "Custom area drawn on the map."}

                def progress(y, d, t):
                    _jobs[rid].update(done=d, total=t, stage=f"reading {y}")

                build_region(rid, info, progress)
                write_index()
                _jobs[rid].update(status="ready", stage="ready")
            except Exception as ex:  # surfaced to the UI, never swallowed
                _jobs[rid].update(status="error", error=str(ex))

    threading.Thread(target=run, daemon=True).start()
    return {"id": rid, **_jobs[rid]}


def is_built(rid):
    return (OUT / rid / "meta.json").exists()


def refresh_if_stale(rid):
    """Keep any area live: when its record is older than the FIRMS cache TTL, rebuild it in the background (only the
    current year is re-read) and keep serving the old record meanwhile. Returns True while a rebuild is running."""
    if SERVERLESS:  # serves the deployed snapshot; a frozen background thread would only waste compute
        return False
    m = _read(rid, "meta")
    age = time.time() - dt.datetime.fromisoformat(m["built_at"]).timestamp()
    with _jobs_lock:
        job = _jobs.get(rid)
        if job and job["status"] == "running":
            return True
        if age < LIVE_TTL_S or (job and job["status"] == "error" and time.time() - job.get("at", 0) < 3600):
            return False  # fresh enough, or a refresh failed within the hour: do not hammer the mirror
        _jobs[rid] = {"status": "running", "done": 0, "total": 0, "stage": "refreshing", "error": None}
    info = {k: m.get(k) for k in ("name", "country", "story", "places", "lang")} | {"bbox": m["bbox"]}

    def run():
        with _build_slots:
            try:
                build_region(rid, info, lambda y, d, t: _jobs[rid].update(done=d, total=t, stage=f"reading {y}"))
                write_index()
                _jobs[rid].update(status="ready", stage="ready")
            except Exception as ex:  # old record stays; error is reported and retried after an hour
                _jobs[rid].update(status="error", error=str(ex), at=time.time())

    threading.Thread(target=run, daemon=True).start()
    return True


def aoi_status(rid):
    if rid in _jobs:
        return {"id": rid, **_jobs[rid]}
    if (OUT / rid / "meta.json").exists():
        return {"id": rid, "status": "ready"}
    raise NotFound(rid)


# ---------- any box, any dates: straight from the global aggregate ----------

MAX_QUERY_DEG2 = 400  # 20 x 20 degrees


def _box_sql(w, s, e, n):
    lon = (f"gx >= {math.floor(w * 10)} AND gx < {math.ceil(e * 10)}" if w <= e
           else f"(gx >= {math.floor(w * 10)} OR gx < {math.ceil(e * 10)})")
    return f"gy >= {math.floor(s * 10)} AND gy < {math.ceil(n * 10)} AND {lon}"


def global_hotspots(bbox, start, end):
    """Raw FIRMS detections for ANY box and date range (up to 366 days, 400 square degrees), per day and satellite,
    from the whole-Earth 0.1-degree aggregate. Raw counts: compare satellites within a day, not across eras."""
    from .globe import OUT as GLOBAL
    w, s, e, n = (float(v) for v in bbox)
    if not (-180 <= w <= 180 and -180 <= e <= 180 and -90 <= s < n <= 90):
        raise ValueError("bbox out of range")
    if ((e - w) if e > w else (e + 360 - w)) * (n - s) > MAX_QUERY_DEG2:
        raise ValueError(f"box must be at most {MAX_QUERY_DEG2} square degrees")
    a, b = dt.date.fromisoformat(str(start)), dt.date.fromisoformat(str(end))
    if b < a or (b - a).days > 366:
        raise ValueError("date range must be 1-366 days")
    files = [f.as_posix() for y in range(a.year, b.year + 1) if (f := GLOBAL / f"agg-{y}.parquet").exists()]
    if not files:
        raise NotFound("the global aggregate is not on this server (python -m kw.globe); use a built area instead")
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    src = f"""(SELECT *, CASE WHEN sensor = 'MODIS' THEN 'MODIS_' || sat ELSE sensor END AS satellite
               FROM read_parquet({files}) WHERE ok AND acq_date BETWEEN DATE '{a}' AND DATE '{b}' AND {_box_sql(w, s, e, n)})"""
    daily = con.execute(f"""SELECT acq_date::VARCHAR, satellite, sum(n) FILTER (WHERE tcls <> 's')::INT,
                                   sum(n) FILTER (WHERE tcls = 's')::INT, round(sum(frp), 1)
                            FROM {src} GROUP BY ALL ORDER BY 1, 2""").fetchall()
    top = con.execute(f"""SELECT gy, gx, sum(n)::INT AS k, round(sum(frp), 1) FROM {src} WHERE tcls <> 's'
                          GROUP BY ALL ORDER BY k DESC LIMIT 10""").fetchall()
    con.close()
    tot = {}
    for _, sat, v, st, _f in daily:
        t = tot.setdefault(sat, {"vegetation": 0, "static_typed": 0})
        t["vegetation"] += v or 0
        t["static_typed"] += st or 0
    return {
        "bbox": [w, s, e, n], "start": str(a), "end": str(b),
        "totals_by_satellite": tot,
        "daily": [{"date": d, "satellite": sat, "detections": v or 0, "static_typed": st or 0, "frp_mw": f} for d, sat, v, st, f in daily],
        "top_cells": [{"lat": round((gy + 0.5) / 10, 2), "lon": round((gx + 0.5) / 10, 2), "detections": k, "frp_mw": f}
                      for gy, gx, k, f in top],
        "note": "Raw detections (confidence-filtered), not harmonized: each satellite sees different numbers, so compare "
                "one satellite across days or build the area for the harmonized 2000-present record. Static sources are "
                "only removed where FIRMS typed them (recent near-real-time rows are untyped).",
    }


def annual(region_id):
    """Per complete year: harmonized hotspots (Aqua scale) next to raw detections of all satellites, the series that
    shows why harmonization matters (raw jumps at each VIIRS launch)."""
    b = _block(region_id, "month")
    v, raw, aqua = b["classes"]["veg"]["hotspots"]["v"], b["raw"]["all_det"], b["classes"]["veg"]["aqua_only"]
    years = {}
    for i, p in enumerate(b["periods"]):
        y = years.setdefault(int(p[:4]), {"n": 0, "h": 0.0, "r": 0, "a": 0.0, "ok": True})
        y["n"] += 1
        y["ok"] &= not b["partial"][i] and v[i] is not None
        y["h"] += v[i] or 0
        y["r"] += raw[i] or 0
        y["a"] += aqua[i] or 0
    return [{"year": y, "harmonized": round(d["h"]), "raw_all_satellites": d["r"], "aqua_only": round(d["a"]),
             "complete": d["ok"] and d["n"] == 12} for y, d in sorted(years.items())]


def _iso_week(season, offset):
    return (season["fire_year_start_week"] - 1 + offset) % 52 + 1


def season_profile(region_id):
    m = _read(region_id, "meta")
    s = m.get("season")
    if not s:
        return {"region_id": region_id, "season": None, "note": "too few hotspots to define a fire season"}
    med = s["median"]
    return {"region_id": region_id, "name": m["name"], "peak_months": m["answers"]["peak_months"],
            "peak_share_pct": m["answers"]["peak_share_pct"],
            "typical_season_iso_weeks": {k: _iso_week(s, med[k]) for k in ("start", "peak", "end")},
            "season_length_weeks": med["end"] - med["start"] + 1, "trend": s["trend"],
            "next_4_weeks_share_pct": s.get("next_4_weeks_share_pct"), "year_to_date": s.get("year_to_date"),
            "definition": "start/end = weeks when 10%/90% of the fire year's hotspots have burned; the fire year starts "
                          "at the quietest week, so seasons crossing 1 January are not split"}


def compare_areas(region_ids):
    """Side by side: early-warning level, season, trend and the last 10 complete years for 2-6 built areas."""
    ids = list(dict.fromkeys(region_ids))[:6]
    if len(ids) < 2:
        raise ValueError("give 2 to 6 region ids")
    out = []
    for rid in ids:
        m = _read(rid, "meta")
        ew = early_warning(rid)
        yrs = [y for y in annual(rid) if y["complete"]][-10:]
        out.append({"region_id": rid, "name": m["name"], "level": ew["level"], "headline": ew["headline"],
                    "peak_months": m["answers"]["peak_months"], "trend_full_harmonized": m["trend"]["full"]["harmonized"],
                    "last_10_years": [{"year": y["year"], "harmonized": y["harmonized"]} for y in yrs],
                    "median_year": sorted(y["harmonized"] for y in yrs)[len(yrs) // 2] if yrs else None})
    return {"areas": out, "unit": "hotspots on the Aqua MODIS scale (harmonized)"}


def find_place(query):
    """Any place name -> centre, box and the built areas overlapping it (shared by MCP and the analyst)."""
    from . import news_more  # local import: only this lookup needs it
    g = news_more.geocode(query)
    if not g:
        return {"found": False, "query": query, "candidates": []}
    w, s, e, n = g["bbox"]
    near = [r for r in list_regions() if not (r["bbox"][2] < w or r["bbox"][0] > e or r["bbox"][3] < s or r["bbox"][1] > n)]
    candidates = g.get("candidates") or [g]
    return {"found": True, **g, "candidates": candidates, "built_areas_overlapping": [{"id": r["id"], "name": r["name"]} for r in near]}


def sensor_status():
    """Last day each satellite delivered data, measured from the records (never hard-coded)."""
    last = {}
    for r in list_regions():
        for s_, d in (r.get("sensors_last") or {}).items():
            last[s_] = max(last.get(s_, ""), d)
    newest = max(last.values(), default=None)
    return {"last_observed": last, "newest": newest,
            "silent_over_3_days": [s_ for s_, d in last.items() if newest and (dt.date.fromisoformat(newest) - dt.date.fromisoformat(d)).days > 3],
            "note": "Derived from the data: the latest detection per satellite across all built areas. "
                    "silent_over_3_days lists satellites with no detection in the 3 days before the newest one."}


def briefing(region_id):
    """Deterministic situation brief (markdown) for fire managers: every number from the record, nothing generated."""
    from . import outlook
    m = _read(region_id, "meta")
    ew = early_warning(region_id)
    try:
        ol = outlook.in_box(m["bbox"], limit=5)
    except Exception:
        ol = None
    ev = [e for e in active_events()["events"] if e["region_id"] == region_id][:5]
    sp = season_profile(region_id)
    t = m["trend"]["full"]["harmonized"]
    mo, nx = ew["month"], ew["next_4_weeks"]
    L = [f"# Fire situation brief: {m['name']}", f"Data through **{ew['as_of']}**. Early-warning level: **{ew['level'].upper()}**.",
         "", ew["headline"], "", "## This month"]
    if mo:
        L.append(f"- {mo['period']} so far ({mo['days']} days): **{mo['value']:.0f}** hotspots (95% interval "
                 f"{mo['ci95'][0]:.0f}-{mo['ci95'][1]:.0f}); median of the same days in earlier years **{mo['median_same_days']:.0f}**; "
                 f"rank {mo['rank']} of {mo['of_years']}.")
    if ew["latest_complete_week_percentile"] is not None:
        L.append(f"- Latest complete week: {ew['latest_complete_week_percentile']:.0f}th percentile of the same week in earlier years.")
    L += ["", "## Next 30 days (climatology, not a forecast)"]
    if nx["median"] is not None:
        L.append(f"- Usual next four weeks ({nx['weeks'][0]}-{nx['weeks'][-1]}): **{nx['median']}** hotspots "
                 f"(10th-90th percentile {nx['p10']}-{nx['p90']}).")
    if ol:
        c = ol["counts"]
        L.append(f"- Outlook grid in this area: **{c['watch']}** watch cells (season ahead and already above normal), "
                 f"{c['above']} above normal, {c['season']} in an active season; {ol['rising']} where the season usually ramps up now.")
    if sp.get("typical_season_iso_weeks"):
        w = sp["typical_season_iso_weeks"]
        L.append(f"- Typical season: starts ISO week {w['start']}, peaks week {w['peak']}, ends week {w['end']}.")
    L += ["", "## Reported events (NASA EONET, open now)"]
    L += [f"- {e['title']} ({e['date']})" for e in ev] or ["- None listed inside this area (absence of reports is not evidence of absence)."]
    L += ["", "## Long term", f"- Seasonal Mann-Kendall test on monthly harmonized hotspots, {t['years'][0]}-{t['years'][1]}: "
          f"Sen slope {t['sen_per_year']} per year, p = {t['p']}" + (" (no significant trend)." if (t["p"] or 1) >= 0.05 else "."), *[f"- {x}" for x in m["answers"]["sentences"][:2]], "",
          "_Satellite hotspots, harmonized across MODIS and VIIRS (Aqua MODIS scale). Detections are not confirmed fires "
          "and not burned area. Compared with history; not a forecast or an official alert._"]
    return {"region_id": region_id, "markdown": "\n".join(L), "level": ew["level"], "as_of": ew["as_of"]}


def list_cases(region_id, verdict=None, limit=50):
    """Fire cases for an area, each with its witnesses and an agreement verdict."""
    if verdict and verdict not in cases.VERDICTS:
        raise ValueError(f"verdict must be one of: {', '.join(cases.VERDICTS)}")
    c = _read(region_id, "cases")
    rows = [x for x in c["cases"] if not verdict or x["verdict"] == verdict]
    return {"region_id": region_id, "as_of": c["built_at"], "data_through": c.get("data_through"), "counts": c["counts"],
            "sources": c["sources"], "caveat": c.get("caveat", cases.CAVEAT), "total": len(rows), "cases": rows[:limit]}


def get_case(region_id, case_id):
    for x in _read(region_id, "cases")["cases"]:
        if x["id"] == case_id:
            return x
    raise NotFound(f"no case '{case_id}' in '{region_id}'")


FARM_SHARE = 0.5   # a cell is "mostly farmland" when cropland covers at least half of it (ESA WorldCover 2021)


def _aligned_grid(region_id):
    """grid.json re-indexed onto exposure.json's cells, matched by coordinates. A live refresh rebuilds grid.json and
    may reorder or add cells; exposure.json (and the cell indices its hospitals, schools and roads carry) keeps the
    order of its own build. Cells with fire that are newer than the exposure build have no exposure data and are left
    out, and counted in 'cells_without_exposure'."""
    g, e = OUT / region_id / "grid.json", OUT / region_id / "exposure.json"
    if not e.exists():
        return _read(region_id, "grid")
    return _aligned_cached(region_id, g.stat().st_mtime, e.stat().st_mtime)


@functools.lru_cache(maxsize=16)
def _aligned_cached(region_id, _gm, _em):
    grid, ex = _read(region_id, "grid"), _read(region_id, "exposure")
    cells = [c[:2] for c in ex["cells"]]
    if cells == grid["cells"]:
        return {**grid, "cells_without_exposure": 0}
    where = {tuple(c): i for i, c in enumerate(cells)}
    remap = [where.get(tuple(c)) for c in grid["cells"]]
    months = {k: [[remap[ci], v] for ci, v in rows if remap[ci] is not None] for k, rows in grid["months"].items()}
    return {**grid, "cells": cells, "months": months, "cells_without_exposure": sum(r is None for r in remap)}


@functools.lru_cache(maxsize=16)
def _fire_profile(region_id, _mtime):
    """Per grid cell, from grid.json: months with fire, last month with fire, and per calendar month the number of
    years with fire and the summed hotspots. Cached per file version; callers must not mutate it."""
    grid = _aligned_grid(region_id)
    n = len(grid["cells"])
    on, last = [0] * n, [None] * n
    cal_years = [[0] * 12 for _ in range(n)]
    cal_hot = [[0.0] * 12 for _ in range(n)]
    years_of_month = [set() for _ in range(12)]          # record years that hold each calendar month
    for k in sorted(grid["months"]):
        m = int(k[5:]) - 1
        years_of_month[m].add(k[:4])
        for ci, v in grid["months"][k]:
            on[ci] += 1
            last[ci] = k
            cal_years[ci][m] += 1
            cal_hot[ci][m] += v
    return {"on": on, "last": last, "cal_years": cal_years, "cal_hot": cal_hot,
            "years_of_month": [len(y) for y in years_of_month]}


def _profile(region_id):
    e = OUT / region_id / "exposure.json"
    return _fire_profile(region_id, ((OUT / region_id / "grid.json").stat().st_mtime, e.stat().st_mtime if e.exists() else 0))


def _cell_km2(lat0, deg=0.1):
    return (111.32 * deg) ** 2 * math.cos(math.radians(lat0 + deg / 2))


def _gc_km(la1, lo1, la2, lo2):
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    return 6371.0 * math.acos(max(-1.0, min(1.0, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl))))


def exposure(region_id, period=None):
    """Population and infrastructure in the 0.1 degree cells where the record shows fire. Context, not impact."""
    if period and not (len(period) == 7 and period[4] == "-" and period[:4].isdigit() and period[5:].isdigit() and 1 <= int(period[5:]) <= 12):
        raise ValueError("period must be a calendar month, 'YYYY-MM'")
    try:
        ex = _read(region_id, "exposure")
    except NotFound:
        raise NotFound(f"no exposure layer built for '{region_id}'")
    grid = _aligned_grid(region_id)
    fire = {ci for ci, _ in grid["months"].get(period, [])} if period else {ci for rows in grid["months"].values() for ci, _ in rows}
    cells = ex["cells"]   # [lat, lon, population, hospitals, clinics, schools, cropland_km2]: index-parallel with grid.cells
    cols = ex.get("cell_columns") or []
    err = ex["infrastructure"].get("errors") or {}
    has_schools = "schools" in cols and "schools" not in err   # files built before schools: unknown, not 0
    has_named = has_schools and "school_columns" in ex
    has_crop = "cropland_km2" in cols and "cropland" not in err
    school = lambda ci: cells[ci][5] if has_schools else 0
    crop = lambda ci: cells[ci][6] if has_crop else 0
    prof = _profile(region_id)
    on, last = prof["on"], prof["last"]

    def place(row, columns):   # a named facility, with how often fire is seen in its 11 km cell
        d = dict(zip(columns, row))
        ci = d["cell"]
        d["cell"] = grid["cells"][ci]
        d["months_with_fire"], d["last_fire"] = on[ci], last[ci]
        return d
    rank = lambda h: (-h["months_with_fire"], h["name"])
    hosp = sorted((place(h, ex["hospital_columns"]) for h in ex["hospitals"] if h[3] in fire), key=rank)
    schools = sorted((place(r, ex["school_columns"]) for r in ex["schools"] if r[3] in fire), key=rank) if has_named else []
    roads = [dict(zip(ex["road_columns"], r)) for r in ex["roads"] if fire.intersection(r[4])]
    for r in roads:
        r["cells"] = [grid["cells"][ci] for ci in r["cells"] if ci in fire]
    farm, farm_cells = None, []
    if has_crop:
        farm_cells = [ci for ci in fire if cells[ci][6] >= FARM_SHARE * _cell_km2(cells[ci][0])]
        farm = {"cropland_km2": round(sum(crop(ci) for ci in fire)), "farm_cells": len(farm_cells),
                "farm_rule": f"cropland covers at least {FARM_SHARE:.0%} of the 11 km cell", "source": ex.get("farmland")}
    detail = {}
    if not period:  # the whole-record view also carries what the Cases & exposure page draws
        by_year = {}
        for k, rows in grid["months"].items():
            for ci, _ in rows:
                by_year.setdefault(int(k[:4]), set()).add(ci)
        detail = {
            "by_year": [{"year": y, "fire_cells": len(cs), "population": sum(cells[ci][2] for ci in cs),
                         "hospitals": sum(cells[ci][3] for ci in cs),
                         "schools": sum(school(ci) for ci in cs) if has_schools else None,
                         "cropland_km2": round(sum(crop(ci) for ci in cs)) if has_crop else None} for y, cs in sorted(by_year.items())],
            "map_cells": [[c[0], c[1], c[2], on[i]] for i, c in enumerate(cells)],   # lat, lon, people, months with fire
            "top_cells": sorted(({"lat": cells[ci][0], "lon": cells[ci][1], "population": cells[ci][2], "hospitals": cells[ci][3],
                                  "clinics": cells[ci][4], "schools": school(ci) if has_schools else None,
                                  "cropland_km2": crop(ci) if has_crop else None,
                                  "months_with_fire": on[ci]} for ci in fire),
                                key=lambda r: (-r["population"], -r["months_with_fire"]))[:15],
            "months_in_record": len(grid["months"]),
        }
        if farm:
            yrs = prof["years_of_month"]
            farm["by_month"] = [{"month": m + 1, "record_years": yrs[m],
                                 "hotspots_per_year": round(sum(prof["cal_hot"][ci][m] for ci in farm_cells) / yrs[m], 1) if yrs[m] else None,
                                 "farm_cells_with_fire_per_year": round(sum(prof["cal_years"][ci][m] for ci in farm_cells) / yrs[m], 1) if yrs[m] else None}
                                for m in range(12)]
            farm["top_cells"] = sorted(({"lat": cells[ci][0], "lon": cells[ci][1], "cropland_km2": cells[ci][6],
                                         "months_with_fire": on[ci], "last_fire": last[ci],
                                         "peak_month": max(range(12), key=lambda m: prof["cal_years"][ci][m]) + 1} for ci in farm_cells),
                                       key=lambda r: (-r["months_with_fire"], -r["cropland_km2"]))[:15]
    return {"region_id": region_id, "period": period, "fire_cells": len(fire), "population": sum(cells[ci][2] for ci in fire), **detail,
            "population_source": ex["population"],
            "hospitals": None if "hospitals" in err else sum(cells[ci][3] for ci in fire),
            "clinics": None if "hospitals" in err else sum(cells[ci][4] for ci in fire),
            "schools": sum(school(ci) for ci in fire) if has_schools else None,
            "hospital_list": [] if "hospitals" in err else hosp[:50],
            "school_list": schools[:100], "schools_named": len(schools) if has_named else None,
            "farmland": farm,
            "major_roads": None if "roads" in err else len(roads), "road_list": [] if "roads" in err else roads[:50],
            "errors": err, "truncated": ex["infrastructure"].get("truncated"), "scope": ex["infrastructure"].get("scope"),
            "built_at": ex["built_at"], "caveat": ex["caveat"], "cells_without_exposure": grid.get("cells_without_exposure", 0)}


def exposure_place(region_id, lat, lon):
    """One place (a school, a hospital, a farm): the 11 km cell that holds it, how often and in which months fire is
    seen there and in the eight cells around it, and who and what lies in it. Context, not impact."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("lat and lon must be numbers")
    try:
        ex = _read(region_id, "exposure")
    except NotFound:
        raise NotFound(f"no exposure layer built for '{region_id}'")
    w, s, e, n = ex["bbox"]
    if not (s <= lat <= n and w <= lon <= e):
        raise ValueError(f"the point is outside this area ({s} to {n} latitude, {w} to {e} longitude)")
    grid = _aligned_grid(region_id)
    prof = _profile(region_id)
    cols = ex.get("cell_columns") or []
    err = ex["infrastructure"].get("errors") or {}
    index = {tuple(c): i for i, c in enumerate(grid["cells"])}
    key = lambda la, lo: (round(math.floor(la * 10 + 1e-9) / 10, 2), round(math.floor(lo * 10 + 1e-9) / 10, 2))
    cell = key(lat, lon)
    ci = index.get(cell)
    around = [index[k] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
              if (dy or dx) and (k := key(cell[0] + dy * 0.1 + 0.05, cell[1] + dx * 0.1 + 0.05)) in index]
    out = {"region_id": region_id, "lat": lat, "lon": lon, "cell": list(cell), "in_record": ci is not None,
           "cell_km2": round(_cell_km2(cell[0])), "months_in_record": len(grid["months"]),
           "neighbours_with_fire": len(around),
           "neighbours_last_fire": max((prof["last"][j] for j in around if prof["last"][j]), default=None),
           "caveat": ex["caveat"], "farmland_source": ex.get("farmland"), "population_source": ex["population"]}
    if ci is None:
        if grid["cells"]:
            out["nearest_fire_cell_km"] = round(min(_gc_km(lat, lon, c[0] + 0.05, c[1] + 0.05) for c in grid["cells"]), 1)
        out["note"] = "No fire has been detected in this 11 km cell since 2000, so it holds no exposure data."
        return out
    c, yrs = ex["cells"][ci], prof["years_of_month"]
    recent = [{"period": k, "hotspots": v} for k in sorted(grid["months"], reverse=True) for j, v in grid["months"][k] if j == ci][:8]
    out.update({
        "months_with_fire": prof["on"][ci], "last_fire": prof["last"][ci], "recent": recent, "unit": grid.get("unit"),
        "by_month": [{"month": m + 1, "years_with_fire": prof["cal_years"][ci][m], "record_years": yrs[m],
                      "hotspots_per_year": round(prof["cal_hot"][ci][m] / yrs[m], 2) if yrs[m] else None} for m in range(12)],
        "population": c[2],
        "hospitals": None if "hospitals" in err else c[3], "clinics": None if "hospitals" in err else c[4],
        "schools": c[5] if "schools" in cols and "schools" not in err else None,
        "cropland_km2": c[6] if "cropland_km2" in cols and "cropland" not in err else None,
        "hospital_list": [{"name": h[0], "lat": h[1], "lon": h[2]} for h in ex["hospitals"] if h[3] == ci][:30],
        "school_list": [{"name": r[0], "lat": r[1], "lon": r[2], "kind": r[4]} for r in ex.get("schools", []) if r[3] == ci][:50],
    })
    return out


def _check_point(region_id, lat, lon):
    lat, lon = float(lat), float(lon)
    m = _read(region_id, "meta")
    w, s, e, n = m["bbox"]
    if not (s <= lat <= n and w <= lon <= e):
        raise ValueError(f"the point is outside this area ({s} to {n} latitude, {w} to {e} longitude)")
    return lat, lon, m


def place_nearby(region_id, lat, lon, radius_km=10.0, days=2):
    """Vegetation-fire detections within radius_km of a point in the last `days` days, from the area's live FIRMS
    cache (confidence-filtered; kilns and other static sources excluded). Pixel centres, not fire locations."""
    lat, lon, m = _check_point(region_id, lat, lon)
    radius_km, days = float(radius_km), int(days)
    if not (1 <= radius_km <= 50) or not (1 <= days <= 10):
        raise ValueError("radius_km must be 1-50 and days 1-10")
    b = dt.datetime.now(dt.timezone.utc).date()
    a = b - dt.timedelta(days=days)
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    _detections(con, region_id, m["bbox"], a, b)
    dist = (f"2 * 6371 * asin(sqrt(pow(sin(radians(lat - {lat}) / 2), 2) + cos(radians({lat})) * cos(radians(lat)) "
            f"* pow(sin(radians(lon - {lon}) / 2), 2)))")
    rows = con.execute(f"""SELECT strftime(acq_datetime, '%Y-%m-%d %H:%M'), satellite, lat, lon, round(frp, 1), round({dist}, 1) AS km
                           FROM e WHERE conf_ok AND cls = 'veg' AND {dist} <= {radius_km}
                           ORDER BY acq_datetime DESC""").fetchall()
    con.close()
    dets = [dict(zip(("time_utc", "satellite", "lat", "lon", "frp_mw", "km"), r)) for r in rows]
    return {"region_id": region_id, "lat": lat, "lon": lon, "radius_km": radius_km, "start": str(a), "end": str(b),
            "count": len(dets), "nearest_km": min((d["km"] for d in dets), default=None),
            "latest_utc": dets[0]["time_utc"] if dets else None, "detections": sorted(dets, key=lambda d: d["km"])[:10],
            "data_through": m.get("data_through"),
            "note": "Satellite detections of heat (VIIRS 375 m, MODIS 1 km pixel centres), confidence-filtered, static "
                    "sources such as kilns removed. A detection is not a confirmed fire and not its edge; check locally."}


def place_season(region_id, lat, lon, month=None):
    """How often fire was detected within about 15 km of a point (its 11 km cell and the eight around it) in one
    calendar month, over every year of the record. A climatology, never a forecast."""
    lat, lon, _ = _check_point(region_id, lat, lon)
    month = int(month or dt.date.today().month)
    if not 1 <= month <= 12:
        raise ValueError("month must be 1-12")
    grid = _read(region_id, "grid")
    index = {tuple(c): i for i, c in enumerate(grid["cells"])}
    gy, gx = math.floor(lat * 10 + 1e-9), math.floor(lon * 10 + 1e-9)
    block = {index[k] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
             if (k := (round((gy + dy) / 10, 2), round((gx + dx) / 10, 2))) in index}
    years, hit = 0, []
    for k, rows in sorted(grid["months"].items()):
        if int(k[5:]) != month:
            continue
        years += 1
        if block and any(ci in block for ci, _ in rows):
            hit.append(k[:4])
    return {"region_id": region_id, "lat": lat, "lon": lon, "month": month, "record_years": years,
            "years_with_fire": len(hit), "share": round(len(hit) / years, 2) if years else None, "years": hit[-10:],
            "note": "Years in which fire was detected within about 15 km of the place in this calendar month. "
                    "History, not a forecast."}


def kilns(region_id):
    """Kiln evidence for an area that has it (the Dhaka brick-kiln belt): a published kiln inventory, how many mapped
    kilns FIRMS sees, and Black Marble night lights in kiln season against the monsoon. FIRMS is not used to find kilns."""
    try:
        return {"region_id": region_id, **_read(region_id, "kilns")}
    except NotFound:
        raise NotFound(f"no kiln evidence built for '{region_id}' (only the Dhaka brick-kiln belt has an inventory)")


def casebook_overview():
    """One honest row per built area: what the casebook and the exposure layer hold, and what failed."""
    out = []
    for r in list_regions():
        row = {"id": r["id"], "name": r["name"], "country": r.get("country"), "cases": None, "exposure": None}
        try:
            c = _read(r["id"], "cases")
            row["cases"] = {"total": len(c["cases"]), "counts": c["counts"], "found": c.get("found"),
                            "failed_sources": [s["name"] for s in c["sources"] if s.get("error")]}
        except NotFound:
            pass
        try:
            ex = _read(r["id"], "exposure")
            row["exposure"] = {**ex["totals"], "errors": ex["infrastructure"].get("errors") or {},
                               "truncated": ex["infrastructure"].get("truncated"), "built_at": ex["built_at"]}
        except NotFound:
            pass
        out.append(row)
    return {"areas": out, "caveat": cases.CAVEAT}


# ---------- any place on Earth: is fire near my school, hospital or home? ----------

PLACE_KINDS = {"school": "school", "kindergarten": "school", "college": "school", "university": "school",
               "hospital": "hospital", "clinic": "clinic", "doctors": "clinic", "nursing_home": "care_home",
               "fire_station": "fire_station"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
FACILITY_CAP = 3000     # elements per Overpass reply; a dense city can hold more (then 'truncated': try a smaller distance)
RECENT_DAYS = 7
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]
_LATLON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)\s*$")


def _facilities(lat, lon, radius_km):
    """Schools, hospitals, clinics, care homes and fire stations within radius_km (OpenStreetMap, cached a week).
    Asks Overpass for the bounding box (index-fast; 'around' on ways is several times slower) and cuts the circle here."""
    r = int(radius_km * 1000)
    d_lat = radius_km / 111.32
    d_lon = d_lat / max(0.05, math.cos(math.radians(lat)))
    box = f"{lat - d_lat:.4f},{lon - d_lon:.4f},{lat + d_lat:.4f},{lon + d_lon:.4f}"
    q = (f'[out:json][timeout:40][bbox:{box}];(nwr["amenity"~"^({"|".join(PLACE_KINDS)})$"];'
         f'nwr["healthcare"~"^(hospital|clinic)$"];nwr["social_facility"="nursing_home"];);out center tags {FACILITY_CAP};')

    def fetch():
        errs = []
        for url in OVERPASS:
            try:
                d = json.loads(news._get(url, timeout=50, data=urllib.parse.urlencode({"data": q}).encode()))
            except Exception as ex:  # noqa: BLE001 - try the next mirror, then report; never a silent empty list
                errs.append(f"{url.split('/')[2]}: {str(ex)[:100]}")
                continue
            if d.get("remark") and "error" in d["remark"].lower():
                errs.append(f"{url.split('/')[2]}: {d['remark'][:100]}")
                continue
            return d.get("elements", [])
        raise RuntimeError("OpenStreetMap (Overpass) did not answer: " + "; ".join(errs))
    els = news._cached(f"fac2:{lat:.3f},{lon:.3f},{r}", 7 * 86400, fetch)
    out = []
    for el in els:
        t = el.get("tags", {})
        la, lo = (el.get("lat"), el.get("lon")) if el["type"] == "node" else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        kind = (PLACE_KINDS.get(t.get("amenity")) or PLACE_KINDS.get(t.get("healthcare"))
                or ("care_home" if t.get("social_facility") == "nursing_home" else None))
        if la is None or not kind:
            continue
        km = _gc_km(lat, lon, la, lo)
        if km <= radius_km:
            out.append({"name": t.get("name:en") or t.get("name"), "kind": kind, "lat": round(la, 5), "lon": round(lo, 5),
                        "km": round(km, 2)})
    return out, len(els) >= FACILITY_CAP


def _firms_through():
    """Newest acquisition date in the mirror's current-year file (read from the Parquet footer, cached an hour)."""
    f = f"{FIRMS_BASE}/year={dt.datetime.now(dt.timezone.utc).year}/detections.parquet"

    def fetch():
        con = connect()
        con.execute("SET enable_progress_bar = false")
        try:
            return con.execute(f"SELECT max(stats_max) FROM parquet_metadata('{f}') WHERE path_in_schema = 'acq_date'").fetchone()[0]
        finally:
            con.close()
    return news._cached(f"firms-through:{int(time.time() // 3600)}", 3600, fetch)


def _recent_fires(lat, lon, radius_km, days=RECENT_DAYS):
    """Vegetation-fire detections of every satellite within radius_km in the last `days` days, straight from the
    public FIRMS mirror (confidence-filtered; FIRMS static types removed where typed; recent rows are untyped)."""
    def fetch():
        b = dt.date.today()
        a = b - dt.timedelta(days=days)
        d_lat = radius_km / 111.32
        d_lon = d_lat / max(0.05, math.cos(math.radians(lat)))
        files = [f"{FIRMS_BASE}/year={y}/detections.parquet" for y in sorted({a.year, b.year})]
        con = connect()
        con.execute("SET enable_progress_bar = false")
        try:
            # Narrow inner read, filters after: with the confidence ORs in the same WHERE, DuckDB stops pruning row
            # groups by the box and scans the whole year (minutes instead of seconds).
            rows = con.execute(f"""WITH t AS MATERIALIZED (
                                       SELECT acq_datetime, satellite, sensor, confidence, confidence_pct, type, frp, geometry
                                       FROM read_parquet({files}) WHERE acq_date >= DATE '{a}' AND ST_Intersects(geometry,
                                       ST_MakeEnvelope({lon - d_lon}, {lat - d_lat}, {lon + d_lon}, {lat + d_lat})))
                                   SELECT strftime(acq_datetime, '%Y-%m-%d %H:%M'), satellite, round(ST_Y(geometry), 4),
                                          round(ST_X(geometry), 4), round(frp, 1)
                                   FROM t WHERE {CONF_SQL} AND (type IS NULL OR type = 0)""").fetchall()
        finally:
            con.close()
        dets = [{"time_utc": t, "satellite": s, "lat": la, "lon": lo, "frp_mw": f, "km": round(_gc_km(lat, lon, la, lo), 2)}
                for t, s, la, lo, f in rows]
        return {"start": str(a), "end": str(b),
                "detections": sorted((d for d in dets if d["km"] <= radius_km), key=lambda d: d["km"])}
    return news._cached(f"recent:{lat:.2f},{lon:.2f},{radius_km}:{int(time.time() // 3600)}", 3600, fetch)


@functools.lru_cache(maxsize=2)
def _season_years(path, _mtime):
    con = duckdb.connect()
    kv = dict(con.execute(f"SELECT key::VARCHAR, value::VARCHAR FROM parquet_kv_metadata('{path}')").fetchall())
    con.close()
    return int(kv["first_year"]), int(kv["last_year"])


def _season(lat, lon, half):
    """Years with MODIS fire in each calendar month in the (2*half+1)^2 block of 0.1 degree cells around a point."""
    from .globe import SEASON
    if not SEASON.exists():
        raise NotFound("the worldwide fire-season table is not on this server (python -m kw.globe season)")
    path = SEASON.as_posix()
    first, last = _season_years(path, SEASON.stat().st_mtime)
    gy, gx = math.floor(lat * 10 + 1e-9), math.floor(lon * 10 + 1e-9)   # ponytail: no wrap at the antimeridian
    con = duckdb.connect()
    rows = con.execute(f"""SELECT * EXCLUDE (gy, gx) FROM read_parquet('{path}')
                           WHERE gy BETWEEN {gy - half} AND {gy + half} AND gx BETWEEN {gx - half} AND {gx + half}""").fetchall()
    con.close()
    n = last - first + 1
    months = []
    for m in range(12):
        mask = 0
        for r in rows:
            mask |= r[m] or 0
        yrs = [first + b for b in range(n) if mask >> b & 1]
        months.append({"month": m + 1, "years_with_fire": len(yrs), "record_years": n, "share": round(len(yrs) / n, 2),
                       "last_year": yrs[-1] if yrs else None})
    return {"first_year": first, "last_year": last, "within_km": round((half + 0.5) * 11), "by_month": months,
            "sensor": "MODIS (Terra and Aqua), confidence-filtered, static types removed"}


def _place_text(name, level, radius_km, dets, season, ocls, rec_ok):
    """Headline and reasons in plain words (one source for the web page, the API and MCP)."""
    today = dt.date.today()
    reasons = []
    if not rec_ok:
        reasons.append("The live satellite check could not be read just now, so fire in the last 7 days is unknown. "
                       "Try again in a few minutes.")
    elif dets:
        reasons.append(f"Satellites saw {len(dets)} fire {'detection' if len(dets) == 1 else 'detections'} within "
                       f"{radius_km:g} km in the last {RECENT_DAYS} days; the closest was {dets[0]['km']:.1f} km away "
                       f"on {dets[0]['time_utc'][:10]}.")
    else:
        reasons.append(f"No fire was seen by satellites within {radius_km:g} km in the last {RECENT_DAYS} days.")
    if season:
        bm = season["by_month"]
        m0, m1 = bm[today.month - 1], bm[today.month % 12]
        busy = [m for m in sorted(bm, key=lambda m: -m["years_with_fire"])[:3] if m["years_with_fire"] > 0]
        reasons.append(f"In {MONTH_NAMES[m0['month'] - 1]}, fire was seen within about {season['within_km']} km in "
                       f"{m0['years_with_fire']} of {m0['record_years']} years; in {MONTH_NAMES[m1['month'] - 1]}, "
                       f"{m1['years_with_fire']} of {m1['record_years']}."
                       + (f" The usual fire months here are {', '.join(MONTH_NAMES[m['month'] - 1] for m in busy)}."
                          if busy else " Fire is rare here."))
    if ocls in ("watch", "above"):
        reasons.append("The last 30 days had more fire than usual in this part of the world.")
    elif ocls == "season":
        reasons.append("The next 30 days are usually a fire season in this part of the world.")
    headline = {
        "near": f"Fire was seen close to {name} this week.",
        "watch": f"Stay alert: fire was seen around {name} this week." if dets
        else f"Stay alert: fire often happens near {name} at this time of year.",
        "season": f"Fire sometimes happens near {name} at this time of year.",
        "low": f"No fire seen near {name} this week, and this is not usually a fire month here.",
        "unknown": f"We could not check the last 7 days for {name} just now.",
    }[level]
    return headline, reasons


def place_risk(query=None, lat=None, lon=None, radius_km=10.0, facilities=True, label=None):
    """Fire near any place on Earth, in plain words: what satellites saw within radius_km in the last 7 days, how
    often fire happens there at this time of year (2003-2025), its 30-day outlook, and the schools, hospitals,
    clinics, care homes and fire stations around it, each with its distance to the nearest fire seen this week.
    Every source that could not be read says why (never shown as 'no fire'). Not a forecast, not an official warning.
    facilities=False leaves the buildings out ('facilities' is then None and not in 'errors'): a fast first answer."""
    from . import news_more, outlook
    radius_km = float(radius_km)
    if not 1 <= radius_km <= 25:
        raise ValueError("radius_km must be 1-25")
    place, candidates = None, []
    if lat is None or lon is None:
        q = (query or "").strip()[:120]
        if not q:
            raise ValueError("give a place name, or lat and lon")
        if (m := _LATLON.match(q)):
            lat, lon = float(m[1]), float(m[2])
        else:
            g = news_more.geocode(q)
            if not g:
                raise NotFound(f"no place called '{q}' was found; try a nearby town, or add the country")
            lat, lon = g["lat"], g["lon"]
            place = {k: g.get(k) for k in ("name", "display_name", "country")}
            candidates = [{k: c.get(k) for k in ("name", "display_name", "country", "lat", "lon")} for c in g.get("candidates", [])[1:6]]
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat must be -90 to 90 and lon -180 to 180")
    place = place or {"name": (label or "").strip()[:80] or "this place", "display_name": f"{lat:.4f}, {lon:.4f}", "country": None}

    errors, got = {}, {}
    with ThreadPoolExecutor(3) as pool:
        jobs = {"recent": pool.submit(_recent_fires, lat, lon, radius_km), "through": pool.submit(_firms_through)}
        if facilities:   # the slow one (Overpass, 20-45 s uncached): the web page asks for it second
            jobs["facilities"] = pool.submit(_facilities, lat, lon, radius_km)
        for k, f in jobs.items():
            try:
                got[k] = f.result()
            except Exception as ex:  # noqa: BLE001 - a witness that could not look says so
                errors[k] = str(ex)[:200]
    try:
        season = _season(lat, lon, max(1, round(radius_km / 11)))
    except Exception as ex:  # noqa: BLE001
        season, errors["season"] = None, str(ex)[:200]
    try:
        ol = outlook.at(lat, lon)
    except Exception as ex:  # noqa: BLE001
        ol, errors["outlook"] = None, str(ex)[:200]

    rec = got.get("recent")
    dets = rec["detections"] if rec else []
    near_km = dets[0]["km"] if dets else None
    today = dt.date.today()
    share = max(season["by_month"][today.month - 1]["share"], season["by_month"][today.month % 12]["share"]) if season else None
    ocls = ((ol or {}).get("outlook") or {})
    level = sc.place_level(near_km, share, ocls.get("class"), recent_ok=rec is not None)

    facs, trunc = got.get("facilities", (None, False))
    counts = counts_near = None
    if facs is not None:
        for f in facs:
            f["fire_km"] = round(min(_gc_km(f["lat"], f["lon"], d["lat"], d["lon"]) for d in dets), 2) if dets else None
            f["level"] = sc.place_level(f["fire_km"], share, ocls.get("class"), recent_ok=rec is not None)
        order = {"near": 0, "watch": 1, "season": 2, "unknown": 3, "low": 4}
        facs.sort(key=lambda f: (order[f["level"]], f["fire_km"] if f["fire_km"] is not None else 1e9, f["km"]))
        kinds = ("school", "hospital", "clinic", "care_home", "fire_station")
        counts = {k: sum(f["kind"] == k for f in facs) for k in kinds}
        counts_near = {k: sum(f["kind"] == k and f["level"] == "near" for f in facs) for k in kinds}

    headline, reasons = _place_text(place["name"].split(",")[0], level, radius_km, dets, season, ocls.get("class"), rec is not None)
    built = next(({"id": r["id"], "name": r["name"]} for r in list_regions()
                  if r["bbox"][1] <= lat <= r["bbox"][3] and r["bbox"][0] <= lon <= r["bbox"][2]), None)
    return {
        "place": {**place, "lat": round(lat, 5), "lon": round(lon, 5)}, "candidates": candidates, "radius_km": radius_km,
        "level": level, "headline": headline, "reasons": reasons,
        "recent": None if rec is None else {
            "days": RECENT_DAYS, "start": rec["start"], "end": rec["end"], "count": len(dets), "nearest_km": near_km,
            "latest_utc": max((d["time_utc"] for d in dets), default=None), "detections": dets[:300],
            "data_through": got.get("through")},
        "season": season, "season_share_now": share,
        "outlook": ocls or None, "outlook_note": (ol or {}).get("note"),
        "facilities": None if facs is None else {
            "counts": counts, "counts_near_fire": counts_near, "truncated": trunc, "list": facs[:300],
            "source": "OpenStreetMap via Overpass API (amenity school, kindergarten, college, university, hospital, "
                      "clinic, doctors, nursing_home, fire_station; healthcare hospital, clinic)"},
        "built_area": built, "errors": errors, "rule": sc.PLACE_RULE,
        "caveat": ("Satellites see heat from space a few hours after it happens and miss small, short or cloud-covered "
                   "fires. A detection is not a confirmed fire and not its edge; factories, gas flares and kilns can also "
                   "show as heat. Schools and hospitals come from OpenStreetMap, which maps some places better than "
                   "others. History and detections, not a forecast and not an official warning: in an emergency, call "
                   "your local fire service."),
    }
