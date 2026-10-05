"""Invariants I1-I4 (PRD 9) on one day's packed matrices -> data/matrices/<day>/invariants_<window>.json.

  I1  LKA on never lengthens a time and never loses reachability; max1transfer never beats unlimited.
  I2  P85 >= P50 >= static for the vast majority of pairs (violation share reported).
  I3  routing probe: LKA on must actually improve some pairs (guards against silent drop of rail).
  I4  walking times roughly symmetric.
Exits non-zero when I1 or I3 is broken (PRD: I1/I3 stop the work). I5 (day-to-day spread) is in M5.
System Python (numpy).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
NR = 255
N_PAIRS = 5662 * 5662


def load(d, name):
    return np.load(d / (name + ".npz"))["p50"]


def worse(a, b):
    """pairs where a is strictly worse than b (unreached = infinity)."""
    ai, bi = a.astype(np.int16), b.astype(np.int16)
    return int(((ai > bi)).sum())  # 255 is the largest value, so unreached sorts as worst


def main(day, window):
    d = HERE / "data/matrices" / day
    rep = {"day": day, "window": window}
    ok = True
    N = lambda t, r, l: load(d, "%s_%s_%s_%s" % (window, t, r, "lka" if l else "nolka"))
    # I1
    viol = {}
    for t in ("static", "p50", "p85"):
        for r in ("unlimited", "max1transfer"):
            viol["lka_on_worse_%s_%s" % (t, r)] = worse(N(t, r, 1), N(t, r, 0))
        for l in (0, 1):
            viol["max1_beats_unlimited_%s_lka%d" % (t, l)] = worse(N(t, "unlimited", l), N(t, "max1transfer", l))
    rep["I1_violations"] = viol
    tol = 1e-6 * N_PAIRS   # boundary artifacts at the walk cap are repaired in aggregate.py; more than this is a real break
    rep["I1_tolerance_pairs"] = tol
    ok &= max(viol.values()) <= tol
    # I2
    s, p50, p85 = N("static", "unlimited", 0), N("p50", "unlimited", 0), N("p85", "unlimited", 0)
    both = lambda a, b: (a != NR) & (b != NR)
    m1, m2 = both(s, p50), both(p50, p85)
    rep["I2"] = {"p50_faster_than_static_share": round(float((p50[m1] < s[m1]).mean()), 4),
                 "p85_faster_than_p50_share": round(float((p85[m2] < p50[m2]).mean()), 4),
                 "p50_minus_static_median_min": float(np.median(p50[m1].astype(int) - s[m1])),
                 "p85_minus_p50_median_min": float(np.median(p85[m2].astype(int) - p50[m2])),
                 "reached_share": {"static": round(float((s != NR).mean()), 4), "p50": round(float((p50 != NR).mean()), 4),
                                   "p85": round(float((p85 != NR).mean()), 4)}}
    # I3
    off, on = N("static", "unlimited", 0).astype(np.int16), N("static", "unlimited", 1).astype(np.int16)
    gain = off - on
    rep["I3_lka_probe"] = {"pairs_improved": int((gain > 0).sum()), "max_gain_min": int(gain.max()),
                           "newly_reached": int(((N("static", "unlimited", 0) == NR) & (N("static", "unlimited", 1) != NR)).sum())}
    ok &= rep["I3_lka_probe"]["pairs_improved"] > 0
    # I4
    w = load(d.parent / "2026-10-02", "morning_walk")   # walking is day- and window-independent; computed once
    m = (w != NR) & (w.T != NR)
    diff = np.abs(w.astype(int) - w.T.astype(int))[m]
    rep["I4_walk_symmetry"] = {"pairs": int(m.sum()), "abs_diff_le_1min_share": round(float((diff <= 1).mean()), 4),
                               "abs_diff_le_3min_share": round(float((diff <= 3).mean()), 4)}
    rep["I1_I3_ok"] = bool(ok)
    json.dump(rep, open(d / ("invariants_%s.json" % window), "w"), indent=1)
    print(json.dumps(rep, indent=1))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
