"""Collect run statistics from every completed city/resolution pass into one
table -- a diagnostics sweep over the artifacts the pipeline leaves behind.

Pure stdlib + osgeo.ogr (for gpkg feature counts) -- run with `py`, NOT QGIS:

    py collect_run_stats.py            # every city/resolution found
    py collect_run_stats.py gdansk     # just one city

Reads, per (city, res):
  work/<city>/network_{static,realized_p50}/*/network.json  -- R5 build, feed, gate
  out/acc_<city>_<case>[_500m].csv.meta.json / .params.json -- run params
  delay_<city>[_500m].gpkg                                  -- hex + POI counts
  out/<city>_delay_summary[_500m].csv / _net_summary        -- results
  out/charts/transfer_ring_<city>_<res>m.json               -- hypothesis verdict
  file mtimes                                               -- approx pass durations

Writes out/run_stats.csv (flat, one row per city/res) and out/run_stats.json
(nested), and prints a compact table.
"""

from __future__ import annotations

import csv
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

try:  # Windows console is cp1250 by default; keep prints from crashing
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

try:
    from osgeo import ogr
    ogr.UseExceptions()
except ImportError:  # pragma: no cover
    ogr = None

import cities as C

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
OUT = HERE / "out"
CATEGORIES = ("school", "pharmacy", "university", "mall")


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mtime(p: Path):
    return p.stat().st_mtime if p.exists() else None


def _dur(a, b):
    if a and b and b > a:
        return round(b - a, 1)
    return None


def _network_stats(city, case):
    files = glob.glob(str(WORK / city / f"network_{case}" / "*" / "network.json"))
    j = _load_json(Path(files[0])) if files else None
    if not j:
        return {}
    sd = j.get("service_days") or {}
    return {
        "r5_version": j.get("r5_version"),
        "network_format": j.get("network_format_version"),
        "built_at": j.get("built_at"),
        "stops": j.get("stops"),
        "routes": j.get("routes"),
        "trip_patterns": j.get("trip_patterns"),
        "street_vertices": j.get("street_vertices"),
        "trips_on_date": sd.get(C.ANALYSIS_DATE),
    }


def _gpkg_counts(gpkg: Path):
    if not gpkg.exists() or ogr is None:
        return {}
    ds = ogr.Open(str(gpkg))
    out = {}
    hg = ds.GetLayerByName("hex_grid")
    if hg:
        out["hex_total"] = hg.GetFeatureCount()
        hg.SetAttributeFilter("pop_total > 0")
        out["hex_with_pop"] = hg.GetFeatureCount()
        hg.SetAttributeFilter(None)
        total = 0.0
        for f in hg:
            total += f.GetField("pop_total") or 0.0
        out["pop_total_sum"] = round(total, 1)
    poi = ds.GetLayerByName("poi_targets")
    if poi:
        out["poi_total"] = poi.GetFeatureCount()
        for cat in CATEGORIES:
            poi.SetAttributeFilter(f"srv_{cat} = 1")
            out[f"poi_{cat}"] = poi.GetFeatureCount()
        poi.SetAttributeFilter(None)
    return out


def _read_summary_csv(p: Path):
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as fh:
        return {r["category"]: r for r in csv.DictReader(fh)}


def _read_net_csv(p: Path):
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as fh:
        return next(csv.DictReader(fh), {}) or {}


def collect_one(city, res):
    suf = "" if res == 250 else f"_{res}m"
    gpkg = HERE / f"delay_{city}{suf}.gpkg"
    prep_m = _mtime(gpkg)
    stat_gpkg_m = _mtime(OUT / f"acc_{city}_static{suf}.gpkg")
    real_gpkg_m = _mtime(OUT / f"acc_{city}_realized_p50{suf}.gpkg")

    meta = _load_json(OUT / f"acc_{city}_static{suf}.csv.meta.json") or {}
    net = _network_stats(city, "static")
    net_r = _network_stats(city, "realized_p50")
    gate_ok = net.get("trips_on_date") == net_r.get("trips_on_date")

    delay_sum = _read_summary_csv(OUT / f"{city}_delay_summary{suf}.csv")
    net_sum = _read_net_csv(OUT / f"{city}_net_summary{suf}.csv")
    verdict = (_load_json(OUT / "charts" / f"transfer_ring_{city}_{res}m.json") or {}).get("verdict", {})

    counts = _gpkg_counts(gpkg)
    pop_diff = None
    # cross-check the overlay against the precinct sum recorded nowhere -- skip;
    # prepare_data already gated it. Keep the hex pop sum for eyeballing.

    row = {
        "city": C.CITIES[city][0] if city in C.CITIES else city,
        "city_key": city,
        "resolution_m": res,
        "gate_ok": gate_ok,
        "trips_static": net.get("trips_on_date"),
        "trips_realized": net_r.get("trips_on_date"),
        "r5_version": net.get("r5_version"),
        "network_format": net.get("network_format"),
        "gtfs_stops": net.get("stops"),
        "gtfs_routes": net.get("routes"),
        "trip_patterns": net.get("trip_patterns"),
        "street_vertices": net.get("street_vertices"),
        "hex_total": counts.get("hex_total"),
        "hex_with_pop": counts.get("hex_with_pop"),
        "pop_total_sum": counts.get("pop_total_sum"),
        "poi_total": counts.get("poi_total"),
        **{f"poi_{c}": counts.get(f"poi_{c}") for c in CATEGORIES},
        "net_mean_delta": net_sum.get("mean_net_delta_pop_weighted"),
        "net_hex_comparable": net_sum.get("hexagons_with_value"),
        "net_hex_zero": net_sum.get("hexagons_net_zero"),
        "transfer_ring_dip": verdict.get("dip"),
        "worst_ring_km": verdict.get("worst_ring_km"),
        "worst_ring_mean": verdict.get("worst_mean"),
        "approx_static_pass_s": _dur(prep_m, stat_gpkg_m),
        "approx_realized_pass_s": _dur(stat_gpkg_m, real_gpkg_m),
        "run_departure": meta.get("departure_time"),
        "run_window_min": meta.get("time_window"),
        "run_percentile": meta.get("percentile"),
        "run_modes": meta.get("modes"),
        "completed": bool(net_sum),
    }
    for cat in CATEGORIES:
        d = delay_sum.get(cat, {})
        row[f"delta_{cat}"] = d.get("mean_delta_pop_weighted")
        row[f"comparable_{cat}"] = d.get("hexagons_with_value")
        row[f"zerobase_{cat}"] = d.get("hexagons_zero_baseline")
    return row


def main(only=None):
    rows = []
    targets = [only] if only else list(C.CITIES)
    for city in targets:
        for res in C.CITIES[city][1]:
            r = collect_one(city, res)
            rows.append(r)

    OUT.mkdir(exist_ok=True)
    cols = list(rows[0].keys()) if rows else []
    with open(OUT / "run_stats.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (OUT / "run_stats.json").write_text(
        json.dumps({"generated": datetime.now().isoformat(timespec="seconds"), "runs": rows},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{'city':10} {'res':>4} {'gate':>5} {'trips':>7} {'hex':>6} {'pop-hex':>8} "
          f"{'POI':>5} {'net_d':>8} {'dip':>5} {'stat_s':>7} {'real_s':>7}")
    for r in rows:
        nd = r["net_mean_delta"]
        nd = f"{float(nd):+.3f}" if nd not in (None, "") else "  --  "
        print(f"{r['city_key']:10} {r['resolution_m']:>4} "
              f"{('ok' if r['gate_ok'] else 'FAIL') if r['gate_ok'] is not None else '-':>5} "
              f"{r['trips_static'] or '-':>7} {r['hex_total'] or '-':>6} {r['hex_with_pop'] or '-':>8} "
              f"{r['poi_total'] or '-':>5} {nd:>8} {str(r['transfer_ring_dip']):>5} "
              f"{r['approx_static_pass_s'] or '-':>7} {r['approx_realized_pass_s'] or '-':>7}")
    done = sum(1 for r in rows if r["completed"])
    print(f"\n[ok] {done}/{len(rows)} runs complete -> out/run_stats.csv, out/run_stats.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
