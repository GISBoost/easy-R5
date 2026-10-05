"""M1: per-hex static layers -> data/static/static_layers.csv (+ .meta.json).

Columns: hex_id, d_tram_m, d_bus_m, d_green_m (network walking distance, 20 m resolution,
empty when > 2000 m), freq_{tram,bus}_{window} (departures/h within the radius, nearest stop
per route+direction). Run with QGIS python (see _qgis_env.py). Reads the pilot-day static GTFS
and the OSM extract.
"""
import collections
import csv
import datetime
import glob
import io
import json
import sys
import warnings
import zipfile
from pathlib import Path

warnings.simplefilter("ignore")
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
import yaml  # noqa: E402
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,  # noqa: E402
                       QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer)

cfg = yaml.safe_load(open(HERE + "/config/static_layers.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE + "/config/time_windows.yaml", encoding="utf-8"))["windows"]
day = cfg["pilot_day"]
out_dir = Path(HERE, "data/static")
out_dir.mkdir(parents=True, exist_ok=True)
R = QgsCoordinateReferenceSystem("EPSG:2180")
W = QgsCoordinateReferenceSystem("EPSG:4326")
to2180 = QgsCoordinateTransform(W, R, QgsProject.instance())

# ---- GTFS (stdlib only) ----
gz = zipfile.ZipFile(next(Path(HERE, "data/gtfs", day, "static").glob("*.zip")))


def rows(name):
    return csv.DictReader(io.TextIOWrapper(gz.open(name), encoding="utf-8-sig"))


d = datetime.date.fromisoformat(day)
dow = d.strftime("%A").lower()
ymd = d.strftime("%Y%m%d")
active = set()
if "calendar.txt" in gz.namelist():
    for r in rows("calendar.txt"):
        if r[dow] == "1" and r["start_date"] <= ymd <= r["end_date"]:
            active.add(r["service_id"])
if "calendar_dates.txt" in gz.namelist():
    for r in rows("calendar_dates.txt"):
        if r["date"] == ymd:
            (active.add if r["exception_type"] == "1" else active.discard)(r["service_id"])
rtype = {r["route_id"]: int(r["route_type"]) for r in rows("routes.txt")}
trips = {r["trip_id"]: (r["route_id"], r.get("direction_id") or "0")
         for r in rows("trips.txt") if r["service_id"] in active}
assert trips, "no active trips on " + day  # silent walk-only guard (CLAUDE.md gotcha)


def mode_of(t):
    if t in cfg["transit"]["tram_route_types"]:
        return "tram"
    return "bus" if t in cfg["transit"]["bus_route_types"] else None


def hm(s):
    return int(s[:2]) * 60 + int(s[3:5])


deps = collections.defaultdict(list)  # (stop, route, dir) -> departure minutes
stop_mode = {}
for r in rows("stop_times.txt"):
    tr = trips.get(r["trip_id"])
    if not tr:
        continue
    m = mode_of(rtype[tr[0]])
    if m:
        deps[(r["stop_id"], tr[0], tr[1])].append(hm(r["departure_time"]))
        stop_mode[r["stop_id"]] = m
stops = {r["stop_id"]: (float(r["stop_lon"]), float(r["stop_lat"]))
         for r in rows("stops.txt") if r["stop_id"] in stop_mode}
print("active trips", len(trips), "tram stops", sum(v == "tram" for v in stop_mode.values()),
      "bus stops", sum(v == "bus" for v in stop_mode.values()))


def points_layer(name, pts):
    lyr = QgsVectorLayer("Point?crs=EPSG:2180&field=pid:integer", name, "memory")
    feats = []
    for i, (x, y) in enumerate(pts):
        ft = QgsFeature(lyr.fields())
        ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        ft.setAttribute(0, i)
        feats.append(ft)
    lyr.dataProvider().addFeatures(feats)
    return lyr


def walk_matrix(origins, dests, tag):
    """origin hex_id -> {dest pid: network walking distance in metres (20 m steps)}."""
    net = glob.glob(HERE + "/data/networks/%s/static/*/network.dat" % day)[0]
    out = str(out_dir / ("walk_%s.csv" % tag))
    processing.run("easyr5:runtraveltimematrix", {
        "NETWORK": net, "ORIGINS": origins, "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": dests, "DEST_ID_FIELD": "pid",
        "DEPARTURE_TIME": "07:00", "TIME_WINDOW": 1, "PERCENTILES": "50", "MODE": 1,
        "WALK_SPEED": cfg["walk"]["speed_kmh"], "MAX_TRIP_DURATION": cfg["walk"]["max_minutes"],
        "MAX_WALK_TIME": cfg["walk"]["max_minutes"], "ESTIMATE_FIRST": False, "OUTPUT_CSV": out})
    step = cfg["walk"]["speed_kmh"] * 1000 / 60
    res = collections.defaultdict(dict)
    for r in csv.DictReader(open(out, encoding="utf-8")):
        res[int(r["from_id"])][int(r["to_id"])] = float(r["travel_time_p50"]) * step
    return res


cent = QgsVectorLayer(HERE + "/data/grid.gpkg|layername=hex_centroids", "c", "ogr")
hexes = sorted(f["hex_id"] for f in cent.getFeatures())

# ---- stops: distances + frequency ----
sid = sorted(stops)
pt = [to2180.transform(QgsPointXY(*stops[s])) for s in sid]
dist_stops = walk_matrix(cent, points_layer("stops", [(p.x(), p.y()) for p in pt]), "stops")
out = {h: {} for h in hexes}
for h in hexes:
    ds = dist_stops.get(h, {})
    for m in ("tram", "bus"):
        v = [dd for p, dd in ds.items() if stop_mode[sid[p]] == m]
        out[h]["d_%s_m" % m] = min(v) if v else None

radius = cfg["frequency"]["radius_m"]
sidx = {s: i for i, s in enumerate(sid)}
by_pid = collections.defaultdict(list)
for (s, rt, dr) in deps:
    by_pid[sidx[s]].append((rt, dr))


def dep_per_hour(minutes, wname):
    a, b = hm(tw[wname]["start"]), hm(tw[wname]["end"])
    return sum(1 for x in minutes if a <= x < b) / ((b - a) / 60)


for h in hexes:
    best = {}  # (route, dir) -> (dist, pid): one line counted once, at its nearest stop
    for p, dd in dist_stops.get(h, {}).items():
        if dd > radius:
            continue
        for k in by_pid[p]:
            if k not in best or dd < best[k][0]:
                best[k] = (dd, p)
    for m in ("tram", "bus"):
        for w in tw:
            out[h]["freq_%s_%s" % (m, w)] = round(sum(
                dep_per_hour(deps[(sid[p], rt, dr)], w)
                for (rt, dr), (dd, p) in best.items() if stop_mode[sid[p]] == m), 2)

# ---- green: OSM polygons >= min area, densified boundary vertices as entrances ----
g = QgsVectorLayer(HERE + "/data/raw/lodz.osm.pbf|layername=multipolygons", "mp", "ogr")
g.setSubsetString(cfg["green"]["osm_filter"])
g = processing.run("native:reprojectlayer", {"INPUT": g, "TARGET_CRS": R, "OUTPUT": "memory:"})["OUTPUT"]
g = processing.run("native:fixgeometries", {"INPUT": g, "OUTPUT": "memory:"})["OUTPUT"]  # OSM multipolygons can be invalid
g = processing.run("native:extractbyexpression", {
    "INPUT": g, "EXPRESSION": "$area >= %s" % (cfg["green"]["min_area_ha"] * 10000),
    "OUTPUT": "memory:"})["OUTPUT"]
n_green = g.featureCount()
# simplified polygons (WGS84) for the web basemap
gw = processing.run("native:reprojectlayer", {"INPUT": g, "TARGET_CRS": W, "OUTPUT": "memory:"})["OUTPUT"]
gw = processing.run("native:simplifygeometries", {"INPUT": gw, "METHOD": 0, "TOLERANCE": 0.00005, "OUTPUT": "memory:"})["OUTPUT"]
from qgis.core import QgsVectorFileWriter
_o = QgsVectorFileWriter.SaveVectorOptions()
_o.driverName = "GeoJSON"
_o.attributesAsDisplayedValues = False
_o.layerOptions = ["COORDINATE_PRECISION=5"]
_o.attributes = []
QgsVectorFileWriter.writeAsVectorFormatV3(gw, str(out_dir / "green.geojson"), QgsProject.instance().transformContext(), _o)
dens = processing.run("native:densifygeometriesgivenaninterval", {
    "INPUT": g, "INTERVAL": cfg["green"]["boundary_spacing_m"], "OUTPUT": "memory:"})["OUTPUT"]
vtx = processing.run("native:extractvertices", {"INPUT": dens, "OUTPUT": "memory:"})["OUTPUT"]
gp = points_layer("green_pts", [(f.geometry().asPoint().x(), f.geometry().asPoint().y())
                                for f in vtx.getFeatures()])
dist_g = walk_matrix(cent, gp, "green")
for h in hexes:
    v = list(dist_g.get(h, {}).values())
    out[h]["d_green_m"] = min(v) if v else None

cols = ["hex_id", "d_tram_m", "d_bus_m", "d_green_m"] + [
    "freq_%s_%s" % (m, w) for m in ("tram", "bus") for w in tw]
with open(out_dir / "static_layers.csv", "w", newline="", encoding="utf-8") as fh:
    wr = csv.writer(fh)
    wr.writerow(cols)
    for h in hexes:
        wr.writerow([h] + ["" if out[h].get(c) is None else out[h][c] for c in cols[1:]])
meta = {"layers_version": cfg["layers_version"],
        "grid_version": json.load(open(HERE + "/data/grid.meta.json"))["grid_version"],
        "day": day, "active_trips": len(trips), "stops": len(sid), "green_polygons": n_green,
        "green_points": gp.featureCount(), "walk_resolution_m": cfg["walk"]["speed_kmh"] * 1000 / 60}
json.dump(meta, open(out_dir / "static_layers.meta.json", "w"), indent=1)
print(json.dumps(meta))
