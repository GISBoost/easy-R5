"""Distance-from-population-centre vs. net accessibility change, per city and
resolution -- the transfer-zone hypothesis test.

Hypothesis (Michal): delays degrade reachability most in a *ring* around the
core -- the transfer-dependent belt -- not uniformly and not monotonically
toward the centre. Łódź (realtime_delay_lodz) showed exactly that: a sharp dip
at 2-3 km, an order of magnitude worse than any other 1 km ring, with the
innermost ring mildly positive.

This bins hex_net_opportunities' net_delta by distance from the
population-weighted centroid of all hexagons (not a guessed CBD point),
1 km bands, population-weighted mean per band. Colour + classification reuse
style_delay_layers exactly. Also writes a machine-readable verdict per city
(is there a mid-ring dip? where? how deep vs the surrounding rings?) that
cross_city_summary.py aggregates.

Rendering conventions copied from easy-OTP/tools/transit_charts (copied, not
imported -- CLAUDE.md cross-project rule). Run inside the QGIS Python env.

    import chart_distance_delta as ch; ch.city("gdansk")
"""

from __future__ import annotations

import hashlib
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_delay_layers as sd  # noqa: E402
import cities as C  # noqa: E402
from prepare_data import gpkg_path  # noqa: E402

from qgis.core import QgsVectorLayer  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out" / "charts"
GRID_KW = dict(alpha=0.25, linewidth=0.6)
BIN_KM = 1.0
MIN_N_WARN = 20
CAPTION_FS = 7.5


def _fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def _num(v):
    if v is None or v != v:
        return None
    try:
        return None if str(v) == "NULL" else float(v)
    except (TypeError, ValueError):
        return None


def _load(gpkg: Path):
    lyr = QgsVectorLayer(f"{gpkg}|layername=hex_net_opportunities", "net", "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load hex_net_opportunities from {gpkg}")
    rows = []
    for f in lyr.getFeatures():
        c = f.geometry().centroid().asPoint()
        rows.append({"pop": _num(f["pop_total"]) or 0.0, "net": _num(f["net_delta"]),
                     "x": c.x(), "y": c.y()})
    return rows, lyr.crs()


def _pop_centre(rows):
    tot = sum(r["pop"] for r in rows)
    if tot <= 0:
        raise RuntimeError("sum(pop) is 0 -- cannot weight a centre.")
    return (sum(r["x"] * r["pop"] for r in rows) / tot,
            sum(r["y"] * r["pop"] for r in rows) / tot)


def _bin(rows, cx, cy, bin_km):
    comp = [r for r in rows if r["net"] is not None]
    if not comp:
        raise RuntimeError("no non-null net_delta.")
    for r in comp:
        r["d"] = ((r["x"] - cx) ** 2 + (r["y"] - cy) ** 2) ** 0.5 / 1000.0
    max_km = max(r["d"] for r in comp)
    bands = []
    lo = 0.0
    while lo < max_km:
        g = [r for r in comp if lo <= r["d"] < lo + bin_km]
        w = sum(r["pop"] for r in g)
        mean = sum(r["net"] * r["pop"] for r in g) / w if w > 0 else float("nan")
        bands.append({"lo": lo, "hi": lo + bin_km, "n": len(g), "pop": w, "mean": mean})
        lo += bin_km
    return [b for b in bands if b["n"] > 0]


def _verdict(bands):
    """Is there a mid-ring dip (rings 1-4 km) that is clearly worse than both
    the innermost ring and the outer rings? Returns a dict for aggregation."""
    usable = [b for b in bands if b["n"] >= MIN_N_WARN]
    if len(usable) < 3:
        return {"dip": None, "reason": "too few usable rings"}
    inner = usable[0]["mean"]
    worst = min(usable, key=lambda b: b["mean"])
    others = [b["mean"] for b in usable if b is not worst]
    med_other = sorted(others)[len(others) // 2]
    is_mid = 1.0 <= worst["lo"] <= 4.0
    return {
        "dip": bool(is_mid and worst["mean"] < inner and worst["mean"] < med_other - 0.3),
        "worst_ring_km": f"{worst['lo']:g}-{worst['hi']:g}",
        "worst_mean": round(worst["mean"], 3),
        "inner_ring_mean": round(inner, 3),
        "median_other_ring_mean": round(med_other, 3),
        "worst_minus_median_other": round(worst["mean"] - med_other, 3),
    }


def render(city: str, spacing_m: int):
    display = C.CITIES[city][0]
    gpkg = gpkg_path(city, spacing_m)
    rows, crs = _load(gpkg)
    cx, cy = _pop_centre(rows)
    bands = _bin(rows, cx, cy, BIN_KM)
    verdict = _verdict(bands)

    labels = [f"{b['lo']:g}-{b['hi']:g}" for b in bands]
    means = [b["mean"] for b in bands]
    colours = [sd.RDBU7[sd.classify(v)] for v in means]

    fig, ax = plt.subplots(figsize=(11.0, 6.0))
    ax.grid(True, axis="y", **GRID_KW)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#555555", linewidth=0.9)
    ax.margins(y=0.18)
    bars = ax.bar(labels, means, color=colours, edgecolor="#808080", linewidth=0.4, width=0.75)
    yr = (max(means) - min(means)) or 1.0
    for bar, b in zip(bars, bands):
        lab = f"n={b['n']}" + (" ⚠" if b["n"] < MIN_N_WARN else "")
        y = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                y + (0.03 * yr if y >= 0 else -0.03 * yr),
                lab, fontsize=7, color="#555555", ha="center",
                va="bottom" if y >= 0 else "top")
    ax.set_xlabel("distance from population-weighted city centre (km)")
    ax.set_ylabel("pop.-weighted mean net Δ (opportunities)")
    ax.set_title(f"Transfer-zone test: does the delay penalty peak in a ring? — {display}, {spacing_m} m hex")

    thin = sum(1 for b in bands if b["n"] < MIN_N_WARN)
    notes = [
        f"{C.ANALYSIS_DATE}, static vs realized-P50 GTFS, 30 min / 07:00-09:00, {spacing_m} m hex "
        f"({len(rows)} hexagons).",
        f"Centre = population-weighted centroid of all hexagons (x={cx:.0f}, y={cy:.0f} "
        f"{crs.description() or crs.authid()}), not a guessed CBD point.",
        "Bars: population-weighted mean net_delta of hexagons in that 1 km band; a hexagon with no "
        "baseline in ANY of the 4 categories is excluded, not zeroed.",
        "Colour reuses the map legend exactly (ColorBrewer RdBu-7, zero-isolated classes).",
        f"Verdict: mid-ring dip = {verdict.get('dip')} "
        f"(worst ring {verdict.get('worst_ring_km')} at {verdict.get('worst_mean')}, "
        f"inner ring {verdict.get('inner_ring_mean')}, "
        f"vs median other ring {verdict.get('median_other_ring_mean')}).",
    ]
    if thin:
        notes.append(f"⚠ {thin} band(s) have n < {MIN_N_WARN} -- read with caution.")
    wrapped = []
    for line in notes:
        wrapped.extend(textwrap.wrap(line, width=150) or [""])
    fig.text(0.01, 0.005, "\n".join(wrapped), fontsize=CAPTION_FS, color="#555555", va="bottom")
    fig.tight_layout(rect=(0, min(0.06 + 0.028 * len(wrapped), 0.32), 1, 1))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = OUT_DIR / f"transfer_ring_{city}_{spacing_m}m"
    fig.savefig(prefix.with_suffix(".png"), dpi=150)
    plt.close(fig)

    import csv
    with open(prefix.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["bin_lo_km", "bin_hi_km", "n_hex", "total_pop", "mean_net_delta"])
        for b in bands:
            w.writerow([b["lo"], b["hi"], b["n"], round(b["pop"], 1), b["mean"]])
    meta = {
        "chart": "transfer_ring", "city": city, "resolution_m": spacing_m,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(gpkg), "source_sha256": _fingerprint(gpkg),
        "centre_xy": [cx, cy], "centre_crs": crs.authid() or crs.description(),
        "verdict": verdict, "notes": notes,
    }
    prefix.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] {prefix.name}  dip={verdict.get('dip')}  worst={verdict.get('worst_ring_km')}km")
    return verdict


def city(name: str):
    for res in C.CITIES[name][1]:
        render(name, res)


def everything():
    for name in C.CITIES:
        city(name)
