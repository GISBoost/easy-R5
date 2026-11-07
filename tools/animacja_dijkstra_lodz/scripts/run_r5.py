"""Two R5 P50 windows, hex centres -> GTFS stops, packed as uint8 minutes.

255 = unreachable or over 60 min. The slider on the site only reads these bytes.

    py scripts/run_r5.py --day 2026-10-06 --limit 10
    py scripts/run_r5.py --day 2026-10-06

A small --limit writes work/sample_<window>.npz and does not touch the website.
The full run writes mapy-analizy/dijkstra-paths/data/.
"""
import argparse
import csv
import gzip
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
AF = HERE.parent / "apartment_finder"
REPO = HERE.parents[1]
sys.path.insert(0, str(AF / "scripts"))
sys.path.insert(0, str(REPO))

import ci_matrices as cm  # noqa: E402
import prepare_gtfs  # noqa: E402
from easy_r5.core import gtfs_calendar, java_env, job_spec, pins, runner  # noqa: E402

ORIGINS = AF / "inputs" / "lodz250_hex_origins.csv"
OSM = REPO / "tools" / "lodzkie_na_mapach_2026" / "work" / "pbf" / "lodz.osm.pbf"
WEB = Path(r"C:\Users\Michal\Desktop\easy\mapy-analizy\dijkstra-paths\data")
HEX_SRC = Path(r"C:\Users\Michal\Desktop\easy\mapy-analizy\lodz-dostepnosc-godzinowa\data\hex.geojson")
TRANSIT_MODES = cm.TRANSIT_MODES
WINDOWS = (
    ("morning", "07:00", 120, "7:00–9:00"),
    ("afternoon", "14:00", 240, "14:00–18:00"),
)
SHOWCASE_LONLAT = (19.4566, 51.7625)


class Feedback(cm.Feedback):
    def setProgress(self, p):  # noqa: N802
        step = int(p) // 5 * 5
        if step != getattr(self, "_step", -1):
            self._step = step
            print("    %d%%" % step, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_gtfs(day):
    gdir = HERE / "data"
    gdir.mkdir(parents=True, exist_ok=True)
    name = "lodz_realized_%s_p50.zip" % day
    dest = gdir / name
    if not dest.exists():
        subprocess.run(
            [prepare_gtfs.GH, "release", "download", prepare_gtfs.lodz_tag(day),
             "--repo", prepare_gtfs.REPO, "-p", name, "-D", str(gdir)],
            check=True,
        )
    return dest


def n_hex():
    n = sum(1 for _ in open(ORIGINS, encoding="utf-8")) - 1
    if n != 5662:
        raise SystemExit("expected 5662 origins, got %d" % n)
    return n


def showcase_hex():
    best, best_d = None, 1e18
    lon0, lat0 = SHOWCASE_LONLAT
    with open(ORIGINS, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d = (float(row["lon"]) - lon0) ** 2 + (float(row["lat"]) - lat0) ** 2
            if d < best_d:
                best_d, best = d, int(row["id"])
    return best


def pack(csv_path, n_rows, n_stops):
    arr = np.full((n_rows, n_stops), 255, np.uint8)
    reached = 0
    with open(csv_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            raw = row.get("travel_time_p50", "")
            if raw == "":
                continue
            minute = int(raw)
            if minute > 60:
                continue
            arr[int(row["from_id"]), int(row["to_id"])] = minute
            reached += 1
    return arr, reached


def run_window(env, xmx, fb, dat, day, origins, dests, name, departure, minutes, out_csv):
    tmp = HERE / "work" / "jobs" / name
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    job = job_spec.build_matrix_job(
        network=str(dat), origins_csv=str(origins), destinations_csv=str(dests),
        origin_range=None, date=day, departure_time=departure, time_window_minutes=minutes,
        percentiles=[50], max_trip_duration_minutes=60, max_walk_time_minutes=60,
        walk_speed_kmh=3.6, bike_speed_kmh=12.0, max_rides=8, monte_carlo_draws=5,
        access_modes=["WALK"], egress_modes=["WALK"], direct_modes=["WALK"],
        transit_modes=TRANSIT_MODES, write_unreachable=False, out_csv=str(out_csv),
    )
    t0 = time.time()
    fb._step = -1
    result = runner.run_job(
        java_env.build_java_command(env, xmx, job_spec.write_job(job, tmp)),
        fb, cwd=tmp, stderr_log=tmp / "stderr.log", r5_version=pins.R5_VERSION,
    )
    used = int(result.results.get("transit_used_pairs", "0"))
    print("[ok] %s in %.0f s, rows %s, transit_used_pairs %d" % (
        name, time.time() - t0, result.done_rowcount, used), flush=True)
    if used <= 0:
        raise SystemExit("walk-only result for %s — feed has no transit advantage" % name)
    return result


def write_gz(path, payload):
    with gzip.open(path, "wb", compresslevel=9) as fh:
        fh.write(payload)


def write_hex_bin(src, dest):
    """5662 rings as uint16 deltas. 1e-5 degree, about 1 m. Hit-tests only."""
    fc = json.loads(Path(src).read_text(encoding="utf-8"))
    rings = [None] * len(fc["features"])
    min_lon, min_lat = 180.0, 90.0
    for feat in fc["features"]:
        ring = feat["geometry"]["coordinates"][0]
        rings[feat["properties"]["hex_id"]] = ring
        for lon, lat in ring:
            min_lon = min(min_lon, lon)
            min_lat = min(min_lat, lat)
    lon0 = int(min_lon * 100000)
    lat0 = int(min_lat * 100000)
    out = bytearray(struct.pack("<Iii", len(rings), lon0, lat0))
    for ring in rings:
        if ring is None:
            raise SystemExit("hex id gap in %s" % src)
        out += struct.pack("<H", len(ring))
        for lon, lat in ring:
            dx = int(round(lon * 100000)) - lon0
            dy = int(round(lat * 100000)) - lat0
            out += struct.pack("<HH", dx, dy)
    Path(dest).write_bytes(out)


def write_web(day, gtfs, osm_sha, gtfs_sha, n_stops, morning, afternoon, showcase):
    WEB.mkdir(parents=True, exist_ok=True)
    write_gz(WEB / "morning.bin.gz", np.ascontiguousarray(morning, dtype=np.uint8).tobytes())
    write_gz(WEB / "afternoon.bin.gz", np.ascontiguousarray(afternoon, dtype=np.uint8).tobytes())
    shutil.copyfile(HERE / "work" / "segments.geojson", WEB / "segments.geojson")
    write_hex_bin(HEX_SRC, WEB / "hex.bin")
    for stale in ("morning.bin", "afternoon.bin", "hex.geojson"):
        old = WEB / stale
        if old.exists():
            old.unlink()
    manifest = {
        "day": day,
        "timezone": "Europe/Warsaw",
        "feed": gtfs.name,
        "release": prepare_gtfs.lodz_tag(day),
        "percentile": 50,
        "max_minutes": 60,
        "sentinel": 255,
        "n_hex": int(morning.shape[0]),
        "n_stops": n_stops,
        "showcase_hex": showcase,
        "osm_sha256": osm_sha,
        "gtfs_sha256": gtfs_sha,
        "r5": pins.R5_VERSION,
        "walk_kmh": 3.6,
        "max_rides": 8,
        "windows": {
            "morning": {"label": "7:00–9:00", "departure": "07:00", "window_minutes": 120, "file": "morning.bin.gz"},
            "afternoon": {"label": "14:00–18:00", "departure": "14:00", "window_minutes": 240, "file": "afternoon.bin.gz"},
        },
        "note": "Minuta odcinka to P50 czasu do przystanku na jego końcu. Suwak tylko porównuje próg z tą tablicą.",
    }
    with open(WEB / "manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("[ok] web data in %s" % WEB)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-10-06")
    ap.add_argument("--osm", default=str(OSM))
    ap.add_argument("--heap-gb", type=float, default=4)
    ap.add_argument("--limit", type=int, default=0, help="route only this many origins, spread across the grid")
    ap.add_argument("--windows", default="morning,afternoon")
    a = ap.parse_args()
    wanted = [w for w in WINDOWS if w[0] in {x.strip() for x in a.windows.split(",") if x.strip()}]
    if not wanted:
        raise SystemExit("no windows selected")

    fb = Feedback()
    env = cm.ensure_env(fb, None)
    xmx = "-Xmx%dm" % int(a.heap_gb * 1024)
    gtfs = ensure_gtfs(a.day)
    work = HERE / "work"
    if not (work / "destinations.csv").exists():
        subprocess.run([sys.executable, str(HERE / "scripts" / "build_segments.py"),
                        "--day", a.day, "--gtfs", str(gtfs), "--out", str(work)], check=True)
    n_stops = sum(1 for _ in open(work / "destinations.csv", encoding="utf-8")) - 1
    rows = n_hex()
    days = gtfs_calendar.compute_service_days([gtfs], cap_days=400)
    if not days.get(a.day):
        raise SystemExit("no active service on %s (%s)" % (a.day, days.get(a.day)))
    print("[ok] service trips on %s: %s; stops %d" % (a.day, days[a.day], n_stops), flush=True)

    origins = ORIGINS
    if a.limit:
        picked = [int(i * (rows / a.limit)) for i in range(a.limit)]
        centre = showcase_hex()
        if centre not in picked:
            picked[0] = centre
        keep = set(picked)
        sample = work / "origins_sample.csv"
        with open(ORIGINS, encoding="utf-8") as src, open(sample, "w", newline="", encoding="utf-8") as dst:
            r = csv.DictReader(src)
            w = csv.DictWriter(dst, fieldnames=r.fieldnames)
            w.writeheader()
            for row in r:
                if int(row["id"]) in keep:
                    w.writerow(row)
        origins = sample
        print("[ok] sample origins %s" % sorted(keep), flush=True)

    dat, _meta = cm.build_network(env, a.osm, gtfs.parent, xmx, fb)
    # build_network globs every zip in the directory. Keep only this day's feed there.
    packed = {}
    for name, departure, minutes, _label in wanted:
        csv_path = work / ("%s%s.csv" % (name, "_sample" if a.limit else ""))
        run_window(env, xmx, fb, dat, a.day, origins, work / "destinations.csv",
                   name + ("_sample" if a.limit else ""), departure, minutes, csv_path)
        arr, reached = pack(csv_path, rows, n_stops)
        np.savez_compressed(work / ("%s%s.npz" % (name, "_sample" if a.limit else "")), minutes=arr)
        csv_path.unlink(missing_ok=True)
        packed[name] = (arr, reached)
        print("[ok] %s reached cells %d / %d" % (name, reached, arr.size), flush=True)

    if a.limit:
        print("[ok] sample only, website not written")
        return
    if set(packed) != {"morning", "afternoon"}:
        raise SystemExit("full web export needs both windows")
    write_web(
        a.day, gtfs, sha256(Path(a.osm)), sha256(gtfs), n_stops,
        packed["morning"][0], packed["afternoon"][0], showcase_hex(),
    )


if __name__ == "__main__":
    main()
