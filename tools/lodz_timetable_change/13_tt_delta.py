"""S3 layer 1b: how much longer/shorter a transit trip takes, one day vs one day (no walk-only trips).

    py -I 13_tt_delta.py

A pair (origin hex, destination hex) counts as a transit trip on a day when R5's p50 door-to-door time is
reached and is shorter than the walk-only time (or walking is not possible within the cap). The comparison
uses pairs that are transit trips on BOTH days; pairs that are transit trips on one day only are counted
separately (gained / lost transit connections). Delta = b - a in minutes: positive = b is slower.
Weights: population of origin x population of destination. Writes out/layer1_tt/<pair>/ summary.csv + hex.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
L1, TT = CFG["layer1"], CFG["tt"]
SRC = Path(CFG["data_dir"]) / "layer1_tt"
OUT = HERE / "out" / "layer1_tt"
CUTS = [10, 20, 30, 45]  # ponytail: trip-length classes by the "before" time; move to config.yaml if reused


def set_grid(name):
    global SRC, OUT
    L1.update(L1["grids"][name])
    sfx = "" if name == "h500" else f"_{name}"
    SRC, OUT = Path(CFG["data_dir"]) / f"layer1_tt{sfx}", HERE / "out" / f"layer1_tt{sfx}"


def wquantile(x, w, q):
    o = np.argsort(x)
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return float(x[np.searchsorted(c, q * c[-1])])


def transit_mask(m, walk):
    return (m >= 0) & ((walk < 0) | (m < walk))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="h500", choices=["h500", "h250"])
    set_grid(ap.parse_args().grid)
    walk = np.load(SRC / "walk.npz")["m"]
    ids = [r["id"] for r in csv.DictReader(open(HERE / L1["origins"], encoding="utf-8"))]
    dest_ids = [r["id"] for r in csv.DictReader(open(HERE / TT["destinations"], encoding="utf-8"))]
    pop = {r["id"]: float(r["pop"]) for r in csv.DictReader(open(HERE / L1["destinations"], encoding="utf-8"))}
    pop500 = {r["id"]: float(r["pop"]) for r in csv.DictReader(open(HERE / L1["grids"]["h500"]["destinations"], encoding="utf-8"))}
    p = np.array([pop[i] for i in ids])
    W = np.outer(p, np.array([pop500[i] for i in dest_ids]))
    square = ids == dest_ids   # self-pairs only exist when origins and destinations are the same grid
    for name, pr in TT["pairs"].items():
        out = OUT / name
        out.mkdir(parents=True, exist_ok=True)
        rows, hex_rows = [], []
        for band in L1["bands"]:
            fa, fb = SRC / pr["a"] / f"{band}.npz", SRC / pr["b"] / f"{band}.npz"
            if not (fa.is_file() and fb.is_file()):
                print(f"[skip] {name} {band}")
                continue
            a, b = np.load(fa)["m"], np.load(fb)["m"]
            ta, tb = transit_mask(a, walk), transit_mask(b, walk)
            if square:
                np.fill_diagonal(ta, False)
                np.fill_diagonal(tb, False)
            both = ta & tb
            d = (b.astype(np.int32) - a.astype(np.int32))
            x, w, ba = d[both].astype(float), W[both], a[both]
            r = {"pair": name, "band": band, "a": pr["a"], "b": pr["b"], "n_pairs_a": int(ta.sum()), "n_pairs_b": int(tb.sum()),
                 "n_both": int(both.sum()), "n_lost": int((ta & ~tb).sum()), "n_gained": int((~ta & tb).sum()),
                 "weighted_mean_delta_min": round(float((x * w).sum() / w.sum()), 3),
                 "weighted_median_delta_min": wquantile(x, w, 0.5),
                 "weighted_p25": wquantile(x, w, 0.25), "weighted_p75": wquantile(x, w, 0.75),
                 "mean_time_a_min": round(float((ba * w).sum() / w.sum()), 2),
                 "share_slower": round(float(w[x > 0].sum() / w.sum()), 4), "share_faster": round(float(w[x < 0].sum() / w.sum()), 4)}
            for lo, hi in zip([0] + CUTS, CUTS + [10**6]):
                s = (ba >= lo) & (ba < hi)
                r[f"median_delta_a_{lo}_{hi if hi < 10**6 else 'inf'}"] = wquantile(x[s], w[s], 0.5) if s.any() else ""
            rows.append(r)
            # per origin hex: median change over destinations transit-connected on both days
            for i, hid in enumerate(ids):
                s = both[i]
                if s.sum() >= 5:
                    hex_rows.append({"pair": name, "band": band, "hex_id": hid, "pop": p[i], "n_dest": int(s.sum()),
                                     "median_delta_min": float(np.median(d[i][s])),
                                     "mean_delta_min": round(float(d[i][s].mean()), 3)})
        for fname, data in (("summary.csv", rows), ("hex.csv", hex_rows)):
            if data:
                with open(out / fname, "w", newline="", encoding="utf-8") as fh:
                    w_ = csv.DictWriter(fh, fieldnames=list(data[0]))
                    w_.writeheader()
                    w_.writerows(data)
        print(f"[ok] {name}")
        for r in rows:
            print(f"  {r['band']:8s} both={r['n_both']} lost={r['n_lost']} gained={r['n_gained']} "
                  f"median {r['weighted_median_delta_min']:+.1f} min, mean {r['weighted_mean_delta_min']:+.2f}, "
                  f"slower {r['share_slower']:.0%} / faster {r['share_faster']:.0%}")


if __name__ == "__main__":
    main()
