"""Count GTFS trips active on each date, from the raw feed zip(s).

Pure stdlib — unit-testable outside QGIS. Feeds the ``service_days`` field of
network.json so M3 can refuse to run on a date with zero service (R5 silently
degrades to walk-only otherwise — the GZM bug of August 2026).

This re-implements the GTFS calendar semantics R5's ``Service.activeOn`` already
has, on purpose: it must be pure Python so the M2 test suite can cover the full
matrix of real Polish feed shapes (calendar-only, calendar_dates-only, both,
all-zero weekday rows, quoted CSV with commas in service_id, BOM headers,
reversed column order) without a JVM. The reference is
``tools/isochrones_lodz/verify_departure_date.R``; the ``weekdays()`` locale trap
it documents does not apply here because ``date.weekday()`` returns an integer.
"""

from __future__ import annotations

import csv
import datetime
import io
import zipfile

# date.weekday(): Monday=0 .. Sunday=6 — indexes this list, no locale involved.
_WEEKDAY_COLS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]

_DEFAULT_CAP_DAYS = 90


def _iter_rows(zf, name):
    """Yield each data row of ``name`` as a dict keyed by lowercased headers.

    Missing file -> nothing. Handles UTF-8 BOM, quoted fields (commas inside a
    value), and any column order. Streams — one row dict live at a time.
    """
    try:
        info = zf.getinfo(name)
    except KeyError:
        return
    with zf.open(info) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.reader(text)
        try:
            header = [h.strip().lower() for h in next(reader)]
        except StopIteration:
            return
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            yield dict(zip(header, row))


def _gtfs_date(s):
    """'20260825' -> date(2026, 8, 25). Raises ValueError on anything else."""
    s = s.strip()
    return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def _services(zf):
    """calendar.txt -> {service_id: {'days': set[int], 'start': date, 'end': date}}."""
    out = {}
    for row in _iter_rows(zf, "calendar.txt"):
        sid = row.get("service_id", "").strip()
        if not sid:
            continue
        try:
            start = _gtfs_date(row["start_date"])
            end = _gtfs_date(row["end_date"])
        except (KeyError, ValueError):
            continue
        days = {
            i for i, col in enumerate(_WEEKDAY_COLS)
            if row.get(col, "0").strip() == "1"
        }
        out[sid] = {"days": days, "start": start, "end": end}
    return out


def _exceptions(zf):
    """calendar_dates.txt -> {(service_id, date): exception_type}."""
    out = {}
    for row in _iter_rows(zf, "calendar_dates.txt"):
        sid = row.get("service_id", "").strip()
        if not sid:
            continue
        try:
            out[(sid, _gtfs_date(row["date"]))] = int(row["exception_type"].strip())
        except (KeyError, ValueError):
            continue
    return out


def _trip_counts(zf):
    """trips.txt -> {service_id: number of trip rows}.

    ponytail: frequency-based trips (frequencies.txt, Warszawa) count as one row
    each — an undercount of vehicle trips. Fine for the "is this date dead?"
    gate; expand by headway only if an exact trip count is ever needed.
    """
    counts = {}
    for row in _iter_rows(zf, "trips.txt"):
        sid = row.get("service_id", "").strip()
        if sid:
            counts[sid] = counts.get(sid, 0) + 1
    return counts


def _active_on(sid, day, services, exceptions):
    """GTFS semantics: a calendar_dates exception overrides calendar entirely."""
    exc = exceptions.get((sid, day))
    if exc is not None:
        return exc == 1  # 1 = added, 2 = removed
    svc = services.get(sid)
    if svc is None:
        return False
    if not (svc["start"] <= day <= svc["end"]):
        return False
    return day.weekday() in svc["days"]


def compute_service_days(gtfs_zip_paths, cap_days=_DEFAULT_CAP_DAYS):
    """Return {ISO date: active trip count} for every day of the feed span.

    Span = min/max over calendar start/end dates and calendar_dates dates,
    across all feeds, capped at ``cap_days`` from the first day. Trip counts are
    summed across feeds. Empty span (no calendar data anywhere) -> {}.
    """
    feeds = []
    all_dates = []
    for path in gtfs_zip_paths:
        with zipfile.ZipFile(path) as zf:
            services = _services(zf)
            exceptions = _exceptions(zf)
            trips = _trip_counts(zf)
        feeds.append((services, exceptions, trips))
        for svc in services.values():
            all_dates.append(svc["start"])
            all_dates.append(svc["end"])
        all_dates.extend(day for (_sid, day) in exceptions)

    if not all_dates:
        return {}

    start = min(all_dates)
    end = min(max(all_dates), start + datetime.timedelta(days=cap_days - 1))

    result = {}
    day = start
    while day <= end:
        total = 0
        for services, exceptions, trips in feeds:
            for sid, count in trips.items():
                if count and _active_on(sid, day, services, exceptions):
                    total += count
        result[day.isoformat()] = total
        day += datetime.timedelta(days=1)
    return result
