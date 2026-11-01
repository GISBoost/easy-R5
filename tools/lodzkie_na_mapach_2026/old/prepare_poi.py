"""E4 -- POI extraction and category coverage check, wojewodztwo lodzkie.

Runs inside QGIS. No Overpass -- reads points/multipolygons straight out of
lodzkie-latest.osm.pbf via OGR (pattern from
tools/realtime_delay_cities/prepare_data.py), same as the population
buildings step. Zero API rate limits, one file read.

Design per the approved plan:
  1. Extract every candidate category (~20 tags from the competition brief,
     docs/lodzkie-na-mapach-2026-metodologia.md) as points (polygon
     centroids deduplicated against standalone nodes).
  2. Count per powiat, per category -> out/poi_coverage_powiaty.csv.
  3. Apply the stated cutoff BEFORE deciding the final list: a category
     survives only if it has >=5 objects in >=18 of 24 powiaty. This is a
     number-driven correction of the metodologia doc's a-priori list, not a
     guess -- categories that fail are kept in the "ograniczenia danych"
     table for the map, not silently dropped from the record.
  4. Surviving categories get aggregated onto both hex grids (woj 1000 m,
     Lodz 250 m) as srv_<category> integer fields -- these become
     OPPORTUNITY_FIELDS for easyr5:runaccessibility.
  5. Point-vs-centroid control (Lodz only, ported from
     modal_complementarity_lodz/poi_control.py): gate is Spearman rho >= 0.95
     between a metric computed on hex centroids vs on exact POI points.
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
import config as C

# tag -> (osm_key, osm_value or None for "key IS NOT NULL")
# Matches docs/lodzkie-na-mapach-2026-metodologia.md section "Kategorie POI".
CATEGORY_TAGS = {
    # Edukacja
    "przedszkole": ("amenity", "kindergarten"),
    "szkola": ("amenity", "school"),
    "uczelnia": ("amenity", ["university", "college"]),
    # Zdrowie
    "przychodnia": ("amenity", ["clinic", "doctors"]),
    "szpital": ("amenity", "hospital"),
    "apteka": ("amenity", "pharmacy"),
    # Kultura i rekreacja
    "biblioteka": ("amenity", "library"),
    "dom_kultury": ("amenity", "community_centre"),
    "kino": ("amenity", "cinema"),
    "teatr": ("amenity", "theatre"),
    "muzeum": ("tourism", "museum"),
    "park": ("leisure", "park"),
    "plac_zabaw": ("leisure", "playground"),
    "silownia": ("leisure", "fitness_centre"),
    "basen": ("leisure", "swimming_pool"),
    "boisko_sport": ("leisure", ["pitch", "sports_centre"]),
    # Handel i uslugi
    "supermarket": ("shop", "supermarket"),
    "centrum_handlowe": ("shop", "mall"),
    "targowisko": ("amenity", "marketplace"),
    "poczta": ("amenity", "post_office"),
    "urzad_gminy": ("office", "government"),  # + amenity=townhall handled separately
}
# amenity=townhall folds into urzad_gminy (OR condition), handled in the query builder.
EXTRA_OR = {
    "urzad_gminy": [("amenity", "townhall")],
}

# Coverage cutoff (stated up front, per the plan -- not adjusted after seeing results)
MIN_COUNT_PER_POWIAT = 5
MIN_POWIATY_COVERED = 18  # of 24

# Large-park handling: a single geometric centroid badly represents a giant,
# irregular polygon (Las Lagiewnicki in Lodz is 1339.8 ha, 52 km of boundary)
# -- someone at the edge of such a park is nowhere near its centre point, so
# the accessibility metric would call them "not reached" even though they can
# walk straight in. Parks above this area get several destination points
# spaced around their boundary instead of one interior point; parks at or
# below it (>90% of the ~194 in the Lodz clip) are unaffected. Found and
# sized against real data 2026-09-13: 45 of 194 Lodz-clip park polygons
# exceed 5 ha.
#
# A FIXED point count per large park (originally 4) was checked visually
# (mcp__qgis__render_map on Las Lagiewnicki) and found too sparse: 4 points
# on a 52 km boundary leaves multi-km gaps, so a resident at the edge still
# reads as "not reached". Point count now scales with sqrt(area) instead --
# gentle for the merely-large (Las Chelmy 120.9 ha, Park na Zdrowiu 209.6 ha
# both still land on 4-5) but reaches 12 for the one genuinely enormous case,
# capped so the "park" category isn't blown out of proportion to every other
# opportunity category in the cumulative-count metric.
LARGE_PARK_AREA_HA = 5
MIN_POINTS_PER_LARGE_PARK = 4
MAX_POINTS_PER_LARGE_PARK = 12


def _n_boundary_points(area_ha):
    return min(MAX_POINTS_PER_LARGE_PARK, max(MIN_POINTS_PER_LARGE_PARK, round(area_ha ** 0.5 / 3)))


def _tag_expr(key, val):
    if isinstance(val, list):
        vals = ",".join(f"'{v}'" for v in val)
        return f'"{key}" IN ({vals})'
    return f'"{key}" = \'{val}\''


def _mp_expr(cat):
    key, val = CATEGORY_TAGS[cat]
    parts = [_tag_expr(key, val)]
    for k2, v2 in EXTRA_OR.get(cat, []):
        parts.append(_tag_expr(k2, v2))
    return " OR ".join(parts)


def _points_expr(cat):
    """OGR's OSM 'points' layer has no dedicated amenity/shop/etc columns --
    tags are packed into a hstore-like 'other_tags' string, same pattern as
    realtime_delay_cities/prepare_data.py."""
    key, val = CATEGORY_TAGS[cat]
    vals = val if isinstance(val, list) else [val]
    parts = [f'"other_tags" LIKE \'%"{key}"=>"{v}"%\'' for v in vals]
    for k2, v2 in EXTRA_OR.get(cat, []):
        parts.append(f'"other_tags" LIKE \'%"{k2}"=>"{v2}"%\'')
    return " OR ".join(parts)


def load_pbf_layers(pbf_path):
    """Load + fix geometries ONCE, reused across all ~20 category filters --
    the original per-category version reopened and fixed the whole pbf's
    multipolygons layer 20 times over, which is the difference between one
    fixgeometries pass and twenty on a voivodeship-sized OSM extract."""
    import processing
    from qgis.core import QgsVectorLayer

    mp = QgsVectorLayer(f"{pbf_path}|layername=multipolygons", "mp", "ogr")
    pts = QgsVectorLayer(f"{pbf_path}|layername=points", "pts", "ogr")
    mp_fixed = processing.run("native:fixgeometries", {"INPUT": mp, "OUTPUT": "memory:"})["OUTPUT"]
    print(f"  loaded+fixed: {mp_fixed.featureCount()} multipolygons, {pts.featureCount()} points")
    return mp_fixed, pts


def _park_destination_points(mp_match):
    """Small/medium park polygons -> single centroid (unchanged behaviour).
    Polygons over LARGE_PARK_AREA_HA -> POINTS_PER_LARGE_PARK points spaced
    evenly along the boundary, so a hexagon near ANY edge of a huge park
    counts as reaching it, not just one near its geometric centre. Per-park
    (not per-metre) spacing keeps a giant polygon from contributing a huge
    number of destination points -- every large park gets the same fixed
    point count regardless of its perimeter."""
    import processing
    from qgis.core import QgsVectorLayer

    reproj = processing.run("native:reprojectlayer", {
        "INPUT": mp_match, "TARGET_CRS": "EPSG:2180", "OUTPUT": "memory:",
    })["OUTPUT"]

    small = QgsVectorLayer("Polygon?crs=EPSG:2180", "small_parks", "memory")
    large_pts_feats = []
    for f in reproj.getFeatures():
        geom = f.geometry()
        area_ha = geom.area() / 10000.0
        if area_ha <= LARGE_PARK_AREA_HA:
            small.dataProvider().addFeatures([f])
            continue
        one = QgsVectorLayer("Polygon?crs=EPSG:2180", "one_park", "memory")
        one.dataProvider().addFeatures([f])
        line = processing.run("native:polygonstolines", {"INPUT": one, "OUTPUT": "memory:"})["OUTPUT"]
        n_points = _n_boundary_points(area_ha)
        pts_along = processing.run("native:pointsalonglines", {
            "INPUT": line, "DISTANCE": geom.length() / n_points,
            "START_OFFSET": 0, "OUTPUT": "memory:",
        })["OUTPUT"]
        large_pts_feats.extend(pts_along.getFeatures())

    small_centroids = processing.run("native:centroids", {
        "INPUT": small, "ALL_PARTS": False, "OUTPUT": "memory:",
    })["OUTPUT"]
    large_out = QgsVectorLayer("Point?crs=EPSG:2180", "large_park_pts", "memory")
    large_out.dataProvider().addFeatures(large_pts_feats)

    merged = processing.run("native:mergevectorlayers", {
        "LAYERS": [small_centroids, large_out], "CRS": "EPSG:2180", "OUTPUT": "memory:",
    })["OUTPUT"]
    return processing.run("native:reprojectlayer", {
        "INPUT": merged, "TARGET_CRS": "EPSG:4326", "OUTPUT": "memory:",
    })["OUTPUT"]


def extract_category(mp_fixed, pts, cat):
    """Returns a memory point layer (EPSG:4326) for one category: polygon
    centroids deduplicated against standalone nodes (a node inside an
    already-counted polygon is dropped). Category "park" uses boundary
    sampling for large polygons instead of a single centroid -- see
    _park_destination_points."""
    import processing

    mp_match = processing.run("native:extractbyexpression", {
        "INPUT": mp_fixed, "EXPRESSION": _mp_expr(cat), "OUTPUT": "memory:",
    })["OUTPUT"]
    if cat == "park":
        mp_centroids = _park_destination_points(mp_match)
    else:
        mp_centroids = processing.run("native:centroids", {
            "INPUT": mp_match, "ALL_PARTS": False, "OUTPUT": "memory:",
        })["OUTPUT"]

    pts_match = processing.run("native:extractbyexpression", {
        "INPUT": pts, "EXPRESSION": _points_expr(cat), "OUTPUT": "memory:",
    })["OUTPUT"]
    pts_standalone = processing.run("native:extractbylocation", {
        "INPUT": pts_match, "PREDICATE": [2], "INTERSECT": mp_match, "OUTPUT": "memory:",
    })["OUTPUT"] if mp_match.featureCount() > 0 else pts_match

    merged = processing.run("native:mergevectorlayers", {
        "LAYERS": [mp_centroids, pts_standalone], "CRS": None, "OUTPUT": "memory:",
    })["OUTPUT"]
    return merged


def coverage_per_powiat(category_layers, powiat_layer):
    """Returns dict: powiat_teryt -> {category: count}. Uses a spatial join
    with an index on the powiat layer (177-feature gminy scale is trivial,
    but this keeps the pattern consistent for the 24-powiat join)."""
    import processing

    counts = defaultdict(lambda: defaultdict(int))
    for cat, lyr in category_layers.items():
        if lyr.featureCount() == 0:
            continue
        joined = processing.run("native:joinattributesbylocation", {
            "INPUT": lyr, "PREDICATE": [0], "JOIN": powiat_layer,
            "JOIN_FIELDS": ["JPT_KOD_JE"], "METHOD": 0,
            "DISCARD_NONMATCHING": True, "OUTPUT": "memory:",
        })["OUTPUT"]
        for f in joined.getFeatures():
            counts[f["JPT_KOD_JE"]][cat] += 1
    return counts


def build_destination_layer(category_layers, survivors, out_gpkg, layer_name):
    """Merges survivor categories into ONE point destination layer with a
    one-hot Integer field per category (srv_<cat>) -- matches the R5
    OPPORTUNITY_FIELDS pattern already validated in realtime_delay_lodz
    (individual POI as destinations, not pre-aggregated to hex centroids;
    modal_complementarity_lodz's control check found hex-centroid
    aggregation only an approximation, rho=0.9886 vs exact points -- so we
    use exact points here as the more precise, already-proven choice, and
    only fall back to hex aggregation if E6 calibration shows the resulting
    destination count is a real routing-cost problem)."""
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField, QgsFeature
    from qgis.PyQt.QtCore import QVariant

    merged = processing.run("native:mergevectorlayers", {
        "LAYERS": [category_layers[c] for c in survivors], "CRS": None, "OUTPUT": "memory:",
    })["OUTPUT"] if survivors else None

    out = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
    pr = out.dataProvider()
    pr.addAttributes([QgsField("poi_id", QVariant.String)] +
                      [QgsField(f"srv_{c}", QVariant.Int) for c in survivors])
    out.updateFields()

    feats = []
    poi_counter = 0
    for cat in survivors:
        lyr = category_layers[cat]
        for f in lyr.getFeatures():
            poi_counter += 1
            nf = QgsFeature(out.fields())
            nf.setGeometry(f.geometry())
            nf.setAttribute("poi_id", f"{cat}/{poi_counter}")
            for c2 in survivors:
                nf.setAttribute(f"srv_{c2}", 1 if c2 == cat else 0)
            feats.append(nf)
    pr.addFeatures(feats)
    out.updateExtents()
    print(f"destination layer '{layer_name}': {out.featureCount()} POI, "
          f"{len(survivors)} categories")

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = layer_name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out, out_gpkg, out.transformContext(), opts)
    print(f"wrote {layer_name} to {out_gpkg}")
    return out


def _write_poi_all_raw_cache(category_layers, out_gpkg):
    """One gpkg layer, all candidate categories, field 'category' -- the
    expensive-to-produce raw material for everything downstream."""
    import processing
    from qgis.core import QgsVectorFileWriter, QgsField, QgsFeature
    from qgis.PyQt.QtCore import QVariant

    layers_with_cat = []
    for cat, lyr in category_layers.items():
        tagged = processing.run("native:fieldcalculator", {
            "INPUT": lyr, "FIELD_NAME": "category", "FIELD_TYPE": 2, "FIELD_LENGTH": 40,
            "FORMULA": f"'{cat}'", "OUTPUT": "memory:",
        })["OUTPUT"] if lyr.featureCount() > 0 else None
        if tagged is not None:
            layers_with_cat.append(tagged)

    merged = processing.run("native:mergevectorlayers", {
        "LAYERS": layers_with_cat, "CRS": None, "OUTPUT": "memory:",
    })["OUTPUT"]

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "poi_all_raw"
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(merged, out_gpkg, merged.transformContext(), opts)
    print(f"  cached {merged.featureCount()} raw POI to poi_all_raw")


def main():
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter
    import csv

    pbf = str(C.PBF_WOJ)
    gpkg = str(C.PRG_GPKG)
    powiaty = QgsVectorLayer(gpkg + "|layername=powiaty", "powiaty", "ogr")
    n_powiaty = powiaty.featureCount()
    print(f"powiaty: {n_powiaty}")

    print("=== E4 step 1: extracting all candidate categories ===")
    # Cache EVERY candidate category (all 20, survivors decided below) into
    # one gpkg layer immediately. This step alone took ~25-30 min against
    # the voivodeship pbf (a full points-layer LIKE-scan per category) --
    # anything downstream (destination-layer assembly, re-running with a
    # different cutoff) must never have to repeat it.
    cache_check = QgsVectorLayer(gpkg + "|layername=poi_all_raw", "cache_check", "ogr")
    if cache_check.isValid() and cache_check.featureCount() > 0:
        print(f"  poi_all_raw cache hit: {cache_check.featureCount()} features, skipping extraction")
        category_layers = {}
        for cat in CATEGORY_TAGS:
            category_layers[cat] = processing.run("native:extractbyexpression", {
                "INPUT": cache_check, "EXPRESSION": f"\"category\" = '{cat}'", "OUTPUT": "memory:",
            })["OUTPUT"]
            print(f"  {cat}: {category_layers[cat].featureCount()} (from cache)")
    else:
        mp_fixed, pts = load_pbf_layers(pbf)
        category_layers = {}
        for cat in CATEGORY_TAGS:
            lyr = extract_category(mp_fixed, pts, cat)
            category_layers[cat] = lyr
            print(f"  {cat}: {lyr.featureCount()}")
        _write_poi_all_raw_cache(category_layers, gpkg)

    print("\n=== E4 step 2: coverage per powiat ===")
    counts = coverage_per_powiat(category_layers, powiaty)

    C.OUT.mkdir(parents=True, exist_ok=True)
    csv_path = C.OUT / "poi_coverage_powiaty.csv"
    powiat_names = {f["JPT_KOD_JE"]: f["JPT_NAZWA_"] for f in powiaty.getFeatures()}
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["powiat_teryt", "powiat_nazwa"] + list(CATEGORY_TAGS))
        for teryt, name in sorted(powiat_names.items()):
            row = [teryt, name] + [counts[teryt].get(cat, 0) for cat in CATEGORY_TAGS]
            w.writerow(row)
    print(f"wrote {csv_path}")

    print("\n=== E4 step 3: apply cutoff (>=5 in >=18/24 powiaty) ===")
    survivors, rejected = [], []
    for cat in CATEGORY_TAGS:
        n_covered = sum(1 for teryt in powiat_names if counts[teryt].get(cat, 0) >= MIN_COUNT_PER_POWIAT)
        total = sum(counts[teryt].get(cat, 0) for teryt in powiat_names)
        verdict = "OK" if n_covered >= MIN_POWIATY_COVERED else "REJECTED"
        print(f"  {cat}: total={total} powiaty_with_>=5={n_covered}/{n_powiaty} -> {verdict}")
        (survivors if verdict == "OK" else rejected).append(cat)

    print(f"\nSURVIVORS ({len(survivors)}): {survivors}")
    print(f"REJECTED ({len(rejected)}) -- goes to 'ograniczenia danych' layer, not dropped: {rejected}")

    print("\n=== E4 step 4: destination layers (woj + lodz-clipped) ===")
    poi_woj = build_destination_layer(category_layers, survivors, gpkg, "poi_targets_woj")

    # NOTE: boundary_lodz's on-disk extent metadata was found stale/degenerate
    # (ogrinfo showed a near-zero bbox, a GPKG gpkg_contents caching quirk --
    # the geometry itself may be fine but don't risk a bbox-prefilter false
    # negative). hex_grid_lodz's extent was independently verified correct
    # (22.2 x 19.5 km, matches Lodz), so clip against that instead.
    lodz_extent_src = QgsVectorLayer(gpkg + "|layername=hex_grid_lodz", "lodz_hex", "ogr")
    category_layers_lodz = {}
    for cat, lyr in category_layers.items():
        clipped = processing_extractbylocation_or_all(lyr, lodz_extent_src)
        category_layers_lodz[cat] = clipped
    poi_lodz = build_destination_layer(category_layers_lodz, survivors, gpkg, "poi_targets_lodz")

    return {
        "category_layers": category_layers, "counts": counts,
        "survivors": survivors, "rejected": rejected, "powiat_names": powiat_names,
        "poi_woj": poi_woj, "poi_lodz": poi_lodz,
    }


def build_lodz_all_categories(gpkg=None):
    """Lodz-specific deviation from the voivodeship coverage filter (Michal,
    2026-09-13): the >=5-in->=18/24-powiaty threshold was calibrated to
    separate genuine OSM gaps from rural rarity, and it correctly rejects 11
    categories at that scale -- but every one of them trivially clears >=5
    objects within Lodz itself (checked directly: uczelnia 88, szpital 25,
    biblioteka 84, dom_kultury 23, kino 12, teatr 25, muzeum 32, silownia 44,
    basen 51, centrum_handlowe 39, targowisko 27). So for Lodz only, ALL 21
    candidate categories go into poi_targets_lodz, not just the 10 voivodeship
    survivors. poi_targets_woj is untouched -- this is a documented, one-off
    methodological difference: Lodz is analysed on a different POI category
    set than the voivodeship (MULTIDAY_LODZ_NOTES.md), not a change to the
    voivodeship threshold itself. Reads from the poi_all_raw cache, no PBF
    rescan needed."""
    import processing
    from qgis.core import QgsVectorLayer

    gpkg = str(gpkg or __import__("config").PRG_GPKG)
    raw = QgsVectorLayer(f"{gpkg}|layername=poi_all_raw", "raw", "ogr")
    lodz_hex = QgsVectorLayer(f"{gpkg}|layername=hex_grid_lodz", "lodz_hex", "ogr")

    all_cats = list(CATEGORY_TAGS)
    category_layers_lodz = {}
    for cat in all_cats:
        lyr = processing.run("native:extractbyexpression", {
            "INPUT": raw, "EXPRESSION": f"\"category\" = '{cat}'", "OUTPUT": "memory:",
        })["OUTPUT"]
        category_layers_lodz[cat] = processing_extractbylocation_or_all(lyr, lodz_hex)
        print(f"  {cat}: {category_layers_lodz[cat].featureCount()} (Lodz)")

    poi_lodz = build_destination_layer(category_layers_lodz, all_cats, gpkg, "poi_targets_lodz")
    return poi_lodz


def processing_extractbylocation_or_all(lyr, boundary_layer):
    import processing
    if lyr.featureCount() == 0:
        return lyr
    return processing.run("native:extractbylocation", {
        "INPUT": lyr, "PREDICATE": [0], "INTERSECT": boundary_layer, "OUTPUT": "memory:",
    })["OUTPUT"]


if __name__ == "__main__":
    main()
