"""Difference in travel time hex 250 m -> hex 250 m between two Mondays (later - earlier; negative = later is faster).

    py -I hex_delta.py [--src <dir with case/band.npz + walk.npz>] [--pairs main,placebo]

Same pairs, models and rules as poi_delta.py, but on the full matrix: every pair of hexes (origin != destination) is one
pair, weighted by population(origin) x population(destination). Pairs are split by straight-line distance
(config.yaml -> hexmatrix.distance_classes_km); the last class is "across the city". Compared only where transit beats
walking on BOTH days ("transit_only") and, separately, where R5 reaches the destination on both days ("door_to_door").
Writes out/hex_delta[_smoke]/<pair>/ summary.csv, sentences.txt, hex.csv (per origin hex, transit_only).
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
P, H, BANDS, CASES = CFG["poi"], CFG["hexmatrix"], CFG["bands"], CFG["cases"]
EDGES = H["distance_classes_km"]
K = len(EDGES)
OFF = CFG["r5"]["max_trip_duration_min"]   # |delta| and times never exceed the trip cap
NV = 2 * OFF + 1
MODES = ("transit_only", "door_to_door")
BLOCK = 500                                # origin rows per block (keeps ~3M-element temporaries)
EARTH_R = 6371008.8


def class_label(k):
    if k == "all":
        return "wszystkich odległości"
    hi = f"{EDGES[k + 1]}" if k + 1 < K else None
    return f"{EDGES[k]}–{hi} km" if hi else f"{EDGES[k]} km i więcej"


def pct(v):
    return f"{100 * v:.1f}".replace(".", ",")


def num(v):
    return f"{v:.2f}".replace(".", ",")


def hist_q(h, q, values):
    c = np.cumsum(h)
    return float(values[np.searchsorted(c, q * c[-1])])


def haversine_block(lon1, lat1, lon2, lat2):
    p1, p2 = np.radians(lat1)[:, None], np.radians(lat2)[None, :]
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2[None, :] - lon1[:, None]) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=None)
    ap.add_argument("--pairs", default="")
    a = ap.parse_args()
    src = Path(a.src) if a.src else Path(os.environ.get("S3_DATA_DIR") or CFG["data_dir"]) / "hex_tt"
    out_root = HERE / "out" / ("hex_delta_smoke" if "smoke" in src.name else "hex_delta")
    wz = np.load(src / "walk.npz")
    ids, dest_ids, walk = [str(i) for i in wz["ids"]], [str(i) for i in wz["dest_ids"]], wz["m"]
    coords = {r["id"]: (float(r["lon"]), float(r["lat"])) for r in csv.DictReader(open(HERE / P["origins"], encoding="utf-8"))}
    pop_all = {r["id"]: float(r["pop"]) for r in csv.DictReader(open(HERE / P["pop"], encoding="utf-8"))}
    olon, olat = (np.array([coords[i][k] for i in ids]) for k in (0, 1))
    dlon, dlat = (np.array([coords[i][k] for i in dest_ids]) for k in (0, 1))
    po, pd = np.array([pop_all[i] for i in ids]), np.array([pop_all[i] for i in dest_ids])
    didx = {d: j for j, d in enumerate(dest_ids)}
    self_col = np.array([didx[i] for i in ids])
    cls = np.empty((len(ids), len(dest_ids)), dtype=np.int8)       # distance class of every pair (same for all bands)
    for s in range(0, len(ids), BLOCK):
        d_km = haversine_block(olon[s:s + BLOCK], olat[s:s + BLOCK], dlon, dlat) / 1000
        cls[s:s + BLOCK] = np.searchsorted(EDGES, d_km, side="right") - 1
    vals_d, vals_t = np.arange(NV) - OFF, np.arange(NV)

    for name, pr in CFG["pairs"].items():
        if a.pairs and name not in a.pairs.split(","):
            continue
        lc, ec = pr["later"], pr["earlier"]
        ll = f"{CASES[lc]['date'][8:]}.{CASES[lc]['date'][5:7]}"
        le = f"{CASES[ec]['date'][8:]}.{CASES[ec]['date'][5:7]}"
        out = out_root / name
        out.mkdir(parents=True, exist_ok=True)
        rows, hex_rows, lines = [], [], []
        for band in BANDS:
            fl, fe = src / lc / f"{band}.npz", src / ec / f"{band}.npz"
            if not (fl.is_file() and fe.is_file()):
                print(f"[skip] {name} {band}")
                continue
            ml, me = np.load(fl)["m"], np.load(fe)["m"]
            acc = {m: {"hd": np.zeros((K, NV)), "hl": np.zeros((K, NV)), "he": np.zeros((K, NV)), "n": np.zeros(K, dtype=np.int64),
                       "lost": np.zeros(K, dtype=np.int64), "gained": np.zeros(K, dtype=np.int64)} for m in MODES}
            o_sum = {k: np.zeros((len(ids), 3)) for k in ("all", "far")}      # weight, weight*delta, n   (transit_only)
            for s in range(0, len(ids), BLOCK):
                sl = slice(s, s + BLOCK)
                tl, te, wk, c = ml[sl].astype(np.int32), me[sl].astype(np.int32), walk[sl].astype(np.int32), cls[sl]
                w = po[sl, None] * pd[None, :]
                rr = np.arange(tl.shape[0])
                for mode in MODES:
                    if mode == "transit_only":
                        ok_l, ok_e = (tl >= 0) & ((wk < 0) | (tl < wk)), (te >= 0) & ((wk < 0) | (te < wk))
                    else:
                        ok_l, ok_e = tl >= 0, te >= 0
                    ok_l[rr, self_col[sl]] = ok_e[rr, self_col[sl]] = False
                    both = ok_l & ok_e
                    A = acc[mode]
                    k_, w_ = c[both].astype(np.int64), w[both]
                    A["hd"] += np.bincount(k_ * NV + (tl - te)[both] + OFF, weights=w_, minlength=K * NV).reshape(K, NV)
                    A["hl"] += np.bincount(k_ * NV + tl[both], weights=w_, minlength=K * NV).reshape(K, NV)
                    A["he"] += np.bincount(k_ * NV + te[both], weights=w_, minlength=K * NV).reshape(K, NV)
                    A["n"] += np.bincount(k_, minlength=K)
                    A["lost"] += np.bincount(c[ok_e & ~ok_l].astype(np.int64), minlength=K)
                    A["gained"] += np.bincount(c[ok_l & ~ok_e].astype(np.int64), minlength=K)
                    if mode == "transit_only":
                        d = (tl - te).astype(float)
                        for key, m_ in (("all", both), ("far", both & (c == K - 1))):
                            wm = pd[None, :] * m_
                            o_sum[key][sl] += np.stack([wm.sum(1), (wm * d).sum(1), m_.sum(1)], axis=1)
            for mode in MODES:
                A = acc[mode]
                for k in list(range(K)) + ["all"]:
                    sel = slice(None) if k == "all" else k
                    hd, hl, he = (A[x][sel].sum(0) if k == "all" else A[x][k] for x in ("hd", "hl", "he"))
                    n = int(A["n"].sum() if k == "all" else A["n"][k])
                    if n == 0:
                        continue
                    tot = hd.sum()
                    r = {"pair": name, "band": band, "mode": mode, "distance_class": class_label(k), "later": lc, "earlier": ec, "n": n,
                         "n_lost": int(A["lost"].sum() if k == "all" else A["lost"][k]),
                         "n_gained": int(A["gained"].sum() if k == "all" else A["gained"][k]),
                         "share_shorter": float(hd[vals_d < 0].sum() / tot), "share_longer": float(hd[vals_d > 0].sum() / tot),
                         "share_same": float(hd[vals_d == 0].sum() / tot),
                         "median_later_min": hist_q(hl, 0.5, vals_t), "median_earlier_min": hist_q(he, 0.5, vals_t),
                         "mean_later_min": float((hl * vals_t).sum() / tot), "mean_earlier_min": float((he * vals_t).sum() / tot),
                         "mean_delta_min": float((hd * vals_d).sum() / tot), "median_delta_min": hist_q(hd, 0.5, vals_d)}
                    rows.append(r)
                    lines.append(f"[{name} / {band} / {mode} / {class_label(k)}] {pct(r['share_shorter'])}% par jedzie krócej {ll} niż {le} "
                                 f"(mediana {ll}: {num(r['median_later_min'])} min, {le}: {num(r['median_earlier_min'])} min; "
                                 f"dłużej {pct(r['share_longer'])}%, tyle samo {pct(r['share_same'])}%; "
                                 f"średnia różnica {num(r['mean_delta_min'])} min; n = {n} par hex-hex)")
            for i, hid in enumerate(ids):
                if o_sum["all"][i, 2] >= H["min_dest_per_origin"]:
                    far = o_sum["far"][i]
                    hex_rows.append({"band": band, "hex_id": hid, "pop": po[i], "n_dest": int(o_sum["all"][i, 2]),
                                     "mean_delta_all_min": o_sum["all"][i, 1] / o_sum["all"][i, 0],
                                     "n_dest_far": int(far[2]),
                                     "mean_delta_far_min": far[1] / far[0] if far[2] >= H["min_dest_per_origin"] else ""})
        for fname, data in (("summary.csv", rows), ("hex.csv", hex_rows)):
            if data:
                with open(out / fname, "w", newline="", encoding="utf-8") as fh:
                    w_ = csv.DictWriter(fh, fieldnames=list(data[0]))
                    w_.writeheader()
                    w_.writerows(data)
        (out / "sentences.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[ok] {name}: {len(lines)} lines -> {out}")


if __name__ == "__main__":
    main()
