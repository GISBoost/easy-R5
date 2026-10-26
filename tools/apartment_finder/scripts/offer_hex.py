"""Offer layer, step 2: investments (offer_fetch.py) -> per-hex asking price per m2 with adaptive reach.

Same idea as price_hex.py, counted in investments: for every hex the smallest circle around its centre
(start_radius_m .. max_radius_m) holding at least `hex.min_n` investments from `hex.min_developers` developers gives a
distance-weighted median of the investments' mean asking price per m2 (the service's mean over active offers). No such
circle -> empty (never 0). Kept only for inhabited hexes, taken from price_hex.csv (res_footprint_m2), so run price_hex.py first.
Writes data/offer/offer_hex.csv (hex_id, offer_m2, radius_m, n, n_dev), offer_hex.meta.json and investments.json (the kept
investments, for the map's point layer). System Python (osgeo, numpy, pyproj).

  py scripts/offer_hex.py
"""
import csv
import json
from pathlib import Path

import numpy as np
import yaml
from osgeo import ogr
from pyproj import Transformer

ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/offer.yaml", encoding="utf-8"))
min_fp = yaml.safe_load(open(HERE / "config/price.yaml", encoding="utf-8"))["inhabited"]["min_footprint_m2"]
OUT = HERE / "data/offer"
H, F = cfg["hex"], cfg["filter"]


def wmedian(vals, w):
    o = np.argsort(vals)
    cw = np.cumsum(w[o])
    return float(vals[o][np.searchsorted(cw, cw[-1] / 2)])


def main():
    raw = json.load(open(OUT / "investments_raw.json", encoding="utf-8"))
    items = raw["result"]["items"]
    keep = [i for i in items if i.get("lat") and i.get("lng") and i.get("offers_active") and i.get("avg_price_per_m2")
            and F["avg_area_m2"][0] <= (i.get("avg_area_m2") or 0) <= F["avg_area_m2"][1]
            and F["price_m2"][0] <= i["avg_price_per_m2"] <= F["price_m2"][1]]
    to2180 = Transformer.from_crs(4326, 2180, always_xy=True)
    P = np.array([to2180.transform(i["lng"], i["lat"]) for i in keep])
    V = np.array([i["avg_price_per_m2"] for i in keep])
    dev = np.unique([i.get("developer_slug") or i["investment_slug"] for i in keep], return_inverse=True)[1].ravel()

    gds = ogr.Open(str(HERE / "data/grid.gpkg"))   # keep the dataset referenced while iterating
    ids, C = [], []
    for f in gds.GetLayerByName("hex_grid"):
        c = f.GetGeometryRef().Centroid()
        ids.append(f["hex_id"]); C.append((c.GetX(), c.GetY()))
    o = np.argsort(ids); ids = np.array(ids)[o]; C = np.array(C)[o]
    with open(HERE / "data/price/price_hex.csv", encoding="utf-8") as fh:
        fp = {int(r["hex_id"]): float(r["res_footprint_m2"]) for r in csv.DictReader(fh)}
    inh = np.array([fp[int(h)] >= min_fp for h in ids])
    D = np.hypot(C[:, None, 0] - P[None, :, 0], C[:, None, 1] - P[None, :, 1])

    radii = list(range(H["start_radius_m"], H["max_radius_m"] + 1, H["radius_step_m"]))
    rows = []
    for k, hid in enumerate(ids):
        row = {"hex_id": int(hid), "offer_m2": "", "radius_m": "", "n": "", "n_dev": ""}
        if inh[k]:
            for r in radii:
                m = D[k] <= r
                if m.sum() >= H["min_n"] and len(set(dev[m])) >= H["min_developers"]:
                    w = 1 - (1 - H["weight_edge"]) * D[k][m] / r
                    row.update(offer_m2=round(wmedian(V[m], w)), radius_m=r, n=int(m.sum()), n_dev=len(set(dev[m])))
                    break
        rows.append(row)
    with open(OUT / "offer_hex.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    pts = [{"lat": round(i["lat"], 5), "lng": round(i["lng"], 5), "name": i["name"], "developer": i.get("developer_name"),
            "district": i.get("district"), "street": i.get("street"), "m2": round(i["avg_price_per_m2"]), "area": i.get("avg_area_m2"),
            "offers": i["offers_active"], "url": i.get("investment_url")} for i in keep]
    json.dump(pts, open(OUT / "investments.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    has = np.array([r["offer_m2"] != "" for r in rows])
    pr = np.array([r["offer_m2"] for r in rows if r["offer_m2"] != ""], float)
    rad = np.array([r["radius_m"] for r in rows if r["radius_m"] != ""], float)
    meta = {"offer_version": cfg["offer_version"], "fetched": raw["fetched"], "investments_all": len(items), "investments_kept": len(keep),
            "developers": int(dev.max()) + 1, "offers_active": int(sum(i["offers_active"] for i in keep)),
            "hexes": len(ids), "inhabited_hexes": int(inh.sum()), "hexes_with_offer": int(has.sum()),
            "coverage_inhabited_pct": round(100 * has.sum() / inh.sum(), 1),
            "radius_m_pct": {p: float(np.percentile(rad, p)) for p in (10, 50, 90)},
            "offer_m2_pct": {p: float(np.percentile(pr, p)) for p in (10, 25, 50, 75, 80, 90)}, "config": H, "filter": F}
    json.dump(meta, open(OUT / "offer_hex.meta.json", "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
