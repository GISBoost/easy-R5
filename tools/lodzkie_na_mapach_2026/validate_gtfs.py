"""E5 pre-flight -- pure stdlib GTFS validation, run BEFORE any R5 build.

Port of tools/realtime_delay_cities/validate_gtfs.py, generalized from "one
big-city feed" to "a folder of several small-to-medium feeds" (our
net_woj_* folders combine 8 independent operators, none as large as a
single city network).

Motivated directly by easy-R5 CLAUDE.md gotcha #1: "Data bez kursow = cichy
walk-only" -- R5 raises no error when a date has zero active trips, it just
silently returns walk-only routes for everything through that feed. This
already bit production once (GZM, August 2026). Never build a network on
an unvalidated GTFS folder.

Usage (no QGIS, no Java -- plain `py`):
    py validate_gtfs.py net_woj_static
    py validate_gtfs.py net_woj_lodzrt
    py validate_gtfs.py net_lodz_static
    py validate_gtfs.py net_lodz_p50
    py validate_gtfs.py --all
"""
import csv
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

# Per-feed minimum active trips on the analysis date. Deliberately per-feed,
# not per-folder: net_woj_static bundles 8 independent small operators, and
# a genuinely tiny rural feed (Rozprza: 69 trips/day, confirmed in E1)
# should not be held to a city-scale MIN_TRIPS. The floor below is "at least
# ONE trip" -- the real gate is "not zero", matching gotcha #1 exactly. A
# feed with a suspiciously low but nonzero count still gets FLAGGED (not
# blocked) so a human looks at it once, rather than the pipeline guessing a
# per-operator threshold it has no basis for.
MIN_TRIPS_HARD = 1
MIN_TRIPS_WARN = 20

REQUIRED_FILES = ["agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"]


def _read_csv(zf, name):
    if name not in zf.namelist():
        return []
    with zf.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def active_service_ids(zf, target_date):
    y, m, d = (int(x) for x in target_date.split("-"))
    tdate = date(y, m, d)
    weekday_field = ["monday", "tuesday", "wednesday", "thursday", "friday",
                      "saturday", "sunday"][tdate.weekday()]
    active = set()
    for row in _read_csv(zf, "calendar.txt"):
        start, end = row.get("start_date", ""), row.get("end_date", "")
        if not start or not end:
            continue
        sd = date(int(start[:4]), int(start[4:6]), int(start[6:8]))
        ed = date(int(end[:4]), int(end[4:6]), int(end[6:8]))
        if sd <= tdate <= ed and row.get(weekday_field, "0") == "1":
            active.add(row["service_id"])
    for row in _read_csv(zf, "calendar_dates.txt"):
        if row.get("date") != target_date.replace("-", ""):
            continue
        if row.get("exception_type") == "1":
            active.add(row["service_id"])
        elif row.get("exception_type") == "2":
            active.discard(row["service_id"])
    return active


def check_monotonic_stop_times(zf):
    """Returns count of trips with a non-increasing arrival_time sequence."""
    rows = _read_csv(zf, "stop_times.txt")
    by_trip = {}
    for r in rows:
        by_trip.setdefault(r["trip_id"], []).append(r)

    def to_secs(hms):
        h, m, s = (int(x) for x in hms.split(":"))
        return h * 3600 + m * 60 + s

    bad = 0
    for trip_id, trs in by_trip.items():
        try:
            trs_sorted = sorted(trs, key=lambda r: int(r["stop_sequence"]))
            times = [to_secs(r["arrival_time"]) for r in trs_sorted if r.get("arrival_time")]
        except (ValueError, KeyError):
            continue
        if any(b < a for a, b in zip(times, times[1:])):
            bad += 1
    return bad, len(by_trip)


def validate_one_feed(zip_path, target_date):
    """Returns dict with all findings for one GTFS zip."""
    result = {"file": zip_path.name, "errors": [], "warnings": []}
    if not zipfile.is_zipfile(zip_path):
        result["errors"].append("not a valid zip file")
        return result

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        missing = [f for f in REQUIRED_FILES if f not in names]
        if missing:
            result["errors"].append(f"missing required files: {missing}")
            return result

        active = active_service_ids(zf, target_date)
        trips = _read_csv(zf, "trips.txt")
        active_trips = [t for t in trips if t.get("service_id") in active]
        result["n_trips_total"] = len(trips)
        result["n_trips_active"] = len(active_trips)

        if len(active_trips) < MIN_TRIPS_HARD:
            result["errors"].append(
                f"GATE FAILED: 0 active trips on {target_date} -- gotcha #1, "
                f"silent walk-only. Feed has {len(trips)} trips total; check whether "
                f"its calendar/calendar_dates actually covers this date."
            )
        elif len(active_trips) < MIN_TRIPS_WARN:
            result["warnings"].append(
                f"only {len(active_trips)} active trips on {target_date} "
                f"(of {len(trips)} total) -- plausible for a small rural operator, "
                f"but confirm this isn't a partial-coverage artifact"
            )

        bad_mono, n_trips_checked = check_monotonic_stop_times(zf)
        if bad_mono:
            result["warnings"].append(
                f"{bad_mono}/{n_trips_checked} trips have non-monotonic stop_times "
                f"(arrival_time decreases along the trip)"
            )

    return result


def compare_static_vs_realized(static_zip, realized_zip, target_date):
    """Static/realized pair check: identical trip_id set (they must, since
    realized is a stop_times.txt rewrite of the same schedule), and the
    shift distribution doesn't look corrupted."""
    out = {"errors": [], "warnings": []}
    with zipfile.ZipFile(static_zip) as zs, zipfile.ZipFile(realized_zip) as zr:
        active_s = active_service_ids(zs, target_date)
        active_r = active_service_ids(zr, target_date)
        trips_s = {t["trip_id"] for t in _read_csv(zs, "trips.txt") if t.get("service_id") in active_s}
        trips_r = {t["trip_id"] for t in _read_csv(zr, "trips.txt") if t.get("service_id") in active_r}
        if trips_s != trips_r:
            only_s = trips_s - trips_r
            only_r = trips_r - trips_s
            out["errors"].append(
                f"trip_id sets differ: {len(only_s)} only in static, {len(only_r)} only in realized "
                f"-- static and realized must describe the same service"
            )

        # shift distribution on shared trips
        st_s = _read_csv(zs, "stop_times.txt")
        st_r = _read_csv(zr, "stop_times.txt")

        def to_secs(hms):
            try:
                h, m, s = (int(x) for x in hms.split(":"))
                return h * 3600 + m * 60 + s
            except (ValueError, AttributeError):
                return None

        idx_s = {(r["trip_id"], r["stop_sequence"]): to_secs(r.get("departure_time", ""))
                  for r in st_s if r["trip_id"] in trips_s}
        shifts = []
        for r in st_r:
            if r["trip_id"] not in trips_r:
                continue
            key = (r["trip_id"], r["stop_sequence"])
            t_s = idx_s.get(key)
            t_r = to_secs(r.get("departure_time", ""))
            if t_s is not None and t_r is not None:
                shifts.append(t_r - t_s)

        if shifts:
            shifts.sort()
            n = len(shifts)
            med = shifts[n // 2]
            p05 = shifts[int(n * 0.05)]
            grossly_early = sum(1 for s in shifts if s < -300) / n
            out["shift_median_s"] = med
            out["shift_p05_s"] = p05
            out["shift_grossly_early_pct"] = 100 * grossly_early
            if med < -120:
                out["errors"].append(f"median shift {med}s -- feed runs systematically early, looks wrong")
            if grossly_early > 0.02:
                out["errors"].append(f"{100*grossly_early:.1f}% of stop-times >5min early -- feed looks wrong")
            if p05 < -300:
                out["errors"].append(f"p05 shift {p05}s -- left tail too heavy, feed looks wrong")
        else:
            out["warnings"].append("no shared (trip_id, stop_sequence) pairs to compare shifts on")
    return out


def validate_folder(name):
    folder = C.NETWORKS_DIR / name / "gtfs"
    print(f"\n{'='*60}\nValidating {name} ({folder})\n{'='*60}")
    if not folder.exists():
        print(f"  ERROR: folder does not exist")
        return False

    zips = sorted(folder.glob("*.zip"))
    print(f"  {len(zips)} feed(s): {[z.name for z in zips]}")
    ok = True
    for z in zips:
        r = validate_one_feed(z, C.ANALYSIS_DATE)
        status = "FAIL" if r["errors"] else ("WARN" if r["warnings"] else "OK")
        print(f"  [{status}] {r['file']}: trips_active={r.get('n_trips_active','?')}"
              f"/{r.get('n_trips_total','?')}")
        for e in r["errors"]:
            print(f"      ERROR: {e}")
            ok = False
        for w in r["warnings"]:
            print(f"      warn: {w}")

    # static-vs-realized pair check where applicable
    pairs = {
        "net_woj_lodzrt": ("net_woj_static", "lodz.zip"),
        "net_lodz_p50": ("net_lodz_static", "lodz.zip"),
    }
    # NOTE: the 2026-09-08/09-09 multi-day networks (MULTIDAY_LODZ_NOTES.md)
    # are deliberately NOT added here -- this function always compares against
    # the single global C.ANALYSIS_DATE, which would silently check the wrong
    # date for those pairs. They were validated once, correctly, with a
    # one-off script calling validate_one_feed/compare_static_vs_realized
    # directly per real date (see MULTIDAY_LODZ_NOTES.md) -- all three passed.
    if name in pairs:
        static_name, fname = pairs[name]
        static_zip = C.NETWORKS_DIR / static_name / "gtfs" / fname
        realized_zip = folder / fname
        if static_zip.exists() and realized_zip.exists():
            print(f"  -- comparing {fname} vs {static_name} --")
            cmp = compare_static_vs_realized(static_zip, realized_zip, C.ANALYSIS_DATE)
            if "shift_median_s" in cmp:
                print(f"     shift median={cmp['shift_median_s']}s p05={cmp['shift_p05_s']}s "
                      f"grossly_early={cmp['shift_grossly_early_pct']:.2f}%")
            for e in cmp["errors"]:
                print(f"      ERROR: {e}")
                ok = False
            for w in cmp["warnings"]:
                print(f"      warn: {w}")

    print(f"  ==> {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    args = sys.argv[1:]
    if not args or args == ["--all"]:
        names = ["net_woj_static", "net_woj_lodzrt", "net_lodz_static", "net_lodz_p50"]
    else:
        names = args
    results = {name: validate_folder(name) for name in names}
    print(f"\n{'='*60}\nSummary\n{'='*60}")
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
