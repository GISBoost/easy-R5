"""Export hex_delay + hex_net_opportunities (both resolutions), plus the
boundary and siatka reference layers, to GeoJSON for the interactive web
version at mapy-analizy/opoznienia-dostepnosc.

Reads delay_lodz.gpkg / delay_lodz_500m.gpkg (produced by prepare_data.py +
run_accessibility.py + compute_delay.py; boundary/siatka added directly via
the QGIS provider API while preparing Michal's print atlas -- see git log),
writes into the SIBLING mapy-analizy repo's data/ folder -- a manual,
occasional re-export, same pattern as uczelnie-dostepnosc's README
("Odswiezenie danych = ponowne uruchomienie pipeline'u ... i re-eksport do
data/, na razie recznie").

Writes: hex_250.geojson, hex_500.geojson (the choropleth data), siatka_250.geojson,
siatka_500.geojson (hex_id + geometry only, outline-reference grid -- includes
hexagons the data layer filters out as null), boundary.geojson (city outline,
resolution-independent), manifest.json.

Must run inside the QGIS Python environment, e.g. mcp__qgis__execute_code.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import processing
    from qgis.core import (
        QgsFeature,
        QgsFields,
        QgsProcessing,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit("export_geojson.py needs qgis.core + processing.") from exc

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent          # .../easy-R5
EASY_ROOT = REPO_ROOT.parent            # .../easy
MAPY_DATA = EASY_ROOT / "mapy-analizy" / "opoznienia-dostepnosc" / "data"

CATEGORIES = ("school", "pharmacy", "university", "mall")
RESOLUTIONS = {"250": HERE / "delay_lodz.gpkg", "500": HERE / "delay_lodz_500m.gpkg"}
ANALYSIS_DATE = "2026-08-21"

# Fields copied from hex_delay onto the exported feature (base0_<category> is
# dropped -- redundant with base_<category> == 0, and it's one less field per
# feature over the wire).
DELAY_FIELDS = ["hex_id", "pop_total"]
for _cat in CATEGORIES:
    DELAY_FIELDS += [f"delta_{_cat}", f"base_{_cat}"]


def _merge_layer(gpkg: Path) -> QgsVectorLayer:
    hex_delay = QgsVectorLayer(f"{gpkg}|layername=hex_delay", "hex_delay", "ogr")
    net = QgsVectorLayer(f"{gpkg}|layername=hex_net_opportunities", "net", "ogr")
    if not hex_delay.isValid() or not net.isValid():
        raise RuntimeError(f"Could not load hex_delay/hex_net_opportunities from {gpkg}")

    net_by_hex = {f["hex_id"]: (f["net_delta"], f["net_delta_n"]) for f in net.getFeatures()}

    fields = QgsFields()
    for name in DELAY_FIELDS:
        fields.append(hex_delay.fields().field(name))
    fields.append(net.fields().field("net_delta"))
    fields.append(net.fields().field("net_delta_n"))

    mem = QgsVectorLayer(f"Polygon?crs={hex_delay.crs().authid() or hex_delay.crs().toWkt()}",
                          "merged", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    out_feats = []
    for f in hex_delay.getFeatures():
        hid = f["hex_id"]
        if hid not in net_by_hex:
            raise RuntimeError(f"hex_id {hid} missing from hex_net_opportunities in {gpkg}")
        net_delta, net_delta_n = net_by_hex[hid]
        nf = QgsFeature(mem.fields())
        nf.setGeometry(f.geometry())
        for name in DELAY_FIELDS:
            nf[name] = f[name]
        nf["net_delta"] = net_delta
        nf["net_delta_n"] = net_delta_n
        out_feats.append(nf)
    mem.dataProvider().addFeatures(out_feats)
    return mem


def export_resolution(res_key: str, gpkg: Path):
    merged = _merge_layer(gpkg)
    reprojected = processing.run("native:reprojectlayer", {
        "INPUT": merged, "TARGET_CRS": "EPSG:4326", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })["OUTPUT"]
    _write_geojson(reprojected, MAPY_DATA / f"hex_{res_key}.geojson")
    return reprojected.featureCount()


def _write_geojson(layer, out_path: Path):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GeoJSON"
    opts.layerOptions = ["COORDINATE_PRECISION=6"]
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(out_path), layer.transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write {out_path}: {err}")
    size_kb = out_path.stat().st_size / 1024
    print(f"[ok] {out_path.name}: {layer.featureCount()} features, {size_kb:.0f} KB")


def export_boundary(gpkg: Path):
    """City outline -- same real-world polygon regardless of hex resolution,
    exported once from the 250 m gpkg (see prepare_data.py -- it's copied
    identically into both)."""
    boundary = QgsVectorLayer(f"{gpkg}|layername=boundary", "boundary", "ogr")
    if not boundary.isValid():
        raise RuntimeError(f"Could not load boundary from {gpkg}")
    reprojected = processing.run("native:reprojectlayer", {
        "INPUT": boundary, "TARGET_CRS": "EPSG:4326", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })["OUTPUT"]
    _write_geojson(reprojected, MAPY_DATA / "boundary.geojson")
    return reprojected


def export_siatka(res_key: str, gpkg: Path):
    """Outline-only hex grid reference, geometry only -- includes hexagons
    filtered out of hex_<res>.geojson (null delta/net_delta), unlike the data
    layer, so the full grid extent stays visible as a graticule."""
    siatka = QgsVectorLayer(f"{gpkg}|layername=siatka", "siatka", "ogr")
    if not siatka.isValid():
        raise RuntimeError(f"Could not load siatka from {gpkg}")
    reprojected = processing.run("native:reprojectlayer", {
        "INPUT": siatka, "TARGET_CRS": "EPSG:4326", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })["OUTPUT"]
    _write_geojson(reprojected, MAPY_DATA / f"siatka_{res_key}.geojson")


def export_manifest(boundary_layer, feature_counts: dict):
    ext = boundary_layer.extent()
    bounds = [[ext.yMinimum(), ext.xMinimum()], [ext.yMaximum(), ext.xMaximum()]]

    manifest = {
        "city": "Łódź",
        "date": ANALYSIS_DATE,
        "bounds": bounds,
        "resolutions": [
            {"key": "250", "label": "250 m", "featureCount": feature_counts["250"]},
            {"key": "500", "label": "500 m", "featureCount": feature_counts["500"]},
        ],
        "categories": [
            {"key": "school", "label_pl": "Szkoły", "label_en": "Schools"},
            {"key": "pharmacy", "label_pl": "Apteki", "label_en": "Pharmacies"},
            {"key": "university", "label_pl": "Uczelnie", "label_en": "Universities"},
            {"key": "mall", "label_pl": "Centra handlowe", "label_en": "Malls"},
        ],
    }
    out_path = MAPY_DATA / "manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out_path}")


def main():
    MAPY_DATA.mkdir(parents=True, exist_ok=True)
    feature_counts = {}
    for res_key, gpkg in RESOLUTIONS.items():
        if not gpkg.exists():
            raise RuntimeError(f"{gpkg} missing -- run the local pipeline first.")
        feature_counts[res_key] = export_resolution(res_key, gpkg)
        export_siatka(res_key, gpkg)
    boundary_layer = export_boundary(RESOLUTIONS["250"])
    export_manifest(boundary_layer, feature_counts)
    print("[done] export_geojson.py finished.")


if __name__ == "__main__":
    main()
