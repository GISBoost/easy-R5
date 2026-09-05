"""Two RunAccessibility passes on delay_lodz.gpkg: static network vs realized
P50 network, same origins/destinations/date/window. Resumable via a
.params.json sidecar next to each CSV (skip a case whose recorded params match
what we'd run again -- same pattern as modal_complementarity_lodz's
run_modal_cases.py).

Must run inside the QGIS Python environment. Run prepare_data.py first.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import processing
    from qgis.core import QgsVectorLayer
except ImportError as exc:  # pragma: no cover
    raise SystemExit("run_accessibility.py needs qgis.core + processing.") from exc

HERE = Path(__file__).resolve().parent
GPKG = HERE / "delay_lodz.gpkg"
OUT = HERE / "out"

ANALYSIS_DATE = "2026-08-21"
OPPORTUNITY_FIELDS = ["srv_school", "srv_pharmacy", "srv_university", "srv_mall"]
CUTOFFS = "30"

CASES = {
    "static": HERE / "network_static",
    "realized_p50": HERE / "network_realized_p50",
}


def _network_dat(cache_dir: Path) -> str:
    hash_dirs = [d for d in cache_dir.iterdir() if d.is_dir()]
    if len(hash_dirs) != 1:
        raise RuntimeError(f"Expected exactly one network cache dir under {cache_dir}, found {hash_dirs}")
    dat = hash_dirs[0] / "network.dat"
    if not dat.exists():
        raise RuntimeError(f"Missing {dat} -- did prepare_data.py's build_networks() run?")
    return str(dat)


def case_params(case_id, network_dat, origins, destinations):
    return {
        "NETWORK": network_dat,
        "ORIGINS": origins,
        "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": destinations,
        "DEST_ID_FIELD": "poi_id",
        "DATE": ANALYSIS_DATE,
        "OPPORTUNITY_FIELDS": OPPORTUNITY_FIELDS,
        "CUTOFFS": CUTOFFS,
        # DEPARTURE_TIME=07:00, TIME_WINDOW=120, PERCENTILES=50, MODE=TRANSIT+WALK,
        # DECAY=STEP, MAX_WALK_TIME=blank -- all the algorithm's own defaults,
        # matching exactly what this analysis needs (07:00-09:00 window, step
        # count of reachable POI within the cutoff).
        "OUTPUT_CSV": str(OUT / f"accessibility_{case_id}.csv"),
        "OUTPUT_LAYER": str(OUT / f"accessibility_{case_id}.gpkg"),
    }


def already_done(case_id, params) -> bool:
    sidecar = OUT / f"accessibility_{case_id}.params.json"
    csv_path = Path(params["OUTPUT_CSV"])
    if not (sidecar.exists() and csv_path.exists()):
        return False
    return json.loads(sidecar.read_text(encoding="utf-8")) == params


def run_case(case_id, cache_dir):
    OUT.mkdir(exist_ok=True)
    network_dat = _network_dat(cache_dir)
    origins = f"{GPKG}|layername=hex_centroids"
    destinations = f"{GPKG}|layername=poi_targets"
    params = case_params(case_id, network_dat, origins, destinations)

    if already_done(case_id, params):
        print(f"[skip] {case_id}: already done with identical params.")
        return

    print(f"[run] {case_id}: {params}")
    processing.run("easyr5:runaccessibility", params)
    sidecar = OUT / f"accessibility_{case_id}.params.json"
    sidecar.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"[ok] {case_id} done -> {params['OUTPUT_CSV']}")


def main():
    if not GPKG.exists():
        raise RuntimeError(f"{GPKG} missing -- run prepare_data.py first.")
    for case_id, cache_dir in CASES.items():
        run_case(case_id, cache_dir)
    print("[done] run_accessibility.py finished.")


if __name__ == "__main__":
    main()
