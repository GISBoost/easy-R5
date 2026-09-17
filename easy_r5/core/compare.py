"""Before/after comparison of two result layers (PR_easy-R5_v03.md R-2). Pure stdlib."""

from __future__ import annotations

# Method fields that must match for a difference to mean anything.
STRICT_FIELDS = ("percentile", "decay", "time_window", "departure_time", "modes", "catchment")
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


def diff_row(value_a, value_b, *, in_a=True, in_b=True):
    """(value_a, value_b, diff, pct_change, status) for one joined feature.

    A missing numeric value on a feature present in both layers counts as 0
    (an origin with no reachable opportunity) — the same rule the accessibility
    output uses. ``pct_change`` is None when A is 0.
    """
    if not in_b:
        return _num(value_a), None, None, None, "only_a"
    if not in_a:
        return None, _num(value_b), None, None, "only_b"
    a = _num(value_a) or 0.0
    b = _num(value_b) or 0.0
    diff = b - a
    pct = 100.0 * diff / a if a else None
    if abs(diff) < 1e-9:
        status = "same"
    else:
        status = "better" if diff > 0 else "worse"
    return a, b, diff, pct, status


def summarize(rows):
    """Counts per status plus sum/mean of diff over rows present in both layers."""
    counts = {}
    diffs = []
    for _a, _b, diff, _pct, status in rows:
        counts[status] = counts.get(status, 0) + 1
        if diff is not None:
            diffs.append(diff)
    return {"counts": counts, "sum_diff": sum(diffs),
            "mean_diff": (sum(diffs) / len(diffs)) if diffs else None}
