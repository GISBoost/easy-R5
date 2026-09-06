"""Manual, zero-isolated diverging classification for hex_delay's
delta_<category> fields and hex_net_opportunities' net_delta.

Why manual breaks, not QGIS's automatic equal-interval/quantile classing:
delta is a small integer with a true, meaningful zero ("no change"), and the
distribution is heavily zero-inflated with a long thin tail (e.g. 250 m
delta_school: 2361/3867 comparable hexagons are exactly 0, but values run out
to -14 and +10). An automatic 7-class scheme puts a wide range like [-2, +2]
in one bucket -- "no change" and "lost 2 opportunities" end up the same
colour, which is exactly the ambiguity this fixes. Manual breaks give 0 its
own singleton class instead.

NULL values (no static baseline -- see compute_delay.py's base0_<category>)
are not covered by any range and QGIS's graduated renderer draws no symbol
for them at all: fully transparent, visually distinct from the pale
"0 / no change" class, which IS present (comparable) data.

Colours: ColorBrewer RdBu-7 (colourblind-safe diverging). Red = fewer
opportunities after delays, blue = more, pale grey-white = no change.

Must run inside the QGIS Python environment, e.g. mcp__qgis__execute_code.
"""

from __future__ import annotations

from pathlib import Path

from qgis.core import (
    QgsFillSymbol,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
)

RDBU7 = ["#b2182b", "#d6604d", "#f4a582", "#f7f7f7", "#92c5de", "#4393c3", "#2166ac"]
SENTINEL = 9999  # safely outside any real delta/net_delta value

CATEGORY_EDGES = [-SENTINEL, -3.5, -1.5, -0.5, 0.5, 1.5, 3.5, SENTINEL]
CATEGORY_LABELS = ["<= -4", "-3 .. -2", "-1", "0 (no change)", "+1", "+2 .. +3", ">= +4"]

NET_EDGES = [-SENTINEL, -5.5, -1.5, -0.5, 0.5, 1.5, 5.5, SENTINEL]
NET_LABELS = ["<= -6", "-5 .. -2", "-1", "0 (no change)", "+1", "+2 .. +5", ">= +6"]


def _ranges(edges, labels):
    ranges = []
    for lo, hi, color, label in zip(edges, edges[1:], RDBU7, labels):
        symbol = QgsFillSymbol.createSimple({
            "color": color, "outline_color": "#808080", "outline_width": "0.1",
        })
        ranges.append(QgsRendererRange(lo, hi, symbol, label))
    return ranges


def style_field(layer, field, edges, labels):
    renderer = QgsGraduatedSymbolRenderer(field, _ranges(edges, labels))
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def style_delta_field(layer, category):
    style_field(layer, f"delta_{category}", CATEGORY_EDGES, CATEGORY_LABELS)


def style_net_delta(layer):
    style_field(layer, "net_delta", NET_EDGES, NET_LABELS)


def save_qml(layer, path: Path):
    layer.saveNamedStyle(str(path))
    print(f"[ok] saved style {path}")


def classify(value, edges=NET_EDGES):
    """Pure-Python counterpart of the QGIS ranges above -- which of the 7 classes
    a value falls into (0 = most negative .. 6 = most positive). Used by
    chart_distance_delta.py so a bar chart can reuse the exact same colours
    as the map legend instead of picking its own scale."""
    for i in range(len(edges) - 1):
        if value <= edges[i + 1]:
            return i
    return len(edges) - 2
