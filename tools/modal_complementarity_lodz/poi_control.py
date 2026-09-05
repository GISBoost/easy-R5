"""F3 -- control run: exact POI points vs hex-centroid opportunities (PRD SS4.3/SS9).

Runs ONE extra RunAccessibility pass: case TB, cutoff 30, percentile 50,
DESTINATIONS = poi_destinations (the 1,328 exact points) instead of
hex_destinations (opportunities pre-aggregated onto hex centroids). Compares
the resulting srv_total_30min per origin hexagon against the hex-based TB run
already computed by run_modal_cases.py, via Spearman's rho.

rho >= 0.95  -> the services metric is trustworthy as computed on hex_destinations.
rho <  0.95  -> flag it: the metric goes into the write-up with a caveat.

Must run inside the QGIS Python environment (needs processing for the extra
RunAccessibility call); the correlation itself is plain stdlib.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

try:
    import processing
except ImportError as exc:  # pragma: no cover -- guard for plain `py` runs
    raise SystemExit(
        "poi_control.py needs qgis.core + processing. Run it inside the QGIS "
        "Python console or via mcp__qgis__execute_code."
    ) from exc

from run_modal_cases import DATE, DEPARTURE_TIME, MAX_RIDES, MAX_TRIP_DURATION, MONTE_CARLO_DRAWS  # noqa: E402
from run_modal_cases import MODE_TRANSIT, TRAM, BUS, TIME_WINDOW, WALK_SPEED, DECAY_STEP, get_network  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
GPKG = HERE / "lodz_modal.gpkg"
RHO_THRESHOLD = 0.95


def run_poi_control():
    network_dat = get_network()
    params = {
        "NETWORK": network_dat,
        "ORIGINS": f"{GPKG}|layername=hex_centroids",
        "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": f"{GPKG}|layername=poi_destinations",
        "DEST_ID_FIELD": "poi_id",
        "DATE": DATE,
        "DEPARTURE_TIME": DEPARTURE_TIME,
        "TIME_WINDOW": TIME_WINDOW,
        "PERCENTILES": "50",
        "MAX_TRIP_DURATION": MAX_TRIP_DURATION,
        "WALK_SPEED": WALK_SPEED,
        "MAX_RIDES": MAX_RIDES,
        "MODE": MODE_TRANSIT,
        "TRANSIT_SUBMODES": [TRAM, BUS],
        "MONTE_CARLO_DRAWS": MONTE_CARLO_DRAWS,
        "ALLOW_NO_SERVICE": False,
        "OPPORTUNITY_FIELDS": ["srv_total"],
        "CUTOFFS": "30",
        "DECAY": DECAY_STEP,
        "OUTPUT_CSV": str(OUT / "acc_poi_control.csv"),
        "OUTPUT_LAYER": str(OUT / "acc_poi_control.gpkg"),
    }
    print("[run] poi_control: TB, DESTINATIONS=poi_destinations, cutoff=30, p50")
    processing.run("easyr5:runaccessibility", params)


def load_srv30(csv_path):
    """{hex_id: accessibility} for opportunity=srv_total, percentile=50, cutoff=30."""
    out = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["opportunity"] == "srv_total" and row["percentile"] == "50" and row["cutoff"] == "30":
                out[row["id"]] = float(row["accessibility"])
    return out


def spearman(xs, ys):
    """Spearman's rho, average ranks for ties. Pure stdlib (no scipy/numpy dependency)."""
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        r = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg_rank
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mean_rx, mean_ry = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x ** 0.5 * var_y ** 0.5)


def main():
    print("=== F3: POI control run ===")
    OUT.mkdir(exist_ok=True)
    run_poi_control()

    poi_srv30 = load_srv30(OUT / "acc_poi_control.csv")
    hex_srv30 = load_srv30(OUT / "acc_TB.csv")

    common = sorted(set(poi_srv30) & set(hex_srv30))
    if len(common) != len(hex_srv30):
        print(f"[warn] only {len(common)}/{len(hex_srv30)} hexagons present in both runs.")

    xs = [hex_srv30[h] for h in common]
    ys = [poi_srv30[h] for h in common]
    rho = spearman(xs, ys)
    print(f"[check] Spearman rho(srv_total_30min: hex-centroid vs exact-POI) = {rho:.4f} "
          f"(threshold >= {RHO_THRESHOLD}), n={len(common)}")

    result = {"rho": rho, "n": len(common), "threshold": RHO_THRESHOLD, "reliable": rho >= RHO_THRESHOLD}
    (OUT / "poi_control.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    if rho >= RHO_THRESHOLD:
        print("[gate OK] services metric is reliable at the hex-centroid resolution.")
    else:
        print(
            "[warn] rho below threshold -- the services metric (srv_total_*) must go "
            "into the write-up WITH a caveat about hex-centroid POI displacement."
        )


if __name__ == "__main__":
    main()
