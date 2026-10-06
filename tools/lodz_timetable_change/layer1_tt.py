"""S3 layer 1b: hex-to-hex R5 p50 travel-time matrices (transit) + one walk-only matrix.

    py layer1_tt.py --osm lodz.osm.pbf --gtfs-dir <dir> [--cases before_clean,after] [--bands am_peak]
        [--limit-origins N] [--heap-gb 8] [--jdk-home ...] [--jar ...]

Writes <data_dir>/layer1_tt/<case>/<band>.npz (int16 minutes, -1 = not reached, origin order = inputs/hex500_origins.csv)
and <data_dir>/layer1_tt/walk.npz. Reuses the runner plumbing of layer1_r5.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np

import layer1_r5 as base
from easy_r5.core import job_spec, java_env, runner, pins

HERE, CFG, L1 = base.HERE, base.CFG, base.L1
TT = CFG["tt"]
OUT = Path(os.environ.get("S3_DATA_DIR") or CFG["data_dir"]) / "layer1_tt"  # CI sets S3_DATA_DIR
DEST = HERE / TT["destinations"]


def run_matrix(env, dat, origins, ids, dest_ids, date, band, transit, xmx, fb, tag):
    r5 = L1["r5"]
    tmp = base.WORK / "jobs" / tag
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    walk_cap = TT["max_walk_time_min"] if transit else TT["walk_only_max_walk_min"]
    job = job_spec.build_matrix_job(
        network=str(dat), origins_csv=str(origins), destinations_csv=str(DEST), origin_range=None,
        date=date, departure_time=band["departure"], time_window_minutes=band["window_min"], percentiles=[50],
        max_trip_duration_minutes=TT["max_trip_duration_min"], max_walk_time_minutes=walk_cap,
        walk_speed_kmh=r5["walk_speed_kmh"], bike_speed_kmh=12.0, max_rides=r5["max_rides"],
        monte_carlo_draws=r5["monte_carlo_draws"], access_modes=["WALK"], egress_modes=["WALK"],
        direct_modes=["WALK"], transit_modes=base.TRANSIT_MODES if transit else [], write_unreachable=False,
        out_csv=str(tmp / "matrix.csv"))
    cmd = java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp))
    runner.run_job(cmd, fb, cwd=tmp, stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION)
    index = {i: k for k, i in enumerate(dest_ids)}
    oindex = {i: k for k, i in enumerate(ids)}
    m = np.full((len(ids), len(dest_ids)), -1, dtype=np.int16)
    with open(tmp / "matrix.csv", newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            if row[2]:
                m[oindex[row[0]], index[row[1]]] = int(row[2])
    shutil.rmtree(tmp, ignore_errors=True)
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grid", default="h500", choices=["h500", "h250"])
    ap.add_argument("--osm", required=True)
    ap.add_argument("--gtfs-dir", required=True)
    ap.add_argument("--cases", default="")
    ap.add_argument("--bands", default="")
    ap.add_argument("--heap-gb", default="8")
    ap.add_argument("--jdk-home", default=os.environ.get("JAVA_HOME"))
    ap.add_argument("--jar", default=None)
    ap.add_argument("--skip-walk", action="store_true", help="CI: the walk matrix is its own job")
    ap.add_argument("--walk-only", action="store_true")
    ap.add_argument("--limit-origins", type=int, default=0, help="smoke only; writes to layer1_tt_smoke")
    a = ap.parse_args()

    global OUT
    base.set_grid(a.grid)
    if a.grid != "h500":
        OUT = OUT.parent / f"layer1_tt_{a.grid}"
    fb = base.Feedback()
    env = base.ensure_env(fb, a.jdk_home, a.jar)
    xmx = f"-Xmx{int(float(a.heap_gb) * 1024)}m"
    cases = [c for c in a.cases.split(",") if c] or TT["cases"]
    bands = [b for b in a.bands.split(",") if b] or list(L1["bands"])
    origins = HERE / L1["origins"]
    ids = [r["id"] for r in csv.DictReader(open(origins, encoding="utf-8"))]
    dest_ids = [r["id"] for r in csv.DictReader(open(DEST, encoding="utf-8"))]
    if a.limit_origins:
        OUT = OUT.parent / "layer1_tt_smoke"
        keep = ids[:: max(1, len(ids) // a.limit_origins)][: a.limit_origins]
        origins = base.WORK / "tt_origins_limited.csv"
        with open(origins, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "lon", "lat"])
            w.writerows([r["id"], r["lon"], r["lat"]] for r in csv.DictReader(open(HERE / L1["origins"], encoding="utf-8"))
                        if r["id"] in set(keep))
        ids = keep
    OUT.mkdir(parents=True, exist_ok=True)
    timing = []
    first = L1["cases"][cases[0]]
    walk_path = OUT / "walk.npz"
    if not a.skip_walk and not walk_path.is_file():
        gtfs = Path(a.gtfs_dir) / f"lodz_static_gtfs_{first['static_day']}.zip"
        dat, _ = base.build_network(env, a.osm, gtfs, xmx, fb)
        t = time.time()
        np.savez_compressed(walk_path, m=run_matrix(env, dat, origins, ids, dest_ids, first["date"], L1["bands"]["am_peak"], False, xmx, fb, "walk"), ids=np.array(ids), dest_ids=np.array(dest_ids))
        timing.append({"step": "walk", "seconds": round(time.time() - t, 1)})
    if a.walk_only:
        cases = []
    for case in cases:
        c = L1["cases"][case]
        gtfs = Path(a.gtfs_dir) / f"lodz_static_gtfs_{c['static_day']}.zip"
        dat, _ = base.build_network(env, a.osm, gtfs, xmx, fb)
        (OUT / case).mkdir(exist_ok=True)
        for band_id in bands:
            path = OUT / case / f"{band_id}.npz"
            if path.is_file():
                print(f"[skip] {case}/{band_id}")
                continue
            t = time.time()
            m = run_matrix(env, dat, origins, ids, dest_ids, c["date"], L1["bands"][band_id], True, xmx, fb, f"{case}_{band_id}")
            np.savez_compressed(path, m=m, ids=np.array(ids), dest_ids=np.array(dest_ids))
            timing.append({"case": case, "band": band_id, "seconds": round(time.time() - t, 1), "reached": int((m >= 0).sum())})
            print(f"[ok  ] {case}/{band_id} in {timing[-1]['seconds']} s, reached pairs {timing[-1]['reached']}", flush=True)
    (OUT / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
