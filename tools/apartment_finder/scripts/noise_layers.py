"""M2: per-hex noise exposure -> data/noise/noise_layers.csv (+ .meta.json).

For each source (road, tram, rail, industry) x indicator (lden, ln) and each dB threshold t in
config/noise.yaml: share of the hex area where the modelled level is >= t (band LMIN >= t).
Thresholds are NOT interpreted here; the web app applies the user's dB limit to these steps.
rail_all = tram + rail union (PRD 3: "szynowy"). Run with QGIS python (see _qgis_env.py).
"""
import csv
import json
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import yaml  # noqa: E402
from qgis.core import QgsGeometry, QgsVectorLayer  # noqa: E402

cfg = yaml.safe_load(open(HERE + "/config/noise.yaml", encoding="utf-8"))
out_dir = Path(HERE, "data/noise")
hexes = QgsVectorLayer(HERE + "/data/grid.gpkg|layername=hex_grid", "h", "ogr")
hex_geoms = {f["hex_id"]: f.geometry() for f in hexes.getFeatures()}
hex_area = {h: g.area() for h, g in hex_geoms.items()}


def band_geoms(src, ind):
    lyr = QgsVectorLayer(str(out_dir / ("%s_%s.json" % (src, ind))), src, "ogr")
    assert lyr.isValid(), src
    return [(f["LMIN"], f.geometry().makeValid()) for f in lyr.getFeatures()]


def shares(geoms_by_min, thresholds):
    """{t: {hex_id: area share}} for the union of bands with LMIN >= t."""
    res = {}
    for t in thresholds:
        sel = [g for lmin, g in geoms_by_min if lmin >= t]
        out = {}
        if sel:
            u = QgsGeometry.unaryUnion(sel)
            eng = QgsGeometry.createGeometryEngine(u.constGet())
            eng.prepareGeometry()
            for h, g in hex_geoms.items():
                if not eng.intersects(g.constGet()):
                    continue
                inter = eng.intersection(g.constGet())
                out[h] = round(inter.area() / hex_area[h], 4) if inter else 0.0
        res[t] = out
        print("  >=%s dB: %d hexes touched" % (t, len(out)), file=sys.stderr)
    return res


table = {h: {} for h in hex_geoms}
for ind, thr in cfg["thresholds"].items():
    cache = {}
    for src in cfg["sources"]:
        print(src, ind, file=sys.stderr)
        cache[src] = band_geoms(src, ind)
        for t, vals in shares(cache[src], thr).items():
            for h in table:
                table[h]["%s_%s_ge%d" % (src, ind, t)] = vals.get(h, 0.0)
    both = cache["tram"] + cache["rail"]
    print("rail_all", ind, file=sys.stderr)
    for t, vals in shares(both, thr).items():
        for h in table:
            table[h]["rail_all_%s_ge%d" % (ind, t)] = vals.get(h, 0.0)

cols = ["hex_id"] + sorted(next(iter(table.values())))
with open(out_dir / "noise_layers.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for h in sorted(table):
        w.writerow([h] + [table[h][c] for c in cols[1:]])
meta = {"layers_version": cfg["layers_version"], "source": cfg["source_note"], "columns": cols[1:]}
json.dump(meta, open(out_dir / "noise_layers.meta.json", "w"), indent=1)
print("done", len(cols) - 1, "columns")
