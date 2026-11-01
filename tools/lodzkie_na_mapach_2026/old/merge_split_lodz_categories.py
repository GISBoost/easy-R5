"""Merge the 10-category (already correct) and 11-category (new11, worked
around easy-R5 issue #5 / KNOWN_ISSUES.md #4) accessibility runs into one
long-format CSV per day, so compute_metrics.py can read a single normal
acc_*.csv per run like every other stage of this pipeline.

Pure stdlib -- no QGIS needed, safe to run standalone (`py merge_split_lodz_categories.py`).

Why this exists: easyr5:runaccessibility silently returns 0 for every
opportunity field once too many destination points are combined (confirmed
fine at 975, broken at 4161 -- see MULTIDAY_LODZ_NOTES.md and
https://github.com/GISBoost/easy-R5/issues/5). poi_targets_lodz (21
categories, 4161 points) hit this; the original 10 categories came back
correct anyway (verified against known-good prior numbers), only the 11
categories added for Lodz's all-category deviation were wrong (zero
everywhere). Fix: reran those 11 alone against poi_targets_lodz_new11 (450
points, safely under the threshold) -- this module drops the (wrong) new11
rows from the original CSV and splices in the (correct) rows from the
new11-only run.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

NEW11 = {"uczelnia", "szpital", "biblioteka", "dom_kultury", "kino", "teatr",
         "muzeum", "silownia", "basen", "centrum_handlowe", "targowisko"}
NEW11_OPP = {f"srv_{c}" for c in NEW11}

# original_csv -> new11_csv -> merged output name
PAIRS = {
    "acc_A3a_lodz_static.csv": "acc_A3a_lodz_static_new11.csv",
    "acc_A3b_lodz_p50.csv": "acc_A3b_lodz_p50_new11.csv",
    "acc_A3b_lodz_p50_2026-09-08.csv": "acc_A3b_lodz_p50_2026-09-08_new11.csv",
    "acc_A3b_lodz_p50_2026-09-09.csv": "acc_A3b_lodz_p50_2026-09-09_new11.csv",
}


def merge_one(original_name, new11_name):
    original = C.OUT / original_name
    new11 = C.OUT / new11_name
    merged = C.OUT / original_name.replace(".csv", "_merged21.csv")

    with open(original, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["opportunity"] not in NEW11_OPP]
        fieldnames = list(csv.DictReader(open(original, encoding="utf-8")).fieldnames)
    n_kept = len(rows)

    # The new11 destinations layer keeps all 21 srv_* columns (just 450 points,
    # none belonging to the original 10 categories), so opportunity_fields()
    # discovers all 21 names here too and this run also computed trivially-zero
    # rows for the original 10 categories. Only the NEW11_OPP rows are real;
    # splicing the whole file back in would silently overwrite the correct
    # original-10 values (which sort later in `rows`, so load_wide()'s
    # last-write-wins dict would keep the wrong, trivial zero).
    with open(new11, encoding="utf-8") as fh:
        new_rows = [r for r in csv.DictReader(fh) if r["opportunity"] in NEW11_OPP]
    rows.extend(new_rows)

    with open(merged, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"{original_name}: kept {n_kept} non-new11 rows + spliced {len(new_rows)} "
          f"new11 rows -> {merged.name} ({len(rows)} total)")
    return merged


def main():
    for original_name, new11_name in PAIRS.items():
        merge_one(original_name, new11_name)


if __name__ == "__main__":
    main()
