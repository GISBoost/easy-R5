"""Job spec validation. Pure Python — run: py -m pytest easy_r5/test/test_job_spec.py -v"""

import json

import pytest

from easy_r5.core.job_spec import (
    JobSpecError,
    build_build_job,
    build_info_job,
    build_matrix_job,
    parse_percentiles,
    validate_percentiles,
    write_job,
)


def _matrix_kwargs(**overrides):
    base = dict(
        network="C:/c/k/network.dat",
        origins_csv="C:/t/origins.csv",
        destinations_csv="C:/t/destinations.csv",
        origin_range=[0, 500],
        date="2026-08-25",
        departure_time="07:00",
        time_window_minutes=120,
        percentiles=[50],
        max_trip_duration_minutes=90,
        max_walk_time_minutes=None,
        walk_speed_kmh=3.6,
        bike_speed_kmh=12.0,
        max_rides=3,
        monte_carlo_draws=5,
        access_modes=["WALK"],
        egress_modes=["WALK"],
        direct_modes=["WALK"],
        transit_modes=["TRAM", "BUS"],
        write_unreachable=False,
        out_csv="C:/t/matrix_000.csv",
    )
    base.update(overrides)
    return base


def test_percentiles_ok_single():
    assert validate_percentiles([50]) == [50]


def test_percentiles_ok_five():
    assert validate_percentiles([10, 25, 50, 75, 90]) == [10, 25, 50, 75, 90]


def test_percentiles_six_raises():
    with pytest.raises(JobSpecError, match="at most 5"):
        validate_percentiles([10, 25, 50, 75, 85, 95])


def test_percentiles_not_ascending_raises():
    with pytest.raises(JobSpecError, match="ascending"):
        validate_percentiles([50, 25])


def test_percentiles_equal_not_strict_raises():
    with pytest.raises(JobSpecError, match="ascending"):
        validate_percentiles([50, 50])


@pytest.mark.parametrize("bad", [[0], [100], [-1]])
def test_percentiles_out_of_range_raises(bad):
    with pytest.raises(JobSpecError, match="range"):
        validate_percentiles(bad)


def test_percentiles_bool_rejected():
    with pytest.raises(JobSpecError):
        validate_percentiles([True])


def test_parse_percentiles_string():
    assert parse_percentiles("25, 50 ,75") == [25, 50, 75]


def test_parse_percentiles_rejects_duplicates():
    with pytest.raises(JobSpecError):
        parse_percentiles("25,50,50")


def test_parse_percentiles_rejects_words():
    with pytest.raises(JobSpecError):
        parse_percentiles("median")


def test_build_info_job():
    assert build_info_job("C:/x/network.dat") == {
        "command": "info",
        "network": "C:/x/network.dat",
    }


def test_build_info_job_empty_raises():
    with pytest.raises(JobSpecError):
        build_info_job("  ")


def test_build_build_job():
    job = build_build_job(
        "C:/d/city.osm.pbf", ["C:/d/a.zip", "C:/d/b.zip"],
        "C:/c/k/network.dat", "C:/c/k/network.json",
    )
    assert job == {
        "command": "build",
        "osm": "C:/d/city.osm.pbf",
        "gtfs": ["C:/d/a.zip", "C:/d/b.zip"],
        "out_network": "C:/c/k/network.dat",
        "out_summary": "C:/c/k/network.json",
    }


@pytest.mark.parametrize("args", [
    ("", ["a.zip"], "n.dat", "n.json"),
    ("o.pbf", [], "n.dat", "n.json"),
    ("o.pbf", ["a.zip"], "", "n.json"),
    ("o.pbf", ["a.zip"], "n.dat", ""),
])
def test_build_build_job_missing_raises(args):
    with pytest.raises(JobSpecError):
        build_build_job(*args)


def test_matrix_job_shape():
    job = build_matrix_job(**_matrix_kwargs(max_walk_time_minutes=45))
    assert job["command"] == "matrix"
    assert job["origin_range"] == [0, 500]
    assert job["percentiles"] == [50]
    assert job["max_walk_time_minutes"] == 45
    assert job["transit_modes"] == ["TRAM", "BUS"]


@pytest.mark.parametrize("walk", [None, "", 0, -5])
def test_matrix_job_walk_time_always_numeric(walk):
    """PRD 2.1 lesson 2 + M3 acceptance: the job never carries a null walk cap."""
    job = build_matrix_job(**_matrix_kwargs(max_walk_time_minutes=walk, max_trip_duration_minutes=90))
    assert isinstance(job["max_walk_time_minutes"], int)
    assert job["max_walk_time_minutes"] == 90


def test_matrix_job_six_percentiles_raises():
    with pytest.raises(JobSpecError, match="at most 5"):
        build_matrix_job(**_matrix_kwargs(percentiles=[10, 25, 50, 75, 85, 95]))


@pytest.mark.parametrize("overrides", [
    {"network": ""},
    {"origins_csv": ""},
    {"destinations_csv": " "},
    {"out_csv": ""},
    {"direct_modes": []},
])
def test_matrix_job_missing_raises(overrides):
    with pytest.raises(JobSpecError):
        build_matrix_job(**_matrix_kwargs(**overrides))


def test_matrix_job_modes_uppercased():
    job = build_matrix_job(**_matrix_kwargs(direct_modes=["walk"], transit_modes=["bus"]))
    assert job["direct_modes"] == ["WALK"]
    assert job["transit_modes"] == ["BUS"]


def test_write_job_roundtrip(tmp_path):
    job = {"command": "info", "network": "C:/x/network.dat"}
    path = write_job(job, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == job
    assert path.parent == tmp_path
