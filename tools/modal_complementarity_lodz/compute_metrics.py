"""F3 -- per-hex modal-dependency metrics (PRD SS4.4-4.5) + city aggregates.

Reads the four out/acc_<id>.csv files (run_modal_cases.py) and hex_destinations'
resident pop_total (F2). Writes:
  - lodz_modal.gpkg layer 'hex_modal' + out/hex_modal.csv
  - out/city_summary.csv -- Abar^m(T) and cov^m(T) for 5 cases x 4 cutoffs
  - out/run_meta.json is extended with the K threshold and filtered-hex count

Scope note: the full metric set (acc_*, *_gain, *_share, transfer_premium,
subadd) is computed for opportunity=pop_total at all 4 cutoffs, percentile=50
-- the headline combo (PRD SS4.2) -- not for every (opportunity x percentile)
combination, which would be ~1700 fields for no use identified in F4/F5.
srv_total at (p50, c30) is carried too, needed by poi_control.py's Spearman
check (PRD SS4/SS9 "control run").

Must run inside the QGIS Python environment (needs qgis.core to write the
GPKG layer); the metric arithmetic itself is plain stdlib.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

try:
    from qgis.core import (
        QgsFeature,
        QgsField,
        QgsFields,
        QgsProject,
        QgsVectorFileWriter,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError as exc:  # pragma: no cover -- guard for plain `py` runs
    raise SystemExit(
        "compute_metrics.py needs qgis.core to write the hex_modal layer. "
        "Run it inside the QGIS Python console or via mcp__qgis__execute_code."
    ) from exc

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
GPKG = HERE / "lodz_modal.gpkg"

CUTOFFS = (15, 30, 45, 60)
PCT = 50
K_THRESHOLD = 1000
GATE_OPP = "pop_total"
GATE_CUTOFF = 30
CASES = ("W", "T", "B", "TB")


def load_acc(case_id):
    """{(id, opportunity, percentile, cutoff): accessibility}"""
    out = {}
    with open(OUT / f"acc_{case_id}.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row["id"], row["opportunity"], int(row["percentile"]), int(row["cutoff"]))
            out[key] = float(row["accessibility"])
    return out


def load_hex_population():
    layer = QgsVectorLayer(f"{GPKG}|layername=hex_destinations", "hex_destinations", "ogr")
    if not layer.isValid():
        raise RuntimeError("Could not load hex_destinations from lodz_modal.gpkg")
    return {str(f["hex_id"]): float(f["pop_total"] or 0.0) for f in layer.getFeatures()}


def a(acc, case, hex_id, opp, cutoff, pct=PCT):
    return acc[case].get((hex_id, opp, pct, cutoff), 0.0)


def compute_hex_row(acc, hex_id, pop_i, gate_pass):
    row = {"hex_id": hex_id, "pop_total": pop_i}
    for cutoff in CUTOFFS:
        suffix = f"pop_p{PCT}_c{cutoff}"
        w = a(acc, "W", hex_id, "pop_total", cutoff)
        t = a(acc, "T", hex_id, "pop_total", cutoff)
        b = a(acc, "B", hex_id, "pop_total", cutoff)
        tb = a(acc, "TB", hex_id, "pop_total", cutoff)

        tram_gain = tb - b
        bus_gain = tb - t
        no_transfer = max(t, b)
        transfer_premium = tb - no_transfer
        a_tilde_t = max(0.0, t - w)
        a_tilde_b = max(0.0, b - w)
        a_tilde_tb = max(0.0, tb - w)
        denom = a_tilde_t + a_tilde_b

        row[f"acc_w_{suffix}"] = w
        row[f"acc_t_{suffix}"] = t
        row[f"acc_b_{suffix}"] = b
        row[f"acc_tb_{suffix}"] = tb
        row[f"tram_gain_{suffix}"] = tram_gain
        row[f"bus_gain_{suffix}"] = bus_gain
        row[f"no_transfer_{suffix}"] = no_transfer
        row[f"transfer_premium_{suffix}"] = transfer_premium

        # PRD SS4.5: shares are NULL (never 0) when A^TB=0 at this cutoff, OR
        # when the hex fails the K-reliability gate at the headline combo.
        share_ok = gate_pass and tb > 0
        row[f"walk_share_{suffix}"] = (w / tb) if share_ok else None
        row[f"tram_share_{suffix}"] = (tram_gain / tb) if share_ok else None
        row[f"bus_share_{suffix}"] = (bus_gain / tb) if share_ok else None
        row[f"mode_balance_{suffix}"] = ((t - b) / tb) if share_ok else None
        row[f"transfer_premium_rel_{suffix}"] = (transfer_premium / tb) if share_ok else None
        row[f"subadd_{suffix}"] = (a_tilde_tb / denom) if (share_ok and denom > 0) else None

    # Headline-combo services accessibility, for poi_control.py's Spearman check.
    row["acc_tb_srv_p50_c30"] = a(acc, "TB", hex_id, "srv_total", GATE_CUTOFF)
    return row


def write_gpkg_and_csv(rows):
    field_names = list(rows[0].keys())
    fields = QgsFields()
    fields.append(QgsField("hex_id", QVariant.Int))
    for name in field_names:
        if name == "hex_id":
            continue
        fields.append(QgsField(name, QVariant.Double))

    layer = QgsVectorLayer(f"{GPKG}|layername=hex_destinations", "hex_destinations", "ogr")
    geom_by_id = {str(f["hex_id"]): f.geometry() for f in layer.getFeatures()}

    mem = QgsVectorLayer(f"Point?crs={layer.crs().authid()}", "hex_modal", "memory")
    mem.dataProvider().addAttributes(fields)
    mem.updateFields()
    feats = []
    for row in rows:
        feat = QgsFeature(mem.fields())
        feat.setGeometry(geom_by_id[str(row["hex_id"])])
        feat.setAttributes([row.get(f.name()) for f in mem.fields()])
        feats.append(feat)
    mem.dataProvider().addFeatures(feats)
    mem.updateExtents()

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = "hex_modal"
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    err = QgsVectorFileWriter.writeAsVectorFormatV3(
        mem, str(GPKG), QgsProject.instance().transformContext(), options
    )
    if err[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed writing hex_modal layer: {err}")
    print(f"[ok] wrote layer 'hex_modal' ({mem.featureCount()} features, {len(field_names)} fields)")

    with open(OUT / "hex_modal.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=field_names)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    print(f"[ok] wrote out/hex_modal.csv ({len(rows)} rows, {len(field_names)} columns)")


def city_summary(acc, pop_by_hex, hex_ids):
    """Abar^m(T) and cov^m(T), person-weighted, opportunity=pop_total, p50."""
    total_pop = sum(pop_by_hex.get(h, 0.0) for h in hex_ids)
    rows = []
    for cutoff in CUTOFFS:
        values = {}
        for case in CASES:
            values[case] = {h: a(acc, case, h, "pop_total", cutoff) for h in hex_ids}
        values["no_transfer"] = {
            h: max(values["T"][h], values["B"][h]) for h in hex_ids
        }

        a_bar = {}
        cov = {}
        for case, per_hex in values.items():
            weighted_sum = sum(pop_by_hex.get(h, 0.0) * per_hex[h] for h in hex_ids)
            a_bar[case] = weighted_sum / total_pop if total_pop else 0.0
            covered_pop = sum(
                pop_by_hex.get(h, 0.0) for h in hex_ids if per_hex[h] >= K_THRESHOLD
            )
            cov[case] = covered_pop / total_pop if total_pop else 0.0

        a_tilde = {m: max(0.0, a_bar[m] - a_bar["W"]) for m in ("T", "B", "TB")}
        denom = a_tilde["T"] + a_tilde["B"]
        subadd_city = a_tilde["TB"] / denom if denom > 0 else None

        for case in ("W", "T", "B", "no_transfer", "TB"):
            rows.append({
                "cutoff": cutoff, "case": case, "opportunity": "pop_total", "percentile": PCT,
                "acc_weighted_mean": round(a_bar[case], 2),
                "coverage_pct_K{}".format(K_THRESHOLD): round(cov[case] * 100, 2),
                "subadd_city": round(subadd_city, 4) if subadd_city is not None else "",
            })
    return rows


def main():
    print("=== F3: compute_metrics ===")
    acc = {c: load_acc(c) for c in CASES}
    hex_ids = sorted({k[0] for k in acc["TB"]})
    pop_by_hex = load_hex_population()

    filtered = 0
    gate_pass_map = {}
    for hid in hex_ids:
        gate_value = a(acc, "TB", hid, GATE_OPP, GATE_CUTOFF)
        passed = gate_value >= K_THRESHOLD
        gate_pass_map[hid] = passed
        if not passed:
            filtered += 1
    print(f"[info] K={K_THRESHOLD}: {filtered}/{len(hex_ids)} hexagons fail the reliability "
          f"gate (A^TB(30,p50,pop_total) < {K_THRESHOLD}) -- shares NULL there.")

    rows = [compute_hex_row(acc, hid, pop_by_hex.get(hid, 0.0), gate_pass_map[hid]) for hid in hex_ids]
    write_gpkg_and_csv(rows)

    summary_rows = city_summary(acc, pop_by_hex, hex_ids)
    with open(OUT / "city_summary.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"[ok] wrote out/city_summary.csv ({len(summary_rows)} rows)")
    for r in summary_rows:
        if r["cutoff"] == 30:
            print("   ", r)

    meta_path = OUT / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta["reliability_threshold_K"] = K_THRESHOLD
    meta["reliability_gate_combo"] = {"opportunity": GATE_OPP, "percentile": PCT, "cutoff": GATE_CUTOFF}
    meta["hexagons_filtered_by_K"] = filtered
    meta["hexagons_total"] = len(hex_ids)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("=== F3 compute_metrics done ===")


if __name__ == "__main__":
    main()
