"""M0: time RunTravelTimeMatrix on a sample of origins -> all hexes (O16 + runtime estimate)."""
import sys, time, glob, random, json
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import warnings; warnings.simplefilter("ignore")
import _qgis_env; app = _qgis_env.start()
import processing
from qgis.core import QgsVectorLayer
n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
net = glob.glob(HERE + "/data/networks/2026-10-02/static/*/network.dat")[0]
cent = QgsVectorLayer(HERE + "/data/grid.gpkg|layername=hex_centroids", "c", "ogr")
ids = sorted(f["hex_id"] for f in cent.getFeatures()); random.seed(1)
sample = random.sample(ids, n)
orig = processing.run("native:extractbyexpression", {"INPUT": cent, "EXPRESSION": "hex_id IN (%s)" % ",".join(map(str, sample)), "OUTPUT": "memory:"})["OUTPUT"]
out = f"{HERE}/data/probe/probe_{n}.csv"
t = time.time()
r = processing.run("easyr5:runtraveltimematrix", {
    "NETWORK": net, "ORIGINS": orig, "ORIGIN_ID_FIELD": "hex_id", "DESTINATIONS": cent, "DEST_ID_FIELD": "hex_id",
    "DATE": "2026-10-02", "DEPARTURE_TIME": "07:00", "TIME_WINDOW": 120, "PERCENTILES": "50,85",
    "MAX_TRIP_DURATION": 90, "MAX_RIDES": 3, "MODE": 0, "MAX_WALK_TIME": 20, "ESTIMATE_FIRST": False, "OUTPUT_CSV": out})
dt = time.time() - t
import os
print(json.dumps({"origins": n, "seconds": round(dt, 1), "s_per_origin": round(dt / n, 2), "csv_mb": round(os.path.getsize(out) / 1e6, 1)}))
