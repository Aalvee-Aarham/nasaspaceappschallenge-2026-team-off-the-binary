"""User alerts for any place on Earth, delivered by email (built in) or by the user's own n8n.

Triggers (each alert picks any of them):
  anomaly  the month so far tops N x the median of the same days in earlier years (at most once per month)
  outlook  the place's 30-day outlook has watch cells: fire season ahead AND already above normal (at most weekly)
  events   NASA EONET lists a new open wildfire event inside the box
  nearby   (place alerts) a vegetation-fire detection within radius_km of the place in the last 2 days (each once)
  season   (place alerts) the coming week falls in a month when fire was detected within ~15 km of the place in at
           least SEASON_SHARE of past years (once per calendar month): history, never a forecast

No accounts: the unguessable token is the credential. Email is double opt-in (a confirm link is mailed first) and
every message carries a one-click unsubscribe link. SMTP comes from env (SMTP_HOST, SMTP_PORT, SMTP_USER,
SMTP_PASSWORD, SMTP_FROM); without it, alerts still work through n8n or the poll endpoint.
"""
import calendar
import datetime as dt
import html
import json
import logging
import math
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
import urllib.error
import urllib.request
from email.message import EmailMessage

from . import tools
from .firms import DATA

FILE = DATA / "alerts.json"
MAX_ALERTS = 2000
MAX_PER_EMAIL = 20
TRIGGERS = ("anomaly", "outlook", "events", "nearby", "season")
PLACE_TRIGGERS = ("nearby", "season")
SEASON_SHARE = 0.5   # "usually": fire detected near the place in at least half of the past years for that month
EMAIL_RE = re.compile(r"^[^@\s<>\"']{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,}$")
_lock = threading.Lock()  # ponytail: one file + one lock; move to SQLite if alerts or writers grow

log = logging.getLogger("kw.alerts")
if not log.handlers:  # uvicorn only configures its own loggers; without this our INFO lines would vanish
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s kw.alerts: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


# KW_STATE_URL: an Azure Blob container SAS URL. The hosted server sleeps when idle and its disk is wiped, so the
# alert list lives in one blob there (read once per process, written through on every change). Unset: a local file.
STATE_URL = os.environ.get("KW_STATE_URL", "").strip()
_mem = None


def _blob(method, body=None):
    base, _, sas = STATE_URL.partition("?")
    req = urllib.request.Request(f"{base.rstrip('/')}/alerts.json?{sas}", data=body, method=method,
                                 headers={"x-ms-blob-type": "BlockBlob", "Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except urllib.error.HTTPError as ex:
        if ex.code == 404 and method == "GET":
            raise            # no list yet: _load starts an empty one
        raise tools.Unavailable(f"the alert store answered HTTP {ex.code}; please try again in a minute") from ex
    except OSError as ex:
        raise tools.Unavailable(f"the alert store could not be reached ({ex}); please try again in a minute") from ex


def _load():
    global _mem
    if not STATE_URL:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    if _mem is None:
        try:
            _mem = json.loads(_blob("GET"))
        except urllib.error.HTTPError as ex:
            if ex.code != 404:   # any other failure must not start an empty list that would overwrite the stored one
                raise
            _mem = {}
    return json.loads(json.dumps(_mem))   # a copy: callers change it and save


def _save(d):
    global _mem
    if STATE_URL:   # raises if the store cannot be written: the caller's request fails visibly, nothing is lost silently
        _blob("PUT", json.dumps(d, ensure_ascii=False).encode("utf-8"))
        _mem = json.loads(json.dumps(d))
        return
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, FILE)


def _update(token, **kv):
    with _lock:
        d = _load()
        if token in d:
            d[token].update(kv)
            _save(d)


def tops(value, median, ratio, floor):
    """True when the month so far exceeds ratio x the median of the same days in earlier years, and is not tiny."""
    return value >= floor and value > ratio * median


def _label(period):
    return dt.date(int(period[:4]), int(period[5:7]), 1).strftime("%B %Y")


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def mask(email):
    if not email:
        return None
    user, _, dom = email.partition("@")
    return f"{user[:1]}{'*' * max(1, len(user) - 1)}@{dom}"


# ---------- email ----------

def smtp_ready():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))


def send_email(to, subject, text, html_body=None):
    if not smtp_ready():
        raise RuntimeError("email delivery is not configured on this server (set SMTP_HOST and SMTP_FROM)")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.environ["SMTP_FROM"], to, subject
    msg.set_content(text)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            if user:
                s.login(user, pw or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            if os.environ.get("SMTP_TLS", "1") != "0":  # SMTP_TLS=0 only for a local relay (MailHog, postfix on localhost)
                s.starttls(context=ctx)
            if user:
                s.login(user, pw or "")
            s.send_message(msg)


FREE_SERVER = ("Please note: Kiln Watch runs on a free student server that goes to sleep when nobody is using the "
               "website. A scheduled job wakes it every 3 hours to check your alert, so an email can come a few hours "
               "after satellites see fire, or be missed if a check fails. Do not rely on it for safety: for fire you can see or smell, call your "
               "local emergency number, and for dependable satellite fire alerts use NASA FIRMS (firms.modaps.eosdis.nasa.gov).")


def _page_url(sub):
    return f"{sub.get('base_url', '').rstrip('/')}/#pg=explore&r={sub['region_id']}"


def _html(title, paras, sub, token, footer_link=True):
    esc = [f"<p style='margin:0 0 12px;line-height:1.5'>{p}</p>" for p in paras]
    base = sub.get("base_url", "").rstrip("/")
    api = (os.environ.get("KW_API_URL") or base).rstrip("/")   # the server that holds the alerts, not a read-only copy
    unsub = f"{api}/api/alerts/{token}/unsubscribe?code={sub.get('code', '')}"
    foot = (f"<p style='color:#8892a0;font-size:12px'>A climatological outlook from NASA FIRMS satellite detections "
            f"(MODIS, VIIRS), harmonized by Kiln Watch. Not a forecast and not an official alert. {FREE_SERVER} "
            f"<a href='{unsub}' style='color:#8892a0'>Unsubscribe</a></p>") if footer_link else ""
    return (f"<div style='font-family:Inter,Arial,sans-serif;background:#05080d;color:#f1f4f8;padding:24px'>"
            f"<div style='max-width:560px;margin:auto'><p style='color:#ff7a6e;font-size:11px;letter-spacing:.12em;"
            f"text-transform:uppercase;margin:0 0 8px'>Kiln Watch</p><h1 style='font-size:20px;margin:0 0 14px'>"
            f"{html.escape(title)}</h1>{''.join(esc)}<p><a href='{_page_url(sub)}' style='background:#00a1ff;color:#00121f;"
            f"padding:9px 14px;text-decoration:none;font-weight:700;font-size:12px;text-transform:uppercase'>Open the "
            f"record</a></p>{foot}</div></div>")


# ---------- welcome emails: the fire picture right after a sign-up ----------

WELCOME = True   # tests switch it off; serverless hosts never start it (no background threads there)
_MONTH = calendar.month_name


def _tile(label, value, note=""):
    return (f"<td style='width:33%;vertical-align:top;padding:12px;background:#0d1420;border:1px solid #1d2a3a'>"
            f"<div style='color:#8892a0;font-size:11px;letter-spacing:.08em;text-transform:uppercase'>{html.escape(label)}</div>"
            f"<div style='font-size:22px;font-weight:700;color:#ffb070;margin:6px 0 4px'>{html.escape(str(value))}</div>"
            f"<div style='color:#c5ccd6;font-size:12px;line-height:1.4'>{html.escape(note)}</div></td>")


def _tiles(cells):
    rows = [cells[i:i + 3] for i in range(0, len(cells), 3)]
    return "".join(f"<table role='presentation' width='100%' cellspacing='6' style='border-collapse:separate'><tr>"
                   f"{''.join(_tile(*c) for c in r)}</tr></table>" for r in rows)


def _try(fn, what):
    """(value, None) or (None, why): a source that could not be read is said so, never shown as zero."""
    try:
        return fn(), None
    except Exception as ex:  # noqa: BLE001
        return None, f"{what} could not be read just now ({str(ex)[:90]})"


def _fmt(n):
    return f"{n:,.0f}"


def _local_picture(sub):
    """(title, paragraphs, plain text) for the place or area of a new alert, from data that answers in seconds to minutes."""
    p, rid, cells, paras, gaps = sub.get("place"), sub["region_id"], [], [], []
    if p:
        pr, why = _try(lambda: tools.place_risk(lat=p["lat"], lon=p["lon"], radius_km=min(25, p["radius_km"]),
                                                facilities=True, label=p["label"]), "The satellite check")
        if pr:
            r, se, fac = pr.get("recent"), pr.get("season"), pr.get("facilities")
            paras.append(f"<b>{html.escape(pr['headline'])}</b>")
            if r:
                cells.append(("Fire this week", f"{_fmt(r['count'])} spots" if r["count"] else "None seen",
                              f"closest {r['nearest_km']:.1f} km away" if r["count"] else f"within {pr['radius_km']:g} km, last {r['days']} days"))
            if se:
                top = sorted(se["by_month"], key=lambda m: -m["years_with_fire"])[:3]
                cells.append(("Usual fire months", ", ".join(_MONTH[m["month"]][:3] for m in top if m["years_with_fire"]) or "Rare here",
                              f"years with fire within {se['within_km']:g} km, {se['first_year']}-{se['last_year']}"))
            if pr.get("outlook"):
                cells.append(("Next 30 days", {"watch": "Watch", "above": "Above normal", "season": "Fire season"}.get(pr["outlook"]["class"], "Usually quiet"),
                              "what this time of year usually brings"))
            if fac:
                c, near = fac["counts"], fac["counts_near_fire"]
                cells.append(("Schools nearby", _fmt(c.get("school", 0)), f"{_fmt(near.get('school', 0))} within 5 km of a fire"))
                cells.append(("Hospitals, clinics", _fmt(c.get("hospital", 0) + c.get("clinic", 0)),
                              f"{_fmt(near.get('hospital', 0) + near.get('clinic', 0))} within 5 km of a fire"))
                closest = [x for x in fac["list"] if x.get("fire_km") is not None][:3]
                if closest:
                    paras.append("Closest to this week's fire: " + "; ".join(
                        f"{html.escape(x['name'] or x['kind'])} ({x['fire_km']:.1f} km from fire)" for x in closest) + ".")
            gaps += [f"{k}: {v}" for k, v in (pr.get("errors") or {}).items()]
        else:
            gaps.append(why)
    w, why = _try(lambda: tools.early_warning(rid), "The area's early-warning level")
    if w:
        cells.append(("Fire outlook", w["level"].title(), w["headline"][:110]))
    elif not p:
        gaps.append(why if "not found" not in (why or "").lower() else "The area's record is still being built (5 to 10 minutes)")
    if not p:
        b = dt.date.today()
        hs, why = _try(lambda: tools.global_hotspots(sub["bbox"], b - dt.timedelta(days=7), b), "This week's detections")
        if hs:
            n20 = hs["totals_by_satellite"].get("VIIRS_NOAA20", {}).get("vegetation")
            cells.append(("Fire this week", _fmt(n20) if n20 is not None else "–", "NOAA-20 VIIRS detections in the area, last 7 days"))
        else:
            gaps.append(why)
        ex, why = _try(lambda: tools.exposure(rid), "Who lives where fire is seen")
        if ex:
            cells.append(("People in fire cells", f"{ex['population'] / 1e6:.1f} M" if ex["population"] >= 1e6 else _fmt(ex["population"]),
                          f"in {_fmt(ex['fire_cells'])} cells of 11 km with fire since 2000"))
            cells.append(("Hospitals, clinics", _fmt((ex.get("hospitals") or 0) + (ex.get("clinics") or 0)), "inside those fire cells"))
        else:
            gaps.append(why)
    elif tools.is_built(rid):
        ep, _ = _try(lambda: tools.exposure_place(rid, p["lat"], p["lon"]), "")
        if ep and ep.get("in_record"):
            cells.append(("People in its 11 km cell", _fmt(ep.get("population") or 0),
                          f"fire seen in {ep.get('months_with_fire', 0)} of {ep.get('months_in_record', 0)} months since 2000"))
    name = (p or {}).get("label") or sub.get("name") or rid
    if gaps:
        paras.append("<span style='color:#8892a0'>Could not look: " + html.escape("; ".join(g for g in gaps if g)) + ". That is not the same as no fire.</span>")
    text = "\n".join([f"Fire around {name} right now"] + [f"- {a}: {b} ({c})" for a, b, c in cells] + gaps)
    return f"Fire around {name} right now", [_tiles(cells)] + paras, text


def _country_of(sub):
    if tools.is_built(sub["region_id"]):
        c = tools._read(sub["region_id"], "meta").get("country")
        if c:
            return c
    p = sub.get("place") or {}
    w, s, e, n = sub["bbox"]
    return tools.news.reverse_geocode(p.get("lat", (s + n) / 2), p.get("lon", (w + e) / 2)).get("country")


def _named_in(cells, country, limit=5):
    """(cell, place name) for cells that fall inside the country (the box spills into neighbours), one per name."""
    out, seen = [], set()
    for c in cells:
        g = tools.news.reverse_geocode(c["lat"], c["lon"])
        if (g.get("country") or "").lower() != country.lower() or not g.get("name") or g["name"] in seen:
            continue
        seen.add(g["name"])
        out.append((c, g["name"]))
        if len(out) >= limit:
            break
    return out


def _country_picture(country):
    """(title, paragraphs, text) for the whole country: this week's detections read live, the outlook's hot regions,
    open NASA EONET wildfire events. The live read takes minutes for a large country."""
    cells, paras, gaps = [], [], []
    cf, why = _try(lambda: tools.country_fires(country), f"This week's detections across {country}")
    if cf:
        bs = cf["by_satellite"]
        for sat, label in (("VIIRS_NOAA20", "NOAA-20 VIIRS"), ("VIIRS_NOAA21", "NOAA-21 VIIRS"), ("MODIS_Aqua", "Aqua MODIS")):
            if sat in bs:
                cells.append((label, _fmt(bs[sat]), f"fire detections, {cf['start']} to {cf['end']}"))
        names = [f"{html.escape(n)} ({_fmt(c['noaa20_detections'])})" for c, n in _named_in(cf["top_cells"], country)]
        if names:
            paras.append("<b>Busiest places this week</b> (NOAA-20 detections per half-degree cell): " + "; ".join(names) + ".")
        paras.append(f"<span style='color:#8892a0'>{html.escape(cf['note'])}</span>")
    else:
        gaps.append(why)
    if cf:
        ol = _outlook(cf["box"])
        if ol is None:
            gaps.append("The 30-day outlook could not be read")
        else:
            c = ol["counts"]
            cells.append(("Fire-season watch", _fmt(c["watch"]), f"half-degree cells entering their fire season while already above normal; {_fmt(c['above'])} more above normal"))
            cells.append(("Usual fire season now", _fmt(c["season"] + c["watch"]), f"cells where the next 30 days usually bring fire ({ol['next_30_days'][0]} to {ol['next_30_days'][1]})"))
            watch = _named_in([x for x in ol["cells"] if x["class"] == "watch"][:10], country, 3)
            if watch:
                paras.append("<b>On watch now in " + html.escape(country) + ":</b> " + "; ".join(html.escape(n) for _, n in watch)
                             + ". A climatological outlook, not a forecast.")
    if cf:
        evs = _events(cf["box"])
        if evs is None:
            gaps.append("NASA EONET could not be reached")
        else:
            cells.append(("Open wildfire events", _fmt(len(evs)), "reported to NASA EONET in the last 30 days"))
            if evs:
                paras.append("<b>Reported wildfires:</b> " + "; ".join(f"{html.escape(e['title'])} ({e['date']})" for e in evs[:5]) + ".")
    if gaps:
        paras.append("<span style='color:#8892a0'>Could not look: " + html.escape("; ".join(gaps)) + ". That is not the same as no fire.</span>")
    text = "\n".join([f"Fire across {country} this week"] + [f"- {a}: {b} ({c})" for a, b, c in cells] + gaps)
    return f"Fire across {country} this week", [_tiles(cells)] + paras, text


def welcome(token):
    """After a sign-up with email: the local picture first (seconds to a few minutes), then the whole country (minutes).
    Each is sent as soon as it is ready; a failure is logged and never blocks the alert."""
    for build in ("local", "country"):
        try:
            sub = get(token)
            if build == "local":
                title, paras, text = _local_picture(sub)
            else:
                country = _country_of(sub)
                if not country:
                    log.info("welcome for %s...: no country found, country email skipped", token[:3])
                    return
                title, paras, text = _country_picture(country)
            paras.append("<span style='color:#8892a0;font-size:13px'>Your alert is active: we will email you when satellites "
                         "see something new there. Satellite detections are heat seen from space, not confirmed fires.</span>")
            send_email(sub["email"], title, text + f"\n\n{FREE_SERVER}", _html(title, paras, sub, token))
            log.info("welcome email (%s) for %s... sent", build, token[:3])
        except Exception as ex:  # noqa: BLE001 - a welcome email never breaks the sign-up
            log.error("welcome email (%s) for %s... failed: %s", build, token[:3], ex)


# ---------- CRUD ----------

def _check_limits(d, email):
    if len(d) >= MAX_ALERTS:
        raise ValueError("alert limit reached")
    if email and sum(s.get("email") == email for s in d.values()) >= MAX_PER_EMAIL:
        raise ValueError(f"at most {MAX_PER_EMAIL} alerts per email address")
    if email and sum(s.get("email") == email and not s.get("confirmed") for s in d.values()) >= 3:
        raise ValueError("this address has 3 unconfirmed alerts: confirm those first (check the inbox)")  # anti-spam


def _place(place):
    """Validate a place {lat, lon, radius_km?, label?}: a school, hospital or farm to watch."""
    try:
        lat, lon = float(place["lat"]), float(place["lon"])
        radius = float(place.get("radius_km") or 10)
    except (KeyError, TypeError, ValueError):
        raise ValueError("place needs numeric lat and lon")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not (1 <= radius <= 50):
        raise ValueError("place lat/lon out of range, or radius_km not 1-50")
    label = str(place.get("label") or "")[:120] or f"{lat:.3f}, {lon:.3f}"
    return {"lat": round(lat, 5), "lon": round(lon, 5), "radius_km": radius, "label": label}


def _area_holding(lat, lon):
    """A built area whose box holds the point: presets first, then the smallest custom box."""
    hold = [r for r in tools.list_regions() if r["bbox"][1] <= lat <= r["bbox"][3] and r["bbox"][0] <= lon <= r["bbox"][2]]
    hold.sort(key=lambda r: (not r.get("preset"), (r["bbox"][2] - r["bbox"][0]) * (r["bbox"][3] - r["bbox"][1])))
    return hold[0] if hold else None


def create(region_id=None, bbox=None, name=None, ratio=1.0, min_hotspots=5.0, email=None, triggers=None, base_url="", place=None):
    ratio, floor = float(ratio), float(min_hotspots)
    if not (0.5 <= ratio <= 20) or not (0 <= floor <= 1000):
        raise ValueError("ratio must be 0.5-20 and min_hotspots 0-1000")
    place = _place(place) if place else None
    triggers = list(dict.fromkeys(triggers or (["nearby", "season"] if place else ["anomaly"])))
    if not triggers or any(t not in TRIGGERS for t in triggers):
        raise ValueError(f"triggers must be some of {', '.join(TRIGGERS)}")
    if not place and any(t in PLACE_TRIGGERS for t in triggers):
        raise ValueError("the nearby and season triggers need a place (lat, lon)")
    if place and not region_id and not bbox:   # watch the place inside the area that holds it, or a box around it
        area = _area_holding(place["lat"], place["lon"])
        if area:
            region_id = area["id"]
        else:
            d_lat = max(place["radius_km"], 25) / 111.32
            d_lon = d_lat / max(0.2, math.cos(math.radians(place["lat"])))
            bbox = [round(place["lon"] - d_lon, 3), round(place["lat"] - d_lat, 3), round(place["lon"] + d_lon, 3), round(place["lat"] + d_lat, 3)]
        name = name or place["label"]
    email = (email or "").strip() or None
    if email and not EMAIL_RE.match(email):
        raise ValueError("that does not look like an email address")
    name = (str(name).strip()[:120] or None) if name is not None else None
    with _lock:
        _check_limits(_load(), email)  # before start_aoi: a rejected alert must not start a build
    if not region_id and not bbox:
        raise ValueError("give a region_id or a bbox")
    if region_id:
        area = next((r for r in tools.list_regions() if r["id"] == region_id), None)
        if not area:
            raise tools.NotFound(f"unknown region '{region_id}'")
        rid, bbox, name = region_id, area["bbox"], name or area["name"]
    else:
        rid = tools.start_aoi(bbox, name)["id"]  # builds the area if nobody has asked for it yet
        bbox = list(tools.validate_bbox(bbox))
    with _lock:
        d = _load()
        _check_limits(d, email)  # again under the lock that writes: two parallel requests cannot both pass
        token = secrets.token_urlsafe(9)
        d[token] = {"region_id": rid, "bbox": bbox, "name": name, "ratio": ratio, "min_hotspots": floor,
                    "created": _now(), "last_notified": None, "triggers": triggers, "email": email,
                    "confirmed": bool(email), "code": secrets.token_urlsafe(16), "base_url": base_url,
                    "last_outlook": None, "events_seen": [], "sent": [],
                    "place": place, "nearby_seen": None, "last_season": None}
        _save(d)
        sub = dict(d[token])
    email_status = None
    if email:   # no confirmation step (a small closed group): the alert is active and the fire picture goes out now
        if not smtp_ready():
            email_status = "not_sent: email delivery is not configured on this server"
        elif tools.SERVERLESS:
            email_status = "not_sent: this copy of the site is read-only"
        else:
            email_status = "sending"
            if WELCOME:   # two emails in the background: the place first, then the whole country
                threading.Thread(target=welcome, args=(token,), daemon=True, name="alert-welcome").start()
    return {"token": token, **public(sub), "email_status": email_status}


def public(sub):
    """What an API caller may see: the email masked, the confirm code never."""
    return {k: v for k, v in sub.items() if k not in ("code", "email", "events_seen", "sent")} | {
        "email": mask(sub.get("email")), "sent": (sub.get("sent") or [])[-10:]}


def delete(token):
    with _lock:
        d = _load()
        if d.pop(token, None) is None:
            raise tools.NotFound("unknown alert")
        _save(d)
    return {"deleted": True}


def get(token):
    sub = _load().get(token)
    if not sub:
        raise tools.NotFound("unknown alert")
    return sub


def confirm(token, code):
    sub = get(token)
    if not code or not secrets.compare_digest(code, sub.get("code") or ""):
        raise ValueError("this confirmation link is not valid")
    _update(token, confirmed=True)
    return {**public(sub), "confirmed": True}


def unsubscribe(token, code):
    sub = get(token)
    if not code or not secrets.compare_digest(code, sub.get("code") or ""):
        raise ValueError("this unsubscribe link is not valid")
    _update(token, email=None, confirmed=False)
    return {"unsubscribed": True, "name": sub.get("name")}


# ---------- checking ----------

def _message(name, m, as_of):
    med = m["median_same_days"]
    vs = (f"median {med:.0f} in earlier years" if not med
          else f"{m['value'] / med:.1f}x the median of the same days in earlier years ({med:.0f})")
    return (f"Kiln Watch alert for {name}. {_label(m['period'])} so far ({m['days']} days): {m['value']:.0f} hotspots, "
            f"{vs}; {m['percentile']:.0f}th percentile, rank {m['rank']} of {m['of_years']}. "
            f"This compares with history; it is not a forecast or an official alert. Data through {as_of}.")


def _outlook(bbox):
    try:
        from . import outlook
        return outlook.in_box(bbox, limit=10)
    except Exception:  # no global aggregate on this server: the trigger is simply unavailable
        return None


def _events(bbox):
    w, s, e, n = bbox
    try:
        evs = tools.news.open_wildfires()
    except Exception:
        return None
    return [x for x in evs if s <= x["lat"] <= n and ((w <= x["lon"] <= e) if w <= e else (x["lon"] >= w or x["lon"] <= e))]


def check(token, once=False, mark=True):
    """Current state of one alert. once=True is the scheduled poll (n8n or the email loop): each hit is reported
    once (anomaly once per month, outlook at most weekly, each EONET event once), then marked."""
    sub = get(token)
    rid = sub["region_id"]
    trig = sub.get("triggers") or ["anomaly"]
    base = {"token": token, "region_id": rid, "name": sub["name"], "ratio": sub["ratio"], "triggers": trig,
            "min_hotspots": sub["min_hotspots"], "triggered": False, "email": mask(sub.get("email")),
            "confirmed": bool(sub.get("confirmed")), "sent": (sub.get("sent") or [])[-10:]}
    ol = _outlook(sub["bbox"]) if "outlook" in trig else None
    evs = _events(sub["bbox"]) if "events" in trig else None
    extra = {"outlook": ol and {k: ol[k] for k in ("as_of", "next_30_days", "counts", "rising")},
             "events_in_box": evs,
             "events_error": "NASA EONET is unavailable right now" if "events" in trig and evs is None else None}
    new_events = [x for x in (evs or []) if x["title"] not in (sub.get("events_seen") or [])]
    last_ol = sub.get("last_outlook")
    ol_hit = bool(ol and ol["counts"]["watch"])
    ol_new = ol_hit and (not last_ol or (dt.date.fromisoformat(ol["as_of"]) - dt.date.fromisoformat(last_ol)).days >= 7)
    if not tools.is_built(rid):
        try:
            st = tools.aoi_status(rid)
            if st["status"] == "error" and once:  # the daily poll doubles as the retry
                st = tools.start_aoi(sub["bbox"], sub["name"])
        except tools.NotFound:  # server restarted mid-build
            st = tools.start_aoi(sub["bbox"], sub["name"])
        return {**base, **extra, "status": st["status"], "progress": {k: st.get(k) for k in ("done", "total", "stage")},
                "error": st.get("error"), "outlook_triggered": ol_new if once else ol_hit,
                "new_events": new_events if once else []}
    refreshing = tools.refresh_if_stale(rid)
    place = _place_state(sub, trig, once)
    w = tools.early_warning(rid)
    m = w["month"]
    name = sub["name"] or w["name"]
    hit = "anomaly" in trig and bool(m) and tops(m["value"], m["median_same_days"], sub["ratio"], sub["min_hotspots"])
    new = hit and sub["last_notified"] != m["period"]
    out = {**base, **extra, "name": name, "status": "ready", "triggered": new if once else hit,
           "already_notified": bool(once and hit and not new), "level": w["level"], "as_of": w["as_of"],
           "stale": w["stale"], "refreshing": refreshing, "month": m,
           "outlook_triggered": ol_new if once else ol_hit, "new_events": new_events if once else [],
           "rule": f"Alert when the month so far is above {sub['ratio']:g} x the median of the same days in earlier "
                   f"years and at least {sub['min_hotspots']:g} hotspots.", **place}
    if m:
        out["message"] = _message(name, m, w["as_of"])
    if out.get("nearby_triggered") or out.get("season_triggered"):   # n8n mails `message`: make it the place news
        dg = _digest(sub, out)
        out["message"] = dg[1] if dg else out.get("message")
    if once and mark:  # n8n polls mark here (n8n sends the mail); send_now marks only after delivery
        _mark(token, out)
    return out


def _place_state(sub, trig, once):
    """The place triggers of one alert: fire detected near the place in the last 2 days, and its usual fire season."""
    p = sub.get("place")
    if not p:
        return {}
    rid, out = sub["region_id"], {"place": p, "nearby_triggered": False, "season_triggered": False}
    if "nearby" in trig:
        try:
            nb = tools.place_nearby(rid, p["lat"], p["lon"], p["radius_km"], 2)
            seen = sub.get("nearby_seen")
            fresh = [d for d in nb["detections"] if not seen or d["time_utc"] > seen] if once else nb["detections"]
            out["nearby"] = {k: nb[k] for k in ("count", "nearest_km", "latest_utc", "radius_km", "start", "end", "data_through", "note")}
            out["nearby"]["new"] = len(fresh) if once else nb["count"]
            out["nearby"]["closest"] = fresh[:5]
            out["nearby_triggered"] = bool(fresh)
        except Exception as ex:  # noqa: BLE001 - a failed read is reported, never shown as "no fire"
            out["nearby_error"] = f"live detections could not be read: {str(ex)[:120]}"
    if "season" in trig:
        try:
            soon = dt.date.today() + dt.timedelta(days=7)          # a week's notice before the season month starts
            se = tools.place_season(rid, p["lat"], p["lon"], soon.month)
            key = soon.strftime("%Y-%m")
            out["season"] = se
            hit = se["share"] is not None and se["share"] >= SEASON_SHARE and se["record_years"] >= 5
            out["season_triggered"] = bool(hit and (not once or sub.get("last_season") != key))
            out["season_key"] = key
        except Exception as ex:  # noqa: BLE001
            out["season_error"] = str(ex)[:120]
    return out


def _mark(token, st):
    """Record what was reported, so the next scheduled poll does not repeat it."""
    with _lock:
        d = _load()
        if token not in d:
            return
        if st.get("triggered") and st.get("month"):
            d[token]["last_notified"] = st["month"]["period"]
        if st.get("outlook_triggered") and st.get("outlook"):
            d[token]["last_outlook"] = st["outlook"]["as_of"]
        if st.get("nearby_triggered") and st.get("nearby", {}).get("latest_utc"):
            d[token]["nearby_seen"] = st["nearby"]["latest_utc"]
        if st.get("season_triggered") and st.get("season_key"):
            d[token]["last_season"] = st["season_key"]
        if st.get("new_events"):
            d[token]["events_seen"] = ((d[token].get("events_seen") or []) + [x["title"] for x in st["new_events"]])[-200:]
        _save(d)


def _digest(sub, st):
    """(subject, text, html paragraphs) for whatever fired; None when nothing did."""
    name = st.get("name") or sub["name"]
    parts, paras = [], []
    if st.get("triggered") and st.get("month"):
        m = st["month"]
        parts.append(st["message"])
        med, val = m["median_same_days"], m["value"]
        vs = f", <b>{val / med:.1f}×</b> the median of the same days in earlier years ({med:.0f})" if med else ""
        paras.append(f"<b>{_label(m['period'])} so far is above your threshold.</b> {val:.0f} hotspots in "
                     f"{m['days']} days{vs}; rank <b>{m['rank']} of {m['of_years']}</b> ({m['percentile']:.0f}th percentile).")
    if st.get("outlook_triggered") and st.get("outlook"):
        o = st["outlook"]
        c = o["counts"]
        t = (f"30-day outlook ({o['next_30_days'][0]} to {o['next_30_days'][1]}): {c['watch']} cells in this area "
             f"enter a usually active fire season while already above normal; {c['above']} more above normal.")
        parts.append(t)
        paras.append(f"<b>Fire-season watch for the next 30 days.</b> {c['watch']} half-degree cells here usually see "
                     f"an active season now and are already running above the same days in earlier years "
                     f"({c['above']} more above normal, {o['rising']} with a season that usually ramps up now).")
    p = st.get("place") or sub.get("place")
    if st.get("nearby_triggered") and st.get("nearby"):
        nb = st["nearby"]
        close = nb["closest"][0] if nb.get("closest") else None
        t = (f"Fire detected near {p['label']}: {nb['new']} satellite detection(s) within {nb['radius_km']:g} km in the last "
             f"2 days, the closest about {close['km']:g} km away ({close['time_utc']} UTC, {close['lat']:.4f}, {close['lon']:.4f})."
             if close else f"Fire detected within {nb['radius_km']:g} km of {p['label']} in the last 2 days.")
        t += " A detection is heat seen from space, not a confirmed fire: check locally and follow official advice."
        parts.append(t)
        paras.append(f"<b>Fire detected near {html.escape(p['label'])}.</b> " + html.escape(t.split(": ", 1)[1]))
        if close:
            paras.append(f"<a href='https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{close['lon']:.3f},{close['lat']:.3f},12.0z' "
                         f"style='color:#00a1ff'>See it on the NASA FIRMS map</a>")
    if st.get("season_triggered") and st.get("season"):
        se = st["season"]
        mon = calendar.month_name[se["month"]]
        t = (f"Fire season near {p['label']}: in {se['years_with_fire']} of {se['record_years']} past years, fire was "
             f"detected within about 15 km in {mon}. History, not a forecast; a good time to clear dry material, "
             f"plan residue burning safely and keep an eye on alerts.")
        parts.append(t)
        paras.append(f"<b>{mon} is usually a fire month near {html.escape(p['label'])}.</b> In {se['years_with_fire']} of "
                     f"{se['record_years']} past years fire was detected within about 15 km. History, not a forecast.")
    for e in st.get("new_events") or []:
        parts.append(f"NASA EONET open wildfire event: {e['title']} ({e['date']}) {e.get('url') or ''}")
        paras.append(f"<b>New wildfire event reported:</b> {html.escape(e['title'])} ({e['date']}) "
                     + (f"<a href='{html.escape(e['url'])}' style='color:#00a1ff'>source</a>" if e.get("url") else ""))
    if not parts:
        return None
    kind = ("Fire detected nearby" if st.get("nearby_triggered") else "Fire activity above normal" if st.get("triggered")
            else "Fire season starting nearby" if st.get("season_triggered") else "Fire-season watch" if st.get("outlook_triggered")
            else "New wildfire event")
    return f"{kind}: {name}", "\n\n".join(parts) + f"\n\nOpen the record: {_page_url(sub)}", paras


def send_now(token, force=False):
    """Check one alert and email whatever fired. force=True mails the current status even if nothing fired (test)."""
    sub = get(token)
    if not sub.get("email") or not sub.get("confirmed"):
        raise ValueError("this alert has no confirmed email address")
    sent = sub.get("sent") or []
    if force and sent and time.time() - dt.datetime.fromisoformat(sent[-1]["at"]).timestamp() < 600:
        raise ValueError("a message was sent less than 10 minutes ago; try again later")
    st = check(token, once=not force, mark=False)
    if st.get("status") != "ready" and not force:
        return {"sent": False, "reason": "area still building"}
    dg = _digest(sub, st)
    if not dg and force:
        m = st.get("month")
        para = (f"Status of <b>{html.escape(st.get('name') or '')}</b>: early-warning level <b>{st.get('level', 'pending')}</b>."
                + (f" {_label(m['period'])} so far: {m['value']:.0f} hotspots, median of earlier years "
                   f"{m['median_same_days']:.0f}." if m else ""))
        dg = (f"Your Kiln Watch alert is active: {st.get('name')}",
              (st.get("message") or "Alert is set up; nothing has fired yet.") + f"\n\n{FREE_SERVER}",
              [para, "Nothing has crossed your thresholds yet. We will try to email you when it does."])
    if not dg:
        return {"sent": False, "reason": "nothing new fired"}
    subject, text, paras = dg
    send_email(sub["email"], subject, text, _html(subject, paras, sub, token))
    if not force:
        _mark(token, st)
    rec = {"at": _now(), "subject": subject}
    with _lock:
        d = _load()
        if token in d:
            d[token]["sent"] = ((d[token].get("sent") or []) + [rec])[-50:]
            _save(d)
    log.info("alert %s... emailed: %s", token[:3], subject)
    return {"sent": True, **rec}


def notify_first(token):
    """Right after the confirm link is clicked: check the alert and mail whatever has already fired, so a subscriber
    on a hot area gets the first message in seconds instead of at the next scheduled pass. Never raises; the confirm
    page reports the outcome. Anything not sent now is picked up by the loop (an area still building, a failed send)."""
    if not smtp_ready():
        return {"sent": False, "reason": "email delivery is not configured on this server"}
    try:
        res = send_now(token)
    except Exception as ex:  # noqa: BLE001 - confirming must succeed even when the first mail cannot go out
        log.error("first alert for %s... failed: %s", token[:3], ex)
        return {"sent": False, "error": str(ex)[:160]}
    if not res.get("sent") and res.get("reason") == "nothing new fired" and not get(token).get("sent"):
        try:   # nothing fired: still mail the status now, so the subscriber sees it works and reads the server note
            res = {**send_now(token, force=True), "status_only": True}
        except Exception as ex:  # noqa: BLE001
            log.error("status email for %s... failed: %s", token[:3], ex)
            return {"sent": False, "error": str(ex)[:160]}
    if not res.get("sent"):
        log.info("first alert for %s... not sent: %s", token[:3], res.get("reason"))
    return res


def deliver_all():
    """One pass of the email loop: every confirmed email alert is checked and mailed if something new fired."""
    done = []
    for token, sub in list(_load().items()):
        if sub.get("email") and sub.get("confirmed"):
            try:
                done.append({"token": token[:3] + "…", **send_now(token)})
            except Exception as ex:  # one bad alert never stops the others
                log.error("delivery for alert %s... failed: %s", token[:3], ex)
                done.append({"token": token[:3] + "…", "sent": False, "error": str(ex)[:160]})
    return done


def start_loop(every_h=None):
    """Background email delivery inside the API process (daemon thread), every ALERT_INTERVAL_H hours (default 3)."""
    every = float(every_h or os.environ.get("ALERT_INTERVAL_H", "3")) * 3600

    def run():
        time.sleep(60)  # let the API come up first
        while True:
            if smtp_ready():
                try:
                    done = deliver_all()
                    log.info("delivery pass: %d alerts checked, %d emailed, %d failed", len(done),
                             sum(bool(x.get("sent")) for x in done), sum(bool(x.get("error")) for x in done))
                except Exception:  # noqa: BLE001 - the loop must survive anything
                    log.exception("delivery pass crashed")
            time.sleep(every)

    threading.Thread(target=run, daemon=True, name="alert-email").start()


def workflow(token, base_url):
    """An importable n8n workflow that polls this alert daily and emails when it triggers."""
    sub = get(token)
    url = f"{base_url.rstrip('/')}/api/alerts/{token}/poll"

    def conn(n):
        return {"main": [[{"node": n, "type": "main", "index": 0}]]}

    return {
        "name": f"Kiln Watch alert: {sub['name'] or sub['region_id']}",
        "nodes": [
            {"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 * * *"}]}}, "id": "n1",
             "name": "Every morning", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 0]},
            {"parameters": {"method": "POST", "url": url, "options": {}}, "id": "n2", "name": "Check Kiln Watch alert",
             "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [220, 0]},
            {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
             "conditions": [{"id": "c1", "leftValue": "={{ $json.triggered || $json.outlook_triggered || $json.nearby_triggered || $json.season_triggered || $json.new_events.length > 0 }}",
                             "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
             "combinator": "and"}, "options": {}}, "id": "n3", "name": "Anything new?",
             "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": [440, 0]},
            {"parameters": {"fromEmail": "kilnwatch@example.com", "toEmail": "you@example.com",
                            "subject": "={{ 'Kiln Watch alert: ' + $json.name }}", "emailFormat": "text",
                            "text": "={{ $json.message }}", "options": {}},
             "id": "n4", "name": "Send email", "type": "n8n-nodes-base.emailSend", "typeVersion": 2.1,
             "position": [660, -80]},
        ],
        "connections": {"Every morning": conn("Check Kiln Watch alert"),
                        "Check Kiln Watch alert": conn("Anything new?"),
                        "Anything new?": {"main": [[{"node": "Send email", "type": "main", "index": 0}], []]}},
        "settings": {"executionOrder": "v1"},
    }
