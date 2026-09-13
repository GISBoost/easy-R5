"""E9 -- symbolization. Runs inside QGIS.

Manual, zero-isolated classification for delta layers (never automatic
equal-interval/quantile -- ported rationale from
tools/realtime_delay_lodz/style_delay_layers.py: at typical delta
distributions, most cells sit at/near 0, so an automatic scheme merges
small losses and small gains into one bucket and hides the story). Same
ColorBrewer RdBu-7 palette, edges on half-integers so an exact integer
never lands on a class boundary, NULL gets no symbol (transparent --
visually distinct from the pale grey "0, checked, no change" class).

RT coverage mask gets its own categorized renderer with a HATCH pattern
for "brak danych o realizacji" -- the explicit methodological requirement
that missing-data must never look like zero-effect.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

RDBU7 = ["#b2182b", "#d6604d", "#f4a582", "#f7f7f7", "#92c5de", "#4393c3", "#2166ac"]
SENTINEL = 9999


def classified_delta_renderer(field, edges, labels):
    from qgis.core import QgsRendererRange, QgsGraduatedSymbolRenderer, QgsFillSymbol

    ranges = []
    for i in range(len(edges) - 1):
        sym = QgsFillSymbol.createSimple({
            "color": RDBU7[i], "outline_color": "#808080", "outline_width": "0.1",
        })
        ranges.append(QgsRendererRange(edges[i], edges[i + 1], sym, labels[i]))
    # NOTE: a prior version of this function called
    # renderer.setClassificationMethod(None) here "defensively". That passes
    # a null QgsClassificationMethod*, and QGIS 3.40.5 does NOT null-check it
    # before calling classificationMethod->clone() whenever the renderer
    # itself is cloned (routine during canvas rendering, e.g. every
    # QgsMapRendererParallelJob). That produced an exact
    # "QgsGraduatedSymbolRenderer::clone -> access violation" crash,
    # confirmed via QGIS's own fatal-exception stack trace (2026-09-13).
    # Manual ranges need no classification method at all -- leave it unset.
    renderer = QgsGraduatedSymbolRenderer(field, ranges)
    return renderer


def delta_edges_labels(scale):
    """scale=1 for single-category deltas (edges at .5/1.5/3.5), scale~3
    for 'total' (sum of ~10 categories, wider buckets) -- matches the
    realtime_delay_lodz pattern of edges sized to the metric's own spread."""
    e = [-SENTINEL, -3.5*scale, -1.5*scale, -0.5, 0.5, 1.5*scale, 3.5*scale, SENTINEL]
    lbl = [f"<= -{4*scale:.0f}", f"-{3*scale:.0f} .. -{2*scale:.0f}", "-1",
           "0 (bez zmian)", "+1", f"+{2*scale:.0f} .. +{3*scale:.0f}", f">= +{4*scale:.0f}"]
    return e, lbl


def sequential_level_renderer(field, breaks):
    """Simple sequential ramp for 'level' maps (A1 accessibility total) --
    quantile-ish manual breaks (not delta, so zero-isolation doesn't apply)."""
    from qgis.core import QgsRendererRange, QgsGraduatedSymbolRenderer, QgsFillSymbol
    ramp = ["#ffffcc", "#c7e9b4", "#7fcdbb", "#41b6c4", "#2c7fb8", "#253494"]
    ranges = []
    edges = [0] + breaks + [SENTINEL]
    for i in range(len(edges) - 1):
        sym = QgsFillSymbol.createSimple({
            "color": ramp[min(i, len(ramp) - 1)], "outline_color": "#808080", "outline_width": "0.05",
        })
        label = f"{edges[i]:.0f}-{edges[i+1]:.0f}" if edges[i+1] != SENTINEL else f">= {edges[i]:.0f}"
        ranges.append(QgsRendererRange(edges[i], edges[i + 1], sym, label))
    return QgsGraduatedSymbolRenderer(field, ranges)


def rt_mask_renderer():
    from qgis.core import QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsFillSymbol

    cats = []
    style_map = {
        "RT pelne": {"color": "#2166ac", "style": "solid"},
        "RT czesciowe": {"color": "#92c5de", "style": "solid"},
        "brak danych o realizacji": {"color": "#f0f0f0", "style": "diagonal"},
    }
    for value, spec in style_map.items():
        if spec["style"] == "diagonal":
            sym = QgsFillSymbol.createSimple({
                "color": spec["color"], "outline_color": "#999999", "outline_width": "0.1",
                "style": "b_diagonal",
            })
        else:
            sym = QgsFillSymbol.createSimple({
                "color": spec["color"], "outline_color": "#808080", "outline_width": "0.1",
            })
        cats.append(QgsRendererCategory(value, sym, value))
    return QgsCategorizedSymbolRenderer("rt_coverage_class", cats)


def apply_all():
    from qgis.core import QgsVectorLayer, QgsProject

    gpkg = str(C.PRG_GPKG)

    # ---- level map (A1, total accessibility, c30) ----
    lvl = QgsVectorLayer(f"{gpkg}|layername=hex_woj_delta", "poziom_woj_c30", "ogr")
    lvl.setRenderer(sequential_level_renderer("base_total_c30", [5, 15, 30, 60, 120]))
    lvl.triggerRepaint()

    # ---- delta maps, per category + total, Lodz ----
    survivors = ["przedszkole", "szkola", "przychodnia", "apteka", "park", "plac_zabaw",
                 "boisko_sport", "supermarket", "poczta", "urzad_gminy"]
    lodz_delta = QgsVectorLayer(f"{gpkg}|layername=hex_lodz_delta", "delta_lodz", "ogr")
    e, lbl = delta_edges_labels(scale=3)  # total is a sum of 10 categories
    lodz_delta.setRenderer(classified_delta_renderer("delta_total_c30", e, lbl))
    lodz_delta.triggerRepaint()

    woj_delta = QgsVectorLayer(f"{gpkg}|layername=hex_woj_delta", "delta_woj", "ogr")
    woj_delta.setRenderer(classified_delta_renderer("delta_total_c30", e, lbl))
    woj_delta.triggerRepaint()

    # ---- RT coverage mask ----
    rt_lodz = QgsVectorLayer(f"{gpkg}|layername=hex_lodz_rt_mask", "rt_mask_lodz", "ogr")
    rt_lodz.setRenderer(rt_mask_renderer())
    rt_lodz.triggerRepaint()

    rt_woj = QgsVectorLayer(f"{gpkg}|layername=hex_woj_rt_mask", "rt_mask_woj", "ogr")
    rt_woj.setRenderer(rt_mask_renderer())
    rt_woj.triggerRepaint()

    return {"lvl": lvl, "lodz_delta": lodz_delta, "woj_delta": woj_delta,
            "rt_lodz": rt_lodz, "rt_woj": rt_woj}


if __name__ == "__main__":
    apply_all()
