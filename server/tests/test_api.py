"""Run: python server/tests/test_api.py  — HTTP-level checks (needs the server venv)."""
import os
import sys
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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
