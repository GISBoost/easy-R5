"""M-C0: OSM building footprints from our own PBF -> data/canopy/osm_buildings.gpkg (EPSG:2180). Run with QGIS's interpreter.
Stand-in for BDOT10k buildings (the canopy mask must exclude roofs); BDOT10k replaces it if Michal prefers (decision C7)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import _qgis_env  # noqa: E402

app = _qgis_env.start()
import processing  # noqa: E402
from qgis.core import QgsVectorLayer  # noqa: E402

mp = QgsVectorLayer(str(HERE / "data/raw/lodz.osm.pbf") + "|layername=multipolygons", "mp", "ogr")
b = processing.run("native:extractbyexpression", {"INPUT": mp, "EXPRESSION": '"building" IS NOT NULL', "OUTPUT": "memory:"})["OUTPUT"]
b = processing.run("native:fixgeometries", {"INPUT": b, "OUTPUT": "memory:"})["OUTPUT"]
out = HERE / "data/canopy/osm_buildings.gpkg"
processing.run("native:reprojectlayer", {"INPUT": b, "TARGET_CRS": "EPSG:2180", "OUTPUT": str(out)})
print("buildings", b.featureCount(), "->", out)
