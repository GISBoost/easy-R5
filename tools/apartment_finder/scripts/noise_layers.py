"""M2: per-hex noise exposure -> data/noise/noise_layers.csv (+ .meta.json).

For each source (road, tram, rail, industry) x indicator (lden, ln) and each dB threshold t in
config/noise.yaml: share of the hex area where the modelled level is >= t (band LMIN >= t).
Thresholds are NOT interpreted here; the web app applies the user's dB limit to these steps.
rail_all = tram + rail (the higher level of the two per cell; PRD 3: "szynowy").

Method: the bands (Esri JSON, EPSG:2180) and the hexagons are rasterised at config `cell_m` metres; each cell
takes the highest band covering it (bands are painted in ascending LMIN order; holes by even-odd over a
feature's rings), and a hex's share is the fraction of its cells at/above t. System Python (numpy, PIL, shapely).
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import export_web  # noqa: E402  (read_gpkg)

cfg = yaml.safe_load(open(HERE / "config/noise.yaml", encoding="utf-8"))
RES = cfg["cell_m"]
out_dir = HERE / "data/noise"

hexes = export_web.read_gpkg("hex_grid")
polys = [hexes[i].geoms[0] if hexes[i].geom_type == "MultiPolygon" else hexes[i] for i in range(len(hexes))]
xmin = min(p.bounds[0] for p in polys) - RES
ymin = min(p.bounds[1] for p in polys) - RES
xmax = max(p.bounds[2] for p in polys) + RES
ymax = max(p.bounds[3] for p in polys) + RES
W, H = int(np.ceil((xmax - xmin) / RES)), int(np.ceil((ymax - ymin) / RES))
px = lambda ring: [((x - xmin) / RES, (ymax - y) / RES) for x, y in ring]


def hex_raster():
    img = Image.new("I", (W, H), -1)
    d = ImageDraw.Draw(img)
    for i, p in enumerate(polys):
        d.polygon(px(p.exterior.coords), fill=i)
    return np.array(img)


def band_raster(path):
    """(highest LMIN per cell as uint8, lowest reported level of the layer).

    Cells below the layer's range stay 0. Some layers carry a catch-all "below X dB" band with a negative LMIN
    (tram/rail) and the road layer only starts at 55 (Lden) / 50 (Ln): such a band says nothing about levels under
    its upper edge, so it is not painted and thresholds under the lowest reported level become "no data".
    """
    feats = [f for f in json.load(open(path, encoding="utf-8"))["features"] if f["attributes"]["LMIN"] > 0]
    feats.sort(key=lambda f: f["attributes"]["LMIN"])
    lowest = min(f["attributes"]["LMIN"] for f in feats)
    arr = np.zeros((H, W), np.uint8)
    for f in feats:
        rings = [px(r) for r in f["geometry"]["rings"]]
        xs = [x for r in rings for x, _ in r]
        ys = [y for r in rings for _, y in r]
        x0, x1 = max(int(min(xs)) - 1, 0), min(int(max(xs)) + 2, W)
        y0, y1 = max(int(min(ys)) - 1, 0), min(int(max(ys)) + 2, H)
        if x1 <= x0 or y1 <= y0:
            continue
        mask = np.zeros((y1 - y0, x1 - x0), bool)
        for r in rings:                      # even-odd across the rings: holes cancel
            im = Image.new("1", (x1 - x0, y1 - y0), 0)
            ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in r], fill=1)
            mask ^= np.array(im, bool)
        arr[y0:y1, x0:x1][mask] = int(f["attributes"]["LMIN"])
    return arr, lowest


def main(dump_rasters=False):
    hid = hex_raster()
    inside = hid >= 0
    cells = np.bincount(hid[inside], minlength=len(polys)).astype(float)
    table = {}
    for ind, thr in cfg["thresholds"].items():
        rasters, lowest = {}, {}
        for src in cfg["sources"]:
            rasters[src], lowest[src] = band_raster(out_dir / ("%s_%s.json" % (src, ind)))
            print(src, ind, file=sys.stderr)
        rasters["rail_all"] = np.maximum(rasters["tram"], rasters["rail"])
        lowest["rail_all"] = max(lowest["tram"], lowest["rail"])
        if dump_rasters:   # for visual checking in QGIS (data/noise/check/): uint8 LMIN per cell, 0 = below range
            (out_dir / "check").mkdir(exist_ok=True)
            for src, r in rasters.items():
                np.save(out_dir / "check" / ("%s_%s.npy" % (src, ind)), r)
            json.dump({"xmin": xmin, "ymax": ymax, "cell_m": RES, "width": W, "height": H, "crs": "EPSG:2180"},
                      open(out_dir / "check" / "grid.json", "w"))
        for src, r in rasters.items():
            for t in thr:
                cnt = np.bincount(hid[inside & (r >= t)], minlength=len(polys))
                share = np.round(cnt / np.maximum(cells, 1), 4)
                table["%s_%s_ge%d" % (src, ind, t)] = share if t >= lowest[src] else np.full(len(polys), np.nan)
    cols = sorted(table)
    with open(out_dir / "noise_layers.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["hex_id"] + cols)
        for i in range(len(polys)):
            w.writerow([i] + ["" if np.isnan(table[c][i]) else table[c][i] for c in cols])
    json.dump({"layers_version": cfg["layers_version"], "source": cfg["source_note"], "cell_m": RES, "columns": cols},
              open(out_dir / "noise_layers.meta.json", "w", encoding="utf-8"), indent=1)
    print("done", len(cols), "columns", file=sys.stderr)


if __name__ == "__main__":
    main(dump_rasters="--dump-rasters" in sys.argv)
