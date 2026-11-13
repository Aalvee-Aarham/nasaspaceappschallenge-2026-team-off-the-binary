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
        assert len(sent) == 1  # the confirmation mail only
        sent.clear()
        code = alerts._load()[a["token"]]["code"]
        alerts.confirm(a["token"], code)
        first = alerts.notify_first(a["token"])
        assert first["sent"] is True and len(sent) == 1 and sent[0][0] == "test@example.com", (first, sent)
        assert alerts.notify_first(a["token"])["sent"] is False and len(sent) == 1  # a second click repeats nothing
    finally:
        alerts.send_email, alerts.smtp_ready = real_send, real_ready


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
