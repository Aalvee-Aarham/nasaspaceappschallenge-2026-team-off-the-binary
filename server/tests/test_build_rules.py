"""Run: python server/tests/test_build_rules.py  — build and service rules (needs the server venv: duckdb)."""
import ast
import copy
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kw import build, tools  # noqa: E402,F401

KW = Path(__file__).resolve().parents[1] / "kw"


def test_no_duplicate_keys_in_dict_literals():
    """A repeated key in a dict literal silently drops the first value (it hid provenance.source)."""
    dups = []
    for f in sorted(KW.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                dups += [f"{f.name}:{node.lineno} {k!r}" for k in set(keys) if keys.count(k) > 1]
    assert not dups, dups


def test_next_weeks_start_after_last_complete_week():
    """Same anchor as the season card (build._season uses the last complete week)."""
    periods = [f"{y}-W{w:02d}" for y in range(2010, 2021) for w in range(1, 53)] + [f"2021-W{w:02d}" for w in range(1, 11)]
    partial = [False] * (len(periods) - 1) + [True]  # 2021-W10 is still in progress
    b = {"periods": periods, "partial": partial, "classes": {"veg": {"hotspots": {"v": [1.0] * len(periods)}}}}
    assert tools._next_weeks(b)["weeks"] == ["W10", "W11", "W12", "W13"]


def test_sensor_status_note_has_no_hard_coded_dates():
    """Sensor availability is measured from data, never stated as a fixed date (project guardrail)."""
    note = tools.sensor_status()["note"]
    assert not re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", note), note


def test_region_summary_without_snpp_validation_row():
    real = tools._read

    def no_snpp(rid, name):
        d = copy.deepcopy(real(rid, name))  # _read is cached: never mutate its result
        if name == "meta":
            d["validation"]["veg_det_D"] = [v for v in d["validation"]["veg_det_D"] if v["sensor"] != "VIIRS_SNPP"]
        return d
    tools._read = no_snpp
    try:
        assert tools.region_summary("punjab")["id"] == "punjab"
    finally:
        tools._read = real


def test_news_outage_is_not_read_as_no_reports():
    """Missing news is not evidence of absence: if no source answered, say so."""
    from kw.news import assess
    r = assess({"percentile": 95}, 0, [{"name": "GDELT", "searched": True, "error": "HTTP 500"}])
    assert "no source answered" in r["label"] and r["tone"] == "neutral", r["label"]
    ok = assess({"percentile": 95}, 0, [{"name": "GDELT", "searched": True, "error": None}])
    assert "no matching reports found" in ok["label"]


def test_analyst_find_place_matches_its_schema():
    """The analyst's find_place promises the built areas overlapping the place, like the MCP tool."""
    from kw import agent, news_more
    real = news_more.geocode
    news_more.geocode = lambda q: {"query": q, "center": [75.0, 31.0], "bbox": [74.0, 30.0, 76.0, 32.0]}
    try:
        r = agent._RUN["find_place"]({"query": "Ludhiana"})
        assert r["found"] is True and "punjab" in [a["id"] for a in r["built_areas_overlapping"]], r
    finally:
        news_more.geocode = real


def test_code_version_marks_uncommitted_builds():
    """Published numbers must be traceable: a build from a dirty tree must not claim a clean commit."""
    want = subprocess.check_output(["git", "describe", "--always", "--dirty"], cwd=KW, text=True).strip()
    assert build._code_version() == want, (build._code_version(), want)


def test_first_incomplete_iso_week_is_partial():
    import datetime as dt
    class Con:
        def execute(self, _sql):
            return type("Rows", (), {"fetchall": lambda self: [("MODIS_T", "2000-W44", 5)]})()
    cov, partial = build._coverage(Con(), ["2000-W44"], True, dt.date(2000, 11, 5), first=dt.date(2000, 11, 1))
    assert cov["MODIS_T"] == [1.0]  # every available day was observed…
    assert partial == [True]        # …but the ISO week still began before the archive


def test_seasonal_sen_slope_is_median_of_season_slopes():
    seasons = [[(2000, 0.0), (2001, 50.0), (2002, 100.0)], [(2000, 10.0), (2001, 20.0)]]
    r = build.sc.seasonal_mann_kendall(seasons)
    assert r["sen_per_year"] == 30.0, r  # median(50, 10), not the pooled median 50
    assert r["sen_per_year_pooled"] == 50.0, r


def test_uncalibrated_chain_has_zero_calibration_variance():
    fits = {"MODIS_T": {"beta": [2.0] * 12, "pooled": 2.0, "sigma2": 0.2},
            "VIIRS_SNPP": {"beta": [3.0] * 12, "pooled": 3.0, "sigma2": 0.3},
            "VIIRS_NOAA20": {"beta": [1.5] * 12, "pooled": 1.5, "sigma2": 0.1},
            "VIIRS_NOAA21": {"beta": [1.2] * 12, "pooled": 1.2, "sigma2": 0.1}}
    to_ref = build._chain(fits, key="none")
    assert all(b == [1.0] * 12 for k, (b, _variance) in to_ref.items() if k != "MODIS_A")
    assert all(variance == 0.0 for _b, variance in to_ref.values())


def test_aggregate_keeps_nrt_unclassified_counts():
    import duckdb
    con = duckdb.connect()
    con.execute("""CREATE TABLE dall (cls VARCHAR, obs VARCHAR, daynight VARCHAR, n INTEGER,
                    frp DOUBLE, quality VARCHAR, unclassified INTEGER, acq_date DATE, gy INTEGER, gx INTEGER,
                    sensor VARCHAR)""")
    con.execute("""INSERT INTO dall VALUES
                    ('veg','VIIRS_SNPP','D',4,10,'nrt',3,'2020-01-01',1,1,'VIIRS_SNPP'),
                    ('veg','MODIS_A','D',2,5,'6.03',0,'2020-01-01',1,1,'MODIS')""")
    con.execute("CREATE VIEW d AS SELECT * FROM dall")
    agg = build._aggregate(con, False)
    assert agg[("veg", "VIIRS_SNPP", "2020-01")]["unclassified"] == 3
    assert agg[("veg", "MODIS_A", "2020-01")]["unclassified"] == 0


def test_grid_cells_use_area_weights_and_reconcile_with_total():
    class Con:
        def execute(self, _sql):
            rows = [("2020-01", 0, 0, "MODIS_A", "D", 0),
                    ("2020-01", 0, 0, "VIIRS_SNPP", "D", 20),
                    ("2020-01", 0, 1, "MODIS_A", "D", 10),
                    ("2020-01", 0, 1, "VIIRS_SNPP", "D", 0)]
            return type("Rows", (), {"fetchall": lambda self: rows})()
    agg = {("veg", "MODIS_A", "2020-01"): {"det_D": 10},
           ("veg", "VIIRS_SNPP", "2020-01"): {"det_D": 20}}
    ref = {"MODIS_A": ([1.0] * 12, 0.0), "VIIRS_SNPP": ([1.0] * 12, 0.0)}
    cals = {"veg": {"det_D": {"to_ref": ref}, "det_N": {"to_ref": ref}}}
    cov = {s: [1.0 if s in ("MODIS_A", "VIIRS_SNPP") else 0.0] for s in build.OBSERVERS}
    grid = build._grid(Con(), ["2020-01"], cov, cals)
    vals = [v for _ci, v in grid["months"]["2020-01"]]
    assert abs(sum(vals) - 15.0) < 1e-9, grid


def test_drift_uses_same_months_every_year():
    keys = [f"{y}-{m:02d}" for y in (2020, 2021) for m in range(1, 13)]
    sats = ("MODIS_A", "VIIRS_SNPP", "MODIS_T", "VIIRS_NOAA20")
    cov = {s: [1.0] * 24 for s in sats}
    for i in range(18, 24):  # 2021 Jul-Dec not observed
        cov["MODIS_A"][i] = 0.0
    # ratio 0.1 in Jan-Jun and 0.5 in Jul-Dec, identical in both years
    a = [10.0 if (i % 12) < 6 else 50.0 for i in range(24)]
    raw = {s: {"det": [100.0] * 24} for s in sats}
    raw["MODIS_A"]["det"] = a
    out = build._drift({"coverage": cov, "raw": raw}, keys)["MODIS_A/VIIRS_SNPP"]
    assert out == [[2020, 0.1], [2021, 0.1]], out   # old code: 2020 -> 0.3, 2021 -> 0.1 (a fake 'drift')


def test_active_before_and_after_drift():
    cov = {s: [1.0] for s in build.OBSERVERS}
    build.AQUA_DRIFT_FROM = "2023-01"
    try:
        assert "MODIS_A" in build._active(cov, 0, key="2022-12")
        assert "MODIS_A" not in build._active(cov, 0, key="2023-01")
        assert "MODIS_A" not in build._active(cov, 0, key="2023-W02")
        assert build._active(cov, 0, set(build.MODIS_SATS), "2024-05") == ["MODIS_A"]   # aqua_only view keeps Aqua
        no_viirs = {**cov, **{s: [0.0] for s in build.VIIRS}}
        assert build._active(no_viirs, 0, key="2024-05") == ["MODIS_A"]               # nothing else observes
    finally:
        build.AQUA_DRIFT_FROM = None


def test_active_without_onset_is_unchanged():
    cov = {s: [1.0] for s in build.OBSERVERS}
    assert build._active(cov, 0, key="2026-01")[0] == "MODIS_A"


def test_aqua_overpass_onset_is_earlier_of_orbit_and_version():
    import duckdb
    tmp = Path(tempfile.mkdtemp())
    (tmp / "cache" / "x").mkdir(parents=True)
    # 150 Aqua day detections per year at lon 0: 13:30 UTC = 13:30 local until 2022, 15:00 from 2023.
    # Archive version 6.03 until 2022-05, 61.03 from 2022-06; an NRT version from 2021 must be ignored.
    duckdb.connect().execute(f"""COPY (
        SELECT make_timestamp(y, m, 15, CASE WHEN y >= 2023 THEN 15 ELSE 13 END, CASE WHEN y >= 2023 THEN 0 ELSE 30 END, 0) AS acq_datetime,
               0.0 AS lon, 'MODIS' AS sensor, 'Aqua' AS satellite, 'D' AS daynight,
               CASE WHEN y = 2021 AND m = 3 THEN '6.1NRT' WHEN y * 100 + m >= 202206 THEN '61.03' ELSE '6.03' END AS version
        FROM range(2003, 2025) t(y), range(1, 13) u(m), range(0, 13) v(k)
    ) TO '{(tmp / "cache" / "x" / "all.parquet").as_posix()}' (FORMAT parquet)""")
    real = build.CACHE, build.AQUA_FILE
    build.CACHE, build.AQUA_FILE = tmp / "cache", tmp / "aqua_overpass.json"
    try:
        out = build.aqua_overpass(["x"])
        assert out["orbit_onset"] == "2023-01", out
        assert out["version_change"] == {"version": "61.03", "from": "2022-06"}, out["version_change"]
        assert out["onset"] == "2022-06" and build.AQUA_FILE.exists()
        assert abs(out["baseline_hour"] - 13.5) < 1e-6
    finally:
        build.CACHE, build.AQUA_FILE = real


def test_builds_read_the_onset_from_the_shared_file():
    """Background single-area rebuilds never run main(), so they must read the onset from aqua_overpass.json."""
    import json
    real = build.AQUA_FILE
    build.AQUA_FILE = Path(tempfile.mkdtemp()) / "aqua_overpass.json"
    try:
        assert build._load_aqua_onset() is None and build.AQUA_DRIFT_FROM is None   # no file: no rule
        build.AQUA_FILE.write_text(json.dumps({"onset": "2023-01"}), encoding="utf-8")
        assert build._load_aqua_onset() == "2023-01" and build.AQUA_DRIFT_FROM == "2023-01"
    finally:
        build.AQUA_FILE, build.AQUA_DRIFT_FROM = real, None


def _flat_cals():
    one = {s: ([1.0] * 12, 0.0) for s in build.OBSERVERS}
    return {"veg": {"det_D": {"to_ref": one}, "det_N": {"to_ref": one}}}


def _daily(first, last, per_day):
    import datetime as dt
    rows, days, d = [], [], dt.date(first, 1, 1)
    while d <= dt.date(last, 12, 31):
        rows.append((d, "MODIS_A", "D", per_day(d)))
        days.append(("MODIS_A", d))
        d += dt.timedelta(days=1)
    return rows, days


def test_month_to_date_counts_days_1_to_D_only():
    daily = _daily(2020, 2021, lambda d: 5 if d.year == 2020 else 2)
    keys, v, _ = build._month_to_date(daily, 3, 10, [2020, 2021], _flat_cals(), 1.0)
    assert keys == ["2020-03", "2021-03"] and v == [50.0, 20.0], v


def test_warning_backtest_flags_the_spike_month_only():
    spike = lambda d: 100 if (d.year, d.month) == (2015, 3) else 10  # noqa: E731
    daily = _daily(2000, 2020, spike)
    periods = [f"{y}-{m:02d}" for y in range(2000, 2021) for m in range(1, 13)]
    # full-month totals at a fixed 30 days, so leap-year Februaries do not look like extreme months
    vals = [float(spike(__import__("datetime").date(int(k[:4]), int(k[5:]), 1)) * 30) for k in periods]
    monthly = {"periods": periods, "partial": [False] * len(periods), "classes": {"veg": {"hotspots": {"v": vals}}}}
    r = build._warning_backtest(daily, monthly, _flat_cals(), 1.0, 2020)
    e = r["by_day"]["10"]["elevated"]
    assert r["scored"] and (e["hits"], e["misses"], e["false_alarms"]) == (1, 0, 0), e
    quiet = {**monthly, "classes": {"veg": {"hotspots": {"v": [1.0] * len(periods)}}}}
    assert build._warning_backtest(daily, quiet, _flat_cals(), 1.0, 2020)["scored"] is False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
