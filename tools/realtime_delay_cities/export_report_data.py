"""Roll every out/*.csv this analysis produced into one small JSON for the
public write-up at mapy-analizy/badanie-opoznienia/ (a static report page,
charts drawn client-side from this file -- same "fetch a manifest" pattern as
opoznienia-dostepnosc/data/manifest.json).

Pure stdlib. `py export_report_data.py`. Reads:
  out/cross_city_net.csv            net delta + transfer-ring verdict per city/res
  out/hex_breakdown.csv             per-category means + hexagon gain/loss counts
  out/charts/transfer_ring_*.csv    per-1km-ring net delta (Łódź from the sibling)
  out/gtfs_shift_by_traction.csv    AM-peak tram/bus late-vs-early split

Writes ../../../mapy-analizy/badanie-opoznienia/report_data.json.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
LODZ_CHARTS = HERE.parent / "realtime_delay_lodz" / "out" / "charts"
DEST = HERE.parent.parent.parent / "mapy-analizy" / "badanie-opoznienia" / "report_data.json"

# Polish label (as written in the roll-up CSVs) -> (key, city.osm key or None for Łódź)
LABEL2KEY = {
    "Łódź": "lodz", "Gdańsk": "gdansk", "Warszawa": "warszawa",
    "Poznań": "poznan", "Kraków": "krakow", "Szczecin": "szczecin",
}

# Wall-clock per city, measured once from artifact mtimes on 2026-09-09 (FINDINGS.md 3b).
# Historical measurement, not re-derivable -- kept here so the report can show it.
COMPUTE = {
    "szczecin": {"wall": "8m 44s", "seconds": 524},
    "gdansk": {"wall": "13m 03s", "seconds": 783, "note": "networks were cache-warm"},
    "poznan": {"wall": "15m 59s", "seconds": 959},
    "krakow": {"wall": "21m 12s", "seconds": 1272, "note": "most origins + densest network"},
    "warszawa": {"wall": "23m 00s", "seconds": 1380, "note": "500 MB network.dat, 500 m only"},
    "lodz": {"wall": "~12m", "seconds": 720, "note": "the original pilot run"},
}

DATE = {"lodz": "2026-08-21"}
DEFAULT_DATE = "2026-08-24"


def _rows(path):
    with io.open(path, encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


def _f(v):
    if v in ("", None):
        return None
    x = float(v)
    return x if math.isfinite(x) else None


def _rings(key, res):
    if key == "lodz":
        path = LODZ_CHARTS / f"distance_vs_net_delta_{res}m.csv"
        if not path.exists():
            return []
        return [
            {"lo": float(r["bin_lo"]), "hi": float(r["bin_hi"]),
             "pop": float(r["total_pop"]), "n_hex": int(float(r["n_hex"])),
             "mean": _f(r["mean_net_delta"]) or 0.0}
            for r in _rows(path)
        ]
    path = OUT / "charts" / f"transfer_ring_{key}_{res}m.csv"
    if not path.exists():
        return []
    return [
        {"lo": float(r["bin_lo_km"]), "hi": float(r["bin_hi_km"]),
         "pop": float(r["total_pop"]), "n_hex": int(float(r["n_hex"])),
         "mean": float(r["mean_net_delta"])}
        for r in _rows(path)
    ]


def main():
    cities = {}

    for r in _rows(OUT / "cross_city_net.csv"):
        key = LABEL2KEY[r["city"]]
        res = r["resolution_m"]
        c = cities.setdefault(key, {"key": key, "label": r["city"],
                                    "date": DATE.get(key, DEFAULT_DATE),
                                    "compute": COMPUTE.get(key, {}),
                                    "resolutions": {}})
        c["resolutions"][res] = {
            "net": _f(r["mean_net_delta"]),
            "hex_comparable": int(r["hexagons_comparable"]),
            "hex_net_zero": int(r["hexagons_net_zero"]),
            "dip": r["transfer_ring_dip"] == "True",
            "worst_ring_km": r["worst_ring_km"],
            "rings": _rings(key, res),
            "categories": {},
        }

    for r in _rows(OUT / "hex_breakdown.csv"):
        key = LABEL2KEY[r["city"]]
        res = r["resolution_m"]
        block = cities[key]["resolutions"][res]
        rec = {
            "mean": _f(r["mean_pop_weighted"]),
            "mean_unweighted": _f(r["mean_unweighted"]),
            "comparable": int(r["comparable"]),
            "no_baseline": int(r["no_baseline"]),
            "gain": int(r["gain"]),
            "loss": int(r["loss"]),
            "unchanged": int(r["unchanged"]),
        }
        if r["metric"] == "net":
            block["net_unweighted"] = rec["mean_unweighted"]
            block["hex"] = {k: rec[k] for k in ("comparable", "no_baseline", "gain", "loss", "unchanged")}
        else:
            block["categories"][r["metric"]] = rec

    for r in _rows(OUT / "gtfs_shift_by_traction.csv"):
        if r["window"] != "szczyt 7-9" or r["traction"] not in ("tram", "autobus"):
            continue
        key = LABEL2KEY.get(r["city"])
        if not key or key not in cities:
            continue
        cities[key].setdefault("shift_peak", {})[r["traction"]] = {
            "trips": int(r["trips"]),
            "late_pct": float(r["late_pct"]),
            "early_pct": float(r["early_pct"]),
            "median_s": int(r["median_shift_s"]),
        }

    order = ["lodz", "warszawa", "poznan", "szczecin", "gdansk", "krakow"]
    payload = {
        "meta": {
            "generated": dt.date.today().isoformat(),
            "cutoff_min": 30,
            "window": "07:00-09:00",
            "date_lodz": "2026-08-21",
            "date_other": "2026-08-24",
            "categories": [
                {"key": "school", "pl": "szkoły", "en": "schools"},
                {"key": "pharmacy", "pl": "apteki", "en": "pharmacies"},
                {"key": "university", "pl": "uczelnie", "en": "universities"},
                {"key": "mall", "pl": "centra handlowe", "en": "malls"},
            ],
        },
        "cities": [cities[k] for k in order if k in cities],
    }
    def clean(o):
        if isinstance(o, float):
            return o if math.isfinite(o) else None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o

    payload = clean(payload)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[ok] {DEST}  ({len(payload['cities'])} cities)")


if __name__ == "__main__":
    main()
