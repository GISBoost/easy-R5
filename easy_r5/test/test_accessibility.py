"""Cumulative-opportunity accessibility. Pure Python —
run: py -m pytest easy_r5/test/test_accessibility.py -v"""

import pytest

from easy_r5.core.accessibility import (
    EXPONENTIAL,
    LOGISTIC,
    STEP,
    compute_accessibility,
    decay_weight,
)


def test_step_weight_at_and_across_boundary():
    # R5 StepDecayFunction is strict: travelTime < cutoff
    assert decay_weight(STEP, 29, 30) == 1.0
    assert decay_weight(STEP, 30, 30) == 0.0   # exactly at the cutoff does NOT count
    assert decay_weight(STEP, 31, 30) == 0.0
    assert decay_weight(STEP, 0, 30) == 1.0


def test_step_weight_unreachable():
    assert decay_weight(STEP, None, 30) == 0.0


def test_exponential_half_at_cutoff():
    assert decay_weight(EXPONENTIAL, 30, 30) == pytest.approx(0.5)
    assert decay_weight(EXPONENTIAL, 0, 30) == pytest.approx(1.0)


def test_logistic_half_at_cutoff_and_monotone():
    assert decay_weight(LOGISTIC, 30, 30) == pytest.approx(0.5)
    assert decay_weight(LOGISTIC, 20, 30) > decay_weight(LOGISTIC, 40, 30)


def _matrix(tmp_path, rows, header="from_id,to_id,travel_time_p50"):
    p = tmp_path / "m.csv"
    p.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


def test_step_boundary_row_counts(tmp_path):
    m = _matrix(tmp_path, ["o1,d1,29", "o1,d2,30"])
    opps = {"d1": {"jobs": 5}, "d2": {"jobs": 7}}
    rows = {(r["cutoff"]): r["accessibility"]
            for r in compute_accessibility(m, opps, ["o1"], [30], STEP)}
    assert rows[30] == 5   # d1 at 29 counts, d2 at exactly 30 does not (strict <)


def test_unreachable_pair_contributes_zero(tmp_path):
    m = _matrix(tmp_path, ["o1,d1,", "o1,d2,10"])
    opps = {"d1": {"jobs": 100}, "d2": {"jobs": 1}}
    out = list(compute_accessibility(m, opps, ["o1"], [30], STEP))
    assert [r["accessibility"] for r in out] == [1]


def test_multiple_opportunity_columns(tmp_path):
    m = _matrix(tmp_path, ["o1,d1,10", "o1,d2,20"])
    opps = {"d1": {"edu": 1, "health": 2}, "d2": {"edu": 3, "health": 0}}
    got = {(r["opportunity"], r["cutoff"]): r["accessibility"]
           for r in compute_accessibility(m, opps, ["o1"], [15, 30], STEP)}
    assert got[("edu", 15)] == 1
    assert got[("edu", 30)] == 4
    assert got[("health", 30)] == 2


def test_origin_with_no_reachable_destinations_is_zero_not_missing(tmp_path):
    m = _matrix(tmp_path, ["o1,d1,10"])
    opps = {"d1": {"jobs": 5}}
    out = {r["id"]: r["accessibility"]
           for r in compute_accessibility(m, opps, ["o1", "o2"], [30], STEP)}
    assert out == {"o1": 5, "o2": 0}


def test_multiple_percentile_columns(tmp_path):
    m = _matrix(tmp_path, ["o1,d1,10,40"], header="from_id,to_id,travel_time_p25,travel_time_p75")
    opps = {"d1": {"jobs": 1}}
    got = {r["percentile"]: r["accessibility"]
           for r in compute_accessibility(m, opps, ["o1"], [30], STEP)}
    assert got == {25: 1, 75: 0}
