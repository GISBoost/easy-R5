"""E3 continued -- building-weighted (dasymetric) population redistribution.

Port of tools/realtime_delay_cities/dasymetric_pop.py, generalized from
"one city" to "one target" (woj | lodz), both reading buildings from the
SAME lodzkie.osm.pbf (no need for a separate Lodz-only pbf clip here --
that clip is an E5/routing concern, not a population-raster concern; extent
is restricted via the hex grid's own bounding box + PAD_M).

Scale check done before writing this (correcting an overestimate in the
approved plan): 18 219 km2 at 10 m resolution is ~182 million cells (a
~15000x12000 px byte raster, a few hundred MB) -- NOT the ~1.8e11 the plan
guessed (that number conflated linear meters with cell count). A single
whole-voivodeship rasterize is fine; no per-powiat tiling needed.

Method: binary dasymetric mapping (Mennis 2003). Building footprint area
(count of built 10 m cells) is the weight -- deliberately not
building:levels x area (uneven OSM coverage in PL, decided 2026-09-10 in
realtime_delay_cities). Mass-preserving: every precinct's population is
fully redistributed onto its own built-up hex fragments; a precinct with
zero residential building coverage falls back to plain area-weighting.
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
import config as C

RASTER_M = 10
PAD_M = 300
MIN_POP = 0.5

# Same curated non-residential exclusion list as realtime_delay_cities/dasymetric_pop.py
EXCL_BUILDINGS = {
    "garage", "garages", "carport", "industrial", "warehouse", "retail",
    "commercial", "office", "school", "university", "college", "kindergarten",
    "hospital", "clinic", "church", "chapel", "cathedral", "mosque",
    "synagogue", "temple", "religious", "hotel", "stadium", "grandstand",
    "sports_hall", "sports_centre", "silo", "water_tower", "storage_tank",
    "hangar", "shed", "roof", "ruins", "greenhouse", "barn", "cowshed",
    "stable", "sty", "farm_auxiliary", "hut", "cabin", "bunker",
    "military", "government", "civic", "public", "train_station",
    "transportation", "parking", "service", "kiosk", "toilets",
    "bridge", "digester", "gatehouse", "guardhouse", "power_substation",
    "transformer_tower", "substation", "static_caravan", "container",
    "construction", "collapsed", "damaged", "no", "yes_industrial",
    "manufacture", "warehouse_industrial", "distribution_centre",
    "mall", "supermarket", "shop", "kiosk_shop", "market",
    "conference_centre", "exhibition_centre", "grandstand_sports",
    "fire_station", "police", "prison", "courthouse", "monastery",
    "convent", "shrine", "mortuary", "funeral_hall", "crematorium",
    "greenhouse_horticulture", "cowbarn", "pigsty", "sty_farm",
    "farm", "agricultural", "outbuilding", "toilet", "restaurant",
    "sports_pitch_building", "grandstand_building",
}


def building_raster(pbf_path, extent_layer, out_tif):
    """Rasterize residential-ish OSM building footprints to a byte raster.
    One raster per target (woj / lodz), cached by output path."""
    import processing
    from qgis.core import QgsVectorLayer

    if Path(out_tif).exists():
        print(f"  raster cached: {out_tif}")
        return out_tif

    from qgis.core import QgsCoordinateTransform, QgsProject

    mp_raw = QgsVectorLayer(f"{pbf_path}|layername=multipolygons", "mp_raw", "ogr")
    print(f"  multipolygons layer: {mp_raw.featureCount()} features (whole pbf, native CRS {mp_raw.crs().authid()})")
    # Whole-voivodeship OSM building extract has at least one invalid geometry
    # (feature 255792, confirmed) -- native:extractbyextent errors hard on
    # that by default rather than skipping it. Fix geometries before anything
    # else touches this layer.
    mp = processing.run("native:fixgeometries", {"INPUT": mp_raw, "OUTPUT": "memory:"})["OUTPUT"]
    print(f"  after fixgeometries: {mp.featureCount()} features")

    crs = extent_layer.crs()
    ext = extent_layer.extent()
    ext.grow(PAD_M)

    # bbox filter in the SOURCE crs first (cheap, benefits from OGR's own
    # spatial index) -- reprojecting ~all Lodzkie buildings before filtering
    # would force a full-layer transform for data we are about to discard.
    xform = QgsCoordinateTransform(crs, mp.crs(), QgsProject.instance())
    ext_native = xform.transformBoundingBox(ext)
    extent_str_native = (f"{ext_native.xMinimum()},{ext_native.xMaximum()},"
                          f"{ext_native.yMinimum()},{ext_native.yMaximum()} [{mp.crs().authid()}]")
    in_extent = processing.run("native:extractbyextent", {
        "INPUT": mp, "EXTENT": extent_str_native, "CLIP": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  buildings within target extent: {in_extent.featureCount()} (bbox pre-filter)")

    excl_list = ",".join(f"'{v}'" for v in EXCL_BUILDINGS)
    expr = f'"building" is not null and "building" not in ({excl_list})'
    residential = processing.run("native:extractbyexpression", {
        "INPUT": in_extent, "EXPRESSION": expr, "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  residential-ish buildings: {residential.featureCount()}")

    extent_str = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()} [{crs.authid()}]"
    reproj = processing.run("native:reprojectlayer", {
        "INPUT": residential, "TARGET_CRS": crs, "OUTPUT": "memory:",
    })["OUTPUT"]

    processing.run("gdal:rasterize", {
        "INPUT": reproj, "FIELD": None, "BURN": 1, "UNITS": 1,
        "WIDTH": RASTER_M, "HEIGHT": RASTER_M,
        "EXTENT": extent_str, "NODATA": 0, "OPTIONS": "", "DATA_TYPE": 0,
        "INIT": 0, "INVERT": False, "OUTPUT": out_tif,
    })
    print(f"  wrote raster: {out_tif}")
    return out_tif


def redistribute(hex_layer, obwody_layer, raster_path, id_field="hex_id"):
    """Mass-preserving dasymetric split. Returns dict hex_id -> population,
    plus stats dict."""
    import processing

    obwody_pop = processing.run("native:extractbyexpression", {
        "INPUT": obwody_layer, "EXPRESSION": '"population" IS NOT NULL', "OUTPUT": "memory:",
    })["OUTPUT"]

    # Spatial-index pre-filter: for the Lodz-scale call this cuts the
    # candidate set from all 14038 voivodeship precincts down to the ~3900
    # actually near Lodz, before the expensive native:intersection. Matters
    # more at woj scale (21585 hexagons) -- this is the qgis-core-architecture
    # "use spatial indexes" guidance, not optional at this data volume.
    obwody_pop = processing.run("native:extractbylocation", {
        "INPUT": obwody_pop, "PREDICATE": [0], "INTERSECT": hex_layer, "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  precincts near this hex grid (spatial pre-filter): {obwody_pop.featureCount()}")

    frags = processing.run("native:intersection", {
        "INPUT": hex_layer, "OVERLAY": obwody_pop,
        "INPUT_FIELDS": [id_field], "OVERLAY_FIELDS": ["OBWOD", "population"],
        "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  hex x precinct fragments: {frags.featureCount()}")

    zonal = processing.run("native:zonalstatisticsfb", {
        "INPUT": frags, "INPUT_RASTER": raster_path, "RASTER_BAND": 1,
        "COLUMN_PREFIX": "b_", "STATISTICS": [1], "OUTPUT": "memory:",
    })["OUTPUT"]

    # per-precinct total built cells and total area (for fallback)
    precinct_built = defaultdict(float)
    precinct_area = defaultdict(float)
    rows = []
    for f in zonal.getFeatures():
        obwod = f["OBWOD"]
        built = f["b_sum"] or 0.0
        area = f.geometry().area()
        pop = f["population"]
        hid = f[id_field]
        precinct_built[obwod] += built
        precinct_area[obwod] += area
        rows.append((hid, obwod, built, area, pop))

    new_pop = defaultdict(float)
    fallback_precincts = 0
    fallback_pop = 0.0
    seen_precincts = set()
    for hid, obwod, built, area, pop in rows:
        tb = precinct_built[obwod]
        if tb > 0:
            new_pop[hid] += pop * (built / tb)
        else:
            if obwod not in seen_precincts:
                fallback_precincts += 1
                fallback_pop += pop
            ta = precinct_area[obwod]
            if ta > 0:
                new_pop[hid] += pop * (area / ta)
        seen_precincts.add(obwod)

    precinct_pop = {}
    for hid, obwod, built, area, pop in rows:
        precinct_pop[obwod] = pop
    prec_pop_total = sum(precinct_pop.values())
    new_sum = sum(new_pop.values())

    stats = {
        "prec_pop_total": prec_pop_total,
        "new_sum": new_sum,
        "mass_diff_pct": 100 * abs(new_sum - prec_pop_total) / prec_pop_total if prec_pop_total else 0,
        "fallback_precincts": fallback_precincts,
        "fallback_pop": fallback_pop,
        "n_precincts": len(precinct_pop),
    }
    return new_pop, stats


def apply(target, hex_layer_name, pbf_path, min_pop=MIN_POP):
    """target: 'woj' or 'lodz'. Writes hex_grid_<target>_pop + hex_centroids_<target>."""
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant
    import processing

    gpkg = str(C.PRG_GPKG)
    hex_layer = QgsVectorLayer(f"{gpkg}|layername={hex_layer_name}", hex_layer_name, "ogr")
    obwody = QgsVectorLayer(f"{gpkg}|layername=obwody_spisowe", "obwody", "ogr")
    print(f"=== dasymetric apply: {target} ({hex_layer.featureCount()} hexagons) ===")

    out_tif = str(C.WORK / "dasym" / f"{target}_bld.tif")
    Path(out_tif).parent.mkdir(parents=True, exist_ok=True)
    raster = building_raster(pbf_path, hex_layer, out_tif)

    new_pop, stats = redistribute(hex_layer, obwody, raster)
    print(f"  mass check: precinct_total={stats['prec_pop_total']:.1f} "
          f"redistributed_total={stats['new_sum']:.1f} diff={stats['mass_diff_pct']:.4f}% "
          f"(gate <=0.01% for float rounding only -- this is a closed accounting identity, "
          f"not an approximation)")
    print(f"  fallback (no buildings in precinct): {stats['fallback_precincts']} / "
          f"{stats['n_precincts']} precincts, {stats['fallback_pop']:.0f} people")

    fixed = processing.run("native:fixgeometries", {"INPUT": hex_layer, "OUTPUT": "memory:"})["OUTPUT"]
    fixed.dataProvider().addAttributes([QgsField("pop_total", QVariant.Double, len=12, prec=2)])
    fixed.updateFields()
    fixed.startEditing()
    idx = fixed.fields().indexOf("pop_total")
    hid_idx_name = "hex_id"
    for f in fixed.getFeatures():
        pop = new_pop.get(f[hid_idx_name], 0.0)
        fixed.changeAttributeValue(f.id(), idx, round(pop, 2))
    fixed.commitChanges()

    n_before = fixed.featureCount()
    populated = processing.run("native:extractbyexpression", {
        "INPUT": fixed, "EXPRESSION": f'"pop_total" >= {min_pop}', "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  hexagons: {n_before} total -> {populated.featureCount()} with pop_total >= {min_pop}")

    centroids = processing.run("native:centroids", {"INPUT": populated, "ALL_PARTS": False, "OUTPUT": "memory:"})["OUTPUT"]

    out_gpkg = gpkg
    for lyr, name in [(fixed, f"hex_{target}_all"), (populated, f"hex_{target}_pop"),
                       (centroids, f"hex_{target}_centroids")]:
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = name
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        QgsVectorFileWriter.writeAsVectorFormatV3(lyr, out_gpkg, lyr.transformContext(), opts)
        print(f"  wrote {name}")

    return {"stats": stats, "n_before": n_before, "n_populated": populated.featureCount()}


def main():
    r_woj = apply("woj", "hex_grid_woj", str(C.PBF_WOJ))
    r_lodz = apply("lodz", "hex_grid_lodz", str(C.PBF_WOJ))  # same pbf, extent-limited by hex grid
    return r_woj, r_lodz


if __name__ == "__main__":
    main()
