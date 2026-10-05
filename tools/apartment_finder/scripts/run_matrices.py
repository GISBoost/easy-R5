"""M4/M5: run one OD matrix scenario via the Easy-R5 plugin (headless) and pack it to uint8.

  QGIS-python scripts/run_matrices.py <day> <window> <ttype> <rides:unlimited|max1transfer> <lka:0|1>
  QGIS-python scripts/run_matrices.py <day> <window> walk|bike|car

Output: data/matrices/<day>/<name>.npz  (p50 / p85 uint8 [origin, dest], 255 = not reached, minutes
capped at 254) + <name>.json (parameters, network hash, R5 meta, timing). Idempotent: skips a scenario
whose json exists. The raw CSV is deleted after packing (it is ~250 MB).
"""
import glob
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
import yaml  # noqa: E402
from qgis.core import QgsVectorLayer  # noqa: E402

scn = yaml.safe_load(open(HERE + "/config/scenarios.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE + "/config/time_windows.yaml", encoding="utf-8"))["windows"]
car = yaml.safe_load(open(HERE + "/config/car.yaml", encoding="utf-8"))["car_version"]
day, window, kind = sys.argv[1], sys.argv[2], sys.argv[3]
transit = kind in scn["ttypes"]
if transit:
    rides, lka = sys.argv[4], sys.argv[5] == "1"
    name = "%s_%s_%s_%s" % (window, kind, rides, "lka" if lka else "nolka")
    net_name = kind + ("_lka" if lka else "")
    mode = 0
else:
    name = "%s_%s" % (window, kind)
    net_name = ("car_" + window) if kind == "car" else "static"
    mode = scn["non_transit"][kind]["mode"]
out_dir = Path(HERE, "data/matrices", day)
out_dir.mkdir(parents=True, exist_ok=True)
meta_path = out_dir / (name + ".json")
if meta_path.exists():
    print("skip (done)", name)
    sys.exit(0)

net = glob.glob(HERE + "/data/networks/%s/%s/*/network.dat" % (day, net_name))[0]
cent = QgsVectorLayer(HERE + "/data/grid.gpkg|layername=hex_centroids", "c", "ogr")
w = tw[window]
h1, m1 = map(int, w["start"].split(":"))
h2, m2 = map(int, w["end"].split(":"))
params = {"NETWORK": net, "ORIGINS": cent, "ORIGIN_ID_FIELD": "hex_id", "DESTINATIONS": cent, "DEST_ID_FIELD": "hex_id",
          "MODE": mode, "PERCENTILES": scn["r5"]["percentiles"], "MAX_TRIP_DURATION": scn["r5"]["max_trip_minutes"],
          "MAX_WALK_TIME": scn["r5"]["max_walk_minutes"] if transit else scn["r5"]["max_trip_minutes"],
          "MONTE_CARLO_DRAWS": scn["r5"]["monte_carlo_draws"], "ESTIMATE_FIRST": False,
          "OUTPUT_CSV": str(out_dir / (name + ".csv"))}
if transit:
    params.update({"DATE": day, "DEPARTURE_TIME": w["start"], "TIME_WINDOW": (h2 * 60 + m2) - (h1 * 60 + m1),
                   "MAX_RIDES": scn["rides"][rides]})
t0 = time.time()
processing.run("easyr5:runtraveltimematrix", params)
secs = time.time() - t0
csv_path = params["OUTPUT_CSV"]
SYSTEM_PY = os.path.expanduser("~/AppData/Local/Programs/Python/Python311/python.exe")
env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "QGIS", "GDAL", "PROJ"))}  # system py must not see the QGIS env
subprocess.run([SYSTEM_PY, HERE + "/scripts/pack_matrix.py", csv_path, str(out_dir / (name + ".npz"))], check=True, env=env)
r5meta = json.load(open(csv_path + ".meta.json", encoding="utf-8"))
json.dump({"scenario": name, "day": day, "window": window, "network": net_name, "r5_seconds": round(secs, 1),
           "scenarios_version": scn["scenarios_version"], "car_version": car, "r5": r5meta},
          open(meta_path, "w", encoding="utf-8"), indent=1)
os.remove(csv_path)
os.remove(csv_path + ".meta.json")
print("done", name, round(secs, 1), "s")
