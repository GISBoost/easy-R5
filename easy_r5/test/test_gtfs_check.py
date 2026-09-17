"""GTFS pre-flight checks. Pure Python — run: py -m pytest easy_r5/test/test_gtfs_check.py -v"""

import zipfile

from easy_r5.core.gtfs_check import (
    ERROR,
    WARN,
    check_feeds,
    r5_supports_route_type,
    render_html,
)

_CAL = ("service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "WD,1,1,1,1,1,0,0,20260801,20260831\n")


def _feed(path, *, files=None, drop=(), trips=None, routes=None, stops=None, stop_times=None,
          feed_id=None):
    content = {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nA,A,http://a,Europe/Warsaw\n",
        "stops.txt": stops or "stop_id,stop_name,stop_lat,stop_lon\nS1,a,51.75,19.45\nS2,b,51.76,19.46\n",
        "routes.txt": routes or "route_id,route_short_name,route_long_name,route_type\nR1,1,One,0\n",
        "trips.txt": trips or "route_id,service_id,trip_id\nR1,WD,T1\nR1,WD,T2\n",
        "stop_times.txt": stop_times or (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,07:00:00,07:00:00,S1,1\nT1,07:05:00,07:05:00,S2,2\n"
            "T2,08:00:00,08:00:00,S1,1\nT2,08:05:00,08:05:00,S2,2\n"),
        "calendar.txt": _CAL,
    }
    if feed_id:
        content["feed_info.txt"] = ("feed_publisher_name,feed_publisher_url,feed_lang,feed_id\n"
                                    "x,http://x,pl,{}\n".format(feed_id))
    content.update(files or {})
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in content.items():
            if name not in drop:
                zf.writestr(name, text)
    return path


def _codes(result, level=None):
    return {i.code for i in result["issues"] if level is None or i.level == level}


def test_clean_feed_has_no_errors(tmp_path):
    res = check_feeds([_feed(tmp_path / "ok.zip")], date="2026-08-24")
    assert _codes(res, ERROR) == set()
    assert res["summary"]["trips_on_date"] == 2
    assert res["routes"][0]["trips"] == 2


def test_missing_files_and_calendar(tmp_path):
    res = check_feeds([_feed(tmp_path / "f.zip", drop=("stop_times.txt", "calendar.txt"))])
    assert {"MISSING_FILE", "NO_CALENDAR", "NO_SERVICE"} <= _codes(res, ERROR)


def test_date_without_service_names_nearest_days(tmp_path):
    res = check_feeds([_feed(tmp_path / "f.zip")], date="2026-08-23")  # a Sunday
    msg = next(i.message for i in res["issues"] if i.code == "DATE_NO_SERVICE")
    assert "2026-08-24" in msg and "2026-08-21" in msg


def test_orphans_are_warnings(tmp_path):
    res = check_feeds([_feed(
        tmp_path / "f.zip",
        trips="route_id,service_id,trip_id\nR9,WD,T1\nR1,NOPE,T2\nR1,WD,T3\n",
        stop_times="trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                   "T1,07:00:00,07:00:00,S1,1\nTX,07:00:00,07:00:00,S9,1\n",
    )])
    assert {"ORPHAN_TRIP_ROUTE", "ORPHAN_TRIP_SERVICE", "ORPHAN_STOP_TIME_TRIP",
            "ORPHAN_STOP_TIME_STOP", "TRIPS_WITHOUT_STOP_TIMES"} <= _codes(res, WARN)


def test_unsupported_route_type(tmp_path):
    res = check_feeds([_feed(tmp_path / "f.zip",
                             routes="route_id,route_short_name,route_long_name,route_type\nR1,1,x,1700\n")])
    assert "UNSUPPORTED_ROUTE_TYPE" in _codes(res, ERROR)


def test_route_type_support_matches_r5():
    assert all(r5_supports_route_type(t) for t in (0, 3, 7, 11, 12, 100, 700, 1499))
    assert not any(r5_supports_route_type(t) for t in (8, 9, 10, 13, 99, 1500, 1702))


def test_realized_and_static_in_one_folder(tmp_path):
    res = check_feeds([_feed(tmp_path / "static.zip"), _feed(tmp_path / "p50.zip")])
    assert "SHARED_TRIP_IDS" in _codes(res, ERROR)


def test_duplicate_feed_id(tmp_path):
    a = _feed(tmp_path / "a.zip", feed_id="lodz")
    b = _feed(tmp_path / "b.zip", feed_id="lodz",
              trips="route_id,service_id,trip_id\nR1,WD,B1\n",
              stop_times="trip_id,arrival_time,departure_time,stop_id,stop_sequence\nB1,07:00:00,07:00:00,S1,1\n")
    assert "DUPLICATE_FEED_ID" in _codes(check_feeds([a, b]), ERROR)


def test_extent(tmp_path):
    f = _feed(tmp_path / "f.zip")
    assert "STOPS_OUTSIDE_EXTENT" in _codes(check_feeds([f], extent=(0, 0, 1, 1)), ERROR)
    assert "STOPS_PARTLY_OUTSIDE_EXTENT" in _codes(
        check_feeds([f], extent=(19.44, 51.74, 19.455, 51.755)), WARN)


def test_bad_zip_and_bad_coords(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip")
    f = _feed(tmp_path / "f.zip", stops="stop_id,stop_name,stop_lat,stop_lon\nS1,a,0,0\nS2,b,51.7,19.4\n")
    res = check_feeds([bad, f])
    assert "BAD_ZIP" in _codes(res, ERROR)
    assert "BAD_STOP_COORDS" in _codes(res, WARN)


def test_render_html_escapes(tmp_path):
    res = check_feeds([_feed(tmp_path / "f.zip",
                             routes="route_id,route_short_name,route_long_name,route_type\n<R>,1,x,1700\n")])
    page = render_html(res)
    assert "<R>" not in page and "UNSUPPORTED_ROUTE_TYPE" in page
