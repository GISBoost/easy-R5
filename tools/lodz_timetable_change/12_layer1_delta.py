"""S3 layer 1: per-hex deltas and summary tables from layer1_r5.py outputs.

    py -I 12_layer1_delta.py [--pairs main,placebo]

Reads out/layer1/<case>/<band>_{acc,svcacc}.csv, writes out/layer1_delta/<pair>/delta_hex.csv (one row per
hex x band x metric x opportunity x cutoff) and summary.csv (gainers/losers, population-weighted).
Hexes with a zero baseline AND a zero result are skipped (nothing to gain or lose), as in realtime_delay_lodz.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))["layer1"]
SRC, DST = HERE / "out" / "layer1", HERE / "out" / "layer1_delta"


def set_grid(name):
    global SRC, DST
    CFG.update(CFG["grids"][name])
    sfx = "" if name == "h500" else f"_{name}"
    SRC, DST = HERE / "out" / f"layer1{sfx}", HERE / "out" / f"layer1_delta{sfx}"


def load(case, band, metric):
    path = SRC / case / f"{band}_{metric}.csv"
    if not path.is_file():
        return None
    return {(r["id"], r["opportunity"], r["cutoff"]): float(r["accessibility"]) for r in csv.DictReader(open(path, encoding="utf-8"))}


def hex_pop():
    with open(HERE / CFG["destinations"], newline="", encoding="utf-8") as fh:
        ids = {r["id"] for r in csv.DictReader(open(HERE / CFG["origins"], encoding="utf-8"))}
        return {r["id"]: float(r["pop"]) for r in csv.DictReader(fh) if r["id"] in ids}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="")
    ap.add_argument("--grid", default="h500", choices=["h500", "h250"])
    args = ap.parse_args()
    set_grid(args.grid)
    pairs = [p for p in args.pairs.split(",") if p] or list(CFG["pairs"])
    pop = hex_pop()
    D = CFG["delta"]
    for name in pairs:
        a_case, b_case = CFG["pairs"][name]["a"], CFG["pairs"][name]["b"]
        out = DST / name
        out.mkdir(parents=True, exist_ok=True)
        rows, summary = [], []
        for band in CFG["bands"]:
            for metric in D["metrics"]:
                a, b = load(a_case, band, metric), load(b_case, band, metric)
                if a is None or b is None:
                    print(f"[skip] {name} {band} {metric}: missing output")
                    continue
                for opp in D["opportunities"]:
                    for cutoff in map(str, CFG["r5"]["cutoffs"]):
                        deltas = []
                        for (hid, o, c), va in a.items():
                            if o != opp or c != cutoff:
                                continue
                            vb = b[(hid, o, c)]
                            if va == 0 and vb == 0:
                                continue
                            rows.append({"pair": name, "band": band, "metric": metric, "opportunity": opp, "cutoff": cutoff,
                                         "hex_id": hid, "pop": pop[hid], "before": va, "after": vb, "delta": round(vb - va, 4)})
                            deltas.append((hid, vb - va))
                        n = len(deltas)
                        if not n:
                            continue
                        w = sum(pop[h] for h, _ in deltas)
                        gain = [h for h, d in deltas if d > 0]
                        loss = [h for h, d in deltas if d < 0]
                        summary.append({
                            "pair": name, "band": band, "metric": metric, "opportunity": opp, "cutoff": cutoff,
                            "n_hex": n, "n_gain": len(gain), "n_loss": len(loss),
                            "pop_gain": round(sum(pop[h] for h in gain)), "pop_loss": round(sum(pop[h] for h in loss)),
                            "mean_delta": round(sum(d for _, d in deltas) / n, 3),
                            "popweighted_mean_delta": round(sum(pop[h] * d for h, d in deltas) / w, 3) if w else "",
                        })
        for fname, data in (("delta_hex.csv", rows), ("summary.csv", summary)):
            if data:
                with open(out / fname, "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(data[0]))
                    w.writeheader()
                    w.writerows(data)
        # top gains/losses for the headline cut: population reach, 30 min, p50
        top = [r for r in rows if r["opportunity"] == "pop" and r["metric"] == "acc" and r["cutoff"] == "30"]
        for band in CFG["bands"]:
            sel = sorted((r for r in top if r["band"] == band), key=lambda r: r["delta"])
            if sel:
                with open(out / f"top_{band}.csv", "w", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(sel[0]))
                    w.writeheader()
                    w.writerows(sel[:D["top_n"]] + sel[-D["top_n"]:])
        print(f"[ok] {name}: {len(rows)} hex rows, {len(summary)} summary rows -> {out}")


if __name__ == "__main__":
    main()
