"""Before/after comparison of two result layers (PR_easy-R5_v03.md R-2). Pure stdlib."""

from __future__ import annotations

# Method fields that must match for a difference to mean anything.
STRICT_FIELDS = ("percentile", "decay", "time_window", "departure_time", "modes", "catchment",
                 "max_trip_duration_minutes", "max_walk_time_minutes", "walk_speed_kmh", "max_rides",
                 "monte_carlo_draws")
# Fields expected to differ between a baseline and a variant — reported, never blocking.
EXPECTED_TO_DIFFER = ("run_date", "network_hash", "scenario", "transit_submodes", "r5_version")


def _distinct(values):
    return sorted({str(v) for v in values if v not in (None, "")})


def method_mismatches(meta_a, meta_b):
    """``meta_*``: {field: iterable of the values found in that layer}.

    Returns (blocking, informational): lists of (field, values_a, values_b) where
    the value sets differ. A field present in only one layer is ignored.
    """
    blocking, info = [], []
    for field in STRICT_FIELDS + EXPECTED_TO_DIFFER:
        if field not in meta_a or field not in meta_b:
            continue
        a, b = _distinct(meta_a[field]), _distinct(meta_b[field])
        if a != b:
            (blocking if field in STRICT_FIELDS else info).append((field, a, b))
    return blocking, info


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def join_key(value):
    """Id value -> comparable string: 12, 12.0 and '12' all give '12'; empty -> None."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    key = str(value).strip()
    return None if key in ("", "NULL") else key


def diff_row(value_a, value_b, *, in_a=True, in_b=True, higher_is_better=True):
    """(value_a, value_b, diff, pct_change, status) for one joined feature.

    ``higher_is_better`` (accessibility, service minutes, 2SFCA): a missing value on a
    feature present in both layers counts as 0 — no reachable opportunity.
    Otherwise (travel times) a missing value means *unreachable*: A reachable and B
    not is ``worse`` with no numeric diff, and the reverse is ``better``.
    ``pct_change`` is None when A is 0 or missing.
    """
    if not in_b:
        return _num(value_a), None, None, None, "only_a"
    if not in_a:
        return None, _num(value_b), None, None, "only_b"
    a, b = _num(value_a), _num(value_b)
    if higher_is_better:
        a, b = a or 0.0, b or 0.0
    elif a is None or b is None:
        if a is None and b is None:
            return None, None, None, None, "same"
        return a, b, None, None, "worse" if b is None else "better"
    diff = b - a
    pct = 100.0 * diff / a if a else None
    if abs(diff) < 1e-9:
        status = "same"
    elif (diff > 0) == higher_is_better:
        status = "better"
    else:
        status = "worse"
    return a, b, diff, pct, status


def summarize(rows):
    """Counts per status plus sum/mean of diff over rows that have a numeric diff."""
    counts = {}
    diffs = []
    for _a, _b, diff, _pct, status in rows:
        counts[status] = counts.get(status, 0) + 1
        if diff is not None:
            diffs.append(diff)
    return {"counts": counts, "sum_diff": sum(diffs),
            "mean_diff": (sum(diffs) / len(diffs)) if diffs else None}
