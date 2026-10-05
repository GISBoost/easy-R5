"""Exact R5 run: hex centres -> facility points (data/services/poi.gpkg), counted per criterion and Y level.

  QGIS python scripts/service_counts.py <day> <scenario>
scenario = walk | bike | car_<window> | transit_<window>_<static|p50|p85>_<nolka|lka> (transfers unlimited).
Writes data/services/<day>/<scenario>.npz (see count_services.py). Resumable (skips an existing result).
"""
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import warnings  # noqa: E402

warnings.simplefilter("ignore")
day, scenario = sys.argv[1], sys.argv[2]
cfg = yaml.safe_load(open(HERE + "/config/services.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE + "/config/time_windows.yaml", encoding="utf-8"))["windows"]
scn = yaml.safe_load(open(HERE + "/config/scenarios.yaml", encoding="utf-8"))
parts = scenario.split("_")
kind = parts[0]
m = cfg["modes"][kind]
out_dir = Path(HERE, "data/services", day)
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / (scenario + ".npz")
if out.exists():
    print("skip (done)", scenario)
    sys.exit(0)
if kind == "car":
    net_name = "car_" + parts[1]
elif kind == "transit":
    net_name = parts[2] + ("_lka" if parts[3] == "lka" else "")
else:
    net_name = "static"
net = glob.glob(HERE + "/data/networks/%s/%s/*/network.dat" % (day, net_name))[0]
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
from qgis.core import QgsVectorLayer  # noqa: E402

cent = QgsVectorLayer(HERE + "/data/grid.gpkg|layername=hex_centroids", "c", "ogr")
poi = QgsVectorLayer(HERE + "/data/services/poi.gpkg|layername=poi", "p", "ogr")
csv_path = str(out_dir / (scenario + ".csv"))
params = {"NETWORK": net, "ORIGINS": cent, "ORIGIN_ID_FIELD": "hex_id", "DESTINATIONS": poi, "DEST_ID_FIELD": "poi_id",
          "MODE": m["mode"], "PERCENTILES": "50", "MAX_TRIP_DURATION": m["max_min"],
          "MAX_WALK_TIME": scn["r5"]["max_walk_minutes"] if kind == "transit" else m["max_min"],
          "MONTE_CARLO_DRAWS": scn["r5"]["monte_carlo_draws"], "ESTIMATE_FIRST": False, "OUTPUT_CSV": csv_path}
if kind == "transit":
    w = tw[parts[1]]
    h1, m1 = map(int, w["start"].split(":"))
    h2, m2 = map(int, w["end"].split(":"))
    params.update({"DATE": day, "DEPARTURE_TIME": w["start"], "TIME_WINDOW": (h2 * 60 + m2) - (h1 * 60 + m1),
                   "MAX_RIDES": scn["rides"]["unlimited"]})
t0 = time.time()
processing.run("easyr5:runtraveltimematrix", params)
print("r5 %s %s %.0f s" % (day, scenario, time.time() - t0))
SYSTEM_PY = os.path.expanduser("~/AppData/Local/Programs/Python/Python311/python.exe")
env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "QGIS", "GDAL", "PROJ"))}
subprocess.run([SYSTEM_PY, HERE + "/scripts/count_services.py", csv_path, str(out), ",".join(map(str, m["levels"]))], check=True, env=env)
os.remove(csv_path)
if os.path.exists(csv_path + ".meta.json"):
    os.remove(csv_path + ".meta.json")
