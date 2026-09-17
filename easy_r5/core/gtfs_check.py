"""Pre-flight checks on raw GTFS zips, before a network is built (PR_easy-R5_v03.md R-3).

Pure stdlib — unit-testable outside QGIS. Reuses the calendar parsers from
``gtfs_calendar`` so "active trips per day" means exactly what the dead-date
guard in the matrix algorithms means by it.

Each check yields an ``Issue(level, code, message)``; nothing here raises on a
broken feed — a broken feed is the thing being reported.
"""

from __future__ import annotations

import datetime
import html
import statistics
import zipfile
from collections import Counter, namedtuple
from pathlib import Path

from .gtfs_calendar import (
    _exceptions,
    _iter_rows,
    _services,
    compute_service_days,
)
from .matrix import nearest_served_days

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"

Issue = namedtuple("Issue", "level code message")

_REQUIRED = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")


def r5_supports_route_type(route_type):
    """True if R5 7.6's ``TransitLayer.getTransitModes`` maps this GTFS route_type.

    Verified 2026-09-17 by javap: basic types 0-7, 11, 12, extended 100-1499.
    Anything else throws IllegalArgumentException inside R5.
    """
    return route_type in (0, 1, 2, 3, 4, 5, 6, 7, 11, 12) or 100 <= route_type < 1500


def check_feed(zip_path):
    """Read one GTFS zip. Returns a dict: ``feed``, ``issues``, ``routes``, ``stop_bbox``,
    ``stop_count``, ``trip_ids``, ``feed_id``, ``timezones``."""
    path = Path(zip_path)
    feed = path.stem
    issues = []
    out = {"feed": feed, "issues": issues, "routes": [], "stop_bbox": None, "stop_count": 0,
           "stop_coords": [], "trip_ids": set(), "feed_id": None, "timezones": set()}
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        issues.append(Issue(ERROR, "BAD_ZIP", "{}: not a readable zip ({}).".format(feed, exc)))
        return out
    with zf:
        names = set(zf.namelist())
        for name in _REQUIRED:
            if name not in names:
                issues.append(Issue(ERROR, "MISSING_FILE", "{}: {} is missing.".format(feed, name)))
        if "calendar.txt" not in names and "calendar_dates.txt" not in names:
            issues.append(Issue(ERROR, "NO_CALENDAR",
                                "{}: neither calendar.txt nor calendar_dates.txt exists.".format(feed)))
        if "shapes.txt" not in names:
            issues.append(Issue(INFO, "NO_SHAPES", "{}: no shapes.txt (fine for routing).".format(feed)))
        if "frequencies.txt" in names:
            issues.append(Issue(INFO, "FREQUENCIES",
                                "{}: frequencies.txt present — frequency trips are counted once "
                                "per row in the trips-per-day figures.".format(feed)))

        for row in _iter_rows(zf, "feed_info.txt"):
            out["feed_id"] = (row.get("feed_id") or "").strip() or None
            break
        for row in _iter_rows(zf, "agency.txt"):
            tz = (row.get("agency_timezone") or "").strip()
            if tz:
                out["timezones"].add(tz)
        if "agency.txt" in names and not out["timezones"]:
            issues.append(Issue(WARN, "NO_TIMEZONE", "{}: agency.txt has no agency_timezone.".format(feed)))

        stop_ids = set()
        bad_coords = 0
        coords = []
        for row in _iter_rows(zf, "stops.txt"):
            sid = (row.get("stop_id") or "").strip()
            if sid:
                stop_ids.add(sid)
            try:
                lat = float(row.get("stop_lat", ""))
                lon = float(row.get("stop_lon", ""))
            except ValueError:
                # GTFS requires coordinates for location_type 0-2; 3/4 may omit them.
                if (row.get("location_type") or "0").strip() in ("", "0", "1", "2"):
                    bad_coords += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
                bad_coords += 1
                continue
            coords.append((lon, lat))
        out["stop_count"] = len(stop_ids)
        out["stop_coords"] = coords
        if coords:
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            out["stop_bbox"] = (min(xs), min(ys), max(xs), max(ys))
        if bad_coords:
            issues.append(Issue(WARN, "BAD_STOP_COORDS",
                                "{}: {} stop(s) have missing, zero or out-of-range coordinates.".format(
                                    feed, bad_coords)))

        routes = {}
        bad_types = Counter()
        for row in _iter_rows(zf, "routes.txt"):
            rid = (row.get("route_id") or "").strip()
            try:
                rtype = int((row.get("route_type") or "").strip())
            except ValueError:
                rtype = None
            routes[rid] = {"feed": feed, "route_id": rid,
                           "short_name": (row.get("route_short_name") or "").strip(),
                           "long_name": (row.get("route_long_name") or "").strip(),
                           "route_type": rtype, "trips": 0}
            if rtype is None or not r5_supports_route_type(rtype):
                bad_types[rtype] += 1
        for rtype, n in sorted(bad_types.items(), key=lambda kv: str(kv[0])):
            issues.append(Issue(ERROR, "UNSUPPORTED_ROUTE_TYPE",
                                "{}: {} route(s) with route_type {} — R5 7.6 cannot map it to a "
                                "transit mode and fails the build.".format(feed, n, rtype)))

        services = _services(zf)
        exceptions = _exceptions(zf)
        service_ids = set(services) | {sid for (sid, _d) in exceptions}

        orphan_route = orphan_service = 0
        trip_ids = set()
        for row in _iter_rows(zf, "trips.txt"):
            tid = (row.get("trip_id") or "").strip()
            rid = (row.get("route_id") or "").strip()
            sid = (row.get("service_id") or "").strip()
            trip_ids.add(tid)
            if rid in routes:
                routes[rid]["trips"] += 1
            else:
                orphan_route += 1
            if sid not in service_ids:
                orphan_service += 1
        out["trip_ids"] = trip_ids
        out["routes"] = list(routes.values())
        if orphan_route:
            issues.append(Issue(WARN, "ORPHAN_TRIP_ROUTE",
                                "{}: {} trip(s) reference a route_id not in routes.txt.".format(
                                    feed, orphan_route)))
        if orphan_service:
            issues.append(Issue(WARN, "ORPHAN_TRIP_SERVICE",
                                "{}: {} trip(s) reference a service_id with no calendar entry — "
                                "they never run.".format(feed, orphan_service)))

        orphan_st_trip = orphan_st_stop = 0
        trips_with_times = set()
        for row in _iter_rows(zf, "stop_times.txt"):
            tid = (row.get("trip_id") or "").strip()
            if tid in trip_ids:
                trips_with_times.add(tid)
            else:
                orphan_st_trip += 1
            if (row.get("stop_id") or "").strip() not in stop_ids:
                orphan_st_stop += 1
        if orphan_st_trip:
            issues.append(Issue(WARN, "ORPHAN_STOP_TIME_TRIP",
                                "{}: {} stop_times row(s) reference a trip_id not in trips.txt.".format(
                                    feed, orphan_st_trip)))
        if orphan_st_stop:
            issues.append(Issue(WARN, "ORPHAN_STOP_TIME_STOP",
                                "{}: {} stop_times row(s) reference a stop_id not in stops.txt.".format(
                                    feed, orphan_st_stop)))
        empty = len(trip_ids - trips_with_times)
        if empty and "stop_times.txt" in names:
            issues.append(Issue(WARN, "TRIPS_WITHOUT_STOP_TIMES",
                                "{}: {} trip(s) have no stop_times.".format(feed, empty)))
    return out


def check_feeds(zip_paths, *, date=None, extent=None):
    """Check every zip, then the cross-feed rules. ``extent`` = (xmin, ymin, xmax, ymax) in WGS84.

    Returns a dict: ``issues`` (all), ``feeds`` (per-feed dicts from ``check_feed``),
    ``service_days`` ({ISO date: trips}), ``routes`` (rows for the routes CSV), ``summary``.
    """
    zip_paths = [Path(p) for p in zip_paths]
    issues = []
    if not zip_paths:
        issues.append(Issue(ERROR, "NO_FEEDS", "No GTFS .zip files given."))
        return {"issues": issues, "feeds": [], "service_days": {}, "routes": [], "summary": {}}

    feeds = [check_feed(p) for p in zip_paths]
    for f in feeds:
        issues.extend(f["issues"])

    readable = [p for p, f in zip(zip_paths, feeds) if not any(i.code == "BAD_ZIP" for i in f["issues"])]
    try:
        service_days = compute_service_days(readable)
    except (OSError, zipfile.BadZipFile):
        service_days = {}

    summary = {"feeds": len(feeds), "stops": sum(f["stop_count"] for f in feeds),
               "routes": sum(len(f["routes"]) for f in feeds)}
    served = {d: n for d, n in service_days.items() if n}
    if not served:
        issues.append(Issue(ERROR, "NO_SERVICE",
                            "No day in the feed calendar has any active trip — R5 would return "
                            "walk-only results for every date."))
    else:
        days = sorted(service_days)
        counts = [service_days[d] for d in days]
        summary.update(first_day=days[0], last_day=days[-1], min_trips=min(counts),
                       median_trips=statistics.median(counts), max_trips=max(counts))
        issues.append(Issue(INFO, "CALENDAR_SPAN",
                            "Calendar {} to {}; active trips per day min {}, median {:g}, max {}.".format(
                                days[0], days[-1], min(counts), statistics.median(counts), max(counts))))
        dead = len(days) - len(served)
        if dead:
            issues.append(Issue(WARN, "DAYS_WITHOUT_SERVICE",
                                "{} day(s) inside the calendar span have no active trips.".format(dead)))

    if date:
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            issues.append(Issue(ERROR, "BAD_DATE", "DATE must be yyyy-MM-dd (got {!r}).".format(date)))
        else:
            n = service_days.get(date, 0)
            summary["trips_on_date"] = n
            if n:
                issues.append(Issue(INFO, "DATE_OK", "{}: {} active trips.".format(date, n)))
            else:
                nearest = nearest_served_days(service_days, date, 3)
                issues.append(Issue(ERROR, "DATE_NO_SERVICE",
                                    "{}: no active trips — R5 would silently return walk-only "
                                    "results. Nearest served days: {}.".format(
                                        date, ", ".join(nearest) or "none")))

    zones = set().union(*(f["timezones"] for f in feeds))
    if len(zones) > 1:
        issues.append(Issue(WARN, "MIXED_TIMEZONES",
                            "Feeds declare different timezones: {}.".format(", ".join(sorted(zones)))))

    seen_ids = {}
    for f in feeds:
        fid = f["feed_id"]
        if fid:
            if fid in seen_ids:
                issues.append(Issue(ERROR, "DUPLICATE_FEED_ID",
                                    "{} and {} share feed_id '{}' — R5 refuses to build "
                                    "(DuplicateFeedException).".format(seen_ids[fid], f["feed"], fid)))
            seen_ids.setdefault(fid, f["feed"])
    for i, a in enumerate(feeds):
        for b in feeds[i + 1:]:
            shared = a["trip_ids"] & b["trip_ids"]
            if shared:
                issues.append(Issue(ERROR, "SHARED_TRIP_IDS",
                                    "{} and {} share {} trip_id(s) — a realized (P50/P85) feed and "
                                    "its static feed cannot sit in one network-build folder; use "
                                    "one folder per variant.".format(a["feed"], b["feed"], len(shared))))

    if extent is not None:
        xmin, ymin, xmax, ymax = extent
        coords = [c for f in feeds for c in f["stop_coords"]]
        inside = sum(1 for x, y in coords if xmin <= x <= xmax and ymin <= y <= ymax)
        if coords and inside == 0:
            issues.append(Issue(ERROR, "STOPS_OUTSIDE_EXTENT",
                                "No stop lies inside the given extent — wrong feed or wrong OSM area."))
        elif inside < len(coords):
            issues.append(Issue(WARN, "STOPS_PARTLY_OUTSIDE_EXTENT",
                                "{} of {} stops lie outside the given extent and will not link to "
                                "streets.".format(len(coords) - inside, len(coords))))

    by_type = Counter(r["route_type"] for f in feeds for r in f["routes"])
    issues.append(Issue(INFO, "ROUTE_TYPES", "Routes by route_type: {}.".format(
        ", ".join("{}={}".format(k, v) for k, v in sorted(by_type.items(), key=lambda kv: str(kv[0])))
        or "none")))
    for f in feeds:
        if f["stop_bbox"]:
            issues.append(Issue(INFO, "STOP_BBOX", "{}: {} stops, bbox {:.5f},{:.5f} - {:.5f},{:.5f}.".format(
                f["feed"], f["stop_count"], *f["stop_bbox"])))

    routes = [r for f in feeds for r in f["routes"]]
    summary["errors"] = sum(1 for i in issues if i.level == ERROR)
    summary["warnings"] = sum(1 for i in issues if i.level == WARN)
    return {"issues": issues, "feeds": feeds, "service_days": service_days,
            "routes": routes, "summary": summary}


def render_html(result, title="GTFS check"):
    """A self-contained HTML report (no external assets)."""
    esc = html.escape
    order = {ERROR: 0, WARN: 1, INFO: 2}
    colors = {ERROR: "#b3261e", WARN: "#8a5a00", INFO: "#44546a"}
    rows = "".join(
        '<tr><td style="color:{c};font-weight:600">{l}</td><td><code>{code}</code></td><td>{m}</td></tr>'.format(
            c=colors[i.level], l=i.level, code=esc(i.code), m=esc(i.message))
        for i in sorted(result["issues"], key=lambda i: order[i.level])
    )
    days = sorted(result["service_days"].items())
    peak = max((n for _d, n in days), default=0) or 1
    day_rows = "".join(
        '<tr><td>{d}</td><td style="text-align:right">{n}</td><td><div style="background:{bg};'
        'height:.7em;width:{w:.1f}%"></div></td></tr>'.format(
            d=d, n=n, w=100.0 * n / peak, bg="#2f6fb0" if n else "#b3261e")
        for d, n in days
    )
    s = result["summary"]
    return """<!doctype html><meta charset="utf-8"><title>{t}</title>
<style>body{{font:14px system-ui,sans-serif;margin:2em;max-width:70em}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:.3em .5em;vertical-align:top;text-align:left}}</style>
<h1>{t}</h1><p><b>{e}</b> error(s), <b>{w}</b> warning(s) — {f} feed(s), {st} stops, {r} routes.</p>
<h2>Findings</h2><table><tr><th>Level</th><th>Code</th><th>Message</th></tr>{rows}</table>
<h2>Active trips per day</h2><table><tr><th>Date</th><th>Trips</th><th></th></tr>{days}</table>
""".format(t=esc(title), e=s.get("errors", 0), w=s.get("warnings", 0), f=s.get("feeds", 0),
           st=s.get("stops", 0), r=s.get("routes", 0), rows=rows, days=day_rows)
