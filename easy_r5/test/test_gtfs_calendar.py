"""service_days computation against synthetic GTFS feeds covering every real
Polish feed shape. Pure Python — run: py -m pytest easy_r5/test/test_gtfs_calendar.py -v
"""

import zipfile

from easy_r5.core.gtfs_calendar import compute_service_days


def _make_gtfs(
    path,
    *,
    calendar=None,          # list of dict rows for calendar.txt
    calendar_dates=None,    # list of (service_id, date, exception_type)
    trips=None,             # list of service_id (one entry per trip row)
    bom=False,
    quoted=False,
    cd_header="service_id,date,exception_type",
):
    def enc(s):
        return ("﻿" if bom else "") + s

    def cell(v):
        return '"{}"'.format(v) if quoted else str(v)

    with zipfile.ZipFile(path, "w") as zf:
        if calendar is not None:
            cols = ["service_id"] + [
                "monday", "tuesday", "wednesday", "thursday", "friday",
                "saturday", "sunday",
            ] + ["start_date", "end_date"]
            lines = [",".join(cols)]
            for row in calendar:
                lines.append(",".join(cell(row[c]) for c in cols))
            zf.writestr("calendar.txt", enc("\n".join(lines) + "\n"))
        if calendar_dates is not None:
            order = cd_header.split(",")
            lines = [cd_header]
            for sid, date, exc in calendar_dates:
                vals = {"service_id": sid, "date": date, "exception_type": exc}
                lines.append(",".join(cell(vals[c]) for c in order))
            zf.writestr("calendar_dates.txt", enc("\n".join(lines) + "\n"))
        if trips is not None:
            lines = ["route_id,service_id,trip_id"]
            for i, sid in enumerate(trips):
                lines.append(",".join([cell("R1"), cell(sid), cell("t{}".format(i))]))
            zf.writestr("trips.txt", enc("\n".join(lines) + "\n"))


def _cal_row(sid, days, start, end):
    flags = {c: v for c, v in zip(
        ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        days,
    )}
    return {"service_id": sid, "start_date": start, "end_date": end, **flags}


def test_calendar_only_weekday_pattern(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar=[_cal_row("WD", [1, 1, 1, 1, 1, 0, 0], "20260801", "20261031")],
        trips=["WD", "WD", "WD"],
    )
    days = compute_service_days([z])
    assert days["2026-08-19"] == 3      # Wednesday
    assert days["2026-08-22"] == 0      # Saturday
    assert "2026-07-31" not in days     # before span


def test_calendar_dates_only(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar_dates=[("S1", "20260825", 1), ("S1", "20260826", 1)],
        trips=["S1", "S1"],
    )
    days = compute_service_days([z])
    assert days["2026-08-25"] == 2
    assert days["2026-08-26"] == 2
    assert days.get("2026-08-27", 0) == 0


def test_both_with_type2_removal_and_type1_addition(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar=[_cal_row("WD", [1, 1, 1, 1, 1, 0, 0], "20260801", "20260930")],
        calendar_dates=[
            ("WD", "20260826", 2),   # remove a Wednesday
            ("WD", "20260830", 1),   # add a Sunday
        ],
        trips=["WD", "WD"],
    )
    days = compute_service_days([z])
    assert days["2026-08-19"] == 2      # ordinary Wednesday, still runs
    assert days["2026-08-26"] == 0      # removed by type-2
    assert days["2026-08-30"] == 2      # added by type-1 (a Sunday)
    assert days["2026-08-23"] == 0      # ordinary Sunday, no service


def test_all_zero_calendar_plus_calendar_dates(tmp_path):
    # Kraków / Łódź / Kielce shape: calendar.txt present but every weekday 0,
    # service entirely driven by calendar_dates type-1 rows.
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar=[_cal_row("A", [0] * 7, "20260820", "20261231")],
        calendar_dates=[("A", "20260824", 1), ("A", "20260825", 1)],
        trips=["A", "A", "A"],
    )
    days = compute_service_days([z])
    assert days["2026-08-24"] == 3
    assert days["2026-08-25"] == 3
    assert days["2026-08-26"] == 0     # no calendar_dates row, calendar all-zero


def test_trip_counts_sum_per_active_service(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar=[
            _cal_row("A", [1, 1, 1, 1, 1, 0, 0], "20260801", "20261031"),  # Mon-Fri
            _cal_row("B", [0, 0, 0, 0, 0, 1, 1], "20260801", "20261031"),  # Sat-Sun
        ],
        trips=["A", "A", "A", "B", "B"],
    )
    days = compute_service_days([z])
    assert days["2026-08-19"] == 3      # Wednesday: only A
    assert days["2026-08-22"] == 2      # Saturday: only B


def test_reversed_calendar_dates_column_order(tmp_path):
    # Warszawa: calendar_dates.txt header is date,service_id,exception_type
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar_dates=[("S1", "20260825", 1)],
        trips=["S1"],
        cd_header="date,service_id,exception_type",
    )
    days = compute_service_days([z])
    assert days["2026-08-25"] == 1


def test_quoted_csv_with_comma_in_service_id(tmp_path):
    # Szczecin: fully quoted CSV, service_id like "+919,999"
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar_dates=[("+919,999", "20260825", 1)],
        trips=["+919,999", "+919,999"],
        quoted=True,
    )
    days = compute_service_days([z])
    assert days["2026-08-25"] == 2


def test_bom_header(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar=[_cal_row("A", [1, 1, 1, 1, 1, 1, 1], "20260801", "20261031")],
        trips=["A"],
        bom=True,
    )
    days = compute_service_days([z])
    assert days["2026-08-19"] == 1


def test_cap_at_90_days(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar=[_cal_row("A", [1] * 7, "20260101", "20261231")],  # ~365 days
        trips=["A"],
    )
    days = compute_service_days([z])
    assert len(days) == 90
    assert min(days) == "2026-01-01"
    assert max(days) == "2026-03-31"    # 2026-01-01 + 89 days


def test_multi_feed_sums(tmp_path):
    z1 = tmp_path / "a.zip"
    z2 = tmp_path / "b.zip"
    _make_gtfs(z1, calendar_dates=[("X", "20260825", 1)], trips=["X", "X"])
    _make_gtfs(z2, calendar_dates=[("Y", "20260825", 1)], trips=["Y", "Y", "Y"])
    days = compute_service_days([z1, z2])
    assert days["2026-08-25"] == 5


def test_empty_feed_returns_empty(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(z, trips=["A"])   # no calendar, no calendar_dates
    assert compute_service_days([z]) == {}


def test_service_in_trips_but_not_in_calendar_contributes_nothing(tmp_path):
    z = tmp_path / "f.zip"
    _make_gtfs(
        z,
        calendar_dates=[("KNOWN", "20260825", 1)],
        trips=["KNOWN", "GHOST", "GHOST"],
    )
    days = compute_service_days([z])
    assert days["2026-08-25"] == 1      # only the KNOWN trip
