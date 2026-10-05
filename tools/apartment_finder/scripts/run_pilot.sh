#!/bin/bash
# M4 pilot: 1 day, morning window, all transit axes + walk/bike/car.
cd "$(dirname "$0")/.."
Q="/c/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat"
D=${1:-2026-10-02}
for t in static p50 p85; do for r in unlimited max1transfer; do for l in 0 1; do
  "$Q" scripts/run_matrices.py $D morning $t $r $l 2>&1 | grep -E "^(done|skip)|Error|Exception"
done; done; done
for k in walk bike car; do "$Q" scripts/run_matrices.py $D morning $k 2>&1 | grep -E "^(done|skip)|Error|Exception"; done
echo PILOT_FINISHED
