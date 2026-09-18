"""Turn the R5 runs into impact tables and equity reports. No QGIS -- runs anywhere.

Everything this needs is a CSV: the accessibility runs in out/<grid>/ (written either by
run_cases.py inside QGIS or by ci_run.py on a CI runner -- verified byte-identical) and
the frozen grid in inputs/<grid>_hex_ses.csv. That is what lets the analysis finish on a
GitHub Actions runner; only the maps still need QGIS (make_map.py).

Writes into out/<grid>/:

  impact_by_case.csv     one row per failure case: population-weighted mean change, who
                         loses, who is cut off entirely
  loo_ranking.csv        every tram line ranked by measured impact, next to its ex-ante
                         rank from rank_lines.py -- this is what says whether the
                         selection criteria were any good
  osiedla_<case>.csv     the same loss per named neighbourhood, so a result can be stated
                         as "a quarter of Gorniak loses ..." instead of "hexagon 214 ..."
  equity_<case>.html/csv the plugin's own core.equity, split by single-parent share
  hex_impact_<case>.csv  per-hexagon values for make_map.py to join onto the grid

The arithmetic lives in impact.py so it can be checked on its own (py impact.py).

    python compute_impact.py --grid h250
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

import impact                                          # noqa: E402
from easy_r5.core import equity as core_equity         # noqa: E402

INPUTS = HERE / "inputs"
OUT_ROOT = HERE / "out"

CATEGORIES = impact.CATEGORIES
SHORT = {"srv_school": "school", "srv_pharmacy": "pharmacy",
         "srv_university": "university", "srv_mall": "mall"}
EQUITY_CASES = ("baseline", "loo_5", "corridor", "bus", "all_trams",
                "cascade_top3", "cascade_top5")

# The equity split. income_idx is in the data but spans only 2980-3125 PLN across 3854
# precincts (sd 21), so terciles of it separate nothing; the single-parent share runs
# 16-41% and is a far better marker of a household that cannot fall back on a car.
GROUP_FIELD = "single_par"
GROUP_LABEL = {"low": "najmniej samotnych rodziców",
               "mid": "środek",
               "high": "najwięcej samotnych rodziców"}


def out_dir(grid_id):
    d = OUT_ROOT / grid_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def hex_attributes(grid_id):
    """{hex_id: {pop_total, single_par, income_idx, osiedle}} from the frozen grid CSV."""
    path = INPUTS / f"{grid_id}_hex_ses.csv"
    if not path.is_file():
        raise SystemExit(f"missing {path} -- run export_inputs.py in QGIS first")
    attrs = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            attrs[r["hex_id"]] = {
                "pop_total": _f(r.get("population")) or 0.0,
                "single_par": _f(r.get("single_par")),
                "income_idx": _f(r.get("income_idx")),
                "osiedle": (r.get("osiedle") or "").strip() or None,
            }
    print(f"[ok] {grid_id}: {len(attrs)} hexagons from {path.name}")
    return attrs


def ses_terciles(attrs, field=GROUP_FIELD):
    """Population-weighted terciles of a census rate -> {hex_id: 'low'|'mid'|'high'}.

    Split on the *people*, not on the hexagons: a tercile is a third of the city's
    residents, so the three groups are directly comparable as populations.
    """
    rows = sorted((r[field], r["pop_total"]) for r in attrs.values()
                  if r.get(field) is not None and r["pop_total"] > 0)
    total = sum(pop for _, pop in rows)
    cuts, cum = [], 0.0
    for value, pop in rows:
        cum += pop
        if len(cuts) == 0 and cum >= total / 3:
            cuts.append(value)
        elif len(cuts) == 1 and cum >= 2 * total / 3:
            cuts.append(value)
    if len(cuts) < 2:
        raise SystemExit(f"could not split {field} into terciles")
    out = {}
    for hid, r in attrs.items():
        v = r.get(field)
        out[hid] = (None if v is None
                    else "low" if v <= cuts[0]
                    else "mid" if v <= cuts[1] else "high")
    print(f"[ok] {field} terciles at {cuts[0]:.1f} / {cuts[1]:.1f}")
    return out, cuts


def available_cases(grid_id):
    return sorted(p.name[len("acc_"):-len(".csv")] for p in out_dir(grid_id).glob("acc_*.csv")
                  if p.name.endswith(".csv") and ".csv." not in p.name)


def osiedle_table(d, population, osiedle_of, path):
    """Per-neighbourhood loss: how many residents live there and how many lose something.

    The share is of the neighbourhood's *comparable* population -- people in hexagons that
    had something to lose -- so it answers "of the people here who could reach a school,
    what fraction now reaches fewer".
    """
    agg = {}
    for hid, row in d.items():
        name = osiedle_of.get(hid)
        if not name:
            continue
        pop = population.get(hid, 0.0)
        a = agg.setdefault(name, {"pop": 0.0, "pop_cmp": 0.0, "pop_lose": 0.0,
                                  "num": 0.0, "base": 0.0})
        a["pop"] += pop
        if row["net_delta"] is None:
            continue
        a["pop_cmp"] += pop
        a["num"] += row["net_delta"] * pop
        a["base"] += sum(row[f"base_{c}"] or 0 for c in CATEGORIES) * pop
        if row["net_delta"] < 0:
            a["pop_lose"] += pop

    rows = []
    for name, a in agg.items():
        mean = a["num"] / a["pop_cmp"] if a["pop_cmp"] else None
        rows.append({
            "osiedle": name,
            "population": round(a["pop"]),
            "population_comparable": round(a["pop_cmp"]),
            "pop_losing": round(a["pop_lose"]),
            "share_losing": round(a["pop_lose"] / a["pop_cmp"], 4) if a["pop_cmp"] else None,
            "mean_net": round(mean, 3) if mean is not None else None,
            "mean_relative": (round(a["num"] / a["base"], 4) if a["base"] else None),
        })
    if not rows:
        return []
    rows.sort(key=lambda r: r["mean_net"] if r["mean_net"] is not None else 0)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def equity_report(records, case_id, grid_id, method):
    """core.equity -- the same code easyr5:summarizeaccessibilityequity wraps."""
    out = out_dir(grid_id)
    fields = [f"scen_{SHORT[c]}" for c in CATEGORIES]
    rows = core_equity.summarize_layer(records, "pop_total", fields, 1.0,
                                       group_field="group")
    if not rows:
        return
    with open(out / f"equity_{case_id}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    html = core_equity.render_html(rows, 1.0, method,
                                   title=f"Równość dostępu — {case_id} ({grid_id})")
    (out / f"equity_{case_id}.html").write_text(html, encoding="utf-8")
    print(f"[ok] equity report for {case_id}")


def write_hex_csv(rows, path):
    if not rows:
        return
    fields = ["hex_id"] + [k for k in next(iter(rows.values()))]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for hid, r in sorted(rows.items(), key=lambda kv: int(kv[0])):
            w.writerow([hid] + ["" if r.get(k) is None else r.get(k) for k in fields[1:]])


def main(grid_id="h1000"):
    out = out_dir(grid_id)
    attrs = hex_attributes(grid_id)
    population = {hid: r["pop_total"] for hid, r in attrs.items()}
    osiedle_of = {hid: r["osiedle"] for hid, r in attrs.items()}
    groups, cuts = ses_terciles(attrs)

    base_path = out / "acc_baseline.csv"
    if not base_path.is_file():
        raise SystemExit(f"missing {base_path} -- run ci_run.py or run_cases.py first")
    base = impact.read_accessibility(base_path)
    cases = [c for c in available_cases(grid_id) if c != "baseline"]
    print(f"[info] {grid_id}: {len(cases)} cases besides baseline")

    summaries, per_case_rows = {}, {}
    for case in cases:
        scen = impact.read_accessibility(out / f"acc_{case}.csv")
        row, d = impact.summarise(base, scen, population)
        row["case"] = case
        summaries[case] = row
        per_case_rows[case] = (scen, d)

    # --- travel time to the centre, and direct (no-transfer) reach ------------
    base_centre = (impact.read_matrix(out / "centre_baseline.csv")
                   if (out / "centre_baseline.csv").is_file() else {})
    base_direct = (impact.read_accessibility(out / "direct_baseline.csv")
                   if (out / "direct_baseline.csv").is_file() else {})
    for case in cases:
        s = summaries[case]
        cpath = out / f"centre_{case}.csv"
        if base_centre and cpath.is_file():
            scen_centre = impact.read_matrix(cpath)
            pairs, lost = [], 0.0
            for hid, b in base_centre.items():
                pop = population.get(hid, 0.0)
                if hid in scen_centre:
                    pairs.append((scen_centre[hid] - b, pop))
                else:
                    lost += pop           # centre no longer reachable at all
            s["centre_minutes_delta"] = impact.weighted_mean(pairs)
            s["pop_centre_unreachable"] = round(lost)
        dpath = out / f"direct_{case}.csv"
        if base_direct and dpath.is_file():
            scen_direct = impact.read_accessibility(dpath)
            drow, _ = impact.summarise(base_direct, scen_direct, population)
            s["direct_mean_net"] = drow["mean_net"]
            s["direct_pop_losing"] = drow["pop_losing"]

    # --- tables ---------------------------------------------------------------
    field_order = ["case", "hexagons", "population", "mean_net", "mean_relative",
                   "pop_losing", "pop_gaining", "share_losing",
                   "centre_minutes_delta", "pop_centre_unreachable",
                   "direct_mean_net", "direct_pop_losing"]
    field_order += [f"mean_{c}" for c in CATEGORIES]
    field_order += [f"pop_cut_off_{c}" for c in CATEGORIES]
    field_order += [f"comparable_{c}" for c in CATEGORIES]
    with open(out / "impact_by_case.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=field_order, extrasaction="ignore")
        w.writeheader()
        for case in sorted(summaries, key=lambda c: summaries[c]["mean_net"] or 0):
            w.writerow(summaries[case])

    ranking = impact.rank_leave_one_out(summaries)
    ex_ante_path = INPUTS / "tram_lines.csv"
    ex_ante = ({r["line"]: r for r in csv.DictReader(open(ex_ante_path, encoding="utf-8"))}
               if ex_ante_path.is_file() else {})
    with open(out / "loo_ranking.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["measured_rank", "line", "mean_net", "pop_losing", "share_losing",
                    "ex_ante_score", "ex_ante_rank_pop", "ex_ante_rank_veh_km",
                    "meets_length", "pop_500m", "veh_km", "length_km"])
        for i, (line, s) in enumerate(ranking, 1):
            e = ex_ante.get(line, {})
            w.writerow([i, line, round(s["mean_net"], 4) if s["mean_net"] else 0,
                        s["pop_losing"], s["share_losing"], e.get("score"),
                        e.get("rank_pop"), e.get("rank_veh_km"), e.get("meets_length"),
                        e.get("pop_500m"), e.get("veh_km"), e.get("length_km")])
    print(f"[ok] {grid_id} worst lines:", ", ".join(line for line, _ in ranking[:5]))

    # --- per-hexagon output, neighbourhoods, equity ----------------------------
    # core.equity.render_html renders the method as a dict of label -> value, the same
    # shape the plugin passes it (the run's meta fields).
    method = {"siatka": grid_id, "data": "2026-08-21", "odjazd": "07:00",
              "okno": "120 min", "percentyl": "50", "próg": "30 min",
              "grupowanie": f"{GROUP_FIELD}, tercyle ważone populacją"}

    def records_for(values, d=None):
        recs = []
        for hid, a in attrs.items():
            rec = {"hex_id": hid, "pop_total": a["pop_total"], "group": groups.get(hid),
                   "osiedle": a["osiedle"], "single_par": a["single_par"],
                   "income_idx": a["income_idx"]}
            for cat in CATEGORIES:
                rec[f"scen_{SHORT[cat]}"] = values.get(hid, {}).get(cat)
            if d is not None and hid in d:
                dr = d[hid]
                rec["net_delta"] = dr["net_delta"]
                rec["net_delta_n"] = dr["net_delta_n"]
                for cat in CATEGORIES:
                    rec[f"delta_{SHORT[cat]}"] = dr[cat]
                    rec[f"base_{SHORT[cat]}"] = dr[f"base_{cat}"]
            recs.append(rec)
        return recs

    for case in cases:
        scen, d = per_case_rows[case]
        osiedle_table(d, population, osiedle_of, out / f"osiedla_{case}.csv")
        if case not in EQUITY_CASES:
            continue
        recs = records_for(scen, d)
        write_hex_csv({r["hex_id"]: {k: v for k, v in r.items() if k != "hex_id"}
                       for r in recs}, out / f"hex_impact_{case}.csv")
        equity_report(recs, case, grid_id, method)

    recs = records_for(base)
    write_hex_csv({r["hex_id"]: {k: v for k, v in r.items() if k != "hex_id"}
                   for r in recs}, out / "hex_impact_baseline.csv")
    equity_report(recs, "baseline", grid_id, method)

    meta = {"grid_id": grid_id, "group_field": GROUP_FIELD,
            "group_tercile_cuts": [round(c, 1) for c in cuts],
            "group_labels": GROUP_LABEL,
            "cases": len(cases), "categories": list(CATEGORIES),
            "worst_lines": [line for line, _ in ranking[:5]]}
    (out / "impact.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    print("[done]", json.dumps(meta, ensure_ascii=False))
    return summaries, ranking


def compute_all(grid_ids=("h250", "h500", "h1000", "h500off")):
    return {g: main(g) for g in grid_ids
            if (OUT_ROOT / g / "acc_baseline.csv").is_file()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--grid", default=None, help="grid id; omit for every grid present")
    a = ap.parse_args()
    if a.grid:
        main(a.grid)
    else:
        compute_all()
