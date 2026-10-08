"""Find routing access points for hexes whose centre snaps onto a disconnected piece of the street network (QGIS interpreter).

An "island" hex reaches (almost) nothing in a once-only matrix (walk, bike, car) although the city around it is connected: R5 snaps the
hex centre to the nearest edge usable by the mode, and that edge belongs to a tiny disconnected component (courtyard driveways, a split
carriageway). For each island hex the candidates around the centre (config/access.yaml: radii x bearings) are tested with R5 against probe
destinations; the nearest candidate that reaches like a normal hex becomes the hex's access point for that mode.

Output data/access_points.csv (mode, hex_id, x, y, shift_m, reach, typical): used by run_matrices.py for the origins and destinations of that
mode. Existing rows are kept (after a fix the matrices show no islands any more). Hexes with no good candidate are listed as UNFIXED.

  python-qgis-ltr.bat scripts/access_points.py [car] [walk] [bike]      (default: all three)
"""
import csv
import glob
import math
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import numpy as np  # noqa: E402
import processing  # noqa: E402
import yaml  # noqa: E402
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer  # noqa: E402

cfg = yaml.safe_load(open(HERE / "config/access.yaml", encoding="utf-8"))
scn = yaml.safe_load(open(HERE / "config/scenarios.yaml", encoding="utf-8"))
days = yaml.safe_load(open(HERE / "config/days.yaml", encoding="utf-8"))["days"]
DAY = days[-1]
MODES = {"car": ("morning_car", "car_morning"), "walk": ("morning_walk", "static"), "bike": ("morning_bike", "static")}   # agg matrix, network variant
OUT = HERE / "data/access_points.csv"


def mem_layer(name, pts):
    layer = QgsVectorLayer("Point?crs=EPSG:2180&field=id:string", name, "memory")
    feats = []
    for k, (x, y) in pts.items():
        f = QgsFeature(layer.fields()); f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y))); f["id"] = k; feats.append(f)
    layer.dataProvider().addFeatures(feats)
    return layer


def main():
    want = [m for m in sys.argv[1:] if m in MODES] or list(MODES)
    cent = QgsVectorLayer(str(HERE / "data/grid.gpkg") + "|layername=hex_centroids", "c", "ogr")
    C = {f["hex_id"]: f.geometry().asPoint() for f in cent.getFeatures()}
    n = len(C)
    old = list(csv.DictReader(open(OUT, encoding="utf-8"))) if OUT.exists() else []
    have = {(r["mode"], int(r["hex_id"])) for r in old}
    rows = list(old)
    probes = list(range(0, n, cfg["probe_step"]))
    for mode in want:
        agg, net_name = MODES[mode]
        m = np.load(HERE / "data/agg" / (agg + ".npy"))
        reached_row = (m < 255).sum(1) - 1
        reached_col = (m < 255).sum(0) - 1
        islands = [h for h in range(n) if (reached_row[h] <= cfg["island_max_reached"] or reached_col[h] <= cfg["island_max_reached"]) and (mode, h) not in have]
        pr = [p for p in probes if p not in islands]
        typical = float(np.median((m[:, pr] < 255).sum(1))) / len(pr) if pr else 0
        print("%s: %d islands %s; typical reach on %d probes: %.0f%%" % (mode, len(islands), islands, len(pr), 100 * typical))
        if not islands:
            continue
        cand = {}
        for h in islands:
            for r in cfg["radii_m"]:
                for k in range(cfg["bearings"]):
                    a = 2 * math.pi * k / cfg["bearings"]
                    cand["%d_%d_%d" % (h, r, k)] = (C[h].x() + r * math.cos(a), C[h].y() + r * math.sin(a))
        net = glob.glob(str(HERE / "data/networks" / DAY / net_name / "*/network.dat"))[0]
        out = str(HERE / ("data/probe/access_%s.csv" % mode))
        processing.run("easyr5:runtraveltimematrix", {
            "NETWORK": net, "ORIGINS": mem_layer("o", cand), "ORIGIN_ID_FIELD": "id",
            "DESTINATIONS": mem_layer("d", {str(p): (C[p].x(), C[p].y()) for p in pr}), "DEST_ID_FIELD": "id",
            "MODE": scn["non_transit"][mode]["mode"], "PERCENTILES": scn["r5"]["percentiles"], "MAX_TRIP_DURATION": scn["r5"]["max_trip_minutes"],
            "MAX_WALK_TIME": scn["r5"]["max_trip_minutes"], "MONTE_CARLO_DRAWS": 1, "ESTIMATE_FIRST": False, "OUTPUT_CSV": out})
        reach = {}
        with open(out, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                reach[r["from_id"]] = reach.get(r["from_id"], 0) + 1
        for h in islands:
            best = None
            for r in cfg["radii_m"]:
                ok = [(reach.get("%d_%d_%d" % (h, r, k), 0), k) for k in range(cfg["bearings"])]
                ok = [(c, k) for c, k in ok if c >= cfg["ok_share_of_median"] * typical * len(pr)]
                if ok:
                    c, k = max(ok)   # the candidate with the best reach on this ring
                    best = (r, k, c)
                    break
            if best is None:
                print("  UNFIXED hex %d (%s): no good candidate within %d m" % (h, mode, cfg["radii_m"][-1]))
                continue
            r, k, c = best
            x, y = cand["%d_%d_%d" % (h, r, k)]
            rows.append({"mode": mode, "hex_id": h, "x": round(x, 1), "y": round(y, 1), "shift_m": r, "reach": c, "typical": round(typical * len(pr))})
            print("  hex %d (%s): moved %d m, reaches %d of %d probes (typical hex %d)" % (h, mode, r, c, len(pr), round(typical * len(pr))))
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["mode", "hex_id", "x", "y", "shift_m", "reach", "typical"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["mode"], int(r["hex_id"]))))


if __name__ == "__main__":
    main()
