"""F3 -- run the four modal-case RunAccessibility passes (W / T / B / TB).

Everything downstream (check_invariants.py, compute_metrics.py) is built from
these four out/acc_<id>.csv files. Parameters are PRD SS4.2, exactly, on the
network + destinations layer F2 built. See docs/prd/PR_easy-R5_flagship-lodz-modal.md.

Must run inside the QGIS Python environment (qgis.core + processing + the
easy_r5 plugin registered) -- e.g. mcp__qgis__execute_code.

Resumable: a case is skipped if its out/acc_<id>.csv already exists with a
out/acc_<id>.params.json sidecar matching the parameters below -- so a typo
caught after case 3 does not force re-running cases 1-2.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

try:
    import processing
except ImportError as exc:  # pragma: no cover -- guard for plain `py` runs
    raise SystemExit(
        "run_modal_cases.py needs qgis.core + processing. Run it inside the "
        "QGIS Python console or via mcp__qgis__execute_code."
    ) from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "out"
GPKG = HERE / "lodz_modal.gpkg"

DATE = "2026-08-24"
DEPARTURE_TIME = "07:00"
TIME_WINDOW = 120
PERCENTILES = "10,25,50,75,90"
CUTOFFS = "15,30,45,60"
MAX_TRIP_DURATION = 60
WALK_SPEED = 3.6
MAX_RIDES = 3
MONTE_CARLO_DRAWS = 5
DECAY_STEP = 0
OPPORTUNITY_FIELDS = ["pop_total", "srv_total", "srv_education", "srv_health", "srv_culture", "srv_groceries"]

# MODE enum: 0=TRANSIT+WALK, 1=WALK (easy_r5/algorithms/_matrix_base.py MODE_OPTIONS).
MODE_TRANSIT = 0
MODE_WALK = 1
# TRANSIT_SUBMODES enum indexes _TRANSIT_MODES = [TRAM, SUBWAY, RAIL, BUS, ...].
TRAM = 0
BUS = 3

CASES = {
    "W": {"MODE": MODE_WALK, "TRANSIT_SUBMODES": []},
    "T": {"MODE": MODE_TRANSIT, "TRANSIT_SUBMODES": [TRAM]},
    "B": {"MODE": MODE_TRANSIT, "TRANSIT_SUBMODES": [BUS]},
    "TB": {"MODE": MODE_TRANSIT, "TRANSIT_SUBMODES": [TRAM, BUS]},
}

_RESUME_KEYS = [
    "NETWORK", "DATE", "DEPARTURE_TIME", "TIME_WINDOW", "PERCENTILES",
    "MAX_TRIP_DURATION", "WALK_SPEED", "MAX_RIDES", "MODE", "TRANSIT_SUBMODES",
    "MONTE_CARLO_DRAWS", "OPPORTUNITY_FIELDS", "CUTOFFS", "DECAY",
]


def plugin_version():
    text = (REPO / "easy_r5" / "metadata.txt").read_text(encoding="utf-8")
    m = re.search(r"^version=(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else "unknown"


def get_network():
    """Cache hit against F2's build -- instant, same inputs, same R5 version."""
    result = processing.run("easyr5:buildnetwork", {
        "OSM_PBF": str(REPO / "tools" / "accessibility_lodz" / "lodz.osm.pbf"),
        "GTFS_FOLDER": str(HERE / "gtfs_static"),
        "CACHE_FOLDER": str(HERE / "network_static"),
        "FORCE_REBUILD": False,
    })
    return result["NETWORK_DAT"]


def case_params(case_id, network_dat):
    c = CASES[case_id]
    return {
        "NETWORK": network_dat,
        "ORIGINS": f"{GPKG}|layername=hex_centroids",
        "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": f"{GPKG}|layername=hex_destinations",
        "DEST_ID_FIELD": "hex_id",
        "DATE": DATE,
        "DEPARTURE_TIME": DEPARTURE_TIME,
        "TIME_WINDOW": TIME_WINDOW,
        "PERCENTILES": PERCENTILES,
        "MAX_TRIP_DURATION": MAX_TRIP_DURATION,
        "WALK_SPEED": WALK_SPEED,
        "MAX_RIDES": MAX_RIDES,
        "MODE": c["MODE"],
        "TRANSIT_SUBMODES": c["TRANSIT_SUBMODES"],
        "MONTE_CARLO_DRAWS": MONTE_CARLO_DRAWS,
        "ALLOW_NO_SERVICE": False,
        "OPPORTUNITY_FIELDS": OPPORTUNITY_FIELDS,
        "CUTOFFS": CUTOFFS,
        "DECAY": DECAY_STEP,
        "OUTPUT_CSV": str(OUT / f"acc_{case_id}.csv"),
        "OUTPUT_LAYER": str(OUT / f"acc_{case_id}.gpkg"),
    }


def already_done(case_id, params):
    csv_path = Path(params["OUTPUT_CSV"])
    params_path = OUT / f"acc_{case_id}.params.json"
    if not (csv_path.exists() and params_path.exists()):
        return False
    saved = json.loads(params_path.read_text(encoding="utf-8"))
    return all(saved.get(k) == params.get(k) for k in _RESUME_KEYS)


def run_case(case_id, network_dat, timings):
    params = case_params(case_id, network_dat)
    if already_done(case_id, params):
        print(f"[skip] {case_id}: out/acc_{case_id}.csv already matches these parameters.")
        timings[case_id] = "cached"
        return
    print(f"[run] {case_id}: MODE={params['MODE']} TRANSIT_SUBMODES={params['TRANSIT_SUBMODES']}")
    t0 = time.monotonic()
    processing.run("easyr5:runaccessibility", params)
    elapsed = round(time.monotonic() - t0, 1)
    timings[case_id] = elapsed
    (OUT / f"acc_{case_id}.params.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"[ok] {case_id}: {elapsed:.1f} s")


def main():
    print("=== F3: four modal-case accessibility runs (Lodz) ===")
    OUT.mkdir(exist_ok=True)
    network_dat = get_network()
    timings = {}
    for case_id in ("W", "T", "B", "TB"):
        run_case(case_id, network_dat, timings)

    numeric_timings = [t for t in timings.values() if isinstance(t, (int, float))]
    meta = {
        "date": DATE, "departure_time": DEPARTURE_TIME, "time_window": TIME_WINDOW,
        "percentiles": PERCENTILES, "cutoffs": CUTOFFS,
        "max_rides": MAX_RIDES, "max_trip_duration": MAX_TRIP_DURATION,
        "plugin_version": plugin_version(),
        "cases": CASES,
        "timings_seconds": timings,
        "total_fresh_run_seconds": round(sum(numeric_timings), 1),
    }
    (OUT / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("=== F3 runs done ===")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
