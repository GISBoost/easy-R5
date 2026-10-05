#!/bin/bash
# Walk/bike/car matrices: independent of the day and of GTFS, so computed once, locally (the CI workflow does transit only).
cd "$(dirname "$0")/.."
Q="/c/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat"
D=2026-10-02
for W in morning midday afternoon; do
  ls data/networks/$D/car_$W/*/network.dat >/dev/null 2>&1 || "$Q" scripts/build_net.py $D static "$(pwd -W)/data/car/lodz_car_$W.osm.pbf" car_$W 2>&1 | grep -E "Error|Exception"
  "$Q" scripts/run_matrices.py $D $W car 2>&1 | grep -E "^(done|skip)|Error|Exception"
done
for K in walk bike; do "$Q" scripts/run_matrices.py $D morning $K 2>&1 | grep -E "^(done|skip)|Error|Exception"; done
echo NONTRANSIT_FINISHED
