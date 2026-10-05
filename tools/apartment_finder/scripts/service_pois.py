"""S1: daily-service POIs from our own OSM extract -> data/services/poi.gpkg (+ inputs/service_pois.csv).

Fine facility types of config/services.yaml (grouped into 4 meta-categories at export time). Pattern from lodzkie_na_mapach_2026/prepare_poi.py: OGR
`points` (tags packed in other_tags) + `multipolygons` (polygon -> centroid), a node inside a polygon of the same
criterion is dropped as a duplicate. Kept: everything inside the city or within `buffer_m` of it (hexes at the border
reach facilities just across the boundary; the exact R5 method can use them). Run with QGIS's interpreter.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
from qgis.core import QgsVectorFileWriter, QgsVectorLayer  # noqa: E402

cfg = yaml.safe_load(open(HERE / "config/services.yaml", encoding="utf-8"))
PBF = str(HERE / "data/raw/lodz.osm.pbf")
OUT = HERE / "data/services"
OUT.mkdir(parents=True, exist_ok=True)
DEDICATED = {"amenity", "shop", "leisure", "office", "tourism"}   # real columns in the OGR multipolygons layer; others live in other_tags


def tag_expr(key, val, polygons):
    if polygons and key in DEDICATED:
        return '"%s" = \'%s\'' % (key, val)
    return '"other_tags" LIKE \'%%"%s"=>"%s"%%\'' % (key, val)


def expr(crit, polygons):
    return " OR ".join(tag_expr(k, v, polygons) for k, v in cfg["types"][crit])


mp = processing.run("native:fixgeometries", {"INPUT": QgsVectorLayer(PBF + "|layername=multipolygons", "mp", "ogr"),
                                              "OUTPUT": "memory:"})["OUTPUT"]
pts = QgsVectorLayer(PBF + "|layername=points", "pts", "ogr")
grid = QgsVectorLayer(str(HERE / "data/grid.gpkg") + "|layername=hex_grid", "g", "ogr")
city = processing.run("native:fixgeometries", {"INPUT": processing.run("native:dissolve", {"INPUT": grid, "OUTPUT": "memory:"})["OUTPUT"], "OUTPUT": "memory:"})["OUTPUT"]
area = processing.run("native:buffer", {"INPUT": city, "DISTANCE": cfg["buffer_m"], "SEGMENTS": 8, "OUTPUT": "memory:"})["OUTPUT"]


def run(alg, **kw):
    kw.setdefault("OUTPUT", "memory:")
    return processing.run(alg, kw)["OUTPUT"]


def to_2180(lyr):
    return run("native:reprojectlayer", INPUT=lyr, TARGET_CRS="EPSG:2180")


rows = []
for crit in cfg["types"]:
    poly = run("native:extractbyexpression", INPUT=mp, EXPRESSION=expr(crit, True))
    cent = run("native:centroids", INPUT=poly, ALL_PARTS=False) if poly.featureCount() else poly
    node = run("native:extractbyexpression", INPUT=pts, EXPRESSION=expr(crit, False))
    if poly.featureCount():
        node = run("native:extractbylocation", INPUT=node, PREDICATE=[2], INTERSECT=poly)   # disjoint = not inside a counted polygon
    for lyr in (cent, node):
        if lyr.featureCount() == 0:
            continue
        lyr2 = to_2180(lyr)
        inbuf = run("native:extractbylocation", INPUT=lyr2, PREDICATE=[0], INTERSECT=area)
        wgs = run("native:reprojectlayer", INPUT=inbuf, TARGET_CRS="EPSG:4326")
        names = wgs.fields().names()
        for f in wgs.getFeatures():
            g = f.geometry().asPoint()
            rows.append({"crit": crit, "lon": round(g.x(), 6), "lat": round(g.y(), 6),
                         "name": (f["name"] if "name" in names and f["name"] else ""), "in_city": 0})
    print(crit, sum(1 for r in rows if r["crit"] == crit))

# in_city flag + stable ids: the points are tested against the (EPSG:2180) city outline; the output layer is WGS84
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsGeometry, QgsPointXY,  # noqa: E402
                       QgsProject)
tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateReferenceSystem("EPSG:2180"), QgsProject.instance())
city_geom = QgsGeometry.unaryUnion([f.geometry() for f in city.getFeatures()]).makeValid()
pl = QgsVectorLayer("Point?crs=EPSG:4326&field=poi_id:string&field=crit:string&field=name:string&field=in_city:integer", "poi", "memory")
feats = []
for i, r in enumerate(rows):
    r["poi_id"] = "%s/%d" % (r["crit"], i)
    r["in_city"] = 1 if city_geom.contains(QgsGeometry.fromPointXY(tr.transform(QgsPointXY(r["lon"], r["lat"])))) else 0
    f = QgsFeature(pl.fields())
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(r["lon"], r["lat"])))
    f.setAttributes([r["poi_id"], r["crit"], r["name"], r["in_city"]])
    feats.append(f)
pl.dataProvider().addFeatures(feats)
opts = QgsVectorFileWriter.SaveVectorOptions()
opts.driverName = "GPKG"
opts.layerName = "poi"
QgsVectorFileWriter.writeAsVectorFormatV3(pl, str(OUT / "poi.gpkg"), pl.transformContext(), opts)
with open(HERE / "inputs/service_pois.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["poi_id", "crit", "lon", "lat", "name", "in_city"])
    w.writeheader()
    w.writerows(rows)
c = Counter((r["crit"], r["in_city"]) for r in rows)
print("POI by criterion (in city / buffer):", {k: (c[(k, 1)], c[(k, 0)]) for k in cfg["types"]})
