"""Batch scheduling + result assembly helpers. Pure Python —
run: py -m pytest easy_r5/test/test_matrix.py -v"""

import pytest

from easy_r5.core.matrix import (
    merge_batch_csvs,
    nearest_served_days,
    systematic_sample_indices,
)


@pytest.mark.parametrize("n,k,expected_len", [(100, 15, 15), (10, 15, 10), (1, 5, 1), (0, 5, 0)])
def test_sample_indices_length(n, k, expected_len):
    assert len(systematic_sample_indices(n, k)) == expected_len


def test_sample_indices_span_and_order():
    idx = systematic_sample_indices(1000, 15)
    assert idx[0] == 0
    assert idx[-1] == 999
    assert idx == sorted(idx)
    assert len(set(idx)) == len(idx)


def test_sample_indices_k_ge_n_is_full_range():
    assert systematic_sample_indices(5, 15) == [0, 1, 2, 3, 4]


def test_merge_batch_csvs(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("from_id,to_id,travel_time_p50\n0,x,5\n0,y,7\n", encoding="utf-8")
    b.write_text("from_id,to_id,travel_time_p50\n1,x,9\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    rows = merge_batch_csvs([a, b], out)
    assert rows == 3
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "from_id,to_id,travel_time_p50"
    assert lines.count("from_id,to_id,travel_time_p50") == 1
    assert "1,x,9" in lines


def test_merge_batch_csvs_skips_missing(tmp_path):
    a = tmp_path / "a.csv"
    a.write_text("from_id,to_id\n0,x\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    assert merge_batch_csvs([a, tmp_path / "gone.csv"], out) == 1


def test_nearest_served_days_picks_closest():
    days = {"2026-08-24": 0, "2026-08-25": 4000, "2026-08-26": 4200, "2026-08-30": 3900}
    assert nearest_served_days(days, "2026-08-27", 2) == ["2026-08-26", "2026-08-25"]


def test_nearest_served_days_skips_zero_count():
    days = {"2026-08-25": 0, "2026-08-26": 0, "2026-08-27": 10}
    assert nearest_served_days(days, "2026-08-25", 3) == ["2026-08-27"]


def test_nearest_served_days_respects_k():
    days = {f"2026-08-{d:02d}": 10 for d in range(1, 20)}
    assert len(nearest_served_days(days, "2026-08-10", 3)) == 3
