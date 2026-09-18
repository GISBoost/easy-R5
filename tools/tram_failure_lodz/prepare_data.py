"""Spatial inputs for the tram-failure analysis. Runs inside QGIS.

Writes tram_failure_lodz.gpkg:
  hex_grid / hex_centroids -- 1000 m hexagons, population (areal interpolation from
                              census precincts) and a population-weighted mean income
                              index, for the equity split
  poi_targets              -- reused as-is from ../realtime_delay_lodz/delay_lodz.gpkg,
                              so this analysis and the delay one count the same 766
                              destinations
  boundary                 -- likewise
  centre                   -- the population-weighted centroid of the city, as a
                              one-point layer: the destination for the travel-time-to-
                              centre metric
  tram_lines               -- one line per tram route, drawn through its stops, for the
                              maps and for eyeballing the corridor

The network is NOT rebuilt: R5 applies every scenario to the existing network in
memory. ../realtime_delay_lodz/network_static is used as-is.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

try:
    import processing
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsFeature,
        QgsField,
        QgsGeometry,
        QgsPointXY,
        QgsProcessing,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover
    raise SystemExit("prepare_data.py must run inside QGIS.") from exc

import gtfs_lines as gl

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
SES = TOOLS / "ses_income_lodz" / "lodz.gpkg"
DELAY_GPKG = TOOLS / "realtime_delay_lodz" / "delay_lodz.gpkg"
OUT_GPKG = HERE / "tram_failure_lodz.gpkg"

PBF = TOOLS / "accessibility_lodz" / "lodz.osm.pbf"
GRIDS_DIR = HERE / "grids"

# grid id -> (hexagon spacing in metres, origin offset in metres).
# The offset grid is the point of the whole set: h500 and h500off are the SAME cell size
# and differ only in where the cell boundaries fall, which separates the *zoning* half of
# MAUP from the *scale* half that h250/h500/h1000 measure.
GRIDS = {
    "h250": (250, (0.0, 0.0)),
    "h500": (500, (0.0, 0.0)),
    "h1000": (1000, (0.0, 0.0)),
    "h500off": (500, (250.0, 144.34)),   # half a cell across and down the hexagon lattice
}

HEX_SPACING_M = 1000
POP_TOLERANCE = 0.01
CENTROID_TOLERANCE_M = 150   # agreement between the QGIS transform and gtfs_lines'

# (census column, field name on the hexagon). Population-weighted means, for the equity
# split in compute_impact.py.
SES_COLUMNS = (
    ("income_index_pln", "income_idx"),
    ("fam_pct_matki_samotne", "single_par"),
    ("hh_pct_jednoosobowe", "hh_single"),
    ("hh_avg_size", "hh_size"),
)


def _run(alg, params, out="OUTPUT"):
    return processing.run(alg, params)[out]


@contextmanager
def planimetric_area():
    """Force planimetric $area for the duration, then restore the project's setting.

    easyr5:populationoverlay interpolates with $area, which follows the *project's*
    ellipsoid. The demo project carries a custom one ("PARAMETER:6378137:6356752.31…")
    for which QGIS returns NaN on every feature, and the algorithm then dies on
    'Cannot convert nan to double' inside "population"/"area" -- an opaque failure a
    long way from its cause. Planimetric area in a projected CRS is the right weight
    for areal interpolation anyway: only the ratio piece/parent matters, and EPSG:2180
    is equal-area enough over one city (EPSG:7019 gives the same ratios to 5 decimals).
    """
    project = QgsProject.instance()
    before = project.ellipsoid()
    if before != "NONE":
        print(f"[warn] project ellipsoid {before!r} -> NONE for this run (restored after)")
        project.setEllipsoid("NONE")
    try:
        yield
    finally:
        project.setEllipsoid(before)


def _tmp():
    return QgsProcessing.TEMPORARY_OUTPUT


def _num(value):
    """Field value as float, or None. A NULL field comes back as QVariant, not None,
    and QVariant fails silently in comparisons and loudly in arithmetic."""
    if value is None or (isinstance(value, QVariant) and value.isNull()):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_grid(spacing_m=HEX_SPACING_M, offset=(0.0, 0.0)):
    raw = QgsVectorLayer(f"{SES}|layername=obwody_spisowe", "obwody_spisowe", "ogr")
    if not raw.isValid():
        raise RuntimeError(f"Cannot load obwody_spisowe from {SES}")
    if raw.crs().isGeographic():
        raise RuntimeError(f"obwody_spisowe CRS is geographic ({raw.crs().description()})")

    # The gpkg records its CRS as a custom entry ("UWPP_1992", srs_id 100000) with no
    # EPSG code. Anything that needs an ellipsoidal area off that layer -- including the
    # $area inside easyr5:populationoverlay -- then evaluates to NaN and the algorithm
    # dies on "population"/"area". The coordinates are plain PL-1992, so relabel it;
    # centre_layer() re-derives the population-weighted centroid through this CRS and
    # fails loudly if the relabelling were wrong.
    was = raw.crs().description()
    raw.setCrs(QgsCoordinateReferenceSystem("EPSG:2180"))   # in memory only; file untouched
    obwody = raw
    print(f"[ok] precincts: {obwody.featureCount()}, CRS relabelled "
          f"{was!r} -> {obwody.crs().authid()}")

    boundary = _run("native:dissolve", {"INPUT": obwody, "FIELD": [],
                                        "SEPARATE_DISJOINT": False, "OUTPUT": _tmp()})
    extent = boundary.extent()
    # Shifting the extent shifts where the lattice starts, which is how the offset grid
    # gets different cell boundaries at the same cell size. Grow the extent by the offset
    # first, so shifting never uncovers a corner of the city.
    extent.grow(max(offset) + spacing_m)
    if any(offset):
        extent.setXMinimum(extent.xMinimum() + offset[0])
        extent.setYMinimum(extent.yMinimum() + offset[1])
    grid = _run("native:creategrid", {
        "TYPE": 4, "EXTENT": extent, "HSPACING": spacing_m, "VSPACING": spacing_m,
        "HOVERLAY": 0, "VOVERLAY": 0, "CRS": obwody.crs(), "OUTPUT": _tmp()})
    clipped = _run("native:extractbylocation", {
        "INPUT": grid, "PREDICATE": [0], "INTERSECT": boundary, "OUTPUT": _tmp()})
    with_id = _run("native:fieldcalculator", {
        "INPUT": clipped, "FIELD_NAME": "hex_id", "FIELD_TYPE": 1, "FIELD_LENGTH": 10,
        "FIELD_PRECISION": 0, "FORMULA": "@row_number", "OUTPUT": _tmp()})
    bare = _run("native:retainfields", {"INPUT": with_id, "FIELDS": ["hex_id"],
                                        "OUTPUT": _tmp()})
    print(f"[ok] {bare.featureCount()} hexagons at {spacing_m} m")
    return obwody, boundary, bare


def add_population(obwody, hex_bare):
    valid = _run("native:extractbyexpression", {
        "INPUT": obwody, "EXPRESSION": '"population" IS NOT NULL AND "population" > 0',
        "OUTPUT": _tmp()})
    precinct_sum = sum(f["population"] for f in valid.getFeatures())

    overlaid = processing.run("easyr5:populationoverlay", {
        "HEX_GRID": hex_bare, "POPULATION_LAYER": valid, "POPULATION_FIELD": "population",
        "OUTPUT": _tmp()})["OUTPUT"]
    renamed = _run("native:fieldcalculator", {
        "INPUT": overlaid, "FIELD_NAME": "pop_total", "FIELD_TYPE": 0, "FIELD_LENGTH": 10,
        "FIELD_PRECISION": 2, "FORMULA": '"population"', "OUTPUT": _tmp()})
    hex_pop = _run("native:retainfields", {
        "INPUT": renamed, "FIELDS": ["hex_id", "pop_total"], "OUTPUT": _tmp()})

    hex_sum = sum(f["pop_total"] or 0 for f in hex_pop.getFeatures())
    diff = abs(hex_sum - precinct_sum) / precinct_sum
    print(f"[check] population: hexagons {hex_sum:.0f} vs precincts {precinct_sum:.0f} "
          f"({diff:.4%})")
    if diff > POP_TOLERANCE:
        raise RuntimeError(f"GATE FAILED: population overlay off by {diff:.2%}")
    return hex_pop, valid


def add_ses(hex_pop, obwody_valid, columns=SES_COLUMNS):
    """Population-weighted mean of each census column per hexagon.

    populationoverlay already splits precinct population across hexagons by area; the
    same weighting is redone here, because a *rate* cannot be summed the way a headcount
    can -- it has to be averaged over the people it describes.

    income_index_pln is carried for completeness but barely varies in Lodz (2980-3125 PLN
    across 3854 precincts, sd 21), so it cannot carry an equity split on its own; the
    single-parent share, which runs 16-41%, is what the equity grouping actually uses.
    """
    pieces = _run("native:intersection", {
        "INPUT": hex_pop, "OVERLAY": obwody_valid, "INPUT_FIELDS": ["hex_id"],
        "OVERLAY_FIELDS": ["OBJECTID", "population"] + [c for c, _ in columns],
        "OUTPUT": _tmp()})
    # Density per precinct, so a piece is weighted by the people in it rather than by its
    # area: a hexagon straddling a tower block and a cemetery must take the tower block's
    # value, not the average of the two.
    density = {f["OBJECTID"]: _num(f["population"]) / f.geometry().area()
               for f in obwody_valid.getFeatures()
               if f.geometry().area() > 0 and _num(f["population"]) is not None}

    num = {alias: {} for _, alias in columns}
    den = {alias: {} for _, alias in columns}
    for f in pieces.getFeatures():
        d = density.get(f["OBJECTID"])
        if d is None:
            continue
        w = f.geometry().area() * d          # people of this precinct inside this hexagon
        hid = f["hex_id"]
        for col, alias in columns:
            value = _num(f[col])
            if value is None:
                continue
            num[alias][hid] = num[alias].get(hid, 0.0) + w * value
            den[alias][hid] = den[alias].get(hid, 0.0) + w

    hex_pop.startEditing()
    missing = [QgsField(alias, QVariant.Double) for _, alias in columns
               if hex_pop.fields().indexOf(alias) < 0]
    if missing:
        hex_pop.dataProvider().addAttributes(missing)
        hex_pop.updateFields()
    for _, alias in columns:
        idx = hex_pop.fields().indexOf(alias)
        for f in hex_pop.getFeatures():
            hid = f["hex_id"]
            hex_pop.changeAttributeValue(
                f.id(), idx, num[alias][hid] / den[alias][hid] if den[alias].get(hid) else None)
    hex_pop.commitChanges()
    for _, alias in columns:
        have = sum(1 for f in hex_pop.getFeatures() if f[alias] is not None)
        print(f"[ok] {alias} on {have}/{hex_pop.featureCount()} hexagons")
    return hex_pop


def centre_layer(obwody_valid):
    """Population-weighted centroid, and a cross-check against gtfs_lines' own transform."""
    total = sx = sy = 0.0
    for f in obwody_valid.getFeatures():
        p = f["population"]
        c = f.geometry().centroid().asPoint()
        total += p
        sx += p * c.x()
        sy += p * c.y()
    pt = QgsPointXY(sx / total, sy / total)

    wgs = QgsCoordinateReferenceSystem("EPSG:4326")
    xform = QgsCoordinateTransform(obwody_valid.crs(), wgs, QgsProject.instance())
    ll = xform.transform(pt)

    ref = gl.weighted_centroid(gl.population_points())
    d = gl.haversine_m((ll.x(), ll.y()), ref)
    print(f"[check] centre QGIS {ll.x():.6f},{ll.y():.6f} vs standalone "
          f"{ref[0]:.6f},{ref[1]:.6f} -> {d:.0f} m apart")
    if d > CENTROID_TOLERANCE_M:
        raise RuntimeError(f"GATE FAILED: the two centroid computations disagree by {d:.0f} m")

    lyr = QgsVectorLayer(f"Point?crs={obwody_valid.crs().authid()}", "centre", "memory")
    lyr.dataProvider().addAttributes([QgsField("poi_id", QVariant.String),
                                      QgsField("name", QVariant.String),
                                      QgsField("srv_centre", QVariant.Int)])
    lyr.updateFields()
    f = QgsFeature(lyr.fields())
    f.setGeometry(QgsGeometry.fromPointXY(pt))
    f.setAttributes(["centre", "population-weighted city centre", 1])
    lyr.dataProvider().addFeatures([f])
    lyr.updateExtents()
    return lyr, (ll.x(), ll.y())


def tram_line_layer(crs):
    """One polyline per tram line, through the stops of its longest pattern."""
    feed = gl.Feed()
    lyr = QgsVectorLayer("LineString?crs=EPSG:4326", "tram_lines", "memory")
    lyr.dataProvider().addAttributes([QgsField("line", QVariant.String),
                                      QgsField("route_id", QVariant.String),
                                      QgsField("length_km", QVariant.Double),
                                      QgsField("veh_km", QVariant.Double)])
    lyr.updateFields()
    feats = []
    for rid in feed.tram_routes():
        pts = [QgsPointXY(*feed.stops[s[1]]) for s in feed.longest_pattern(rid)
               if s[1] in feed.stops]
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPolylineXY(pts))
        f.setAttributes([feed.routes[rid]["route_short_name"], rid,
                         round(feed.length_km(rid), 2), round(feed.vehicle_km(rid), 1)])
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    reproj = _run("native:reprojectlayer", {"INPUT": lyr, "TARGET_CRS": crs, "OUTPUT": _tmp()})
    print(f"[ok] tram_lines: {reproj.featureCount()} lines")
    return reproj


def osiedle_layer(boundary, crs):
    """Lodz's 36 osiedla (jednostki pomocnicze) from OSM, clipped to the city.

    These are the names people actually use -- Gorniak, Teofilow-Wielkopolska,
    Widzew-Wschod -- which is what lets a result be stated as "a quarter of Gorniak
    loses ..." instead of "hexagon 214 loses ...". OSM maps them as
    boundary=administrative, admin_level=11; level 10 is a different, overlapping
    division and level 9 is the five big dzielnice.
    """
    mp = QgsVectorLayer(f"{PBF}|layername=multipolygons", "osm_mp", "ogr")
    if not mp.isValid():
        raise RuntimeError(f"Cannot read multipolygons from {PBF}")
    picked = _run("native:extractbyexpression", {
        "INPUT": mp,
        "EXPRESSION": '"boundary" = \'administrative\' AND "admin_level" = \'11\' '
                      'AND "name" IS NOT NULL',
        "OUTPUT": _tmp()})
    reproj = _run("native:reprojectlayer", {"INPUT": picked, "TARGET_CRS": crs,
                                            "OUTPUT": _tmp()})
    # Clip rather than select: OSM's city outline and the dissolved census precincts do
    # not agree to the metre, so "is within" silently drops every osiedle that touches the
    # edge -- 21 of 36 survived that test. Clipping keeps them, trimmed to the same city
    # outline the hexagons use. Neighbouring gminy (Ksawerow-*) also use level 11 and
    # clip down to slivers or nothing, so drop anything under 0.1 km2.
    clipped = _run("native:clip", {"INPUT": reproj, "OVERLAY": boundary, "OUTPUT": _tmp()})
    big = _run("native:extractbyexpression", {
        "INPUT": clipped, "EXPRESSION": "$area > 100000", "OUTPUT": _tmp()})
    named = _run("native:retainfields", {"INPUT": big, "FIELDS": ["name"],
                                         "OUTPUT": _tmp()})
    print(f"[ok] osiedla: {named.featureCount()} "
          f"(np. {', '.join(sorted(f['name'] for f in named.getFeatures())[:4])})")
    return named


def _write(layer, name, gpkg, first):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.layerName = name
    opts.driverName = "GPKG"
    opts.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteFile if first
                                 else QgsVectorFileWriter.CreateOrOverwriteLayer)
    err = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, str(gpkg), QgsProject.instance().transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"writing {name}: {err}")
    print(f"[ok] wrote {name}")


def main(grid_id="h1000"):
    if grid_id not in GRIDS:
        raise RuntimeError(f"unknown grid {grid_id!r}; known: {', '.join(GRIDS)}")
    spacing_m, offset = GRIDS[grid_id]
    GRIDS_DIR.mkdir(exist_ok=True)
    gpkg = GRIDS_DIR / f"{grid_id}.gpkg"
    print(f"=== {grid_id}: {spacing_m} m, offset {offset} -> {gpkg.name}")
    with planimetric_area():
        obwody, boundary, bare = build_grid(spacing_m, offset)
        hex_pop, valid = add_population(obwody, bare)
        hex_pop = add_ses(hex_pop, valid)
    centre, centre_ll = centre_layer(valid)
    trams = tram_line_layer(obwody.crs())

    centroids = _run("native:centroids", {"INPUT": hex_pop, "ALL_PARTS": False,
                                          "OUTPUT": _tmp()})
    poi = QgsVectorLayer(f"{DELAY_GPKG}|layername=poi_targets", "poi_targets", "ogr")
    if not poi.isValid():
        raise RuntimeError(f"Cannot load poi_targets from {DELAY_GPKG}")

    with planimetric_area():        # the sliver filter below uses $area too
        osiedla = osiedle_layer(boundary, obwody.crs())

    _write(hex_pop, "hex_grid", gpkg, first=True)
    _write(centroids, "hex_centroids", gpkg, first=False)
    _write(poi, "poi_targets", gpkg, first=False)
    _write(boundary, "boundary", gpkg, first=False)
    _write(centre, "centre", gpkg, first=False)
    _write(trams, "tram_lines", gpkg, first=False)
    _write(osiedla, "osiedla", gpkg, first=False)

    pop = sum(f["pop_total"] or 0 for f in hex_pop.getFeatures())
    meta = {"grid_id": grid_id, "hex_spacing_m": spacing_m, "offset_m": list(offset),
            "hexagons": hex_pop.featureCount(),
            "hexagons_with_population": sum(1 for f in hex_pop.getFeatures()
                                            if (f["pop_total"] or 0) > 0),
            "population": round(pop), "poi_targets": poi.featureCount(),
            "osiedla": osiedla.featureCount(),
            "centre_lon_lat": [round(centre_ll[0], 6), round(centre_ll[1], 6)],
            "crs": obwody.crs().authid() or obwody.crs().description()}
    out_dir = HERE / "out" / grid_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prepare_data.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("[done]", json.dumps(meta))
    return meta


def build_all(grid_ids=tuple(GRIDS)):
    return {g: main(g) for g in grid_ids}


if __name__ == "__main__":
    main()
