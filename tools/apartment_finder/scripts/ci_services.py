"""Daily-service counts on a CI runner: the transit scenarios of one (day, window), no QGIS.

Same work as service_counts.py (R5 from the hex centres to the exact facility coordinates of inputs/service_pois.csv),
driven through the plugin's PyQGIS-free core like ci_matrices.py (whose helpers are reused). Per job: 6 networks
(static|p50|p85 x without|with ŁKA) and 6 scenarios (3 time types x ŁKA off/on), transfers unlimited, counted per fine
facility type and level by count_services.py -> data/services/<day>/transit_<window>_<ttype>_<nolka|lka>.npz.

    python scripts/ci_services.py --day 2026-10-02 --window morning --osm lodz.osm.pbf

Walk, bike and car do not depend on the day or GTFS and are computed locally (service_counts.py).
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import ci_matrices as cm  # noqa: E402  (Feedback, ensure_env, build_network, sha256; main() is not run on import)
from easy_r5.core import gtfs_calendar, java_env, job_spec, pins, runner  # noqa: E402
import prepare_gtfs  # noqa: E402

cfg = yaml.safe_load(open(HERE / "config/services.yaml", encoding="utf-8"))
scn = yaml.safe_load(open(HERE / "config/scenarios.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE / "config/time_windows.yaml", encoding="utf-8"))["windows"]
POI = HERE / "inputs/service_pois.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--window", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--heap-gb", type=float, default=11)
    ap.add_argument("--jar", default=None)
    ap.add_argument("--only", default="", help="comma-separated scenario names (testing)")
    a = ap.parse_args()
    if a.window not in tw:
        raise SystemExit("unknown window %r; config/time_windows.yaml has: %s" % (a.window, ", ".join(tw)))
    fb = cm.Feedback()
    env = cm.ensure_env(fb, a.jar)
    xmx = "-Xmx%dm" % int(a.heap_gb * 1024)
    prepare_gtfs.prepare(a.day)
    nets = {}

    def net(variant):
        if variant not in nets:
            vdir = HERE / "data/gtfs" / a.day / variant
            dat, meta = cm.build_network(env, a.osm, vdir, xmx, fb)
            if not gtfs_calendar.compute_service_days(sorted(vdir.glob("*.zip")), cap_days=400).get(a.day):   # silent walk-only guard
                raise SystemExit("no active service on %s in network %s" % (a.day, variant))
            nets[variant] = (dat, meta)
        return nets[variant]

    cm.WORK.mkdir(exist_ok=True)
    dest = cm.WORK / "service_destinations.csv"          # id = row of service_pois.csv (count_services.py maps it back)
    with open(POI, encoding="utf-8") as src, open(dest, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["id", "lon", "lat"])
        for i, r in enumerate(csv.DictReader(src)):
            w.writerow([i, r["lon"], r["lat"]])
    win = tw[a.window]
    h1, m1 = map(int, win["start"].split(":"))
    h2, m2 = map(int, win["end"].split(":"))
    m = cfg["modes"]["transit"]
    out_dir = HERE / "data/services" / a.day
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = {x for x in a.only.split(",") if x}
    for t in scn["ttypes"]:
        for lka in (False, True):
            name = "transit_%s_%s_%s" % (a.window, t, "lka" if lka else "nolka")
            if (wanted and name not in wanted) or (out_dir / (name + ".npz")).exists():
                continue
            dat, meta = net(t + ("_lka" if lka else ""))
            tmp = cm.WORK / "jobs" / name
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            csv_path = out_dir / (name + ".csv")
            job = job_spec.build_matrix_job(
                network=str(dat), origins_csv=str(cm.ORIGINS), destinations_csv=str(dest), origin_range=None,
                date=a.day, departure_time=win["start"], time_window_minutes=(h2 * 60 + m2) - (h1 * 60 + m1),
                percentiles=[50], max_trip_duration_minutes=m["max_min"], max_walk_time_minutes=scn["r5"]["max_walk_minutes"],
                walk_speed_kmh=3.6, bike_speed_kmh=12.0, max_rides=scn["rides"]["unlimited"],
                monte_carlo_draws=scn["r5"]["monte_carlo_draws"], access_modes=["WALK"], egress_modes=["WALK"],
                direct_modes=["WALK"], transit_modes=cm.TRANSIT_MODES, write_unreachable=False, out_csv=str(csv_path))
            t0 = time.time()
            runner.run_job(java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp)), fb, cwd=tmp,
                           stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION)
            subprocess.run([sys.executable, str(HERE / "scripts/count_services.py"), str(csv_path), str(out_dir / (name + ".npz")),
                            ",".join(map(str, m["levels"]))], check=True)
            csv_path.unlink()
            json.dump({"scenario": name, "day": a.day, "network_hash": meta.get("network_hash"), "r5_seconds": round(time.time() - t0, 1),
                       "services_version": cfg["services_version"], "r5_version": pins.R5_VERSION, "pois_sha256": cm.sha256(POI),
                       "runner": "ci_services.py"}, open(out_dir / (name + ".json"), "w", encoding="utf-8"), indent=1)
            shutil.rmtree(tmp, ignore_errors=True)
            print("[ok  ] %s in %.0f s" % (name, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
