"""TRANSIT_SUBMODES resolution (F1). Pure Python -
run: py -m pytest easy_r5/test/test_matrix_base.py -v"""

from easy_r5.algorithms._matrix_base import (
    MODE_MAP,
    _TRANSIT_MODES,
    _mode_label,
    _resolve_transit_submodes,
    _transit_submodes_meta,
)


def test_blank_selection_is_all_modes_unchanged():
    """PRD/F1 acceptance: bit-for-bit identical to today's hardcoded default."""
    assert _resolve_transit_submodes(0, []) == list(_TRANSIT_MODES)
    assert _resolve_transit_submodes(0, []) == MODE_MAP[0][1]
    assert len(_resolve_transit_submodes(0, [])) == 8


def test_selection_normalized_to_transit_modes_order():
    # BUS = index 3, TRAM = index 0 in _TRANSIT_MODES - picked in reverse order.
    assert _resolve_transit_submodes(0, [3, 0]) == ["TRAM", "BUS"]


def test_non_transit_mode_ignores_selection():
    # MODE=WALK (index 1): no transit component, selection has no effect.
    assert _resolve_transit_submodes(1, [0, 3]) == []


def test_transit_submodes_meta_blank_is_all():
    assert _transit_submodes_meta(0, [], list(_TRANSIT_MODES)) == "ALL"


def test_transit_submodes_meta_selection_lists_modes():
    transit_modes = _resolve_transit_submodes(0, [3, 0])
    assert _transit_submodes_meta(0, [3, 0], transit_modes) == "TRAM,BUS"


def test_transit_submodes_meta_non_transit_mode_is_na():
    assert _transit_submodes_meta(1, [0, 3], []) == "N/A"


def test_mode_label_unchanged_when_blank():
    assert _mode_label(0, [], list(_TRANSIT_MODES)) == "TRANSIT + WALK"


def test_mode_label_appends_selection():
    transit_modes = _resolve_transit_submodes(0, [3, 0])
    assert _mode_label(0, [3, 0], transit_modes) == "TRANSIT + WALK (TRAM, BUS)"


def test_mode_label_non_transit_mode_unaffected_by_selection():
    assert _mode_label(1, [0, 3], []) == "WALK"
