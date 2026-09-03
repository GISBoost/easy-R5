"""gtfs-dashboard manifest client. Pure Python (no qgis) —
run: py -m pytest easy_r5/test/test_gtfs_dashboard.py -v"""

import json
from pathlib import Path

import pytest

from easy_r5.core import gtfs_dashboard as gd

FIXTURE = Path(__file__).parent / "fixtures" / "manifest.json"


@pytest.fixture
def manifest():
    return gd.slim(json.loads(FIXTURE.read_text(encoding="utf-8")))


# --- slim ---------------------------------------------------------------

def test_slim_drops_extra_keys_keeps_assets(manifest):
    lodz = manifest["cities"]["lodz"]
    assert lodz["display_name"] == "Łódź"
    day = lodz["days"][0]
    assert set(day) == {"date", "status", "assets"}
    assert set(day["assets"]) == {"p50", "p85", "static_gtfs"}   # diff_chart etc. dropped


def test_slim_is_idempotent(manifest):
    assert gd.slim(manifest) == manifest


def test_slim_rejects_empty():
    with pytest.raises(gd.ManifestError):
        gd.slim({"cities": {}})
    with pytest.raises(gd.ManifestError):
        gd.slim({"generated_at": "x"})


# --- navigation -------------------------------------------------------

def test_cities_sorted_by_display_name(manifest):
    got = gd.cities(manifest)
    assert ("lodz", "Łódź") in got
    assert got == sorted(got, key=lambda t: t[1].lower())


def test_months_newest_first(manifest):
    assert gd.months(manifest, "lodz") == ["2026-07"]


def test_days_newest_first(manifest):
    ds = gd.days(manifest, "lodz", "2026-07")
    dates = [d["date"] for d in ds]
    assert dates == sorted(dates, reverse=True)
    assert "2026-07-13" in dates


def test_unknown_city_lists_available(manifest):
    with pytest.raises(gd.ManifestError, match="poznan"):
        gd.months(manifest, "atlantis")


# --- resolve_asset ---------------------------------------------------

def test_resolve_asset_happy(manifest):
    url = gd.resolve_asset(manifest, "lodz", "2026-07-13", "p50")
    assert url.startswith("https://github.com/GISBoost/easy-GTFS-RT/releases/download/")
    assert url.endswith("_p50.zip")


def test_resolve_asset_bad_date_format(manifest):
    with pytest.raises(gd.ManifestError, match="yyyy-MM-dd"):
        gd.resolve_asset(manifest, "lodz", "13-07-2026", "p50")


def test_resolve_asset_missing_date_suggests_nearest(manifest):
    with pytest.raises(gd.ManifestError, match="Nearest"):
        gd.resolve_asset(manifest, "lodz", "2026-07-01", "p50")


def test_resolve_asset_missing_variant(manifest, monkeypatch):
    # null out p85 for one day, then ask for it
    day = manifest["cities"]["lodz"]["days"][0]
    day["assets"]["p85"] = None
    with pytest.raises(gd.ManifestError, match="Available: p50, static_gtfs"):
        gd.resolve_asset(manifest, "lodz", day["date"], "p85")


def test_resolve_asset_unknown_variant(manifest):
    with pytest.raises(gd.ManifestError, match="Unknown variant"):
        gd.resolve_asset(manifest, "lodz", "2026-07-13", "p99")


def test_day_status(manifest):
    assert gd.day_status(manifest, "lodz", "2026-07-13") == "partial"


# --- zip GTFS sanity check ----------------------------------------

def _gtfs_zip(path, files, prefix=""):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for f in files:
            z.writestr(prefix + f, "header\n")
    return path


def test_zip_is_gtfs_complete(tmp_path):
    z = _gtfs_zip(tmp_path / "f.zip", ["agency.txt", "stops.txt", "routes.txt",
                                       "trips.txt", "stop_times.txt", "calendar.txt"])
    assert gd.zip_is_gtfs(z)
    assert gd.zip_missing_gtfs(z) == []


def test_zip_is_gtfs_nested_top_dir(tmp_path):
    z = _gtfs_zip(tmp_path / "f.zip", ["agency.txt", "stops.txt", "routes.txt",
                                       "trips.txt", "stop_times.txt", "calendar_dates.txt"],
                  prefix="lodz_realized_2026-07-13/")
    assert gd.zip_is_gtfs(z)   # matched by basename regardless of nesting


def test_zip_missing_stop_times(tmp_path):
    z = _gtfs_zip(tmp_path / "f.zip", ["agency.txt", "stops.txt", "routes.txt",
                                       "trips.txt", "calendar.txt"])
    assert not gd.zip_is_gtfs(z)
    assert "stop_times.txt" in gd.zip_missing_gtfs(z)


def test_zip_no_calendar(tmp_path):
    z = _gtfs_zip(tmp_path / "f.zip", ["agency.txt", "stops.txt", "routes.txt",
                                       "trips.txt", "stop_times.txt"])
    assert any("calendar" in m for m in gd.zip_missing_gtfs(z))


def test_zip_not_a_zip(tmp_path):
    bad = tmp_path / "f.zip"
    bad.write_text("<html>404</html>", encoding="utf-8")
    assert not gd.zip_is_gtfs(bad)


# --- fetch_manifest ------------------------------------------------

def test_fetch_manifest_from_file_url(tmp_path):
    gd._MEMO.update(data=None, at=0.0, url=None)
    data = gd.fetch_manifest(url=FIXTURE.as_uri(), cache_dir=tmp_path)
    assert "lodz" in data["cities"]
    assert (tmp_path / gd.CACHE_FILENAME).is_file()   # cached to disk


def test_fetch_manifest_falls_back_to_stale_cache(tmp_path):
    gd._MEMO.update(data=None, at=0.0, url=None)
    (tmp_path / gd.CACHE_FILENAME).write_text(
        json.dumps({"generated_at": "old", "cities": {"x": {"display_name": "X", "days": []}}}),
        encoding="utf-8",
    )
    data = gd.fetch_manifest(url="http://127.0.0.1:1/nope.json", cache_dir=tmp_path)
    assert data["_stale"] is True
    assert "x" in data["cities"]


def test_fetch_manifest_no_cache_raises(tmp_path):
    gd._MEMO.update(data=None, at=0.0, url=None)
    with pytest.raises(gd.ManifestError, match="easy-GTFS-RT/releases"):
        gd.fetch_manifest(url="http://127.0.0.1:1/nope.json", cache_dir=tmp_path)
