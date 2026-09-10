"""Data prep for the multi-city realized-GTFS delay analysis.

Generalized from ../realtime_delay_lodz/prepare_data.py -- same method, same
Easy-R5 algorithms (easyr5:buildnetwork, easyr5:populationoverlay) + native
QGIS + stdlib. No R/r5r, no Overpass, no pip.

Per city it builds two R5 networks (static, realized P50 -- one GTFS variant
per folder), a hexagon grid clipped to the dissolved obwody_spisowe boundary
with area-weighted population, and poi_targets (school / pharmacy / mall from
the city's .osm.pbf, university from the curated CSV).

Gate: the static network's service_days[DATE] count is the reference; the
realized network must report the identical count for the same day (rewritten
times, same trips) and it must be >= cities.MIN_TRIPS (else silent walk-only).

Run inside the QGIS Python env, e.g. mcp__qgis__execute_code:

    import prepare_data; prepare_data.main("gdansk", 250)
    import prepare_data; prepare_data.main("gdansk", 500)
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

try:
    import processing
    from qgis.core import (
        QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
        QgsProcessing, QgsVectorFileWriter, QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover
    raise SystemExit("prepare_data.py needs qgis.core + processing (run via mcp__qgis__execute_code).") from exc

import cities as C

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
POP_TOLERANCE = 0.01

CATEGORY_TAGS = {
    "school": ("amenity", "school"),
    "pharmacy": ("amenity", "pharmacy"),
    "mall": ("shop", "mall"),
}
CATEGORIES = ("school", "pharmacy", "university", "mall")


def gpkg_path(city: str, spacing_m: int) -> Path:
    suffix = "" if spacing_m == 250 else f"_{spacing_m}m"
    return HERE / f"delay_{city}{suffix}.gpkg"


def _run(alg, params, out="OUTPUT"):
    return processing.run(alg, params)[out]


def _copy_one(src: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    zips = sorted(dst_dir.glob("*.zip"))
    if len(zips) != 1:
        raise RuntimeError(f"{dst_dir} must hold exactly one feed, found {zips}")


def _build_network(city, osm_pbf, gtfs_dir, cache_dir, label):
    result = processing.run("easyr5:buildnetwork", {
        "OSM_PBF": str(osm_pbf), "GTFS_FOLDER": str(gtfs_dir),
        "CACHE_FOLDER": str(cache_dir), "FORCE_REBUILD": False,
    })
    summary = json.loads(Path(result["NETWORK_JSON"]).read_text(encoding="utf-8"))
    trips = (summary.get("service_days") or {}).get(C.ANALYSIS_DATE)
    print(f"[{city}] {label}: service_days[{C.ANALYSIS_DATE}] = {trips}")
    return result, trips


def build_networks(city):
    p = C.paths(city)
    gs, gr = WORK / city / "gtfs_static", WORK / city / "gtfs_realized_p50"
    ns, nr = WORK / city / "network_static", WORK / city / "network_realized_p50"
    _copy_one(p["gtfs_static"], gs)
    _copy_one(p["gtfs_realized"], gr)
    _, ref = _build_network(city, p["osm_pbf"], gs, ns, "static")
    _, got = _build_network(city, p["osm_pbf"], gr, nr, "realized_p50")
    if not ref or ref < C.MIN_TRIPS:
        raise RuntimeError(f"GATE FAILED ({city}): static day has {ref} active trips (<{C.MIN_TRIPS}) -- walk-only feed, stop.")
    if got != ref:
        raise RuntimeError(f"GATE FAILED ({city}): realized day has {got} trips, static has {ref}. Feeds are not the same service.")
    print(f"[gate OK] {city}: static == realized == {ref} active trips on {C.ANALYSIS_DATE}")
    return ns, nr


def build_boundary_and_grid(city, spacing_m):
    ses = C.paths(city)["ses_gpkg"]
    obwody = QgsVectorLayer(f"{ses}|layername=obwody_spisowe", "obwody_spisowe", "ogr")
    if not obwody.isValid():
        raise RuntimeError(f"Could not load obwody_spisowe from {ses}")
    if obwody.crs().isGeographic():
        raise RuntimeError(f"obwody_spisowe CRS ({obwody.crs().description()}) is geographic.")

    boundary = _run("native:dissolve", {
        "INPUT": obwody, "FIELD": [], "SEPARATE_DISJOINT": False,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    grid = _run("native:creategrid", {
        "TYPE": 4, "EXTENT": boundary.extent(),
        "HSPACING": spacing_m, "VSPACING": spacing_m, "HOVERLAY": 0, "VOVERLAY": 0,
        "CRS": obwody.crs(), "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    clipped = _run("native:extractbylocation", {
        "INPUT": grid, "PREDICATE": [0], "INTERSECT": boundary,
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
    print(f"[{city}] hex_grid_bare ({spacing_m} m): {hex_grid_bare.featureCount()} features")
    # Boundary = the stepped outline of the hex grid itself (what the map shows),
    # not the smooth census polygon. +1/-1 m buffer closes sub-metre seams that
    # a plain dissolve of a 250 m grid in this CRS leaves open. See rebuild_boundary.py.
    grown = _run("native:buffer", {
        "INPUT": hex_grid_bare, "DISTANCE": 1, "DISSOLVE": True,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    shrunk = _run("native:buffer", {
        "INPUT": grown, "DISTANCE": -1, "DISSOLVE": True,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    boundary_single = _run("native:multiparttosingleparts", {
        "INPUT": shrunk, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    return obwody, hex_grid_bare, boundary_single


def overlay_population(city, obwody, hex_grid_bare):
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
    print(f"[{city}] pop overlay: hexes={hex_pop_sum:.0f} precincts={precinct_pop_sum:.0f} diff={diff_pct:.4%}")
    if diff_pct > POP_TOLERANCE:
        raise RuntimeError(f"GATE FAILED ({city}): population overlay off by {diff_pct:.2%}.")
    if hex_with_pop == 0:
        raise RuntimeError(f"GATE FAILED ({city}): 0 hexagons have pop_total > 0.")
    return hex_pop


def _category_points_from_pbf(pts, mp, key, value):
    mp_match = _run("native:extractbyexpression", {
        "INPUT": mp, "EXPRESSION": f'"{key}" = \'{value}\'',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    mp_centroids = _run("native:centroids", {
        "INPUT": mp_match, "ALL_PARTS": False, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    pts_match = _run("native:extractbyexpression", {
        "INPUT": pts, "EXPRESSION": f'"other_tags" LIKE \'%"{key}"=>"{value}"%\'',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    pts_standalone = _run("native:extractbylocation", {
        "INPUT": pts_match, "PREDICATE": [2], "INTERSECT": mp_match,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    return mp_centroids, pts_standalone, mp_match.featureCount(), pts_standalone.featureCount()


def build_poi_layer(city):
    p = C.paths(city)
    pbf = str(p["osm_pbf"])
    pts = QgsVectorLayer(f"{pbf}|layername=points", "pts", "ogr")
    mp = QgsVectorLayer(f"{pbf}|layername=multipolygons", "mp", "ogr")
    if not pts.isValid() or not mp.isValid():
        raise RuntimeError(f"Could not load points/multipolygons from {pbf}")

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

    def add(geom, poi_id, name, category):
        feat = QgsFeature(mem.fields())
        feat.setGeometry(geom)
        feat["poi_id"] = poi_id
        feat["name"] = name or ""
        feat["category"] = category
        for cat in CATEGORIES:
            feat[f"srv_{cat}"] = 1 if cat == category else 0
        mem.dataProvider().addFeature(feat)
        counts[category] += 1

    for category, (key, value) in CATEGORY_TAGS.items():
        mp_c, pts_s, n_mp, n_pt = _category_points_from_pbf(pts, mp, key, value)
        print(f"[{city}] {category}: {n_mp} polygons + {n_pt} standalone points")
        for f in mp_c.getFeatures():
            mp_id = f["osm_id"] if f["osm_id"] not in (None, "NULL") else f"w{f['osm_way_id']}"
            add(f.geometry(), f"mp/{mp_id}", f["name"], category)
        for f in pts_s.getFeatures():
            add(f.geometry(), f"pt/{f['osm_id']}", f["name"], category)

    with open(p["universities"], encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            geom = QgsGeometry.fromPointXY(QgsPointXY(float(row["lon"]), float(row["lat"])))
            add(geom, f"{row['osm_type']}/{row['osm_id']}", row["name"] or row["university"], "university")

    print(f"[{city}] POI counts: {counts}")
    for cat, n in counts.items():
        if n < 5:
            raise RuntimeError(f"GATE FAILED ({city}): category {cat!r} has only {n} POI.")
    return mem


def write_gpkg(city, spacing_m, layers):
    out_gpkg = gpkg_path(city, spacing_m)
    if out_gpkg.exists():
        out_gpkg.unlink()
    for i, (name, layer) in enumerate(layers):
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = name
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if i == 0
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(out_gpkg), layer.transformContext(), opts)
        if err[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Failed to write layer {name}: {err}")
    print(f"[{city}] wrote {out_gpkg.name}: {[n for n, _ in layers]}")


def main(city: str, hex_spacing_m: int = 250):
    C.check_inputs(city)
    build_networks(city)
    obwody, hex_grid_bare, boundary = build_boundary_and_grid(city, hex_spacing_m)
    hex_pop = overlay_population(city, obwody, hex_grid_bare)
    hex_centroids = _run("native:centroids", {
        "INPUT": hex_pop, "ALL_PARTS": False, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    siatka = _run("native:retainfields", {
        "INPUT": hex_pop, "FIELDS": ["hex_id"], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    poi_targets = build_poi_layer(city)
    write_gpkg(city, hex_spacing_m, [
        ("hex_grid", hex_pop),
        ("hex_centroids", hex_centroids),
        ("poi_targets", poi_targets),
        ("boundary", boundary),
        ("siatka", siatka),
    ])
    print(f"[done] prepare_data {city} {hex_spacing_m} m")
