# realtime_delay_lodz — where GTFS-RT delays hurt reachability the most

**Question:** where in the city do real-world transit delays most degrade public-transport
reachability? Answered by comparing accessibility computed on the *static* GTFS schedule
against the *realized P50* schedule (the median of what vehicles actually did), for the
same real day, on the same network otherwise.

**Entirely on Easy-R5's own Processing algorithms** (`easyr5:buildnetwork`,
`easyr5:populationoverlay`, `easyr5:runaccessibility`) + native QGIS algorithms + stdlib.
No R/r5r, no Overpass API call at runtime, no pip — a dogfooding exercise, unlike
`../accessibility_lodz/` (R + r5r + Overpass) which this folder deliberately does not
depend on except for read-only, already-downloaded input files.

## Metric

For each 250 m hexagon and each of 4 destination categories, count how many points of
that category are reachable within **30 minutes**, departing in the **07:00–09:00**
morning window (`TIME_WINDOW=120`, `DEPARTURE_TIME=07:00` — the algorithm's own
defaults), median (P50) travel time. Run this once on the static network, once on the
realized-P50 network, same day (**2026-08-21**). `delta_<category> = realized - static`
— negative means delays make fewer points of that category reachable.

Categories: **school** (`amenity=school`, not kindergarten), **pharmacy**
(`amenity=pharmacy`), **university** (curated OSM extract, reused from
`accessibility_lodz/lodz_universities.csv`), **mall** (`shop=mall`).

## Data reused from prior sessions (nothing new downloaded)

| Input | Source |
|---|---|
| `.osm.pbf` | `../accessibility_lodz/lodz.osm.pbf` |
| GTFS static, 2026-08-21 | `../accessibility_lodz/lodz_static_gtfs_2026-08-21.zip` |
| GTFS realized P50, 2026-08-21 | `../accessibility_lodz/lodz_realized_2026-08-21_p50.zip` |
| Population per census precinct | `../ses_income_lodz/lodz.gpkg` layer `obwody_spisowe`, field `population` (real GUS count, not the income-index proxy also in that file) |
| Universities | `../accessibility_lodz/lodz_universities.csv` |

Verified directly (zipfile inspection) before building anything: both GTFS zips map
2026-08-21 to the identical `service_id` (`11493_11`) with the **identical 9893-trip
`trip_id` set** — the realized feed is a rewritten timetable for the same trips, not a
different set of runs. This is the hard prerequisite for the comparison to mean anything.

## Pipeline (`mcp__qgis__execute_code`, in order)

1. **`prepare_data.py`** — builds `network_static/` and `network_realized_p50/` (same
   `.osm.pbf`, separate GTFS folders — the project's "one variant per build dir" rule);
   a fresh 250 m hexagon grid (`native:creategrid`) clipped to the dissolved
   `obwody_spisowe` boundary, with population via `easyr5:populationoverlay`; and
   `poi_targets` — school/pharmacy/mall extracted straight from `lodz.osm.pbf`'s `points`
   and `multipolygons` OGR layers (`other_tags` filter on points, dedicated
   `amenity`/`shop` columns on multipolygons), polygon centroids preferred over a
   co-located point to avoid double-counting a building mapped both ways, university
   loaded from the existing CSV. Writes `delay_lodz.gpkg` (`hex_grid`, `hex_centroids`,
   `poi_targets`).
2. **`run_accessibility.py`** — two `easyr5:runaccessibility` runs (static, realized_p50),
   `OPPORTUNITY_FIELDS = [srv_school, srv_pharmacy, srv_university, srv_mall]`,
   `CUTOFFS=30`, everything else left at the algorithm's defaults (07:00, 120 min window,
   P50, TRANSIT+WALK, STEP decay, lossless `MAX_WALK_TIME`). Resumable via a
   `.params.json` sidecar per case, same pattern as `../modal_complementarity_lodz/run_modal_cases.py`.
3. **`compute_delay.py`** — `delta_<category> = acc_realized - acc_static` per hexagon,
   writes layer `hex_delay` (`hex_id`, `pop_total`, 4 `delta_<category>` fields — nothing
   else) into `delay_lodz.gpkg`, plus `out/city_delay_summary.csv` (population-weighted
   mean delta per category).

## Real numbers from the verified run (2026-08-21)

- Hex grid: 5662 hexagons (250 m), 5631 with `pop_total > 0`; population overlay off by
  0.034% vs the precinct sum (18 precincts excluded, GUS-suppressed `population=NULL`).
- POI counts: 311 schools, 350 pharmacies, 47 universities, 58 malls.
- Population-weighted city-wide mean `delta` (realized P50 minus static, points reachable
  within 30 min, 07:00-09:00): **school -0.128, pharmacy -0.078, university +0.009,
  mall -0.087**. Per-hex range is much wider (e.g. `delta_school` from -14 to +10,
  `delta_pharmacy` from -19 to +14) — the city-wide average is small because gains and
  losses partly cancel out; the worst losses (school, pharmacy) visually concentrate in
  the dense city-centre network, where more transfers make delays compound.
- **Note on running this**: `run_accessibility.py`'s two `RunAccessibility` passes
  (5662 origins here, vs. 1479 in `modal_complementarity_lodz`) took long enough that a
  single `mcp__qgis__execute_code` call timed out on the MCP transport and reported
  "failed" — QGIS itself kept computing in the main thread (it is unresponsive by design
  during a script, per the tool's own docs) and both runs finished correctly regardless.
  Check `out/*.params.json` exists for both cases before assuming a real failure and
  re-running from scratch.

## What Michał can check by hand in QGIS

- `hex_delay`, styled per category with a diverging ramp centred on 0 (red = fewer
  reachable points because of delays) — one map per category, no print layout needed.
- `out/city_delay_summary.csv` for the city-wide, population-weighted picture.
- If a category's `delta` distribution looks suspicious (all zero, all NULL, an absurd
  magnitude), that is very likely a parameter or data problem, not a real result — say so
  before trusting it.
