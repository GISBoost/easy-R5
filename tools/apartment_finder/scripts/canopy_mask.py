"""Canopy stage 2: nDSM height codes -> canopy mask per tile (resumable, idempotent).

For each `data/canopy/codes/<godlo>.tif`:
  1. canopy candidate = code >= number of thresholds up to config `height_m`;
  2. minus BDOT10k structures (config `exclude`: buildings, tanks, towers, technical devices, sport structures as buffered
     polygons; bridges as buffered lines; masts/technical devices as buffered points), rasterised at 0.5 m;
  3. morphological opening (config `open_radius_m`) removes objects thinner than ~2 m (poles, lamp arms, wires, fences);
  4. patches smaller than `min_patch_m2` are dropped.
Output `data/canopy/final/<godlo>.tif`: uint8, 1 = canopy, 0 = other, 255 = no data. Run after canopy_tiles.py (system Python).

  py scripts/canopy_mask.py [--only GODLO ...] [--tag NAME]     (--tag writes to final_<NAME>/ for experiments)
"""
import argparse
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from osgeo import gdal, ogr, osr
from scipy import ndimage as ndi

gdal.UseExceptions()
ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/canopy.yaml", encoding="utf-8"))
OUT = HERE / "data/canopy"
S2177, S2180 = osr.SpatialReference(), osr.SpatialReference()
S2177.ImportFromEPSG(2177)
S2180.ImportFromEPSG(2180)
for s in (S2177, S2180):
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
TO2177, TO2180 = osr.CoordinateTransformation(S2180, S2177), osr.CoordinateTransformation(S2177, S2180)
PX = 0.5
NEED = [i for i, t in enumerate(cfg["height_codes_m"]) if t == cfg["height_m"]][0] + 1   # code >= NEED means height >= height_m

_layers = {}


def bdot_layer(name):
    if name not in _layers:
        p = glob.glob(str(OUT / "bdot" / ("*__OT_%s.gpkg" % name)))[0]
        ds = ogr.Open(p)
        _layers[name] = (ds, ds.GetLayer(0))
    return _layers[name][1]


def exclusion(gt, w, h):
    """Boolean raster (h, w) of BDOT10k structures (buffered) for the tile grid."""
    x0, y0 = gt[0], gt[3]
    x1, y1 = x0 + w * PX, y0 - h * PX
    c = [TO2180.TransformPoint(x, y)[:2] for x in (x0, x1) for y in (y0, y1)]
    xmin, xmax, ymin, ymax = min(p[0] for p in c) - 10, max(p[0] for p in c) + 10, min(p[1] for p in c) - 10, max(p[1] for p in c) + 10
    mem = ogr.GetDriverByName("Memory").CreateDataSource("x")
    ml = mem.CreateLayer("x", S2177, ogr.wkbUnknown)
    for kind in ("polygons", "lines", "points"):
        for name, buf in cfg["exclude"][kind].items():
            lyr = bdot_layer(name)
            lyr.SetSpatialFilterRect(xmin, ymin, xmax, ymax)
            for f in lyr:
                g = f.GetGeometryRef().Clone()
                if buf:
                    g = g.Buffer(buf)
                g.Transform(TO2177)
                ft = ogr.Feature(ml.GetLayerDefn())
                ft.SetGeometry(g)
                ml.CreateFeature(ft)
    r = gdal.GetDriverByName("MEM").Create("", w, h, 1, gdal.GDT_Byte)
    r.SetGeoTransform(gt)
    r.SetProjection(S2177.ExportToWkt())
    gdal.RasterizeLayer(r, [1], ml, burn_values=[1])
    return r.ReadAsArray() > 0


def disk(radius_px):
    y, x = np.ogrid[-radius_px:radius_px + 1, -radius_px:radius_px + 1]
    return x * x + y * y <= radius_px * radius_px


def clean(mask):
    rp = int(round(cfg["open_radius_m"] / PX))
    pad = rp + 1
    m = np.pad(mask, pad, mode="edge")                      # edge padding: no erosion artefact at tile borders
    m = ndi.binary_opening(m, structure=disk(rp))[pad:-pad, pad:-pad]
    lab, n = ndi.label(m, structure=np.ones((3, 3)))
    if n:
        sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
        keep = np.concatenate([[False], sizes * PX * PX >= cfg["min_patch_m2"]])
        m = keep[lab]
    return m


def process(src, dst):
    ds = gdal.Open(str(src))
    gt, w, h = ds.GetGeoTransform(), ds.RasterXSize, ds.RasterYSize
    code = ds.ReadAsArray()
    nodata = code == 255
    cand = (code >= NEED) & ~nodata
    ex = exclusion(gt, w, h)
    final = clean(cand & ~ex)
    out = final.astype(np.uint8)
    out[nodata] = 255
    tmp = str(dst) + ".part"
    o = gdal.GetDriverByName("GTiff").Create(tmp, w, h, 1, gdal.GDT_Byte, ["COMPRESS=DEFLATE", "TILED=YES"])
    o.SetGeoTransform(gt)
    o.SetProjection(S2177.ExportToWkt())
    o.GetRasterBand(1).SetNoDataValue(255)
    o.GetRasterBand(1).WriteArray(out)
    o = ds = None
    Path(tmp).replace(dst)
    valid = ~nodata
    return {"raw": float(cand.sum() / max(1, valid.sum())), "excluded_part": float((cand & ex).sum() / max(1, cand.sum())),
            "final": float(final.sum() / max(1, valid.sum())), "nodata": float(nodata.mean())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    fin = OUT / ("final_" + a.tag if a.tag else "final")
    fin.mkdir(parents=True, exist_ok=True)
    srcs = sorted((OUT / "codes").glob("*.tif"))
    if a.only:
        srcs = [p for p in srcs if p.stem in a.only]
    t0, stats = time.time(), {}
    for i, p in enumerate(srcs, 1):
        dst = fin / p.name
        if dst.exists():
            continue
        stats[p.stem] = process(p, dst)
        if i % 50 == 0:
            print(i, "/", len(srcs), "%.0fs" % (time.time() - t0), flush=True)
    if stats:
        log = fin / "stats.json"
        old = json.load(open(log)) if log.exists() else {}
        old.update(stats)
        json.dump(old, open(log, "w"))
    print("done", len(stats), "new tiles in", fin, "%.0fs" % (time.time() - t0))
