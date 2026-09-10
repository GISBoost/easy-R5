"""Per-hex accessibility delta (realized_p50 - static) + population-weighted
city summary, per city/resolution. Generalized from realtime_delay_lodz.

Writes into delay_<city>[_500m].gpkg:
  - hex_delay: hex_id, pop_total, delta_<cat>, base0_<cat>, base_<cat>
  - hex_net_opportunities: hex_id, pop_total, net_delta, net_delta_n
and out/<city>_delay_summary[_500m].csv, out/<city>_net_summary[_500m].csv

delta_<cat> is NULL wherever the static count was 0 ("no baseline to lose or
gain", not "unaffected") -- base0_<cat> flags those. Summary stats over
non-NULL deltas only.

Run inside the QGIS Python env:  import compute_delay; compute_delay.main("gdansk", 250)
"""

from __future__ import annotations

import csv
from pathlib import Path

try:
    from qgis.core import QgsFeature, QgsField, QgsFields, QgsVectorFileWriter, QgsVectorLayer
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover
    raise SystemExit("compute_delay.py needs qgis.core.") from exc

from prepare_data import gpkg_path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CATEGORIES = ("school", "pharmacy", "university", "mall")
ACC_FIELD = "acc_srv_{}_p50_c30"


def _suffix(spacing_m):
    return "" if spacing_m == 250 else f"_{spacing_m}m"


def load_acc(city, case_id, spacing_m):
    path = OUT / f"acc_{city}_{case_id}{_suffix(spacing_m)}.gpkg"
    lyr = QgsVectorLayer(str(path), case_id, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load {path} -- did run_accessibility run?")
    return {f["hex_id"]: {c: f[ACC_FIELD.format(c)] for c in CATEGORIES} for f in lyr.getFeatures()}


def load_pop(gpkg):
    lyr = QgsVectorLayer(f"{gpkg}|layername=hex_grid", "hex_grid", "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load hex_grid from {gpkg}")
    return {f["hex_id"]: (f["pop_total"] or 0.0) for f in lyr.getFeatures()}, lyr


def _write_layer(mem, gpkg, name):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    err = QgsVectorFileWriter.writeAsVectorFormatV3(mem, str(gpkg), mem.transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write {name}: {err}")


def write_hex_delay(hex_grid_lyr, pop, static, realized, gpkg):
    hex_ids = sorted(pop)
    missing = [h for h in hex_ids if h not in static or h not in realized]
    if missing:
        raise RuntimeError(f"{len(missing)} hex_id(s) missing from an accessibility run, e.g. {missing[:5]}")

    fields = QgsFields()
    fields.append(QgsField("hex_id", QVariant.Int))
    fields.append(QgsField("pop_total", QVariant.Double))
    for cat in CATEGORIES:
        fields.append(QgsField(f"delta_{cat}", QVariant.Double))
        fields.append(QgsField(f"base0_{cat}", QVariant.Int))
        fields.append(QgsField(f"base_{cat}", QVariant.Double))

    crs = hex_grid_lyr.crs()
    mem = QgsVectorLayer(f"Polygon?crs={crs.authid() or crs.toWkt()}", "hex_delay", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    geoms = {f["hex_id"]: f.geometry() for f in hex_grid_lyr.getFeatures()}
    rows = []
    for hid in hex_ids:
        feat = QgsFeature(mem.fields())
        feat.setGeometry(geoms[hid])
        feat["hex_id"] = hid
        feat["pop_total"] = pop[hid]
        row = {"hex_id": hid, "pop_total": pop[hid]}
        for cat in CATEGORIES:
            s, r = static[hid][cat], realized[hid][cat]
            base0 = s is None or float(s) == 0.0
            delta = None if (base0 or r is None) else float(r) - float(s)
            feat[f"delta_{cat}"] = delta
            feat[f"base0_{cat}"] = 1 if base0 else 0
            feat[f"base_{cat}"] = None if s is None else float(s)
            row[f"delta_{cat}"] = delta
            row[f"base0_{cat}"] = base0
        mem.dataProvider().addFeature(feat)
        rows.append(row)
    _write_layer(mem, gpkg, "hex_delay")
    print(f"[ok] hex_delay ({len(hex_ids)} hexagons) -> {gpkg.name}")
    return rows


def write_hex_net(hex_grid_lyr, rows, gpkg):
    fields = QgsFields()
    fields.append(QgsField("hex_id", QVariant.Int))
    fields.append(QgsField("pop_total", QVariant.Double))
    fields.append(QgsField("net_delta", QVariant.Double))
    fields.append(QgsField("net_delta_n", QVariant.Int))

    crs = hex_grid_lyr.crs()
    mem = QgsVectorLayer(f"Polygon?crs={crs.authid() or crs.toWkt()}", "hex_net_opportunities", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    geoms = {f["hex_id"]: f.geometry() for f in hex_grid_lyr.getFeatures()}
    net_rows = []
    for row in rows:
        hid = row["hex_id"]
        deltas = [row[f"delta_{c}"] for c in CATEGORIES if row[f"delta_{c}"] is not None]
        net_delta = sum(deltas) if deltas else None
        feat = QgsFeature(mem.fields())
        feat.setGeometry(geoms[hid])
        feat["hex_id"] = hid
        feat["pop_total"] = row["pop_total"]
        feat["net_delta"] = net_delta
        feat["net_delta_n"] = len(deltas)
        mem.dataProvider().addFeature(feat)
        net_rows.append({"hex_id": hid, "pop_total": row["pop_total"],
                         "net_delta": net_delta, "net_delta_n": len(deltas)})
    _write_layer(mem, gpkg, "hex_net_opportunities")
    print(f"[ok] hex_net_opportunities ({len(net_rows)} hexagons) -> {gpkg.name}")
    return net_rows


def write_city_summary(city, rows, spacing_m):
    OUT.mkdir(exist_ok=True)
    out_csv = OUT / f"{city}_delay_summary{_suffix(spacing_m)}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "mean_delta_pop_weighted", "hexagons_with_value", "hexagons_zero_baseline"])
        for cat in CATEGORIES:
            ws = wt = 0.0
            n = base0_n = 0
            for row in rows:
                if row[f"base0_{cat}"]:
                    base0_n += 1
                    continue
                ws += row["pop_total"] * row[f"delta_{cat}"]
                wt += row["pop_total"]
                n += 1
            mean = (ws / wt) if wt else None
            w.writerow([cat, mean, n, base0_n])
            m = "n/a" if mean is None else f"{mean:+.3f}"
            print(f"[summary] {city} {spacing_m}m {cat}: {m}  ({n} comparable, {base0_n} zero-baseline)")
    print(f"[ok] {out_csv.name}")


def write_net_summary(city, net_rows, spacing_m):
    OUT.mkdir(exist_ok=True)
    ws = wt = 0.0
    n = zero_n = 0
    for row in net_rows:
        if row["net_delta"] is None:
            continue
        ws += row["pop_total"] * row["net_delta"]
        wt += row["pop_total"]
        n += 1
        zero_n += (row["net_delta"] == 0)
    mean = (ws / wt) if wt else None
    out_csv = OUT / f"{city}_net_summary{_suffix(spacing_m)}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["mean_net_delta_pop_weighted", "hexagons_with_value", "hexagons_net_zero"])
        w.writerow([mean, n, zero_n])
    m = "n/a" if mean is None else f"{mean:+.3f}"
    print(f"[summary] {city} {spacing_m}m net_delta: {m}  ({n} comparable, {zero_n} netted 0)")
    print(f"[ok] {out_csv.name}")


def main(city: str, hex_spacing_m: int = 250):
    gpkg = gpkg_path(city, hex_spacing_m)
    static = load_acc(city, "static", hex_spacing_m)
    realized = load_acc(city, "realized_p50", hex_spacing_m)
    pop, hex_grid_lyr = load_pop(gpkg)
    rows = write_hex_delay(hex_grid_lyr, pop, static, realized, gpkg)
    write_city_summary(city, rows, hex_spacing_m)
    net_rows = write_hex_net(hex_grid_lyr, rows, gpkg)
    write_net_summary(city, net_rows, hex_spacing_m)
    print(f"[done] compute_delay {city} {hex_spacing_m} m")
