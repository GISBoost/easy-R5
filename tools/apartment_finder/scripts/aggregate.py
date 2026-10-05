"""M5: median over the days per scenario -> data/agg/<scenario>.npy, plus I5 (day-to-day spread) report.

Transit scenarios exist for every day in config/days.yaml; walk/bike/car were computed once (they do not
depend on the day) and are copied from the last day. A pair counts as reached in the median only when at least
3 of the 5 days reached it (255 sorts last). I5: per scenario, the share of pairs whose reached days differ by
more than 10 min and the per-day mean absolute deviation from the median; the day with the largest deviation is
flagged. System Python (numpy, yaml).
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parents[1]
days = yaml.safe_load(open(HERE / "config/days.yaml", encoding="utf-8"))["days"]
OUT = HERE / "data/agg"
OUT.mkdir(parents=True, exist_ok=True)


MAX_REPAIR_SHARE = 1e-6   # more repaired pairs than this means a real I1 problem: stop instead of repairing
repaired_pairs = {}


def raw(day, name):
    return np.load(HERE / "data/matrices" / day / (name + ".npz"))["p50"]


def load(day, name):
    """One day's matrix with the I1 monotone repair applied.

    I1: LKA on never lengthens a time; at most 1 transfer never beats unlimited transfers. R5 breaks it for a
    handful of pairs whose only path has a walking leg right at the walk cap (MAX_WALK_TIME), because adding the
    LKA stops re-links street edges by ~1 min (diagnosed 2026-10-05: the 3 violating pairs of the pilot vanish
    with a 25 min cap). Where the invariant is violated we take the better of the two matrices.
    """
    parts = name.split("_")
    if len(parts) != 4 or parts[1] not in ("static", "p50", "p85"):
        return raw(day, name)                       # walk / bike / car
    w, t, rides, lka = parts
    g = {(r, l): raw(day, "_".join((w, t, r, l))) for r in ("unlimited", "max1transfer") for l in ("nolka", "lka")}
    best = {}                                       # element-wise lower envelope along the partial order
    best[("max1transfer", "nolka")] = g[("max1transfer", "nolka")]
    best[("max1transfer", "lka")] = np.minimum(g[("max1transfer", "lka")], best[("max1transfer", "nolka")])
    best[("unlimited", "nolka")] = np.minimum(g[("unlimited", "nolka")], best[("max1transfer", "nolka")])
    best[("unlimited", "lka")] = np.minimum.reduce([g[("unlimited", "lka")], best[("max1transfer", "lka")],
                                                    best[("unlimited", "nolka")]])
    key = (rides, lka)
    n = int((best[key] != g[key]).sum())
    repaired_pairs[(day, name)] = n
    if n > MAX_REPAIR_SHARE * g[key].size:
        raise SystemExit("I1 violated in %d pairs of %s %s (> %g share): not a boundary artifact, stop" % (n, day, name, MAX_REPAIR_SHARE))
    return best[key]


def main():
    names = sorted(p.stem for p in (HERE / "data/matrices" / days[-1]).glob("*.npz"))
    report = {}
    for name in names:
        have = [d for d in days if (HERE / "data/matrices" / d / (name + ".npz")).exists()]
        if len(have) < len(days):
            if len(have) == 1 and have[0] == days[-1]:  # once-only scenario (walk, bike, car)
                np.save(OUT / (name + ".npy"), load(days[-1], name))
                continue
            print("skip (missing days)", name, file=sys.stderr)
            continue
        stack = np.stack([load(d, name) for d in days])          # (days, n, n) uint8
        med = np.sort(stack, axis=0)[len(days) // 2]
        np.save(OUT / (name + ".npy"), med)
        reached = (stack != 255)
        both = reached.all(axis=0)
        s = stack.astype(np.int16)
        spread = (np.where(both, s.max(0) - s.min(0), 0) > 10)[both]
        dev = [float(np.abs(s[i].astype(np.int32) - med)[both].mean()) for i in range(len(days))]
        report[name] = {"pairs_reached_all_days": int(both.sum()),
                        "share_pairs_spread_gt_10min": round(float(spread.mean()), 4),
                        "mean_abs_dev_per_day_min": {d: round(v, 2) for d, v in zip(days, dev)},
                        "outlier_day": days[int(np.argmax(dev))]}
        print(name, report[name]["share_pairs_spread_gt_10min"], report[name]["outlier_day"], file=sys.stderr)
    report["_i1_repaired_pairs_total"] = int(sum(repaired_pairs.values()))
    report["_i1_repaired_pairs_by_scenario_day"] = {"%s|%s" % k: v for k, v in repaired_pairs.items() if v}
    json.dump(report, open(OUT / "i5_report.json", "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
