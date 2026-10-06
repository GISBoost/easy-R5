"""Export the web app's data into <easy>/gdzie-mieszkac-lodz-data, the working copy of the data repo (PRD 8).

  py scripts/export_web.py [--agg data/agg] [--out ../../../gdzie-mieszkac-lodz-data] [--only name,...]

Writes manifest.json, hex.json, layers.json and m/<scenario>.{r,c}.bin. Each matrix is capped
(config/export.yaml: cap_min), quantised (scale_min minutes per unit) and stored one DEFLATE-raw block per
row (r.bin = from a hex) and per column (c.bin = to a hex, i.e. the transposed matrix) behind an offset
table, so the browser can fetch one row/column with an HTTP Range request.

File layout: 'HXM1' | u32 n | u32 scale_min | u32 cap_min | u32 offsets[n+1] | blocks (all big-endian).
Transit scenarios other than a window's base (static, unlimited, no LKA) are stored as uint8 differences
(manifest matrix.base); decode: unit = (base + delta) mod 256.
Input matrices are data/agg/<scenario>.npy (median over the days, uint8, 255 = not reached); with --agg
pointing at a single day's directory of .npz files (pilot) they are read from there instead.
System Python (numpy, shapely, pyproj, yaml).
"""
import argparse
import csv
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
import yaml
from pyproj import Transformer
from shapely import wkb

HERE = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load(open(HERE / "config/export.yaml", encoding="utf-8"))
curves = yaml.safe_load(open(HERE / "config/curves.yaml", encoding="utf-8"))
noise_cfg = yaml.safe_load(open(HERE / "config/noise.yaml", encoding="utf-8"))
tw = yaml.safe_load(open(HERE / "config/time_windows.yaml", encoding="utf-8"))
grid_meta = json.load(open(HERE / "data/grid.meta.json"))
to4326 = Transformer.from_crs(2180, 4326, always_xy=True)


def read_gpkg(layer):
    import sqlite3
    c = sqlite3.connect(HERE / "data/grid.gpkg")
    out = {}
    for hid, g in c.execute("select hex_id, geom from %s" % layer):
        env = (g[3] >> 1) & 7
        off = 8 + [0, 32, 48, 48, 64][env]
        out[hid] = wkb.loads(bytes(g[off:]))
    return out


def export_hex(out):
    cents, polys = read_gpkg("hex_centroids"), read_gpkg("hex_grid")
    n = len(cents)
    assert sorted(cents) == list(range(n)), "hex_id must be 0..n-1"
    c, p = [], []
    for i in range(n):
        x, y = to4326.transform(cents[i].x, cents[i].y)
        c.append([round(x, 5), round(y, 5)])
        ring = list(polys[i].geoms[0].exterior.coords)[:-1] if polys[i].geom_type == "MultiPolygon" else list(polys[i].exterior.coords)[:-1]
        flat = []
        for px, py in ring:
            lx, ly = to4326.transform(px, py)
            flat += [round(lx, 5), round(ly, 5)]
        p.append(flat)
    json.dump({"c": c, "p": p}, open(out / "hex.json", "w"), separators=(",", ":"))
    lons, lats = [a[0] for a in c], [a[1] for a in c]
    return n, [[min(lats), min(lons)], [max(lats), max(lons)]]


def read_csv_cols(path):
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    cols = {k: [None if r[k] == "" else float(r[k]) for r in rows] for k in rows[0] if k != "hex_id"}
    assert [int(r["hex_id"]) for r in rows] == list(range(len(rows)))
    return cols


def export_layers(out):
    cols = read_csv_cols(HERE / "data/static/static_layers.csv")
    nz = HERE / "data/noise/noise_layers.csv"
    if nz.exists():
        cols.update(read_csv_cols(nz))
    cv = HERE / "data/canopy/canopy_hex.csv"
    if cv.exists():
        c = read_csv_cols(cv)
        assert all(v is not None and 0 <= v <= 1 for v in c["canopy_hex"]) and min(c["cover_hex"]) >= 0.99, "canopy layer incomplete"
        cols["canopy"] = [round(v, 3) for v in c["canopy_hex"]]   # share of the hex area under canopy (canopy-v2), 0..1
    json.dump(cols, open(out / "layers.json", "w"), separators=(",", ":"))
    return sorted(cols)


def canopy_manifest(out):
    """Canopy block of the manifest: method, data year and the optional preview image (canopy_overlay.py writes it)."""
    mp = HERE / "data/canopy/canopy_hex.meta.json"
    if not mp.exists():
        return None
    c = json.load(open(mp))
    cc = yaml.safe_load(open(HERE / "config/canopy.yaml", encoding="utf-8"))
    ov = out / "canopy_overlay.json"
    return {"version": c["canopy_version"], "year": c["year"], "height_m": c["height_m"], "scan_date": "2021-04",
            "overlay": json.load(open(ov)) if ov.exists() and (out / "canopy.webp").exists() else None}


def export_context(out):
    """Own vector basemap (no third-party tiles): major roads, tram/rail, rivers, district names, from the OSM extract."""
    import xml.etree.ElementTree as ET
    ctx = {"road": [], "tram": [], "rail": [], "water": [], "places": []}
    roads_ok = {"motorway", "trunk", "primary", "secondary", "tertiary"}
    for fname in ("lodz_drive.osm", "context_lines.osm"):
        nodes, ways = {}, []
        for _, el in ET.iterparse(HERE / "data/car" / fname, events=("end",)):
            if el.tag == "node":
                nodes[el.get("id")] = (float(el.get("lon")), float(el.get("lat")))
                el.clear()
            elif el.tag == "way":
                tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                kind = None
                if tags.get("highway") in roads_ok:
                    kind = "road"
                elif tags.get("railway") == "tram":
                    kind = "tram"
                elif tags.get("railway") == "rail":
                    kind = "rail"
                elif tags.get("waterway") in ("river", "canal"):
                    kind = "water"
                if kind:
                    ways.append((kind, [n.get("ref") for n in el.findall("nd")]))
                el.clear()
        for kind, refs in ways:
            pts = [nodes[r] for r in refs if r in nodes]
            if len(pts) >= 2:
                flat = []
                for x, y in pts:
                    flat += [round(x, 5), round(y, 5)]
                ctx[kind].append(flat)
    for _, el in ET.iterparse(HERE / "data/car/context_places.osm", events=("end",)):
        if el.tag == "node":
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            if tags.get("name") and tags.get("place") in ("suburb", "quarter", "neighbourhood", "city", "town"):
                ctx["places"].append([tags["name"], tags["place"], round(float(el.get("lon")), 5), round(float(el.get("lat")), 5)])
            el.clear()
    gj = HERE / "data/static/green.geojson"
    ctx["green"] = json.load(open(gj, encoding="utf-8")) if gj.exists() else None
    json.dump(ctx, open(out / "context.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return {k: (len(v) if isinstance(v, list) else bool(v)) for k, v in ctx.items()}


def encode(m, n):
    scale, cap = CFG["scale_min"], CFG["cap_min"]
    u = np.where((m == 255) | (m > cap), 255, np.round(m / scale)).astype(np.uint8)
    return u


def write_hxm(path, u):
    n = u.shape[0]
    blocks, offs = [], [0]
    for i in range(n):
        co = zlib.compressobj(9, zlib.DEFLATED, -15)  # raw deflate for DecompressionStream("deflate-raw")
        b = co.compress(np.ascontiguousarray(u[i]).tobytes()) + co.flush()
        blocks.append(b)
        offs.append(offs[-1] + len(b))
    with open(path, "wb") as fh:
        fh.write(struct.pack(">4sIII", b"HXM1", n, CFG["scale_min"], CFG["cap_min"]))
        fh.write(struct.pack(">%dI" % (n + 1), *offs))
        for b in blocks:
            fh.write(b)
    return offs[-1]


ALIAS = {"walk": "morning_walk", "bike": "morning_bike"}   # window-free modes are computed once, under the morning name


def load_matrix(agg, name):
    name = ALIAS.get(name, name)
    f = agg / (name + ".npy")
    if f.exists():
        return np.load(f)
    return np.load(agg / (name + ".npz"))["p50"]


def base_of(name):
    """Transit scenarios are stored as differences against the window's scheduled / unlimited / no-LKA matrix."""
    parts = name.split("_")
    if len(parts) == 2 and parts[1] == "car" and parts[0] != "morning":
        return "morning_car"                         # car differs between windows only slightly: store as a difference
    if len(parts) == 4 and parts[1] in ("static", "p50", "p85"):
        return "%s_static_unlimited_nolka" % parts[0]
    return None


def scenario_names():
    names = []
    for w in tw["windows"]:
        for t in ("static", "p50", "p85"):
            for r in ("unlimited", "max1transfer"):
                for l in ("nolka", "lka"):
                    names.append("%s_%s_%s_%s" % (w, t, r, l))
        names.append("%s_car" % w)
    return names + ["walk", "bike"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agg", default=str(HERE / "data/agg"))
    ap.add_argument("--out", default=str((HERE / "../../../gdzie-mieszkac-lodz-data").resolve()))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    out, agg = Path(a.out), Path(a.agg)
    (out / "m").mkdir(parents=True, exist_ok=True)
    n, bounds = export_hex(out)
    cols = export_layers(out)
    if not CFG["basemap"]["url"]:
        print("context:", export_context(out), file=sys.stderr)
    assert n == grid_meta["hexes"]
    files, total, bases = {}, 0, {}
    names = [x for x in a.only.split(",") if x] or scenario_names()
    for name in names:
        try:
            m = load_matrix(agg, name)
        except FileNotFoundError:
            continue
        assert m.shape == (n, n)
        # day-level matrices of the pilot may be named with the window prefix; "walk"/"bike" are window-free
        u = encode(m, n)
        bn = base_of(name)
        if bn and bn != name:
            bm = encode(load_matrix(agg, bn), n)
            u = ((u.astype(np.int16) - bm.astype(np.int16)) % 256).astype(np.uint8)  # lossless: e = (base + d) mod 256
            bases[name] = bn
        sz = write_hxm(out / "m" / (name + ".r.bin"), u) + write_hxm(out / "m" / (name + ".c.bin"), np.ascontiguousarray(u.T))
        files[name] = sz
        total += sz
        print(name, round(sz / 1e6, 2), "MB", file=sys.stderr)
    # the manifest describes everything present in out/m, not only what this run (e.g. --only) wrote
    present = sorted(f.name[:-6] for f in (out / "m").glob("*.r.bin"))
    bases = {n: base_of(n) for n in present if base_of(n) and base_of(n) != n}
    manifest = {
        "method_version": "apt-v1 (grid %s, layers %s, noise %s, canopy %s, car %s, curves %s)" % (
            grid_meta["grid_version"], "static-v1", noise_cfg["layers_version"], (canopy_manifest(out) or {}).get("version", "none"),
            "car-v1", curves["curves_version"]),
        "canopy": canopy_manifest(out),
        "n": n, "bounds": bounds,
        "windows": {k: {"start": v["start"], "end": v["end"]} for k, v in tw["windows"].items()},
        "default_dir": {k: ("to" if v == "to_target" else "from") for k, v in tw["default_direction"].items()},
        "curves": {k: v for k, v in curves.items() if k != "curves_version"},
        "noise_steps": noise_cfg["thresholds"],
        "matrix": {"scale": CFG["scale_min"], "cap": CFG["cap_min"], "scenarios": present, "base": bases},
        "layer_columns": cols,
        "basemap": CFG["basemap"],
        "days": yaml.safe_load(open(HERE / "config/days.yaml", encoding="utf-8"))["days"],
    }
    json.dump(manifest, open(out / "manifest.json", "w"), indent=1, ensure_ascii=False)
    print("matrix files: %d, %.1f MB total" % (len(files), total / 1e6), file=sys.stderr)


if __name__ == "__main__":
    main()
