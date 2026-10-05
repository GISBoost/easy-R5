"""M3 check: R5 CAR matrices on the per-time-of-day OSM copies for a sample of origins; compares them."""
import sys, glob, random, json, warnings
warnings.simplefilter("ignore")
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import _qgis_env; app = _qgis_env.start()
import processing
from qgis.core import QgsVectorLayer
cent = QgsVectorLayer(HERE + "/data/grid.gpkg|layername=hex_centroids", "c", "ogr")
random.seed(2); sample = random.sample(sorted(f["hex_id"] for f in cent.getFeatures()), 200)
orig = processing.run("native:extractbyexpression", {"INPUT": cent, "EXPRESSION": "hex_id IN (%s)" % ",".join(map(str, sample)), "OUTPUT": "memory:"})["OUTPUT"]
for w in ("morning", "afternoon"):
    net = glob.glob(HERE + "/data/networks/2026-10-02/car_%s/*/network.dat" % w)[0]
    processing.run("easyr5:runtraveltimematrix", {"NETWORK": net, "ORIGINS": orig, "ORIGIN_ID_FIELD": "hex_id", "DESTINATIONS": cent,
        "DEST_ID_FIELD": "hex_id", "MODE": 3, "PERCENTILES": "50", "MAX_TRIP_DURATION": 90, "MAX_WALK_TIME": 90,
        "ESTIMATE_FIRST": False, "OUTPUT_CSV": HERE + "/data/probe/car_%s.csv" % w})
