"""Characterise every tram line in a GTFS feed. Pure stdlib -- no QGIS, no R5.

Shared by rank_lines.py (which ranks and picks) and build_scenarios.py (which needs
the same route ids and corridor overlaps). Nothing here decides anything; it measures.

Run standalone for the table:  py gtfs_lines.py
"""

from __future__ import annotations

import csv
import io
import math
import sqlite3
import statistics
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
GTFS = TOOLS / "accessibility_lodz" / "lodz_static_gtfs_2026-08-21.zip"
CENSUS = TOOLS / "ses_income_lodz" / "lodz.gpkg"

ANALYSIS_DATE = date(2026, 8, 21)
TRAM = "0"
WALK_M = 500          # how far people walk to a tram stop, for "population served"
PEAK = (7 * 3600, 9 * 3600)
INNER_M = 2500        # "city centre" = within this of the population-weighted centroid
OUTER_M = 4000
MIN_TRIPS = 20        # below this a route is a depot run or a curiosity, not a line

_EARTH_R = 6371008.8
_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def haversine_m(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_R * math.asin(math.sqrt(h))


def _rows(zf, name):
    with zf.open(name) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig"))


def _secs(text):
    h, m, s = (int(x) for x in text.split(":"))
    return h * 3600 + m * 60 + s


# --- PL-1992 (EPSG:2180) -> WGS84 -------------------------------------------
# The census gpkg stores its CRS as srs_id 100000 with organization NONE, so neither
# sqlite3 nor pyproj can look it up; the parameters are PL-1992's by inspection of the
# coordinate range. prepare_data.py re-derives the same centroid inside QGIS with a real
# CRS transform and asserts the two agree -- that assertion is what makes this safe.
_A, _F = 6378137.0, 1 / 298.257222101
_E2 = _F * (2 - _F)
_K0, _LON0, _X0, _Y0 = 0.9993, math.radians(19.0), 500000.0, -5300000.0


def pl1992_to_wgs84(x, y):
    m = (y - _Y0) / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64))
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16) * math.sin(4 * mu) + (151 * e1 ** 3 / 96) * math.sin(6 * mu))
    c1 = _E2 / (1 - _E2) * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = _A / math.sqrt(1 - _E2 * math.sin(phi1) ** 2)
    r1 = _A * (1 - _E2) / (1 - _E2 * math.sin(phi1) ** 2) ** 1.5
    d = (x - _X0) / (n1 * _K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * _E2 / (1 - _E2)) * d ** 4 / 24)
    lon = _LON0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6) / math.cos(phi1)
    return math.degrees(lon), math.degrees(lat)


def population_points(census=CENSUS):
    """[(population, lon, lat)] per census precinct, from the GPKG r-tree envelope.

    Precinct envelopes are a few hundred metres across, so their centre is a fine
    stand-in for the centroid at the 500 m / 1000 m scales used here.
    """
    con = sqlite3.connect(census)
    try:
        rows = con.execute("""
            select p.population, (r.minx + r.maxx) / 2, (r.miny + r.maxy) / 2
            from obwody_spisowe p join rtree_obwody_spisowe_geom r on r.id = p.fid
            where p.population is not null and p.population > 0
        """).fetchall()
    finally:
        con.close()
    return [(pop, *pl1992_to_wgs84(x, y)) for pop, x, y in rows]


def weighted_centroid(points):
    total = sum(p for p, _, _ in points)
    return (sum(p * lon for p, lon, _ in points) / total,
            sum(p * lat for p, _, lat in points) / total)


class Feed:
    """The parts of one GTFS feed this analysis needs, for one service date."""

    def __init__(self, path=GTFS, day=ANALYSIS_DATE):
        self.path = Path(path)
        zf = zipfile.ZipFile(self.path)
        weekday = _DAYS[day.weekday()]
        stamp = day.strftime("%Y%m%d")

        self.services = set()
        for r in _rows(zf, "calendar.txt"):
            if r["start_date"] <= stamp <= r["end_date"] and r[weekday] == "1":
                self.services.add(r["service_id"])
        for r in _rows(zf, "calendar_dates.txt"):
            if r["date"] == stamp:
                (self.services.add if r["exception_type"] == "1"
                 else self.services.discard)(r["service_id"])

        self.stops = {r["stop_id"]: (float(r["stop_lon"]), float(r["stop_lat"]))
                      for r in _rows(zf, "stops.txt")}
        self.stop_names = {r["stop_id"]: r["stop_name"] for r in _rows(zf, "stops.txt")}
        self.routes = {r["route_id"]: r for r in _rows(zf, "routes.txt")}
        self.trips = {r["trip_id"]: r for r in _rows(zf, "trips.txt")
                      if r["service_id"] in self.services}

        self.trip_stops = defaultdict(list)
        for r in _rows(zf, "stop_times.txt"):
            if r["trip_id"] in self.trips:
                self.trip_stops[r["trip_id"]].append(
                    (int(r["stop_sequence"]), r["stop_id"], r["arrival_time"],
                     r["departure_time"]))
        for tid in self.trip_stops:
            self.trip_stops[tid].sort()
        zf.close()

    def trips_of(self, route_id):
        return [t for t, r in self.trips.items() if r["route_id"] == route_id]

    def stops_of(self, route_id):
        return {s[1] for t in self.trips_of(route_id) for s in self.trip_stops[t]
                if s[1] in self.stops}

    def tram_routes(self, min_trips=MIN_TRIPS):
        """Route ids of tram lines with real service, longest-first."""
        out = []
        for rid, r in self.routes.items():
            if r["route_type"] != TRAM:
                continue
            tids = self.trips_of(rid)
            if len(tids) < min_trips or not any(len(self.trip_stops[t]) > 1 for t in tids):
                continue
            out.append(rid)
        return sorted(out, key=lambda rid: -self.length_km(rid))

    def longest_pattern(self, route_id):
        best = []
        for t in self.trips_of(route_id):
            if len(self.trip_stops[t]) > len(best):
                best = self.trip_stops[t]
        return best

    def length_km(self, route_id):
        pts = [self.stops[s[1]] for s in self.longest_pattern(route_id) if s[1] in self.stops]
        return sum(haversine_m(a, b) for a, b in zip(pts, pts[1:])) / 1000

    def vehicle_km(self, route_id):
        total = 0.0
        for t in self.trips_of(route_id):
            pts = [self.stops[s[1]] for s in self.trip_stops[t] if s[1] in self.stops]
            total += sum(haversine_m(a, b) for a, b in zip(pts, pts[1:]))
        return total / 1000

    def peak_departures(self, route_id):
        """Departures from the first stop inside the morning peak, per hour."""
        n = 0
        for t in self.trips_of(route_id):
            s = self.trip_stops[t]
            if s and PEAK[0] <= _secs(s[0][3] or s[0][2]) < PEAK[1]:
                n += 1
        return n / ((PEAK[1] - PEAK[0]) / 3600)

    def segments(self, route_id, peak_only=True):
        """[(distance_m, running_time_s, midpoint)] over every hop of every trip.

        Running time is departure -> arrival, so dwell is excluded: this is speed
        between stops, not commercial speed.
        """
        out = []
        for t in self.trips_of(route_id):
            s = self.trip_stops[t]
            if not s:
                continue
            if peak_only and not (PEAK[0] <= _secs(s[0][3] or s[0][2]) < PEAK[1]):
                continue
            for a, b in zip(s, s[1:]):
                if a[1] not in self.stops or b[1] not in self.stops:
                    continue
                pa, pb = self.stops[a[1]], self.stops[b[1]]
                dist = haversine_m(pa, pb)
                run = _secs(b[2]) - _secs(a[3])
                if run <= 0 or dist < 50:       # same-stop pairs and zero-time hops
                    continue
                out.append((dist, run, ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)))
        return out

    def speed_profile(self, route_id, centre):
        """(inner_kmh, outer_kmh, n_inner, n_outer) -- median segment speed by distance
        from the city centre. None where there are too few segments to be worth a median."""
        segs = self.segments(route_id)
        inner = [d / r * 3.6 for d, r, m in segs if haversine_m(m, centre) <= INNER_M]
        outer = [d / r * 3.6 for d, r, m in segs if haversine_m(m, centre) > OUTER_M]
        return (statistics.median(inner) if len(inner) >= 20 else None,
                statistics.median(outer) if len(outer) >= 20 else None,
                len(inner), len(outer))

    def mean_stop_spacing_m(self, route_id, centre=None, inner=True):
        segs = self.segments(route_id)
        if centre is not None:
            segs = [s for s in segs
                    if (haversine_m(s[2], centre) <= INNER_M) == inner]
        return statistics.median(d for d, _, _ in segs) if segs else None


def population_near(stop_ids, feed, points, radius_m=WALK_M):
    """Population of precincts whose centroid is within radius_m of any of these stops."""
    coords = [feed.stops[s] for s in stop_ids if s in feed.stops]
    if not coords:
        return 0.0
    # Degree box big enough for radius_m at this latitude, to skip the haversine for
    # the ~99% of precinct/stop pairs that are nowhere near each other.
    dlat = radius_m / 111_320
    dlon = dlat / math.cos(math.radians(51.77))
    total = 0.0
    for pop, lon, lat in points:
        for c in coords:
            if (abs(lon - c[0]) < dlon and abs(lat - c[1]) < dlat
                    and haversine_m((lon, lat), c) <= radius_m):
                total += pop
                break
    return total


def _demo():
    feed = Feed()
    points = population_points()
    centre = weighted_centroid(points)
    assert 19.3 < centre[0] < 19.6 and 51.6 < centre[1] < 51.9, centre
    trams = feed.tram_routes()
    assert trams, "no tram routes with service"
    for rid in trams:
        assert feed.length_km(rid) > 0
        assert feed.stops_of(rid)
    print(f"centre {centre[0]:.5f}, {centre[1]:.5f}; {len(trams)} tram lines; "
          f"{sum(p for p, _, _ in points):.0f} residents in {len(points)} precincts")
    print("self-check ok")


if __name__ == "__main__":
    _demo()
