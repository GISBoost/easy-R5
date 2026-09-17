"""Population-weighted equity statistics. Pure Python — run: py -m pytest easy_r5/test/test_equity.py -v"""

import pytest

from easy_r5.core.equity import (
    clean_pairs,
    render_html,
    summarize,
    summarize_layer,
    weighted_gini,
    weighted_quantile,
)


def test_gini_equal_is_zero_and_all_to_one_is_half():
    assert weighted_gini([(5, 1), (5, 3)]) == pytest.approx(0.0)
    assert weighted_gini([(0, 1), (1, 1)]) == pytest.approx(0.5)


def test_gini_weights_equal_duplicated_rows():
    # weight 2 on a value must equal listing that value twice
    assert weighted_gini([(1, 2), (4, 1)]) == pytest.approx(weighted_gini([(1, 1), (1, 1), (4, 1)]))


def test_gini_undefined_when_no_access():
    assert weighted_gini([(0, 10)]) is None


def test_weighted_quantile():
    pairs = [(0, 50), (10, 30), (20, 20)]
    assert weighted_quantile(pairs, 0.5) == 0
    assert weighted_quantile(pairs, 0.6) == 10
    assert weighted_quantile(pairs, 0.9) == 20
    assert weighted_quantile([], 0.5) is None


def test_clean_pairs_null_access_is_zero_null_pop_skipped():
    pairs, skipped = clean_pairs([None, 3, 4, 5], [10, None, -1, 0])
    assert pairs == [(0.0, 10.0)]
    assert skipped == 2


def test_summarize_shares():
    row = summarize([0, 1, 3], [100, 300, 600], threshold=1)
    assert row["population"] == 1000
    assert row["share_at_least"] == pytest.approx(0.9)
    assert row["share_zero"] == pytest.approx(0.1)
    assert row["mean"] == pytest.approx(2.1)
    assert row["p50"] == 3


def test_summarize_layer_groups():
    recs = [{"pop": 10, "acc": 0, "d": "N"}, {"pop": 30, "acc": 2, "d": "S"}, {"pop": 60, "acc": 1, "d": "S"}]
    rows = summarize_layer(recs, "pop", ["acc"], 1, group_field="d")
    assert [r["grp"] for r in rows] == ["ALL", "N", "S"]
    assert rows[0]["share_at_least"] == pytest.approx(0.9)
    assert rows[1]["share_at_least"] == 0
    page = render_html(rows, 1, {"percentile": ["50"]})
    assert "90.0%" in page and "percentile" in page
