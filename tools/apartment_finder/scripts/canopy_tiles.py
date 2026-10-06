"""Canopy stage 1: per-tile nDSM height codes from GUGiK NMPT and NMT (streamed, resumable, idempotent).

For every 800x500 m tile covering the city + buffer: download NMPT.asc and NMT.asc (0.5 m, ~11 MB each), compute
nDSM = NMPT - NMT, store a small uint8 GeoTIFF `data/canopy/codes/<godlo>.tif` (band 1: code = number of config `height_codes_m`
thresholds reached, 0 = below the lowest or above `max_height_m`, 255 = no data; band 2: local std of NMPT in cm) and delete the ASC files.
Buildings/poles are handled in stage 2 (canopy_mask.py). System Python (osgeo + numpy), no QGIS needed.

  py scripts/canopy_tiles.py [--workers 4] [--limit N]
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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
CODES = OUT / "codes"
TMP = OUT / "_dl"
for d in (CODES, TMP):
    d.mkdir(parents=True, exist_ok=True)
CRS2177 = osr.SpatialReference()
CRS2177.ImportFromEPSG(2177)
CRS2177.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
BBOX = "51.64,19.25,51.90,19.72,urn:ogc:def:crs:EPSG::4326"       # whole city extent (lat,lon order for urn CRS)


def wfs_to_file(base, layer, dst):
    q = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": layer, "bbox": BBOX}
    urllib.request.urlretrieve(base + "?" + urllib.parse.urlencode(q, safe=":,"), dst)


def city_geometry():
    ds = ogr.Open(str(HERE / "data/grid.gpkg"))   # keep the dataset referenced while iterating
    lyr = ds.GetLayerByName("hex_grid")
    u = None
    for f in lyr:
        g = f.GetGeometryRef().Clone()
        u = g if u is None else u.Union(g)
    return u.Buffer(cfg["tiles_buffer_m"])


def read_index(path, keep=None):
    ds = ogr.Open(str(path))
    lyr = ds.GetLayer(0)
    rows = []
    for f in lyr:
        g = f.GetGeometryRef()
        if g is None or (keep is not None and not g.Intersects(keep)):
            continue
        rows.append({"godlo": f.GetField("godlo"), "url": f.GetField("url_do_pobrania"), "xy": f.GetField("uklad_xy"),
                     "year": f.GetField("akt_rok"), "date": f.GetField("timePosition")})
    return rows


def tile_list():
    cache = OUT / "tiles_index.json"
    if cache.exists():
        return json.load(open(cache, encoding="utf-8"))
    src = cfg["source"]
    lidar = OUT / src["lidar_index_gml"]
    if not lidar.exists():
        wfs_to_file(src["nmpt_wfs"].replace("NumerycznyModelPokryciaTerenuEVRF2007", "DanePomiaroweLidarEVRF2007"),
                    "gugik:SkorowidzDanychPomiarowychLIDAR%d" % src["year"], lidar)
    tiles = {r["godlo"] for r in read_index(lidar, city_geometry())}
    per = {}
    for key, base, layer in (("nmpt", src["nmpt_wfs"], src["nmpt_layer"]), ("nmt", src["nmt_wfs"], src["nmt_layer"])):
        gml = OUT / ("idx_%s.gml" % key)
        if not gml.exists():
            wfs_to_file(base, layer, gml)
        for r in read_index(gml):
            if r["godlo"] in tiles and r["year"] == src["year"] and r["xy"] == "PL-2000:S6":
                per.setdefault(r["godlo"], {})[key] = r["url"]
    res = [{"godlo": g, **per[g]} for g in sorted(tiles) if g in per and "nmpt" in per[g] and "nmt" in per[g]]
    missing = sorted(tiles - {r["godlo"] for r in res})
    json.dump({"tiles": res, "missing": missing, "lidar_tiles": len(tiles)}, open(cache, "w"), indent=0)
    return {"tiles": res, "missing": missing, "lidar_tiles": len(tiles)}


def fetch(url, dst):
    for k in range(4):
        try:
            urllib.request.urlretrieve(url, dst)
            return
        except Exception:
            time.sleep(2 * (k + 1))
    raise RuntimeError("download failed: " + url)


def process(t):
    out = CODES / (t["godlo"] + ".tif")
    if out.exists():
        return t["godlo"], "skip"
    a, b = TMP / (t["godlo"] + "_nmpt.asc"), TMP / (t["godlo"] + "_nmt.asc")
    da = db = None
    try:
        fetch(t["nmpt"], a)
        fetch(t["nmt"], b)
        da, db = gdal.Open(str(a)), gdal.Open(str(b))
        gt = da.GetGeoTransform()
        if da.RasterXSize != db.RasterXSize or da.RasterYSize != db.RasterYSize or gt != db.GetGeoTransform():
            raise RuntimeError("NMPT/NMT grids differ")
        s, g = da.ReadAsArray().astype(np.float32), db.ReadAsArray().astype(np.float32)
        bad = (s < -9000) | (g < -9000)
        h = s - g
        code = np.zeros(h.shape, np.uint8)
        for thr in cfg["height_codes_m"]:
            code += (h >= thr).astype(np.uint8)
        code[h > cfg["max_height_m"]] = 0
        code[bad] = 255
        w = cfg["smooth"]["window_px"]
        z = np.where(bad, np.nan, s).astype(np.float64)
        z = np.nan_to_num(z - np.nanmean(z), nan=0.0)             # centred: avoids cancellation in the variance
        var = ndi.uniform_filter(z * z, w) - ndi.uniform_filter(z, w) ** 2
        std_cm = np.clip(np.sqrt(np.maximum(var, 0)) * 100, 0, 254).astype(np.uint8)
        drv = gdal.GetDriverByName("GTiff")
        tmp = str(out) + ".part"
        o = drv.Create(tmp, code.shape[1], code.shape[0], 2, gdal.GDT_Byte, ["COMPRESS=DEFLATE", "TILED=YES"])
        o.SetGeoTransform(gt)
        o.SetProjection(CRS2177.ExportToWkt())
        o.GetRasterBand(1).SetNoDataValue(255)
        o.GetRasterBand(1).WriteArray(code)
        o.GetRasterBand(2).WriteArray(std_cm)
        o = None
        Path(tmp).replace(out)
        return t["godlo"], "ok"
    except Exception as e:
        return t["godlo"], "ERR " + str(e)[:120]
    finally:
        da = db = None            # release the GDAL handles first: Windows cannot delete open files
        for p in (a, b):
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    idx = tile_list()
    tiles = idx["tiles"][: a.limit] if a.limit else idx["tiles"]
    print("tiles", len(tiles), "of", idx["lidar_tiles"], "LAZ tiles; without NMPT+NMT:", len(idx["missing"]), idx["missing"][:5], flush=True)
    t0, n, errs = time.time(), 0, []
    with ThreadPoolExecutor(a.workers) as ex:
        for godlo, st in ex.map(process, tiles):
            n += 1
            if st.startswith("ERR"):
                errs.append((godlo, st))
            if n % 20 == 0 or st.startswith("ERR"):
                print(n, "/", len(tiles), godlo, st, "%.0fs" % (time.time() - t0), flush=True)
    print("done", n, "errors", len(errs), errs[:10], "%.0fs" % (time.time() - t0), flush=True)
    sys.exit(1 if errs else 0)
