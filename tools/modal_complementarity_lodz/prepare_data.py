"""F2 -- data prep for the flagship Lodz modal-complementarity analysis.

Builds the ONE network, ONE origins/destinations layer set, and ONE set of
opportunity fields that all four F3 accessibility runs (W / T / B / TB) share.
See docs/prd/PR_easy-R5_flagship-lodz-modal.md SS3, SS4.3, SS9 F2.

Must run inside the QGIS Python environment (qgis.core + processing + the
easy_r5 plugin registered) -- e.g. the QGIS Python console, or
`mcp__qgis__execute_code`. A plain `py prepare_data.py` has no qgis.core.

Run against a fresh/empty QGIS project. Re-running it against a project that
already accumulated this script's own TEMPORARY_OUTPUT layers from a prior run
in the same session has been observed to corrupt the population-density field
calculator step (spurious NaN) -- a QGIS processing-context artifact, not a
data problem. `mcp__qgis__create_new_project` (or File > New) before each run
avoids it.

Reads (read-only -- never modified, never copied except the GTFS zip):
  tools/accessibility_lodz/lodz.osm.pbf
  tools/accessibility_lodz/lodz_static_gtfs_2026-08-21.zip
  tools/accessibility_lodz/lodz_hex500.gpkg (layer hex500)
  tools/accessibility_lodz/lodz_services.csv
  tools/ses_income_lodz/lodz.gpkg (layer obwody_spisowe)

Writes (all gitignored):
  gtfs_static/lodz_static_gtfs_2026-08-21.zip
  network_static/<hash>/network.dat, network.json
  lodz_modal.gpkg -- layers hex_grid, hex_centroids, hex_destinations,
                     poi_destinations
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
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover -- guard for plain `py` runs
    raise SystemExit(
        "prepare_data.py needs qgis.core + processing. Run it inside the QGIS "
        "Python console or via mcp__qgis__execute_code, not a plain Python "
        "interpreter."
    ) from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ACC = REPO / "tools" / "accessibility_lodz"
SES = REPO / "tools" / "ses_income_lodz"

GTFS_SRC = ACC / "lodz_static_gtfs_2026-08-21.zip"
GTFS_DIR = HERE / "gtfs_static"
NETWORK_DIR = HERE / "network_static"
OUT_GPKG = HERE / "lodz_modal.gpkg"

TRIPS_DATE = "2026-08-24"
EXPECTED_TRIPS = 9893
PILOT_HEX_WITH_POP = 640
EXPECTED_POI = 1328
POP_TOLERANCE = 0.01
CATEGORIES = ("education", "health", "culture", "groceries")


def copy_gtfs():
    GTFS_DIR.mkdir(exist_ok=True)
    dst = GTFS_DIR / GTFS_SRC.name
    if not dst.exists():
        shutil.copy2(GTFS_SRC, dst)
    zips = sorted(GTFS_DIR.glob("*.zip"))
    if len(zips) != 1:
        raise RuntimeError(f"gtfs_static/ must hold exactly one feed, found {zips}")
    return dst


def build_network():
    result = processing.run("easyr5:buildnetwork", {
        "OSM_PBF": str(ACC / "lodz.osm.pbf"),
        "GTFS_FOLDER": str(GTFS_DIR),
        "CACHE_FOLDER": str(NETWORK_DIR),
        "FORCE_REBUILD": False,
    })
    summary = json.loads(Path(result["NETWORK_JSON"]).read_text(encoding="utf-8"))
    trips = (summary.get("service_days") or {}).get(TRIPS_DATE)
    if trips != EXPECTED_TRIPS:
        raise RuntimeError(
            f"GATE FAILED: {TRIPS_DATE} has {trips} active trips in network.json, "
            f"expected {EXPECTED_TRIPS}. Stopping -- do not proceed to F3."
        )
    print(f"[gate OK] network: {TRIPS_DATE} has {trips} active trips.")
    return result


def _run(alg, params):
    return processing.run(alg, params)["OUTPUT"]


def build_hex_layers():
    """Clean hex_id-only polygon layer from the 74-column pilot hex500."""
    hex500 = QgsVectorLayer(f"{ACC / 'lodz_hex500.gpkg'}|layername=hex500", "hex500", "ogr")
    if not hex500.isValid():
        raise RuntimeError("Could not load hex500 layer from lodz_hex500.gpkg")
    hex_grid_bare = _run("native:retainfields", {
        "INPUT": hex500, "FIELDS": ["hex_id"], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    print(f"[ok] hex_grid_bare: {hex_grid_bare.featureCount()} features (expect 1479)")
    return hex_grid_bare


def overlay_population(hex_grid_bare):
    obwody = QgsVectorLayer(f"{SES / 'lodz.gpkg'}|layername=obwody_spisowe", "obwody_spisowe", "ogr")
    if not obwody.isValid():
        raise RuntimeError("Could not load obwody_spisowe layer from ses_income_lodz/lodz.gpkg")
    if obwody.crs().isGeographic():
        raise RuntimeError(
            f"obwody_spisowe CRS ({obwody.crs().authid()}) is geographic -- "
            "geometry().area() below would be in degrees^2, not m^2."
        )

    obwody_null = _run("native:extractbyexpression", {
        "INPUT": obwody, "EXPRESSION": '"population" IS NULL',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    null_area_km2 = sum(f.geometry().area() for f in obwody_null.getFeatures()) / 1e6
    print(
        f"[info] {obwody_null.featureCount()} precincts have population=NULL "
        f"(GUS suppression), covering {null_area_km2:.2f} km2 -- excluded, not zeroed."
    )

    obwody_valid = _run("native:extractbyexpression", {
        "INPUT": obwody, "EXPRESSION": '"population" IS NOT NULL',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    precinct_pop_sum = sum(f["population"] for f in obwody_valid.getFeatures())

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
        raise RuntimeError(
            f"GATE FAILED: population overlay off by {diff_pct:.2%}, exceeds "
            f"{POP_TOLERANCE:.0%} tolerance. Stopping."
        )
    print(f"[check] hexagons with pop_total > 0: {hex_with_pop} (pilot point-in-polygon: {PILOT_HEX_WITH_POP})")
    if hex_with_pop <= PILOT_HEX_WITH_POP:
        raise RuntimeError(
            f"GATE FAILED: only {hex_with_pop} hexagons have pop_total > 0, not "
            f"significantly more than the {PILOT_HEX_WITH_POP}-hex pilot. The "
            "area-weighted overlay likely did not work -- stopping."
        )
    return hex_pop, {
        "precinct_pop_sum": precinct_pop_sum,
        "hex_pop_sum": hex_pop_sum,
        "diff_pct": diff_pct,
        "hex_with_pop": hex_with_pop,
        "null_precincts": obwody_null.featureCount(),
        "null_area_km2": null_area_km2,
    }


def build_poi_layer():
    """poi_destinations: exact POI points, srv_total=1 + one-hot per category."""
    fields = QgsFields()
    fields.append(QgsField("poi_id", QVariant.String))
    fields.append(QgsField("category", QVariant.String))
    fields.append(QgsField("name", QVariant.String))
    fields.append(QgsField("srv_total", QVariant.Int))
    for cat in CATEGORIES:
        fields.append(QgsField(f"srv_{cat}", QVariant.Int))

    mem = QgsVectorLayer("Point?crs=EPSG:4326", "poi_destinations", "memory")
    provider = mem.dataProvider()
    provider.addAttributes(fields)
    mem.updateFields()

    feats = []
    with open(ACC / "lodz_services.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cat = row["category"]
            if cat not in CATEGORIES:
                raise RuntimeError(
                    f"lodz_services.csv row {row!r} has category {cat!r}, not one of "
                    f"{CATEGORIES} -- would silently vanish from the per-category fields."
                )
            feat = QgsFeature(mem.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(row["lon"]), float(row["lat"]))))
            values = {
                "poi_id": f'{row["osm_type"]}/{row["osm_id"]}',
                "category": cat, "name": row.get("name", ""), "srv_total": 1,
            }
            for c in CATEGORIES:
                values[f"srv_{c}"] = 1 if c == cat else 0
            feat.setAttributes([values[f.name()] for f in mem.fields()])
            feats.append(feat)
    provider.addFeatures(feats)
    mem.updateExtents()
    if mem.featureCount() != EXPECTED_POI:
        raise RuntimeError(f"lodz_services.csv has {mem.featureCount()} rows, expected {EXPECTED_POI}")
    return mem


def overlay_services(hex_pop, poi_wgs84, hex_crs):
    poi_projected = _run("native:reprojectlayer", {
        "INPUT": poi_wgs84, "TARGET_CRS": hex_crs, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    dissolved = _run("native:dissolve", {
        "INPUT": hex_pop, "FIELD": [], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    poi_outside = _run("native:extractbylocation", {
        "INPUT": poi_projected, "PREDICATE": [2], "INTERSECT": dissolved,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    if poi_outside.featureCount():
        names = [f"{f['category']}/{f['name']}" for f in poi_outside.getFeatures()]
        print(f"[warn] {poi_outside.featureCount()} POI outside the hex grid boundary: {names}")
    else:
        print("[check] 0 POI outside the hex grid boundary.")

    poi_inside = _run("native:extractbylocation", {
        "INPUT": poi_projected, "PREDICATE": [0], "INTERSECT": dissolved,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    hex_full = hex_pop
    for cat in CATEGORIES:
        cat_points = _run("native:extractbyexpression", {
            "INPUT": poi_inside, "EXPRESSION": f"\"category\" = '{cat}'",
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        })
        hex_full = _run("native:countpointsinpolygon", {
            "POLYGONS": hex_full, "POINTS": cat_points, "WEIGHT": None,
            "CLASSFIELD": None, "FIELD": f"srv_{cat}", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        })
    hex_full = _run("native:countpointsinpolygon", {
        "POLYGONS": hex_full, "POINTS": poi_inside, "WEIGHT": None,
        "CLASSFIELD": None, "FIELD": "srv_total", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    srv_total_sum = sum(f["srv_total"] or 0 for f in hex_full.getFeatures())
    print(f"[check] sum(srv_total) over hexagons = {srv_total_sum} (expect {EXPECTED_POI})")
    if srv_total_sum != EXPECTED_POI:
        raise RuntimeError(
            f"GATE FAILED: sum(srv_total) = {srv_total_sum}, expected {EXPECTED_POI} "
            f"({poi_outside.featureCount()} POI outside boundary). Stopping."
        )

    # srv_total alone would not catch a category mismatch (each category one-hot
    # sums independently) -- cross-check the four category sums add up too.
    cat_sums = {cat: sum(f[f"srv_{cat}"] or 0 for f in hex_full.getFeatures()) for cat in CATEGORIES}
    cat_sum_total = sum(cat_sums.values())
    print(f"[check] sum of per-category fields = {cat_sum_total} {cat_sums} (expect {EXPECTED_POI})")
    if cat_sum_total != EXPECTED_POI:
        raise RuntimeError(
            f"GATE FAILED: category fields sum to {cat_sum_total}, expected {EXPECTED_POI} "
            f"({cat_sums}) -- a POI likely has a category outside {CATEGORIES}. Stopping."
        )
    return hex_full


def write_gpkg(hex_grid, hex_centroids, hex_destinations, poi_destinations):
    if OUT_GPKG.exists():
        OUT_GPKG.unlink()
    layers = [
        ("hex_grid", hex_grid),
        ("hex_centroids", hex_centroids),
        ("hex_destinations", hex_destinations),
        ("poi_destinations", poi_destinations),
    ]
    transform_context = QgsProject.instance().transformContext()
    for i, (name, layer) in enumerate(layers):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = name
        if i > 0:
            # First layer creates the file; later layers add to it.
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(OUT_GPKG), transform_context, options)
        if err[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Failed writing layer '{name}': {err}")
        print(f"[ok] wrote layer '{name}' ({layer.featureCount()} features)")


def main():
    print("=== F2: modal-complementarity data prep (Lodz) ===")
    copy_gtfs()
    build_network()

    hex_grid_bare = build_hex_layers()
    hex_pop, pop_stats = overlay_population(hex_grid_bare)

    poi_wgs84 = build_poi_layer()
    hex_full = overlay_services(hex_pop, poi_wgs84, hex_grid_bare.crs())

    hex_destinations = _run("native:centroids", {
        "INPUT": hex_full, "ALL_PARTS": False, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    hex_centroids = _run("native:retainfields", {
        "INPUT": hex_destinations, "FIELDS": ["hex_id"], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    write_gpkg(hex_full, hex_centroids, hex_destinations, poi_wgs84)

    print("=== F2 done ===")
    print(json.dumps({
        "precinct_pop_sum": pop_stats["precinct_pop_sum"],
        "hex_pop_sum": pop_stats["hex_pop_sum"],
        "diff_pct": pop_stats["diff_pct"],
        "hex_with_pop": pop_stats["hex_with_pop"],
        "null_precincts": pop_stats["null_precincts"],
        "null_area_km2": pop_stats["null_area_km2"],
    }, indent=2))


if __name__ == "__main__":
    main()
