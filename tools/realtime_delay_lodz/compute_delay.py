"""Compute per-hex accessibility delta (realized_p50 - static) and the
population-weighted city summary. Reads the two RunAccessibility OUTPUT_LAYER
gpkgs from run_accessibility.py, writes:
  - layer hex_delay in delay_lodz.gpkg: hex_id, pop_total, delta_<category>,
    base0_<category>, base_<category> (the actual static count -- how many
    points of that category are reachable in 30 min under the *regular*,
    unmodified GTFS schedule; base0_<category> is just "is base_<category>
    zero?" as a 0/1 flag)
  - out/city_delay_summary.csv: population-weighted mean delta per category
  - layer hex_net_opportunities: hex_id, pop_total, net_delta (sum of
    delta_<category> over whichever categories were comparable for that hex),
    net_delta_n (how many of the 4 categories went into that sum) -- the
    single-number hero-map layer: how many opportunities (of any kind) does
    this hexagon net gain or lose to delays
  - out/city_net_summary.csv: population-weighted mean net_delta

A hexagon where the *static* schedule already reaches 0 points of a category
within the cutoff has delta=0 too (0-0=0), but that is not "unaffected by
delays" -- it is "no baseline access to lose or gain", i.e. not comparable at
all. Counting it as a real zero would dilute the signal with places the
category was never reachable from in the first place. So delta_<category> is
set to NULL (not 0) wherever the static count was 0, and base0_<category>
(1/0) flags those hexagons explicitly so they show up in the layer and can be
styled/filtered separately in QGIS. City summary stats are computed only over
non-NULL deltas.

main(gpkg, out_suffix) is parametrized the same way as run_accessibility.py, so a
different hex resolution's results (e.g. delay_lodz_500m.gpkg /
out/accessibility_*_500m.gpkg) can be reduced without overwriting the default outputs.

Must run inside the QGIS Python environment. Run prepare_data.py and
run_accessibility.py first.
"""

from __future__ import annotations

import csv
from pathlib import Path

try:
    from qgis.core import QgsFeature, QgsField, QgsFields, QgsVectorFileWriter, QgsVectorLayer
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover
    raise SystemExit("compute_delay.py needs qgis.core.") from exc

HERE = Path(__file__).resolve().parent
GPKG = HERE / "delay_lodz.gpkg"
OUT = HERE / "out"

CATEGORIES = ("school", "pharmacy", "university", "mall")
ACC_FIELD = "acc_srv_{}_p50_c30"


def load_acc(case_id, out_suffix=""):
    path = OUT / f"accessibility_{case_id}{out_suffix}.gpkg"
    lyr = QgsVectorLayer(str(path), case_id, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load {path} -- did run_accessibility.py run?")
    out = {}
    for f in lyr.getFeatures():
        out[f["hex_id"]] = {cat: f[ACC_FIELD.format(cat)] for cat in CATEGORIES}
    return out


def load_pop(gpkg):
    lyr = QgsVectorLayer(f"{gpkg}|layername=hex_grid", "hex_grid", "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load hex_grid from {gpkg}")
    return {f["hex_id"]: (f["pop_total"] or 0.0) for f in lyr.getFeatures()}, lyr


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

    mem = QgsVectorLayer(f"Polygon?crs={hex_grid_lyr.crs().authid() or hex_grid_lyr.crs().toWkt()}",
                          "hex_delay", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    geoms = {f["hex_id"]: f.geometry() for f in hex_grid_lyr.getFeatures()}
    rows_for_csv = []
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
        rows_for_csv.append(row)

    if gpkg.exists():
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = "hex_delay"
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        err = QgsVectorFileWriter.writeAsVectorFormatV3(mem, str(gpkg), mem.transformContext(), opts)
        if err[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Failed to write hex_delay: {err}")
    print(f"[ok] wrote layer hex_delay ({len(hex_ids)} hexagons) to {gpkg}")
    return rows_for_csv


def write_hex_net_opportunities(hex_grid_lyr, rows, gpkg):
    """Hero-map layer: one number per hex -- how many opportunities (summed
    across all 4 categories) does this hexagon net gain or lose to delays.
    A category missing (base0) is skipped, not treated as 0 -- net_delta_n
    records how many of the 4 categories actually went into the sum, so a
    hexagon comparable on only 1 category isn't silently equated with one
    comparable on all 4. NULL net_delta means none of the 4 were comparable."""
    fields = QgsFields()
    fields.append(QgsField("hex_id", QVariant.Int))
    fields.append(QgsField("pop_total", QVariant.Double))
    fields.append(QgsField("net_delta", QVariant.Double))
    fields.append(QgsField("net_delta_n", QVariant.Int))

    mem = QgsVectorLayer(f"Polygon?crs={hex_grid_lyr.crs().authid() or hex_grid_lyr.crs().toWkt()}",
                          "hex_net_opportunities", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()

    geoms = {f["hex_id"]: f.geometry() for f in hex_grid_lyr.getFeatures()}
    net_rows = []
    for row in rows:
        hid = row["hex_id"]
        deltas = [row[f"delta_{cat}"] for cat in CATEGORIES if row[f"delta_{cat}"] is not None]
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

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "hex_net_opportunities"
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    err = QgsVectorFileWriter.writeAsVectorFormatV3(mem, str(gpkg), mem.transformContext(), opts)
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write hex_net_opportunities: {err}")
    print(f"[ok] wrote layer hex_net_opportunities ({len(net_rows)} hexagons) to {gpkg}")
    return net_rows


def write_net_summary(net_rows, out_suffix=""):
    OUT.mkdir(exist_ok=True)
    weighted_sum, weight_sum, n, zero_n = 0.0, 0.0, 0, 0
    for row in net_rows:
        if row["net_delta"] is None:
            continue
        weighted_sum += row["pop_total"] * row["net_delta"]
        weight_sum += row["pop_total"]
        n += 1
        if row["net_delta"] == 0:
            zero_n += 1
    mean = (weighted_sum / weight_sum) if weight_sum else None
    print(f"[summary] net_delta (sum over comparable categories): pop-weighted mean = "
          f"{mean:.3f} ({n}/{len(net_rows)} hexagons had >=1 comparable category, "
          f"{zero_n} netted exactly 0)")
    out_csv = OUT / f"city_net_summary{out_suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["mean_net_delta_pop_weighted", "hexagons_with_value", "hexagons_net_zero"])
        w.writerow([mean, n, zero_n])
    print(f"[ok] wrote {out_csv}")


def write_city_summary(rows, out_suffix=""):
    OUT.mkdir(exist_ok=True)
    summary = {}
    for cat in CATEGORIES:
        weighted_sum, weight_sum, n = 0.0, 0.0, 0
        base0_n = 0
        for row in rows:
            if row[f"base0_{cat}"]:
                base0_n += 1
                continue
            delta = row[f"delta_{cat}"]
            weighted_sum += row["pop_total"] * delta
            weight_sum += row["pop_total"]
            n += 1
        summary[cat] = {
            "mean_delta_pop_weighted": (weighted_sum / weight_sum) if weight_sum else None,
            "hexagons_with_value": n,
            "hexagons_zero_baseline": base0_n,
        }
        print(f"[summary] {cat}: pop-weighted mean delta = "
              f"{summary[cat]['mean_delta_pop_weighted']:.3f} "
              f"({n}/{len(rows)} hexagons comparable, {base0_n} excluded -- "
              "static already reached 0 points of this category)")

    out_csv = OUT / f"city_delay_summary{out_suffix}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["category", "mean_delta_pop_weighted", "hexagons_with_value", "hexagons_zero_baseline"])
        for cat, s in summary.items():
            w.writerow([cat, s["mean_delta_pop_weighted"], s["hexagons_with_value"], s["hexagons_zero_baseline"]])
    print(f"[ok] wrote {out_csv}")


def main(gpkg=GPKG, out_suffix=""):
    static = load_acc("static", out_suffix)
    realized = load_acc("realized_p50", out_suffix)
    pop, hex_grid_lyr = load_pop(gpkg)
    rows = write_hex_delay(hex_grid_lyr, pop, static, realized, gpkg)
    write_city_summary(rows, out_suffix)
    net_rows = write_hex_net_opportunities(hex_grid_lyr, rows, gpkg)
    write_net_summary(net_rows, out_suffix)
    print("[done] compute_delay.py finished.")


if __name__ == "__main__":
    main()
