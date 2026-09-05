"""Data prep for the realized-GTFS delay analysis (Lodz).

Answers: where in the city do GTFS-RT delays hurt reachability the most, by
comparing accessibility (points reachable within 30 min) computed on the
*static* schedule vs the *realized P50* schedule for the same real day.

Entirely on Easy-R5's own Processing algorithms (`easyr5:buildnetwork`,
`easyr5:populationoverlay`) + native QGIS algorithms + stdlib -- no R/r5r, no
Overpass API call at runtime, no pip. POI categories are extracted straight
from the already-downloaded `.osm.pbf` via QGIS's own OGR OSM driver.

Must run inside the QGIS Python environment (qgis.core + processing + the
easy_r5 plugin registered) -- e.g. `mcp__qgis__execute_code`. A plain
`py prepare_data.py` has no qgis.core.

Reads (read-only, from prior sessions' downloads -- never modified):
  tools/accessibility_lodz/lodz.osm.pbf
  tools/accessibility_lodz/lodz_static_gtfs_2026-08-21.zip
  tools/accessibility_lodz/lodz_realized_2026-08-21_p50.zip
  tools/accessibility_lodz/lodz_universities.csv
  tools/ses_income_lodz/lodz.gpkg (layer obwody_spisowe)

Writes (all gitignored):
  gtfs_static/, gtfs_realized_p50/ -- copied GTFS zips, one variant per folder
  network_static/, network_realized_p50/ -- R5 network caches
  delay_lodz.gpkg -- layers hex_grid, hex_centroids, poi_targets
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

try:
    import processing
    from qgis.core import (
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
        QgsPointXY,
        QgsProcessing,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "prepare_data.py needs qgis.core + processing. Run it inside the QGIS "
        "Python console or via mcp__qgis__execute_code."
    ) from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ACC = REPO / "tools" / "accessibility_lodz"
SES = REPO / "tools" / "ses_income_lodz"

GTFS_STATIC_SRC = ACC / "lodz_static_gtfs_2026-08-21.zip"
GTFS_REALIZED_SRC = ACC / "lodz_realized_2026-08-21_p50.zip"
GTFS_STATIC_DIR = HERE / "gtfs_static"
GTFS_REALIZED_DIR = HERE / "gtfs_realized_p50"
NETWORK_STATIC_DIR = HERE / "network_static"
NETWORK_REALIZED_DIR = HERE / "network_realized_p50"
OUT_GPKG = HERE / "delay_lodz.gpkg"

ANALYSIS_DATE = "2026-08-21"
# Verified directly (zipfile/csv) on both feeds before writing this script:
# calendar_dates.txt maps 2026-08-21 to service_id 11493_11 in both, and the
# trip_id sets for that service are IDENTICAL between static and realized_p50
# (realized = rewritten times for the same trips, not a different service).
EXPECTED_TRIPS = 9893
POP_TOLERANCE = 0.01
HEX_SPACING_M = 250

CATEGORY_TAGS = {
    # category -> (osm key, osm value) as tagged on multipolygons' dedicated
    # column and inside points' other_tags hstore string.
    "school": ("amenity", "school"),
    "pharmacy": ("amenity", "pharmacy"),
    "mall": ("shop", "mall"),
}
CATEGORIES = ("school", "pharmacy", "university", "mall")


def _run(alg, params, out="OUTPUT"):
    return processing.run(alg, params)[out]


def copy_gtfs(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    zips = sorted(dst_dir.glob("*.zip"))
    if len(zips) != 1:
        raise RuntimeError(f"{dst_dir} must hold exactly one feed, found {zips}")
    return dst


def build_network(gtfs_dir: Path, cache_dir: Path, label: str):
    result = processing.run("easyr5:buildnetwork", {
        "OSM_PBF": str(ACC / "lodz.osm.pbf"),
        "GTFS_FOLDER": str(gtfs_dir),
        "CACHE_FOLDER": str(cache_dir),
        "FORCE_REBUILD": False,
    })
    summary = json.loads(Path(result["NETWORK_JSON"]).read_text(encoding="utf-8"))
    trips = (summary.get("service_days") or {}).get(ANALYSIS_DATE)
    if trips != EXPECTED_TRIPS:
        raise RuntimeError(
            f"GATE FAILED ({label}): {ANALYSIS_DATE} has {trips} active trips in "
            f"network.json, expected {EXPECTED_TRIPS}. Stopping."
        )
    print(f"[gate OK] {label}: {ANALYSIS_DATE} has {trips} active trips.")
    return result


def build_networks():
    copy_gtfs(GTFS_STATIC_SRC, GTFS_STATIC_DIR)
    copy_gtfs(GTFS_REALIZED_SRC, GTFS_REALIZED_DIR)
    static = build_network(GTFS_STATIC_DIR, NETWORK_STATIC_DIR, "static")
    realized = build_network(GTFS_REALIZED_DIR, NETWORK_REALIZED_DIR, "realized_p50")
    return static, realized


def build_boundary_and_grid():
    obwody = QgsVectorLayer(f"{SES / 'lodz.gpkg'}|layername=obwody_spisowe", "obwody_spisowe", "ogr")
    if not obwody.isValid():
        raise RuntimeError("Could not load obwody_spisowe from ses_income_lodz/lodz.gpkg")
    if obwody.crs().isGeographic():
        raise RuntimeError(f"obwody_spisowe CRS ({obwody.crs().description()}) is geographic.")

    boundary = _run("native:dissolve", {
        "INPUT": obwody, "FIELD": [], "SEPARATE_DISJOINT": False,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    grid = _run("native:creategrid", {
        "TYPE": 4,  # Hexagon (Polygon)
        "EXTENT": boundary.extent(),
        "HSPACING": HEX_SPACING_M, "VSPACING": HEX_SPACING_M,
        "HOVERLAY": 0, "VOVERLAY": 0,
        "CRS": obwody.crs(),
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    clipped = _run("native:extractbylocation", {
        "INPUT": grid, "PREDICATE": [0], "INTERSECT": boundary,  # intersect
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    with_id = _run("native:fieldcalculator", {
        "INPUT": clipped, "FIELD_NAME": "hex_id", "FIELD_TYPE": 1,
        "FIELD_LENGTH": 10, "FIELD_PRECISION": 0, "FORMULA": "@row_number",
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    hex_grid_bare = _run("native:retainfields", {
        "INPUT": with_id, "FIELDS": ["hex_id"], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    print(f"[ok] hex_grid_bare (hexagon, {HEX_SPACING_M} m): {hex_grid_bare.featureCount()} features")
    return obwody, hex_grid_bare


def overlay_population(obwody, hex_grid_bare):
    obwody_null = _run("native:extractbyexpression", {
        "INPUT": obwody, "EXPRESSION": '"population" IS NULL',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    obwody_valid = _run("native:extractbyexpression", {
        "INPUT": obwody, "EXPRESSION": '"population" IS NOT NULL',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    precinct_pop_sum = sum(f["population"] for f in obwody_valid.getFeatures())
    print(f"[info] {obwody_null.featureCount()} precincts have population=NULL (GUS suppression), excluded.")

    overlaid = processing.run("easyr5:populationoverlay", {
        "HEX_GRID": hex_grid_bare, "POPULATION_LAYER": obwody_valid,
        "POPULATION_FIELD": "population", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })["OUTPUT"]

    renamed = _run("native:fieldcalculator", {
        "INPUT": overlaid, "FIELD_NAME": "pop_total", "FIELD_TYPE": 0,
        "FIELD_LENGTH": 10, "FIELD_PRECISION": 2, "FORMULA": '"population"',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    hex_pop = _run("native:retainfields", {
        "INPUT": renamed, "FIELDS": ["hex_id", "pop_total"],
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    hex_pop_sum = sum(f["pop_total"] or 0 for f in hex_pop.getFeatures())
    hex_with_pop = sum(1 for f in hex_pop.getFeatures() if (f["pop_total"] or 0) > 0)
    diff_pct = abs(hex_pop_sum - precinct_pop_sum) / precinct_pop_sum
    print(f"[check] sum(pop_total) over hexagons = {hex_pop_sum:.1f}")
    print(f"[check] sum(population) over precincts (non-NULL) = {precinct_pop_sum:.1f}")
    print(f"[check] relative difference = {diff_pct:.4%} (tolerance {POP_TOLERANCE:.0%})")
    if diff_pct > POP_TOLERANCE:
        raise RuntimeError(f"GATE FAILED: population overlay off by {diff_pct:.2%}. Stopping.")
    if hex_with_pop == 0:
        raise RuntimeError("GATE FAILED: 0 hexagons have pop_total > 0 -- overlay did not work.")
    print(f"[check] hexagons with pop_total > 0: {hex_with_pop} / {hex_pop.featureCount()}")
    return hex_pop


def _category_points_from_pbf(pbf_layer_pts, pbf_layer_mp, key, value):
    """Points tagged key=value, plus centroids of matching polygons, deduped:
    a point that falls on/inside a matching polygon is dropped in favour of
    the polygon centroid (schools/malls are usually mapped as building
    outlines; a node on the same building would double-count it)."""
    mp_match = _run("native:extractbyexpression", {
        "INPUT": pbf_layer_mp, "EXPRESSION": f'"{key}" = \'{value}\'',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    mp_centroids = _run("native:centroids", {
        "INPUT": mp_match, "ALL_PARTS": False, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    pts_match = _run("native:extractbyexpression", {
        "INPUT": pbf_layer_pts,
        "EXPRESSION": f'"other_tags" LIKE \'%"{key}"=>"{value}"%\'',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    pts_standalone = _run("native:extractbylocation", {
        "INPUT": pts_match, "PREDICATE": [2], "INTERSECT": mp_match,  # disjoint
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    print(f"    {value}: {mp_match.featureCount()} polygons + {pts_standalone.featureCount()} "
          f"standalone points ({pts_match.featureCount() - pts_standalone.featureCount()} points "
          "deduped against polygons)")
    return mp_centroids, pts_standalone


def build_poi_layer():
    """poi_targets: category points, one-hot srv_<category> fields for
    RunAccessibility's OPPORTUNITY_FIELDS."""
    pbf = str(ACC / "lodz.osm.pbf")
    pts = QgsVectorLayer(f"{pbf}|layername=points", "pts", "ogr")
    mp = QgsVectorLayer(f"{pbf}|layername=multipolygons", "mp", "ogr")
    if not pts.isValid() or not mp.isValid():
        raise RuntimeError("Could not load points/multipolygons layers from lodz.osm.pbf")

    fields = QgsFields()
    fields.append(QgsField("poi_id", QVariant.String))
    fields.append(QgsField("name", QVariant.String))
    fields.append(QgsField("category", QVariant.String))
    for cat in CATEGORIES:
        fields.append(QgsField(f"srv_{cat}", QVariant.Int))

    mem = QgsVectorLayer("Point?crs=EPSG:4326", "poi_targets", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    counts = {cat: 0 for cat in CATEGORIES}

    def add_feature(geom, poi_id, name, category):
        feat = QgsFeature(mem.fields())
        feat.setGeometry(geom)
        feat["poi_id"] = poi_id
        feat["name"] = name or ""
        feat["category"] = category
        for cat in CATEGORIES:
            feat[f"srv_{cat}"] = 1 if cat == category else 0
        mem.dataProvider().addFeature(feat)
        counts[category] += 1

    print("[poi] extracting school / pharmacy / mall from lodz.osm.pbf:")
    for category, (key, value) in CATEGORY_TAGS.items():
        mp_centroids, pts_standalone = _category_points_from_pbf(pts, mp, key, value)
        for f in mp_centroids.getFeatures():
            # GDAL's OSM multipolygons layer: relations use osm_id, way-based
            # polygons (the common case for a single building) use osm_way_id
            # and leave osm_id NULL -- fall back so poi_id stays unique.
            mp_id = f["osm_id"] if f["osm_id"] not in (None, "NULL") else f"w{f['osm_way_id']}"
            add_feature(f.geometry(), f"mp/{mp_id}", f["name"], category)
        for f in pts_standalone.getFeatures():
            add_feature(f.geometry(), f"pt/{f['osm_id']}", f["name"], category)

    uni_csv = ACC / "lodz_universities.csv"
    with open(uni_csv, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            geom = QgsGeometry.fromPointXY(QgsPointXY(float(row["lon"]), float(row["lat"])))
            add_feature(geom, f"{row['osm_type']}/{row['osm_id']}", row["name"] or row["university"], "university")

    print(f"[check] POI counts per category: {counts}")
    for cat, n in counts.items():
        if n < 5:
            raise RuntimeError(f"GATE FAILED: category {cat!r} has only {n} POI -- OSM filter likely wrong.")
    return mem


def write_gpkg(hex_grid, hex_centroids, poi_targets):
    if OUT_GPKG.exists():
        OUT_GPKG.unlink()
    layers = [
        ("hex_grid", hex_grid),
        ("hex_centroids", hex_centroids),
        ("poi_targets", poi_targets),
    ]
    for i, (name, layer) in enumerate(layers):
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = name
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if i == 0
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        err = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(OUT_GPKG), layer.transformContext(), opts)
        if err[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Failed to write layer {name}: {err}")
    print(f"[ok] wrote {OUT_GPKG} with layers: {[n for n, _ in layers]}")


def main():
    build_networks()
    obwody, hex_grid_bare = build_boundary_and_grid()
    hex_pop = overlay_population(obwody, hex_grid_bare)
    hex_centroids = _run("native:centroids", {
        "INPUT": hex_pop, "ALL_PARTS": False, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    poi_targets = build_poi_layer()
    write_gpkg(hex_pop, hex_centroids, poi_targets)
    print("[done] prepare_data.py finished.")


if __name__ == "__main__":
    main()
