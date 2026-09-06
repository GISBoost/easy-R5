"""Compute per-hex accessibility delta (realized_p50 - static) and the
population-weighted city summary. Reads the two RunAccessibility OUTPUT_LAYER
gpkgs from run_accessibility.py, writes:
  - layer hex_delay in delay_lodz.gpkg: hex_id, pop_total, delta_<category>,
    base0_<category>
  - out/city_delay_summary.csv: population-weighted mean delta per category

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
    print("[done] compute_delay.py finished.")


if __name__ == "__main__":
    main()
