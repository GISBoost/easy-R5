"""F3 -- verify I1/I2/I3 across the four modal-case accessibility runs.

PRD SS4.6. This is the proof that R5 actually respects TRANSIT_SUBMODES on the
runner path, not a step of the pipeline -- kept in its own file on purpose.

- I1/I2 violated -> stop. That is an engine/parameter/join bug, never noise.
- I3 not satisfied -> stop and say so plainly: R5 is likely ignoring
  TRANSIT_SUBMODES. The route_type-filtering fallback
  (docs/notes/flagship-analysis-candidates.md SS3) is NOT to be implemented
  from here without asking first.

Pure stdlib -- run with plain `py check_invariants.py` after run_modal_cases.py.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
EPS = 1e-6
I3_THRESHOLD = 0.05


def load(case_id):
    """{(id, opportunity, percentile, cutoff): accessibility}"""
    out = {}
    with open(OUT / f"acc_{case_id}.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row["id"], row["opportunity"], int(row["percentile"]), int(row["cutoff"]))
            out[key] = float(row["accessibility"])
    return out


def main():
    cases = {c: load(c) for c in ("W", "T", "B", "TB")}
    keys = set(cases["TB"])
    for c in ("W", "T", "B"):
        keys &= set(cases[c])
    if len(keys) != len(cases["TB"]):
        raise RuntimeError(
            f"Row-set mismatch across the four cases: TB has {len(cases['TB'])} rows, "
            f"the common intersection has {len(keys)}. The four runs are not "
            "directly comparable -- did they use different destinations/cutoffs?"
        )

    i1_violations = []
    i2_violations = []
    abs_diffs = []
    tb_values = []
    for key in keys:
        w, t, b, tb = cases["W"][key], cases["T"][key], cases["B"][key], cases["TB"][key]
        if w > t + EPS or w > b + EPS or w > tb + EPS:
            i1_violations.append((key, w, t, b, tb))
        if tb + EPS < max(t, b):
            i2_violations.append((key, t, b, tb))
        abs_diffs.append(abs(t - b))
        tb_values.append(tb)

    def report(name, violations):
        print(f"[{name}] {len(violations)} violation(s) out of {len(keys)} rows.")
        for v in violations[:10]:
            print("   ", v)

    report("I1", i1_violations)
    report("I2", i2_violations)

    mean_abs_diff = sum(abs_diffs) / len(abs_diffs)
    mean_tb = sum(tb_values) / len(tb_values)
    i3_value = mean_abs_diff / mean_tb if mean_tb else 0.0
    print(f"[I3] mean|A_T - A_B| / mean(A_TB) = {i3_value:.4f} (threshold > {I3_THRESHOLD})")

    result = {
        "rows_checked": len(keys),
        "i1_violations": len(i1_violations),
        "i2_violations": len(i2_violations),
        "i3_value": i3_value,
        "i3_threshold": I3_THRESHOLD,
        "i3_pass": i3_value > I3_THRESHOLD,
    }
    (OUT / "invariants.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    if i1_violations or i2_violations:
        raise RuntimeError(
            f"GATE FAILED: I1 has {len(i1_violations)} violation(s), I2 has "
            f"{len(i2_violations)} violation(s) -- see the example rows printed above. "
            "This is an engine/parameter/join bug, not noise. Stopping."
        )
    if i3_value <= I3_THRESHOLD:
        raise RuntimeError(
            f"GATE FAILED: I3 = {i3_value:.4f}, not > {I3_THRESHOLD}. R5 is likely "
            "ignoring TRANSIT_SUBMODES on the runner path -- this analysis is invalid "
            "as-is. Do NOT implement the route_type-filtering fallback from "
            "docs/notes/flagship-analysis-candidates.md SS3 without asking first. Stopping."
        )
    print("[gate OK] I1, I2, I3 all pass.")


if __name__ == "__main__":
    main()
