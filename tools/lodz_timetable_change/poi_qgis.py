"""Maps of the change in travel time to the 3 nearest POIs, hex 250 m (run inside QGIS, e.g. via mcp__qgis__execute_code).

    exec(open(r"<path>/poi_qgis.py", encoding="utf-8").read())

Reads out/poi_delta/<pair>/hex.csv (poi_delta.py). Field d_<category>_<band> = median over a hex's comparable nearest POIs
of (later - earlier) minutes, transit trips only; d_all_<band> = mean of the category values of that hex.
Blue = the later Monday is faster, red = slower, pale grey = no change, no fill = not comparable.
"""

import csv
from collections import defaultdict
from pathlib import Path

from qgis.core import (
    QgsFeature, QgsField, QgsFields, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsProject, QgsRendererRange,
    QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

HERE = Path(r"C:/Users/Michal/Desktop/easy/easy-R5/tools/lodz_timetable_change")
SRC = globals().get("SRC_DIR", HERE / "out" / "poi_delta")
GRID = HERE.parent / "tram_failure_lodz" / "grids" / "h250.gpkg"
OUT_GPKG = HERE / "out" / "s3_poi.gpkg"
CATS = ["pharmacy", "school", "clinic", "supermarket"]
CAT_PL = {"all": "wszystkie", "pharmacy": "apteki", "school": "szkoły", "clinic": "przychodnie", "supermarket": "supermarkety"}
PAIRS = {"main": "5.10 vs 28.09", "placebo": "28.09 vs 21.09 (placebo)"}
BAND = globals().get("BAND", "am_peak")
EDGES = (3, 1, 0.25)   # minutes: strong / medium / weak change
BLUES, REDS, GREY = ["#2166ac", "#4393c3", "#92c5de"], ["#f4a582", "#d6604d", "#b2182b"], "#f7f7f7"
LABELS = ["≤ -3 min (krócej)", "-3 … -1", "-1 … -0,25", "≈ bez zmiany", "0,25 … 1", "1 … 3", "≥ 3 min (dłużej)"]


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


values = {}   # pair -> hex_id -> {field: value}
for pair in PAIRS:
    f = Path(SRC) / pair / "hex.csv"
    if not f.is_file():
        continue
    per = defaultdict(lambda: defaultdict(list))
    for r in read(f):
        per[r["hex_id"]][(r["category"], r["band"])].append(float(r["delta_min"]))
    v = {}
    for hid, d in per.items():
        row = {}
        for (c, b), x in d.items():
            row[f"d_{c}_{b}"] = x[0]
        for b in {b for _, b in d}:
            got = [d[(c, b)][0] for c in CATS if (c, b) in d]
            row[f"d_all_{b}"] = sum(got) / len(got)
        v[hid] = row
    values[pair] = v

fields = [f"{p}_{c}_{BAND}" for p in values for c in ["all"] + CATS]
src = QgsVectorLayer(f"{GRID.as_posix()}|layername=hex_grid", "src", "ogr")
assert src.isValid(), "hex_grid not found"
mem = QgsFields()
mem.append(QgsField("hex_id", QVariant.Int))
mem.append(QgsField("pop", QVariant.Double))
for f in fields:
    mem.append(QgsField(f, QVariant.Double))
OUT_GPKG.parent.mkdir(parents=True, exist_ok=True)
opts = QgsVectorFileWriter.SaveVectorOptions()
opts.driverName, opts.layerName, opts.fileEncoding = "GPKG", "hex_delta", "UTF-8"
writer = QgsVectorFileWriter.create(str(OUT_GPKG), mem, QgsWkbTypes.Polygon, src.crs(),
                                    QgsProject.instance().transformContext(), opts)
n = 0
for ft in src.getFeatures():
    hid = str(ft["hex_id"])
    out = QgsFeature(mem)
    out.setGeometry(ft.geometry())
    out.setAttributes([int(ft["hex_id"]), float(ft["pop_total"] or 0)] +
                      [values[p].get(hid, {}).get(f"d_{c}_{BAND}") for p in values for c in ["all"] + CATS])
    writer.addFeature(out)
    n += 1
del writer
print("hexes written:", n, {p: len(v) for p, v in values.items()})


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
for old in [l for l in proj.mapLayers().values() if l.name().startswith("S3 POI")]:
    proj.removeMapLayer(old.id())
root = proj.layerTreeRoot()
for pair, label in PAIRS.items():
    if pair not in values:
        continue
    for c in ["all"] + CATS:
        name = f"S3 POI Δ czas {label}, {CAT_PL[c]}, {BAND}"
        lyr = QgsVectorLayer(f"{OUT_GPKG.as_posix()}|layername=hex_delta", name, "ogr")
        style(lyr, f"{pair}_{c}_{BAND}")
        proj.addMapLayer(lyr)
        root.findLayer(lyr.id()).setItemVisibilityChecked(pair == "main" and c == "all")
print("layers added")
