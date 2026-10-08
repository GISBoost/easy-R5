"""Price layer, ŁOG source, step 2: price-class cells (price_log_fetch.py) -> per-hex price level per snapshot and market.

Same method as price_hex.py: smallest circle (start..max radius around the hex centre) holding at least `log_hex.min_cells` cell centres,
distance-weighted median, empty when there is not enough, kept only for inhabited hexes. A cell's value is the middle of its class; the open top
class ("≥ 7 501") takes its lower bound + `log_hex.open_class_add` and is flagged: a hex value is CENSORED when more than half of the weight sits
in open classes (the real level is then at least the value). Writes data/price/log/log_hex.csv (hex_id, snapshot, market, price_m2, radius_m, n,
censored) + log_hex.meta.json. Markets: RP, RW and ALL (cells of both pooled; ALL is not transaction-weighted). System Python (osgeo, numpy).

  py scripts/price_log_hex.py
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from osgeo import ogr

ogr.UseExceptions()
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from price_hex import wmedian   # noqa: E402

cfg = yaml.safe_load(open(HERE / "config/price.yaml", encoding="utf-8"))
OUT = HERE / "data/price/log"
H, LH = cfg["hex"], cfg["log_hex"]


def cell_value(lo, hi):
    """(value, open_class): middle of a bounded class, lower bound + add for the open top class, upper bound for a bottom class."""
    if lo is not None and hi is not None:
        return (lo + hi) / 2, False
    if lo is not None:
        return lo + LH["open_class_add"], True
    return hi, False


def main():
    gds = ogr.Open(str(HERE / "data/grid.gpkg"))
    ids, C = [], []
    for f in gds.GetLayerByName("hex_grid"):
        c = f.GetGeometryRef().Centroid()
        ids.append(f["hex_id"]); C.append((c.GetX(), c.GetY()))
    o = np.argsort(ids); ids = np.array(ids)[o]; C = np.array(C)[o]
    inhabited = {}
    for r in csv.DictReader(open(HERE / "data/price/price_hex.csv", encoding="utf-8")):
        inhabited[int(r["hex_id"])] = float(r["res_footprint_m2"]) >= cfg["inhabited"]["min_footprint_m2"]

    cds = ogr.Open(str(OUT / "log_cells.gpkg"))
    cells = {}
    for f in cds.GetLayer(0):
        c = f.GetGeometryRef().Centroid()
        v, op = cell_value(f["lo"], f["hi"])
        cells.setdefault((f["snapshot"], f["market"]), []).append((c.GetX(), c.GetY(), v, op))
    for snap in {k[0] for k in cells}:
        cells[(snap, "ALL")] = cells.get((snap, "RP"), []) + cells.get((snap, "RW"), [])

    radii = list(range(H["start_radius_m"], H["max_radius_m"] + 1, H["radius_step_m"]))
    rows, summary = [], {}
    for (snap, mk), cl in sorted(cells.items()):
        P = np.array([(x, y) for x, y, _, _ in cl]); V = np.array([v for _, _, v, _ in cl]); OP = np.array([op for *_, op in cl])
        D = np.hypot(C[:, None, 0] - P[None, :, 0], C[:, None, 1] - P[None, :, 1])
        got = cens = 0
        for k, hid in enumerate(ids):
            if not inhabited[int(hid)]:
                continue
            for r in radii:
                m = D[k] <= r
                if m.sum() >= LH["min_cells"]:
                    w = 1 - (1 - H["weight_edge"]) * D[k][m] / r
                    censored = w[OP[m]].sum() > w.sum() / 2
                    rows.append({"hex_id": int(hid), "snapshot": snap, "market": mk, "price_m2": round(wmedian(V[m], w)), "radius_m": r, "n": int(m.sum()),
                                 "censored": int(censored)})
                    got += 1; cens += censored
                    break
        n_inh = sum(inhabited.values())
        summary["%s %s" % (snap, mk)] = {"cells": len(cl), "open_class_cells_pct": round(100 * OP.mean()), "hexes": got, "coverage_inhabited_pct": round(100 * got / n_inh, 1),
                                         "censored_pct": round(100 * cens / got, 1) if got else None}
    with open(OUT / "log_hex.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump({"price_version": cfg["price_version"], "config": LH, "summary": summary}, open(OUT / "log_hex.meta.json", "w"), indent=1)
    for k, v in summary.items():
        print(k, v)


if __name__ == "__main__":
    main()
