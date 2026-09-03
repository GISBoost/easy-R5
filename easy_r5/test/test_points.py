"""Stable id generation for point layers. Pure Python —
run: py -m pytest easy_r5/test/test_points.py -v"""

import pytest

from easy_r5.core.points import stable_ids


def test_none_gives_zero_padded_indices():
    assert stable_ids(None, 3) == ["0", "1", "2"]


def test_padding_width_tracks_n():
    ids = stable_ids(None, 1000)
    assert ids[0] == "000"
    assert ids[-1] == "999"
    assert len(ids) == 1000


def test_none_empty():
    assert stable_ids(None, 0) == []


def test_given_values_stringified():
    assert stable_ids([1, 2, "x"], 3) == ["1", "2", "x"]


def test_duplicate_values_raise():
    with pytest.raises(ValueError, match="duplicate"):
        stable_ids(["a", "b", "a"], 3)


def test_duplicate_after_stringify_raises():
    with pytest.raises(ValueError):
        stable_ids([1, "1"], 2)


@pytest.mark.parametrize("bad", ["a,b", 'x"y', "line\nbreak"])
def test_id_with_csv_metachar_raises(bad):
    with pytest.raises(ValueError, match="comma, quote or newline"):
        stable_ids(["ok", bad], 2)
