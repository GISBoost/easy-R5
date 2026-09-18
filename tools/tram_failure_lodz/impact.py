"""Turn accessibility CSVs into impact numbers. Pure stdlib -- no QGIS, no R5.

The rules that matter, all inherited from ../realtime_delay_lodz and kept identical so
the two analyses can be read side by side:

* **Zero-baseline hexagons are excluded, not zeroed.** A hexagon that already reaches 0
  schools in 30 minutes under the normal timetable also has delta = 0 when a line is
  removed, but that is "nothing to lose", not "unaffected". Counting it as a real zero
  dilutes every city-wide mean with the outskirts. delta is None there.
* **Population weighting** everywhere: a hexagon is a container of people, not a vote.
* **net_delta** sums delta over the categories that *are* comparable in that hexagon,
  and records how many went into the sum.

Run standalone for the self-check:  py impact.py
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

CATEGORIES = ("srv_school", "srv_pharmacy", "srv_university", "srv_mall")


def read_accessibility(path):
    """out/acc_<case>.csv -> {hex_id: {category: count}}.

    The algorithm writes one row per (origin, opportunity, percentile, cutoff); this
    analysis runs a single percentile and a single cutoff, so the key is just the pair.
    """
    out = defaultdict(dict)
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["id"]][row["opportunity"]] = float(row["accessibility"])
    return dict(out)


def read_matrix(path):
    """out/centre_<case>.csv -> {hex_id: minutes}. Unreachable origins are absent."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            value = row.get("travel_time_p50") or row.get("travel_time") or row.get("time")
            if value in (None, "", "NA"):
                continue
            out[row["from_id"]] = float(value)
    return out


def deltas(base, scen, categories=CATEGORIES):
    """Per-hexagon delta per category plus net_delta, with the zero-baseline rule."""
    out = {}
    for hid, base_row in base.items():
        scen_row = scen.get(hid, {})
        row = {"net_delta": None, "net_delta_n": 0}
        total, n = 0.0, 0
        for cat in categories:
            b = base_row.get(cat)
            s = scen_row.get(cat)
            if b is None or s is None or b == 0:
                row[cat] = None
                row[f"base_{cat}"] = b
                continue
            row[cat] = s - b
            row[f"base_{cat}"] = b
            total += s - b
            n += 1
        if n:
            row["net_delta"], row["net_delta_n"] = total, n
        out[hid] = row
    return out


def weighted_mean(pairs):
    """pairs = [(value, weight)], skipping None values. None if nothing is comparable."""
    num = den = 0.0
    for value, weight in pairs:
        if value is None or weight is None or weight <= 0:
            continue
        num += value * weight
        den += weight
    return num / den if den else None


def summarise(base, scen, population, categories=CATEGORIES):
    """One row of headline numbers for a case."""
    d = deltas(base, scen, categories)
    pop_of = lambda hid: population.get(hid, 0.0)          # noqa: E731

    row = {
        "hexagons": len(d),
        "population": round(sum(population.get(h, 0.0) for h in d)),
    }
    for cat in categories:
        row[f"mean_{cat}"] = weighted_mean([(d[h][cat], pop_of(h)) for h in d])
        row[f"comparable_{cat}"] = sum(1 for h in d if d[h][cat] is not None)
    row["mean_net"] = weighted_mean([(d[h]["net_delta"], pop_of(h)) for h in d])

    # People who lose something, and people who lose their last one of a category.
    losing = sum(pop_of(h) for h in d if (d[h]["net_delta"] or 0) < 0)
    gaining = sum(pop_of(h) for h in d if (d[h]["net_delta"] or 0) > 0)
    row["pop_losing"] = round(losing)
    row["pop_gaining"] = round(gaining)
    total_pop = sum(pop_of(h) for h in d)
    row["share_losing"] = round(losing / total_pop, 4) if total_pop else None

    for cat in categories:
        cut_off = sum(pop_of(h) for h in d
                      if d[h][cat] is not None
                      and d[h][f"base_{cat}"] > 0
                      and d[h][f"base_{cat}"] + d[h][cat] == 0)
        row[f"pop_cut_off_{cat}"] = round(cut_off)

    # Relative loss, which is what a resident actually feels: -2 of 3 schools is a
    # different event from -2 of 40.
    rel = []
    for h in d:
        b = sum(d[h][f"base_{c}"] or 0 for c in categories)
        delta = d[h]["net_delta"]
        if delta is not None and b > 0:
            rel.append((delta / b, pop_of(h)))
    row["mean_relative"] = weighted_mean(rel)
    return row, d


def rank_leave_one_out(summaries):
    """[(case_id, mean_net)] worst first. Ties broken by population losing."""
    rows = [(case, s) for case, s in summaries.items() if case.startswith("loo_")]
    rows.sort(key=lambda kv: (kv[1]["mean_net"] if kv[1]["mean_net"] is not None else 0,
                              -kv[1]["pop_losing"]))
    return [(case[len("loo_"):], s) for case, s in rows]


def gini(values, weights):
    """Population-weighted Gini of a non-negative distribution. 0 = everyone equal."""
    pairs = sorted((v, w) for v, w in zip(values, weights) if v is not None and w > 0)
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    total_v = sum(v * w for v, w in pairs)
    if total_v <= 0:
        return 0.0
    cum_w = cum_v = 0.0
    area = 0.0
    for v, w in pairs:
        prev_w, prev_v = cum_w, cum_v
        cum_w += w / total_w
        cum_v += v * w / total_v
        area += (cum_w - prev_w) * (cum_v + prev_v) / 2
    return round(1 - 2 * area, 4)


def _demo():
    base = {"a": {"srv_school": 4.0, "srv_mall": 0.0},
            "b": {"srv_school": 2.0, "srv_mall": 1.0},
            "c": {"srv_school": 0.0, "srv_mall": 0.0}}
    scen = {"a": {"srv_school": 2.0, "srv_mall": 0.0},
            "b": {"srv_school": 0.0, "srv_mall": 1.0},
            "c": {"srv_school": 0.0, "srv_mall": 0.0}}
    pop = {"a": 100.0, "b": 100.0, "c": 1000.0}
    cats = ("srv_school", "srv_mall")
    row, d = summarise(base, scen, pop, cats)

    # c has no baseline at all: excluded, not counted as "unaffected"
    assert d["c"]["net_delta"] is None, d["c"]
    # a's mall baseline is 0, so only its school counts
    assert d["a"]["srv_mall"] is None and d["a"]["net_delta_n"] == 1
    assert d["b"]["net_delta_n"] == 2 and d["b"]["net_delta"] == -2.0
    # mean over the 200 people who had anything to lose, not over all 1200
    assert row["mean_net"] == -2.0, row["mean_net"]
    assert row["pop_losing"] == 200 and row["pop_gaining"] == 0
    # b loses its last school; a keeps 2 of 4
    assert row["pop_cut_off_srv_school"] == 100, row
    assert row["pop_cut_off_srv_mall"] == 0
    # relative: a loses 2 of 4, b loses 2 of 3
    assert abs(row["mean_relative"] - statistics.mean([-0.5, -2 / 3])) < 1e-9

    assert gini([1, 1, 1, 1], [1, 1, 1, 1]) == 0.0
    assert gini([0, 0, 0, 4], [1, 1, 1, 1]) > 0.7
    assert weighted_mean([(None, 5), (2.0, 1)]) == 2.0
    assert weighted_mean([]) is None
    print("impact self-check ok")


if __name__ == "__main__":
    _demo()
    print("categories:", ", ".join(CATEGORIES))
    here = Path(__file__).resolve().parent / "out"
    if (here / "acc_baseline.csv").exists():
        b = read_accessibility(here / "acc_baseline.csv")
        print(f"baseline: {len(b)} hexagons, "
              f"median schools in 30 min = "
              f"{statistics.median(v['srv_school'] for v in b.values()):.0f}")
