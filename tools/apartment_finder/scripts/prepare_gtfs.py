"""Prepare per-day GTFS folders: data/gtfs/<day>/{static,p50,p85}[_lka]/ (one network each).

The LKA release asset `lka_static_gtfs_<day>.zip` is the NATIONAL rail feed (all carriers, ~7600
active trips/day), while the realized P50/P85 zips hold only LKA's own trips (~330/day). Using the
national file as "LKA static" would not be comparable, so the static LKA feed is filtered to the
trip_ids present in that day's realized zip (all 1082 are found in the national file).
"static" (+ P50/P85) Lodz zips are downloaded by hand/gh into data/gtfs/<day>/<variant>/ already.
System Python (stdlib + pandas).
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
GH = r"C:\Program Files\GitHub CLI\gh.exe" if sys.platform == "win32" else "gh"  # CLAUDE.md: `gh` in PATH here is another tool
REPO = "GISBoost/easy-GTFS-RT"


def download(day):
    """Lodz (static/p50/p85) and LKA release assets for a day, if not present yet."""
    for v in ("static", "p50", "p85"):
        (HERE / "data/gtfs" / day / v).mkdir(parents=True, exist_ok=True)
    lodz = {"static": "lodz_static_gtfs_%s.zip" % day, "p50": "lodz_realized_%s_p50.zip" % day,
            "p85": "lodz_realized_%s_p85.zip" % day}
    for v, name in lodz.items():
        if not (HERE / "data/gtfs" / day / v / name).exists():
            subprocess.run([GH, "release", "download", "lodz-realized-%s-phone" % day, "--repo", REPO,
                            "-p", name, "-D", str(HERE / "data/gtfs" / day / v)], check=True)
    d = HERE / "data/lka" / day
    d.mkdir(parents=True, exist_ok=True)
    if not list(d.glob("lka_realized_*_p85.zip")):
        subprocess.run([GH, "release", "download", "lka-realized-%s-tripupdates" % day, "--repo", REPO,
                        "-p", "lka_*.zip", "-D", str(d)], check=True)


def filter_static_lka(day):
    d = HERE / "data/lka" / day
    out = d / ("lka_static_only_lka_%s.zip" % day)
    if out.exists():
        return out
    zr = zipfile.ZipFile(d / ("lka_realized_%s_p50.zip" % day))
    trips_keep = set(pd.read_csv(zr.open("trips.txt"), dtype=str, usecols=["trip_id"]).trip_id)
    zs = zipfile.ZipFile(d / ("lka_static_gtfs_%s.zip" % day))
    trips = pd.read_csv(zs.open("trips.txt"), dtype=str, low_memory=False)
    trips = trips[trips.trip_id.isin(trips_keep)]
    assert len(trips) == len(trips_keep), (len(trips), len(trips_keep))
    st = pd.read_csv(zs.open("stop_times.txt"), dtype=str, low_memory=False)
    st = st[st.trip_id.isin(trips_keep)]
    routes = pd.read_csv(zs.open("routes.txt"), dtype=str)
    routes = routes[routes.route_id.isin(trips.route_id)]
    stops = pd.read_csv(zs.open("stops.txt"), dtype=str)
    stops = stops[stops.stop_id.isin(st.stop_id)]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for name, df in (("trips.txt", trips), ("stop_times.txt", st), ("routes.txt", routes), ("stops.txt", stops)):
            zo.writestr(name, df.to_csv(index=False))
        for name in ("calendar.txt", "calendar_dates.txt", "agency.txt", "feed_info.txt"):
            if name in zs.namelist():
                df = pd.read_csv(zs.open(name), dtype=str, low_memory=False)
                if "service_id" in df:
                    df = df[df.service_id.isin(trips.service_id)]
                if name == "agency.txt":
                    df = df[df.agency_id.isin(routes.agency_id)]
                zo.writestr(name, df.to_csv(index=False))
    return out


def prepare(day):
    download(day)
    lka_static = filter_static_lka(day)
    d = HERE / "data/lka" / day
    lka = {"static": lka_static, "p50": d / ("lka_realized_%s_p50.zip" % day), "p85": d / ("lka_realized_%s_p85.zip" % day)}
    for v, src in lka.items():
        dst = HERE / "data/gtfs" / day / (v + "_lka")
        dst.mkdir(parents=True, exist_ok=True)
        base = next((HERE / "data/gtfs" / day / v).glob("lodz_*.zip"))
        for s in (base, src):
            # distinct file names = distinct R5 feed ids
            name = s.name if s != src else ("lka_" + v + "_" + day + ".zip")
            if not (dst / name).exists():
                shutil.copy2(s, dst / name)


if __name__ == "__main__":
    days = sys.argv[1:] or yaml.safe_load(open(HERE / "config/days.yaml", encoding="utf-8"))["days"]
    for day in days:
        prepare(day)
        print("prepared", day)
