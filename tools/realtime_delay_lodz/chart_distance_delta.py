"""Distance-from-population-centre vs. net accessibility change -- a chart
meant to sit next to the hex_delay/hex_net_opportunities maps on a print
board, answering with a number what the maps only suggest with colour: do
delays hurt more near the centre?

Rendering conventions copied from easy-OTP/tools/transit_charts (a sibling
project's chart tooling, matplotlib+pandas, NOT imported -- CLAUDE.md's rule
against importing between projects applies here too, so the relevant bits
are copied, not depended on):
  - `matplotlib.use("Agg")` before any `pyplot` import.
  - Thin, recessive grid (`GRID_KW`), axisbelow.
  - A caption under the axes carrying provenance/caveats in wrapped small text
    -- these PNGs get pasted into documents where the caveats must travel
    with the image, not live only in this docstring.
  - Every figure ships its numbers: `<prefix>.png` + `<prefix>.csv` (the
    exact values plotted) + `<prefix>.json` (params, source fingerprint).

Bar colours reuse style_delay_layers.RDBU7/classify() -- the EXACT same
7-class, zero-isolated legend as the QGIS maps and the web version, so a
reader who has already seen either does not have to learn a new scale.

Must run inside the QGIS Python environment (needs qgis.core to read the
gpkg's geometry), e.g. mcp__qgis__execute_code.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # noqa: E402 -- must precede pyplot

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_delay_layers as sd  # noqa: E402

from qgis.core import QgsVectorLayer  # noqa: E402

HERE = Path(__file__).resolve().parent
RESOLUTIONS = {"250": HERE / "delay_lodz.gpkg", "500": HERE / "delay_lodz_500m.gpkg"}
OUT_DIR = HERE / "out" / "charts"

GRID_KW = dict(alpha=0.25, linewidth=0.6)
BIN_KM = 1.0
MIN_N_WARN = 20  # bins thinner than this get an explicit "n=" flag, not silently trusted
CAPTION_FONTSIZE = 7.5


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def _num_or_none(value):
    """QGIS hands back a QVariant(NULL) for a null field, not Python None --
    pandas/numpy arithmetic chokes on that object silently deep in a groupby,
    so convert at the read boundary instead of at every call site."""
    if value is None or value != value:  # NaN also fails equality with itself
        return None
    try:
        if str(value) == "NULL":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_hexes(gpkg: Path):
    lyr = QgsVectorLayer(f"{gpkg}|layername=hex_net_opportunities", "net", "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Could not load hex_net_opportunities from {gpkg}")
    rows = []
    for f in lyr.getFeatures():
        c = f.geometry().centroid().asPoint()
        rows.append({
            "hex_id": f["hex_id"],
            "pop_total": _num_or_none(f["pop_total"]) or 0.0,
            "net_delta": _num_or_none(f["net_delta"]),
            "x": c.x(), "y": c.y(),
        })
    return pd.DataFrame(rows), lyr.crs()


def _population_centre(df: pd.DataFrame) -> tuple[float, float]:
    """Population-weighted centroid of all hexagons -- "where people actually
    live", not the geometric centre of the (irregularly shaped) city
    boundary, and not a guessed CBD coordinate (CLAUDE.md: nie zgaduj)."""
    total_pop = df.pop_total.sum()
    if total_pop <= 0:
        raise RuntimeError("sum(pop_total) is 0 -- cannot compute a population-weighted centre.")
    cx = (df.x * df.pop_total).sum() / total_pop
    cy = (df.y * df.pop_total).sum() / total_pop
    return cx, cy


def _bin_by_distance(df: pd.DataFrame, cx: float, cy: float, bin_km: float) -> pd.DataFrame:
    df = df.copy()
    df["dist_km"] = ((df.x - cx) ** 2 + (df.y - cy) ** 2) ** 0.5 / 1000.0
    comparable = df[df.net_delta.notna()].copy()
    if comparable.empty:
        raise RuntimeError("no hexagon has a non-null net_delta -- nothing to bin.")

    max_km = comparable.dist_km.max()
    edges = [i * bin_km for i in range(int(max_km // bin_km) + 2)]
    comparable["bin_lo"] = pd.cut(comparable.dist_km, edges, right=False, labels=edges[:-1])
    comparable["bin_lo"] = comparable["bin_lo"].astype(float)

    def _wmean(g):
        w = g.pop_total
        return (g.net_delta * w).sum() / w.sum() if w.sum() > 0 else float("nan")

    stats = (
        comparable.groupby("bin_lo", observed=True)
        .apply(lambda g: pd.Series({
            "n_hex": len(g),
            "total_pop": g.pop_total.sum(),
            "mean_net_delta": _wmean(g),
        }))
        .reset_index()
        .sort_values("bin_lo")
    )
    stats["bin_hi"] = stats.bin_lo + bin_km
    stats["bin_label"] = stats.apply(lambda r: f"{r.bin_lo:g}-{r.bin_hi:g}", axis=1)
    return stats


def render(resolution: str, gpkg: Path, bin_km: float = BIN_KM):
    df, crs = _load_hexes(gpkg)
    cx, cy = _population_centre(df)
    stats = _bin_by_distance(df, cx, cy, bin_km)

    colours = [sd.RDBU7[sd.classify(v)] for v in stats.mean_net_delta]

    fig, ax = plt.subplots(figsize=(11.0, 6.0))
    ax.grid(True, axis="y", **GRID_KW)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#555555", linewidth=0.9)
    ax.margins(y=0.18)  # headroom so the n= labels never collide with the frame

    bars = ax.bar(stats.bin_label, stats.mean_net_delta, color=colours,
                   edgecolor="#808080", linewidth=0.4, width=0.75)

    y_range = float(stats.mean_net_delta.max() - stats.mean_net_delta.min()) or 1.0
    label_offset = 0.03 * y_range
    for bar, n in zip(bars, stats.n_hex):
        n = int(n)
        label = f"n={n}" + (" ⚠" if n < MIN_N_WARN else "")
        y = bar.get_height()
        va = "bottom" if y >= 0 else "top"
        ax.text(bar.get_x() + bar.get_width() / 2, y + (label_offset if y >= 0 else -label_offset),
                label, fontsize=7, color="#555555", ha="center", va=va)

    ax.set_xlabel("distance from population-weighted city centre (km)")
    ax.set_ylabel("pop.-weighted mean net Δ (opportunities)")
    ax.set_title(f"Does the delay penalty grow toward the centre? — Łódź, {resolution} m hex grid")

    thin_bins = int((stats.n_hex < MIN_N_WARN).sum())
    notes = [
        f"2026-08-21, static vs realized-P50 GTFS, 30 min / 07:00-09:00, {resolution} m hex grid "
        f"({len(df)} hexagons total).",
        f"Centre = population-weighted centroid of all hexagons "
        f"(x={cx:.0f}, y={cy:.0f} in {crs.description() or crs.authid()}), not a guessed CBD point.",
        f"Bars are the population-weighted mean net_delta of hexagons whose distance falls in "
        f"that {bin_km:g} km band; a hexagon with no baseline in ANY of the 4 categories has "
        f"net_delta=NULL and is excluded, not zeroed (same rule as the maps).",
        f"Colour reuses the map legend exactly (ColorBrewer RdBu-7, zero-isolated classes).",
    ]
    if thin_bins:
        notes.append(f"⚠ {thin_bins} bin(s) have n < {MIN_N_WARN} hexagons -- read those with caution.")

    import textwrap
    wrapped = []
    for line in notes:
        wrapped.extend(textwrap.wrap(line, width=150) or [""])
    fig.text(0.01, 0.005, "\n".join(wrapped), fontsize=CAPTION_FONTSIZE, color="#555555",
              va="bottom", ha="left")

    bottom = 0.06 + 0.028 * len(wrapped)
    fig.tight_layout(rect=(0, min(bottom, 0.30), 1, 1))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = OUT_DIR / f"distance_vs_net_delta_{resolution}m"
    fig.savefig(prefix.with_suffix(".png"), dpi=150)
    plt.close(fig)

    stats.to_csv(prefix.with_suffix(".csv"), index=False)
    meta = {
        "chart": "distance_vs_net_delta",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolution_m": resolution,
        "source": str(gpkg),
        "source_sha256": _fingerprint(gpkg),
        "source_rows": len(df),
        "options": {"bin_km": bin_km, "min_n_warn": MIN_N_WARN,
                    "centre_xy": [cx, cy], "centre_crs": crs.authid() or crs.description()},
        "notes": notes,
    }
    prefix.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ok] {prefix.name}.png/.csv/.json -- {len(stats)} bins, centre=({cx:.0f},{cy:.0f})")
    for warning in notes:
        if warning.startswith("⚠"):
            print(f"[warn] {warning}")
    return stats


def main():
    for res, gpkg in RESOLUTIONS.items():
        if not gpkg.exists():
            raise RuntimeError(f"{gpkg} missing -- run the local pipeline first.")
        render(res, gpkg)
    print("[done] chart_distance_delta.py finished.")


if __name__ == "__main__":
    main()
