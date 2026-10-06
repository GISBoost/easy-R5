"""M-C0 pilot: share of vegetation points (LiDAR classes 3+4+5, 1 m raster as in the video method) per hex and per
hex + 150 m neighbourhood, on the downtown tiles that are already on disk. Not the production pipeline (M-C1/M-C2).

Run with QGIS's interpreter:  python-qgis-ltr.bat scripts/canopy_pilot.py <tif_dir> [out.csv]
A pixel is vegetation when the 1 m cell holds a valid value (the raster is the IDW export of `Classification` filtered to
3,4,5; NoData = no such point). Coverage = the tile extents, so only hexes fully inside them are reported.
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
from osgeo import gdal  # noqa: E402
from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry, QgsRasterLayer, QgsVectorLayer  # noqa: E402

tif_dir = Path(sys.argv[1])
out_csv = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "data/canopy/pilot_hex.csv"
out_csv.parent.mkdir(parents=True, exist_ok=True)
BUF = 150

tiles = sorted(p for p in tif_dir.glob("class*.tif"))
vrt = out_csv.parent / "pilot_tiles.vrt"
gdal.BuildVRT(str(vrt), [str(p) for p in tiles], srcNodata=-9999, VRTNodata=-9999)
rl = QgsRasterLayer(str(vrt), "veg")
cover = QgsGeometry.unaryUnion([QgsGeometry.fromRect(QgsRasterLayer(str(p)).extent()) for p in tiles])
print("tiles", len(tiles), "covered km2", round(cover.area() / 1e6, 2), "CRS", rl.crs().authid())

grid = QgsVectorLayer(str(HERE / "data/grid.gpkg") + "|layername=hex_grid", "g", "ogr")
hex_ = processing.run("native:reprojectlayer", {"INPUT": grid, "TARGET_CRS": rl.crs(), "OUTPUT": "memory:"})["OUTPUT"]
buf = processing.run("native:buffer", {"INPUT": hex_, "DISTANCE": BUF, "SEGMENTS": 8, "OUTPUT": "memory:"})["OUTPUT"]


def zs(layer, prefix):
    return processing.run("native:zonalstatisticsfb", {"INPUT": layer, "INPUT_RASTER": rl, "RASTER_BAND": 1, "COLUMN_PREFIX": prefix,
                                                      "STATISTICS": [0], "OUTPUT": "memory:"})["OUTPUT"]   # 0 = count of valid pixels


zh, zb = zs(hex_, "h_"), zs(buf, "b_")
bf = {f["hex_id"]: f for f in zb.getFeatures()}
rows = []
for f in zh.getFeatures():
    g = f.geometry()
    gb = bf[f["hex_id"]].geometry()
    ch = g.intersection(cover).area() / g.area()
    cb = gb.intersection(cover).area() / gb.area()
    rows.append({"hex_id": f["hex_id"], "cover_hex": round(ch, 4), "cover_buf": round(cb, 4),
                 "share_hex": round(f["h_count"] / g.area(), 4) if f["h_count"] is not None else 0.0,
                 "share_buf": round(bf[f["hex_id"]]["b_count"] / gb.area(), 4) if bf[f["hex_id"]]["b_count"] is not None else 0.0})
with open(out_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print("wrote", out_csv, "rows", len(rows), "hexes fully covered", sum(r["cover_hex"] > 0.99 for r in rows),
      "with buffer fully covered", sum(r["cover_buf"] > 0.99 for r in rows))
