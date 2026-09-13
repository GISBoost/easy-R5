"""Stable id generation for point layers. Pure Python —
run: py -m pytest easy_r5/test/test_points.py -v"""

import pytest

from easy_r5.core.points import _check_fields_present, stable_ids


class _FakeFields:
    """Minimal stand-in for QgsFields: name -> index, -1 if absent."""

    def __init__(self, names):
        self._names = list(names)

    def lookupField(self, name):
        try:
            return self._names.index(name)
        except ValueError:
            return -1


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


# --- _check_fields_present (easy-R5 issue #5 regression guard) -------------
# A destinations layer with a stale, cached field list (e.g. a QgsVectorLayer
# already open in the project when the underlying GeoPackage table gained
# columns) must never be read silently: lookupField() on the stale schema
# either misses a new column entirely, or returns the wrong index for one
# that shifted — either way, reading it produces a quietly wrong number.


def test_all_fields_present_is_a_noop():
    fields = _FakeFields(["poi_id", "srv_park", "srv_szkola"])
    _check_fields_present(fields, ["srv_park", "srv_szkola"], "Destination")  # no raise


def test_missing_field_raises_with_name():
    fields = _FakeFields(["poi_id", "srv_park"])
    with pytest.raises(ValueError, match="srv_uczelnia"):
        _check_fields_present(fields, ["srv_park", "srv_uczelnia"], "Destination")


def test_missing_field_error_names_the_layer_label():
    fields = _FakeFields([])
    with pytest.raises(ValueError, match="Destination"):
        _check_fields_present(fields, ["srv_park"], "Destination")


def test_empty_names_is_a_noop():
    _check_fields_present(_FakeFields([]), [], "Destination")  # no raise
