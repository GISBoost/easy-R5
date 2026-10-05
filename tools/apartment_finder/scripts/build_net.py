"""Build one R5 network per (day, variant): data/networks/<day>/<variant>/ (variant = static|p50|p85)."""
import sys, json, shutil
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import warnings; warnings.simplefilter("ignore")
import _qgis_env; app = _qgis_env.start()
import processing
from pathlib import Path
day, variant = sys.argv[1], sys.argv[2]
pbf = sys.argv[3] if len(sys.argv) > 3 else HERE + "/data/raw/lodz.osm.pbf"   # car variants: data/car/lodz_car_<tw>.osm.pbf
net_name = sys.argv[4] if len(sys.argv) > 4 else variant
gtfs_dir = Path(HERE, "data/gtfs", day, variant)   # exactly one zip per variant (CLAUDE.md gotcha)
assert len(list(gtfs_dir.glob("*.zip"))) == (2 if variant.endswith("_lka") else 1), gtfs_dir
cache = Path(HERE, "data/networks", day, net_name); cache.mkdir(parents=True, exist_ok=True)
r = processing.run("easyr5:buildnetwork", {"OSM_PBF": pbf, "GTFS_FOLDER": str(gtfs_dir),
                                           "CACHE_FOLDER": str(cache)})
print(json.dumps({k: str(v) for k, v in r.items()}))
