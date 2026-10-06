"""Difference in travel time to the 3 nearest POIs between two Mondays (later - earlier; negative = later is faster).

    py -I poi_delta.py [--src <dir with case/band.npz + walk.npz>] [--pairs main,placebo]

For every pair of models in config.yaml -> pairs, band and category (pharmacy, school, clinic, supermarket, all):
  * pair level: one (hex, POI) pair = one of the 3 frozen nearest POIs of a hex. Compared only where transit beats
    walking on BOTH days ("transit_only", no walk-only trips) and, separately, where R5 reaches the POI on both days
    ("door_to_door", walking included). Weights = population of the origin hex.
  * hex level: median over the (up to 3) comparable POIs of a hex, per category.
Writes out/poi_delta[_smoke]/<pair>/ summary_pairs.csv, summary_hex.csv, hex.csv, sentences.txt.
"""

from __future__ import annotations

import argparse
import csv
import os
import warnings
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
P, BANDS, CASES = CFG["poi"], CFG["bands"], CFG["cases"]
K = P["k_nearest"]
CATS = list(P["categories"])
CAT_PL = {"pharmacy": "aptek", "school": "szkół", "clinic": "przychodni", "supermarket": "supermarketów", "all": "wszystkich kategorii"}
MODES = {"transit_only": "transportem (bez pieszych)", "door_to_door": "od drzwi do drzwi (z dojściem pieszo)"}


def wquantile(x, w, q):
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return float(x[np.searchsorted(c, q * c[-1])])


def wmean(x, w):
    return float((x * w).sum() / w.sum())


def stats(tl, te, w):
    """Shares and typical times for arrays of later/earlier minutes (already restricted to comparable pairs)."""
    d = tl.astype(float) - te
    return {"n": int(len(d)), "pop_weight": round(float(w.sum()), 1),
            "share_shorter": wmean((d < 0).astype(float), w), "share_longer": wmean((d > 0).astype(float), w),
            "share_same": wmean((d == 0).astype(float), w),
            "median_later_min": wquantile(tl.astype(float), w, 0.5), "median_earlier_min": wquantile(te.astype(float), w, 0.5),
            "mean_later_min": wmean(tl.astype(float), w), "mean_earlier_min": wmean(te.astype(float), w),
            "mean_delta_min": wmean(d, w), "median_delta_min": wquantile(d, w, 0.5)}


def pct(v):
    return f"{100 * v:.1f}".replace(".", ",")


def num(v):
    return f"{v:.2f}".replace(".", ",")


def sentence(pair, band, cat, mode, s, later, earlier):
    return (f"[{pair} / {band} / {cat} / {mode}] {pct(s['share_shorter'])}% par jedzie krócej {later} niż {earlier} "
            f"(mediana {later}: {num(s['median_later_min'])} min, {earlier}: {num(s['median_earlier_min'])} min; "
            f"dłużej {pct(s['share_longer'])}%, tyle samo {pct(s['share_same'])}%; średnia różnica {num(s['mean_delta_min'])} min; "
            f"n = {s['n']} par hex-POI do {CAT_PL[cat]})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=None)
    ap.add_argument("--pairs", default="")
    a = ap.parse_args()
    src = Path(a.src) if a.src else Path(os.environ.get("S3_DATA_DIR") or CFG["data_dir"]) / "poi_tt"
    out_root = HERE / "out" / ("poi_delta_smoke" if "smoke" in src.name else "poi_delta")
    walk_npz = np.load(src / "walk.npz")
    ids, dest_ids, walk = [str(i) for i in walk_npz["ids"]], [str(i) for i in walk_npz["dest_ids"]], walk_npz["m"]
    pop_all = {r["id"]: float(r["pop"]) for r in csv.DictReader(open(HERE / P["pop"], encoding="utf-8"))}
    pop = np.array([pop_all[i] for i in ids])
    hidx, didx = {h: i for i, h in enumerate(ids)}, {d: i for i, d in enumerate(dest_ids)}
    near = {c: np.full((len(ids), K), -1, dtype=int) for c in CATS}
    for r in csv.DictReader(open(HERE / P["nearest"], encoding="utf-8")):
        if r["hex_id"] in hidx:
            near[r["category"]][hidx[r["hex_id"]], int(r["rank"]) - 1] = didx[r["poi_id"]]
    rows_i = np.arange(len(ids))[:, None]
    walk_c = {c: walk[rows_i, near[c]] for c in CATS}

    def times(case, band):
        m = np.load(src / case / f"{band}.npz")["m"]
        return {c: m[rows_i, near[c]] for c in CATS}

    for name, pr in CFG["pairs"].items():
        if a.pairs and name not in a.pairs.split(","):
            continue
        later_c, earlier_c = pr["later"], pr["earlier"]
        ll = f"{CASES[later_c]['date'][8:]}.{CASES[later_c]['date'][5:7]}"
        le = f"{CASES[earlier_c]['date'][8:]}.{CASES[earlier_c]['date'][5:7]}"
        out = out_root / name
        out.mkdir(parents=True, exist_ok=True)
        pair_rows, hex_rows, hex_sum, lines = [], [], [], []
        for band in BANDS:
            if not ((src / later_c / f"{band}.npz").is_file() and (src / earlier_c / f"{band}.npz").is_file()):
                print(f"[skip] {name} {band}")
                continue
            tl_all, te_all = times(later_c, band), times(earlier_c, band)
            elig = {}
            for mode in MODES:
                for c in CATS:
                    tl, te, wk = tl_all[c], te_all[c], walk_c[c]
                    if mode == "transit_only":
                        ok_l = (tl >= 0) & ((wk < 0) | (tl < wk))
                        ok_e = (te >= 0) & ((wk < 0) | (te < wk))
                    else:
                        ok_l, ok_e = tl >= 0, te >= 0
                    elig[mode, c] = ok_l & ok_e
                    row = {"pair": name, "band": band, "mode": mode, "category": c, "later": later_c, "earlier": earlier_c,
                           "n_pairs_total": int(tl.size), "n_lost": int((ok_e & ~ok_l).sum()), "n_gained": int((ok_l & ~ok_e).sum())}
                    both = elig[mode, c]
                    w = np.broadcast_to(pop[:, None], tl.shape)[both]
                    if both.any():
                        row.update(stats(tl[both], te[both], w))
                        lines.append(sentence(name, band, c, mode, row, ll, le))
                    pair_rows.append(row)
                # all categories pooled
                tl = np.concatenate([tl_all[c][elig[mode, c]] for c in CATS])
                te = np.concatenate([te_all[c][elig[mode, c]] for c in CATS])
                w = np.concatenate([np.broadcast_to(pop[:, None], tl_all[c].shape)[elig[mode, c]] for c in CATS])
                row = {"pair": name, "band": band, "mode": mode, "category": "all", "later": later_c, "earlier": earlier_c,
                       "n_pairs_total": sum(r["n_pairs_total"] for r in pair_rows[-len(CATS):]),
                       "n_lost": sum(r["n_lost"] for r in pair_rows[-len(CATS):]),
                       "n_gained": sum(r["n_gained"] for r in pair_rows[-len(CATS):])}
                if len(tl):
                    row.update(stats(tl, te, w))
                    lines.append(sentence(name, band, "all", mode, row, ll, le))
                pair_rows.append(row)
            # hex level: median over the comparable nearest POIs, transit-only
            for c in CATS:
                e = elig["transit_only", c]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    ml = np.nanmedian(np.where(e, tl_all[c], np.nan), axis=1)
                    me = np.nanmedian(np.where(e, te_all[c], np.nan), axis=1)
                n_ok = e.sum(1)
                good = n_ok > 0
                for i in np.where(good)[0]:
                    hex_rows.append({"band": band, "category": c, "hex_id": ids[i], "pop": pop[i], "n_poi": int(n_ok[i]),
                                     "median_later_min": ml[i], "median_earlier_min": me[i], "delta_min": ml[i] - me[i]})
                if good.any():
                    s = stats(ml[good], me[good], pop[good])
                    s.update({"band": band, "category": c, "n_hexes_total": len(ids)})
                    hex_sum.append(s)
                    lines.append(f"[{name} / {band} / {c} / hex] {pct(s['share_shorter'])}% ludności (hexów: {s['n']}) ma krótszy "
                                 f"czas do mediany 3 najbliższych {CAT_PL[c]} {ll} niż {le} (mediana: {num(s['median_later_min'])} "
                                 f"vs {num(s['median_earlier_min'])} min)")
        for fname, data in (("summary_pairs.csv", pair_rows), ("summary_hex.csv", hex_sum), ("hex.csv", hex_rows)):
            if data:
                cols = list(dict.fromkeys(k for r in data for k in r))
                with open(out / fname, "w", newline="", encoding="utf-8") as fh:
                    w_ = csv.DictWriter(fh, fieldnames=cols)
                    w_.writeheader()
                    w_.writerows(data)
        (out / "sentences.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[ok] {name}: {len(lines)} lines -> {out}")


if __name__ == "__main__":
    main()
