"""Static vs realized-P50 GTFS: how many trips run late / early / unchanged on
the analysis day, split by traction (tram / bus / ...), whole-day and AM-peak.

Pure stdlib, `py analyze_gtfs_shifts.py [city ...]`. Reads the same feed pairs
the pipeline uses (isochrones_lodz/<city>_network_{static,rt}/), Łódź from
accessibility_lodz/. A trip is classified by the mean of (realized - static)
arrival time over its shared stops: > +30 s = late, < -30 s = early, else
unchanged. Writes out/gtfs_shift_by_traction.csv.
"""

from __future__ import annotations

import csv
import glob
import io
import statistics
import sys
import zipfile
from datetime import date

import cities as C

# GTFS basic + extended (HVT) route_type -> traction
def traction(rt: str) -> str:
    if rt in ("0", "5") or rt.startswith("90"):
        return "tram"
    if rt == "1" or rt.startswith("40"):
        return "metro"
    if rt == "2" or rt.startswith("1"):
        return "kolej"
    if rt == "3" or rt.startswith("7") or rt.startswith("70"):
        return "autobus"
    if rt == "11" or rt.startswith("80"):
        return "trolejbus"
    if rt in ("4",) or rt.startswith("100"):
        return "prom"
    return "inne"

THRESH = 30  # seconds of mean shift to call a trip late / early
TRACTIONS = ("tram", "autobus", "trolejbus", "metro", "kolej", "prom", "inne")


def _rows(zf, name):
    with zf.open(name) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, "utf-8-sig"))


def _active_services(zf, ds, weekday):
    names = zf.namelist()
    a = set()
    if "calendar.txt" in names:
        for r in _rows(zf, "calendar.txt"):
            if r["start_date"] <= ds <= r["end_date"] and r.get(weekday) == "1":
                a.add(r["service_id"])
    if "calendar_dates.txt" in names:
        for r in _rows(zf, "calendar_dates.txt"):
            if r["date"] == ds:
                (a.add if r["exception_type"] == "1" else a.discard)(r["service_id"])
    return a


def _load(zpath, ds, weekday):
    zf = zipfile.ZipFile(zpath)
    active = _active_services(zf, ds, weekday)
    rtype = {r["route_id"]: r.get("route_type", "") for r in _rows(zf, "routes.txt")}
    trip_tr, trip_svc = {}, {}
    for r in _rows(zf, "trips.txt"):
        trip_tr[r["trip_id"]] = traction(rtype.get(r["route_id"], ""))
        trip_svc[r["trip_id"]] = r["service_id"]
    st = {}
    for r in _rows(zf, "stop_times.txt"):
        tid = r["trip_id"]
        if trip_svc.get(tid) not in active:
            continue
        t = (r.get("arrival_time") or "").strip().split(":")
        if len(t) != 3:
            continue
        try:
            sec = int(t[0]) * 3600 + int(t[1]) * 60 + int(t[2])
        except ValueError:
            continue
        st.setdefault(tid, {})[int(r["stop_sequence"])] = sec
    return trip_tr, st


def analyse(city, ds, weekday):
    if city == "lodz":
        zs = "../accessibility_lodz/lodz_static_gtfs_2026-08-21.zip"
        zr = "../accessibility_lodz/lodz_realized_2026-08-21_p50.zip"
        ds, weekday = "20260821", "friday"
    else:
        zs = glob.glob(f"../isochrones_lodz/{city}_network_static/*.zip")[0]
        zr = glob.glob(f"../isochrones_lodz/{city}_network_rt/*.zip")[0]
    tr, s = _load(zs, ds, weekday)
    _, r = _load(zr, ds, weekday)

    out = []
    for window in ("caly dzien", "szczyt 7-9"):
        buckets = {}  # traction -> [late, early, same, shifts...]
        for tid in set(s) & set(r):
            common = sorted(set(s[tid]) & set(r[tid]))
            if len(common) < 2:
                continue
            first_dep = s[tid][common[0]]
            if window == "szczyt 7-9" and not (25200 <= first_dep <= 32400):
                continue
            shifts = [r[tid][q] - s[tid][q] for q in common]
            mean = statistics.mean(shifts)
            b = buckets.setdefault(tr.get(tid, "inne"), [0, 0, 0, []])
            if mean > THRESH:
                b[0] += 1
            elif mean < -THRESH:
                b[1] += 1
            else:
                b[2] += 1
            b[3].append(mean)
        for k in TRACTIONS:
            if k not in buckets:
                continue
            late, early, same, sh = buckets[k]
            n = late + early + same
            out.append({
                "city": C.CITIES[city][0] if city in C.CITIES else "Łódź",
                "window": window, "traction": k, "trips": n,
                "late": late, "late_pct": round(100 * late / n, 1),
                "early": early, "early_pct": round(100 * early / n, 1),
                "unchanged": same, "unchanged_pct": round(100 * same / n, 1),
                "median_shift_s": round(statistics.median(sh)),
                "mean_shift_s": round(statistics.mean(sh)),
            })
    return out


def main(only=None):
    ds = C.ANALYSIS_DATE.replace("-", "")
    weekday = date(int(ds[:4]), int(ds[4:6]), int(ds[6:])).strftime("%A").lower()
    rows = []
    for city in (only or list(C.CITIES) + ["lodz"]):
        rows += analyse(city, ds, weekday)

    with open("out/gtfs_shift_by_traction.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    cur = None
    for r in rows:
        if (r["city"], r["window"]) != cur:
            cur = (r["city"], r["window"])
            print(f"\n{r['city']} — {r['window']}")
            print(f"  {'trakcja':10} {'kursów':>7} {'późn.':>13} {'przysp.':>13} {'bez zm.':>13} {'med':>6} {'śr':>6}")
        print(f"  {r['traction']:10} {r['trips']:>7} "
              f"{r['late']:>6} ({r['late_pct']:>4}%) {r['early']:>6} ({r['early_pct']:>4}%) "
              f"{r['unchanged']:>6} ({r['unchanged_pct']:>4}%) {r['median_shift_s']:>+5}s {r['mean_shift_s']:>+5}s")
    print("\n[ok] out/gtfs_shift_by_traction.csv")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main(sys.argv[1:] or None)
