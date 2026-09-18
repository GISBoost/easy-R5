"""Freeze the QGIS-built grids into CSVs that CI can read. Runs inside QGIS, once.

This is the seam between the two halves of the pipeline. Everything upstream of it needs
QGIS (census polygons, areal interpolation, the OSM osiedle boundaries); everything
downstream of it -- building the R5 network, running 40-odd scenarios, computing
accessibility, the impact tables, MAUP and the charts -- needs only Python and Java, which
is what lets the expensive part run on a GitHub Actions runner.

Writes inputs/:
  <grid>_hex_origins.csv   id,lon,lat          -- R5 origins, WGS84, the plugin's own
                                                  points-CSV format (core/points.py)
  <grid>_hex_ses.csv       hex_id,population,single_par,...,osiedle
  poi_targets.csv          id,lon,lat,srv_*    -- R5 destinations + the opportunity columns
  centre.csv               id,lon,lat          -- the one-point "city centre" destination

The naming follows tools/accessibility_cities/<city>/<city>_hex_{origins,ses}.csv, which
the repo's .gitignore already un-ignores on purpose: these files define a run, so they are
code, not data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsVectorLayer,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit("export_inputs.py must run inside QGIS.") from exc

HERE = Path(__file__).resolve().parent
GRIDS_DIR = HERE / "grids"
INPUTS = HERE / "inputs"

GRIDS = ("h250", "h500", "h1000", "h500off")
OPPORTUNITY_FIELDS = ("srv_school", "srv_pharmacy", "srv_university", "srv_mall")
SES_FIELDS = ("population", "single_par", "income_idx", "hh_single", "hh_size", "osiedle")


def _to_wgs84(layer):
    wgs = QgsCoordinateReferenceSystem("EPSG:4326")
    return QgsCoordinateTransform(layer.crs(), wgs, QgsProject.instance())


def _layer(gpkg, name):
    lyr = QgsVectorLayer(f"{gpkg}|layername={name}", name, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"cannot load {name} from {gpkg}")
    return lyr


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def export_origins(grid_id):
    """hex centroids -> id,lon,lat in WGS84, exactly as core/points.py would write them."""
    gpkg = GRIDS_DIR / f"{grid_id}.gpkg"
    lyr = _layer(gpkg, "hex_centroids")
    xform = _to_wgs84(lyr)
    path = INPUTS / f"{grid_id}_hex_origins.csv"
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "lon", "lat"])
        for f in sorted(lyr.getFeatures(), key=lambda f: int(f["hex_id"])):
            p = xform.transform(f.geometry().asPoint())
            w.writerow([int(f["hex_id"]), f"{p.x():.7f}", f"{p.y():.7f}"])
            n += 1
    print(f"[ok] {path.name}: {n} origins")
    return n


def export_ses(grid_id, osiedle_of):
    gpkg = GRIDS_DIR / f"{grid_id}.gpkg"
    lyr = _layer(gpkg, "hex_grid")
    path = INPUTS / f"{grid_id}_hex_ses.csv"
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["hex_id", *SES_FIELDS])
        for f in sorted(lyr.getFeatures(), key=lambda f: int(f["hex_id"])):
            hid = int(f["hex_id"])
            row = [hid]
            for field in SES_FIELDS:
                if field == "osiedle":
                    row.append(osiedle_of.get(str(hid)) or "")
                elif field == "population":
                    row.append(round(_num(f["pop_total"]) or 0.0, 3))
                else:
                    v = _num(f[field])
                    row.append("" if v is None else round(v, 4))
            w.writerow(row)
            n += 1
    print(f"[ok] {path.name}: {n} hexagons")
    return n


def export_destinations():
    """POI and the centre point -- identical for every grid, so written once."""
    gpkg = GRIDS_DIR / "h1000.gpkg"
    poi = _layer(gpkg, "poi_targets")
    xform = _to_wgs84(poi)
    with open(INPUTS / "poi_targets.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "lon", "lat", *OPPORTUNITY_FIELDS])
        n = 0
        for f in poi.getFeatures():
            p = xform.transform(f.geometry().asPoint())
            w.writerow([f["poi_id"], f"{p.x():.7f}", f"{p.y():.7f}",
                        *[int(_num(f[c]) or 0) for c in OPPORTUNITY_FIELDS]])
            n += 1
    print(f"[ok] poi_targets.csv: {n} destinations")

    centre = _layer(gpkg, "centre")
    xf2 = _to_wgs84(centre)
    with open(INPUTS / "centre.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "lon", "lat", "srv_centre"])
        for f in centre.getFeatures():
            p = xf2.transform(f.geometry().asPoint())
            w.writerow([f["poi_id"], f"{p.x():.7f}", f"{p.y():.7f}", 1])
    print("[ok] centre.csv: 1 destination")
    return n


def main(grids=GRIDS):
    import compute_impact                      # for the hexagon -> osiedle join
    INPUTS.mkdir(exist_ok=True)
    meta = {"grids": {}, "opportunity_fields": list(OPPORTUNITY_FIELDS)}
    for grid_id in grids:
        if not (GRIDS_DIR / f"{grid_id}.gpkg").exists():
            print(f"[skip] {grid_id}: no gpkg")
            continue
        osiedle_of = compute_impact.hex_to_osiedle(grid_id)
        meta["grids"][grid_id] = {"origins": export_origins(grid_id),
                                  "hexagons": export_ses(grid_id, osiedle_of)}
    meta["destinations"] = export_destinations()
    (INPUTS / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("[done]", json.dumps(meta))
    return meta


if __name__ == "__main__":
    main()
