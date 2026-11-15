"""Run: python server/tests/test_alerts.py  — alert rule, once-per-month polling, n8n workflow shape (uses a temp store)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kw import alerts, tools  # noqa: E402

tools.SERVERLESS = True  # no background rebuild threads in tests (they abort the interpreter at exit)


def _hot_area():
    """A built preset whose month so far tops 0.5 x the median: these tests are about the marking logic, so they must
    not depend on one area's live data (Punjab stopped qualifying once drifted Aqua was taken out of 2023+)."""
    for r in tools.list_regions():
        m = tools.early_warning(r["id"])["month"]
        if m and alerts.tops(m["value"], m["median_same_days"], 0.5, 0):
            return r["id"]
    raise AssertionError("no preset area currently tops 0.5 x its median; the marking tests cannot run")


def test_tops_rule():
    assert alerts.tops(10, 5, 1.0, 5) is True
    assert alerts.tops(10, 10, 1.0, 5) is False          # equal to the median is not "above"
    assert alerts.tops(3, 0, 1.0, 5) is False            # tiny counts never alert
    assert alerts.tops(11, 5, 2.0, 5) is True and alerts.tops(9, 5, 2.0, 5) is False


def test_poll_notifies_once_per_month_and_workflow_has_token():
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    a = alerts.create(region_id=_hot_area(), ratio=0.5, min_hotspots=0)   # low bar: this month tops 0.5 x median
    first = alerts.check(a["token"], once=True)
    again = alerts.check(a["token"], once=True)
    assert first["status"] == "ready" and first["triggered"] is True and "not a forecast" in first["message"]
    assert again["triggered"] is False and again["already_notified"] is True
    assert alerts.check(a["token"])["triggered"] is True  # plain status ignores the once-per-month mark
    wf = alerts.workflow(a["token"], "http://host:8000/")
    assert wf["nodes"][1]["parameters"]["url"] == f"http://host:8000/api/alerts/{a['token']}/poll"
    alerts.delete(a["token"])
    try:
        alerts.check(a["token"])
        raise AssertionError("deleted alert still answered")
    except tools.NotFound:
        pass


def test_bad_input():
    for kw in ({"region_id": "nowhere"}, {"region_id": "punjab", "ratio": 0}, {"bbox": [0, 0, 50, 50]}):
        try:
            alerts.create(**kw)
            raise AssertionError(f"accepted {kw}")
        except (tools.NotFound, ValueError):
            pass


def test_failed_send_is_retried():
    """A send that fails must leave the alert due, so the next scheduled pass tries again."""
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    real = alerts.send_email

    def boom(*a, **k):
        raise RuntimeError("SMTP unreachable")
    alerts.send_email = boom
    try:
        a = alerts.create(region_id=_hot_area(), ratio=0.5, min_hotspots=0, email="test@example.com", base_url="http://x")
        d = alerts._load()
        d[a["token"]]["confirmed"] = True
        alerts._save(d)
        try:
            alerts.send_now(a["token"])
            raise AssertionError("send_now hid the failure")
        except RuntimeError:
            pass
        assert alerts.check(a["token"], once=True)["triggered"] is True  # still due after the failed send
    finally:
        alerts.send_email = real


def test_first_alert_goes_out_on_confirm():
    """Confirming a subscription on an area that is already above threshold mails at once, and only once."""
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    real_send, real_ready, sent = alerts.send_email, alerts.smtp_ready, []
    alerts.send_email = lambda to, subject, text, html_body=None: sent.append((to, subject))
    alerts.smtp_ready = lambda: True
    try:
        a = alerts.create(region_id=_hot_area(), ratio=0.5, min_hotspots=0, email="test@example.com", base_url="http://x")
        assert sent == [] and alerts._load()[a["token"]]["confirmed"] is True   # no confirmation step: active at once
        first = alerts.notify_first(a["token"])
        assert first["sent"] is True and len(sent) == 1 and sent[0][0] == "test@example.com", (first, sent)
        assert alerts.notify_first(a["token"])["sent"] is False and len(sent) == 1  # a second click repeats nothing
    finally:
        alerts.send_email, alerts.smtp_ready = real_send, real_ready


def test_quiet_area_still_gets_a_status_email_on_confirm():
    """Nothing above threshold: confirming still mails the current status once (with the free-server note)."""
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    real_send, real_ready, sent = alerts.send_email, alerts.smtp_ready, []
    alerts.send_email = lambda to, subject, text, html_body=None: sent.append((subject, text))
    alerts.smtp_ready = lambda: True
    try:
        a = alerts.create(region_id="punjab", ratio=20, min_hotspots=1000, email="test@example.com", base_url="http://x")
        first = alerts.notify_first(a["token"])
        assert first.get("status_only") and len(sent) == 1 and "active" in sent[0][0], (first, sent)
        assert alerts.FREE_SERVER in sent[0][1]   # every email says the server sleeps
        again = alerts.notify_first(a["token"])
        assert again["sent"] is False and "error" not in again and len(sent) == 1, again   # a second click: no error, no mail
    finally:
        alerts.send_email, alerts.smtp_ready = real_send, real_ready


def test_email_sign_up_is_active_at_once_and_starts_the_welcome_emails():
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    started = []
    real = alerts.smtp_ready, alerts.welcome, tools.SERVERLESS
    alerts.smtp_ready, alerts.welcome, tools.SERVERLESS = (lambda: True), started.append, False
    try:
        a = alerts.create(region_id="punjab", email="test@example.com", base_url="http://x")
        for _ in range(50):          # the welcome emails run in a background thread
            if started:
                break
            __import__("time").sleep(0.05)
        assert a["email_status"] == "sending" and a["confirmed"] is True and started == [a["token"]], (a, started)
    finally:
        alerts.smtp_ready, alerts.welcome, tools.SERVERLESS = real


def test_alerts_survive_a_restart_through_the_blob_store():
    """KW_STATE_URL: the list is written through to one blob and read back by a fresh process."""
    store = {}

    def fake_blob(method, body=None):
        if method == "PUT":
            store["b"] = body
            return b""
        if "b" not in store:
            raise alerts.urllib.error.HTTPError("u", 404, "not found", {}, None)
        return store["b"]
    real = alerts._blob, alerts.STATE_URL, alerts._mem
    alerts._blob, alerts.STATE_URL, alerts._mem = fake_blob, "https://x.blob.core.windows.net/state?sig=1", None
    try:
        assert alerts._load() == {}                      # first run: no blob yet
        a = alerts.create(region_id="punjab", name="blob test")
        alerts._mem = None                               # the server slept: memory is gone, the blob is not
        assert alerts.get(a["token"])["name"] == "blob test"
    finally:
        alerts._blob, alerts.STATE_URL, alerts._mem = real


def test_welcome_sends_local_then_country_and_names_what_could_not_be_read():
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    sent = []

    def down(*a, **k):
        raise RuntimeError("mirror down")
    saved = {n: getattr(tools, n) for n in ("global_hotspots", "country_fires")}
    real = alerts.send_email, alerts._outlook, alerts._events, alerts._country_of
    alerts.send_email = lambda to, subject, text, html_body=None: sent.append((subject, text))
    tools.global_hotspots = down                                       # this week's detections fail
    tools.country_fires = lambda c: {"box": [88, 20, 93, 27], "start": "a", "end": "b", "by_satellite": {"VIIRS_NOAA20": 7},
                                     "top_cells": [], "note": "box"}
    alerts._outlook = lambda box: None
    alerts._events, alerts._country_of = (lambda box: []), (lambda sub: "Bangladesh")
    try:
        a = alerts.create(region_id="punjab", name="welcome test")
        alerts._update(a["token"], email="test@example.com")
        alerts.welcome(a["token"])
        assert [s for s, _ in sent] == ["Fire around welcome test right now", "Fire across Bangladesh this week"], sent
        assert "could not be read" in sent[0][1] and "Fire this week: 0" not in sent[0][1]   # failed, never zero
        assert "NOAA-20 VIIRS: 7" in sent[1][1] and "outlook could not be read" in sent[1][1]
    finally:
        alerts.send_email, alerts._outlook, alerts._events, alerts._country_of = real
        for n, f in saved.items():
            setattr(tools, n, f)


def test_first_alert_failure_never_breaks_confirm():
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    real_send, real_ready = alerts.send_email, alerts.smtp_ready
    alerts.smtp_ready = lambda: True
    try:
        alerts.send_email = lambda *a, **k: None
        a = alerts.create(region_id=_hot_area(), ratio=0.5, min_hotspots=0, email="test@example.com", base_url="http://x")
        alerts.confirm(a["token"], alerts._load()[a["token"]]["code"])

        def boom(*a, **k):
            raise RuntimeError("535 bad credentials")
        alerts.send_email = boom
        res = alerts.notify_first(a["token"])  # must return, not raise
        assert res["sent"] is False and "535" in res["error"], res
        assert alerts.check(a["token"], once=True)["triggered"] is True  # still due: the loop retries it
    finally:
        alerts.send_email, alerts.smtp_ready = real_send, real_ready


def test_eonet_outage_is_reported():
    """'EONET is down' must not look like 'no events here'."""
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    real = tools.news.open_wildfires

    def down():
        raise OSError("EONET unreachable")
    tools.news.open_wildfires = down
    try:
        a = alerts.create(region_id="punjab", triggers=["events"])
        st = alerts.check(a["token"])
        assert st["events_in_box"] is None and st["events_error"], st.get("events_error")
    finally:
        tools.news.open_wildfires = real


def test_rejected_alert_starts_no_build():
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    calls, real_start, real_max = [], tools.start_aoi, alerts.MAX_ALERTS
    tools.start_aoi = lambda *a, **k: calls.append(a) or {"id": "aoi-test"}
    alerts.MAX_ALERTS = 0
    try:
        try:
            alerts.create(bbox=[90.0, 23.0, 91.0, 24.0], name="test")
            raise AssertionError("over the limit but accepted")
        except ValueError:
            pass
        assert calls == [], "a rejected alert started an area build"
    finally:
        tools.start_aoi, alerts.MAX_ALERTS = real_start, real_max


def test_place_alert_reports_each_detection_once():
    """A place alert (school, farm) lands in the area holding it; nearby fire is reported once per new detection and the
    season once per month. Live reads are stubbed: this is about the marking logic, not today's fires."""
    alerts.FILE = Path(tempfile.mkdtemp()) / "alerts.json"
    real = tools.place_nearby, tools.place_season
    det = [{"time_utc": "2026-11-12 08:09", "satellite": "NOAA-20", "lat": 30.80, "lon": 75.81, "frp_mw": 9.0, "km": 11.5}]
    tools.place_nearby = lambda rid, la, lo, r, d: {"count": len(det), "nearest_km": 11.5, "latest_utc": max(x["time_utc"] for x in det),
                                                    "radius_km": r, "start": "", "end": "", "data_through": "", "note": "", "detections": list(det)}
    tools.place_season = lambda rid, la, lo, m: {"month": m, "years_with_fire": 20, "record_years": 25, "share": 0.8, "years": []}
    try:
        a = alerts.create(place={"lat": 30.9, "lon": 75.85, "radius_km": 25, "label": "Test farm"})
        assert a["region_id"] == "punjab" and a["triggers"] == ["nearby", "season"]
        first = alerts.check(a["token"], once=True)
        assert first["nearby_triggered"] and first["season_triggered"] and "Test farm" in first["message"]
        assert "not a confirmed fire" in first["message"] and "not a forecast" in first["message"]
        again = alerts.check(a["token"], once=True)
        assert not again["nearby_triggered"] and not again["season_triggered"]
        det.insert(0, {**det[0], "time_utc": "2026-11-13 07:50", "km": 4.0})   # a newer detection fires again
        third = alerts.check(a["token"], once=True)
        assert third["nearby_triggered"] and third["nearby"]["new"] == 1 and not third["season_triggered"]
        try:
            alerts.create(region_id="punjab", triggers=["nearby"])
            raise AssertionError("a nearby trigger without a place was accepted")
        except ValueError:
            pass
    finally:
        tools.place_nearby, tools.place_season = real


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
