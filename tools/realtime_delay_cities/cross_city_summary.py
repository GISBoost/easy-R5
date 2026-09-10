"""Roll up every city's per-category and net delay summary + the transfer-zone
verdicts into two comparison tables and one hypothesis verdict.

Pure stdlib, run with `py cross_city_summary.py` after the pipeline + charts.

Reads out/<city>_delay_summary[_500m].csv, out/<city>_net_summary[_500m].csv,
out/charts/transfer_ring_<city>_<res>m.json  (+ the Łódź analysis's
../realtime_delay_lodz/out/city_*_summary*.csv for a 6-city comparison).

Writes:
  out/cross_city_delay.csv   city x resolution x category -> mean delta
  out/cross_city_net.csv     city x resolution -> mean net delta + transfer-ring verdict
  out/HYPOTHESIS.md          the transfer-zone verdict in prose
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cities as C

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CHARTS = OUT / "charts"
LODZ = HERE.parent / "realtime_delay_lodz" / "out"
CATEGORIES = ("school", "pharmacy", "university", "mall")
RES = (250, 500)


def _suffix(res):
    return "" if res == 250 else f"_{res}m"


def _read_delay(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return {r["category"]: r for r in csv.DictReader(fh)}


def _read_net(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return next(csv.DictReader(fh))


def _f(x):
    try:
        return round(float(x), 3)
    except (TypeError, ValueError):
        return None


MIN_N = 20


def _verdict_from_bands(bands):
    """Same rule as chart_distance_delta._verdict, re-implemented here because
    that module needs qgis/matplotlib at import and this script runs under
    plain `py`. bands: list of (lo, n, mean)."""
    usable = [(lo, n, m) for lo, n, m in bands if n >= MIN_N and m == m]
    if len(usable) < 3:
        return {}
    inner = usable[0][2]
    worst = min(usable, key=lambda t: t[2])
    others = sorted(m for t in usable for m in [t[2]] if t is not worst)
    med_other = others[len(others) // 2]
    is_mid = 1.0 <= worst[0] <= 4.0
    return {
        "dip": bool(is_mid and worst[2] < inner and worst[2] < med_other - 0.3),
        "worst_ring_km": f"{worst[0]:g}-{worst[0] + 1:g}",
        "worst_mean": round(worst[2], 3),
        "inner_ring_mean": round(inner, 3),
        "median_other_ring_mean": round(med_other, 3),
        "worst_minus_median_other": round(worst[2] - med_other, 3),
    }


def _verdict_from_csv(path: Path):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    lo_key = "bin_lo_km" if rows and "bin_lo_km" in rows[0] else "bin_lo"
    n_key = "n_hex"
    m_key = "mean_net_delta"
    bands = []
    for r in rows:
        try:
            bands.append((float(r[lo_key]), int(float(r[n_key])), float(r[m_key])))
        except (KeyError, ValueError):
            return {}
    bands.sort()
    return _verdict_from_bands(bands)


def collect():
    delay_rows, net_rows = [], []
    # 5 new cities
    sources = [(c, C.CITIES[c][0], C.CITIES[c][1], OUT, f"{c}_") for c in C.CITIES]
    # Łódź from the sibling analysis (250 + 500, files named city_*_summary*.csv)
    sources.append(("lodz", "Łódź", (250, 500), LODZ, "city_"))

    for city, display, resolutions, base, prefix in sources:
        for res in resolutions:
            d = _read_delay(base / f"{prefix}delay_summary{_suffix(res)}.csv")
            n = _read_net(base / f"{prefix}net_summary{_suffix(res)}.csv")
            if d:
                for cat in CATEGORIES:
                    row = d.get(cat, {})
                    delay_rows.append({
                        "city": display, "resolution_m": res, "category": cat,
                        "mean_delta": _f(row.get("mean_delta_pop_weighted")),
                        "hexagons_comparable": row.get("hexagons_with_value"),
                        "hexagons_zero_baseline": row.get("hexagons_zero_baseline"),
                    })
            v = {}
            if city == "lodz":
                v = _verdict_from_csv(LODZ / "charts" / f"distance_vs_net_delta_{res}m.csv")
            else:
                jp = CHARTS / f"transfer_ring_{city}_{res}m.json"
                if jp.exists():
                    v = json.loads(jp.read_text(encoding="utf-8")).get("verdict", {}) or {}
            if n:
                net_rows.append({
                    "city": display, "resolution_m": res,
                    "mean_net_delta": _f(n.get("mean_net_delta_pop_weighted")),
                    "hexagons_comparable": n.get("hexagons_with_value"),
                    "hexagons_net_zero": n.get("hexagons_net_zero"),
                    "transfer_ring_dip": v.get("dip"),
                    "worst_ring_km": v.get("worst_ring_km"),
                    "worst_ring_mean": v.get("worst_mean"),
                    "inner_ring_mean": v.get("inner_ring_mean"),
                    "worst_minus_median_other": v.get("worst_minus_median_other"),
                })
    return delay_rows, net_rows


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"[ok] {path}  ({len(rows)} rows)")


def write_hypothesis(net_rows):
    lines = [
        "# Transfer-zone hypothesis — verdict",
        "",
        "**Hypothesis.** Real-world transit delays degrade reachability most in a *ring*",
        "around the core (the transfer-dependent belt), not uniformly toward the centre.",
        "Test: population-weighted mean `net_delta` (realized-P50 minus static, 30 min,",
        "07:00-09:00) binned by 1 km distance from each city's population-weighted centroid.",
        "A city 'confirms' if its worst 1 km ring sits at 1-4 km, is worse than the",
        "innermost ring, and is at least 0.3 opportunities below the median of the other rings.",
        "",
        "| City | res | mean net Δ | worst ring | worst mean | inner ring | worst − median(other) | mid-ring dip? |",
        "|---|--:|--:|---|--:|--:|--:|:--:|",
    ]
    confirm = deny = 0
    for r in sorted(net_rows, key=lambda x: (x["city"], x["resolution_m"])):
        dip = r["transfer_ring_dip"]
        mark = "✅" if dip else ("—" if dip is None else "❌")
        if dip is True:
            confirm += 1
        elif dip is False:
            deny += 1
        lines.append(
            f"| {r['city']} | {r['resolution_m']} | {r['mean_net_delta']} | "
            f"{r['worst_ring_km']} | {r['worst_ring_mean']} | {r['inner_ring_mean']} | "
            f"{r['worst_minus_median_other']} | {mark} |"
        )
    lines += [
        "",
        f"**{confirm} city-resolutions confirm the mid-ring dip, {deny} do not.**",
        "",
        "See `out/charts/transfer_ring_<city>_<res>m.png` for the per-city bar charts",
        "and `../realtime_delay_lodz/` for the Łódź original (`distance_vs_net_delta_*`).",
    ]
    (OUT / "HYPOTHESIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] {OUT / 'HYPOTHESIS.md'}  ({confirm} confirm / {deny} deny)")


def main():
    OUT.mkdir(exist_ok=True)
    delay_rows, net_rows = collect()
    write_csv(OUT / "cross_city_delay.csv", delay_rows,
              ["city", "resolution_m", "category", "mean_delta",
               "hexagons_comparable", "hexagons_zero_baseline"])
    write_csv(OUT / "cross_city_net.csv", net_rows,
              ["city", "resolution_m", "mean_net_delta", "hexagons_comparable",
               "hexagons_net_zero", "transfer_ring_dip", "worst_ring_km",
               "worst_ring_mean", "inner_ring_mean", "worst_minus_median_other"])
    write_hypothesis(net_rows)


if __name__ == "__main__":
    main()
