"""Two figures answering "is this an artefact of the grid?". Plain Python (py maup_charts.py).

Reads out/maup/*.csv, written by maup.py. Cross-grid, so the filenames carry no grid
suffix -- they are about all four grids at once.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                               # noqa: E402
from matplotlib.ticker import FuncFormatter                   # noqa: E402

import maup                                                   # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
FIG = OUT / "figures"

COLOUR = {"h250": "#67001f", "h500": "#b2182b", "h1000": "#f4a582",
          "h500off": "#2166ac"}
MARKER = {"h250": "o", "h500": "s", "h1000": "^", "h500off": "D"}

plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": ":"})


def _rows(name):
    """Rows of a maup/ table, or [] when that comparison had too few grids to write one."""
    path = OUT / "maup" / name
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)
    print("[ok]", FIG / name)


def chart_scale_effect():
    """Same scenarios, four grids: what moves and what does not."""
    rows = _rows("city_by_grid.csv")
    if not rows:
        print("[skip] 10_maup_skala: no city table")
        return
    cases = ["loo_5", "bus", "corridor", "cascade_top3", "all_trams"]
    names = {"loo_5": "linia 5\nznika", "bus": "5 zastąpiona\nautobusem",
             "corridor": "torowisko\n5+16", "cascade_top3": "trzy linie",
             "all_trams": "wszystkie\ntramwaje"}
    cases = [c for c in cases if any(r["case"] == c for r in rows)]
    by = {(r["grid"], r["case"]): r for r in rows}
    grids = [g for g in maup.GRIDS if any(r["grid"] == g for r in rows)]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.9))
    width = 0.8 / len(grids)
    for k, g in enumerate(grids):
        xs = [i + (k - (len(grids) - 1) / 2) * width for i in range(len(cases))]
        ax.bar(xs, [abs(_f(by[(g, c)]["mean_net"], 0)) for c in cases], width,
               color=COLOUR[g], label=maup.LABEL[g])
        ax2.bar(xs, [100 * _f(by[(g, c)]["share_losing"], 0) for c in cases], width,
                color=COLOUR[g])
    for a in (ax, ax2):
        a.set_xticks(range(len(cases)), [names[c] for c in cases], fontsize=7.5)
    ax.set_title("Ile celów ubywa przeciętnemu mieszkańcowi", fontsize=9, loc="left")
    ax.set_ylabel("cele w 30 min")
    ax.legend(fontsize=7.5)
    ax2.set_title("Ilu mieszkańców w ogóle coś traci", fontsize=9, loc="left")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.suptitle("Rozmiar heksa zmienia wysokość słupków, nie ich kolejność",
                 x=0.01, ha="left", fontsize=10)
    _save(fig, "10_maup_skala.png")


def chart_ranking_stability():
    """Does each grid put the same tram lines at the top?"""
    rows = _rows("ranking_by_grid.csv")
    grids = [g for g in maup.GRIDS if any(r.get(f"rank_{g}") for r in rows)]
    if not grids:
        print("[skip] 11_maup_ranking: no rankings")
        return
    order = sorted(rows, key=lambda r: int(r[f"rank_{grids[0]}"] or 99))
    lines = [r["line"] for r in order]

    fig, ax = plt.subplots(figsize=(7.4, 5.4))
    for g in grids:
        ys = [int(r[f"rank_{g}"]) if r.get(f"rank_{g}") else None for r in order]
        xs = [i for i, y in enumerate(ys) if y is not None]
        ax.plot(xs, [y for y in ys if y is not None], MARKER[g] + "-", color=COLOUR[g],
                label=maup.LABEL[g], alpha=0.85, markersize=5, linewidth=1.1)
    ax.set_xticks(range(len(lines)), lines, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("linia tramwajowa (kolejność wg siatki 250 m)")
    ax.set_ylabel("miejsce w rankingu ważności\n← ważniejsza")
    ax.set_title("Ranking linii jest ten sam na każdej siatce\n"
                 "cztery linie łamane niemal się pokrywają", loc="left")
    ax.legend(fontsize=8, ncol=2)
    _save(fig, "11_maup_ranking.png")


def chart_osiedla_stability(case="loo_5", top=14):
    """The reported neighbourhood numbers, measured on all four grids."""
    rows = _rows(f"osiedla_by_grid_{case}.csv")[:top]
    if not rows:
        print("[skip] 12_maup_osiedla: needs at least two grids")
        return
    grids = [g for g in maup.GRIDS if any(r.get(f"share_losing_{g}") for r in rows)]
    names = [r["osiedle"].replace("imienia Józefa Montwiłła-Mireckiego", "Montwiłła-Mireckiego")
             for r in rows][::-1]
    rows = rows[::-1]

    fig, ax = plt.subplots(figsize=(7.6, 5.6))
    height = 0.8 / len(grids)
    for k, g in enumerate(grids):
        ys = [i + (k - (len(grids) - 1) / 2) * height for i in range(len(rows))]
        ax.barh(ys, [100 * (_f(r.get(f"share_losing_{g}"), 0)) for r in rows], height,
                color=COLOUR[g], label=maup.LABEL[g])
    ax.set_yticks(range(len(rows)), names, fontsize=8)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("% mieszkańców osiedla, którzy tracą choć jeden cel")
    ax.set_title("Wynik na osiedlach nie zależy od siatki\n"
                 "linia 5 nie jeździ — cztery siatki, te same osiedla", loc="left")
    ax.legend(fontsize=8, loc="lower right")
    _save(fig, "12_maup_osiedla.png")


def main():
    chart_scale_effect()
    chart_ranking_stability()
    chart_osiedla_stability()
    print("[done] MAUP figures in", FIG)


if __name__ == "__main__":
    main()
