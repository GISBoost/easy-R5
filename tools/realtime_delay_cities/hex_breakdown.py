"""Hexagon-count breakdown of the delay effect, per city/resolution: how many
hexagons gain / lose / are unchanged / have no baseline -- unweighted counts
next to the population-weighted mean, so it is clear the headline number in
FINDINGS.md is population-weighted and the plain hexagon share is smaller.

`py hex_breakdown.py [city ...]` -- reads delay_<city>[_500m].gpkg (osgeo.ogr).
Writes out/hex_breakdown.csv.
"""

from __future__ import annotations

import csv
import sys

from osgeo import ogr
ogr.UseExceptions()

import pathlib

import cities as C

HERE = pathlib.Path(__file__).resolve().parent
LODZ = HERE.parent / "realtime_delay_lodz"

# Łódź is the pilot and lives in the sibling folder; include it so the write-up's
# hexagon table covers all 6 cities.
CITY_LABEL = {**{k: v[0] for k, v in C.CITIES.items()}, "lodz": "Łódź"}
CITY_RES = {**{k: v[1] for k, v in C.CITIES.items()}, "lodz": (250, 500)}


def gpkg_path(city, res):
    if city == "lodz":
        return LODZ / ("delay_lodz.gpkg" if res == 250 else f"delay_lodz_{res}m.gpkg")
    return HERE / (f"delay_{city}.gpkg" if res == 250 else f"delay_{city}_{res}m.gpkg")


CATS = ("school", "pharmacy", "university", "mall", "net")


def _field(cat):
    return "net_delta" if cat == "net" else f"delta_{cat}"


def _layer(gpkg, cat):
    ds = ogr.Open(str(gpkg))
    return ds, ds.GetLayerByName("hex_net_opportunities" if cat == "net" else "hex_delay")


def breakdown(city, res):
    gpkg = gpkg_path(city, res)
    rows = []
    for cat in CATS:
        ds, lyr = _layer(gpkg, cat)
        f = _field(cat)
        gain = loss = zero = nul = 0
        wsum = wtot = 0.0
        usum = ucount = 0.0
        for feat in lyr:
            v = feat.GetField(f)
            pop = feat.GetField("pop_total") or 0.0
            if v is None:
                nul += 1
                continue
            if v > 0:
                gain += 1
            elif v < 0:
                loss += 1
            else:
                zero += 1
            wsum += pop * v
            wtot += pop
            usum += v
            ucount += 1
        comp = gain + loss + zero
        rows.append({
            "city": CITY_LABEL[city], "resolution_m": res, "metric": cat,
            "hex_total": comp + nul, "comparable": comp, "no_baseline": nul,
            "gain": gain, "loss": loss, "unchanged": zero,
            "gain_pct_of_comparable": round(100 * gain / comp, 1) if comp else None,
            "loss_pct_of_comparable": round(100 * loss / comp, 1) if comp else None,
            "mean_unweighted": round(usum / ucount, 3) if ucount else None,
            "mean_pop_weighted": round(wsum / wtot, 3) if wtot else None,
        })
        ds = None
    return rows


def main(only=None):
    rows = []
    for city in (only or list(C.CITIES) + ["lodz"]):
        for res in CITY_RES[city]:
            rows += breakdown(city, res)
    with open("out/hex_breakdown.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cur = None
    for r in rows:
        if (r["city"], r["resolution_m"]) != cur:
            cur = (r["city"], r["resolution_m"])
            print(f"\n{r['city']} {r['resolution_m']} m   (hex total {r['hex_total']})")
            print(f"  {'metric':10} {'porówn.':>8} {'zysk':>13} {'strata':>13} {'0':>8} {'brak bazy':>10} "
                  f"{'śr.bez wag':>11} {'śr.waż.pop':>11}")
        print(f"  {r['metric']:10} {r['comparable']:>8} "
              f"{r['gain']:>6} ({r['gain_pct_of_comparable'] or 0:>4}%) "
              f"{r['loss']:>6} ({r['loss_pct_of_comparable'] or 0:>4}%) "
              f"{r['unchanged']:>8} {r['no_baseline']:>10} "
              f"{str(r['mean_unweighted']):>11} {str(r['mean_pop_weighted']):>11}")
    print("\n[ok] out/hex_breakdown.csv")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
