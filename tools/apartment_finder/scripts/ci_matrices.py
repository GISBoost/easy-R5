"""M5 on a CI runner: all transit OD matrices of one (day, window), no QGIS.

Same work as run_matrices.py, driven through the plugin's own PyQGIS-free core modules (job_spec,
java_env, runner, network_cache, pins), the pattern proven by tools/tram_failure_lodz/ci_run.py
(copied, not imported -- CLAUDE.md). Per job: 6 networks (static|p50|p85 x without|with LKA) and the 12
scenarios (3 time types x 2 transfer limits x LKA off/on) of the window, packed to uint8 .npz exactly like
run_matrices.py (pack_matrix.py), written to data/matrices/<day>/.

    python scripts/ci_matrices.py --day 2026-10-02 --window morning --osm lodz.osm.pbf

Needs: Java 21 on PATH/JAVA_HOME, numpy + pandas + pyyaml, GH_TOKEN for `gh release download`.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE / "scripts"))

from easy_r5.core import downloads, gtfs_calendar, java_env, job_spec, network_cache, pins, runner  # noqa: E402
import pack_matrix  # noqa: E402
import prepare_gtfs  # noqa: E402

WORK = HERE / "_ci_work"
scn = yaml.safe_load(open(HERE / "config/scenarios.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE / "config/time_windows.yaml", encoding="utf-8"))["windows"]
TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"]  # = plugin default
ORIGINS = HERE / "inputs/lodz250_hex_origins.csv"   # id,lon,lat; id = hex_id, frozen by export_inputs.py


class Feedback:
    """Console stand-in for QgsProcessingFeedback; anything unimplemented is a no-op."""

    def isCanceled(self):        # noqa: N802
        return False

    def pushInfo(self, m):       # noqa: N802
        print("   ", m, flush=True)

    def pushWarning(self, m):    # noqa: N802
        print("    WARN:", m, flush=True)

    def reportError(self, m, *a):  # noqa: N802
        print("    ERROR:", m, flush=True)

    def setProgress(self, p):    # noqa: N802
        pass

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *a, **k: None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_env(fb, jar_path=None):
    home = os.environ.get("JAVA_HOME")
    java = next((Path(home) / "bin" / n for n in ("java", "java.exe") if home and (Path(home) / "bin" / n).is_file()), None)
    java = java or Path(shutil.which("java") or "")
    ok, version, err = java_env.check_java_version(java)
    if not ok:
        raise SystemExit("Java check failed: %s" % err)
    WORK.mkdir(exist_ok=True)
    jar = Path(jar_path) if jar_path else WORK / pins.R5_JAR_FILENAME
    if not (jar.is_file() and sha256(jar) == pins.R5_JAR_SHA256):
        downloads.download_file(pins.R5_JAR_URL, jar, feedback=fb, user_agent="easy-R5 tools/apartment_finder")
        if sha256(jar) != pins.R5_JAR_SHA256:
            raise SystemExit("R5 jar checksum mismatch")
    source = REPO / "easy_r5" / "java" / pins.RUNNER_SOURCE_FILENAME
    class_dir = WORK / "runner_classes"
    class_dir.mkdir(parents=True, exist_ok=True)
    mode, detail = java_env.compile_runner(java.parent, jar, source, class_dir)
    print("[ok] java %s, runner %s (%s)" % (version, mode, detail))
    return java_env.resolve_env({"jdk_path": str(java), "r5_jar_path": str(jar), "runner_mode": mode,
                                 "runner_class_dir": str(class_dir), "runner_source_path": str(source)})


def build_network(env, osm, variant_dir, xmx, fb):
    gtfs = sorted(Path(variant_dir).glob("*.zip"))
    key = network_cache.cache_key(Path(osm).resolve(), [g.resolve() for g in gtfs], pins.R5_VERSION)
    cache = network_cache.cache_dir(WORK / "network_cache", key)
    dat = network_cache.network_dat(cache)
    if not network_cache.is_complete(cache):
        cache.mkdir(parents=True, exist_ok=True)
        tmp = WORK / "build"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        job = job_spec.build_build_job(str(Path(osm).resolve()), [str(g.resolve()) for g in gtfs], str(dat),
                                       str(network_cache.network_json(cache)))
        t = time.time()
        runner.run_job(java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp)), fb, cwd=tmp,
                       stderr_log=tmp / "build.log", r5_version=pins.R5_VERSION)
        print("[ok] built %s in %.0f s" % (Path(variant_dir).name, time.time() - t), flush=True)
    return dat, json.load(open(network_cache.network_json(cache), encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--window", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--heap-gb", type=float, default=11)
    ap.add_argument("--jar", default=None)
    ap.add_argument("--only", default="", help="comma-separated scenario names (testing)")
    ap.add_argument("--out", default=str(HERE / "data/matrices"))
    a = ap.parse_args()
    fb = Feedback()
    env = ensure_env(fb, a.jar)
    xmx = "-Xmx%dm" % int(a.heap_gb * 1024)
    prepare_gtfs.prepare(a.day)
    nets = {}

    def net(variant):  # built lazily and cached, so --only runs build just what they need
        if variant not in nets:
            dat, meta = build_network(env, a.osm, HERE / "data/gtfs" / a.day / variant, xmx, fb)
            # silent walk-only guard (CLAUDE.md): the day must have active trips in the network
            # the plugin adds service_days to network.json in Python (BuildNetwork); recompute it here from the zips
            days_active = gtfs_calendar.compute_service_days(sorted((HERE / "data/gtfs" / a.day / variant).glob("*.zip")), cap_days=400)
            if not days_active.get(a.day):
                raise SystemExit("no active service on %s in network %s" % (a.day, variant))
            nets[variant] = (dat, meta)
        return nets[variant]

    if a.window not in tw:
        raise SystemExit("unknown window %r; config/time_windows.yaml has: %s" % (a.window, ", ".join(tw)))
    w = tw[a.window]
    h1, m1 = map(int, w["start"].split(":"))
    h2, m2 = map(int, w["end"].split(":"))
    out_dir = Path(a.out).resolve() / a.day
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = {x for x in a.only.split(",") if x}
    for t in scn["ttypes"]:
        for r, rides in scn["rides"].items():
            for lka in (False, True):
                name = "%s_%s_%s_%s" % (a.window, t, r, "lka" if lka else "nolka")
                if wanted and name not in wanted:
                    continue
                if (out_dir / (name + ".json")).exists():
                    print("[skip]", name)
                    continue
                dat, meta = net(t + ("_lka" if lka else ""))
                tmp = WORK / "jobs" / name
                shutil.rmtree(tmp, ignore_errors=True)
                tmp.mkdir(parents=True)
                csv_path = out_dir / (name + ".csv")
                job = job_spec.build_matrix_job(
                    network=str(dat), origins_csv=str(ORIGINS), destinations_csv=str(ORIGINS), origin_range=None,
                    date=a.day, departure_time=w["start"], time_window_minutes=(h2 * 60 + m2) - (h1 * 60 + m1),
                    percentiles=[int(p) for p in str(scn["r5"]["percentiles"]).split(",")],
                    max_trip_duration_minutes=scn["r5"]["max_trip_minutes"],
                    max_walk_time_minutes=scn["r5"]["max_walk_minutes"], walk_speed_kmh=3.6, bike_speed_kmh=12.0,
                    max_rides=rides, monte_carlo_draws=scn["r5"]["monte_carlo_draws"],
                    access_modes=["WALK"], egress_modes=["WALK"], direct_modes=["WALK"],
                    transit_modes=TRANSIT_MODES, write_unreachable=False, out_csv=str(csv_path))
                t0 = time.time()
                runner.run_job(java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp)), fb, cwd=tmp,
                               stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION)
                pack_matrix.main(str(csv_path), str(out_dir / (name + ".npz")))
                csv_path.unlink()
                json.dump({"scenario": name, "day": a.day, "window": a.window, "network_hash": meta.get("network_hash"),
                           "r5_seconds": round(time.time() - t0, 1), "scenarios_version": scn["scenarios_version"],
                           "r5_version": pins.R5_VERSION, "origins_sha256": sha256(ORIGINS), "runner": "ci_matrices.py"},
                          open(out_dir / (name + ".json"), "w", encoding="utf-8"), indent=1)
                shutil.rmtree(tmp, ignore_errors=True)
                print("[ok  ] %s in %.0f s" % (name, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
