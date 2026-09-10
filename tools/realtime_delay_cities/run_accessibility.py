"""Two RunAccessibility passes per city/resolution: static vs realized-P50
network, same origins/destinations/date/window. Resumable via a .params.json
sidecar next to each CSV (same pattern as realtime_delay_lodz).

Run inside the QGIS Python env:

    import run_accessibility; run_accessibility.main("gdansk", 250)
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import processing
except ImportError as exc:  # pragma: no cover
    raise SystemExit("run_accessibility.py needs processing.") from exc

import cities as C
from prepare_data import gpkg_path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
OUT = HERE / "out"

OPPORTUNITY_FIELDS = ["srv_school", "srv_pharmacy", "srv_university", "srv_mall"]
CUTOFFS = "30"
CASES = {"static": "network_static", "realized_p50": "network_realized_p50"}


def _network_dat(city, sub):
    cache_dir = WORK / city / sub
    hash_dirs = [d for d in cache_dir.iterdir() if d.is_dir()]
    if len(hash_dirs) != 1:
        raise RuntimeError(f"Expected one cache dir under {cache_dir}, found {hash_dirs}")
    dat = hash_dirs[0] / "network.dat"
    if not dat.exists():
        raise RuntimeError(f"Missing {dat} -- run prepare_data.main({city!r}, ...) first.")
    return str(dat)


def _params(city, case_id, spacing_m):
    gpkg = gpkg_path(city, spacing_m)
    suffix = "" if spacing_m == 250 else f"_{spacing_m}m"
    return {
        "NETWORK": _network_dat(city, CASES[case_id]),
        "ORIGINS": f"{gpkg}|layername=hex_centroids",
        "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": f"{gpkg}|layername=poi_targets",
        "DEST_ID_FIELD": "poi_id",
        "DATE": C.ANALYSIS_DATE,
        "OPPORTUNITY_FIELDS": OPPORTUNITY_FIELDS,
        "CUTOFFS": CUTOFFS,
        # DEPARTURE_TIME=07:00, TIME_WINDOW=120, PERCENTILES=50, MODE=TRANSIT+WALK,
        # DECAY=STEP, MAX_WALK_TIME=blank -- all algorithm defaults, exactly what
        # this analysis needs (07:00-09:00 window, step count within the cutoff).
        "OUTPUT_CSV": str(OUT / f"acc_{city}_{case_id}{suffix}.csv"),
        "OUTPUT_LAYER": str(OUT / f"acc_{city}_{case_id}{suffix}.gpkg"),
    }


def _done(sidecar: Path, params) -> bool:
    csv_path = Path(params["OUTPUT_CSV"])
    if not (sidecar.exists() and csv_path.exists()):
        return False
    return json.loads(sidecar.read_text(encoding="utf-8")) == params


def run_case(city, case_id, spacing_m):
    OUT.mkdir(exist_ok=True)
    params = _params(city, case_id, spacing_m)
    suffix = "" if spacing_m == 250 else f"_{spacing_m}m"
    sidecar = OUT / f"acc_{city}_{case_id}{suffix}.params.json"
    if _done(sidecar, params):
        print(f"[skip] {city} {case_id} {spacing_m}m -- identical params.")
        return
    print(f"[run] {city} {case_id} {spacing_m}m")
    processing.run("easyr5:runaccessibility", params)
    sidecar.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"[ok] {city} {case_id} {spacing_m}m -> {params['OUTPUT_CSV']}")


def main(city: str, hex_spacing_m: int = 250):
    if not gpkg_path(city, hex_spacing_m).exists():
        raise RuntimeError(f"{gpkg_path(city, hex_spacing_m)} missing -- run prepare_data first.")
    for case_id in CASES:
        run_case(city, case_id, hex_spacing_m)
    print(f"[done] run_accessibility {city} {hex_spacing_m} m")
