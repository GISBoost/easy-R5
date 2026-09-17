"""Two-step floating catchment area (2SFCA) accessibility (PR_easy-R5_v03.md R-5). Pure stdlib.

Luo & Wang (2003). With a non-STEP decay this is the E2SFCA-style weighted
variant; the weights come from ``accessibility.decay_weight`` and are cut to 0
at and beyond the catchment in both steps.

    step 1 (supply):  R_j = S_j / sum_k P_k * w(t_kj)
    step 2 (demand):  A_i = sum_j R_j * w(t_ij)

Property used as a check: sum_i A_i * P_i == sum_j S_j over supply that has
any demand in its catchment — 2SFCA distributes all supply, no more, no less.
"""

from __future__ import annotations

import csv

from .accessibility import STEP, decay_weight


def weight(decay, travel_time, catchment):
    if travel_time is None or travel_time >= catchment:
        return 0.0
    return decay_weight(decay, travel_time, catchment)


def read_matrix_pairs(matrix_csv, percentile):
    """Yield (origin, dest, minutes) from a ``travel_time_p<percentile>`` column; blanks skipped."""
    col_name = "travel_time_p{}".format(int(percentile))
    with open(matrix_csv, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if col_name not in header:
            raise ValueError("matrix has no column {}".format(col_name))
        col = header.index(col_name)
        for row in reader:
            if len(row) > col and row[col] != "":
                yield row[0], row[1], int(row[col])


def two_step_fca(pairs, population, capacity, *, catchment, decay=STEP, per_population=1.0):
    """Run 2SFCA over ``pairs`` (origin, dest, minutes).

    ``population``: {origin: P}, ``capacity``: {dest: S}. Missing/negative values count as 0.
    Returns a dict: ``access`` {origin: A * per_population} (every origin in
    ``population``), ``ratio`` {dest: R}, ``demand`` {dest: weighted demand},
    ``unserved_supply`` (dests with capacity but no demand in catchment),
    ``distributed_supply`` (sum S_j over dests with demand).
    """
    pairs = [(o, d, t) for o, d, t in pairs if weight(decay, t, catchment) > 0.0]
    pop = {o: max(0.0, float(v or 0)) for o, v in population.items()}
    cap = {d: max(0.0, float(v or 0)) for d, v in capacity.items()}

    demand = {d: 0.0 for d in cap}
    for o, d, t in pairs:
        if d in demand:
            demand[d] += pop.get(o, 0.0) * weight(decay, t, catchment)
    ratio = {d: (cap[d] / demand[d] if demand[d] > 0 else 0.0) for d in cap}

    access = {o: 0.0 for o in pop}
    for o, d, t in pairs:
        if o in access:
            access[o] += ratio.get(d, 0.0) * weight(decay, t, catchment)

    return {
        "access": {o: a * per_population for o, a in access.items()},
        "ratio": ratio,
        "demand": demand,
        "unserved_supply": sum(1 for d in cap if cap[d] > 0 and demand[d] == 0),
        "distributed_supply": sum(cap[d] for d in cap if demand[d] > 0),
    }
