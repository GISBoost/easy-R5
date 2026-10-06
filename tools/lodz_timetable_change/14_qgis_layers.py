"""S3 layer 1: build s3_layer1.gpkg (hex 500 m with deltas) and a styled QGIS project.

Must run inside the QGIS Python environment (qgis.core), e.g. via mcp__qgis__execute_code:
    exec(open(r"<path>/14_qgis_layers.py", encoding="utf-8").read())

Reads out/layer1_delta/main/delta_hex.csv (reach deltas), out/layer1_tt/main/hex.csv and placebo/hex.csv
(transit travel-time deltas). Delta = after (12.10) - before (14.09). Blue = better for the traveller in every map
(more people reachable, shorter trips), red = worse, pale grey = exactly no change, no fill = not comparable.
"""

import csv
from pathlib import Path

from qgis.core import (
    QgsFeature, QgsField, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsProject, QgsRendererRange,
    QgsVectorFileWriter, QgsVectorLayer, QgsFields, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

HERE = Path(r"C:/Users/Michal/Desktop/easy/easy-R5/tools/lodz_timetable_change")
GRID_NAME = globals().get("GRID_NAME", "h500")   # set before exec() for the 250 m maps
SFX = "" if GRID_NAME == "h500" else f"_{GRID_NAME}"
GRID = HERE.parent / "tram_failure_lodz" / "grids" / f"{GRID_NAME}.gpkg"
BANDS = ["am_peak", "midday", "pm_peak", "evening"]
OUT_GPKG = HERE / "out" / f"s3_layer1{SFX}.gpkg"


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


values = {}  # hex_id -> {field: value}
for r in read(HERE / "out" / f"layer1_delta{SFX}" / "main" / "delta_hex.csv"):
    if r["metric"] == "acc" and r["opportunity"] == "pop" and r["cutoff"] in ("30", "60"):
        values.setdefault(r["hex_id"], {})[f"dpop{r['cutoff']}_{r['band']}"] = float(r["delta"])
for pair, tag in (("main", "tt"), ("placebo", "ttplc")):
    for r in read(HERE / "out" / f"layer1_tt{SFX}" / pair / "hex.csv"):
        values.setdefault(r["hex_id"], {})[f"{tag}_{r['band']}"] = float(r["mean_delta_min"])

fields = [f"dpop30_{b}" for b in BANDS] + [f"dpop60_{b}" for b in BANDS] + \
         [f"tt_{b}" for b in BANDS] + [f"ttplc_{b}" for b in BANDS]

src = QgsVectorLayer(f"{GRID.as_posix()}|layername=hex_grid", "src", "ogr")
assert src.isValid(), "hex_grid not found"
mem_fields = QgsFields()
mem_fields.append(QgsField("hex_id", QVariant.Int))
mem_fields.append(QgsField("pop", QVariant.Double))
for f in fields:
    mem_fields.append(QgsField(f, QVariant.Double))

OUT_GPKG.parent.mkdir(parents=True, exist_ok=True)
opts = QgsVectorFileWriter.SaveVectorOptions()
opts.driverName = "GPKG"
opts.layerName = "hex_delta"
opts.fileEncoding = "UTF-8"
writer = QgsVectorFileWriter.create(str(OUT_GPKG), mem_fields, QgsWkbTypes.Polygon, src.crs(),
                                    QgsProject.instance().transformContext(), opts)
n = 0
for ft in src.getFeatures():
    hid = str(ft["hex_id"])
    v = values.get(hid, {})
    out = QgsFeature(mem_fields)
    out.setGeometry(ft.geometry())
    out.setAttributes([int(ft["hex_id"]), float(ft["pop_total"] or 0)] + [v.get(f) for f in fields])
    writer.addFeature(out)
    n += 1
del writer
print("hexes written:", n, "with values:", len(values))

# --- styling ---------------------------------------------------------------
BLUES = ["#2166ac", "#4393c3", "#92c5de"]
REDS = ["#f4a582", "#d6604d", "#b2182b"]
GREY = "#f7f7f7"


def style(layer, field, edges, better_negative, labels):
    b, s, t = edges
    inf = 1e12
    # colours: for "better_negative" (shorter trips) negative values are blue
    if better_negative:
        spec = [(-inf, -b, BLUES[0]), (-b, -s, BLUES[1]), (-s, -t, BLUES[2]), (-t, t, GREY),
                (t, s, REDS[0]), (s, b, REDS[1]), (b, inf, REDS[2])]
    else:
        spec = [(-inf, -b, REDS[2]), (-b, -s, REDS[1]), (-s, -t, REDS[0]), (-t, t, GREY),
                (t, s, BLUES[2]), (s, b, BLUES[1]), (b, inf, BLUES[0])]
    ranges = []
    for (lo, hi, col), label in zip(spec, labels):
        sym = QgsFillSymbol.createSimple({"color": col, "outline_color": "#999999", "outline_width": "0.05"})
        ranges.append(QgsRendererRange(lo, hi, sym, label))
    layer.setRenderer(QgsGraduatedSymbolRenderer(field, ranges))


REACH_LABELS = ["≤ -5000", "-5000 … -1000", "-1000 … ~0", "no change", "~0 … 1000", "1000 … 5000", "≥ 5000"]
TT_LABELS = ["≤ -3 min (faster)", "-3 … -1", "-1 … -0.25", "≈ no change", "0.25 … 1", "1 … 3", "≥ 3 min (slower)"]

proj = QgsProject.instance()
for ln in tuple(f"{n}{SFX}" for n in ("S3 tt Δ am_peak", "S3 tt Δ pm_peak", "S3 reach30 Δ am_peak", "S3 reach30 Δ pm_peak", "S3 PLACEBO tt Δ am_peak")):
    for old in proj.mapLayersByName(ln):
        proj.removeMapLayer(old.id())

specs = [
    ("S3 tt Δ am_peak", "tt_am_peak", (3, 1, 0.25), True, TT_LABELS),
    ("S3 tt Δ pm_peak", "tt_pm_peak", (3, 1, 0.25), True, TT_LABELS),
    ("S3 reach30 Δ am_peak", "dpop30_am_peak", (5000, 1000, 0.5), False, REACH_LABELS),
    ("S3 reach30 Δ pm_peak", "dpop30_pm_peak", (5000, 1000, 0.5), False, REACH_LABELS),
    ("S3 PLACEBO tt Δ am_peak", "ttplc_am_peak", (3, 1, 0.25), True, TT_LABELS),
]
root = proj.layerTreeRoot()
for name, field, edges, neg_better, labels in specs:
    name = f"{name}{SFX}"
    lyr = QgsVectorLayer(f"{OUT_GPKG.as_posix()}|layername=hex_delta", name, "ogr")
    # no fill for NULL: a graduated renderer simply draws nothing for features outside every range
    style(lyr, field, edges, neg_better, labels)
    proj.addMapLayer(lyr)
    node = root.findLayer(lyr.id())
    node.setItemVisibilityChecked(name == f"S3 tt Δ am_peak{SFX}")
print("layers added:", [f"{s[0]}{SFX}" for s in specs])
