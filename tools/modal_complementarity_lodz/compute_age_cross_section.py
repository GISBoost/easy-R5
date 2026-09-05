"""F3 (late addition, F5 write-up needs it) -- one-sentence age cross-section.

PRD SS6 P4 / F5 prompt item 8: "czy mlodzi (20-29) mieszkaja bardziej
tramwajowo niz ogol" -- compares the pop_20_29-weighted mean tram_share
against the pop_total-weighted mean, on the same hexagon subset (hexes with
both a reliable tram_share and age-2029 data), so it's an apples-to-apples
comparison, not two different denominators.

Pure stdlib -- run with plain `py compute_age_cross_section.py`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "out"
STUDENTS_CSV = REPO / "tools" / "accessibility_lodz" / "lodz_hex_students.csv"


def main():
    age = {}
    with open(STUDENTS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["pop_20_29"]:
                age[row["hex_id"]] = float(row["pop_20_29"])

    rows = {}
    with open(OUT / "hex_modal.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows[row["hex_id"]] = row

    common = [hid for hid in age if hid in rows and rows[hid]["tram_share_pop_p50_c30"] != ""]
    pop_20_29_weighted_num = sum(age[hid] * float(rows[hid]["tram_share_pop_p50_c30"]) for hid in common)
    pop_20_29_weighted_den = sum(age[hid] for hid in common)
    pop_total_weighted_num = sum(
        float(rows[hid]["pop_total"]) * float(rows[hid]["tram_share_pop_p50_c30"]) for hid in common
    )
    pop_total_weighted_den = sum(float(rows[hid]["pop_total"]) for hid in common)

    result = {
        "hexagons_with_age_data_and_reliable_share": len(common),
        "tram_share_mean_weighted_by_pop_20_29": round(pop_20_29_weighted_num / pop_20_29_weighted_den, 4),
        "tram_share_mean_weighted_by_pop_total": round(pop_total_weighted_num / pop_total_weighted_den, 4),
    }
    print(json.dumps(result, indent=2))
    (OUT / "age_cross_section.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
