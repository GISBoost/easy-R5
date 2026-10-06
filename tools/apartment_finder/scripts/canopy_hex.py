"""Canopy stage 3: canopy mask tiles -> share of canopy per hex (QGIS interpreter).

Reads `data/canopy/final/*.tif` (1 = canopy, 0 = other, 255 = no data; 0.5 m, EPSG:2177), builds a VRT, runs zonal
statistics on the hexes and writes `data/canopy/canopy_hex.csv`: hex_id, canopy_hex (share in [0, 1] of the whole hex area,
buildings and roads included in the denominator), cover_hex (fraction covered by valid pixels; must be ~1); method version and
data year go to canopy_hex.meta.json.

  python-qgis-ltr.bat scripts/canopy_hex.py [final_dir_name]
"""
import csv
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
from osgeo import gdal  # noqa: E402
from qgis.core import QgsRasterLayer, QgsVectorLayer  # noqa: E402

cfg = yaml.safe_load(open(HERE / "config/canopy.yaml", encoding="utf-8"))
OUT = HERE / "data/canopy"
fin = OUT / (sys.argv[1] if len(sys.argv) > 1 else "final")
tiles = sorted(fin.glob("*.tif"))
vrt = OUT / "canopy_final.vrt"
gdal.BuildVRT(str(vrt), [str(p) for p in tiles], srcNodata=255, VRTNodata=255)
rl = QgsRasterLayer(str(vrt), "canopy")
grid = QgsVectorLayer(str(HERE / "data/grid.gpkg") + "|layername=hex_grid", "g", "ogr")
hexes = processing.run("native:reprojectlayer", {"INPUT": grid, "TARGET_CRS": rl.crs(), "OUTPUT": "memory:"})["OUTPUT"]


def zs(layer, prefix):
    return processing.run("native:zonalstatisticsfb", {"INPUT": layer, "INPUT_RASTER": rl, "RASTER_BAND": 1, "COLUMN_PREFIX": prefix,
                                                      "STATISTICS": [0, 2], "OUTPUT": "memory:"})["OUTPUT"]   # count, mean (valid pixels only)


zh = zs(hexes, "h_")
PX2 = 0.25
rows = []
for f in zh.getFeatures():
    g = f.geometry()
    rows.append({"hex_id": f["hex_id"],
                 "canopy_hex": round(f["h_mean"], 4) if f["h_mean"] is not None else "",
                 "cover_hex": round((f["h_count"] or 0) * PX2 / g.area(), 4)})
rows.sort(key=lambda r: r["hex_id"])
with open(OUT / "canopy_hex.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
json.dump({"canopy_version": cfg["canopy_version"], "year": cfg["source"]["year"], "height_m": cfg["height_m"], "tiles": len(tiles)}, open(OUT / "canopy_hex.meta.json", "w"))
low = [r["hex_id"] for r in rows if r["cover_hex"] < 0.99]
print("hexes", len(rows), "tiles", len(tiles), "hexes with <99% coverage:", len(low), low[:10])
