"""HTTP API. Run: uvicorn kw.api:app --port 8000   (from server/)"""
import contextlib
import csv
import html
import io
import os
from pathlib import Path
from urllib.parse import urlencode, urlparse

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route

from . import agent, alerts, mcp_server, news_more, outlook, personas, tools
from .build import OUT


class _McpEndpoint:
    """The MCP server rides along at /mcp, so any deployment is also a remote MCP connector (claude.ai, Claude Code).
    Stateless, one short-lived session manager per request: needs no app-startup hook, so it also works on serverless
    hosts (Vercel) that may skip lifespan events. DNS-rebinding protection is for localhost-only servers; this one is
    public and has no cookie auth to steal."""

    async def __call__(self, scope, receive, send):
        sm = StreamableHTTPSessionManager(app=mcp_server.mcp._mcp_server, stateless=True, json_response=True,
                                          security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False))
        async with sm.run():
            await sm.handle_request(scope, receive, send)


@contextlib.asynccontextmanager
async def lifespan(_app):
    # ponytail: on serverless (Vercel) there is no long-lived process and /tmp is wiped, so email delivery needs a
    # persistent host (Docker / HF Space) or an external store; skipped there rather than half-working.
    if not tools.SERVERLESS:
        alerts.start_loop()  # email delivery every ALERT_INTERVAL_H hours (no-op without SMTP settings)
    yield


app = FastAPI(title="Kiln Watch API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except tools.NotFound as ex:
        raise HTTPException(404, str(ex))
    except ValueError as ex:
        raise HTTPException(400, str(ex))


@app.get("/api/health")
def health():
    regions = tools.list_regions()
    return {"ok": True, "agent": agent.available(), "model": agent.MODEL if agent.available() else None,
            "email": alerts.smtp_ready(), "serverless": tools.SERVERLESS,
            "regions": len(regions), "data_through": max((r["data_through"] for r in regions), default=None)}


@app.get("/api/regions")
def regions():
    return {"regions": tools.list_regions()}


@app.get("/api/casebook")
def casebook():
    return tools.casebook_overview()


@app.get("/api/regions/{rid}/cases")
def cases(rid: str, verdict: str | None = None, limit: int = 50):
    return _guard(tools.list_cases, rid, verdict, min(max(limit, 1), 200))


@app.get("/api/regions/{rid}/cases/{case_id}")
def case_detail(rid: str, case_id: str):
    return _guard(tools.get_case, rid, case_id)


@app.get("/api/regions/{rid}/exposure")
def exposure(rid: str, period: str | None = None):
    return _guard(tools.exposure, rid, period)


@app.get("/api/regions/{rid}/exposure/place")
def exposure_place(rid: str, lat: float, lon: float):
    return _guard(tools.exposure_place, rid, lat, lon)


@app.get("/api/regions/{rid}/summary")
def summary(rid: str):
    return _guard(tools.region_summary, rid)


@app.get("/api/regions/{rid}/warning")
def warning(rid: str):
    def run():
        refreshing = tools.refresh_if_stale(rid)  # any area stays live: stale records rebuild in the background
        return {**tools.early_warning(rid), "refreshing": refreshing}
    return _guard(run)


@app.get("/api/warnings")
def warnings(min_level: str | None = None):
    """Every area's early-warning status. min_level=watch keeps watch and elevated."""
    return _guard(tools.warnings, min_level)


@app.get("/api/outlook")
def outlook_all():
    """Worldwide 30-day outlook grid (0.5 degree, Aqua MODIS). Needs the global aggregate (python -m kw.globe)."""
    try:
        return outlook.get()
    except FileNotFoundError as ex:
        raise HTTPException(503, str(ex))


@app.get("/api/outlook/at")
def outlook_at(lat: float, lon: float):
    try:
        return outlook.at(lat, lon)
    except FileNotFoundError as ex:
        raise HTTPException(503, str(ex))


@app.get("/api/news/latest")
def news_latest(days: int = 7):
    """Worldwide fire news and events of the last 1-30 days (Google News in 7 languages, GDACS, NASA EONET)."""
    return news_more.latest(days)


@app.get("/api/news/search")
def news_search(place: str, start: str = "", end: str = ""):
    """Fire reports for ANY place name and window (default last 30 days); no built area needed."""
    import datetime as dt
    def run():
        b = dt.date.fromisoformat(end) if end else dt.date.today()
        a = dt.date.fromisoformat(start) if start else b - dt.timedelta(days=30)
        if (b - a).days > 3 * 366:
            raise ValueError("window must be at most 3 years")
        return news_more.search_place(place.strip()[:120], a, b)
    return _guard(run)


@app.get("/api/place")
def place(q: str = ""):
    """Geocode any place name to centre, bbox and overlapping areas (Nominatim via backend cache)."""
    return _guard(tools.find_place, q.strip()[:120])


@app.get("/api/hotspots")
def hotspots_any(west: float, south: float, east: float, north: float, start: str, end: str):
    """Raw detections per day and satellite for any box and window, from the global aggregate."""
    return _guard(tools.global_hotspots, [west, south, east, north], start, end)


@app.get("/api/regions/{rid}/brief")
def brief(rid: str):
    return _guard(tools.briefing, rid)


@app.get("/api/regions/{rid}/annual")
def annual(rid: str):
    return _guard(tools.annual, rid)


@app.get("/api/personas")
def persona_list():
    return {"personas": personas.public()}


@app.get("/api/personas/{pid}.md")
def persona_md(pid: str):
    if pid not in personas.BY_ID:
        raise HTTPException(404, "unknown character")
    return PlainTextResponse(personas.subagent_md(pid), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{pid}.md"'})


@app.get("/api/events")
def events():
    try:
        return tools.active_events()
    except Exception as ex:  # EONET unreachable: say so, never an empty "no fires" answer
        raise HTTPException(502, f"NASA EONET is unavailable: {ex}")


@app.get("/api/regions/{rid}/evidence")
def evidence(rid: str, period: str):
    return _guard(tools.evidence, rid, period)


@app.get("/api/regions/{rid}/reports")
def reports(rid: str, period: str):
    return _guard(tools.reports, rid, period)


@app.get("/api/regions/{rid}/timeline-reports")
def timeline_reports(rid: str, start: str, end: str):
    return _guard(tools.timeline_reports, rid, start, end)


@app.get("/api/regions/{rid}/export.csv")
def export(rid: str, granularity: str = "month"):
    cal = _guard(tools.get_calendar, rid, granularity)
    meta = _guard(tools.audit, rid)
    buf = io.StringIO()
    buf.write(f"# Kiln Watch harmonized fire record — {rid}\n# {meta['estimand']['primary']}\n")
    buf.write(f"# {meta['provenance']['acknowledgement']}\n# source: {meta['provenance']['mirror']} "
              f"(updated {meta['provenance']['mirror_updated']}); code {meta['provenance']['code_version']}; "
              f"reproduce: {meta['provenance']['reproduce']}\n")
    w = csv.writer(buf, lineterminator="\n")
    obs = list(tools.RAW_OBS)
    w.writerow(["period", "partial", "provisional", "raw_detections_all_satellites", "hotspots_aqua_scale", "ci95_lo",
                "ci95_hi", "hotspots_viirs_scale", "viirs_scale_modelled", "fire_celldays_aqua_scale", "median_same_period",
                "ratio_to_median", "percentile", "rank", "of_years", "satellites_used",
                *[f"coverage_{s}" for s in obs], *[f"raw_det_{s}" for s in obs], "static_source_hotspots", "nrt_share"])
    for r in cal["rows"]:
        h = r["vs_history"]
        w.writerow([r["period"], int(r["partial"]), int(r["provisional"]), r["raw_detections_all_satellites"],
                    r["hotspots_aqua_scale"]["value"], *r["hotspots_aqua_scale"]["ci95"], r["hotspots_viirs_scale"]["value"],
                    int(r["hotspots_viirs_scale"]["modelled"]), r["fire_celldays_aqua_scale"]["value"],
                    h["median_same_period"], h["ratio_to_median"], h["percentile"], h["rank"], h["of_years"],
                    "+".join(r["satellites_used"]), *[r["coverage"].get(s) for s in obs],
                    *[r["raw_detections"][s] for s in obs], r["static_source_hotspots_aqua_scale"], r["nrt_share"]])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="kilnwatch-{rid}-{granularity}.csv"'})


@app.get("/api/regions/{rid}/hotspots.csv")
def hotspots(rid: str, start: str, end: str):
    text = _guard(tools.hotspots_csv, rid, start, end)
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="kilnwatch-{rid}-hotspots-{start}-{end}.csv"'})


def _origin_of(url):
    p = urlparse(url or "")
    return f"{p.scheme}://{p.netloc}".lower() if p.scheme in ("http", "https") and p.netloc else ""


def _trusted_origin(origin):
    """The site the subscriber is actually on (any dev port on localhost, or a configured live domain)."""
    origin = _origin_of(origin)
    if not origin:
        return ""
    p = urlparse(origin)
    if p.hostname in ("localhost", "127.0.0.1", "::1"):
        return origin  # a localhost link only ever opens on the reader's own machine
    allowed = {_origin_of(u) for u in [os.environ.get("PUBLIC_URL", "")] + os.environ.get("ALLOWED_ORIGINS", "").split(",")}
    return origin if origin in allowed else ""


def _public_base(request: Request, client_origin=None):
    # Links in emails must point at the site the user subscribed from. The Host header and the client's origin are
    # caller-controlled, so only localhost (any port), PUBLIC_URL and ALLOWED_ORIGINS are honoured.
    trusted = _trusted_origin(client_origin) or _trusted_origin(request.headers.get("origin"))
    if trusted:
        return trusted
    if os.environ.get("PUBLIC_URL"):
        return os.environ["PUBLIC_URL"]
    if alerts.smtp_ready():
        raise HTTPException(503, "PUBLIC_URL must be set on a server that sends email")
    return str(request.base_url)


@app.post("/api/alerts")
def alert_create(request: Request, body: dict = Body(...)):
    """Your own alert for any area: {region_id | bbox, name?, ratio?, min_hotspots?, email?, triggers?, place?}.
    triggers: any of anomaly, outlook, events, and with a place {lat, lon, radius_km?, label?} also nearby (fire
    detected within radius_km in the last 2 days) and season (the place's usual fire month is starting).
    With email, a confirmation link is mailed first (double opt-in). Returns the secret token."""
    return _guard(alerts.create, body.get("region_id"), body.get("bbox"), body.get("name"),
                  body.get("ratio", 1.0), body.get("min_hotspots", 5.0), body.get("email"), body.get("triggers"),
                  _public_base(request, body.get("origin")), body.get("place"))


def _note(title, text, ok=True, token="", name="", page="warning", base="", region=""):
    color = "#00a1ff" if ok else "#ff8a80"
    base = base.rstrip("/")
    q = urlencode({"pg": page, **({"r": region} if region else {}), **({"token": token} if token else {})})
    target = f"{base}/#{q}"      # r= reopens the same area the alert was made in
    script = f"""<script>
try {{
    const k = 'kw.alerts';
    const list = JSON.parse(localStorage.getItem(k) || '[]');
    if ('{token}' && !list.some(x => x.token === '{token}')) {{
        list.push({{ token: '{token}', name: '{html.escape(name)}' }});
        localStorage.setItem(k, JSON.stringify(list));
    }}
}} catch(e) {{}}
</script>""" if token and ok else ""
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        f"<title>Kiln Watch</title><body style='margin:0;background:#05080d;color:#f1f4f8;font:16px Inter,"
                        f"Arial,sans-serif;display:grid;place-items:center;min-height:100vh'><div style='max-width:460px;"
                        f"padding:24px'><p style='color:#ff7a6e;font-size:11px;letter-spacing:.12em;text-transform:uppercase'>"
                        f"Kiln Watch</p><h1 style='font-size:22px;color:{color}'>{html.escape(title)}</h1><p>{html.escape(text)}"
                        f"</p><p><a href='{html.escape(target)}' style='color:#00a1ff'>Back to Kiln Watch</a></p></div>{script}",
                        status_code=200 if ok else 400)


@app.get("/api/alerts/{token}/confirm")
def alert_confirm(token: str, code: str = ""):
    try:
        sub = alerts.confirm(token, code)
    except (ValueError, tools.NotFound) as ex:
        return _note("Link not valid", str(ex), False)
    first = alerts.notify_first(token)  # a hot area gets its first message now, not at the next 3-hourly pass
    if first.get("sent"):
        text = (f"Fire activity around {sub.get('name')} is already above your thresholds: the alert email is on its way "
                "to your inbox now. After that you will only hear from us when something new happens. Every email has a "
                "one-click unsubscribe link.")
    elif first.get("error"):
        text = (f"Your alert for {sub.get('name')} is active, but the first email could not be sent just now "
                f"({first['error']}). It will be retried automatically.")
    elif first.get("reason") == "area still building":
        text = (f"Your alert for {sub.get('name')} is active. The area's record is still being built; you will get an "
                "email as soon as it is ready and something has crossed your thresholds.")
    else:
        text = (f"Your alert for {sub.get('name')} is active. Nothing is above your thresholds right now; you will get an "
                "email when fire activity crosses them. Every email has a one-click unsubscribe link.")
    if sub.get("place"):  # a school, hospital or farm: say what it watches and go back to where it was made
        p = sub["place"]
        what = " and ".join(x for x, t in (("fire detected within %g km" % p["radius_km"], "nearby"),
                                          ("the start of its usual fire month", "season")) if t in (sub.get("triggers") or []))
        if first.get("sent"):
            text = (f"Fire has already been detected near {p['label']}: the alert email is on its way. After that you will only "
                    "hear from us about new detections. Every email has a one-click unsubscribe link.")
        elif first.get("error"):
            text = f"Your alert for {p['label']} is active, but the first email could not be sent just now ({first['error']}). It will be retried automatically."
        else:
            text = (f"Your alert for {p['label']} is active. You will get an email when there is {what}. "
                    "Satellites see heat a few hours after it happens and miss small fires: this is an early hint, not an official warning.")
        return _note("Alert confirmed", text, True, token, p["label"], "cases", sub.get("base_url") or "", sub["region_id"])
    return _note("Alert confirmed", text, True, token, sub.get("name") or "", base=sub.get("base_url") or "", region=sub["region_id"])


@app.get("/api/alerts/{token}/unsubscribe")
def alert_unsubscribe(token: str, code: str = ""):
    try:
        alerts.unsubscribe(token, code)
    except (ValueError, tools.NotFound) as ex:
        return _note("Link not valid", str(ex), False)
    return _note("Unsubscribed", "No more emails for this alert. The alert itself still works through n8n if you set that up.")


@app.post("/api/alerts/{token}/send-test")
def alert_send_test(token: str):
    """Email the alert's current status now (confirmed email only, at most every 10 minutes)."""
    try:
        return _guard(alerts.send_now, token, True)
    except RuntimeError as ex:
        raise HTTPException(503, str(ex))


@app.get("/api/alerts/{token}")
def alert_status(token: str):
    return _guard(alerts.check, token)


@app.post("/api/alerts/{token}/poll")
def alert_poll(token: str):
    """What n8n calls on a schedule: triggered is true once per month when the alert's rule is met."""
    return _guard(alerts.check, token, True)


@app.delete("/api/alerts/{token}")
def alert_delete(token: str):
    return _guard(alerts.delete, token)


@app.get("/api/alerts/{token}/n8n.json")
def alert_workflow(token: str, request: Request):
    wf = _guard(alerts.workflow, token, str(request.base_url))
    return JSONResponse(wf, headers={"Content-Disposition": 'attachment; filename="kiln-watch-alert.n8n.json"'})


@app.post("/api/aoi")
def aoi(body: dict = Body(...)):
    return _guard(tools.start_aoi, body.get("bbox") or [], body.get("name"))


@app.get("/api/aoi/{rid}")
def aoi_status(rid: str):
    return _guard(tools.aoi_status, rid)


@app.post("/api/agent")
def ask(body: dict = Body(...)):
    msg = (body.get("message") or "").strip()
    if not msg or len(msg) > 2000:
        raise HTTPException(400, "message must be 1-2000 characters")
    try:
        return agent.ask(msg, body.get("history"), body.get("context"))
    except RuntimeError as ex:
        # Deterministic fallback: the pipeline's own sentences for the area on screen, so the demo never blanks.
        rid = (body.get("context") or {}).get("region_id")
        try:
            facts = tools.region_summary(rid)["answers"] if rid else []
        except tools.NotFound:
            facts = []
        if not facts:
            raise HTTPException(503, str(ex))
        from . import charts
        return {"answer": "**The language model is unavailable, so here are the record's own findings.**\n\n"
                          + "\n".join(f"- {f}" for f in facts),
                "trace": [{"tool": "region_summary", "args": {"region_id": rid}, "ok": True}],
                "actions": [], "model": None, "fallback": str(ex), "charts": charts.auto([("region_summary", {"region_id": rid}),
                                                                                          ("early_warning", {"region_id": rid})])}


app.router.routes.insert(0, Route("/mcp", endpoint=_McpEndpoint(), methods=["GET", "POST", "DELETE"]))  # before the SPA catch-all

OUT.mkdir(parents=True, exist_ok=True)
app.mount("/data/regions", StaticFiles(directory=OUT), name="regions")

# Single-process deploy: serve the built web app too (web/dist), with SPA fallback.
DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith(("api/", "data/")):  # unknown API route: a real 404, never the app's HTML
            raise HTTPException(404, f"no such endpoint /{path}")
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
