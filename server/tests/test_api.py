"""Run: python server/tests/test_api.py  — HTTP-level checks (needs the server venv)."""
import datetime as dt
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from kw import alerts, api, tools  # noqa: E402

tools.SERVERLESS = True  # no background rebuild threads in tests
client = TestClient(api.app)  # no `with`: the lifespan (email loop) is not started


def test_health_reports_serverless():
    h = client.get("/api/health").json()
    assert h["serverless"] is True and h["regions"] >= 9, h


class _Req:
    base_url = "http://evil.example/"  # what a forged Host header would produce
    headers: dict = {}                 # no Origin header


def test_links_never_come_from_host_header_when_email_is_on():
    real, env = alerts.smtp_ready, os.environ.pop("PUBLIC_URL", None)
    alerts.smtp_ready = lambda: True
    try:
        try:
            api._public_base(_Req())
            raise AssertionError("built an email link from the Host header")
        except HTTPException as ex:
            assert ex.status_code == 503
        os.environ["PUBLIC_URL"] = "https://kiln-watch-seven.vercel.app"
        assert api._public_base(_Req()) == "https://kiln-watch-seven.vercel.app"
    finally:
        alerts.smtp_ready = real
        os.environ.pop("PUBLIC_URL", None)
        if env is not None:
            os.environ["PUBLIC_URL"] = env


def test_public_base_without_email_uses_request():
    real, env = alerts.smtp_ready, os.environ.pop("PUBLIC_URL", None)
    alerts.smtp_ready = lambda: False
    try:
        assert api._public_base(_Req()) == "http://evil.example/"
    finally:
        alerts.smtp_ready = real
        if env is not None:
            os.environ["PUBLIC_URL"] = env


def test_place_lookup():
    res = client.get("/api/place?q=Dhaka").json()
    assert res.get("found") is True
    assert "bbox" in res and len(res["bbox"]) == 4
    empty = client.get("/api/place?q=").json()
    assert empty.get("found") is False


def test_alert_without_target_is_bad_request():
    r = client.post("/api/alerts", json={})
    assert r.status_code == 400
    assert "region_id" in r.json()["detail"] and "bbox" in r.json()["detail"]


def test_large_json_responses_are_gzipped():
    r = client.get("/api/regions", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_hotspots_csv_is_streamed():
    def rows(_rid, _a, _b):
        yield "latitude,longitude\n"
        for i in range(10):
            yield f"{i},{i}\n"

    real = tools.hotspots_csv
    api.tools.hotspots_csv = rows
    try:
        r = client.get("/api/regions/punjab/hotspots.csv?start=2020-01-01&end=2020-01-02")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers["content-disposition"]
        assert b"latitude,longitude" in r.content
    finally:
        api.tools.hotspots_csv = real


def test_news_cache_is_atomic_and_negatively_cached():
    import tempfile
    from pathlib import Path
    from kw import news

    real_cache = news.CACHE
    news.CACHE = Path(tempfile.mkdtemp())
    calls = [0]

    def boom():
        calls[0] += 1
        raise ValueError("provider down")
    try:
        for _ in range(2):
            try:
                news._cached("down:key", 60, boom)
                raise AssertionError("cached a failed provider as success")
            except Exception as ex:
                assert "provider down" in str(ex)
        assert calls[0] == 1, "a failed provider was retried inside its negative-cache TTL"

        results = []
        def many():
            for _ in range(8):
                try:
                    results.append(news._cached("atomic:key", 60, lambda: {"ok": True})["ok"])
                except Exception as ex:
                    results.append(ex)
        threads = [threading.Thread(target=many) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert results == [True] * 64, results
    finally:
        news.CACHE = real_cache


def test_google_news_language_queries_run_concurrently():
    from kw import news_more

    start = dt.date(2020, 1, 1)
    barrier = threading.Barrier(3)

    def fake(query, lang, a, b):
        barrier.wait(timeout=2)  # serial execution would deadlock here
        return [{"title": f"{lang}:{a}", "date": str(a), "url": query, "lang": lang, "outlet": "test"}], query, query
    real = news_more.google_news
    news_more.google_news = fake
    try:
        items, _url, _q = news_more._google_for(["Place"], ["es", "pt"], start, start + dt.timedelta(days=2))
    finally:
        news_more.google_news = real
    assert len(items) == 3 and {i["lang"] for i in items} == {"es", "pt", "en"}


def test_custom_area_capacity_limit_is_429_and_starts_no_build():
    real_pending, real_max, real_serverless = tools.MAX_PENDING_BUILDS, tools.MAX_CUSTOM_AREAS, tools.SERVERLESS
    started = []
    real_build = tools.build_region
    tools.MAX_PENDING_BUILDS, tools.MAX_CUSTOM_AREAS, tools.SERVERLESS = 0, 20, False
    tools.build_region = lambda *a, **k: started.append(a)
    try:
        r = client.post("/api/aoi", json={"bbox": [90.0, 23.0, 91.0, 24.0], "name": "cap test"})
        assert r.status_code == 429 and "build queue" in r.json()["detail"]
    finally:
        tools.MAX_PENDING_BUILDS, tools.MAX_CUSTOM_AREAS = real_pending, real_max
        tools.SERVERLESS, tools.build_region = real_serverless, real_build
    assert started == []


def test_missing_raw_cache_on_serverless_is_503_not_inline_download():
    def unavailable(*_a):
        raise tools.Unavailable("the raw detection cache is not on this server")
    real = tools._cache_files
    tools._cache_files = unavailable
    try:
        r = client.get("/api/regions/punjab/evidence?period=2024-01")
        assert r.status_code == 503
        assert "raw detection cache" in r.json()["detail"]
    finally:
        tools._cache_files = real


def test_public_mcp_mode_removes_state_changing_tools():
    import importlib
    from kw import mcp_server

    os.environ["KW_PUBLIC_MCP"] = "1"
    try:
        importlib.reload(mcp_server)
        public = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
        assert {"create_custom_area", "subscribe_email_alert", "create_alert",
                "subscribe_place_alert", "delete_alert"}.isdisjoint(public)
        # every tool that declares itself not read-only must be gone from the public list
        writes = {t.name for t in mcp_server.mcp._tool_manager.list_tools()
                  if t.annotations and t.annotations.readOnlyHint is False}
        assert writes.isdisjoint(public), writes
        assert len(public) == 35   # 40 tools minus the five that change state
    finally:
        os.environ.pop("KW_PUBLIC_MCP", None)
        importlib.reload(mcp_server)
    trusted = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert len(trusted) == 40


def test_cases_and_exposure_endpoints():
    r = client.get("/api/regions/dhaka-kilns/cases?limit=2")
    assert r.status_code == 200 and sum(r.json()["counts"].values()) >= len(r.json()["cases"]) and "caveat" in r.json()
    assert client.get("/api/regions/dhaka-kilns/cases?verdict=bogus").status_code == 400
    assert client.get("/api/regions/dhaka-kilns/cases/not-a-case").status_code == 404
    case = r.json()["cases"][0]
    assert client.get(f"/api/regions/dhaka-kilns/cases/{case['id']}").json()["id"] == case["id"]
    e = client.get("/api/regions/dhaka-kilns/exposure?period=2018-11")
    assert e.status_code == 200 and e.json()["caveat"] and e.json()["population"] > 0
    assert client.get("/api/regions/dhaka-kilns/exposure?period=2018-13").status_code == 400
    assert client.get("/api/regions/nowhere/exposure").status_code == 404


def test_watchlist_rows_carry_the_backtest():
    rows = tools.warnings()["alerts"]
    assert rows and all("backtest" in a for a in rows)
    for a in rows:   # a score, or a stated reason: never a silent blank
        assert (a["backtest"] and 0 <= a["backtest"]["pod"] <= 1) or a["backtest_reason"], a["region_id"]


def test_kiln_evidence_endpoint():
    k = client.get("/api/regions/dhaka-kilns/kilns")
    assert k.status_code == 200 and k.json()["inventory"]["license"] and k.json()["firms"]["mapped_kilns"]["n"] > 0
    assert "caveat" in k.json() and len(k.json()["kilns"]) == k.json()["inventory"]["n_in_area"]
    assert client.get("/api/regions/punjab/kilns").status_code == 404          # only the Dhaka belt has an inventory
    assert client.get("/api/regions/nowhere/kilns").status_code == 404


def test_feedback_stored_and_refused_when_read_only():
    import tempfile
    from kw import feedback
    assert client.post("/api/feedback", json={"message": "a real question here"}).status_code == 503  # read-only copy
    real_path, tools.SERVERLESS = feedback.PATH, False
    feedback.PATH = Path(tempfile.mkdtemp()) / "fb.jsonl"
    try:
        r = client.post("/api/feedback", json={"kind": "question", "message": "does the Aqua scale hold for peat?"},
                        headers={"x-forwarded-for": "203.0.113.9"})
        assert r.status_code == 200 and r.json()["stored"] and feedback.PATH.exists(), r.text
        assert client.post("/api/feedback", json={"message": "short"}).status_code == 400
    finally:
        feedback.PATH, tools.SERVERLESS = real_path, True


def test_export_columns_formats_and_old_csv_unchanged():
    full = client.get("/api/regions/punjab/export.csv?granularity=month").text      # the original endpoint, all columns
    cols = full.split("\n# ")[-1].split("\n")[1].split(",")
    assert cols[:3] == ["period", "partial", "provisional"] and cols[-1] == "nrt_share", cols[:3]
    r = client.get("/api/regions/punjab/export", params={"columns": "hotspots", "start": "2020", "end": "2021", "comments": "false"})
    lines = r.text.strip().split("\n")
    assert lines[0] == "period,hotspots_aqua_scale,ci95_lo,ci95_hi" and lines[1].startswith("2020-01") and lines[-1].startswith("2021-12"), lines[:2]
    j = client.get("/api/regions/punjab/export", params={"format": "json", "columns": "period,percentile", "granularity": "week"}).json()
    assert j["columns"] == ["period", "percentile"] and "provenance" in j and j["rows"][0].keys() == {"period", "percentile"}
    assert client.get("/api/regions/punjab/export", params={"columns": "nope"}).status_code == 400
    assert client.get("/api/regions/punjab/export", params={"format": "xml"}).status_code == 400
    assert client.get("/api/regions/punjab/export", params={"kind": "detections"}).status_code == 400


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
