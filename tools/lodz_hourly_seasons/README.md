# lodz_hourly_seasons

Hourly accessibility of Lodz, August vs September vs October 2026, from the realized-P50 timetables (easy-GTFS-RT). Part of the
"Lodzkie na mapach 2026" entry (older competition work: `../lodzkie_na_mapach_2026/old/`).

Metric: number of OSM facilities (21 types -> 4 meta-categories, `../apartment_finder/config/services.yaml`) within 30 min of each
250 m hex centre by public transport, departure window = one clock hour 06-22, R5 percentile 50. No LKA, no static baseline.
Days and rationale: `config.yaml`.

1. `.github/workflows/lodz-hourly-seasons.yml` (workflow_dispatch): one job per day, 16 R5 runs each. Local test:
   `JAVA_HOME=<jdk21> py scripts/ci_hourly.py --day 2026-09-10 --osm <lodz.osm.pbf> --hours 8`
2. `gh run download <id> -D data`, then `py scripts/aggregate.py` -> `data/seasons.npz`, `data/summary.json`.

Data (`data/`) is not versioned.
