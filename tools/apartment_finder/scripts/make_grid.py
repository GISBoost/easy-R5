"""Build the 250 m hex grid + centroids for Lodz (PRD 5.1, M0/M1).

Recipe from tools/realtime_delay_lodz/prepare_data.py (native:creategrid hexagon),
but cells are kept by centre-in-city and hex_id is contiguous 0..N-1. Copied, not imported (CLAUDE.md).
Run with QGIS python: see _qgis_env.py.
"""
import json, math, sys
HERE = __file__.replace("\\", "/").rsplit("/", 2)[0]
sys.path.insert(0, HERE + "/scripts")
import warnings; warnings.simplefilter("ignore")
import _qgis_env; app = _qgis_env.start()
import processing, yaml
from qgis.core import QgsVectorLayer, QgsCoordinateReferenceSystem, QgsProcessing, QgsVectorFileWriter, QgsProject

cfg = yaml.safe_load(open(HERE + "/config/grid.yaml", encoding="utf-8"))
src, layer = (HERE + "/" + cfg["boundary_source"]).split("|layername=")
boundary = QgsVectorLayer(f"{src}|layername={layer}", "boundary", "ogr")
crs = QgsCoordinateReferenceSystem(cfg["crs"])
if boundary.crs() != crs and boundary.crs().isValid():
    boundary = processing.run("native:reprojectlayer", {"INPUT": boundary, "TARGET_CRS": crs, "OUTPUT": "memory:"})["OUTPUT"]
run = lambda a, p: processing.run(a, {**p, "OUTPUT": "memory:"})["OUTPUT"]
s = cfg["spacing_m"]
grid = run("native:creategrid", {"TYPE": 4, "EXTENT": boundary.extent(), "HSPACING": s, "VSPACING": s,
                                 "HOVERLAY": 0, "VOVERLAY": 0, "CRS": crs})
# Keep cells whose CENTRE lies inside the city (PRD 5.1: city only, no neighbouring gminas).
bgeom = next(boundary.getFeatures()).geometry()
keep = [f.id() for f in grid.getFeatures() if bgeom.contains(f.geometry().centroid())]
grid = run("native:extractbyexpression", {"INPUT": grid, "EXPRESSION": "$id IN (%s)" % ",".join(map(str, keep))})
grid = run("native:fieldcalculator", {"INPUT": grid, "FIELD_NAME": "hex_id", "FIELD_TYPE": 1,
                                      "FIELD_LENGTH": 10, "FIELD_PRECISION": 0, "FORMULA": "@row_number"})
grid = run("native:retainfields", {"INPUT": grid, "FIELDS": ["hex_id"]})
cent = run("native:centroids", {"INPUT": grid})
out = HERE + "/data/grid.gpkg"
for lyr, name in ((grid, "hex_grid"), (cent, "hex_centroids")):
    o = QgsVectorFileWriter.SaveVectorOptions(); o.driverName = "GPKG"; o.layerName = name
    o.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer if name != "hex_grid" else QgsVectorFileWriter.CreateOrOverwriteFile
    err = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out, QgsProject.instance().transformContext(), o)
    assert err[0] == 0, err
# nearest-neighbour centre spacing + share of centroids inside the boundary
pts = [f.geometry().asPoint() for f in cent.getFeatures()]
d = min(math.dist((pts[0].x(), pts[0].y()), (p.x(), p.y())) for p in pts[1:])
inside = processing.run("native:extractbylocation", {"INPUT": cent, "PREDICATE": [6], "INTERSECT": boundary, "OUTPUT": "memory:"})["OUTPUT"].featureCount()
rep = {"grid_version": cfg["grid_version"], "hexes": grid.featureCount(), "centroids_inside_boundary": inside,
       "nn_centre_spacing_m": round(d, 1), "pairs_millions": round(grid.featureCount() ** 2 / 1e6, 1)}
print(json.dumps(rep)); json.dump(rep, open(HERE + "/data/grid.meta.json", "w"), indent=1)
