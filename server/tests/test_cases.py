"""Run: python server/tests/test_cases.py  — verdict logic, abstention, and the shipped cases.json / exposure.json files."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kw import cases  # noqa: E402

REGIONS = Path(__file__).resolve().parents[2] / "data" / "regions"
agency, press = {"source": "NASA EONET"}, {"source": "GDELT DOC", "count": 3}


def test_satellite_states():
    assert cases.satellite_state({"MODIS_A": 0.0}, None, False) == "abstain"
    assert cases.satellite_state({"MODIS_A": 1.0}, 12.0, True) == "fire"
    assert cases.satellite_state({"MODIS_A": 1.0}, None, False) == "quiet"
    assert cases.satellite_state({"MODIS_A": 0.0, "VIIRS_SNPP": 0.0}, 5.0, True) == "abstain"   # never a negative finding


def test_verdicts_all_six():
    f = cases.verdict
    assert f("fire", {}, agency, None, None) == "corroborated"
    assert f("fire", {}, None, {"source": "GDACS"}, None) == "corroborated"
    assert f("fire", {}, None, None, press) == "reported"
    assert f("fire", {}, None, None, None) == "satellite_only"
    assert f("quiet", {}, agency, None, None) == "agency_only"          # the reverse direction
    assert f("quiet", {}, None, None, press) == "reported"
    assert f("abstain", {}, agency, None, None) == "abstained"
    assert f("abstain", {}, None, None, None) == "abstained"            # an absent witness is never a finding
    assert f("quiet", {}, None, None, None) == "insufficient"


def test_cross_family_band():
    cov = {"MODIS_A": 1.0}
    assert cases.cross_family(100, 105, cov)["agrees"] is True
    assert cases.cross_family(100, 160, cov)["agrees"] is False
    assert cases.cross_family(None, 160, cov)["state"] == "abstain"
    assert cases.cross_family(100, 105, {"MODIS_A": 0.0})["state"] == "abstain"
    assert cases.cross_family(0, 0, cov)["state"] == "quiet"


def test_assemble_dedupes_by_cell_and_month_and_gets_agency_only():
    # a hand-built area: one cell with fire in 2020-01, none in 2020-02; EONET events in both months
    periods = ["2020-01", "2020-02"]
    z = [1.0, 1.0]
    monthly = {"periods": periods, "partial": [False, False], "coverage": {o: z for o in cases.OBSERVERS},
               "classes": {"veg": {"hotspots": {"v": [5.0, 0.0], "lo": [4, 0], "hi": [6, 0], "sensors": [["MODIS_A"], ["MODIS_A"]]},
                                   "history": {"pct": [90, None], "rank": [1, None], "n": [3, None]}, "aqua_only": [5.0, 0.0]}}}
    grid = {"cells": [[10.0, 20.0]], "months": {"2020-01": [[0, 5.0]]}}
    meta = {"bbox": [19.5, 9.5, 20.5, 10.5], "name": "Test"}
    ev = lambda i, d: {"id": f"EONET_{i}", "title": "fire", "start_date": d, "date": d, "lat": 10.05, "lon": 20.05}
    kept, counts, capped, total, found = cases.assemble("t", meta, monthly, grid, [ev(1, "2020-01-03"), ev(2, "2020-01-09"), ev(3, "2020-02-04")], [], None, None)
    by = {c["period"]: c for c in kept}
    assert len(kept) == 2 and total == 2 and not capped
    assert by["2020-01"]["verdict"] == "corroborated" and "2 NASA EONET" in by["2020-01"]["note"]
    assert by["2020-02"]["verdict"] == "agency_only"
    assert sum(counts.values()) == len(kept)


def test_shipped_case_files():
    for d in sorted(p for p in REGIONS.iterdir() if (p / "cases.json").exists()):
        c = json.loads((d / "cases.json").read_text(encoding="utf-8"))
        assert sum(c["counts"].values()) == len(c["cases"]), d.name
        assert set(c["counts"]) <= set(cases.VERDICTS)
        for x in c["cases"]:
            s = x["witnesses"]["satellite"]
            assert x["verdict"] in cases.VERDICTS and s["state"] in ("fire", "quiet", "abstain"), (d.name, x["id"])
            if s["state"] != "abstain":
                assert (s["coverage"] or 0) > 0, (d.name, x["id"], "a witness that could see must have coverage")
        assert len({x["id"] for x in c["cases"]}) == len(c["cases"]), d.name


def test_shipped_exposure_files():
    for d in sorted(p for p in REGIONS.iterdir() if (p / "exposure.json").exists()):
        ex, grid = (json.loads((d / f"{n}.json").read_text(encoding="utf-8")) for n in ("exposure", "grid"))
        n = len(grid["cells"])
        assert len(ex["cells"]) == n, d.name
        assert all(e[:2] == g for e, g in zip(ex["cells"], grid["cells"])), f"{d.name}: index-parallel rule broken"
        assert ex["totals"]["population"] == sum(c[2] for c in ex["cells"]) or abs(ex["totals"]["population"] - sum(c[2] for c in ex["cells"])) <= n
        assert ex["population"]["source"] and ex["caveat"] and (d / "exposure.json").stat().st_size <= 600 * 1024
        assert all(0 <= h[3] < n for h in ex["hospitals"]) and all(all(0 <= i < n for i in r[4]) for r in ex["roads"])
        assert ex["totals"]["hospitals"] is None or ex["totals"]["hospitals"] == sum(c[3] for c in ex["cells"])


def test_exposure_join_counts_only_fire_cells():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from kw import tools
    for d in sorted(p for p in REGIONS.iterdir() if (p / "exposure.json").exists())[:2]:
        grid = json.loads((d / "grid.json").read_text(encoding="utf-8"))
        ex = json.loads((d / "exposure.json").read_text(encoding="utf-8"))
        period = max(grid["months"], key=lambda k: len(grid["months"][k]))
        fire = {ci for ci, _ in grid["months"][period]}
        r = tools.exposure(d.name, period)
        assert r["fire_cells"] == len(fire) and r["population"] == sum(ex["cells"][i][2] for i in fire)
        assert r["hospitals"] == sum(ex["cells"][i][3] for i in fire)
        assert r["population"] <= tools.exposure(d.name)["population"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
