"""GTFS shapes for one service day -> stop list and drawable A->B segments.

One segment is the shape piece from stop A to the next stop B. The web map
colours it with R5's P50 minute of stop B. Overlapping patterns that share
the same stop pair keep a single geometry.

    py scripts/build_segments.py --day 2026-10-06 --gtfs ../data/lodz_realized_2026-10-06_p50.zip
"""
import argparse
import csv
import datetime
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from easy_r5.core.gtfs_calendar import _active_on, _exceptions, _services  # noqa: E402

TRAM = 0
MIN_M = 12.0


def rows(zf, name):
    with zf.open(name) as fh:
        text = (line.decode("utf-8-sig") for line in fh)
        yield from csv.DictReader(text)


def hav_m(a, b):
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def decimate(coords):
    if len(coords) < 3:
        return coords
    out = [coords[0]]
    for p in coords[1:-1]:
        if hav_m(out[-1], p) >= MIN_M:
            out.append(p)
    if hav_m(out[-1], coords[-1]) < 1.0 and len(out) > 1:
        out[-1] = coords[-1]
    else:
        out.append(coords[-1])
    return out


def at_dist(coords, dist, d):
    if d <= dist[0]:
        return coords[0]
    if d >= dist[-1]:
        return coords[-1]
    lo, hi = 0, len(dist) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if dist[mid] <= d:
            lo = mid
        else:
            hi = mid
    span = dist[hi] - dist[lo]
    t = 0.0 if span <= 0 else (d - dist[lo]) / span
    a, b = coords[lo], coords[hi]
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def slice_dist(coords, dist, d0, d1):
    if d1 < d0:
        d0, d1 = d1, d0
    if d1 - d0 < 1.0:
        p = at_dist(coords, dist, d0)
        return [p, at_dist(coords, dist, d1)]
    out = [at_dist(coords, dist, d0)]
    for i in range(1, len(coords) - 1):
        if d0 < dist[i] < d1:
            out.append(coords[i])
    out.append(at_dist(coords, dist, d1))
    cleaned = [out[0]]
    for p in out[1:]:
        if hav_m(cleaned[-1], p) >= 1.0:
            cleaned.append(p)
    return decimate(cleaned)


def cum_m(coords):
    dist = [0.0]
    for i in range(1, len(coords)):
        dist.append(dist[-1] + hav_m(coords[i - 1], coords[i]))
    return dist


def project(coords, dist, stop_ll):
    """Monotonic nearest-vertex distances along the shape."""
    prev = 0
    out = []
    for ll in stop_ll:
        best_i, best_d = prev, 1e18
        for i in range(prev, len(coords)):
            d = hav_m(coords[i], ll)
            if d < best_d:
                best_d, best_i = d, i
        out.append(dist[best_i])
        prev = best_i
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--gtfs", required=True)
    ap.add_argument("--out", required=True, help="directory for stops, destinations, segments.geojson")
    a = ap.parse_args()
    day = datetime.date.fromisoformat(a.day)
    gtfs = Path(a.gtfs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(gtfs) as zf:
        services = _services(zf)
        exceptions = _exceptions(zf)
        active = set()
        stops = {}
        for row in rows(zf, "stops.txt"):
            sid = row["stop_id"].strip()
            if not sid:
                continue
            stops[sid] = (float(row["stop_lon"]), float(row["stop_lat"]), row.get("stop_name", "").strip())
        routes = {}
        for row in rows(zf, "routes.txt"):
            try:
                rt = int(row.get("route_type") or 3)
            except ValueError:
                rt = 3
            routes[row["route_id"].strip()] = rt
        trips = {}
        n_trips = 0
        for row in rows(zf, "trips.txt"):
            n_trips += 1
            sid = row["service_id"].strip()
            if not _active_on(sid, day, services, exceptions):
                continue
            active.add(sid)
            trips[row["trip_id"].strip()] = (row["route_id"].strip(), row.get("shape_id", "").strip())
        shapes = defaultdict(list)
        for row in rows(zf, "shapes.txt"):
            sid = row["shape_id"].strip()
            dist = row.get("shape_dist_traveled", "").strip()
            shapes[sid].append((
                int(float(row["shape_pt_sequence"])),
                float(row["shape_pt_lon"]),
                float(row["shape_pt_lat"]),
                float(dist) if dist else None,
            ))
        by_trip = defaultdict(list)
        for row in rows(zf, "stop_times.txt"):
            tid = row["trip_id"].strip()
            if tid not in trips:
                continue
            dist = row.get("shape_dist_traveled", "").strip()
            by_trip[tid].append((
                int(float(row["stop_sequence"])),
                row["stop_id"].strip(),
                float(dist) if dist else None,
            ))

    if not trips:
        raise SystemExit("no active trips on %s" % a.day)
    for sid in shapes:
        shapes[sid].sort(key=lambda p: p[0])

    # One geometry build per (shape, stop sequence).
    patterns = {}
    for tid, (route_id, shape_id) in trips.items():
        seq = sorted(by_trip.get(tid) or [])
        if len(seq) < 2:
            continue
        key = (shape_id, tuple(s[1] for s in seq))
        rt = routes.get(route_id, 3)
        dists = tuple(s[2] for s in seq)
        prev = patterns.get(key)
        if prev is None:
            patterns[key] = [rt, dists]
        elif rt == TRAM:
            prev[0] = TRAM

    used = []
    seg = {}  # (a, b) -> (coords, mode, npts)
    n_shape = n_proj = n_straight = 0
    for (shape_id, stop_ids), (rt, dists) in patterns.items():
        for s in stop_ids:
            if s not in stops:
                break
        else:
            mode = "tram" if rt == TRAM else "bus"
            raw = shapes.get(shape_id) or []
            coords = [(p[1], p[2]) for p in raw]
            shape_dist = [p[3] for p in raw]
            have_shape_dist = bool(coords) and all(d is not None for d in shape_dist) and all(d is not None for d in dists)
            if have_shape_dist:
                along = shape_dist
                stop_d = list(dists)
                kind = "shape"
            elif len(coords) >= 2:
                along = cum_m(coords)
                stop_d = project(coords, along, [stops[s][:2] for s in stop_ids])
                kind = "proj"
            else:
                along = None
                kind = "straight"
            for i in range(len(stop_ids) - 1):
                a, b = stop_ids[i], stop_ids[i + 1]
                if a == b:
                    continue
                if kind == "straight":
                    piece = [stops[a][:2], stops[b][:2]]
                else:
                    piece = slice_dist(coords, along, stop_d[i], stop_d[i + 1])
                if len(piece) < 2:
                    piece = [stops[a][:2], stops[b][:2]]
                # A two-point chord of several kilometres is a missing shape, not a road.
                if len(piece) <= 2 and hav_m(piece[0], piece[-1]) > 2000:
                    continue
                key = (a, b)
                prev = seg.get(key)
                if prev is None or len(piece) > prev[2] or (mode == "tram" and prev[1] != "tram"):
                    keep_mode = "tram" if (prev and prev[1] == "tram") or mode == "tram" else mode
                    seg[key] = (piece, keep_mode, len(piece))
            if kind == "shape":
                n_shape += 1
            elif kind == "proj":
                n_proj += 1
            else:
                n_straight += 1
            used.extend(stop_ids)

    order = sorted(set(used))
    index = {sid: i for i, sid in enumerate(order)}
    with open(out / "stops.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "stop_id", "name", "lon", "lat"])
        for sid in order:
            lon, lat, name = stops[sid]
            w.writerow([index[sid], sid, name, "%.6f" % lon, "%.6f" % lat])
    with open(out / "destinations.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "lon", "lat"])
        for sid in order:
            lon, lat, _name = stops[sid]
            w.writerow([index[sid], "%.6f" % lon, "%.6f" % lat])

    features = []
    for n, ((stop_a, stop_b), (piece, mode, _npts)) in enumerate(sorted(seg.items())):
        features.append({
            "type": "Feature",
            "id": n,
            "properties": {"to": index[stop_b], "mode": mode},
            "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in piece]},
        })
    geo = {"type": "FeatureCollection", "features": features}
    with open(out / "segments.geojson", "w", encoding="utf-8") as fh:
        json.dump(geo, fh, separators=(",", ":"))

    print("day %s active_services %d trips %d / %d patterns %d" % (day.isoformat(), len(active), len(trips), n_trips, len(patterns)))
    print("stops %d segments %d shape %d projected %d straight %d" % (len(order), len(features), n_shape, n_proj, n_straight))
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
