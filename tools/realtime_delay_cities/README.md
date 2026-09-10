# realtime_delay_cities — the Łódź delay-vs-accessibility analysis, for 5 more cities

Sister of [`../realtime_delay_lodz/`](../realtime_delay_lodz/README.md). Same
question, same method, same Easy-R5 algorithms — run for **Gdańsk, Warszawa,
Poznań, Kraków, Szczecin** on the same real day, **2026-08-24**, to
confirm or refute one hypothesis: **do transit delays punish a transfer-zone
*ring* around the core rather than the centre uniformly?** (Łódź showed a sharp
dip at 2–3 km.)

**Question.** Where in each city do real-world transit delays most degrade
public-transport reachability? Accessibility on the *static* GTFS schedule vs
the *realized P50* schedule (median of what vehicles actually did), same day,
same network otherwise.

## Inputs — all already local, nothing downloaded

| Input | Source |
|---|---|
| `.osm.pbf` | `../isochrones_lodz/<city>_network_static/<city>.osm.pbf` |
| GTFS static, 2026-08-24 | `../isochrones_lodz/<city>_network_static/<city>_static_gtfs_2026-08-24.zip` |
| GTFS realized P50, 2026-08-24 | `../isochrones_lodz/<city>_network_rt/<city>_realized_2026-08-24_p50.zip` |
| Population per census precinct | `../ses_income_lodz/<city>.gpkg` layer `obwody_spisowe`, field `population` (real GUS count) |
| Universities | `../accessibility_cities/<city>/<city>_universities.csv` |

`validate_gtfs.py` (pure stdlib, run first) checks every feed **before** any R5
build: required files present and non-empty, ≥3000 trips active on 2026-08-24
(else silent walk-only — CLAUDE.md gotcha #1), monotonic arrival times, and
static vs realized identical trip / stop sets with a plausible realized-vs-
static shift distribution (near-zero median, fat *late* tail, negligible
grossly-early mass). All 5 cities pass.

## Resolutions

250 m **and** 500 m for every city **except Warszawa** (500 m only — a 250 m
grid over the whole city is a real R5 memory/time risk per easy-R5 CLAUDE.md).

## Method (identical to realtime_delay_lodz)

For each hexagon and each of 4 destination categories (**school**
`amenity=school`, **pharmacy** `amenity=pharmacy`, **university** curated OSM
extract, **mall** `shop=mall`), count points reachable within **30 min**,
departing **07:00–09:00** (`TIME_WINDOW=120`), median (P50) travel time.
`delta_<category> = realized − static`. **Zero-baseline hexagons are NULL, not
zeroed** (`base0_<category>` flags them; `base_<category>` is the plain static
count). `hex_net_opportunities.net_delta` sums `delta` over the comparable
categories; `net_delta_n` records how many.

Legend: **manual, zero-isolated** ColorBrewer RdBu-7 (7 classes, 0 its own
singleton, half-integer edges) — never automatic equal-interval/quantile.
See `style_delay_layers.py` (copied verbatim from the Łódź analysis).

## Pipeline (`mcp__qgis__execute_code`, in order)

```python
import run_all
run_all.city("gdansk")     # prepare_data -> run_accessibility -> compute_delay, all resolutions
run_all.everything()       # every city; Warszawa last (heaviest)

import dasymetric_pop as dp; dp.apply_all()           # replace areal pop with OSM-building
                                                      # dasymetric, drop empty hexes (§below)
# then re-run compute_delay for every city/res, no R5 needed

import chart_distance_delta as ch; ch.everything()   # transfer-zone bar charts + verdicts
import build_project;   build_project.main()          # delay_cities.qgz
import export_geojson;  export_geojson.main()         # -> mapy-analizy/opoznienia-dostepnosc/data/
```
then, plain `py`:
```
py collect_run_stats.py    # out/run_stats.csv/.json -- diagnostics sweep over every pass
py cross_city_summary.py   # out/cross_city_delay.csv, out/cross_city_net.csv, out/HYPOTHESIS.md
py analyze_gtfs_shifts.py  # out/gtfs_shift_by_traction.csv -- AM-peak tram/bus late-vs-early
py hex_breakdown.py        # out/hex_breakdown.csv -- gain/loss/unchanged hex counts (incl. Łódź)
py export_report_data.py   # -> mapy-analizy/badanie-opoznienia/report_data.json (the write-up page)
```

- **`dasymetric_pop.py`** — replaces `prepare_data`'s **areal** population
  (`easyr5:populationoverlay` spreads a precinct's GUS count uniformly over its
  whole polygon → phantom residents on fields / rail / port) with a
  **dasymetric** estimate: each precinct's population redistributed onto its
  OSM building footprint, mass-preserving, uniform-areal fallback for
  building-less precincts. Hexagons < 0.5 person are dropped from `hex_grid` /
  `hex_centroids` (`siatka` kept). Building raster cached in `work/dasym/`.
  Idempotent (uses `siatka` as the stable geometry source). Full write-up:
  `FINDINGS.md` §0. Run `apply_all()` then re-run `compute_delay` for all.
- **`prepare_data.py`** — two R5 networks per city (`work/<city>/network_*`,
  one GTFS variant per folder), hex grid clipped to the dissolved
  `obwody_spisowe` boundary + area-weighted population via
  `easyr5:populationoverlay` (later replaced by `dasymetric_pop.py`),
  `poi_targets` from the city `.osm.pbf`. Gate: the
  static network's `service_days[2026-08-24]` is the reference; realized must
  match it exactly and be ≥ `cities.MIN_TRIPS`. Writes `delay_<city>[_500m].gpkg`
  (`hex_grid`, `hex_centroids`, `poi_targets`, `boundary`, `siatka`).
- **`run_accessibility.py`** — two `easyr5:runaccessibility` passes (static,
  realized_p50), `CUTOFFS=30`, everything else the algorithm's defaults.
  Resumable via a `.params.json` sidecar per case.
- **`compute_delay.py`** — `delta` / `base0` / `base` per hex, `hex_delay` +
  `hex_net_opportunities` into the gpkg, `out/<city>_delay_summary[_500m].csv`
  and `out/<city>_net_summary[_500m].csv` (population-weighted, comparable
  hexagons only).
- **`chart_distance_delta.py`** — the transfer-zone test: `net_delta` binned by
  1 km distance from each city's population-weighted centroid, same colours as
  the maps, plus a machine-readable verdict (`out/charts/transfer_ring_*.json`).
- **`analyze_gtfs_shifts.py`** — stdlib: per city, how many trips run late /
  early / unchanged on the analysis day (whole day + 07:00–09:00), split by
  traction (tram / bus / …) → `out/gtfs_shift_by_traction.csv`. The morning-peak
  tram/bus balance predicts each city's `net_delta` sign.
- **`hex_breakdown.py`** — ogr: hexagon-count breakdown (gain / loss /
  unchanged / no-baseline) next to the population-weighted **and** unweighted
  mean, per city/resolution/category → `out/hex_breakdown.csv`. Shows the
  headline number is pop-weighted and ~2–3× the plain per-hex mean.
- **`collect_run_stats.py`** — stdlib+ogr diagnostics sweep: per city/resolution
  it pulls the R5 build info, gate trip counts, hex + POI counts, population
  overlay sum, per-category comparable/zero-baseline counts, net mean, the
  transfer verdict and approximate pass durations from every artifact the run
  left behind → `out/run_stats.csv` / `.json` + a printed table.
- **`cross_city_summary.py`** — rolls the 5 cities **+ Łódź** into
  `out/cross_city_*.csv` and `out/HYPOTHESIS.md`.
- **`rebuild_boundary.py`** — rewrites each gpkg's `boundary` layer as the
  **dissolve of the hex grid** (a stepped outline that hugs the hexes, like
  Łódź), replacing the smooth dissolved `obwody_spisowe`. A ±1 m buffer
  round-trip closes the sub-metre seams a plain dissolve of a 250 m grid leaves
  open. `prepare_data` now does the same for fresh runs; this is the retrofit.
- **`build_project.py`** — `delay_cities.qgz`, one group per city.
- **`export_geojson.py`** — per-city GeoJSON + a 6-city `manifest.json` into
  the sibling `mapy-analizy/opoznienia-dostepnosc` page (which gains a city
  switcher on top of its resolution tabs / category panel).
- **`export_report_data.py`** — rolls `out/*.csv` into one small
  `report_data.json` for `mapy-analizy/badanie-opoznienia/` — the public
  write-up page (own tab in the mapy-analizy top bar) that turns FINDINGS.md
  into charts a non-specialist can read.

## Results

See **[`FINDINGS.md`](FINDINGS.md)** for the write-up. Headline:

1. **The transfer-zone hypothesis is refuted as a general pattern.** Only Łódź
   has the 2–3 km mid-ring dip; the other 5 cities show a monotone radial
   gradient (core benefits most, outskirts least) — the opposite.
2. **The city-wide sign is a property of the static schedule, not of delays.**
   Poznań / Szczecin / Warszawa go strongly *positive* (realized-P50 beats a
   peak-padded timetable), Kraków negative (tight schedule), Gdańsk / Łódź ≈ 0.
   Stable across category and resolution; confirmed for Poznań with a full
   5132 × 681 O-D travel-time matrix.

## What Michał checks by hand

- `out/HYPOTHESIS.md` — the transfer-zone verdict per city/resolution; does it
  match what the `out/charts/transfer_ring_*.png` bars show?
- `out/cross_city_delay.csv` — per-category city-wide means; any category that
  is all-zero / all-NULL / absurd magnitude is a data or parameter problem, not
  a result.
- `delay_cities.qgz` in QGIS — `hex_net_opportunities` per city, swap the
  classified field on `hex_delay` for the per-category maps.
- The `mapy-analizy/opoznienia-dostepnosc` page with the city switcher.
