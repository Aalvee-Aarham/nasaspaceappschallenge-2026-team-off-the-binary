"""Run: python server/tests/test_data_integrity.py  — the committed region data is self-consistent (stdlib only)."""
import json
from pathlib import Path

REGIONS = Path(__file__).resolve().parents[2] / "data" / "regions"
FILES = ("meta.json", "monthly.json", "weekly.json", "grid.json", "static.json")


def test_index_entries_exist():
    missing = [r["id"] for r in json.loads((REGIONS / "index.json").read_text(encoding="utf-8"))["regions"]
               if not (REGIONS / r["id"] / "meta.json").exists()]
    assert not missing, f"index.json lists areas that are not in the repo: {missing}"


def test_presets_have_all_files():
    presets = [r["id"] for r in json.loads((REGIONS / "index.json").read_text(encoding="utf-8"))["regions"] if r.get("preset")]
    assert presets, "no preset areas in index.json"
    gaps = [f"{p}/{f}" for p in presets for f in FILES if not (REGIONS / p / f).exists()]
    assert not gaps, f"missing files: {gaps}"


def test_presets_have_transfer_validation():
    presets = [r["id"] for r in json.loads((REGIONS / "index.json").read_text(encoding="utf-8"))["regions"] if r.get("preset")]
    empty = [p for p in presets if json.loads((REGIONS / p / "meta.json").read_text(encoding="utf-8")).get("transfer_validation") is None]
    assert not empty, f"transfer_validation is null in: {empty} (run: cd server && python -m kw.build --transfer-only)"


def test_map_cells_reconcile_with_the_calendar():
    """The map cells of a month must add up to that month's calendar value.

    The cells use the area's sensor weights, so the two agree by construction; what is left is rounding.
    """
    for d in sorted(p for p in REGIONS.iterdir() if (p / "grid.json").exists()):
        monthly, grid = (json.loads((d / f"{n}.json").read_text(encoding="utf-8")) for n in ("monthly", "grid"))
        values = monthly["classes"]["veg"]["hotspots"]["v"]
        for i, period in enumerate(monthly["periods"]):
            rows = grid["months"].get(period)
            if not rows or values[i] is None:
                continue
            total = sum(v for _, v in rows)
            assert abs(total - values[i]) <= 0.01 + 0.001 * abs(values[i]), f"{d.name} {period}: {total} vs {values[i]}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
