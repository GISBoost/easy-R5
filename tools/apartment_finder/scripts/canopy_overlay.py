"""Preview image of the canopy mask for the web app: EPSG:3857 PNG (WebP RGBA, green, alpha = canopy share per cell) + bounds.

Warps the final canopy tiles (0.5 m, EPSG:2177) to Web Mercator with averaging (`overlay_res_m` per pixel, config/canopy.yaml),
writes <out>/canopy.webp and <out>/canopy_overlay.json {url, bounds [[south, west], [north, east]], res_m}.
System Python (osgeo, numpy, PIL):  py scripts/canopy_overlay.py [--final final_v2] [--out ../../../gdzie-mieszkac-lodz-data]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import yaml
from osgeo import gdal, osr
from PIL import Image

gdal.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/canopy.yaml", encoding="utf-8"))
ap = argparse.ArgumentParser()
ap.add_argument("--final", default="final_v2")
ap.add_argument("--out", default=str((HERE / "../../../gdzie-mieszkac-lodz-data").resolve()))
a = ap.parse_args()
OUT = Path(a.out)
res = cfg["overlay_res_m"]
tiles = sorted((HERE / "data/canopy" / a.final).glob("*.tif"))
vrt = HERE / "data/canopy/_overlay_src.vrt"
gdal.BuildVRT(str(vrt), [str(p) for p in tiles], srcNodata=255, VRTNodata=255)
# bounds of the hex grid (+ margin) in Web Mercator: only what the app can show
lay = gdal.OpenEx(str(HERE / "data/grid.gpkg"))
ext = lay.GetLayerByName("hex_grid").GetExtent()      # EPSG:2180 (minx, maxx, miny, maxy)
s80, s3857 = osr.SpatialReference(), osr.SpatialReference()
s80.ImportFromEPSG(2180); s3857.ImportFromEPSG(3857)
for s in (s80, s3857):
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(s80, s3857)
pts = [tr.TransformPoint(x, y)[:2] for x in (ext[0], ext[1]) for y in (ext[2], ext[3])]
bb = (min(p[0] for p in pts) - 300, min(p[1] for p in pts) - 300, max(p[0] for p in pts) + 300, max(p[1] for p in pts) + 300)
w = gdal.Warp("", str(vrt), format="MEM", dstSRS="EPSG:3857", outputBounds=bb, xRes=res, yRes=res, resampleAlg="average",
              srcNodata=255, dstNodata=255, outputType=gdal.GDT_Float32)
share = w.GetRasterBand(1).ReadAsArray()
valid = share != 255
levels = np.clip(np.round(np.where(valid, share, 0) * 8), 0, 8).astype(np.uint8)       # 8 alpha steps keep the PNG small
pal = [(0, 0, 0)] + [(0, 150, 50)] * 8
alpha = [0] + [int(255 * k / 8 * 0.9) for k in range(1, 9)]
rgba = np.zeros(levels.shape + (4,), np.uint8)
rgba[..., :3] = (0, 150, 50)
rgba[..., 3] = np.array(alpha, np.uint8)[levels]
png = OUT / "canopy.webp"                     # lossy WebP with alpha: ~6x smaller than the paletted PNG at the same resolution
Image.fromarray(rgba, "RGBA").save(png, quality=cfg["overlay_quality"], method=6)
t = osr.SpatialReference(); t.ImportFromEPSG(4326); t.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr2 = osr.CoordinateTransformation(s3857, t)
w_, s_ = tr2.TransformPoint(bb[0], bb[1])[:2]
e_, n_ = tr2.TransformPoint(bb[2], bb[3])[:2]
json.dump({"url": "canopy.webp", "bounds": [[round(s_, 6), round(w_, 6)], [round(n_, 6), round(e_, 6)]], "res_m": res, "size": list(levels.shape[::-1])},
          open(OUT / "canopy_overlay.json", "w"))
print("canopy.webp %.2f MB, %s px, canopy share (valid cells) %.3f" % (png.stat().st_size / 1e6, levels.shape[::-1], float((share[valid]).mean())))
