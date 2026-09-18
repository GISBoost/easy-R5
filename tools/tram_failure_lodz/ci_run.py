"""Run the whole R5 half of the analysis without QGIS. Works on a CI runner.

This is the same work `run_cases.py` does inside QGIS, driven through the plugin's own
core modules instead of its Processing algorithms -- every module under easy_r5/core/
imports cleanly without PyQGIS, which is what makes a GitHub Actions run possible without
putting QGIS in a container:

    core.job_spec       builds the JSON the Java runner eats
    core.java_env       compiles EasyR5Runner.java and assembles the java command
    core.runner         runs the child process and parses its RESULT/ERROR protocol
    core.accessibility  turns a travel-time matrix into opportunity counts
    core.network_cache  keys a built network by its inputs + R5 version
    core.pins           the pinned R5 jar URL and its SHA-256

So this is still dogfooding: CI exercises the code the plugin ships, not a reimplementation.

Inputs come from inputs/ (written once by export_inputs.py inside QGIS and committed),
outputs land in out/<grid>/ in exactly the format compute_impact.py already reads, so the
local and CI halves are interchangeable.

    python ci_run.py --grid h250 --osm lodz.osm.pbf --gtfs lodz_static_gtfs_2026-08-21.zip
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from easy_r5.core import (            # noqa: E402
    accessibility,
    downloads,
    java_env,
    job_spec,
    network_cache,
    pins,
    runner,
    scenario as scenario_mod,
)

INPUTS = HERE / "inputs"
SCEN = HERE / "scenarios"
OUT_ROOT = HERE / "out"
WORK = HERE / "_ci_work"

ANALYSIS_DATE = "2026-08-21"
OPPORTUNITY_FIELDS = ["srv_school", "srv_pharmacy", "srv_university", "srv_mall"]
CUTOFFS = [30]
DEPARTURE_TIME = "07:00"
TIME_WINDOW = 120
PERCENTILES = [50]
MAX_TRIP_DURATION = 90
MAX_WALK_TIME = 30
WALK_SPEED = 3.6
MAX_RIDES = 3
MONTE_CARLO_DRAWS = 5
# Same list and same order as _matrix_base._TRANSIT_MODES, i.e. the plugin's "all modes"
# default. Kept explicit rather than imported: _matrix_base needs PyQGIS.
TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY",
                 "CABLE_CAR", "GONDOLA", "FUNICULAR"]

HEADLINE = ("baseline", "loo_5", "corridor", "bus", "all_trams",
            "cascade_top2", "cascade_top3", "cascade_top5")


class Feedback:
    """A console stand-in for QgsProcessingFeedback.

    The core modules each use a different slice of that class -- core.runner wants
    isCanceled/pushInfo/pushWarning/reportError/pushDebugInfo, core.downloads also wants
    setProgress -- so anything not implemented here falls through __getattr__ to a no-op
    instead of raising. A missing progress callback must not be able to fail a two-hour
    job: the first CI run died on exactly that, because the local smoke test had the jar
    cached and never exercised the download path.
    """

    def __init__(self, verbose=False):
        self.verbose = verbose
        self._last_pct = -1

    def isCanceled(self):        # noqa: N802
        return False

    def pushInfo(self, msg):     # noqa: N802
        print("   ", msg, flush=True)

    def pushWarning(self, msg):  # noqa: N802
        print("    WARN:", msg, flush=True)

    def reportError(self, msg, *a):  # noqa: N802
        print("    ERROR:", msg, flush=True)

    def pushDebugInfo(self, msg):    # noqa: N802
        if self.verbose:
            print("    .", msg, flush=True)

    def setProgress(self, pct):  # noqa: N802
        """Print at most one line per 10% so a 65 MB download is 10 lines, not 10 000."""
        step = int(pct) // 10
        if step != self._last_pct:
            self._last_pct = step
            print(f"    ... {int(pct)}%", flush=True)

    def setProgressText(self, text):  # noqa: N802
        print("   ", text, flush=True)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if self.verbose:
            print(f"    . feedback.{name}() ignored", flush=True)
        return lambda *a, **kw: None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_jar(feedback):
    """Download the pinned R5 jar and check it against the pinned SHA-256."""
    WORK.mkdir(exist_ok=True)
    jar = WORK / pins.R5_JAR_FILENAME
    if jar.is_file() and sha256(jar) == pins.R5_JAR_SHA256:
        print(f"[ok] R5 jar already present ({jar.name})")
        return jar
    print(f"[..] downloading {pins.R5_JAR_URL}")
    downloads.download_file(pins.R5_JAR_URL, jar, feedback=feedback,
                            user_agent="easy-R5 tools/tram_failure_lodz")
    got = sha256(jar)
    if got != pins.R5_JAR_SHA256:
        raise SystemExit(f"R5 jar checksum mismatch: {got} != {pins.R5_JAR_SHA256}")
    print(f"[ok] R5 jar verified ({jar.stat().st_size / 1e6:.0f} MB)")
    return jar


def resolve_java():
    """Full path to a java executable: JAVA_HOME first (that is what CI sets), then PATH."""
    home = os.environ.get("JAVA_HOME")
    if home:
        for name in ("java", "java.exe"):
            candidate = Path(home) / "bin" / name
            if candidate.is_file():
                return candidate
    found = shutil.which("java")
    if not found:
        raise SystemExit("No java on PATH and no usable JAVA_HOME. Need a Java 21 JDK.")
    return Path(found)


def ensure_env(feedback):
    java_bin = resolve_java()
    ok, version, error = java_env.check_java_version(java_bin)
    if not ok:
        raise SystemExit(f"Java check failed: {error}")
    print(f"[ok] java: {java_bin} ({version})")

    jar = ensure_jar(feedback)
    source = REPO / "easy_r5" / "java" / pins.RUNNER_SOURCE_FILENAME
    class_dir = WORK / "runner_classes"
    class_dir.mkdir(parents=True, exist_ok=True)
    mode, detail = java_env.compile_runner(java_bin.parent, jar, source, class_dir)
    print(f"[ok] runner: {mode} ({detail})")
    return java_env.resolve_env({
        "jdk_path": str(java_bin),
        "r5_jar_path": str(jar),
        "runner_mode": mode,
        "runner_class_dir": str(class_dir),
        "runner_source_path": str(source),
    })


def heap_flag(override_gb=None):
    """The -Xmx flag string build_java_command splices straight into the command."""
    mb = (int(float(override_gb) * 1024) if override_gb
          else java_env.heap_mb_for(java_env.detect_ram_bytes()))
    return f"-Xmx{mb}m"


def build_network(env, osm_path, gtfs_path, xmx, feedback):
    """Build (or reuse) the R5 network. Keyed by inputs + R5 version, like the plugin."""
    # Absolute: the runner's cwd is the per-job temp dir, so a relative input path
    # would resolve against the wrong directory and R5 reports only "file not found".
    osm_path, gtfs_path = Path(osm_path).resolve(), Path(gtfs_path).resolve()
    for p in (osm_path, gtfs_path):
        if not p.is_file():
            raise SystemExit(f"missing input: {p}")
    key = network_cache.cache_key(osm_path, [gtfs_path], pins.R5_VERSION)
    cache = network_cache.cache_dir(WORK / "network_cache", key)
    dat = network_cache.network_dat(cache)
    if network_cache.is_complete(cache):
        print(f"[ok] network already built: {dat}")
        return dat

    cache.mkdir(parents=True, exist_ok=True)
    tmp = WORK / "build"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    job = job_spec.build_build_job(str(osm_path), [str(gtfs_path)], str(dat),
                                   str(network_cache.network_json(cache)))
    job_path = job_spec.write_job(job, tmp)
    cmd = java_env.build_java_command(env, xmx, job_path)
    print("[..] building network (this is the slow one)")
    t = time.time()
    runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "build.log",
                   r5_version=pins.R5_VERSION)
    print(f"[ok] network built in {time.time() - t:.0f} s -> {dat}")
    return dat


def cases():
    """{case_id: scenario path or None}. baseline has no scenario file."""
    meta = json.loads((OUT_ROOT / "scenarios.json").read_text(encoding="utf-8"))
    out = {"baseline": None}
    for case_id in meta["cases"]:
        path = SCEN / f"{case_id}.json"
        if not path.exists():
            raise SystemExit(f"missing scenario file {path}")
        out[case_id] = path
    return out


def _origins(grid_id):
    path = INPUTS / f"{grid_id}_hex_origins.csv"
    if not path.is_file():
        raise SystemExit(f"missing {path} -- run export_inputs.py in QGIS and commit it")
    with open(path, newline="", encoding="utf-8") as fh:
        ids = [r["id"] for r in csv.DictReader(fh)]
    return path, ids


def run_case(env, dat, grid_id, case_id, scenario_path, metric, xmx, feedback,
             force=False):
    """One R5 run + its post-processing, resumable through a .params.json sidecar."""
    out = OUT_ROOT / grid_id
    out.mkdir(parents=True, exist_ok=True)
    origins_csv, origin_ids = _origins(grid_id)
    dests = INPUTS / ("centre.csv" if metric == "centre" else "poi_targets.csv")

    scenario = scenario_mod.load_scenario(scenario_path) if scenario_path else None
    job = job_spec.build_matrix_job(
        network=str(dat), origins_csv=str(origins_csv), destinations_csv=str(dests),
        origin_range=None, date=ANALYSIS_DATE, departure_time=DEPARTURE_TIME,
        time_window_minutes=TIME_WINDOW, percentiles=PERCENTILES,
        max_trip_duration_minutes=MAX_TRIP_DURATION,
        max_walk_time_minutes=MAX_WALK_TIME, walk_speed_kmh=WALK_SPEED,
        bike_speed_kmh=12.0, max_rides=1 if metric == "direct" else MAX_RIDES,
        monte_carlo_draws=MONTE_CARLO_DRAWS,
        access_modes=["WALK"], egress_modes=["WALK"], direct_modes=["WALK"],
        transit_modes=TRANSIT_MODES, write_unreachable=False,
        out_csv=str(out / f"matrix_{metric}_{case_id}.csv"), scenario=scenario)

    stamp = {"grid": grid_id, "case": case_id, "metric": metric,
             "date": ANALYSIS_DATE, "departure_time": DEPARTURE_TIME,
             "time_window": TIME_WINDOW, "percentiles": PERCENTILES,
             "cutoffs": CUTOFFS, "max_rides": job["max_rides"],
             "opportunity_fields": OPPORTUNITY_FIELDS,
             "origins_sha256": sha256(origins_csv),
             "destinations_sha256": sha256(dests),
             "scenario_sha256": sha256(scenario_path) if scenario_path else None,
             "r5_version": pins.R5_VERSION}
    side = out / f"{metric}_{case_id}.params.json"
    final = out / (f"centre_{case_id}.csv" if metric == "centre"
                   else f"{metric}_{case_id}.csv")
    if not force and side.is_file() and final.is_file():
        if json.loads(side.read_text(encoding="utf-8")) == stamp:
            print(f"[skip] {grid_id} {metric}/{case_id}")
            return False

    tmp = WORK / "jobs" / f"{grid_id}_{metric}_{case_id}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    job_path = job_spec.write_job(job, tmp)
    cmd = java_env.build_java_command(env, xmx, job_path)
    print(f"[run ] {grid_id} {metric}/{case_id}", flush=True)
    t = time.time()
    runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr.log",
                   r5_version=pins.R5_VERSION)

    matrix_csv = Path(job["out_csv"])
    if metric == "centre":
        shutil.move(str(matrix_csv), final)
    else:
        opportunities = accessibility.read_opportunities(dests, OPPORTUNITY_FIELDS)
        rows = list(accessibility.compute_accessibility(
            matrix_csv, opportunities, origin_ids, CUTOFFS, decay="STEP"))
        with open(final, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "opportunity", "percentile",
                                               "cutoff", "accessibility"])
            w.writeheader()
            w.writerows(rows)
        matrix_csv.unlink(missing_ok=True)
    final.with_suffix(".csv.meta.json").write_text(
        json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    side.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    print(f"[ok  ] {grid_id} {metric}/{case_id} in {time.time() - t:.0f} s")
    shutil.rmtree(tmp, ignore_errors=True)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grid", required=True, help="grid id, e.g. h250")
    ap.add_argument("--osm", required=True, help="clipped .osm.pbf for Lodz")
    ap.add_argument("--gtfs", required=True, help="static GTFS zip for the analysis date")
    ap.add_argument("--metrics", default="acc",
                    help="comma-separated: acc, centre, direct (default acc)")
    ap.add_argument("--only", default="", help="comma-separated case ids (default: all)")
    ap.add_argument("--heap-gb", default=None, help="Java heap; default from machine RAM")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    feedback = Feedback(args.verbose)
    env = ensure_env(feedback)
    xmx = heap_flag(args.heap_gb)
    print(f"[ok] java heap: {xmx}")
    dat = build_network(env, args.osm, args.gtfs, xmx, feedback)

    todo = cases()
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        todo = {k: v for k, v in todo.items() if k in wanted}
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]

    t0, done = time.time(), 0
    for metric in metrics:
        for case_id, scenario_path in todo.items():
            if metric in ("centre", "direct") and case_id not in HEADLINE:
                continue
            if run_case(env, dat, args.grid, case_id, scenario_path, metric, xmx,
                        feedback, args.force):
                done += 1
    print(f"[done] {args.grid}: {done} run(s) in {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
