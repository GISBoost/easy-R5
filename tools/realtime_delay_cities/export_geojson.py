"""Export every city's hex_delay + hex_net_opportunities (both resolutions),
boundary and siatka, to GeoJSON for the interactive web version at
mapy-analizy/opoznienia-dostepnosc -- extended here from single-city (Łódź)
to a 6-city switcher.

Also re-exports Łódź from ../realtime_delay_lodz/delay_lodz*.gpkg so the
manifest and data/ folder stay one coherent set.

Writes into <easy>/mapy-analizy/opoznienia-dostepnosc/data/:
  hex_<city>_<res>.geojson       choropleth (delta_<cat>, base_<cat>, net_delta, net_delta_n)
  siatka_<city>_<res>.geojson    hex_id + geometry only (full grid outline)
  boundary_<city>_<res>.geojson  stepped city outline -- the 250 m and 500 m grids
                                 dissolve to different staircases, so one per res
  manifest.json                  { cities: [ {key, label, date, bounds, resolutions[]} ] }

Run inside the QGIS Python env, e.g. mcp__qgis__execute_code.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import processing
    from qgis.core import QgsFeature, QgsFields, QgsProcessing, QgsVectorFileWriter, QgsVectorLayer
except ImportError as exc:  # pragma: no cover
    raise SystemExit("export_geojson.py needs qgis.core + processing.") from exc

import cities as C
from prepare_data import gpkg_path

HERE = Path(__file__).resolve().parent
EASY_ROOT = HERE.parent.parent.parent
MAPY_DATA = EASY_ROOT / "mapy-analizy" / "opoznienia-dostepnosc" / "data"
LODZ_DIR = HERE.parent / "realtime_delay_lodz"

CATEGORIES = ("school", "pharmacy", "university", "mall")
DELAY_FIELDS = ["hex_id", "pop_total"]
for _c in CATEGORIES:
    DELAY_FIELDS += [f"delta_{_c}", f"base_{_c}"]

# city -> {res: gpkg path}. Łódź uses the sibling analysis's file names.
def _gpkgs():
    out = {c: {r: gpkg_path(c, r) for r in C.CITIES[c][1]} for c in C.CITIES}
    out["lodz"] = {250: LODZ_DIR / "delay_lodz.gpkg", 500: LODZ_DIR / "delay_lodz_500m.gpkg"}
    return out


DISPLAY = {**{k: v[0] for k, v in C.CITIES.items()}, "lodz": "Łódź"}
DATE = {**{k: C.ANALYSIS_DATE for k in C.CITIES}, "lodz": "2026-08-21"}


def _reproject(layer):
    return processing.run("native:reprojectlayer", {
        "INPUT": layer, "TARGET_CRS": "EPSG:4326", "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })["OUTPUT"]


def _write(layer, out_path: Path):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GeoJSON"
    opts.layerOptions = ["COORDINATE_PRECISION=6"]
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(out_path), layer.transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write {out_path}: {err}")
    print(f"[ok] {out_path.name}: {layer.featureCount()} feat, {out_path.stat().st_size / 1024:.0f} KB")


def _merged(gpkg: Path):
    hd = QgsVectorLayer(f"{gpkg}|layername=hex_delay", "hd", "ogr")
    net = QgsVectorLayer(f"{gpkg}|layername=hex_net_opportunities", "net", "ogr")
    if not hd.isValid() or not net.isValid():
        raise RuntimeError(f"Missing hex_delay/hex_net_opportunities in {gpkg}")
    net_by = {f["hex_id"]: (f["net_delta"], f["net_delta_n"]) for f in net.getFeatures()}
    fields = QgsFields()
    for name in DELAY_FIELDS:
        fields.append(hd.fields().field(name))
    fields.append(net.fields().field("net_delta"))
    fields.append(net.fields().field("net_delta_n"))
    mem = QgsVectorLayer(f"Polygon?crs={hd.crs().authid() or hd.crs().toWkt()}", "m", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()
    feats = []
    for f in hd.getFeatures():
        nd, ndn = net_by[f["hex_id"]]
        nf = QgsFeature(mem.fields())
        nf.setGeometry(f.geometry())
        for name in DELAY_FIELDS:
            nf[name] = f[name]
        nf["net_delta"] = nd
        nf["net_delta_n"] = ndn
        feats.append(nf)
    mem.dataProvider().addFeatures(feats)
    return mem


def _layer(gpkg, name):
    lyr = QgsVectorLayer(f"{gpkg}|layername={name}", name, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Missing {name} in {gpkg}")
    return lyr


def export_city(key: str, res_gpkgs: dict):
    entry = {"key": key, "label": DISPLAY[key], "date": DATE[key], "resolutions": []}
    bounds = None
    for res, gpkg in sorted(res_gpkgs.items()):
        if not gpkg.exists():
            print(f"[skip] {key} {res}m -- {gpkg.name} missing")
            continue
        merged = _reproject(_merged(gpkg))
        _write(merged, MAPY_DATA / f"hex_{key}_{res}.geojson")
        _write(_reproject(_layer(gpkg, "siatka")), MAPY_DATA / f"siatka_{key}_{res}.geojson")
        entry["resolutions"].append({"key": str(res), "label": f"{res} m",
                                     "featureCount": merged.featureCount()})
        b = _reproject(_layer(gpkg, "boundary"))
        _write(b, MAPY_DATA / f"boundary_{key}_{res}.geojson")
        if res == min(res_gpkgs):
            e = b.extent()
            bounds = [[e.yMinimum(), e.xMinimum()], [e.yMaximum(), e.xMaximum()]]
    entry["bounds"] = bounds
    return entry if entry["resolutions"] else None


def main(only=None):
    MAPY_DATA.mkdir(parents=True, exist_ok=True)
    gpkgs = _gpkgs()
    order = ["lodz"] + [c for c in C.CITIES]
    cities_out = []
    for key in order:
        if only and key not in only:
            continue
        entry = export_city(key, gpkgs[key])
        if entry:
            cities_out.append(entry)
    manifest = {
        "categories": [
            {"key": "school", "label_pl": "Szkoły", "label_en": "Schools"},
            {"key": "pharmacy", "label_pl": "Apteki", "label_en": "Pharmacies"},
            {"key": "university", "label_pl": "Uczelnie", "label_en": "Universities"},
            {"key": "mall", "label_pl": "Centra handlowe", "label_en": "Malls"},
        ],
        "cities": cities_out,
    }
    (MAPY_DATA / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] manifest.json -- {len(cities_out)} cities")
    print("[done] export_geojson")
