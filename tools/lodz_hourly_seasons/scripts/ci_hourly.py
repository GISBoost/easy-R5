"""Hourly 30-min facility counts for ONE day: Lodz realized-P50 network built once, one R5 matrix run per clock hour.

    py scripts/ci_hourly.py --day 2026-09-10 --osm lodz.osm.pbf [--hours 7,8]

Reuses the apartment_finder CI helpers (same repo): network build/cache, R5 job runner, POI list, hex origins.
Output: data/<day>.npz, arr uint16 [hour, fine type, hex] = facilities of the type reachable within cutoff_min.
"""
import argparse
import csv
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
AF = HERE.parent / "apartment_finder"
sys.path.insert(0, str(AF / "scripts"))
import ci_matrices as cm  # noqa: E402  (Feedback, ensure_env, build_network; also puts the repo root on sys.path)
import prepare_gtfs  # noqa: E402  (lodz_tag)
from easy_r5.core import gtfs_calendar, java_env, job_spec, pins, runner  # noqa: E402

cfg = yaml.safe_load(open(HERE / "config.yaml", encoding="utf-8"))
scn = yaml.safe_load(open(AF / "config/scenarios.yaml", encoding="utf-8"))
svc = yaml.safe_load(open(AF / "config/services.yaml", encoding="utf-8"))
GH = prepare_gtfs.GH
TYPES = list(svc["types"])
POI_TYPE = pd.read_csv(AF / "inputs/service_pois.csv").crit.map({t: i for i, t in enumerate(TYPES)}).values   # row of the CSV -> type
N_HEX = sum(1 for _ in open(cm.ORIGINS, encoding="utf-8")) - 1


def count_within(times_csv, cutoff):
    """uint16 [type, hex]: facilities with travel_time_p50 <= cutoff (count_services.py clips at 255, which the centre can exceed)."""
    acc = np.zeros((len(TYPES), N_HEX), np.int32)
    for ch in pd.read_csv(times_csv, chunksize=4_000_000):
        m = ch.travel_time_p50.values <= cutoff
        np.add.at(acc, (POI_TYPE[ch.to_id.values[m].astype(int)], ch.from_id.values[m].astype(int)), 1)
    return acc.astype(np.uint16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--heap-gb", type=float, default=11)
    ap.add_argument("--jar", default=None)
    ap.add_argument("--hours", default="", help="comma-separated subset of hours (testing)")
    a = ap.parse_args()
    hours = [int(h) for h in a.hours.split(",") if h] or cfg["hours"]
    out = HERE / "data" / (a.day + ".npz")
    out.parent.mkdir(exist_ok=True)

    fb = cm.Feedback()
    env = cm.ensure_env(fb, a.jar)
    xmx = "-Xmx%dm" % int(a.heap_gb * 1024)

    gdir = HERE / "data/gtfs" / a.day
    gdir.mkdir(parents=True, exist_ok=True)
    name = "lodz_realized_%s_p50.zip" % a.day
    if not (gdir / name).exists():
        subprocess.run([GH, "release", "download", prepare_gtfs.lodz_tag(a.day), "--repo", prepare_gtfs.REPO,
                        "-p", name, "-D", str(gdir)], check=True)
    dat, meta = cm.build_network(env, a.osm, gdir, xmx, fb)
    if not gtfs_calendar.compute_service_days([gdir / name], cap_days=400).get(a.day):   # silent walk-only guard
        raise SystemExit("no active service on %s in %s" % (a.day, name))

    cm.WORK.mkdir(exist_ok=True)
    dest = cm.WORK / "hourly_destinations.csv"      # id = row of service_pois.csv (count_services.py maps it back)
    with open(AF / "inputs/service_pois.csv", encoding="utf-8") as src, open(dest, "w", newline="", encoding="utf-8") as o:
        w = csv.writer(o)
        w.writerow(["id", "lon", "lat"])
        for i, r in enumerate(csv.DictReader(src)):
            w.writerow([i, r["lon"], r["lat"]])

    res = {}
    if out.exists():                                # resume
        z = np.load(out)
        res = {int(h): z["arr"][i] for i, h in enumerate(z["hours"])}
    for h in hours:
        if h in res:
            continue
        t0 = time.time()
        tmp = cm.WORK / "jobs" / ("hourly_%s_%02d" % (a.day, h))
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        csv_path = tmp / "times.csv"
        job = job_spec.build_matrix_job(
            network=str(dat), origins_csv=str(cm.ORIGINS), destinations_csv=str(dest), origin_range=None,
            date=a.day, departure_time="%02d:00" % h, time_window_minutes=60, percentiles=[50],
            max_trip_duration_minutes=cfg["cutoff_min"], max_walk_time_minutes=cfg["cutoff_min"],   # cap at the cut-off is lossless
            walk_speed_kmh=3.6, bike_speed_kmh=12.0, max_rides=scn["rides"]["unlimited"],
            monte_carlo_draws=scn["r5"]["monte_carlo_draws"], access_modes=["WALK"], egress_modes=["WALK"],
            direct_modes=["WALK"], transit_modes=cm.TRANSIT_MODES, write_unreachable=False, out_csv=str(csv_path))
        runner.run_job(java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp)), fb, cwd=tmp,
                       stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION)
        res[h] = count_within(csv_path, cfg["cutoff_min"])
        shutil.rmtree(tmp, ignore_errors=True)
        hs = sorted(res)
        np.savez_compressed(out, arr=np.stack([res[k] for k in hs]), hours=np.array(hs), types=np.array(TYPES))
        print("[ok  ] %s %02d:00 in %.0f s, total facilities counted %d" % (a.day, h, time.time() - t0, int(res[h].sum())), flush=True)


if __name__ == "__main__":
    main()
