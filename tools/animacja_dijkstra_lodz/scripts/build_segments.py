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
import re
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from easy_r5.core.gtfs_calendar import _active_on, _exceptions, _services  # noqa: E402

TRAM = 0
MIN_M = 12.0

# R* = zjazdy do zajezdni (R11, R16, …). P* / oP* = przewóz pracowników.
# F/G/H/W = linie zakładowe / zajezdniowe (F1, G1, G2, H, W). T gdy wróci w feedzie.
# Z* zostaje: to bieżąca komunikacja zastępcza.
def keep_line(name):
    if not name:
        return False
    if name in ("T", "H", "W"):
        return False
    if re.fullmatch(r"R\d+", name):
        return False
    if re.fullmatch(r"o?P\d+", name, re.I):
        return False
    if re.fullmatch(r"[FG]\d+", name):
        return False
    return True


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


def shape_median(coords):
    if len(coords) < 2:
        return None
    return statistics.median(hav_m(coords[i - 1], coords[i]) for i in range(1, len(coords)))


def split_spikes(piece, med):
    """Drop one edge that jumps across a hole in an otherwise dense shape.

    ponytail: threshold is max(250m, 8x that shape's median edge). A uniformly
    coarse shape stays intact. The hole is deleted, not rebuilt from other shapes.
    """
    if med is None or len(piece) < 2:
        return [piece] if len(piece) >= 2 else []
    thr = max(250.0, 8.0 * med)
    parts = []
    cur = [piece[0]]
    for p in piece[1:]:
        if hav_m(cur[-1], p) > thr:
            if len(cur) >= 2:
                parts.append(cur)
            cur = [p]
        else:
            cur.append(p)
    if len(cur) >= 2:
        parts.append(cur)
    return parts


SNAP_M = 100.0


def other_tags(raw):
    out = {}
    if not raw:
        return out
    for key, val in re.findall(r'"((?:\\.|[^"\\])*)"=>"((?:\\.|[^"\\])*)"', raw):
        out[key.replace('\\"', '"')] = val.replace('\\"', '"').replace("\\\\", "\\")
    return out


def closest_measure(coords, dist, pt, max_m):
    best_d, best_m = max_m, None
    cos = math.cos(math.radians(pt[1]))
    for i in range(1, len(coords)):
        ax, ay = coords[i - 1]
        bx, by = coords[i]
        dx = math.radians(bx - ax) * 6371000 * cos
        dy = math.radians(by - ay) * 6371000
        px = math.radians(pt[0] - ax) * 6371000 * cos
        py = math.radians(pt[1] - ay) * 6371000
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 <= 0 else max(0.0, min(1.0, (px * dx + py * dy) / l2))
        d = math.hypot(px - dx * t, py - dy * t)
        if d < best_d:
            best_d = d
            best_m = dist[i - 1] + (dist[i] - dist[i - 1]) * t
    return best_m


def chain_lines(parts, tol_m=40.0):
    """Join a route's pieces where the ways almost meet.

    ponytail: greedy endpoint join. A branch that does not meet within tol_m stays a separate line.
    """
    unused = [list(p) for p in parts if len(p) >= 2]
    out = []
    while unused:
        cur = unused.pop(0)
        grew = True
        while grew:
            grew = False
            for i, other in enumerate(unused):
                if hav_m(cur[-1], other[0]) <= tol_m:
                    cur.extend(other[1:])
                elif hav_m(cur[-1], other[-1]) <= tol_m:
                    cur.extend(reversed(other[:-1] if len(other) > 1 else other))
                elif hav_m(cur[0], other[-1]) <= tol_m:
                    cur = other[:-1] + cur
                elif hav_m(cur[0], other[0]) <= tol_m:
                    cur = list(reversed(other[1:])) + cur
                else:
                    continue
                unused.pop(i)
                grew = True
                break
        if len(cur) >= 2:
            out.append(cur)
    return out


def osm_lines(pbf):
    from osgeo import gdal, ogr
    gdal.SetConfigOption("OGR_INTERLEAVED_READING", "YES")
    ds = ogr.Open(str(pbf))
    if ds is None:
        raise SystemExit("cannot open %s" % pbf)
    layers = [ds.GetLayerByIndex(i) for i in range(ds.GetLayerCount())]
    found = defaultdict(list)

    def take(feat):
        tags = other_tags(feat.GetField("other_tags"))
        kind = tags.get("route")
        ref = (tags.get("ref") or "").strip()
        if kind not in ("tram", "bus") or not ref or ";" in ref:
            return
        geom = feat.GetGeometryRef()
        if geom is None:
            return
        n = geom.GetGeometryCount()
        geoms = [geom.GetGeometryRef(i) for i in range(n)] if n else [geom]
        parts = []
        for g in geoms:
            coords = [(g.GetPoint(i)[0], g.GetPoint(i)[1]) for i in range(g.GetPointCount())]
            if len(coords) >= 2:
                parts.append(coords)
        for coords in chain_lines(parts):
            found[(kind, ref)].append((coords, cum_m(coords)))

    # ponytail: GDAL stops a single-layer scan once the points layer overflows. Read every layer in turn.
    while True:
        progressed = False
        for layer in layers:
            feat = layer.GetNextFeature()
            while feat is not None:
                progressed = True
                if layer.GetName() == "multilinestrings":
                    take(feat)
                feat = layer.GetNextFeature()
        if not progressed:
            break
    return found


def osm_piece(lines, a_ll, b_ll):
    straight = hav_m(a_ll, b_ll)
    best = None
    for coords, dist in lines:
        ma = closest_measure(coords, dist, a_ll, SNAP_M)
        mb = closest_measure(coords, dist, b_ll, SNAP_M)
        if ma is None or mb is None or abs(mb - ma) < 1:
            continue
        along = abs(mb - ma)
        if along > max(straight * 4, straight + 800):
            continue
        rank = abs(along - straight)
        if best is None or rank < best[0]:
            best = (rank, coords, dist, ma, mb)
    if best is None:
        return None
    _rank, coords, dist, ma, mb = best
    return slice_dist(coords, dist, ma, mb)


def _self_check():
    lat = 51.76
    dense = [(19.40 + i * 0.0003, lat) for i in range(8)]
    jump = dense + [(dense[-1][0] + 0.03, lat)]
    parts = split_spikes(jump, 20.0)
    assert parts == [dense], parts
    coarse = [(19.40 + i * 0.008, lat) for i in range(5)]
    assert split_spikes(coarse, 550.0) == [coarse]
    assert split_spikes([coarse[0], coarse[-1]], None) == [[coarse[0], coarse[-1]]]
    assert other_tags('"ref"=>"10","route"=>"tram"')["route"] == "tram"
    line = [(19.40, 51.76), (19.42, 51.76)]
    got = closest_measure(line, cum_m(line), (19.41, 51.7603), 80)
    assert got is not None and 600 < got < 900, got
    joined = chain_lines([[(19.40, 51.76), (19.41, 51.76)], [(19.41005, 51.76), (19.42, 51.76)]])
    assert len(joined) == 1 and joined[0][-1][0] == 19.42, joined
    assert keep_line("10A") and keep_line("6") and keep_line("Z13") and keep_line("N2")
    assert not keep_line("T") and not keep_line("R11") and not keep_line("R16")
    assert not keep_line("P1") and not keep_line("oP6")
    assert not keep_line("F1") and not keep_line("G1") and not keep_line("G2")
    assert not keep_line("H") and not keep_line("W")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--gtfs", required=True)
    ap.add_argument("--out", required=True, help="directory for stops, destinations, segments.geojson")
    ap.add_argument("--osm", help="OSM PBF; route ref fills a stop pair, GTFS shape stays where it does not")
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
            routes[row["route_id"].strip()] = (rt, row.get("route_short_name", "").strip())
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
        rt, short = routes.get(route_id, (3, ""))
        dists = tuple(s[2] for s in seq)
        names = {short} if keep_line(short) else set()
        prev = patterns.get(key)
        if prev is None:
            patterns[key] = [rt, dists, names]
        else:
            if rt == TRAM:
                prev[0] = TRAM
            prev[2] |= names

    osm = osm_lines(a.osm) if a.osm else {}
    used = []
    seg = {}  # (a, b) -> (parts, mode, npts, refs)
    n_shape = n_proj = n_straight = n_osm = 0
    for (shape_id, stop_ids), (rt, dists, refs) in patterns.items():
        for s in stop_ids:
            if s not in stops:
                break
        else:
            mode = "tram" if rt == TRAM else "bus"
            refs = {n for n in refs if keep_line(n)}
            if not refs:
                used.extend(stop_ids)
                continue
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
            med = None if kind == "straight" else shape_median(coords)
            for i in range(len(stop_ids) - 1):
                a, b = stop_ids[i], stop_ids[i + 1]
                if a == b:
                    continue
                want = "tram" if mode == "tram" else "bus"
                lines = []
                for ref in refs:
                    lines.extend(osm.get((want, ref), ()))
                osm_part = osm_piece(lines, stops[a][:2], stops[b][:2]) if lines else None
                if osm_part and len(osm_part) >= 2:
                    parts = [osm_part]
                    n_osm += 1
                else:
                    if kind == "straight":
                        piece = [stops[a][:2], stops[b][:2]]
                    else:
                        piece = slice_dist(coords, along, stop_d[i], stop_d[i + 1])
                    if len(piece) < 2:
                        piece = [stops[a][:2], stops[b][:2]]
                    parts = []
                    for part in split_spikes(piece, med):
                        # A two-point chord of several kilometres is a missing shape, not a road.
                        if len(part) <= 2 and hav_m(part[0], part[-1]) > 2000:
                            continue
                        parts.append(part)
                if not parts:
                    continue
                npts = sum(len(part) for part in parts)
                key = (a, b)
                prev = seg.get(key)
                names = set(refs)
                if prev is not None:
                    names |= prev[3]
                if prev is None or npts > prev[2] or (mode == "tram" and prev[1] != "tram"):
                    keep_mode = "tram" if (prev and prev[1] == "tram") or mode == "tram" else mode
                    seg[key] = (parts, keep_mode, npts, names)
                else:
                    seg[key] = (prev[0], prev[1], prev[2], names)
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
    fid = 0
    for (stop_a, stop_b), (parts, mode, _npts, names) in sorted(seg.items()):
        line = ", ".join(sorted(n for n in names if n))
        for part in parts:
            features.append({
                "type": "Feature",
                "id": fid,
                "properties": {"to": index[stop_b], "mode": mode, "line": line},
                "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in part]},
            })
            fid += 1
    geo = {"type": "FeatureCollection", "features": features}
    with open(out / "segments.geojson", "w", encoding="utf-8") as fh:
        json.dump(geo, fh, separators=(",", ":"))

    print("day %s active_services %d trips %d / %d patterns %d" % (day.isoformat(), len(active), len(trips), n_trips, len(patterns)))
    print("stops %d segments %d shape %d projected %d straight %d osm %d" % (len(order), len(features), n_shape, n_proj, n_straight, n_osm))
    print("wrote %s" % out)


if __name__ == "__main__":
    _self_check()
    main()
