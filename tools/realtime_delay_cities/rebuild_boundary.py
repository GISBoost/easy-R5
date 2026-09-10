"""Rebuild each city's `boundary` layer as the DISSOLVE OF THE HEX GRID -- a
stepped outline that hugs the hexes -- instead of the smooth dissolved
`obwody_spisowe`. Łódź already had this shape; this makes the other 5 match.

The census boundary and the hex-grid boundary differ by a hexagon's width at
the edge (and the census one carries ~30 leftover attribute columns). For a
map whose whole content is the hex grid, the stepped outline is the honest
frame.

Run inside QGIS (mcp__qgis__execute_code):
    import rebuild_boundary as rb
    rb.all()                      # every city + resolution, incl. Łódź
then re-run export_geojson + build_project.
"""

from __future__ import annotations

from pathlib import Path

try:
    import processing
    from qgis.core import QgsProcessing, QgsVectorFileWriter, QgsVectorLayer
except ImportError as exc:  # pragma: no cover
    raise SystemExit("rebuild_boundary.py runs inside QGIS.") from exc

from dasymetric_pop import _paths  # same city -> gpkg / label resolver


def _run(alg, params, out="OUTPUT"):
    return processing.run(alg, params)[out]


def rebuild(city: str, spacing_m: int):
    P = _paths(city)
    gpkg = P["gpkg"](spacing_m)
    si = QgsVectorLayer(f"{gpkg}|layername=siatka", "siatka", "ogr")
    if not si.isValid():
        raise RuntimeError(f"no siatka in {gpkg}")

    # Plain dissolve of a 250 m hex grid in this custom CRS fragments into ~50
    # chunks (creategrid's neighbouring hex edges are not bit-identical). A
    # +1 m / -1 m buffer round-trip closes those sub-metre seams while leaving
    # genuine islands (river/sea gaps > 2 m) as separate parts, and the ~1 m
    # rounding is invisible at map scale.
    grown = _run("native:buffer", {
        "INPUT": si, "DISTANCE": 1, "DISSOLVE": True,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    dissolved = _run("native:buffer", {
        "INPUT": grown, "DISTANCE": -1, "DISSOLVE": True,
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    single = _run("native:multiparttosingleparts", {
        "INPUT": dissolved, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    named = _run("native:fieldcalculator", {
        "INPUT": single, "FIELD_NAME": "name", "FIELD_TYPE": 2,
        "FIELD_LENGTH": 40, "FIELD_PRECISION": 0, "FORMULA": f"'{_label(city)}'",
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    bare = _run("native:retainfields", {
        "INPUT": named, "FIELDS": ["name"], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "boundary"
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    err = QgsVectorFileWriter.writeAsVectorFormatV3(bare, str(gpkg), bare.transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"write boundary failed: {err}")
    n = sum(1 for _ in bare.getFeatures())
    print(f"[ok] {gpkg.name}: boundary = dissolve(siatka), {n} part(s)")


def _label(city: str) -> str:
    if city == "lodz":
        return "Łódź"
    import cities as C
    return C.CITIES[city][0]


def all():  # noqa: A003 -- deliberately short
    import cities as C
    for city in list(C.CITIES) + ["lodz"]:
        for r in _paths(city)["resolutions"]:
            rebuild(city, r)
