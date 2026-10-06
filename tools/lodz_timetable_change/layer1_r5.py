"""S3 layer 1: R5 on the static GTFS of each case (before/after), no QGIS.

Same pattern as tools/tram_failure_lodz/ci_run.py: drives R5 through the plugin's own
easy_r5/core modules (job_spec, java_env, runner, network_cache, accessibility), so it runs
both locally and on a GitHub Actions runner.

    py layer1_r5.py --osm lodz.osm.pbf --gtfs-dir <dir with lodz_static_gtfs_<day>.zip>
        [--cases before_clean,after] [--bands am_peak] [--heap-gb 8] [--limit-origins N]

Per (case, band) two matrix jobs: percentile mode (p50 -> accessibility at 30/45/60 for population
and services) and service-minutes mode (-> accessibility averaged over the departure minutes of the band).
Output: out/layer1/<case>/<band>_acc.csv and <band>_svcacc.csv, plus a timing.json. Resumable via sidecars.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from easy_r5.core import (  # noqa: E402
    accessibility, downloads, java_env, job_spec, network_cache, pins, runner,
)

CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
L1, R5 = CFG["layer1"], CFG["layer1"]["r5"]
OUT = HERE / "out" / "layer1"
WORK = HERE / "_ci_work"
TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"]


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


def set_grid(name):
    """Point the module at one of the config grids; non-default grids write to out/layer1_<grid>."""
    global OUT
    L1.update(L1["grids"][name])
    OUT = HERE / "out" / ("layer1" if name == "h500" else f"layer1_{name}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_env(feedback, jdk_home, jar_path):
    if jdk_home:
        java_bin = Path(jdk_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
    else:
        java_bin = Path(shutil.which("java"))
    ok, version, error = java_env.check_java_version(java_bin)
    if not ok:
        raise SystemExit(f"Java check failed: {error}")
    print(f"[ok] java {version}")
    WORK.mkdir(exist_ok=True)
    jar = Path(jar_path) if jar_path else WORK / pins.R5_JAR_FILENAME
    if not (jar.is_file() and sha256(jar) == pins.R5_JAR_SHA256):
        downloads.download_file(pins.R5_JAR_URL, jar, feedback=feedback,
                                user_agent="easy-R5 tools/lodz_timetable_change")
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
    key = network_cache.cache_key(osm, [gtfs], pins.R5_VERSION)
    cache = network_cache.cache_dir(WORK / "network_cache", key)
    dat = network_cache.network_dat(cache)
    if network_cache.is_complete(cache):
        return dat, 0.0
    cache.mkdir(parents=True, exist_ok=True)
    tmp = WORK / "build"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    job = job_spec.build_build_job(str(osm), [str(gtfs)], str(dat), str(network_cache.network_json(cache)))
    cmd = java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp))
    t = time.time()
    runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "build.log", r5_version=pins.R5_VERSION)
    return dat, time.time() - t


def job_for(mode, dat, origins, band, date, out_csv):
    common = dict(
        network=str(dat), origins_csv=str(origins), destinations_csv=str(HERE / L1["destinations"]),
        origin_range=None, date=date, departure_time=band["departure"], time_window_minutes=band["window_min"],
        max_trip_duration_minutes=R5["max_trip_duration_min"], max_walk_time_minutes=R5["max_walk_time_min"],
        walk_speed_kmh=R5["walk_speed_kmh"], bike_speed_kmh=12.0, max_rides=R5["max_rides"],
        monte_carlo_draws=R5["monte_carlo_draws"], access_modes=["WALK"], egress_modes=["WALK"],
        direct_modes=["WALK"], transit_modes=TRANSIT_MODES, write_unreachable=False, out_csv=str(out_csv))
    if mode == "acc":
        return job_spec.build_matrix_job(percentiles=R5["percentiles"], **common)
    return job_spec.build_service_minutes_job(cutoffs=R5["cutoffs"], **common)


def reduce_svc(matrix_csv, opps, origin_ids, window_min):
    """Accessibility averaged over the band's departure minutes: sum_d opp_d * svc_min(o,d,c) / window."""
    acc = defaultdict(float)
    with open(matrix_csv, newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        cols = [(i, int(h.rsplit("_c", 1)[1])) for i, h in enumerate(header) if h.startswith("svc_min_c")]
        for row in rd:
            d = opps.get(row[1])
            if not d:
                continue
            for i, c in cols:
                if row[i]:
                    m = float(row[i]) / window_min
                    for name, v in d.items():
                        if v:
                            acc[(row[0], name, c)] += v * m
    names = sorted({n for d in opps.values() for n in d})
    for o in origin_ids:
        for name in names:
            for _, c in cols:
                yield {"id": o, "opportunity": name, "cutoff": c, "accessibility": round(acc[(o, name, c)], 4)}


def run(env, dat, case, band_id, date, origins, origin_ids, opps, xmx, feedback, timing):
    band = L1["bands"][band_id]
    out = OUT / case
    out.mkdir(parents=True, exist_ok=True)
    for mode, final in (("acc", out / f"{band_id}_acc.csv"), ("svc", out / f"{band_id}_svcacc.csv")):
        stamp = {"case": case, "band": band_id, "date": date, "mode": mode, "band_cfg": band, "r5": R5,
                 "n_origins": len(origin_ids), "origins_sha": sha256(origins),
                 "destinations_sha": sha256(HERE / L1["destinations"]), "r5_version": pins.R5_VERSION}
        side = final.with_suffix(".params.json")
        if final.is_file() and side.is_file() and json.loads(side.read_text(encoding="utf-8")) == stamp:
            print(f"[skip] {case}/{band_id}/{mode}")
            continue
        tmp = WORK / "jobs" / f"{case}_{band_id}_{mode}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        matrix_csv = tmp / "matrix.csv"
        job = job_for(mode, dat, origins, band, date, matrix_csv)
        cmd = java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp))
        print(f"[run ] {case}/{band_id}/{mode} date={date}", flush=True)
        t = time.time()
        runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION)
        if mode == "acc":
            rows = accessibility.compute_accessibility(matrix_csv, opps, origin_ids, R5["cutoffs"], decay="STEP")
            fields = ["id", "opportunity", "percentile", "cutoff", "accessibility"]
        else:
            rows = reduce_svc(matrix_csv, opps, origin_ids, band["window_min"])
            fields = ["id", "opportunity", "cutoff", "accessibility"]
        with open(final, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        side.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
        secs = time.time() - t
        timing.append({"case": case, "band": band_id, "mode": mode, "seconds": round(secs, 1),
                       "origins": len(origin_ids)})
        print(f"[ok  ] {case}/{band_id}/{mode} in {secs:.0f} s", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)


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
    ap.add_argument("--limit-origins", type=int, default=0,
                    help="timing/smoke runs only; writes to out/layer1_smoke")
    args = ap.parse_args()

    global OUT
    set_grid(args.grid)
    fb = Feedback()
    env = ensure_env(fb, args.jdk_home, args.jar)
    xmx = f"-Xmx{int(float(args.heap_gb) * 1024)}m"
    cases = [c for c in args.cases.split(",") if c] or list(L1["cases"])
    bands = [b for b in args.bands.split(",") if b] or list(L1["bands"])

    origins = HERE / L1["origins"]
    with open(origins, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.limit_origins:
        OUT = HERE / "out" / "layer1_smoke"
        origins = WORK / "origins_limited.csv"
        WORK.mkdir(exist_ok=True)
        rows = rows[:: max(1, len(rows) // args.limit_origins)][: args.limit_origins]
        with open(origins, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "lon", "lat"])
            w.writeheader()
            w.writerows({k: r[k] for k in ("id", "lon", "lat")} for r in rows)
    origin_ids = [r["id"] for r in rows]
    opps = accessibility.read_opportunities(HERE / L1["destinations"], L1["opportunity_fields"])

    timing = []
    for case in cases:
        c = L1["cases"][case]
        gtfs = Path(args.gtfs_dir) / f"lodz_static_gtfs_{c['static_day']}.zip"
        print(f"=== {case}: date {c['date']} on static {c['static_day']}", flush=True)
        dat, build_s = build_network(env, args.osm, gtfs, xmx, fb)
        timing.append({"case": case, "step": "network_build", "seconds": round(build_s, 1)})
        for band_id in bands:
            run(env, dat, case, band_id, c["date"], origins, origin_ids, opps, xmx, fb, timing)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    print(json.dumps(timing, indent=1))


if __name__ == "__main__":
    main()
