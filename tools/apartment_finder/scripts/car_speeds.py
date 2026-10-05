"""M3: car speeds from bus segments -> OSM copies with maxspeed per time of day.

1. segment slowdown factors from the tidy GTFS-RT (bus only): free-flow time / observed time of the
   same stop-to-stop segment, per time of day, median over days;
2. matched to OSM edges (corridor + bearing), aggregated per way, smoothed by class group + radius;
3. maxspeed = base speed x factor written into a copy of the OSM extract per time of day.

Needs data/car/lodz.osm (osmosis --read-pbf ... --write-xml) and data/car/lodz_drive.osm
(osmosis --tf accept-ways highway=... --used-node). System Python (pandas, shapely, pyproj, scipy).
Outputs: data/car/factors_<tw>.csv, data/car/lodz_car_<tw>.osm (convert to pbf with osmosis),
data/car/car.meta.json.
"""
import csv
import io
import json
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely import STRtree
from shapely.geometry import LineString, Point

HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/car.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE / "config/time_windows.yaml", encoding="utf-8"))["windows"]
M, S, F = cfg["match"], cfg["smoothing"], cfg["factor"]
to2180 = Transformer.from_crs(4326, 2180, always_xy=True)
CAR = HERE / "data/car"


def hm(s):
    return int(s[:2]) * 60 + int(s[3:5])


# ---- 1. segment factors from bus observations ----
def load_obs():
    frames = []
    for day in cfg["days"]:
        z = zipfile.ZipFile(next((HERE / "data/gtfs" / day / "static").glob("*.zip")))
        r = pd.read_csv(z.open("routes.txt"), dtype=str)
        bus = set(r.route_id[r.route_type.astype(int).isin([3, 700, 702, 704])])
        d = pd.read_csv(HERE / ("data/tidy/lodz_tidy_%s.csv.gz" % day), low_memory=False)
        d = d[(d.seg_status == "ok") & d.seg_time_s.notna() & d.route_id.astype(str).isin(bus)]
        d = d[(d.seg_speed_kmh <= M["max_speed_kmh"]) & (d.seg_time_s > 0)]
        t = pd.to_datetime(d.obs_local.astype(str).str.slice(0, 19))
        d = d.assign(minute=t.dt.hour * 60 + t.dt.minute, day=day)
        frames.append(d[["from_stop_id", "stop_id", "seg_time_s", "minute", "day"]])
    obs = pd.concat(frames)
    obs["a"] = obs.from_stop_id.astype(int)
    obs["b"] = obs.stop_id.astype(int)
    return obs


def stop_coords():
    z = zipfile.ZipFile(next((HERE / "data/gtfs" / cfg["days"][-1] / "static").glob("*.zip")))
    s = pd.read_csv(z.open("stops.txt"), dtype=str)
    xs, ys = to2180.transform(s.stop_lon.astype(float).values, s.stop_lat.astype(float).values)
    return {int(i): (x, y) for i, x, y in zip(s.stop_id, xs, ys) if str(i).isdigit()}


def segment_factors(obs):
    ref = obs.groupby(["a", "b"]).seg_time_s.quantile(F["free_flow_percentile"] / 100).rename("ref")
    obs = obs.join(ref, on=["a", "b"])
    out = {}
    for name, w in tw.items():
        lo, hi = hm(w["start"]), hm(w["end"])
        o = obs[(obs.minute >= lo) & (obs.minute < hi)]
        g = o.groupby(["a", "b"]).agg(n=("seg_time_s", "size"), med=("seg_time_s", "median"), ref=("ref", "first"))
        g = g[g.n >= M["min_obs"]]
        g["factor"] = (g.ref / g.med).clip(F["min"], F["max"])
        out[name] = g
    return out


# ---- 2. OSM edges ----
def parse_drive():
    nodes, ways = {}, {}
    for _, el in ET.iterparse(CAR / "lodz_drive.osm", events=("end",)):
        if el.tag == "node":
            nodes[int(el.get("id"))] = (float(el.get("lon")), float(el.get("lat")))
            el.clear()
        elif el.tag == "way":
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            hw = tags.get("highway")
            if hw in cfg["drivable"]:
                ways[int(el.get("id"))] = (hw, tags.get("maxspeed"), [int(n.get("ref")) for n in el.findall("nd")])
            el.clear()
    return nodes, ways


def build_edges(nodes, ways):
    ids = list(nodes)
    xs, ys = to2180.transform([nodes[i][0] for i in ids], [nodes[i][1] for i in ids])
    xy = {i: (x, y) for i, x, y in zip(ids, xs, ys)}
    mid, brg, ln, wid = [], [], [], []
    for w, (_, _, nds) in ways.items():
        for a, b in zip(nds, nds[1:]):
            if a in xy and b in xy:
                (x1, y1), (x2, y2) = xy[a], xy[b]
                mid.append(((x1 + x2) / 2, (y1 + y2) / 2))
                brg.append(math.degrees(math.atan2(x2 - x1, y2 - y1)) % 180)
                ln.append(math.hypot(x2 - x1, y2 - y1))
                wid.append(w)
    return np.array(mid), np.array(brg), np.array(ln), np.array(wid)


def way_factors(seg_f, stops, mid, brg, ln, wid, ways):
    pts = [Point(*p) for p in mid]
    tree = STRtree(pts)
    res = {}
    for name, g in seg_f.items():
        acc = defaultdict(list)  # way -> [(factor, weight)]
        for (a, b), row in g.iterrows():
            if a not in stops or b not in stops:
                continue
            (x1, y1), (x2, y2) = stops[a], stops[b]
            if math.hypot(x2 - x1, y2 - y1) < 20:
                continue
            sb = math.degrees(math.atan2(x2 - x1, y2 - y1)) % 180
            idx = tree.query(LineString([(x1, y1), (x2, y2)]), predicate="dwithin", distance=M["corridor_m"])
            for i in idx:
                d = abs(brg[i] - sb)
                if min(d, 180 - d) <= M["max_angle_deg"]:
                    acc[wid[i]].append((row.factor, ln[i]))
        res[name] = {w: float(np.average([f for f, _ in v], weights=[l for _, l in v])) for w, v in acc.items()}
    return res


def smooth(direct, ways, wmid):
    """Fill ways without data with the median factor of same-group data ways within the radius."""
    group = {w: cfg["class_group"][ways[w][0]] for w in ways}
    out = {}
    for name, d in direct.items():
        filled, src = dict(d), {w: "direct" for w in d}
        for grp in ("major", "minor"):
            have = [w for w in d if group[w] == grp]
            need = [w for w in ways if group[w] == grp and w not in d]
            glob = float(np.median([d[w] for w in have])) if have else 1.0
            if have:
                tr = cKDTree(np.array([wmid[w] for w in have]))
                near = tr.query_ball_point(np.array([wmid[w] for w in need]), S["radius_m"]) if need else []
            for k, w in enumerate(need):
                if have and near[k]:
                    filled[w] = float(np.median([d[have[j]] for j in near[k]]))
                    src[w] = "radius"
                else:
                    filled[w] = glob
                    src[w] = "class"
        out[name] = (filled, src)
    return out


def base_speed(hw, ms):
    if ms:
        m = re.match(r"^\s*(\d+)\s*(mph)?\s*$", ms)
        if m:
            v = float(m.group(1)) * (1.609 if m.group(2) else 1)
            if 5 <= v <= 140:
                return v
    return cfg["default_speed_kmh"][hw]


# ---- 3. write OSM copies ----
def write_copy(name, speeds):
    src, dst = CAR / "lodz.osm", CAR / ("lodz_car_%s.osm" % name)
    way_re = re.compile(r'<way id="(\d+)"')
    cur = None
    with open(src, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8", newline="\n") as fo:
        for line in fi:
            m = way_re.search(line)
            if m:
                cur = int(m.group(1))
            if cur is not None and '<tag k="maxspeed"' in line:
                continue  # replaced below
            if "</way>" in line and cur is not None:
                if cur in speeds:
                    fo.write('    <tag k="maxspeed" v="%d"/>\n' % speeds[cur])
                cur = None
            fo.write(line)


def main():
    obs = load_obs()
    stops = stop_coords()
    seg_f = segment_factors(obs)
    nodes, ways = parse_drive()
    mid, brg, ln, wid = build_edges(nodes, ways)
    wmid = {}
    sums = defaultdict(lambda: [0.0, 0.0, 0.0])
    for (x, y), l, w in zip(mid, ln, wid):
        s = sums[w]
        s[0] += x * l; s[1] += y * l; s[2] += l
    wmid = {w: (s[0] / s[2], s[1] / s[2]) for w, s in sums.items()}
    direct = way_factors(seg_f, stops, mid, brg, ln, wid, ways)
    final = smooth(direct, ways, wmid)
    wlen = {w: s[2] for w, s in sums.items()}
    total = sum(wlen.values())
    meta = {"car_version": cfg["car_version"], "days": cfg["days"], "bus_observations": int(len(obs)),
            "segments_used": {n: int(len(g)) for n, g in seg_f.items()}, "ways": len(ways), "per_window": {}}
    for name, (filled, src) in final.items():
        spd = {w: max(5, round(base_speed(ways[w][0], ways[w][1]) * filled[w])) for w in ways}
        with open(CAR / ("factors_%s.csv" % name), "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh); wr.writerow(["way_id", "highway", "factor", "source", "maxspeed_kmh"])
            for w in ways:
                wr.writerow([w, ways[w][0], round(filled[w], 3), src[w], spd[w]])
        vals = np.array([filled[w] for w in ways]); wl = np.array([wlen[w] for w in ways])
        direct_share = sum(wlen[w] for w in ways if src[w] == "direct") / total
        meta["per_window"][name] = {"direct_length_share": round(direct_share, 3),
                                    "factor_median": round(float(np.median(vals)), 3),
                                    "factor_p10": round(float(np.percentile(vals, 10)), 3),
                                    "length_weighted_mean": round(float(np.average(vals, weights=wl)), 3)}
        write_copy(name, spd)
        print(name, meta["per_window"][name], file=sys.stderr)
    json.dump(meta, open(CAR / "car.meta.json", "w"), indent=1)


if __name__ == "__main__":
    main()
