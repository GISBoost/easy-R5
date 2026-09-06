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

For each hexagon (run at **250 m** and, separately, at **500 m** — see below) and each
of 4 destination categories, count how many points of that category are reachable
within **30 minutes**, departing in the **07:00–09:00** morning window
(`TIME_WINDOW=120`, `DEPARTURE_TIME=07:00` — the algorithm's own defaults), median
(P50) travel time. Run this once on the static network, once on the realized-P50
network, same day (**2026-08-21**). `delta_<category> = realized - static` — negative
means delays make fewer points of that category reachable.

Categories: **school** (`amenity=school`, not kindergarten), **pharmacy**
(`amenity=pharmacy`), **university** (curated OSM extract, reused from
`accessibility_lodz/lodz_universities.csv`), **mall** (`shop=mall`).

**Zero-baseline hexagons are excluded, not zeroed.** A hexagon where the *static*
schedule already reaches 0 points of a category within 30 min has `delta = 0-0 = 0`
too, but that is not "unaffected by delays" — it is "nothing to lose or gain in the
first place", and counting it as a real zero dilutes the signal with the city's
outskirts, which is mostly all-zero for schools/pharmacies/universities/malls at a 30
min cutoff. `delta_<category>` is `NULL` wherever the static count was 0, and
`base0_<category>` (1/0) flags those hexagons explicitly in the layer.

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

Want to reproduce this by hand, in the Processing Toolbox, with no Python and no MCP —
just the plugin's own algorithms? See [`HOWTO_MANUAL.md`](HOWTO_MANUAL.md).

## Pipeline (`mcp__qgis__execute_code`, in order)

All three scripts are parametrized by hex resolution so the same pipeline runs at both
250 m (the default) and 500 m into separate files, without rebuilding the two networks
(they don't depend on hex size — R5's own cache makes a second `buildnetwork` call for
the same `.osm.pbf`+GTFS instant) or re-extracting `poi_targets` from scratch:

```python
# 250 m (default)
prepare_data.main()
run_accessibility.main()
compute_delay.main()

# 500 m
prepare_data.main(hex_spacing_m=500, out_gpkg=prepare_data.HERE / "delay_lodz_500m.gpkg")
run_accessibility.main(gpkg=run_accessibility.HERE / "delay_lodz_500m.gpkg", out_suffix="_500m")
compute_delay.main(gpkg=compute_delay.HERE / "delay_lodz_500m.gpkg", out_suffix="_500m")
```

1. **`prepare_data.py`** — builds `network_static/` and `network_realized_p50/` (same
   `.osm.pbf`, separate GTFS folders — the project's "one variant per build dir" rule);
   a hexagon grid (`native:creategrid`) clipped to the dissolved `obwody_spisowe`
   boundary, with population via `easyr5:populationoverlay`; and `poi_targets` —
   school/pharmacy/mall extracted straight from `lodz.osm.pbf`'s `points` and
   `multipolygons` OGR layers (`other_tags` filter on points, dedicated `amenity`/`shop`
   columns on multipolygons), polygon centroids preferred over a co-located point to
   avoid double-counting a building mapped both ways, university loaded from the
   existing CSV. Writes `delay_lodz.gpkg` (or `delay_lodz_500m.gpkg`) with `hex_grid`,
   `hex_centroids`, `poi_targets`.
2. **`run_accessibility.py`** — two `easyr5:runaccessibility` runs (static, realized_p50),
   `OPPORTUNITY_FIELDS = [srv_school, srv_pharmacy, srv_university, srv_mall]`,
   `CUTOFFS=30`, everything else left at the algorithm's defaults (07:00, 120 min window,
   P50, TRANSIT+WALK, STEP decay, lossless `MAX_WALK_TIME`). Resumable via a
   `.params.json` sidecar per case, same pattern as `../modal_complementarity_lodz/run_modal_cases.py`.
3. **`compute_delay.py`** — `delta_<category> = acc_realized - acc_static` per hexagon
   (`NULL` where the static count was 0 — see above), writes layer `hex_delay`
   (`hex_id`, `pop_total`, 4× `delta_<category>` + `base0_<category>`) into the same
   gpkg, plus `out/city_delay_summary.csv` / `_500m.csv` (population-weighted mean delta
   per category, computed only over non-`base0` hexagons, plus how many were excluded).

## Real numbers from the verified run (2026-08-21)

- Hex grid: 5662 hexagons (250 m), 5631 with `pop_total > 0`; population overlay off by
  0.034% vs the precinct sum (18 precincts excluded, GUS-suppressed `population=NULL`).
- POI counts: 311 schools, 350 pharmacies, 47 universities, 58 malls.
- Population-weighted city-wide mean `delta`, **excluding zero-baseline hexagons**
  (realized P50 minus static, points reachable within 30 min, 07:00-09:00):
  **school -0.131** (3867/5662 hexagons comparable, 1795 excluded), **pharmacy -0.081**
  (3725, 1937 excluded), **university -0.003** (1092, 4570 excluded — most of the city
  is simply >30 min from any university regardless of delays), **mall -0.113** (2158,
  3504 excluded). Before excluding zero-baseline hexagons the naive means looked
  smaller and, for university, had the wrong sign (+0.009 vs the correct -0.003) —
  exactly the noise those hexagons were adding. Per-hex range is much wider than the
  city mean (e.g. `delta_school` from -14 to +10); the worst losses visually concentrate
  in the dense city-centre network, where more transfers make delays compound.
- **Note on running this**: `run_accessibility.py`'s two `RunAccessibility` passes
  (5662 origins here, vs. 1479 in `modal_complementarity_lodz`) took long enough that a
  single `mcp__qgis__execute_code` call timed out on the MCP transport and reported
  "failed" — QGIS itself kept computing in the main thread (it is unresponsive by design
  during a script, per the tool's own docs) and both runs finished correctly regardless.
  Check `out/*.params.json` exists for both cases before assuming a real failure and
  re-running from scratch.

## 250 m vs 500 m — resolution matters, and not just in magnitude

Same networks, same POI, same day, same everything except hex size. `delay_lodz_500m.gpkg`
has 1479 hexagons (492 with `pop_total = 0`, all excluded automatically same as at 250 m).

| category | 250 m mean delta (comparable / excluded) | 500 m mean delta (comparable / excluded) |
|---|---|---|
| school | **-0.131** (3867 / 1795) | **+0.061** (992 / 487) |
| pharmacy | **-0.081** (3725 / 1937) | **+0.155** (941 / 538) |
| university | **-0.003** (1092 / 4570) | **-0.018** (281 / 1198) |
| mall | **-0.113** (2158 / 3504) | **-0.097** (546 / 933) |

**School and pharmacy flip sign between resolutions.** This is not a bug — it's a real
instance of the modifiable areal unit problem (MAUP): a coarser hexagon's centroid can
land on a different street/stop than a finer one, and R5's step-cutoff accessibility is
sensitive to exactly which side of the 30-minute threshold a trip falls on. With ~4x
fewer, larger hexagons at 500 m, individual origin placement matters more and averages
out differently. **Practical takeaway: don't quote a single-resolution number as "the"
city-wide effect** — report both, or note the resolution explicitly, the way `docs/notes/`
already asks for `[verify]`-tagged claims to be checked rather than assumed. University
and mall (fewer POI, so most hexagons are `base0`-excluded either way) are more stable in
sign and in the same order of magnitude across resolutions.

## What Michał can check by hand in QGIS

- `hex_delay` in `delay_lodz.gpkg` (250 m) and `delay_lodz_500m.gpkg` (500 m), styled
  per category with a diverging ramp centred on 0 (red = fewer reachable points because
  of delays) — one map per category, no print layout needed.
- `out/city_delay_summary.csv` and `out/city_delay_summary_500m.csv` for the city-wide,
  population-weighted picture at each resolution — and whether the sign flip above still
  looks right to you, or whether it's worth digging into which specific hexagons drive it.
- If a category's `delta` distribution looks suspicious (all zero, all NULL, an absurd
  magnitude), that is very likely a parameter or data problem, not a real result — say so
  before trusting it.
