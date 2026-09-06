"""How far out does a hexagon's access already reach, and does that predict
how much it loses to delays?

chart_distance_delta.py bins hexagons by straight-line distance from ONE
fixed point (the population-weighted city centre). This is a different
question: for THIS hexagon, THIS category, how far away is the farthest
point among the ones it can already reach in 30 min (static schedule)? Call
that the hexagon's "reach radius" for that category. The hypothesis: a hexagon
whose reach radius is large is living close to the 30-minute cutoff -- a
handful of seconds of delay is what it takes to push the farthest, marginal
point out of reach. A hexagon with a small reach radius (amenity right next
door) should be robust to delay.

Reach radius, precisely: `base_<category>` (from hex_delay -- how many points
of that category are reachable in 30 min under the *static* schedule) is a
count, not a distance. So take the N nearest points of that category by
straight-line distance from the hex centroid, where N = base_<category>, and
the radius is the distance to the Nth (farthest of the reachable ones). This
uses only data already on disk (poi_targets, hex_centroids, hex_delay) -- no
new R5 run. It is an approximation: straight-line distance stands in for
network travel time, because RunAccessibility gives a count per cutoff, not a
travel time per destination (that would need RunTravelTimeMatrix instead).
Flag this as a cheap first pass, not a settled measurement -- CLAUDE.md's
"nie zgaduj" applies to over-trusting a proxy as much as to guessing a fact.

Categories vary hugely in POI density (350 pharmacies vs 47 universities), so
this bins by POPULATION-WEIGHTED QUANTILE of radius (equal-population bins),
not fixed-width km bins like chart_distance_delta.py -- a fixed km grid would
leave some categories with mostly-empty bins and others with everything
crammed into the first one.

For "net" (hex_net_opportunities): combined radius = mean of the per-category
radii among the categories that were comparable for that hexagon (same
"skip missing, don't zero" rule as net_delta itself).

Rendering conventions (Agg backend before pyplot, thin recessive grid, wrapped
provenance caption, png+csv+json triple, RDBU7 colours via classify()) copied
from chart_distance_delta.py -- see that file's docstring for the "why".

Must run inside the QGIS Python environment (qgis.core needed to read
geometries from the gpkg).
"""

from __future__ import annotations

import hashlib
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # noqa: E402 -- must precede pyplot

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_delay_layers as sd  # noqa: E402

from qgis.core import QgsCoordinateTransform, QgsProject, QgsVectorLayer  # noqa: E402

HERE = Path(__file__).resolve().parent
RESOLUTIONS = {"250": HERE / "delay_lodz.gpkg", "500": HERE / "delay_lodz_500m.gpkg"}
OUT_DIR = HERE / "out" / "charts"

CATEGORIES = ("school", "pharmacy", "university", "mall")
N_BINS = 10
MIN_N_WARN = 20
GRID_KW = dict(alpha=0.25, linewidth=0.6)
CAPTION_FONTSIZE = 7.5


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def _num_or_none(value):
    """See chart_distance_delta.py's identical helper for why this is needed
    instead of a plain `is None` check on a QGIS attribute value."""
    if value is None or value != value:
        return None
    try:
        if str(value) == "NULL":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_points(gpkg: Path, layername: str, extra_fields: list[str], target_crs=None) -> pd.DataFrame:
    lyr = QgsVectorLayer(f"{gpkg}|layername={layername}", layername, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load {layername} from {gpkg}")
    xform = None
    if target_crs is not None and lyr.crs() != target_crs:
        xform = QgsCoordinateTransform(lyr.crs(), target_crs, QgsProject.instance())
    rows = []
    for f in lyr.getFeatures():
        pt = f.geometry().asPoint()
        if xform is not None:
            pt = xform.transform(pt)
        row = {"x": pt.x(), "y": pt.y()}
        for fld in extra_fields:
            row[fld] = _num_or_none(f[fld])
        rows.append(row)
    return pd.DataFrame(rows)


def _load_hex_delay(gpkg: Path) -> pd.DataFrame:
    lyr = QgsVectorLayer(f"{gpkg}|layername=hex_delay", "hex_delay", "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load hex_delay from {gpkg}")
    rows = []
    for f in lyr.getFeatures():
        row = {"hex_id": f["hex_id"], "pop_total": _num_or_none(f["pop_total"]) or 0.0}
        for cat in CATEGORIES:
            row[f"delta_{cat}"] = _num_or_none(f[f"delta_{cat}"])
            row[f"base_{cat}"] = _num_or_none(f[f"base_{cat}"]) or 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def _load_net(gpkg: Path) -> pd.DataFrame:
    lyr = QgsVectorLayer(f"{gpkg}|layername=hex_net_opportunities", "net", "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load hex_net_opportunities from {gpkg}")
    rows = []
    for f in lyr.getFeatures():
        rows.append({"hex_id": f["hex_id"], "net_delta": _num_or_none(f["net_delta"])})
    return pd.DataFrame(rows)


def _reach_radius_m(hex_xy: np.ndarray, poi_xy: np.ndarray, base_counts: np.ndarray) -> np.ndarray:
    """For each hex, the distance (metres) to the Nth-nearest POI, N=base_counts
    for that hex. NaN where base_counts is 0 (nothing reachable to measure)."""
    if len(poi_xy) == 0:
        return np.full(len(hex_xy), np.nan)
    d2 = ((hex_xy[:, None, :] - poi_xy[None, :, :]) ** 2).sum(axis=2)  # (n_hex, n_poi)
    radius = np.full(len(hex_xy), np.nan)
    max_n = d2.shape[1]
    for i in range(len(hex_xy)):
        n = int(round(base_counts[i]))
        if n <= 0:
            continue
        n = min(n, max_n)
        nearest_sq = np.partition(d2[i], n - 1)[n - 1]
        radius[i] = nearest_sq ** 0.5
    return radius


def _quantile_bin(df: pd.DataFrame, value_col: str, weight_col: str, n_bins: int) -> pd.DataFrame:
    """Equal-COUNT quantile bins on value_col (not equal-population -- pandas.qcut
    bins by rank, which is what we want here: comparable sample size per bin so
    a thin, noisy bin doesn't hide next to a thick, stable one)."""
    d = df.dropna(subset=[value_col]).copy()
    d["bin"] = pd.qcut(d[value_col], q=min(n_bins, d[value_col].nunique()), duplicates="drop")
    stats = []
    for interval, g in d.groupby("bin", observed=True):
        w = g[weight_col]
        wmean = (g["value"] * w).sum() / w.sum() if w.sum() > 0 else float("nan")
        stats.append({
            "radius_lo_km": interval.left / 1000, "radius_hi_km": interval.right / 1000,
            "n_hex": len(g), "total_pop": w.sum(), "mean_delta_pop_weighted": wmean,
        })
    return pd.DataFrame(stats).sort_values("radius_lo_km").reset_index(drop=True)


def render(resolution: str, gpkg: Path):
    hex_delay = _load_hex_delay(gpkg)
    net = _load_net(gpkg)
    centroids_lyr = QgsVectorLayer(f"{gpkg}|layername=hex_centroids", "hex_centroids", "ogr")
    if not centroids_lyr.isValid():
        raise RuntimeError(f"Could not load hex_centroids from {gpkg}")
    hex_crs = centroids_lyr.crs()
    centroids = _load_points(gpkg, "hex_centroids", ["hex_id"], target_crs=hex_crs)
    poi = _load_points(gpkg, "poi_targets", [f"srv_{c}" for c in CATEGORIES], target_crs=hex_crs)

    hex_delay = hex_delay.merge(centroids, on="hex_id", how="left")
    hex_xy = hex_delay[["x", "y"]].to_numpy()

    radii = {}
    for cat in CATEGORIES:
        poi_cat = poi[poi[f"srv_{cat}"] == 1.0]
        poi_xy = poi_cat[["x", "y"]].to_numpy()
        radii[cat] = _reach_radius_m(hex_xy, poi_xy, hex_delay[f"base_{cat}"].to_numpy())
        hex_delay[f"radius_{cat}_m"] = radii[cat]

    # combined radius for "net": mean of the per-category radii that exist
    # (base>0) for that hex -- same "skip missing, don't zero" rule as net_delta
    radius_cols = [f"radius_{c}_m" for c in CATEGORIES]
    hex_delay["radius_net_m"] = hex_delay[radius_cols].mean(axis=1, skipna=True)
    hex_delay = hex_delay.merge(net, on="hex_id", how="left")

    charts = list(CATEGORIES) + ["net"]
    results = {}
    for key in charts:
        value_col = "net_delta" if key == "net" else f"delta_{key}"
        d = hex_delay[["pop_total", value_col, f"radius_{key}_m"]].rename(
            columns={value_col: "value"})
        stats = _quantile_bin(d, f"radius_{key}_m", "pop_total", N_BINS)
        results[key] = stats
        _plot_one(key, resolution, stats, gpkg)
    return results


def _plot_one(key: str, resolution: str, stats: pd.DataFrame, gpkg: Path):
    colours = [sd.RDBU7[sd.classify(v)] for v in stats.mean_delta_pop_weighted]
    labels = [f"{r.radius_lo_km:.1f}-{r.radius_hi_km:.1f}" for r in stats.itertuples()]

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.grid(True, axis="y", **GRID_KW)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#555555", linewidth=0.9)
    ax.margins(y=0.18)

    bars = ax.bar(labels, stats.mean_delta_pop_weighted, color=colours,
                   edgecolor="#808080", linewidth=0.4, width=0.75)
    y_range = float(stats.mean_delta_pop_weighted.max() - stats.mean_delta_pop_weighted.min()) or 1.0
    off = 0.03 * y_range
    for bar, n in zip(bars, stats.n_hex):
        label = f"n={int(n)}" + (" ⚠" if n < MIN_N_WARN else "")
        y = bar.get_height()
        va = "bottom" if y >= 0 else "top"
        ax.text(bar.get_x() + bar.get_width() / 2, y + (off if y >= 0 else -off),
                 label, fontsize=7, color="#555555", ha="center", va=va)

    label_en = {"school": "schools", "pharmacy": "pharmacies", "university": "universities",
                "mall": "malls", "net": "combined"}[key]
    ax.set_xlabel("reach radius -- distance to the farthest reachable point (km)")
    ax.set_ylabel("pop.-weighted mean change in accessibility")
    ax.set_title(f"Does farther-out access lose more to delays? -- {label_en}, {resolution} m")

    notes = [
        "2026-08-21, static vs realized P50 GTFS, 30 min / 07:00-09:00, "
        f"{resolution} m grid. Bins = decile of hexagon count (equal count, not equal km width) "
        "by reach radius (straight-line distance to the Nth-nearest point of the category, "
        "N=base_<category> -- how many points of that category are reachable in 30 min under the static schedule).",
        "This is an approximation: straight-line distance, not network travel time -- the real margin to the "
        "cutoff would need a per-destination travel time matrix (RunTravelTimeMatrix), not just the RunAccessibility count.",
        "Colours match the maps/legend (ColorBrewer RdBu-7, classes isolated at zero).",
    ]
    wrapped = []
    for line in notes:
        wrapped.extend(textwrap.wrap(line, width=150) or [""])
    fig.text(0.01, 0.005, "\n".join(wrapped), fontsize=CAPTION_FONTSIZE, color="#555555",
              va="bottom", ha="left")
    bottom = 0.06 + 0.028 * len(wrapped)
    fig.tight_layout(rect=(0, min(bottom, 0.32), 1, 1))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = OUT_DIR / f"reach_radius_{key}_{resolution}m"
    fig.savefig(prefix.with_suffix(".png"), dpi=150)
    plt.close(fig)

    stats.to_csv(prefix.with_suffix(".csv"), index=False)
    meta = {
        "chart": "reach_radius", "category": key,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolution_m": resolution, "source": str(gpkg), "source_sha256": _fingerprint(gpkg),
        "n_bins": N_BINS, "notes": notes,
    }
    prefix.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] {prefix.name}.png/.csv/.json -- {len(stats)} bins")
    for n, v in zip(stats.n_hex, stats.mean_delta_pop_weighted):
        if n < MIN_N_WARN:
            print(f"[warn] {key}: a bin has only n={int(n)} hexagons -- read with caution")


def main():
    for res, gpkg in RESOLUTIONS.items():
        if not gpkg.exists():
            raise RuntimeError(f"{gpkg} missing -- run the local pipeline first.")
        render(res, gpkg)
    print("[done] chart_reach_radius.py finished.")


if __name__ == "__main__":
    main()
