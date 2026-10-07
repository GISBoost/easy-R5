"""Price layer, step 3: clean transactions (price_clean.py) -> per-hex median price per m2.

Own-hex median (n, price_m2) and, as a denser alternative, the median over the hex and its 6 neighbours
(n_ring, price_m2_ring). A value exists only with at least `hex.min_n` / `hex.ring_min_n` deeds, otherwise empty.
Writes data/price/price_hex.csv + price_hex.meta.json (coverage for several thresholds). System Python (osgeo).

  py scripts/price_hex.py
"""
import csv
import json
import math
from pathlib import Path
from statistics import median

import yaml
from osgeo import ogr

ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/price.yaml", encoding="utf-8"))
OUT = HERE / "data/price"


def main():
    gds = ogr.Open(str(HERE / "data/grid.gpkg"))   # keep the dataset referenced while iterating
    glyr = gds.GetLayerByName("hex_grid")
    hexes = {}
    for f in glyr:
        g = f.GetGeometryRef()
        c = g.Centroid()
        hexes[f["hex_id"]] = (c.GetX(), c.GetY(), g.Clone())
    ids = sorted(hexes)
    pds = ogr.Open(str(OUT / "price_clean.gpkg"))
    plyr = pds.GetLayer(0)
    vals = {i: [] for i in ids}
    outside = 0
    for p in plyr:
        pt = p.GetGeometryRef()
        glyr.SetSpatialFilter(pt)
        hit = [f["hex_id"] for f in glyr if hexes[f["hex_id"]][2].Contains(pt)]
        glyr.SetSpatialFilter(None)
        if hit:
            vals[hit[0]].append(p["cena_m2"])
        else:
            outside += 1
    nb = {i: [j for j in ids if j != i and math.hypot(hexes[i][0] - hexes[j][0], hexes[i][1] - hexes[j][1]) < 300] for i in ids}
    assert max(len(v) for v in nb.values()) <= 6, "hex neighbourhood is not a ring of 6"
    rows = []
    for i in ids:
        own = vals[i]
        ring = own + [v for j in nb[i] for v in vals[j]]
        rows.append({"hex_id": i, "n": len(own), "price_m2": round(median(own)) if len(own) >= cfg["hex"]["min_n"] else "",
                     "n_ring": len(ring), "price_m2_ring": round(median(ring)) if len(ring) >= cfg["hex"]["ring_min_n"] else ""})
    with open(OUT / "price_hex.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    total = sum(len(v) for v in vals.values())
    cov = {"own n>=%d" % k: sum(1 for i in ids if len(vals[i]) >= k) for k in (1, 3, 5, 10)}
    cov.update({"ring n>=%d" % k: sum(1 for r in rows if r["n_ring"] >= k) for k in (5, 10, 20)})
    pv = sorted(r["price_m2"] for r in rows if r["price_m2"] != "")
    pr = sorted(r["price_m2_ring"] for r in rows if r["price_m2_ring"] != "")
    q = lambda a, p: a[int(p * (len(a) - 1))] if a else None
    meta = {"price_version": cfg["price_version"], "hexes": len(ids), "deeds_in_hexes": total, "deeds_outside_city_hexes": outside,
            "min_n": cfg["hex"]["min_n"], "ring_min_n": cfg["hex"]["ring_min_n"], "coverage_hexes": cov,
            "own_price_m2_pct": {p: q(pv, p / 100) for p in (10, 25, 50, 75, 90)},
            "ring_price_m2_pct": {p: q(pr, p / 100) for p in (10, 25, 50, 75, 90)}}
    json.dump(meta, open(OUT / "price_hex.meta.json", "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
