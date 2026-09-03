"""Cumulative-opportunity accessibility from a travel-time matrix.

R5 cannot compute this for us — ``recordAccessibility = true`` dies with
``task.destinationPointSetKeys is null`` because R5 pulls opportunity grids
through Conveyal's object storage (spike 2026-09-02). So we sum in Python over
the matrix CSV: for each origin, opportunity column, percentile and cutoff,
add each destination's opportunity count weighted by a decay function of the
travel time.

Pure stdlib. ``STEP`` is the only function the studies used and the only one
validated against r5r (``docs/notes/validation-gdansk.md``); ``LOGISTIC`` and
``EXPONENTIAL`` are provided but unvalidated.
"""

from __future__ import annotations

import csv
import math

STEP = "STEP"
LOGISTIC = "LOGISTIC"
EXPONENTIAL = "EXPONENTIAL"
DECAYS = (STEP, LOGISTIC, EXPONENTIAL)

# R5 LogisticDecayFunction default (standardDeviationMinutes); only used for LOGISTIC.
_LOGISTIC_SD_MIN = 10.0


def decay_weight(decay, travel_time, cutoff):
    """Weight in [0, 1] for a trip of ``travel_time`` min against ``cutoff`` min.

    - ``STEP``: 1 *below* the cutoff, 0 at or above it. R5's ``StepDecayFunction``
      is a strict ``travelTime < cutoff`` (verified from bytecode); matching that
      exactly is what reproduces r5r's Gdańsk output row for row — all 27 780
      rows, every cutoff (``docs/notes/validation-gdansk.md``).
    - ``EXPONENTIAL``: ``0.5 ** (t / cutoff)`` — half weight at the cutoff. The
      shape matches R5's ExponentialDecayFunction but has **not** been checked
      against the jar; do not assume an exact r5r match.
    - ``LOGISTIC``: rolloff centred on the cutoff, 10-minute standard deviation.
      Same caveat — **not** validated against R5's LogisticDecayFunction.
    """
    if travel_time is None:
        return 0.0
    if decay == STEP:
        return 1.0 if travel_time < cutoff else 0.0
    if decay == EXPONENTIAL:
        return math.pow(0.5, travel_time / cutoff) if cutoff > 0 else 0.0
    if decay == LOGISTIC:
        scale = _LOGISTIC_SD_MIN * math.sqrt(3.0) / math.pi
        return 1.0 / (1.0 + math.exp((travel_time - cutoff) / scale))
    raise ValueError("unknown decay function: {!r}".format(decay))


def _percentile_columns(header):
    """[(column index, percentile int)] for every travel_time_p<n> column."""
    out = []
    for i, name in enumerate(header):
        if name.startswith("travel_time_p"):
            out.append((i, int(name[len("travel_time_p"):])))
    return out


def compute_accessibility(matrix_csv, opportunities, origin_ids, cutoffs, decay=STEP):
    """Long-format accessibility rows, the same shape r5r's ``accessibility()`` emits.

    ``matrix_csv``: path to a ``from_id,to_id,travel_time_p<n>...`` matrix (blank
    cell = unreachable). ``opportunities``: ``{dest_id: {opp_name: value}}``.
    ``origin_ids``: every origin that must appear in the output — an origin with
    no reachable destination contributes 0 (never NULL, never missing).

    Yields dicts ``{id, opportunity, percentile, cutoff, accessibility}``.
    A STEP sum that is already whole (integer opportunity counts — the r5r case)
    is emitted as an int so the diff stays byte-exact; a fractional STEP sum
    (e.g. residents from PopulationOverlay) keeps 4 decimals rather than being
    silently truncated. The weighted functions always keep 4 decimals.
    """
    opp_names = sorted({name for d in opportunities.values() for name in d})
    cutoffs = sorted(int(c) for c in cutoffs)

    with open(matrix_csv, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        pct_cols = _percentile_columns(header)
        # acc[(origin, opp, pct, cutoff)] -> running sum
        acc = {
            (o, opp, pct, c): 0.0
            for o in origin_ids
            for opp in opp_names
            for _, pct in pct_cols
            for c in cutoffs
        }
        for row in reader:
            if not row:
                continue
            origin, dest = row[0], row[1]
            dest_opps = opportunities.get(dest)
            if not dest_opps:
                continue
            for col, pct in pct_cols:
                cell = row[col] if col < len(row) else ""
                if cell == "":
                    continue
                tt = int(cell)
                for c in cutoffs:
                    w = decay_weight(decay, tt, c)
                    if w == 0.0:
                        continue
                    for opp, value in dest_opps.items():
                        if value:
                            acc[(origin, opp, pct, c)] += value * w

    for o in origin_ids:
        for opp in opp_names:
            for _, pct in pct_cols:
                for c in cutoffs:
                    v = acc[(o, opp, pct, c)]
                    if decay == STEP and abs(v - round(v)) < 1e-6:
                        out_v = int(round(v))
                    else:
                        out_v = round(v, 4)
                    yield {
                        "id": o,
                        "opportunity": opp,
                        "percentile": pct,
                        "cutoff": c,
                        "accessibility": out_v,
                    }


def read_opportunities(csv_path, opp_fields):
    """``{id: {field: float}}`` from a destinations CSV (id column + opp columns)."""
    out = {}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["id"]] = {f: float(row[f] or 0) for f in opp_fields if f in row}
    return out
