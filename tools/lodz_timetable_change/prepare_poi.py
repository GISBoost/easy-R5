"""Freeze the destinations: POIs of the chosen categories and the k nearest of each category per origin hex.

    py -I prepare_poi.py

Reads poi_targets_lodz from the lodzkie_na_mapach_2026 base GPKG (local only, 175 MB) and writes two small CSVs under
inputs/ that ARE versioned, so CI can run without the GPKG: poi_dest.csv (R5 destinations) and nearest.csv
(origin hex, category, rank, poi, straight-line distance). Nearest = smallest great-circle distance, never travel time.
"""

import csv
import sqlite3
import struct
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
P = CFG["poi"]
ENVELOPE = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}   # GeoPackage binary header, bytes by envelope indicator
EARTH_R = 6371008.8


def point(blob):
    """lon, lat of a GeoPackage point blob (EPSG:4326, little- or big-endian WKB)."""
    flags = blob[3]
    off = 8 + ENVELOPE[(flags >> 1) & 7]
    end = "<" if blob[off] == 1 else ">"
    return struct.unpack(end + "dd", blob[off + 5: off + 21])


def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def main():
    gpkg = (HERE / P["source_gpkg"]).resolve()
    db = sqlite3.connect(f"file:{gpkg.as_posix()}?mode=ro", uri=True)
    cats = P["categories"]
    cols = ", ".join(cats.values())
    rows = db.execute(f"select poi_id, geom, {cols} from {P['source_layer']}").fetchall()
    pois = {}
    for pid, blob, *flags in rows:
        if any(flags):
            pois[pid] = point(blob) + tuple(int(f or 0) for f in flags)
    ids = sorted(pois)
    with open(HERE / P["pois"], "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "lon", "lat"] + list(cats))
        for i in ids:
            lon, lat, *fl = pois[i]
            w.writerow([i, f"{lon:.7f}", f"{lat:.7f}"] + fl)
    print(f"pois: {len(ids)}", {c: sum(pois[i][2 + k] for i in ids) for k, c in enumerate(cats)})

    origins = list(csv.DictReader(open(HERE / P["origins"], encoding="utf-8")))
    olon = np.array([float(r["lon"]) for r in origins])[:, None]
    olat = np.array([float(r["lat"]) for r in origins])[:, None]
    plon = np.array([pois[i][0] for i in ids])[None, :]
    plat = np.array([pois[i][1] for i in ids])[None, :]
    dist = haversine(olon, olat, plon, plat)
    n = 0
    with open(HERE / P["nearest"], "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["hex_id", "category", "rank", "poi_id", "dist_m"])
        for k, c in enumerate(cats):
            member = np.array([bool(pois[i][2 + k]) for i in ids])
            idx = np.where(member)[0]
            sub = dist[:, idx]
            order = np.argsort(sub, axis=1, kind="stable")[:, : P["k_nearest"]]
            for o, r in enumerate(origins):
                for rank, j in enumerate(order[o], start=1):
                    w.writerow([r["id"], c, rank, ids[idx[j]], round(float(sub[o, j]), 1)])
                    n += 1
    print(f"nearest rows: {n} = {len(origins)} hexes x {len(cats)} categories x {P['k_nearest']}")


if __name__ == "__main__":
    main()
