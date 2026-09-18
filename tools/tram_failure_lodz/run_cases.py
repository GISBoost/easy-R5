"""Run R5 for every failure case. Runs inside QGIS.

One network, many scenarios: R5 applies each scenario file to the loaded network in
memory, so nothing is rebuilt between cases. The network is
../realtime_delay_lodz/network_static, reused as-is.

Three metrics, because "how bad was it" has three different answers:

  acc     -- opportunities (school / pharmacy / university / mall) reachable within
             30 min, 07:00-09:00, P50. Same fields, cutoff and window as
             ../realtime_delay_lodz, so the two analyses are directly comparable.
  centre  -- travel time to the population-weighted city centre. One destination, so
             this is a travel-time matrix, not an accessibility count.
  direct  -- the acc run again with MAX_RIDES=1: opportunities reachable *without
             changing vehicle*. Subtracting it from acc is how this analysis gets at
             "lost direct connections" -- R5's matrix does not report transfer counts,
             and MAX_RIDES is the parameter that does the same job without touching
             the Java runner.

Every run is resumable: a .params.json sidecar records exactly what produced each CSV
and a case whose params are unchanged is skipped. main(metrics=..., only=...) lets the
work be split across several MCP calls, since QGIS is unresponsive while R5 runs.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import processing
    from qgis.core import QgsProcessing
except ImportError as exc:  # pragma: no cover
    raise SystemExit("run_cases.py must run inside QGIS.") from exc

HERE = Path(__file__).resolve().parent
GRIDS_DIR = HERE / "grids"
SCEN = HERE / "scenarios"
OUT_ROOT = HERE / "out"
NETWORK_DIR = HERE.parent / "realtime_delay_lodz" / "network_static"

# Everything below is per grid: origins come from grids/<grid_id>.gpkg and results land in
# out/<grid_id>/. Scenario files are shared -- a scenario is a change to the timetable and
# knows nothing about how the city is cut into cells.
DEFAULT_GRID = "h1000"

ANALYSIS_DATE = "2026-08-21"
OPPORTUNITY_FIELDS = ["srv_school", "srv_pharmacy", "srv_university", "srv_mall"]
CUTOFFS = "30"
DEPARTURE_TIME = "07:00"
TIME_WINDOW = 120
PERCENTILES = "50"

# The full battery is expensive and only interesting where the story is told; the
# leave-one-out pass needs the accessibility metric alone to rank the lines.
HEADLINE = ("baseline", "loo_5", "corridor", "bus", "all_trams",
            "cascade_top2", "cascade_top3", "cascade_top5")


def network_dat():
    dirs = [d for d in NETWORK_DIR.iterdir() if d.is_dir()]
    if len(dirs) != 1:
        raise RuntimeError(f"expected one cache dir under {NETWORK_DIR}, found {dirs}")
    dat = dirs[0] / "network.dat"
    if not dat.exists():
        raise RuntimeError(f"missing {dat}")
    return str(dat)


def cases():
    scen = json.loads((OUT_ROOT / "scenarios.json").read_text(encoding="utf-8"))
    out = {"baseline": None}
    for case_id in scen["cases"]:
        path = SCEN / f"{case_id}.json"
        if not path.exists():
            raise RuntimeError(f"missing scenario file {path}")
        out[case_id] = str(path)
    return out


def grid_gpkg(grid_id):
    gpkg = GRIDS_DIR / f"{grid_id}.gpkg"
    if not gpkg.exists():
        raise RuntimeError(f"missing {gpkg} -- run prepare_data.main({grid_id!r}) first")
    return gpkg


def out_dir(grid_id):
    d = OUT_ROOT / grid_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _common(scenario_path, grid_id):
    params = {
        "NETWORK": network_dat(),
        "ORIGINS": f"{grid_gpkg(grid_id)}|layername=hex_centroids",
        "ORIGIN_ID_FIELD": "hex_id",
        "DATE": ANALYSIS_DATE,
        "DEPARTURE_TIME": DEPARTURE_TIME,
        "TIME_WINDOW": TIME_WINDOW,
        "PERCENTILES": PERCENTILES,
    }
    if scenario_path:
        params["SCENARIO"] = scenario_path
    return params


def params_for(metric, case_id, scenario_path, grid_id):
    p = _common(scenario_path, grid_id)
    gpkg, out = grid_gpkg(grid_id), out_dir(grid_id)
    # The CSV is the analysed artefact; the layer output is required but redundant
    # (same rows, joined back to the hexagons), so it goes to a temporary layer.
    if metric == "centre":
        p.update({
            "DESTINATIONS": f"{gpkg}|layername=centre",
            "DEST_ID_FIELD": "poi_id",
            "OUTPUT_CSV": str(out / f"centre_{case_id}.csv"),
            "OUTPUT_LAYER": QgsProcessing.TEMPORARY_OUTPUT,
        })
        return "easyr5:runtraveltimematrix", p
    p.update({
        "DESTINATIONS": f"{gpkg}|layername=poi_targets",
        "DEST_ID_FIELD": "poi_id",
        "OPPORTUNITY_FIELDS": OPPORTUNITY_FIELDS,
        "CUTOFFS": CUTOFFS,
        "OUTPUT_CSV": str(out / f"{metric}_{case_id}.csv"),
        "OUTPUT_LAYER": QgsProcessing.TEMPORARY_OUTPUT,
    })
    if metric == "direct":
        p["MAX_RIDES"] = 1        # board once: no transfer allowed
    return "easyr5:runaccessibility", p


def sidecar(metric, case_id, grid_id):
    return out_dir(grid_id) / f"{metric}_{case_id}.params.json"


def run_one(metric, case_id, scenario_path, grid_id, force=False):
    alg, params = params_for(metric, case_id, scenario_path, grid_id)
    side = sidecar(metric, case_id, grid_id)
    csv_path = Path(params["OUTPUT_CSV"])
    if not force and side.exists() and csv_path.exists():
        if json.loads(side.read_text(encoding="utf-8")) == params:
            print(f"[skip] {grid_id} {metric}/{case_id}")
            return False
    print(f"[run ] {grid_id} {metric}/{case_id}")
    processing.run(alg, params)
    side.write_text(json.dumps(params, indent=2), encoding="utf-8")
    print(f"[ok  ] {grid_id} {metric}/{case_id} -> {csv_path.name}")
    return True


def main(metrics=("acc",), only=None, force=False, budget=None, grid_id=DEFAULT_GRID):
    """Run metrics x cases for one grid. `budget` stops after N runs, to fit a time box."""
    todo = cases()
    if only:
        todo = {k: v for k, v in todo.items() if k in only}
    done = 0
    for metric in metrics:
        for case_id, scenario_path in todo.items():
            if metric in ("centre", "direct") and case_id not in HEADLINE:
                continue
            if run_one(metric, case_id, scenario_path, grid_id, force):
                done += 1
            if budget and done >= budget:
                print(f"[stop] budget of {budget} runs reached")
                return done
    print(f"[done] {done} run(s) executed")
    return done


if __name__ == "__main__":
    main()
