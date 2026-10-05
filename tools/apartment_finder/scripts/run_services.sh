#!/bin/bash
# Daily-service counts by the exact method (resumable). Needs data/services/poi.gpkg (service_pois.py) and the
# car networks (run_nontransit.sh). Per day: 6 transit networks (built if missing) x 3 windows x 3 ttypes x 2 ŁKA = 18 runs.
cd "$(dirname "$0")/.."
Q="/c/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat"
PY=py
DAYS=$($PY -c "import yaml;print(' '.join(yaml.safe_load(open('config/days.yaml',encoding='utf-8'))['days']))")
LAST=$(echo $DAYS | awk '{print $NF}')
PBF="$(pwd -W)/data/raw/lodz.osm.pbf"
run() { "$Q" scripts/service_counts.py "$@" 2>&1 | grep -E "^(r5|counted|skip)|Error|Exception|Traceback"; }
# non-transit results are day-independent: computed on the last day's network folder and stored under that day
for S in walk bike car_morning car_midday car_afternoon; do run $LAST $S; done
for D in $DAYS; do
  $PY scripts/prepare_gtfs.py $D || exit 1
  for V in static static_lka p50 p50_lka p85 p85_lka; do
    ls data/networks/$D/$V/*/network.dat >/dev/null 2>&1 || "$Q" scripts/build_net.py $D $V "$PBF" 2>&1 | grep -E "Error|Exception"
  done
  for W in morning midday afternoon; do for T in static p50 p85; do for L in nolka lka; do
    run $D transit_${W}_${T}_${L}
  done; done; done
  echo "SERVICES_DAY_DONE $D"
done
echo SERVICES_ALL_FINISHED
