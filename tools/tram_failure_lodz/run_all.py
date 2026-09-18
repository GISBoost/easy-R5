"""The whole pipeline, in order. Runs inside QGIS.

    import run_all; run_all.main()

Everything is resumable, so re-running is cheap: grids that exist are rebuilt (fast),
R5 runs whose parameters are unchanged are skipped (the expensive part), and the tables,
figures and maps are always redrawn.

Order matters in exactly two places:
  * cascades are built from the MEASURED leave-one-out ranking, so the h1000 pass has to
    finish before build_scenarios.build_cascades() can know which lines to combine;
  * maup.py compares grids, so every grid has to be through compute_impact first.
"""

from __future__ import annotations

import json
import time

import build_scenarios
import compute_impact
import make_map
import prepare_data
import run_cases

GRIDS = ("h1000", "h500", "h500off", "h250")   # cheapest first, so failures surface early
FULL_METRICS = ("acc", "centre", "direct")     # grids that get the whole battery
ACC_ONLY = ("h500", "h500off")                 # the MAUP controls need the ranking only
REPORT_GRID = "h250"                           # the grid the headline numbers come from


def main(grids=GRIDS):
    t0 = time.time()

    print("\n### 1. grids")
    prepare_data.build_all(grids)

    print("\n### 2. scenarios")
    build_scenarios.main()

    print("\n### 3. R5 -- reference grid first, to get the cascade order")
    run_cases.main(metrics=("acc",), grid_id="h1000")
    compute_impact.main("h1000")
    worst = json.loads(
        (compute_impact.out_dir("h1000") / "impact.json").read_text(encoding="utf-8")
    )["worst_lines"]
    print("[info] cascade order from measurement:", worst)
    build_scenarios.build_cascades(worst)

    print("\n### 4. R5 -- every grid, every case")
    for grid in grids:
        metrics = ("acc",) if grid in ACC_ONLY else FULL_METRICS
        run_cases.main(metrics=metrics, grid_id=grid)
        print("  [%s] %.0f min elapsed" % (grid, (time.time() - t0) / 60))

    print("\n### 5. impact tables, neighbourhoods, equity")
    for grid in grids:
        compute_impact.main(grid)

    print("\n### 6. maps")
    make_map.main_all([g for g in grids if g != "h500off"])

    print("\n### done in %.0f min. Now, outside QGIS:" % ((time.time() - t0) / 60))
    print("    py maup.py && py charts.py")
    return True


if __name__ == "__main__":
    main()
