"""E3 -- population on hexagons for wojewodztwo lodzkie + Lodz city.

Runs inside QGIS (mcp__qgis__execute_code) -- uses openpyxl (bundled in the
QGIS python env by the easy-R5 plugin bootstrap), processing.run, native:*.

Steps:
  1. Parse ludnosc_nsp_2021.xlsx "Lodzkie" sheet into a (gmina7, rejon6, obw) ->
     population lookup. Population source is the NSP2021 CENSUS total
     (wojewodztwo row = 2 410 286), not the newer ~2 328 825 GUS demographic
     estimate -- our whole precinct geometry (SU_BREC) is NSP2021-vintage,
     so we validate against the matching-vintage total.
  2. Join onto obwody_spisowe_raw (SU_BREC, EPSG:2180 reassigned -- source
     .prj has no EPSG authority code but matches EPSG:2180 parameters
     exactly). Unmatched precincts get population = NULL, never 0.
  3. Build hex grids: wojewodztwo 1000 m, Lodz 250 m. Boundary = stepped
     dissolve of the grid itself (buffer +1/-1), not a plain dissolve of the
     14000+ precinct polygons (fragments into dozens of parts per prior
     tools/ experience).
  4. Areal population overlay (native: pipeline ported from
     easy_r5/algorithms/population_overlay.py) as the baseline; dasymetric
     building-weighted correction is a separate step (dasymetric_pop.py,
     ported from tools/realtime_delay_cities, tiled per powiat for the
     voivodeship scale -- see that module's docstring).

Gate: |sum(population) over matched precincts - 2410286| / 2410286 <= 1%.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

GPKG = C.PRG_GPKG


def load_population_lookup():
    """Returns dict (gmina7, rejon6, obw) -> population (int)."""
    import openpyxl

    wb = openpyxl.load_workbook(str(C.LUDNOSC_XLSX), read_only=True, data_only=True)
    ws = wb["Łódzkie"]

    lookup = {}
    current_gmina = None
    current_rejon = None
    n_obw_rows = 0
    for row in ws.iter_rows(min_row=7, values_only=True):
        struktura = row[3]
        if struktura is None:
            continue
        if struktura in ("gmina miejska", "gmina wiejska", "miasto", "obszar wiejski", "delegatura"):
            current_gmina = str(int(row[4])).zfill(7)
            current_rejon = None
        elif struktura == "rejon statystyczny":
            current_rejon = str(int(row[4])).zfill(6)
        elif struktura == "obwód spisowy":
            n_obw_rows += 1
            obw = str(int(row[4]))
            pop = row[5]
            if current_gmina is None or current_rejon is None:
                continue
            lookup[(current_gmina, current_rejon, obw)] = pop
        # "gmina miejsko-wiejska", "wojewodztwo", "powiat", "miasto na prawach
        # powiatu", "Polska - ogolem" are parent rollup rows -- deliberately
        # not tracked as current_gmina, since their children are "miasto" /
        # "obszar wiejski" (or delegatura for Lodz), which we do track. Using
        # the parent would double count against those children.

    print(f"xlsx: {n_obw_rows} obwod-spisowy rows, {len(lookup)} unique keys")
    return lookup


def join_population(obwody_layer, lookup):
    """Adds a Double 'population' field, NULL where unmatched. Returns
    (matched_count, unmatched_count, sum_population)."""
    import processing
    from qgis.core import QgsField
    from qgis.PyQt.QtCore import QVariant

    out = processing.run("native:fixgeometries", {"INPUT": obwody_layer, "OUTPUT": "memory:"})["OUTPUT"]
    out.dataProvider().addAttributes([QgsField("population", QVariant.Double, len=12, prec=0)])
    out.updateFields()
    out.startEditing()
    idx = out.fields().indexOf("population")
    matched, unmatched = 0, 0
    for f in out.getFeatures():
        key = (f["GMINA"], f["REJ"], f["OBW"])
        pop = lookup.get(key)
        if pop is None:
            unmatched += 1
            continue
        matched += 1
        out.changeAttributeValue(f.id(), idx, float(pop))
    out.commitChanges()

    total = sum(f["population"] for f in out.getFeatures() if f["population"] is not None)
    print(f"join: matched={matched} unmatched={unmatched} sum_population={total}")
    return out, matched, unmatched, total


def build_stepped_boundary(polygon_layer, out_name="boundary"):
    """Dissolve via +1/-1 buffer -- plain native:dissolve on 14000+ precinct
    polygons fragments into dozens of parts (documented in
    realtime_delay_cities/rebuild_boundary.py)."""
    import processing

    grown = processing.run("native:buffer", {
        "INPUT": polygon_layer, "DISTANCE": 1, "SEGMENTS": 5, "DISSOLVE": True,
        "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2, "OUTPUT": "memory:",
    })["OUTPUT"]
    shrunk = processing.run("native:buffer", {
        "INPUT": grown, "DISTANCE": -1, "SEGMENTS": 5, "DISSOLVE": True,
        "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2, "OUTPUT": "memory:",
    })["OUTPUT"]
    single = processing.run("native:multiparttosingleparts", {"INPUT": shrunk, "OUTPUT": "memory:"})["OUTPUT"]
    print(f"{out_name}: {single.featureCount()} part(s) after stepped dissolve")
    return single


def build_hex_grid(boundary_layer, spacing_m, crs):
    """native:creategrid TYPE=4 (hexagon) -> extract by location -> hex_id."""
    import processing
    from qgis.core import QgsField
    from qgis.PyQt.QtCore import QVariant

    extent_layer = boundary_layer
    extent = extent_layer.extent()
    extent_str = f"{extent.xMinimum()},{extent.xMaximum()},{extent.yMinimum()},{extent.yMaximum()} [{crs.authid()}]"

    grid = processing.run("native:creategrid", {
        "TYPE": 4, "EXTENT": extent_str, "HSPACING": spacing_m, "VSPACING": spacing_m,
        "HOVERLAY": 0, "VOVERLAY": 0, "CRS": crs, "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"grid raw: {grid.featureCount()} hexagons at {spacing_m} m")

    clipped = processing.run("native:extractbylocation", {
        "INPUT": grid, "PREDICATE": [0], "INTERSECT": boundary_layer, "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"grid clipped: {clipped.featureCount()} hexagons")

    clipped.dataProvider().addAttributes([QgsField("hex_id", QVariant.Int)])
    clipped.updateFields()
    clipped.startEditing()
    idx = clipped.fields().indexOf("hex_id")
    for i, f in enumerate(clipped.getFeatures()):
        clipped.changeAttributeValue(f.id(), idx, i)
    clipped.commitChanges()
    return clipped


def main():
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsCoordinateReferenceSystem

    print("=== E3 step 1: population lookup from xlsx ===")
    lookup = load_population_lookup()
    ref_total = 2410286
    lookup_total = sum(lookup.values())
    print(f"lookup total (all keys): {lookup_total} vs census wojewodztwo row {ref_total} "
          f"({100*(lookup_total-ref_total)/ref_total:+.4f}%)")

    print("\n=== E3 step 2: join onto SU_BREC obwody ===")
    obwody_raw = QgsVectorLayer(str(GPKG) + "|layername=obwody_spisowe_raw", "obwody_raw", "ogr")
    obwody_raw.setCrs(QgsCoordinateReferenceSystem("EPSG:2180"))
    obwody, matched, unmatched, total_matched_pop = join_population(obwody_raw, lookup)

    diff_pct = 100 * abs(total_matched_pop - ref_total) / ref_total
    print(f"GATE population sum vs census total: {diff_pct:.4f}% (must be <= 1%)")
    if diff_pct > 1.0:
        raise RuntimeError(f"GATE FAILED: population sum off by {diff_pct:.2f}%")

    out_gpkg = str(GPKG)
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "obwody_spisowe"
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(obwody, out_gpkg, obwody.transformContext(), opts)
    print("wrote layer obwody_spisowe")

    print("\n=== E3 step 3: boundaries + hex grids ===")
    crs = QgsCoordinateReferenceSystem("EPSG:2180")

    woj_boundary = build_stepped_boundary(obwody, "wojewodztwo boundary")
    opts2 = QgsVectorFileWriter.SaveVectorOptions()
    opts2.driverName = "GPKG"
    opts2.layerName = "boundary_woj"
    opts2.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(woj_boundary, out_gpkg, woj_boundary.transformContext(), opts2)

    hex_woj = build_hex_grid(woj_boundary, C.HEX_SPACING_WOJ_M, crs)
    opts3 = QgsVectorFileWriter.SaveVectorOptions()
    opts3.driverName = "GPKG"
    opts3.layerName = "hex_grid_woj"
    opts3.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(hex_woj, out_gpkg, hex_woj.transformContext(), opts3)
    print(f"wrote hex_grid_woj: {hex_woj.featureCount()} hexagons")

    # Lodz-city boundary: obwody whose GMINA is one of the 5 Lodz delegatura codes
    import processing
    lodz_obwody = processing.run("native:extractbyexpression", {
        "INPUT": obwody,
        "EXPRESSION": '"GMINA" IN (\'1061029\',\'1061039\',\'1061049\',\'1061059\',\'1061069\')',
        "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"Lodz precincts: {lodz_obwody.featureCount()}")
    lodz_boundary = build_stepped_boundary(lodz_obwody, "Lodz boundary")
    opts4 = QgsVectorFileWriter.SaveVectorOptions()
    opts4.driverName = "GPKG"
    opts4.layerName = "boundary_lodz"
    opts4.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(lodz_boundary, out_gpkg, lodz_boundary.transformContext(), opts4)

    hex_lodz = build_hex_grid(lodz_boundary, C.HEX_SPACING_LODZ_M, crs)
    opts5 = QgsVectorFileWriter.SaveVectorOptions()
    opts5.driverName = "GPKG"
    opts5.layerName = "hex_grid_lodz"
    opts5.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(hex_lodz, out_gpkg, hex_lodz.transformContext(), opts5)
    print(f"wrote hex_grid_lodz: {hex_lodz.featureCount()} hexagons")

    lodz_area_km2 = sum(f.geometry().area() for f in lodz_boundary.getFeatures()) / 1e6
    print(f"Lodz boundary area: {lodz_area_km2:.1f} km2 (expect ~293 km2)")

    return {
        "obwody": obwody, "matched": matched, "unmatched": unmatched,
        "total_matched_pop": total_matched_pop, "hex_woj": hex_woj, "hex_lodz": hex_lodz,
        "woj_boundary": woj_boundary, "lodz_boundary": lodz_boundary,
    }


if __name__ == "__main__":
    main()
