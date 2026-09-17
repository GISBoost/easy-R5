"""Scenario comparison. Pure Python — run: py -m pytest easy_r5/test/test_compare.py -v"""

import pytest

from easy_r5.core.compare import diff_row, method_mismatches, summarize


def test_diff_row_statuses():
    assert diff_row(10, 15) == (10.0, 15.0, 5.0, 50.0, "better")
    assert diff_row("10", "5")[4] == "worse"
    assert diff_row(3, 3)[4] == "same"
    assert diff_row(None, 4) == (0.0, 4.0, 4.0, None, "better")  # NULL = 0, pct undefined
    assert diff_row(7, None, in_b=False) == (7.0, None, None, None, "only_a")
    assert diff_row(None, 2, in_a=False) == (None, 2.0, None, None, "only_b")


def test_method_mismatches_split():
    a = {"percentile": ["50"], "decay": ["STEP"], "scenario": ["baseline"], "run_date": ["2026-08-24"]}
    b = {"percentile": ["85"], "decay": ["STEP"], "scenario": ["tram.json:abcd1234"],
         "run_date": ["2026-08-24"]}
    blocking, info = method_mismatches(a, b)
    assert blocking == [("percentile", ["50"], ["85"])]
    assert info == [("scenario", ["baseline"], ["tram.json:abcd1234"])]


def test_method_mismatches_ignores_one_sided_and_blanks():
    blocking, info = method_mismatches({"percentile": ["50", None]}, {"percentile": ["50"], "decay": ["X"]})
    assert blocking == [] and info == []


def test_summarize():
    rows = [diff_row(1, 2), diff_row(2, 1), diff_row(1, 1), diff_row(1, None, in_b=False)]
    s = summarize(rows)
    assert s["counts"] == {"better": 1, "worse": 1, "same": 1, "only_a": 1}
    assert s["sum_diff"] == 0 and s["mean_diff"] == pytest.approx(0)


def test_travel_time_null_means_unreachable():
    assert diff_row(30, 20, higher_is_better=False) == (30.0, 20.0, -10.0, pytest.approx(-33.333, abs=1e-3), "better")
    assert diff_row(20, 30, higher_is_better=False)[4] == "worse"
    assert diff_row(45, None, higher_is_better=False) == (45.0, None, None, None, "worse")
    assert diff_row(None, 45, higher_is_better=False) == (None, 45.0, None, None, "better")
    assert diff_row(None, None, higher_is_better=False)[4] == "same"


def test_join_key_normalises_numeric_ids():
    from easy_r5.core.compare import join_key
    assert join_key(12) == join_key(12.0) == join_key("12") == "12"
    assert join_key(None) is None and join_key(" ") is None
    assert join_key(1.5) == "1.5"


def test_run_parameters_are_strict():
    blocking, _ = method_mismatches({"max_rides": [2]}, {"max_rides": [4]})
    assert blocking == [("max_rides", ["2"], ["4"])]
