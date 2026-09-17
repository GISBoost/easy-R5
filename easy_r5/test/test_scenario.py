"""Scenario file building/reading. Pure Python — run: py -m pytest easy_r5/test/test_scenario.py -v"""

import json

import pytest

from easy_r5.core.scenario import (
    ScenarioError,
    build_scenario,
    haversine_m,
    line_to_add_trips,
    load_scenario,
    parse_route_list,
    scenario_label,
)


def test_haversine_one_degree_latitude():
    assert haversine_m(19.0, 51.0, 19.0, 52.0) == pytest.approx(111195, rel=1e-3)


def test_line_hop_times_from_speed():
    # ~1112 m apart at 40 km/h -> ~100 s
    mod = line_to_add_trips([(19.45, 51.75), (19.45, 51.76)], mode="TRAM", speed_kmh=40,
                            dwell_seconds=20, headway_minutes=5, start="06:00", end="22:00")
    assert mod["type"] == "add-trips" and mod["mode"] == 0
    tt = mod["frequencies"][0]
    assert tt["hopTimes"] == [100]
    assert tt["dwellTimes"] == [20, 20]
    assert tt["headwaySecs"] == 300 and tt["startTime"] == 21600 and tt["endTime"] == 79200
    assert all(tt[d] for d in ("monday", "sunday"))
    # R5 rejects new stops that also carry an id/name (spike 2026-09-17).
    assert mod["stops"] == [{"lon": 19.45, "lat": 51.75}, {"lon": 19.45, "lat": 51.76}]


def test_line_merges_duplicate_vertices_and_needs_two():
    mod = line_to_add_trips([(19.0, 51.0), (19.0, 51.0), (19.0, 51.01)])
    assert len(mod["stops"]) == 2
    with pytest.raises(ScenarioError, match="two distinct"):
        line_to_add_trips([(19.0, 51.0), (19.0, 51.0)])


@pytest.mark.parametrize("kw", [{"speed_kmh": 0}, {"headway_minutes": 0}, {"start": "22:00", "end": "06:00"},
                                {"mode": "BLIMP"}, {"start": "7am"}])
def test_line_bad_params(kw):
    with pytest.raises(ScenarioError):
        line_to_add_trips([(19.0, 51.0), (19.0, 51.01)], **kw)


def test_parse_route_list():
    assert parse_route_list(" 86, Z2  14;86 ") == ["86", "Z2", "14"]
    assert parse_route_list(None) == []


def test_build_scenario_all_parts():
    line = line_to_add_trips([(19.0, 51.0), (19.0, 51.01)])
    sc = build_scenario(new_lines=[line], remove_routes=["86"], speed_routes=["1"], speed_scale=0.8,
                        headway_routes=["14"], headway_minutes=4)
    assert [m["type"] for m in sc["modifications"]] == [
        "add-trips", "easy-remove-routes", "easy-adjust-speed", "easy-set-headway"]
    assert sc["modifications"][3]["headway_minutes"] == 4.0


def test_build_scenario_empty_or_bad():
    with pytest.raises(ScenarioError, match="no modifications"):
        build_scenario()
    with pytest.raises(ScenarioError):
        build_scenario(speed_routes=["1"], speed_scale=0)
    with pytest.raises(ScenarioError):
        build_scenario(headway_routes=["1"], headway_start="10:00", headway_end="09:00")


def test_load_scenario_roundtrip_and_label(tmp_path):
    p = tmp_path / "a.scenario.json"
    p.write_text(json.dumps(build_scenario(remove_routes=["86"])), encoding="utf-8")
    assert load_scenario(p)["modifications"][0]["routes"] == ["86"]
    label = scenario_label(p)
    assert label.startswith("a.scenario.json:") and len(label.split(":")[1]) == 8


@pytest.mark.parametrize("content", ["not json", "[]", '{"modifications": []}',
                                     '{"modifications": [{"type": "teleport"}]}'])
def test_load_scenario_rejects(tmp_path, content):
    p = tmp_path / "bad.json"
    p.write_text(content, encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(p)
