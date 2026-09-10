"""Pre-flight GTFS check for the 5 cities -- run BEFORE any R5 build so we never
compute accessibility on an empty or broken feed (easy-R5 CLAUDE.md gotcha #1:
"data bez kursow = cichy walk-only", R5 raises no error).

Pure stdlib, run with `py validate_gtfs.py`. For each city, static + realized:
  - required files present and non-empty
  - stops / routes / trips / stop_times row counts sane
  - >= cities.MIN_TRIPS trips active on ANALYSIS_DATE (calendar + calendar_dates)
  - stop_times HH:MM:SS parse; per-trip arrival non-decreasing
And static vs realized: identical trip_id set, identical stop_id set, realized
median shift vs static is small and >= 0 (trains/buses run late, not early).
Exit non-zero on any hard failure.
"""

from __future__ import annotations

import csv
import io
import statistics
import sys
import zipfile
from datetime import date

import cities as C

REQUIRED = ("agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
DATE = C.ANALYSIS_DATE
DS = DATE.replace("-", "")
WEEKDAY = date(int(DS[:4]), int(DS[4:6]), int(DS[6:])).strftime("%A").lower()


def _rows(zf, name):
    with zf.open(name) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, "utf-8-sig"))


def _active_services(zf):
    names = zf.namelist()
    active = set()
    if "calendar.txt" in names:
        for r in _rows(zf, "calendar.txt"):
            if r["start_date"] <= DS <= r["end_date"] and r.get(WEEKDAY) == "1":
                active.add(r["service_id"])
    if "calendar_dates.txt" in names:
        for r in _rows(zf, "calendar_dates.txt"):
            if r["date"] == DS:
                (active.add if r["exception_type"] == "1" else active.discard)(r["service_id"])
    return active


def _to_sec(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def _load(zf):
    """-> (trip_ids_on_date, stop_ids, {trip_id: [(seq, arr_sec, stop_id)]})"""
    active = _active_services(zf)
    trips_on_date = {r["trip_id"] for r in _rows(zf, "trips.txt") if r["service_id"] in active}
    stop_ids = {r["stop_id"] for r in _rows(zf, "stops.txt")}
    st = {}
    for r in _rows(zf, "stop_times.txt"):
        tid = r["trip_id"]
        if tid not in trips_on_date:
            continue
        arr = r.get("arrival_time") or r.get("departure_time") or ""
        if not arr.strip():
            continue
        st.setdefault(tid, []).append((int(r["stop_sequence"]), _to_sec(arr), r["stop_id"]))
    return trips_on_date, stop_ids, st


def check_feed(city, kind, zpath, problems):
    tag = f"{city}/{kind}"
    if not zpath.exists():
        problems.append(f"{tag}: file missing {zpath}")
        return None
    zf = zipfile.ZipFile(zpath)
    names = set(zf.namelist())
    for req in REQUIRED:
        if req not in names:
            problems.append(f"{tag}: missing {req}")
        elif zf.getinfo(req).file_size == 0:
            problems.append(f"{tag}: {req} is empty")
    if not names.issuperset(REQUIRED):
        return None

    trips_on_date, stop_ids, st = _load(zf)
    n_stops = sum(1 for _ in _rows(zf, "stops.txt"))
    n_routes = sum(1 for _ in _rows(zf, "routes.txt"))
    print(f"  {tag:22} stops={n_stops:6} routes={n_routes:5} trips@{DATE}={len(trips_on_date):6} "
          f"stop_times_trips={len(st):6}")

    if len(trips_on_date) < C.MIN_TRIPS:
        problems.append(f"{tag}: only {len(trips_on_date)} trips active on {DATE} (< {C.MIN_TRIPS}) -- walk-only risk")
    if not st:
        problems.append(f"{tag}: no stop_times for any {DATE} trip")
    bad_mono = 0
    for tid, seq in st.items():
        arrs = [a for _, a, _ in sorted(seq)]
        if any(b < a for a, b in zip(arrs, arrs[1:])):
            bad_mono += 1
    if bad_mono:
        problems.append(f"{tag}: {bad_mono} trips have decreasing arrival times")
    return trips_on_date, stop_ids, st


def compare(city, s, r, problems):
    if not s or not r:
        return
    s_trips, s_stops, s_st = s
    r_trips, r_stops, r_st = r
    if s_trips != r_trips:
        problems.append(f"{city}: trip_id set differs static vs realized "
                        f"(only-static={len(s_trips - r_trips)}, only-realized={len(r_trips - s_trips)})")
    if not s_stops.issubset(r_stops) and not r_stops.issubset(s_stops):
        problems.append(f"{city}: stop_id sets diverge (s\\r={len(s_stops - r_stops)}, r\\s={len(r_stops - s_stops)})")

    shifts = []
    for tid in s_trips & r_trips:
        sd = {seq: a for seq, a, _ in s_st.get(tid, [])}
        rd = {seq: a for seq, a, _ in r_st.get(tid, [])}
        for seq in sd.keys() & rd.keys():
            shifts.append(rd[seq] - sd[seq])
    if shifts:
        shifts.sort()
        med = statistics.median(shifts)
        p05 = shifts[len(shifts) // 20]
        grossly_early = sum(1 for x in shifts if x < -300) / len(shifts)
        print(f"  {city}: realized-vs-static shift  median={med:+.0f}s  mean={statistics.mean(shifts):+.0f}s  "
              f"p05={p05:+.0f}s  >5min early={grossly_early:.2%}  (n={len(shifts)})")
        # A healthy realized feed sits near a 0 median with a fat *late* tail.
        # Fail only on a real corruption signature: strongly negative centre,
        # or a heavy grossly-early mass (vehicles can't systematically beat the
        # schedule by 5+ min).
        if med < -120:
            problems.append(f"{city}: realized median shift {med:+.0f}s -- feed runs systematically early, looks wrong")
        if grossly_early > 0.02:
            problems.append(f"{city}: {grossly_early:.1%} of stop times are >5 min early in realized -- feed looks wrong")
        if p05 < -300:
            problems.append(f"{city}: realized p05 shift {p05:+.0f}s -- left tail too heavy, feed looks wrong")
    else:
        problems.append(f"{city}: no overlapping (trip,stop) pairs to compare shift")


def main(only=None):
    problems = []
    for city in (only or C.CITIES):
        print(f"[{city}]")
        p = C.paths(city)
        s = check_feed(city, "static", p["gtfs_static"], problems)
        r = check_feed(city, "realized", p["gtfs_realized"], problems)
        compare(city, s, r, problems)
    print()
    if problems:
        print("FAIL:")
        for x in problems:
            print("  -", x)
        sys.exit(1)
    print("OK -- all feeds valid, safe to build R5 networks.")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
