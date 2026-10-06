"""Maps of the change in travel time hex -> all other hexes, 5 Oct vs 28 Sep (run inside QGIS via mcp__qgis__execute_code).

    exec(open(r"<path>/hex_qgis.py", encoding="utf-8").read(), {"BAND": "am_peak"})

Reads out/hex_delta/main/hex.csv (hex_delta.py). Per ORIGIN hex: population-weighted mean of (later - earlier) minutes over
destinations that are transit trips on both days; `all` = every destination, `far` = destinations 10 km or more away
(trips across the city). Blue = the later Monday is faster, red = slower, pale grey = no change, no fill = too few
comparable destinations. Placebo is not mapped (reported as text only).
"""

import csv
from pathlib import Path

from qgis.core import (
    QgsFeature, QgsField, QgsFields, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsProject, QgsRendererRange,
    QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

HERE = Path(r"C:/Users/Michal/Desktop/easy/easy-R5/tools/lodz_timetable_change")
GRID = HERE.parent / "tram_failure_lodz" / "grids" / "h250.gpkg"
BAND = globals().get("BAND", "am_peak")
OUT_GPKG = HERE / "out" / f"s3_hex_{BAND}.gpkg"
EDGES = (3, 1, 0.25)   # minutes: strong / medium / weak change
BLUES, REDS, GREY = ["#2166ac", "#4393c3", "#92c5de"], ["#f4a582", "#d6604d", "#b2182b"], "#f7f7f7"
LABELS = ["≤ -3 min (krócej)", "-3 … -1", "-1 … -0,25", "≈ bez zmiany", "0,25 … 1", "1 … 3", "≥ 3 min (dłużej)"]
KINDS = {"all": ("mean_delta_all_min", "wszystkie cele"), "far": ("mean_delta_far_min", "cele ≥ 10 km (przez miasto)")}

values = {}
with open(HERE / "out" / "hex_delta" / "main" / "hex.csv", newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        if r["band"] == BAND:
            values[r["hex_id"]] = {k: (float(r[col]) if r[col] != "" else None) for k, (col, _) in KINDS.items()}

src = QgsVectorLayer(f"{GRID.as_posix()}|layername=hex_grid", "src", "ogr")
assert src.isValid(), "hex_grid not found"
mem = QgsFields()
mem.append(QgsField("hex_id", QVariant.Int))
mem.append(QgsField("pop", QVariant.Double))
for k in KINDS:
    mem.append(QgsField(f"d_{k}", QVariant.Double))
OUT_GPKG.parent.mkdir(parents=True, exist_ok=True)
opts = QgsVectorFileWriter.SaveVectorOptions()
opts.driverName, opts.layerName, opts.fileEncoding = "GPKG", "hex_delta", "UTF-8"
writer = QgsVectorFileWriter.create(str(OUT_GPKG), mem, QgsWkbTypes.Polygon, src.crs(),
                                    QgsProject.instance().transformContext(), opts)
for ft in src.getFeatures():
    v = values.get(str(ft["hex_id"]), {})
    out = QgsFeature(mem)
    out.setGeometry(ft.geometry())
    out.setAttributes([int(ft["hex_id"]), float(ft["pop_total"] or 0)] + [v.get(k) for k in KINDS])
    writer.addFeature(out)
del writer
print("hexes with values:", len(values))


def style(layer, field):
    b, s, t = EDGES
    inf = 1e12
    spec = [(-inf, -b, BLUES[0]), (-b, -s, BLUES[1]), (-s, -t, BLUES[2]), (-t, t, GREY),
            (t, s, REDS[0]), (s, b, REDS[1]), (b, inf, REDS[2])]
    ranges = [QgsRendererRange(lo, hi, QgsFillSymbol.createSimple(
        {"color": col, "outline_color": "#999999", "outline_width": "0.05"}), lab)
        for (lo, hi, col), lab in zip(spec, LABELS)]
    layer.setRenderer(QgsGraduatedSymbolRenderer(field, ranges))


proj = QgsProject.instance()
for old in [l for l in proj.mapLayers().values() if l.name().startswith("S3 HEX") and l.name().endswith(BAND)]:
    proj.removeMapLayer(old.id())
root = proj.layerTreeRoot()
for k, (_, label) in KINDS.items():
    lyr = QgsVectorLayer(f"{OUT_GPKG.as_posix()}|layername=hex_delta", f"S3 HEX Δ czas 5.10 vs 28.09, {label}, {BAND}", "ogr")
    style(lyr, f"d_{k}")
    proj.addMapLayer(lyr)
    root.findLayer(lyr.id()).setItemVisibilityChecked(k == "all")
print("layers added")
