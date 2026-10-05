#!/bin/bash
# M5: full computation, resumable (every step skips finished work).
#   scripts/run_all.sh            # all days from config/days.yaml
# Per day: GTFS folders -> 6 transit networks -> 4 windows x 3 ttypes x 2 rides x 2 lka = 48 matrices.
# Once (not per day): walk, bike, car per window (they do not depend on GTFS or day).
cd "$(dirname "$0")/.."
Q="/c/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat"
PY=py
DAYS=$($PY -c "import yaml;print(' '.join(yaml.safe_load(open('config/days.yaml',encoding='utf-8'))['days']))")
WINDOWS="morning midday afternoon allday"
PBF="$(pwd -W)/data/raw/lodz.osm.pbf"
for D in $DAYS; do
  $PY scripts/prepare_gtfs.py $D || exit 1
  for V in static static_lka p50 p50_lka p85 p85_lka; do
    ls data/networks/$D/$V/*/network.dat >/dev/null 2>&1 || "$Q" scripts/build_net.py $D $V "$PBF" 2>&1 | grep -E "Error|Exception"
  done
  for W in $WINDOWS; do for T in static p50 p85; do for R in unlimited max1transfer; do for L in 0 1; do
    "$Q" scripts/run_matrices.py $D $W $T $R $L 2>&1 | grep -E "^(done|skip)|Error|Exception"
  done; done; done; done
  echo "DAY_DONE $D"
done
D=$(echo $DAYS | awk '{print $NF}')   # non-transit once, on the last day's folder layout
for W in $WINDOWS; do
  ls data/networks/$D/car_$W/*/network.dat >/dev/null 2>&1 || "$Q" scripts/build_net.py $D static "$(pwd -W)/data/car/lodz_car_$W.osm.pbf" car_$W 2>&1 | grep -E "Error|Exception"
  "$Q" scripts/run_matrices.py $D $W car 2>&1 | grep -E "^(done|skip)|Error|Exception"; done
for K in walk bike; do "$Q" scripts/run_matrices.py $D morning $K 2>&1 | grep -E "^(done|skip)|Error|Exception"; done
echo ALL_FINISHED
