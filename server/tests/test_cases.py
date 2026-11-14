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


def test_near_match_neighbour_and_next_month():
    cells = [(10.0, 20.0), (10.1, 20.0)]
    look, per = {c: i for i, c in enumerate(cells)}, {"2020-01", "2020-02"}
    m = lambda gm: cases.near_match(gm, look, (10.0, 20.0), "2020-01", per)  # noqa: E731
    assert m({"2020-01": [[0, 4.0]]}) == ("cell", 4.0)
    assert m({"2020-01": [[1, 3.0]]}) == ("neighbour", 3.0)           # the event point sits one cell off the fire
    assert m({"2020-02": [[0, 2.0]]}) == ("cell_next_month", 2.0)     # the event started before the first hotspots
    assert m({}) == (None, 0)                                         # nothing near, nothing next month: the record missed it
    assert cases.next_period("2020-12") == "2021-01" and cases.next_period("2020-03") == "2020-04"


def test_burn_scar_counts_like_an_agency_record_and_gaps_are_reasons():
    assert cases.verdict("quiet", {}, None, None, None, {"km2": 5}) == "agency_only"
    assert cases.verdict("fire", {}, None, None, None, {"km2": 5}) == "corroborated"
    assert cases.verdict("abstain", {}, None, None, None, {"km2": 5}) == "abstained"
    u = cases.unavailable("2019-05", {"press": "rate-limited"})
    assert u["press"].startswith("the search failed") and "2021" in u["disaster_system"]
    assert cases.unavailable("2024-05", {}) == {}
    assert "2017" in cases.unavailable("2015-05", {})["press"] and "press" not in cases.unavailable("2015-05", {}, press_found=True)

    def case(period):
        return {"cell": [10.0, 20.0], "period": period, "verdict": "insufficient", "witnesses": {
            "satellite": {"state": "quiet"}, "cross_family": {}, "agency": None, "disaster_system": None, "press": None}}
    tab = {"through": "2020-12", "cells": {"10.0,20.0|2020-01": 7.5, "10.0,20.0|2020-02": 0}}
    out = cases.apply_burned({"cases": [case("2020-01"), case("2020-02"), case("2021-03"), case("2019-01")]}, tab)["cases"]
    assert out[0]["verdict"] == "agency_only" and out[0]["witnesses"]["burned_area"]["km2"] == 7.5
    assert out[1]["verdict"] == "insufficient" and out[1]["witnesses"]["burned_area"] is None and "burned_area" not in out[1]["witnesses"]["unavailable"]
    assert "published to 2020-12" in out[2]["witnesses"]["unavailable"]["burned_area"]      # beyond the product: could not look
    assert "did not cover" in out[3]["witnesses"]["unavailable"]["burned_area"]              # not queried: could not look, never "none"
    assert "not been run" in cases.apply_burned({"cases": [case("2020-01")]}, None)["cases"][0]["witnesses"]["unavailable"]["burned_area"]


def test_shipped_kiln_evidence():
    f = REGIONS / "dhaka-kilns" / "kilns.json"
    if not f.exists():
        return
    k = json.loads(f.read_text(encoding="utf-8"))
    assert k["inventory"]["n_on_labelled_kiln"] == sum(r[4] for r in k["kilns"]) and k["inventory"]["n_in_area"] == len(k["kilns"])
    assert all(len(r) == len(k["fields"]) for r in k["kilns"]) and all(len(r) == len(k["static_fields"]) for r in k["static_sources"])
    assert k["firms"]["static_sources"]["n"] == len(k["static_sources"])
    for g in ("mapped_kilns", "random_places"):
        assert 0 <= k["firms"][g]["viirs_any_pct"] <= 100 and 0 <= k["firms"][g]["modis_any_pct"] <= 100
    w, s, e, n = k["bbox"]
    assert all(w <= r[0] <= e and s <= r[1] <= n for r in k["kilns"])
    if k.get("radar"):   # one viewing geometry, both seasons observed, shares are shares
        r = k["radar"]
        assert r["scenes"]["kiln_season"] > 0 and r["scenes"]["monsoon"] > 0 and r["mapped_kilns"]["n"] > 0
        assert 0 <= r["mapped_kilns"]["rise_above_random_75th_pct"] <= 100 and "not proof" in r["note"]


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
            gaps = x["witnesses"].get("unavailable")
            assert isinstance(gaps, dict), (d.name, x["id"], "every case must say which witnesses could not look")
            if x["witnesses"]["press"] is None and x["period"] < cases.PRESS_FROM and "press" not in gaps:
                gn = next((s for s in c["sources"] if s["name"] == "Google News RSS"), None)   # it looked and found nothing: a real answer
                assert gn and gn["searched"] and not gn["error"], (d.name, x["id"], "no news before 2017 must be 'could not look', not 'none'")
            if x["period"] < cases.GDACS_FROM:
                assert "disaster_system" in gaps, (d.name, x["id"])
        assert len({x["id"] for x in c["cases"]}) == len(c["cases"]), d.name


def test_shipped_exposure_files():
    for d in sorted(p for p in REGIONS.iterdir() if (p / "exposure.json").exists()):
        ex, grid = (json.loads((d / f"{n}.json").read_text(encoding="utf-8")) for n in ("exposure", "grid"))
        n = len(ex["cells"])   # hospitals, schools and roads index exposure.json's own cell order
        coords = [tuple(e[:2]) for e in ex["cells"]]
        assert len(set(coords)) == n, f"{d.name}: duplicate exposure cells"
        # the runtime joins by coordinates (a live refresh may reorder grid.json); a shipped pair must cover the same cells
        assert set(coords) == {tuple(g) for g in grid["cells"]}, f"{d.name}: exposure and grid cover different cells"
        assert ex["totals"]["population"] == sum(c[2] for c in ex["cells"]) or abs(ex["totals"]["population"] - sum(c[2] for c in ex["cells"])) <= n
        assert ex["population"]["source"] and ex["caveat"] and (d / "exposure.json").stat().st_size <= 600 * 1024
        assert all(0 <= h[3] < n for h in ex["hospitals"]) and all(all(0 <= i < n for i in r[4]) for r in ex["roads"])
        assert ex["totals"]["hospitals"] is None or ex["totals"]["hospitals"] == sum(c[3] for c in ex["cells"])
        if "schools" in ex.get("cell_columns", []):
            assert ex["totals"]["schools"] is None or ex["totals"]["schools"] == sum(c[5] for c in ex["cells"]), d.name
        if "school_columns" in ex:      # named schools: each in a real cell, never more listed than counted there
            assert all(0 <= s[3] < n for s in ex["schools"]), d.name
            per = {}
            for s in ex["schools"]:
                per[s[3]] = per.get(s[3], 0) + 1
            assert all(k <= ex["cells"][ci][5] for ci, k in per.items()), f"{d.name}: more named schools than counted"
        if "cropland_km2" in ex.get("cell_columns", []) and "cropland" not in ex["infrastructure"].get("errors", {}):
            import math
            for c in ex["cells"]:   # cropland can never exceed the cell (0.1 degree, cosine of latitude), with rounding slack
                assert 0 <= c[6] <= (11.132 ** 2) * math.cos(math.radians(c[0] + 0.05)) + 0.1, f"{d.name}: cropland {c[6]} at {c[:2]}"
            assert ex["farmland"]["source"] and ex["farmland"]["note"]


def test_exposure_join_counts_only_fire_cells():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from kw import tools
    for d in sorted(p for p in REGIONS.iterdir() if (p / "exposure.json").exists())[:2]:
        grid = tools._aligned_grid(d.name)   # grid months on exposure.json cell indices
        ex = json.loads((d / "exposure.json").read_text(encoding="utf-8"))
        period = max(grid["months"], key=lambda k: len(grid["months"][k]))
        fire = {ci for ci, _ in grid["months"][period]}
        r = tools.exposure(d.name, period)
        assert r["fire_cells"] == len(fire) and r["population"] == sum(ex["cells"][i][2] for i in fire)
        assert r["hospitals"] == sum(ex["cells"][i][3] for i in fire)
        assert r["population"] <= tools.exposure(d.name)["population"]
        assert all(tuple(s["cell"]) in {tuple(grid["cells"][i]) for i in fire} for s in r.get("school_list", []))


def test_exposure_place():
    from kw import tools
    d = REGIONS / "dhaka-kilns"
    grid = tools._aligned_grid("dhaka-kilns")
    on = {}
    for rows in grid["months"].values():
        for ci, _ in rows:
            on[ci] = on.get(ci, 0) + 1
    ci = max(on, key=on.get)
    la, lo = grid["cells"][ci]
    p = tools.exposure_place("dhaka-kilns", la + 0.05, lo + 0.05)
    assert p["in_record"] and p["cell"] == [la, lo] and p["months_with_fire"] == on[ci]
    assert sum(m["years_with_fire"] for m in p["by_month"]) == on[ci]       # every month with fire falls in one calendar month
    assert all(m["years_with_fire"] <= m["record_years"] for m in p["by_month"])
    for bad in ((0, 0), ("x", 1)):
        try:
            tools.exposure_place("dhaka-kilns", *bad)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
