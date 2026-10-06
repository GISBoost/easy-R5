"""R5 travel times hex 250 m -> service points (POIs), one model (realized P50 GTFS) per Monday, no QGIS.

Same pattern as tools/tram_failure_lodz/ci_run.py: R5 is driven through the plugin's own easy_r5/core modules, so
the script runs on a laptop and on a GitHub Actions runner.

    py poi_tt.py --osm lodz.osm.pbf --gtfs-dir <dir with lodz_realized_<day>_p50.zip>
        [--cases before,after] [--bands am_peak] [--heap-gb 8] [--limit-origins N]
        [--walk-only | --skip-walk] [--dest poi|hex] [--jdk-home ...] [--jar ...]

Writes <data_dir>/poi_tt/<case>/<band>.npz (int16 minutes, -1 = not reached, rows = inputs/hex250_origins.csv,
columns = inputs/poi_dest.csv) and <data_dir>/poi_tt/walk.npz (walk-only, same shape). CI sets S3_DATA_DIR.
With --dest hex the destinations are the origin hexes themselves (full 250 m matrix) and the output goes to hex_tt/.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from easy_r5.core import downloads, java_env, job_spec, network_cache, pins, runner  # noqa: E402

CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
P, R5, BANDS = CFG["poi"], CFG["r5"], CFG["bands"]
OUT = Path(os.environ.get("S3_DATA_DIR") or CFG["data_dir"]) / "poi_tt"
DEST_CSV = HERE / P["pois"]
WORK = HERE / "_ci_work"
TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class Feedback:
    """Console stand-in for QgsProcessingFeedback; unknown callbacks are no-ops (see ci_run.py)."""

    def isCanceled(self):  # noqa: N802
        return False

    def pushInfo(self, m):  # noqa: N802
        print("   ", m, flush=True)

    def pushWarning(self, m):  # noqa: N802
        print("    WARN:", m, flush=True)

    def reportError(self, m, *a):  # noqa: N802
        print("    ERROR:", m, flush=True)

    def setProgress(self, pct):  # noqa: N802
        pass

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a, **kw: None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def active_trips(gtfs_zip, day):
    """Trips running on `day` (calendar.txt + calendar_dates.txt). R5 silently returns walk-only for a day without trips."""
    def rows(z, name):
        if name not in z.namelist():
            return []
        return list(csv.DictReader(z.open(name).read().decode("utf-8-sig").splitlines()))

    ymd = day.strftime("%Y%m%d")
    with zipfile.ZipFile(gtfs_zip) as z:
        on = {r["service_id"] for r in rows(z, "calendar.txt")
              if r["start_date"] <= ymd <= r["end_date"] and r[WEEKDAYS[day.weekday()]] == "1"}
        for r in rows(z, "calendar_dates.txt"):
            if r["date"] == ymd:
                (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
        return sum(1 for r in rows(z, "trips.txt") if r["service_id"] in on)


def ensure_env(feedback, jdk_home, jar_path):
    java_bin = Path(jdk_home) / "bin" / ("java.exe" if os.name == "nt" else "java") if jdk_home else Path(shutil.which("java"))
    ok, version, error = java_env.check_java_version(java_bin)
    if not ok:
        raise SystemExit(f"Java check failed: {error}")
    print(f"[ok] java {version}")
    WORK.mkdir(exist_ok=True)
    jar = Path(jar_path) if jar_path else WORK / pins.R5_JAR_FILENAME
    if not (jar.is_file() and sha256(jar) == pins.R5_JAR_SHA256):
        downloads.download_file(pins.R5_JAR_URL, jar, feedback=feedback, user_agent="easy-R5 tools/lodz_timetable_change")
        if sha256(jar) != pins.R5_JAR_SHA256:
            raise SystemExit("R5 jar checksum mismatch")
    source = REPO / "easy_r5" / "java" / pins.RUNNER_SOURCE_FILENAME
    class_dir = WORK / "runner_classes"
    class_dir.mkdir(parents=True, exist_ok=True)
    mode, detail = java_env.compile_runner(java_bin.parent, jar, source, class_dir)
    print(f"[ok] runner: {mode} ({detail})")
    return java_env.resolve_env({"jdk_path": str(java_bin), "r5_jar_path": str(jar), "runner_mode": mode,
                                 "runner_class_dir": str(class_dir), "runner_source_path": str(source)})


def build_network(env, osm, gtfs, xmx, feedback):
    osm, gtfs = Path(osm).resolve(), Path(gtfs).resolve()
    cache = network_cache.cache_dir(WORK / "network_cache", network_cache.cache_key(osm, [gtfs], pins.R5_VERSION))
    dat = network_cache.network_dat(cache)
    if network_cache.is_complete(cache):
        return dat
    cache.mkdir(parents=True, exist_ok=True)
    tmp = WORK / "build"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    job = job_spec.build_build_job(str(osm), [str(gtfs)], str(dat), str(network_cache.network_json(cache)))
    cmd = java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp))
    runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "build.log", r5_version=pins.R5_VERSION)
    return dat


def run_matrix(env, dat, origins_csv, ids, dest_ids, date, band, transit, xmx, feedback, tag):
    tmp = WORK / "jobs" / tag
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    job = job_spec.build_matrix_job(
        network=str(dat), origins_csv=str(origins_csv), destinations_csv=str(DEST_CSV), origin_range=None,
        date=date, departure_time=band["departure"], time_window_minutes=band["window_min"],
        percentiles=R5["percentiles"], max_trip_duration_minutes=R5["max_trip_duration_min"],
        max_walk_time_minutes=R5["max_walk_time_min"] if transit else R5["walk_only_max_walk_min"],
        walk_speed_kmh=R5["walk_speed_kmh"], bike_speed_kmh=12.0, max_rides=R5["max_rides"],
        monte_carlo_draws=R5["monte_carlo_draws"], access_modes=["WALK"], egress_modes=["WALK"], direct_modes=["WALK"],
        transit_modes=TRANSIT_MODES if transit else [], write_unreachable=False, out_csv=str(tmp / "matrix.csv"))
    cmd = java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp))
    runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION)
    d_index = {i: k for k, i in enumerate(dest_ids)}
    o_index = {i: k for k, i in enumerate(ids)}
    m = np.full((len(ids), len(dest_ids)), -1, dtype=np.int16)
    with open(tmp / "matrix.csv", newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            if row[2]:
                m[o_index[row[0]], d_index[row[1]]] = int(row[2])
    shutil.rmtree(tmp, ignore_errors=True)
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--osm", required=True)
    ap.add_argument("--gtfs-dir", required=True)
    ap.add_argument("--cases", default="")
    ap.add_argument("--bands", default="")
    ap.add_argument("--heap-gb", default="8")
    ap.add_argument("--jdk-home", default=os.environ.get("JAVA_HOME"))
    ap.add_argument("--jar", default=None)
    ap.add_argument("--skip-walk", action="store_true", help="CI: the walk matrix is its own job")
    ap.add_argument("--walk-only", action="store_true")
    ap.add_argument("--dest", default="poi", choices=["poi", "hex"], help="hex = hex-to-hex matrix")
    ap.add_argument("--limit-origins", type=int, default=0, help="smoke only; writes to poi_tt_smoke")
    a = ap.parse_args()

    global OUT, DEST_CSV
    if a.dest == "hex":
        OUT, DEST_CSV = OUT.parent / "hex_tt", HERE / CFG["hexmatrix"]["dest"]
    fb = Feedback()
    env = ensure_env(fb, a.jdk_home, a.jar)
    xmx = f"-Xmx{int(float(a.heap_gb) * 1024)}m"
    cases = [c for c in a.cases.split(",") if c] or list(CFG["cases"])
    bands = [b for b in a.bands.split(",") if b] or list(BANDS)
    origins_csv = HERE / P["origins"]
    rows = list(csv.DictReader(open(origins_csv, encoding="utf-8")))
    ids = [r["id"] for r in rows]
    dest_ids = [r["id"] for r in csv.DictReader(open(DEST_CSV, encoding="utf-8"))]
    if a.limit_origins:
        OUT = OUT.parent / f"{OUT.name}_smoke"
        step = max(1, len(rows) // a.limit_origins)
        rows = rows[::step][: a.limit_origins]
        ids = [r["id"] for r in rows]
        origins_csv = WORK / "origins_limited.csv"
        with open(origins_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "lon", "lat"])
            w.writerows([r["id"], r["lon"], r["lat"]] for r in rows)
    OUT.mkdir(parents=True, exist_ok=True)

    def gtfs_of(case):
        day = CFG["cases"][case]["date"]
        path = Path(a.gtfs_dir) / CFG["source"]["assets"]["realized"].format(city=CFG["source"]["city"], date=day)
        n = active_trips(path, dt.date.fromisoformat(day))
        if n == 0:
            raise SystemExit(f"{case}: {path.name} has no active trips on {day} (R5 would silently return walk-only)")
        print(f"[ok] {case} {day}: {n} active trips in {path.name}")
        return path

    timing = []
    walk_path = OUT / "walk.npz"
    if not a.skip_walk and not walk_path.is_file():
        first = cases[0]
        dat = build_network(env, a.osm, gtfs_of(first), xmx, fb)
        t = time.time()
        m = run_matrix(env, dat, origins_csv, ids, dest_ids, CFG["cases"][first]["date"], BANDS["am_peak"], False, xmx, fb, "walk")
        np.savez_compressed(walk_path, m=m, ids=np.array(ids), dest_ids=np.array(dest_ids))
        timing.append({"step": "walk", "seconds": round(time.time() - t, 1)})
    for case in [] if a.walk_only else cases:
        dat = build_network(env, a.osm, gtfs_of(case), xmx, fb)
        (OUT / case).mkdir(exist_ok=True)
        for band_id in bands:
            path = OUT / case / f"{band_id}.npz"
            if path.is_file():
                print(f"[skip] {case}/{band_id}")
                continue
            t = time.time()
            m = run_matrix(env, dat, origins_csv, ids, dest_ids, CFG["cases"][case]["date"], BANDS[band_id], True, xmx, fb, f"{case}_{band_id}")
            np.savez_compressed(path, m=m, ids=np.array(ids), dest_ids=np.array(dest_ids))
            timing.append({"case": case, "band": band_id, "seconds": round(time.time() - t, 1), "reached": int((m >= 0).sum())})
            print(f"[ok  ] {case}/{band_id} in {timing[-1]['seconds']} s, reached pairs {timing[-1]['reached']}", flush=True)
    (OUT / f"timing_{'_'.join(cases)}.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
