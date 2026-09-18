"""Charts for the tram-failure analysis. Plain Python + matplotlib (py charts.py).

Reads only what is already on disk in out/; runs no R5 and needs no QGIS.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                               # noqa: E402
from matplotlib.ticker import FuncFormatter                   # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
FIG = OUT / "figures"

# Figures are named <nn>_<topic>_<grid>.png so a folder listing sorts into the order of
# the story and every file says which grid it came from. Cross-grid (MAUP) figures carry
# no grid suffix, because they are about all of them at once.
GRID = "h250"
GRID_LABEL = {"h250": "siatka 250 m", "h500": "siatka 500 m", "h1000": "siatka 1000 m",
              "h500off": "siatka 500 m przesunięta"}

RED, BLUE, GREY = "#b2182b", "#2166ac", "#9e9e9e"
PALE_RED, PALE_BLUE = "#f4a582", "#92c5de"

plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": ":"})


def _rows(name, grid=None):
    """Read a CSV from out/<grid>/ (grid-specific) or out/ (shared)."""
    path = OUT / (grid or GRID) / name
    if not path.exists():
        path = OUT / name
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


def chart_loo_ranking():
    """Every tram line ranked by what its removal actually costs."""
    rows = _rows("loo_ranking.csv")
    lines = [r["line"] for r in rows][::-1]
    values = [-_f(r["mean_net"]) for r in rows][::-1]
    meets = [r["meets_length"] == "1" for r in rows][::-1]

    fig, ax = plt.subplots(figsize=(6.4, 6.2))
    colours = [RED if m else PALE_RED for m in meets]
    ax.barh(range(len(lines)), values, color=colours)
    ax.set_yticks(range(len(lines)), lines)
    ax.set_xlabel("Ubytek dostępności po usunięciu linii\n"
                  "(średnia ważona populacją, liczba celów w 30 min)")
    ax.set_ylabel("linia tramwajowa")
    ax.set_title("Która linia jest naprawdę najważniejsza?\n"
                 f"Łódź, 21 linii tramwajowych, każda usuwana osobno ({GRID_LABEL[GRID]})",
                 loc="left")
    for i, (v, r) in enumerate(zip(values, rows[::-1])):
        ax.text(v + 0.02, i, f"{int(_f(r['pop_losing'])):,}".replace(",", " "),
                va="center", fontsize=7, color="#444")
    handles = [plt.Rectangle((0, 0), 1, 1, color=RED),
               plt.Rectangle((0, 0), 1, 1, color=PALE_RED)]
    ax.legend(handles, ["w górnych 25% długości (kryterium 4)", "poniżej progu długości"],
              loc="lower right", fontsize=8, framealpha=0.9)
    ax.text(1.0, 1.005, "liczby przy słupkach: ilu mieszkańców traci choć jeden cel",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="#666")
    _save(fig, f"01_ranking_linii_{GRID}.png")


def chart_ex_ante_vs_measured():
    """Did the ex-ante criteria pick the right line?"""
    rows = _rows("loo_ranking.csv")
    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    for r in rows:
        x, y = _f(r["ex_ante_score"]), int(r["measured_rank"])
        if x is None:
            continue
        meets = r["meets_length"] == "1"
        ax.scatter(x, y, s=46, color=RED if meets else GREY,
                   zorder=3, edgecolor="white", linewidth=0.6)
        ax.annotate(r["line"], (x, y), textcoords="offset points", xytext=(6, 3),
                    fontsize=8, color="#333")
    ax.invert_yaxis()
    ax.set_xlabel("ranking ex ante (średnia pozycji: populacja + wozokilometry)\n"
                  "← lepszy kandydat wg kryteriów")
    ax.set_ylabel("zmierzona pozycja po usunięciu linii\n← większy realny skutek")
    ax.set_title("Kryteria kontra pomiar\nczerwone = przeszły kryterium długości",
                 loc="left")
    _save(fig, f"02_kryteria_vs_pomiar_{GRID}.png")


def chart_cascade():
    """How the loss grows as more lines fail, against the additive expectation."""
    by_case = {r["case"]: r for r in _rows("impact_by_case.csv")}
    loo = {r["line"]: -_f(r["mean_net"]) for r in _rows("loo_ranking.csv")}
    order = json.loads((OUT / GRID / "impact.json").read_text(encoding="utf-8"))["worst_lines"]

    steps = [("0", 0.0, 0.0, 0.0)]
    cumulative = 0.0
    for n, case in ((1, "loo_5"), (2, "cascade_top2"), (3, "cascade_top3"),
                    (5, "cascade_top5")):
        if case not in by_case:
            continue
        cumulative = sum(loo[line] for line in order[:n])
        steps.append((str(n), -_f(by_case[case]["mean_net"]), cumulative,
                      _f(by_case[case]["share_losing"])))
    if "all_trams" in by_case:
        steps.append(("21", -_f(by_case["all_trams"]["mean_net"]), sum(loo.values()),
                      _f(by_case["all_trams"]["share_losing"])))

    labels = [s[0] for s in steps]
    measured = [s[1] for s in steps]
    additive = [s[2] for s in steps]

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(6.2, 6.0), sharex=True,
                                  gridspec_kw={"height_ratios": [2, 1]})
    ax.plot(labels, measured, "-o", color=RED, label="zmierzone razem")
    ax.plot(labels, additive, "--o", color=BLUE, markerfacecolor="white",
            label="suma skutków pojedynczych")
    ax.set_ylabel("ubytek dostępności\n(cele w 30 min, śr. waż. populacją)")
    ax.set_title("Straty się kumulują szybciej niż liniowo\n"
                 "linie wyłączane w kolejności zmierzonej ważności", loc="left")
    ax.legend(fontsize=8)

    ax2.bar(labels, [s[3] * 100 for s in steps], color=PALE_BLUE)
    ax2.set_ylabel("% mieszkańców\nktórzy coś tracą")
    ax2.set_xlabel("ile linii tramwajowych nie jeździ")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    _save(fig, f"03_kaskada_{GRID}.png")


def chart_failure_modes():
    """One line, three assumptions about what "went down" means."""
    by_case = {r["case"]: r for r in _rows("impact_by_case.csv")}
    cases = [("bus", "5 zastąpiona\nautobusem", PALE_RED),
             ("loo_5", "5 znika\nbez zastępstwa", RED),
             ("corridor", "zamknięte torowisko\n(5 + 16)", "#7f0b1c")]
    cases = [c for c in cases if c[0] in by_case]

    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.4))
    metrics = [("mean_net", "ubytek celów w 30 min", 1, ""),
               ("share_losing", "% mieszkańców, którzy tracą", 100, "%"),
               ("centre_minutes_delta", "dłuższy dojazd do centrum", 1, " min")]
    for ax, (key, title, scale, unit) in zip(axes, metrics):
        vals = [abs(_f(by_case[c][key], 0.0)) * scale for c, _, _ in cases]
        ax.bar([lbl for _, lbl, _ in cases], vals, color=[col for _, _, col in cases])
        ax.set_title(title, fontsize=9, loc="left")
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.2f}{unit}" if unit != "%" else f"{v:.1f}%",
                    ha="center", va="bottom", fontsize=8)
        ax.set_ylim(0, max(vals) * 1.25)
        ax.tick_params(axis="x", labelsize=7.5)
    fig.suptitle("To samo zdarzenie, trzy założenia — i trzy różne odpowiedzi",
                 x=0.01, ha="left", fontsize=10)
    _save(fig, f"04_tryby_awarii_{GRID}.png")


def chart_equity():
    """Who carries the loss, by share of single-parent families."""
    labels = {"low": "najmniej samotnych\nrodziców (<24%)",
              "mid": "środek\n(24-29%)",
              "high": "najwięcej samotnych\nrodziców (>29%)"}
    base = {r["grp"]: r for r in _rows("equity_baseline.csv") if r["field"] == "scen_school"}
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.6))

    groups = ["low", "mid", "high"]
    ax.bar([labels[g] for g in groups], [_f(base[g]["mean"]) for g in groups],
           color=[GREY, PALE_BLUE, BLUE])
    ax.set_title("Punkt wyjścia: szkoły w zasięgu 30 min", fontsize=9, loc="left")
    ax.set_ylabel("średnia liczba szkół")
    ax.tick_params(axis="x", labelsize=7.5)
    for i, g in enumerate(groups):
        ax.text(i, _f(base[g]["mean"]), f"{_f(base[g]['mean']):.1f}",
                ha="center", va="bottom", fontsize=8)

    width, cases = 0.38, [("loo_5", "5 nie jeździ", RED), ("all_trams", "żaden tramwaj", "#7f0b1c")]
    for k, (case, label, colour) in enumerate(cases):
        rows = {r["grp"]: r for r in _rows(f"equity_{case}.csv") if r["field"] == "scen_school"}
        loss = [100 * (_f(rows[g]["mean"]) - _f(base[g]["mean"])) / _f(base[g]["mean"])
                for g in groups]
        ax2.bar([i + (k - 0.5) * width for i in range(3)], loss, width,
                color=colour, label=label)
    ax2.set_xticks(range(3), [labels[g] for g in groups], fontsize=7.5)
    ax2.set_title("Ile z tego ubywa", fontsize=9, loc="left")
    ax2.set_ylabel("zmiana względna liczby szkół")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.legend(fontsize=8)
    _save(fig, f"05_kto_traci_{GRID}.png")


def main(grid="h250"):
    global GRID
    GRID = grid
    chart_loo_ranking()
    chart_ex_ante_vs_measured()
    chart_cascade()
    chart_failure_modes()
    chart_equity()
    print("[done] figures for", grid, "in", FIG)


def main_all(grids=("h250", "h500", "h1000", "h500off")):
    for g in grids:
        if (OUT / g / "impact_by_case.csv").exists():
            main(g)
    import maup_charts
    maup_charts.main()


if __name__ == "__main__":
    main()
