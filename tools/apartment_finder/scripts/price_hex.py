"""Price layer, step 3: clean transactions (price_clean.py) -> per-hex price per m2 with adaptive reach.

For every hex the smallest circle around its centre (start_radius_m .. max_radius_m) holding at least `hex.min_n` deeds
(and `hex.min_points` distinct locations) gives the value: a distance-weighted median of price per m2. No such circle
-> empty (never 0). Also marks "inhabited" hexes (BDOT10k residential building footprint, config `inhabited`) to report
coverage where people live. A price is kept only for inhabited hexes (the others get it in price_m2_outside, for QGIS checks).
Writes data/price/price_hex.csv (hex_id, price_m2, radius_m, n, n_pts, res_footprint_m2, price_m2_outside) + price_hex.meta.json. System Python (osgeo, numpy).

  py scripts/price_hex.py
"""
import csv
import json
from pathlib import Path

import numpy as np
import yaml
from osgeo import ogr

ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/price.yaml", encoding="utf-8"))
OUT = HERE / "data/price"
H = cfg["hex"]


def wmedian(vals, w):
    o = np.argsort(vals)
    cw = np.cumsum(w[o])
    return float(vals[o][np.searchsorted(cw, cw[-1] / 2)])


def nearest_hex(C, xy, max_d=150.0):
    """Index of the hex containing each point: for a regular hex tiling it is the nearest centre; -1 when farther than max_d."""
    idx = np.empty(len(xy), int)
    for a in range(0, len(xy), 4000):
        d = np.hypot(xy[a:a + 4000, None, 0] - C[None, :, 0], xy[a:a + 4000, None, 1] - C[None, :, 1])
        j = d.argmin(1)
        idx[a:a + 4000] = np.where(d[np.arange(len(j)), j] <= max_d, j, -1)   # circumradius of a 250 m hex is 144 m
    return idx


def main():
    gds = ogr.Open(str(HERE / "data/grid.gpkg"))   # keep datasets referenced while iterating
    ids, C = [], []
    for f in gds.GetLayerByName("hex_grid"):
        c = f.GetGeometryRef().Centroid()
        ids.append(f["hex_id"]); C.append((c.GetX(), c.GetY()))
    o = np.argsort(ids); ids = np.array(ids)[o]; C = np.array(C)[o]

    pds = ogr.Open(str(OUT / "price_clean.gpkg"))
    P, V = [], []
    for f in pds.GetLayer(0):
        g = f.GetGeometryRef(); P.append((g.GetX(), g.GetY())); V.append(f["cena_m2"])
    P = np.array(P); V = np.array(V)
    loc = np.unique(np.round(P).astype(int), axis=0, return_inverse=True)[1].ravel()   # distinct locations (1 m)
    D = np.hypot(C[:, None, 0] - P[None, :, 0], C[:, None, 1] - P[None, :, 1])

    bds = ogr.Open(str(next((HERE / cfg["inhabited"]["bdot_dir"]).glob("*BUBD_A.gpkg"))))
    bxy, bar = [], []
    for f in bds.GetLayer(0):
        if f["FUNKCJAOGOLNABUDYNKU"] == "budynki mieszkalne":
            g = f.GetGeometryRef(); c = g.Centroid(); bxy.append((c.GetX(), c.GetY())); bar.append(g.GetArea())
    bh = nearest_hex(C, np.array(bxy))
    res_fp = np.bincount(bh[bh >= 0], weights=np.array(bar)[bh >= 0], minlength=len(ids))

    radii = list(range(H["start_radius_m"], H["max_radius_m"] + 1, H["radius_step_m"]))
    rows = []
    for k, hid in enumerate(ids):
        row = {"hex_id": int(hid), "price_m2": "", "radius_m": "", "n": "", "n_pts": "", "res_footprint_m2": round(res_fp[k]), "price_m2_outside": ""}
        for r in radii:
            m = D[k] <= r
            if m.sum() >= H["min_n"] and len(set(loc[m])) >= H["min_points"]:
                w = 1 - (1 - H["weight_edge"]) * D[k][m] / r
                row.update(price_m2=round(wmedian(V[m], w)), radius_m=r, n=int(m.sum()), n_pts=len(set(loc[m])))
                break
        if row["price_m2"] != "" and res_fp[k] < cfg["inhabited"]["min_footprint_m2"]:
            row.update(price_m2_outside=row["price_m2"], price_m2="", radius_m="", n="", n_pts="")
        rows.append(row)
    with open(OUT / "price_hex.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    has = np.array([r["price_m2"] != "" for r in rows])
    outside = sum(1 for r in rows if r["price_m2_outside"] != "")
    inh = res_fp >= cfg["inhabited"]["min_footprint_m2"]
    pr = np.array([r["price_m2"] for r in rows if r["price_m2"] != ""], float)
    rad = np.array([r["radius_m"] for r in rows if r["radius_m"] != ""], float)
    meta = {"price_version": cfg["price_version"], "hexes": len(ids), "inhabited_hexes": int(inh.sum()),
            "coverage_all_pct": round(100 * has.mean(), 1), "coverage_inhabited_pct": round(100 * has.sum() / inh.sum(), 1),
            "hexes_with_price": int(has.sum()), "price_hidden_not_inhabited": outside,
            "radius_m_pct": {p: float(np.percentile(rad, p)) for p in (10, 50, 90)},
            "price_m2_pct": {p: float(np.percentile(pr, p)) for p in (10, 25, 50, 75, 90)}, "config": H}
    json.dump(meta, open(OUT / "price_hex.meta.json", "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
