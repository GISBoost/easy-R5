"""Is the answer an artefact of the grid? (MAUP). Plain Python -- no QGIS, no R5.

The modifiable areal unit problem has two halves and they are separate questions:

  scale   -- does the answer change when the cells get bigger?  h250 vs h500 vs h1000
  zoning  -- does it change when cells of the SAME size are drawn in a different place?
             h500 vs h500off, which is the same 500 m lattice shifted half a cell

Most write-ups test only the first and call it MAUP. Testing the second is what separates
"my numbers moved because I aggregated" from "my numbers moved because I happened to draw
the lines here".

Three things are checked, in rising order of how much they matter to the conclusions:

  1. the city-wide magnitudes (mean loss, share of residents losing) -- expected to move,
     because averaging over bigger cells smooths a corridor-shaped loss;
  2. the leave-one-out RANKING of the 21 tram lines -- the actual claim of the analysis
     ("line 5 matters most"), which should survive if it means anything;
  3. the per-neighbourhood results -- osiedla are fixed real geography, identical across
     all four grids, so if those agree the reported statements are grid-independent even
     where the hexagon numbers are not.

Run:  py maup.py
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MAUP = OUT / "maup"

GRIDS = ("h250", "h500", "h1000", "h500off")
SCALE_GRIDS = ("h250", "h500", "h1000")
ZONING_PAIR = ("h500", "h500off")
LABEL = {"h250": "250 m", "h500": "500 m", "h1000": "1000 m",
         "h500off": "500 m przesunięta"}


def _rows(grid, name):
    path = OUT / grid / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def spearman(a, b):
    """Rank correlation of two equal-length sequences. 1 = same order, 0 = unrelated."""
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        out = [0.0] * len(xs)
        i = 0
        while i < len(order):            # average ranks within ties
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            shared = (i + j) / 2
            for k in range(i, j + 1):
                out[order[k]] = shared
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


def city_by_grid():
    """One row per (case, grid): the headline city-wide numbers."""
    rows = []
    for grid in GRIDS:
        for r in _rows(grid, "impact_by_case.csv"):
            rows.append({"grid": grid, "spacing_label": LABEL[grid], "case": r["case"],
                         "mean_net": _f(r["mean_net"]), "mean_relative": _f(r["mean_relative"]),
                         "pop_losing": _f(r["pop_losing"]), "share_losing": _f(r["share_losing"])})
    return rows


def ranking_by_grid():
    """{grid: {line: (rank, mean_net)}} from each grid's leave-one-out pass."""
    out = {}
    for grid in GRIDS:
        rows = _rows(grid, "loo_ranking.csv")
        if rows:
            out[grid] = {r["line"]: (int(r["measured_rank"]), _f(r["mean_net"]))
                         for r in rows}
    return out


def ranking_agreement(rankings):
    """Pairwise Spearman on the line ranking, plus top-1 and top-5 agreement."""
    pairs = []
    grids = [g for g in GRIDS if g in rankings]
    for i, a in enumerate(grids):
        for b in grids[i + 1:]:
            lines = sorted(set(rankings[a]) & set(rankings[b]))
            if len(lines) < 3:
                continue
            rho = spearman([rankings[a][ln][0] for ln in lines],
                           [rankings[b][ln][0] for ln in lines])
            top_a = [ln for ln in sorted(rankings[a], key=lambda x: rankings[a][x][0])][:5]
            top_b = [ln for ln in sorted(rankings[b], key=lambda x: rankings[b][x][0])][:5]
            pairs.append({
                "grid_a": a, "grid_b": b,
                "kind": "zoning" if {a, b} == set(ZONING_PAIR) else "scale",
                "lines": len(lines), "spearman": round(rho, 3),
                "same_worst_line": top_a[0] == top_b[0],
                "top5_shared": len(set(top_a) & set(top_b)),
                "top5_a": " ".join(top_a), "top5_b": " ".join(top_b),
            })
    return pairs


def osiedla_by_grid(case="loo_5"):
    """{osiedle: {grid: row}} -- the same real neighbourhoods measured on four grids."""
    out = {}
    for grid in GRIDS:
        for r in _rows(grid, f"osiedla_{case}.csv"):
            out.setdefault(r["osiedle"], {})[grid] = {
                "population": _f(r["population"]),
                "share_losing": _f(r["share_losing"]),
                "mean_net": _f(r["mean_net"]),
                "mean_relative": _f(r["mean_relative"]),
            }
    return out


def osiedla_stability(per_osiedle, key="share_losing"):
    """How far apart the grids are for each neighbourhood, and overall."""
    rows = []
    for name, by_grid in per_osiedle.items():
        vals = {g: d[key] for g, d in by_grid.items() if d.get(key) is not None}
        if len(vals) < 2:
            continue
        scale_vals = [v for g, v in vals.items() if g in SCALE_GRIDS]
        zoning = [vals[g] for g in ZONING_PAIR if g in vals]
        rows.append({
            "osiedle": name,
            "population": round(max(d["population"] or 0 for d in by_grid.values())),
            **{f"{key}_{g}": (round(vals[g], 4) if g in vals else None) for g in GRIDS},
            "spread_scale": (round(max(scale_vals) - min(scale_vals), 4)
                             if len(scale_vals) > 1 else None),
            "spread_zoning": round(abs(zoning[0] - zoning[1]), 4) if len(zoning) == 2 else None,
        })
    rows.sort(key=lambda r: -(r.get(f"{key}_h250") or 0))
    return rows


def main(case="loo_5"):
    MAUP.mkdir(parents=True, exist_ok=True)

    city = city_by_grid()
    if not city:
        raise RuntimeError("no impact_by_case.csv found -- run compute_impact first")
    with open(MAUP / "city_by_grid.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(city[0]))
        w.writeheader()
        w.writerows(city)

    rankings = ranking_by_grid()
    lines = sorted(set().union(*(set(v) for v in rankings.values())))
    with open(MAUP / "ranking_by_grid.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["line"] + [f"rank_{g}" for g in GRIDS]
                   + [f"mean_net_{g}" for g in GRIDS])
        for ln in lines:
            w.writerow([ln]
                       + [rankings.get(g, {}).get(ln, ("", ""))[0] for g in GRIDS]
                       + [rankings.get(g, {}).get(ln, ("", ""))[1] for g in GRIDS])

    agreement = ranking_agreement(rankings)
    if agreement:
        with open(MAUP / "ranking_agreement.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(agreement[0]))
            w.writeheader()
            w.writerows(agreement)

    per_osiedle = osiedla_by_grid(case)
    stability = osiedla_stability(per_osiedle) if per_osiedle else []
    if stability:
        with open(MAUP / f"osiedla_by_grid_{case}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(stability[0]))
            w.writeheader()
            w.writerows(stability)

    # --- the verdict, in numbers a reader can check --------------------------
    by_case = {}
    for r in city:
        by_case.setdefault(r["case"], {})[r["grid"]] = r

    def spread(case_id, key):
        vals = {g: by_case.get(case_id, {}).get(g, {}).get(key) for g in SCALE_GRIDS}
        vals = {g: v for g, v in vals.items() if v is not None}
        return vals

    scale_pairs = [p for p in agreement if p["kind"] == "scale"]
    zoning_pairs = [p for p in agreement if p["kind"] == "zoning"]
    summary = {
        "grids": {g: LABEL[g] for g in GRIDS},
        "case_examined": case,
        "city_mean_net_by_grid": spread(case, "mean_net"),
        "city_share_losing_by_grid": spread(case, "share_losing"),
        "city_mean_relative_by_grid": spread(case, "mean_relative"),
        "ranking_spearman_scale": [p["spearman"] for p in scale_pairs],
        "ranking_spearman_zoning": [p["spearman"] for p in zoning_pairs],
        "same_worst_line_everywhere": all(p["same_worst_line"] for p in agreement),
        "top5_shared_min": min((p["top5_shared"] for p in agreement), default=None),
        "osiedla_compared": len(stability),
        "osiedla_share_spread_scale_median": (
            round(statistics.median(r["spread_scale"] for r in stability
                                    if r["spread_scale"] is not None), 4) if stability else None),
        "osiedla_share_spread_zoning_median": (
            round(statistics.median(r["spread_zoning"] for r in stability
                                    if r["spread_zoning"] is not None), 4) if stability else None),
    }
    (MAUP / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")

    print(f"--- MAUP, przypadek {case}")
    for key in ("city_mean_net_by_grid", "city_share_losing_by_grid"):
        print(f"  {key}: " + ", ".join(f"{LABEL[g]}={v:.4f}" for g, v in summary[key].items()))
    for p in agreement:
        print(f"  {p['kind']:6} {LABEL[p['grid_a']]:>16} vs {LABEL[p['grid_b']]:<16} "
              f"spearman={p['spearman']:+.3f} ta sama najgorsza={p['same_worst_line']} "
              f"wspólne z top5={p['top5_shared']}/5")
    print(f"  osiedla: {summary['osiedla_compared']}, mediana rozrzutu udziału tracących — "
          f"skala {summary['osiedla_share_spread_scale_median']}, "
          f"zonowanie {summary['osiedla_share_spread_zoning_median']}")
    print("[done] ->", MAUP)
    return summary


def _demo():
    assert abs(spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [1, 1, 1, 1])) < 1e-9      # no variance -> 0
    assert abs(spearman([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) - 0.8) < 1e-9
    rows = osiedla_stability({"A": {"h250": {"population": 10, "share_losing": 0.5},
                                    "h1000": {"population": 10, "share_losing": 0.3},
                                    "h500": {"population": 10, "share_losing": 0.4},
                                    "h500off": {"population": 10, "share_losing": 0.42}}})
    assert rows[0]["spread_scale"] == 0.2 and rows[0]["spread_zoning"] == 0.02, rows
    print("maup self-check ok")


if __name__ == "__main__":
    _demo()
    main()
