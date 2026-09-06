"""Vertical loss/gain/no-change population profile -- a companion chart meant
to sit in the print board's side margin: tall & narrow, unlike
chart_distance_delta's landscape bar chart. One 100%-stacked column per
destination category (+ the "Zbiorczo" net column), split by the population
living in hexagons that net LOSE reachable points to delays (red, bottom),
stay unchanged (pale grey, middle), or GAIN (blue, top) -- same three-way
split already used to answer "ile zbiorczo tracimy" by hand, now drawn.

Rendering conventions copied from chart_distance_delta.py (Agg backend before
pyplot, thin recessive grid, wrapped provenance caption, png+csv+json
triple) -- same rules, see that file's docstring for the "why". Colours reuse
style_delay_layers.RDBU7 exactly (index 1 = red, 3 = pale grey/zero, 5 =
blue), so this reads on the same scale as the maps and the distance chart.

Must run inside the QGIS Python environment (qgis.core needed only to read
pop_total/delta_*/net_delta from the gpkg).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_delay_layers as sd  # noqa: E402

from qgis.core import QgsVectorLayer  # noqa: E402

HERE = Path(__file__).resolve().parent
RESOLUTIONS = {"250": HERE / "delay_lodz.gpkg", "500": HERE / "delay_lodz_500m.gpkg"}
OUT_DIR = HERE / "out" / "charts"

CATEGORIES = ("school", "pharmacy", "university", "mall")
LABELS = {
    "pl": {"school": "Szkoly", "pharmacy": "Apteki", "university": "Uczelnie",
           "mall": "C. handl.", "net": "Zbiorczo"},
    "en": {"school": "Schools", "pharmacy": "Pharmacies", "university": "Universities",
           "mall": "Malls", "net": "Combined"},
}
LEGEND_LABELS = {
    "pl": ["strata netto", "bez zmian", "zysk netto"],
    "en": ["net loss", "no change", "net gain"],
}
YLABEL = {"pl": "udzial ludnosci (%)", "en": "share of population (%)"}
ORDER = ["school", "pharmacy", "university", "mall", "net"]

LOSS_COLOR, ZERO_COLOR, GAIN_COLOR = "#c55260", sd.RDBU7[3], "#598cc1"
GRID_KW = dict(alpha=0.25, linewidth=0.6)


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


def _band_populations(gpkg: Path) -> dict:
    """key -> (pop_loss, pop_zero, pop_gain, n_loss, n_zero, n_gain)."""
    bands = {}

    net_lyr = QgsVectorLayer(f"{gpkg}|layername=hex_net_opportunities", "net", "ogr")
    if not net_lyr.isValid():
        raise RuntimeError(f"Could not load hex_net_opportunities from {gpkg}")
    loss = zero = gain = 0.0
    n_loss = n_zero = n_gain = 0
    for f in net_lyr.getFeatures():
        v = _num_or_none(f["net_delta"])
        if v is None:
            continue
        pop = _num_or_none(f["pop_total"]) or 0.0
        if v < 0:
            loss += pop; n_loss += 1
        elif v > 0:
            gain += pop; n_gain += 1
        else:
            zero += pop; n_zero += 1
    bands["net"] = (loss, zero, gain, n_loss, n_zero, n_gain)

    delay_lyr = QgsVectorLayer(f"{gpkg}|layername=hex_delay", "delay", "ogr")
    if not delay_lyr.isValid():
        raise RuntimeError(f"Could not load hex_delay from {gpkg}")
    per_cat = {c: [0.0, 0.0, 0.0, 0, 0, 0] for c in CATEGORIES}
    for f in delay_lyr.getFeatures():
        pop = _num_or_none(f["pop_total"]) or 0.0
        for c in CATEGORIES:
            v = _num_or_none(f[f"delta_{c}"])
            if v is None:
                continue
            row = per_cat[c]
            if v < 0:
                row[0] += pop; row[3] += 1
            elif v > 0:
                row[2] += pop; row[5] += 1
            else:
                row[1] += pop; row[4] += 1
    for c in CATEGORIES:
        bands[c] = tuple(per_cat[c])
    return bands


def render(resolution: str, gpkg: Path, lang: str = "pl"):
    bands = _band_populations(gpkg)
    labels = LABELS[lang]

    fig, ax = plt.subplots(figsize=(3.6, 9.5))
    ax.grid(True, axis="y", **GRID_KW)
    ax.set_axisbelow(True)

    x = list(range(len(ORDER)))
    width = 0.62
    csv_rows = []
    for i, key in enumerate(ORDER):
        loss, zero, gain, n_loss, n_zero, n_gain = bands[key]
        total = loss + zero + gain
        if total <= 0:
            continue
        loss_pct, zero_pct, gain_pct = loss / total * 100, zero / total * 100, gain / total * 100
        ax.bar(i, loss_pct, width, bottom=0, color=LOSS_COLOR, edgecolor="#808080", linewidth=0.4)
        ax.bar(i, zero_pct, width, bottom=loss_pct, color=ZERO_COLOR, edgecolor="#808080", linewidth=0.4)
        ax.bar(i, gain_pct, width, bottom=loss_pct + zero_pct, color=GAIN_COLOR, edgecolor="#808080", linewidth=0.4)

        if loss_pct > 6:
            ax.text(i, loss_pct / 2, f"{loss_pct:.0f}%", ha="center", va="center", fontsize=8, color="white")
        if gain_pct > 6:
            ax.text(i, loss_pct + zero_pct + gain_pct / 2, f"{gain_pct:.0f}%",
                     ha="center", va="center", fontsize=8, color="white")
        ax.text(i, 100.8, f"n={n_loss + n_zero + n_gain}", ha="center", va="bottom",
                 fontsize=6, color="#555555")

        csv_rows.append(dict(category=key, pop_loss=loss, pop_zero=zero, pop_gain=gain,
                               pop_loss_pct=loss_pct, pop_zero_pct=zero_pct, pop_gain_pct=gain_pct,
                               n_loss=n_loss, n_zero=n_zero, n_gain=n_gain))


    ax.set_xticks(x)
    ax.set_xticklabels([labels[k] for k in ORDER], fontsize=6.5)
    ax.set_ylim(0, 104)
    ax.set_ylabel(YLABEL[lang], fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    # no title, no provenance caption -- this chart sits directly on the
    # print board, which already carries its own header/footer/caption

    handles = [plt.Rectangle((0, 0), 1, 1, color=LOSS_COLOR),
               plt.Rectangle((0, 0), 1, 1, color=ZERO_COLOR),
               plt.Rectangle((0, 0), 1, 1, color=GAIN_COLOR)]
    ax.legend(handles, LEGEND_LABELS[lang],
              loc="upper center", bbox_to_anchor=(0.5, -0.06), fontsize=7.5, frameon=False, ncol=1)

    fig.tight_layout()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if lang == "pl" else f"_{lang}"
    prefix = OUT_DIR / f"loss_gain_profile_{resolution}m{suffix}"
    fig.savefig(prefix.with_suffix(".png"), dpi=400, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)

    import csv
    with open(prefix.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
        w.writeheader()
        w.writerows(csv_rows)

    meta = {
        "chart": "loss_gain_profile",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolution_m": resolution,
        "source": str(gpkg),
        "source_sha256": _fingerprint(gpkg),
        "note": "30 min / 07:00-09:00, statyczny vs zrealizowany P50 GTFS, 2026-08-21. "
                 "Slupek = populacja w heksagonach porownywalnych dla tej kategorii "
                 "(base0 wykluczone), 100% = cala ta populacja. n = liczba heksagonow.",
    }
    prefix.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ok] {prefix.name}.png/.csv/.json")
    return csv_rows


def render_strip(resolution: str, gpkg: Path):
    """Just the 'Zbiorczo' (net) band, alone -- a single narrow strip with no
    title and no provenance caption, for embedding directly in the print
    board's side margin where those would be redundant with the board's own
    header/footer. Segments are labelled in place (strata/zysk/bez zmian),
    same colours as render()'s bars and the map legend."""
    bands = _band_populations(gpkg)
    loss, zero, gain, n_loss, n_zero, n_gain = bands["net"]
    total = loss + zero + gain
    loss_pct, zero_pct, gain_pct = loss / total * 100, zero / total * 100, gain / total * 100

    fig, ax = plt.subplots(figsize=(1.3, 9.0))
    width = 0.9
    ax.bar(0, loss_pct, width, bottom=0, color=LOSS_COLOR, edgecolor="#808080", linewidth=0.4)
    ax.bar(0, zero_pct, width, bottom=loss_pct, color=ZERO_COLOR, edgecolor="#808080", linewidth=0.4)
    ax.bar(0, gain_pct, width, bottom=loss_pct + zero_pct, color=GAIN_COLOR, edgecolor="#808080", linewidth=0.4)

    ax.text(0, loss_pct / 2, f"STRATA {loss_pct:.0f}%", ha="center", va="center",
             fontsize=9, fontweight="bold", color="white", rotation=90)
    ax.text(0, loss_pct + zero_pct / 2, f"BEZ ZMIAN {zero_pct:.0f}%", ha="center", va="center",
             fontsize=9, fontweight="bold", color="#333333", rotation=90)
    ax.text(0, loss_pct + zero_pct + gain_pct / 2, f"ZYSK {gain_pct:.0f}%", ha="center", va="center",
             fontsize=9, fontweight="bold", color="white", rotation=90)

    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(0, 100)
    ax.axis("off")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = OUT_DIR / f"loss_gain_strip_{resolution}m"
    fig.savefig(prefix.with_suffix(".png"), dpi=200, bbox_inches="tight", pad_inches=0.05, transparent=True)
    plt.close(fig)

    import csv
    with open(prefix.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["pop_loss", "pop_zero", "pop_gain",
                                             "pop_loss_pct", "pop_zero_pct", "pop_gain_pct",
                                             "n_loss", "n_zero", "n_gain"])
        w.writeheader()
        w.writerow(dict(pop_loss=loss, pop_zero=zero, pop_gain=gain,
                          pop_loss_pct=loss_pct, pop_zero_pct=zero_pct, pop_gain_pct=gain_pct,
                          n_loss=n_loss, n_zero=n_zero, n_gain=n_gain))

    meta = {
        "chart": "loss_gain_strip",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "resolution_m": resolution,
        "source": str(gpkg),
        "source_sha256": _fingerprint(gpkg),
        "note": "Zbiorczo (net_delta) only, no title/caption -- meant for the print board's side margin.",
    }
    prefix.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ok] {prefix.name}.png/.csv/.json")


def main():
    for res, gpkg in RESOLUTIONS.items():
        if not gpkg.exists():
            raise RuntimeError(f"{gpkg} missing -- run the local pipeline first.")
        render(res, gpkg)
        render_strip(res, gpkg)
    print("[done] chart_loss_gain_profile.py finished.")


if __name__ == "__main__":
    main()
