"""E11 Krok 1 -- export lodzkie_base.gpkg layers to GeoJSON for the
interactive map at mapy-analizy/lodzkie-dostepnosc.

Same skeleton as tools/realtime_delay_lodz/export_geojson.py (the only
precedent in this repo): a field whitelist per layer (drop
native:creategrid's grid bookkeeping and anything the map doesn't need),
reprojection EPSG:2180 -> EPSG:4326, GeoJSON written with
COORDINATE_PRECISION=6 (no geometry simplification -- hex edges are already
coarse, per the precedent's own experience). Categories are read from the
poi_targets_* srv_* fields at run time rather than hardcoded, so a category
added/dropped in E4 doesn't need this file edited too.

Two-stage write (Michal, 2026-09-14 plan): export_all(STAGING) first --
stays inside easy-R5, safe to rerun while iterating on field lists and
measuring sizes. Only after Michal confirms the reported sizes does a
second, explicit call target PUBLISH (mapy-analizy/lodzkie-dostepnosc/data)
-- that is the one call that actually touches the mapy-analizy repo.
Running this file directly always writes to STAGING; call
export_all(PUBLISH) yourself (e.g. via mcp__qgis__execute_code) once ready.

Must run inside the QGIS Python environment (mcp__qgis__execute_code).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C

try:
    import processing
    from qgis.core import QgsProcessing, QgsVectorFileWriter, QgsVectorLayer
except ImportError as exc:  # pragma: no cover
    raise SystemExit("export_geojson.py needs qgis.core + processing.") from exc

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent          # .../easy-R5
EASY_ROOT = REPO_ROOT.parent            # .../easy
STAGING = HERE / "out" / "geojson_staging"
PUBLISH = EASY_ROOT / "mapy-analizy" / "lodzkie-dostepnosc" / "data"

GPKG = str(C.PRG_GPKG)


def _survivors(dest_layer_name):
    """Category list read off poi_targets_{woj,lodz}'s own srv_* fields --
    same convention compute_metrics.py uses, so this file can't drift from
    the real E4 category decision."""
    dest = QgsVectorLayer(f"{GPKG}|layername={dest_layer_name}", "d", "ogr")
    if not dest.isValid():
        raise RuntimeError(f"Could not load {dest_layer_name}")
    return [f.name()[4:] for f in dest.fields() if f.name().startswith("srv_")]


def _cat_fields(cats, *patterns):
    """[pattern.format(cat=c) for c in cats+['total'] for pattern in patterns]."""
    out = []
    for c in cats + ["total"]:
        for p in patterns:
            out.append(p.format(cat=c))
    return out


def _export_layer(layer_name, field_whitelist, out_name, out_dir):
    src = QgsVectorLayer(f"{GPKG}|layername={layer_name}", layer_name, "ogr")
    if not src.isValid():
        raise RuntimeError(f"Could not load {layer_name}")
    available = {f.name() for f in src.fields()}
    missing = set(field_whitelist) - available
    if missing:
        raise RuntimeError(f"{layer_name}: fields not found: {sorted(missing)}")

    if field_whitelist:
        thinned = processing.run("native:retainfields", {
            "INPUT": src, "FIELDS": field_whitelist, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        })["OUTPUT"]
    else:
        thinned = src

    reprojected = processing.run("native:reprojectlayer", {
        "INPUT": thinned, "TARGET_CRS": "EPSG:4326", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })["OUTPUT"]
    _write_geojson(reprojected, out_dir / out_name)
    return reprojected


def _write_geojson(layer, out_path):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GeoJSON"
    opts.layerOptions = ["COORDINATE_PRECISION=6"]
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(out_path), layer.transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write {out_path}: {err}")
    size_kb = out_path.stat().st_size / 1024
    print(f"[ok] {out_path.name}: {layer.featureCount()} features, {size_kb:.0f} KB")
    return size_kb


def _layer_plan():
    """Built lazily (not at import time) so this file can be imported for
    its constants/helpers without touching the GPKG."""
    woj_cats = _survivors("poi_targets_woj")   # 10 categories
    lodz_cats = _survivors("poi_targets_lodz")  # 21 categories

    return [
        # (source layer, output filename, field whitelist)
        ("hex_woj_level", "level_woj.geojson",
         ["hex_id", "pop_total"] + _cat_fields(woj_cats, "level_{cat}_c30")),
        # Trimmed to _total fields only (Michal, 2026-09-14): the first,
        # all-fields export measured 23.6 MB, ~4x the next-heaviest file --
        # the map only shows growth_total as the flagship layer (Krok 2), so
        # per-category detail isn't wired to any UI yet. Per-category detail
        # still lives in hex_woj_thresholds inside lodzkie_base.gpkg / the
        # QGIS attribute table if needed later.
        ("hex_woj_thresholds", "growth_woj.geojson",
         ["hex_id", "pop_total", "level_total_c30", "level_total_c60", "growth_total", "ratio_total"]),
        ("hex_lodz_delta", "delta_lodz_wrzesien.geojson",
         ["hex_id", "pop_total", "net_delta_n"]
         + _cat_fields(lodz_cats, "delta_{cat}_c30", "base0_{cat}_c30", "base_{cat}_c30")),
        ("hex_lodz_delta_multiday", "delta_lodz_3dni.geojson",
         ["hex_id", "pop_total"] + _cat_fields(lodz_cats, "avg_delta_{cat}_c30", "spread_{cat}_c30", "base0_{cat}_c30")),
        ("hex_lodz_delta_vacation", "delta_lodz_wakacje.geojson",
         ["hex_id", "pop_total"] + _cat_fields(lodz_cats, "avg_delta_{cat}_c30", "spread_{cat}_c30", "base0_{cat}_c30")),
        # RT coverage mask deliberately NOT exported here (Michal, 2026-09-15):
        # at hex resolution (1000 m / 250 m) it doesn't read as anything
        # meaningful on a web map -- it would only make sense aggregated to
        # gmina/powiat. Still lives in lodzkie_base.gpkg
        # (hex_woj_rt_mask / hex_lodz_rt_mask) and in the QGIS project/print
        # layouts, where the methodological requirement (flag missing RT
        # data, never silently zero) is served by the printed map instead.
        ("hex_woj_all", "siatka_woj.geojson", ["hex_id"]),
        ("hex_lodz_all", "siatka_lodz.geojson", ["hex_id"]),
        ("boundary_woj", "boundary_woj.geojson", []),
        ("boundary_lodz", "boundary_lodz.geojson", []),
    ], woj_cats, lodz_cats


def export_all(out_dir):
    """Writes every layer in _layer_plan() to out_dir, prints per-file and
    total size, and writes a manifest.json. Pass STAGING (default target of
    running this file directly) or PUBLISH (mapy-analizy, only after sizes
    are confirmed -- see module docstring)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan, woj_cats, lodz_cats = _layer_plan()
    results = []
    total_kb = 0.0
    for layer_name, out_name, fields in plan:
        layer = _export_layer(layer_name, fields, out_name, out_dir)
        size_kb = (out_dir / out_name).stat().st_size / 1024
        total_kb += size_kb
        results.append({"source_layer": layer_name, "file": out_name,
                         "features": layer.featureCount(), "size_kb": round(size_kb, 1)})

    print(f"[total] {total_kb:.0f} KB across {len(results)} files -> {out_dir}")

    boundary_woj = QgsVectorLayer(f"{GPKG}|layername=boundary_woj", "b", "ogr")
    boundary_lodz = QgsVectorLayer(f"{GPKG}|layername=boundary_lodz", "b", "ogr")

    def _bounds_4326(lyr):
        r = processing.run("native:reprojectlayer", {
            "INPUT": lyr, "TARGET_CRS": "EPSG:4326", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        })["OUTPUT"]
        ext = r.extent()
        return [[ext.yMinimum(), ext.xMinimum()], [ext.yMaximum(), ext.xMaximum()]]

    manifest = {
        "region": "wojewodztwo lodzkie",
        "date_woj": C.ANALYSIS_DATE,
        "date_lodz_vacation_days": ["2026-08-13", "2026-08-14", "2026-08-17", "2026-08-18"],
        "bounds_woj": _bounds_4326(boundary_woj),
        "bounds_lodz": _bounds_4326(boundary_lodz),
        "woj_categories": woj_cats,
        "lodz_categories": lodz_cats,
        "files": results,
        "total_size_kb": round(total_kb, 1),
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote {manifest_path}")
    return results


if __name__ == "__main__":
    export_all(STAGING)
