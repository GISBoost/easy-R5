"""2SFCA. Pure Python — run: py -m pytest easy_r5/test/test_fca.py -v"""

import pytest

from easy_r5.core.accessibility import EXPONENTIAL, STEP
from easy_r5.core.fca import read_matrix_pairs, two_step_fca, weight

# Hand-computed: X serves A and B (demand 400) -> R_X = 10/400 = 0.025;
# Y serves only B (A-Y is 40 min, outside the 30-min catchment) -> R_Y = 20/300.
PAIRS = [("A", "X", 10), ("A", "Y", 40), ("B", "X", 20), ("B", "Y", 25), ("A", "Z", 35)]
POP = {"A": 100, "B": 300}
CAP = {"X": 10, "Y": 20, "Z": 5}


def test_classic_2sfca_hand_example():
    r = two_step_fca(PAIRS, POP, CAP, catchment=30)
    assert r["ratio"]["X"] == pytest.approx(0.025)
    assert r["ratio"]["Y"] == pytest.approx(20 / 300)
    assert r["access"]["A"] == pytest.approx(0.025)
    assert r["access"]["B"] == pytest.approx(0.025 + 20 / 300)
    assert r["unserved_supply"] == 1 and r["ratio"]["Z"] == 0.0


def test_supply_is_conserved():
    r = two_step_fca(PAIRS, POP, CAP, catchment=30)
    assert sum(r["access"][o] * POP[o] for o in POP) == pytest.approx(r["distributed_supply"]) == pytest.approx(30)
    re = two_step_fca(PAIRS, POP, CAP, catchment=30, decay=EXPONENTIAL)
    assert sum(re["access"][o] * POP[o] for o in POP) == pytest.approx(re["distributed_supply"])


def test_per_population_scaling_and_missing_values():
    r = two_step_fca(PAIRS, {"A": 100, "B": 300, "C": None}, CAP, catchment=30, per_population=1000)
    assert r["access"]["A"] == pytest.approx(25.0)
    assert r["access"]["C"] == 0.0


def test_catchment_is_strict():
    assert weight(STEP, 29, 30) == 1.0
    assert weight(STEP, 30, 30) == 0.0
    assert weight(EXPONENTIAL, 31, 30) == 0.0
    assert weight(STEP, None, 30) == 0.0


def test_read_matrix_pairs(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("from_id,to_id,travel_time_p50\nA,X,10\nA,Y,\n", encoding="utf-8")
    assert list(read_matrix_pairs(p, 50)) == [("A", "X", 10)]
    with pytest.raises(ValueError):
        list(read_matrix_pairs(p, 85))
