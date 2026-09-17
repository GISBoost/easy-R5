"""Population-weighted accessibility summaries (PR_easy-R5_v03.md R-4). Pure stdlib.

Every statistic weights each feature by its population: "62% of residents"
rather than "62% of hexagons".
"""

from __future__ import annotations

import html

QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_pairs(values, weights):
    """[(x, w)] with NULL x -> 0 (no access) and NULL/negative/zero w dropped. Returns (pairs, skipped)."""
    pairs, skipped = [], 0
    for v, w in zip(values, weights):
        w = _num(w)
        if w is None or w < 0:
            skipped += 1
            continue
        if w == 0:
            continue
        x = _num(v)
        pairs.append((0.0 if x is None else x, w))
    return pairs, skipped


def weighted_quantile(pairs, q):
    """Smallest x whose cumulative weight reaches q * total weight. None for no data."""
    total = sum(w for _x, w in pairs)
    if total <= 0:
        return None
    acc = 0.0
    for x, w in sorted(pairs):
        acc += w
        if acc >= q * total - 1e-9:
            return x
    return sorted(pairs)[-1][0]


def weighted_gini(pairs):
    """Population-weighted Gini of x: sum_ij w_i w_j |x_i - x_j| / (2 W^2 mu). None when mu == 0."""
    total = sum(w for _x, w in pairs)
    if total <= 0 or any(x < 0 for x, _w in pairs):
        return None  # Gini is only meaningful for non-negative values (not for a diff field)
    mean = sum(x * w for x, w in pairs) / total
    if mean <= 0:
        return None
    s = 0.0
    cum_w = cum_wx = 0.0
    for x, w in sorted(pairs):
        s += w * (x * cum_w - cum_wx)
        cum_w += w
        cum_wx += w * x
    return (2 * s) / (2 * total * total * mean)


def summarize(values, weights, threshold):
    """One row of statistics for one accessibility field (and one group)."""
    pairs, skipped = clean_pairs(values, weights)
    total = sum(w for _x, w in pairs)
    at_least = sum(w for x, w in pairs if x >= threshold)
    zero = sum(w for x, w in pairs if x <= 0)
    row = {
        "population": total,
        "pop_at_least": at_least,
        "share_at_least": (at_least / total) if total else None,
        "pop_zero": zero,
        "share_zero": (zero / total) if total else None,
        "mean": (sum(x * w for x, w in pairs) / total) if total else None,
        "gini": weighted_gini(pairs),
        "skipped": skipped,
    }
    for q in QUANTILES:
        row["p{}".format(int(q * 100))] = weighted_quantile(pairs, q)
    return row


def summarize_layer(records, pop_field, acc_fields, threshold, group_field=None):
    """``records``: iterable of dicts. Rows for group 'ALL' plus one per group value, per field."""
    records = list(records)
    groups = [("ALL", records)]
    if group_field:
        by = {}
        for r in records:
            key = r.get(group_field)
            by.setdefault("(none)" if key in (None, "") else str(key), []).append(r)
        groups += sorted(by.items())
    rows = []
    for name, recs in groups:
        weights = [r.get(pop_field) for r in recs]
        for field in acc_fields:
            row = summarize([r.get(field) for r in recs], weights, threshold)
            rows.append({"grp": name, "field": field, **row})
    return rows


def _fmt(v, pct=False, digits=2):
    if v is None:
        return "–"
    if pct:
        return "{:.1f}%".format(100 * v)
    if abs(v - round(v)) < 1e-9 and abs(v) >= 1:
        return "{:,.0f}".format(v).replace(",", " ")
    return "{:,.{d}f}".format(v, d=digits).replace(",", " ")


def sentence(row, threshold):
    return "{g}: {s} of residents ({a} of {t}) have {f} ≥ {th}; {z} have none.".format(
        g=row["grp"], s=_fmt(row["share_at_least"], pct=True), a=_fmt(row["pop_at_least"]),
        t=_fmt(row["population"]), f=row["field"], th=_fmt(threshold), z=_fmt(row["share_zero"], pct=True))


def render_html(rows, threshold, method, title="Accessibility equity summary"):
    esc = html.escape
    cols = ["grp", "field", "population", "pop_at_least", "share_at_least", "pop_zero", "share_zero",
            "mean", "p10", "p25", "p50", "p75", "p90", "gini"]
    body = "".join(
        "<tr>" + "".join("<td>{}</td>".format(esc(
            _fmt(r[c], pct=c.startswith("share")) if isinstance(r[c], (int, float)) or r[c] is None
            else str(r[c]))) for c in cols) + "</tr>"
        for r in rows)
    sentences = "".join("<li>{}</li>".format(esc(sentence(r, threshold))) for r in rows if r["grp"] == "ALL")
    meth = "".join("<tr><th>{}</th><td>{}</td></tr>".format(esc(k), esc(", ".join(v)))
                   for k, v in sorted(method.items()) if v)
    return """<!doctype html><meta charset="utf-8"><title>{t}</title>
<style>body{{font:14px system-ui,sans-serif;margin:2em}}table{{border-collapse:collapse}}
td,th{{border-bottom:1px solid #ddd;padding:.3em .6em;text-align:left}}</style>
<h1>{t}</h1><ul>{s}</ul><h2>Statistics (population-weighted)</h2>
<table><tr>{h}</tr>{b}</table><h2>Method recorded in the input layer</h2><table>{m}</table>
""".format(t=esc(title), s=sentences, h="".join("<th>{}</th>".format(c) for c in cols), b=body,
           m=meth or "<tr><td>none</td></tr>")
