# tools/modal_complementarity_lodz — F2/F3/F4: modal-complementarity experiment

**Status: parked, not the flagship.** This was the first attempt at a headline result for
Easy-R5 — end-to-end, technically correct (I1-I3 invariants pass, ρ_POI = 0.9886 vs. Gdańsk),
and a real proof that `TRANSIT_SUBMODES` (F1) dogfoods correctly on the plugin's own
`RunAccessibility`. But holding it up against 2025-2026 literature (`docs/notes/
flagship-analysis-decision.md`) showed "counterfactual mode removal" is a fairly standard
method now, not distinctive enough to lead with — so we moved on to
[`tools/realtime_delay_lodz/`](../realtime_delay_lodz/README.md) (real GTFS-RT delays vs.
service reachability) instead. Left in place as a working example of dogfooding the plugin's
own algorithms for a real analysis, and as a candidate to revisit later (e.g. as a secondary
angle once the delay analysis has a home) — not deleted, just not the thing we're leading with.

**Standalone data-prep tooling**, not part of the plugin. Builds the ONE R5 network and the
ONE origins/destinations layer set that all four accessibility runs of
[`docs/prd/PR_easy-R5_flagship-lodz-modal.md`](../../docs/prd/PR_easy-R5_flagship-lodz-modal.md)
(W / T / B / TB, see §4.1) share — computed once so F3's four runs differ **only** by
`TRANSIT_SUBMODES`.

Inputs are **read-only** from [`tools/accessibility_lodz/`](../accessibility_lodz/) and
[`tools/ses_income_lodz/`](../ses_income_lodz/) — nothing there is modified or copied except
the one static GTFS feed (copied into `gtfs_static/`, because a realized P50/P85 feed shares
`trip_id`s with it and cannot share a network-build directory, per `CLAUDE.md`).

## Reproduce

Run `prepare_data.py` **inside the QGIS Python environment** — the QGIS Python console, or
`mcp__qgis__execute_code` — not a plain `py prepare_data.py` (needs `qgis.core` + `processing`
+ the `easy_r5` plugin registered, which a bare CPython interpreter does not have):

```python
exec(open("tools/modal_complementarity_lodz/prepare_data.py", encoding="utf-8").read())
```

Idempotent: `BuildNetwork` is cache-keyed by input hash + R5 version (instant re-run), the
GTFS copy is skip-if-exists, and `lodz_modal.gpkg` is rebuilt from scratch every run. **Run
against a fresh/empty QGIS project** — re-running against a project that already holds this
script's own temporary output layers from a prior run has been observed to corrupt the
population-overlay field calculator (spurious NaN); a QGIS processing-context artifact, not a
data issue. `mcp__qgis__create_new_project` (or File > New) before each run avoids it.

## Output

- `network_static/<hash>/network.dat` + `network.json` — gitignored, R5-version-pinned cache.
- `gtfs_static/lodz_static_gtfs_2026-08-21.zip` — gitignored copy of the ZDiT static feed.
- `lodz_modal.gpkg` — gitignored, four layers:
  - `hex_grid` — the 1,479 hex500 polygons (`hex_id` only, none of the 74 pilot columns) with
    the computed `pop_total`, `srv_education`, `srv_health`, `srv_culture`, `srv_groceries`,
    `srv_total` fields. Kept as polygons for a sane choropleth in QGIS.
  - `hex_centroids` — the same 1,479 hexagons, `hex_id` + centroid point only.
  - `hex_destinations` — `hex_centroids` + the same opportunity fields as `hex_grid`. **This
    is the one destinations layer for all four F3 runs** (PRD §4.3).
  - `poi_destinations` — the 1,328 exact POI points from `lodz_services.csv`, `srv_total=1` +
    one-hot `srv_<category>` fields. Used only by F3's control run (§9: Spearman ρ ≥ 0.95
    between the hex-centroid and exact-point versions of `srv_total_30min`).

## Control numbers (this run, `prepare_data.py` output)

| check | value | gate |
|---|---|---|
| Active trips, 2026-08-24 (`network.json`) | **9,893** | must equal 9,893 |
| Σ `pop_total` over hexagons | 669,408.0 | — |
| Σ `population` over non-NULL precincts | 669,995.0 | — |
| Relative difference | **0.088%** | ≤ 1% |
| Precincts with `population = NULL` (GUS suppression) | 18, covering **4.32 km²** | documented, not zeroed |
| Hexagons with `pop_total > 0` | **1,477** | must be ≫ 640 (pilot point-in-polygon count) |
| Σ `srv_total` over hexagons | **1,328** | must equal 1,328 (no POI lost or double-counted) |
| POI outside the hex grid boundary | 0 | logged if any |

Σ population ≈ 670k matches Łódź's real population closely — sanity-consistent.

## The `Z1`/`Z2`/`P1`/`P2`/`R8`/`O` question (PRD §3.2)

`routes.txt` carries no `route_long_name`/`route_desc` for these six `route_type=0` (tram)
routes, so the answer came from `trip_headsign` in `trips.txt` instead:

- **`Z1`, `Z2`, `O`** — real passenger tram lines with real destinations (`DOŁY`,
  `DW. ŁÓDŹ ŻABIENIEC`, `DW. ŁÓDŹ DĄBROWA`, `PÓŁNOCNA`, `RADIOSTACJA`, `CHOCIANOWICE IKEA`).
  **Not** replacement/"zastępcze" trams as the PRD's own working hypothesis guessed — that
  hypothesis was wrong. The extra headsign `"<line> DO ZAJEZDNI ..."` on some trips is just the
  last run of the day returning to depot, a normal GTFS pattern, not evidence of a special line.
- **`R8`** — same pattern, only 6 trips/day, heading to depot `TELEFONICZNA`.
- **`P1`, `P2`** — every one of their 72 and 90 trips has `trip_headsign = "PRZEWÓZ
  PRACOWNIKÓW"` ("worker transport"). These are worker-shuttle lines, not general-purpose
  passenger routes — kept in the data as-is (not removed), since they are published GTFS
  `route_type=0` service and the PRD says not to guess or delete.

None of these routes were removed from the network or from any count in this milestone.

## F3 — the four modal-case runs (`run_modal_cases.py`, `check_invariants.py`, `compute_metrics.py`, `poi_control.py`)

Run in this order, all inside the QGIS Python environment (same caveat as `prepare_data.py` —
`check_invariants.py` is the one exception, pure stdlib, runs with plain `py`):

```python
exec(open("tools/modal_complementarity_lodz/run_modal_cases.py", encoding="utf-8").read())
# then, plain `py check_invariants.py` (or inside QGIS, same effect) — stops on I1/I2/I3 failure
exec(open("tools/modal_complementarity_lodz/compute_metrics.py", encoding="utf-8").read())
exec(open("tools/modal_complementarity_lodz/poi_control.py", encoding="utf-8").read())
```

`run_modal_cases.py` is resumable — a case is skipped if `out/acc_<id>.csv` already matches the
requested parameters (`out/acc_<id>.params.json`).

**This run's numbers** (see [`COLUMNS.md`](COLUMNS.md) for what every field means):

| check | value | gate |
|---|---|---|
| Four runs' wall time (W / T / B / TB) | 37.0 / 82.6 / 93.2 / 104.4 s (≈5.3 min total) | measured, in `out/run_meta.json` |
| `I1`, `I2` violations | **0** out of 177,480 rows | must be 0 |
| `I3` (R5 respects `TRANSIT_SUBMODES`) | **0.308** | must be > 0.05 |
| POI control, Spearman ρ (hex-centroid vs exact-POI `srv_total_30min`) | **0.9886** | ≥ 0.95 |
| Hexagons failing the K=1,000 reliability gate (shares NULL there) | 474 / 1,479 | documented in `run_meta.json` |
| `Ā^TB(30)`, person-weighted (headline city number) | **82,747** people | — |
| City `subadd(30)` | **0.9047** (< 1, sub-additive — matches the literature) | — |

Outputs (all gitignored, in `out/`): `acc_<W\|T\|B\|TB>.csv` (+ `.gpkg`, `.meta.json`,
`.params.json`), `acc_poi_control.csv`, `run_meta.json`, `invariants.json`, `poi_control.json`,
`hex_modal.csv`, `city_summary.csv`. Plus the `hex_modal` layer added to `lodz_modal.gpkg`.

**Scope decision, flagged for Michał:** the per-hex metric fields on `hex_modal` are computed
for opportunity=`pop_total` only (not every opportunity × percentile combination — see
`COLUMNS.md`'s "Scope of the per-hex fields"). This wasn't explicit in the F3 prompt; the
alternative (~1,700 fields covering every percentile/opportunity) had no identified consumer in
F4/F5, so this is a judgment call, not a hidden assumption — flag if a different scope is
wanted before F4 cartography locks in field names.

## F4 — cartography (`make_figures.py`) — **P3 done, P1/P2 blocked**

```python
exec(open("tools/modal_complementarity_lodz/make_figures.py", encoding="utf-8").read())
```

**P3** (`docs/img/flagship-lodz-modal-bars.png`) — done, verified visually. Person-weighted
accessibility by modal case × cutoff, the `no_transfer` marker line, subadd annotations.

**P1/P2** (`docs/img/flagship-lodz-tram-share-*.png`, `flagship-lodz-transfer-premium-*.png`)
— **not produced.** The text layer, legend-woven sentence, disclaimer, source line and tram
network inset all render correctly, but the `hex_modal` choropleth fill itself renders as a
blank map panel, in every configuration tried:

| Renderer tried | Result |
|---|---|
| `QgsRuleBasedRenderer`, full rule tree (7 classes + 2 sentinel rules) | blank |
| `QgsRuleBasedRenderer`, simplest possible (1 root + 1 catch-all child, solid fill) | blank |
| `QgsGraduatedSymbolRenderer` with a `CASE WHEN...` classification expression | blank |
| `QgsSingleSymbolRenderer` (QGIS's own default, unstyled) | **renders fine** |

So the map item, the layer, the CRS (tested both the native UWPP_1992 and reprojected
EPSG:2180 — same result either way) and the extent are all fine; something specific to how
this QGIS 3.40.5 build paints a *classified* (rule-based or graduated) vector renderer inside a
`QgsLayoutItemMap` during `QgsLayoutExporter.exportToImage()` is not working. `renderer.
originalSymbolsForFeature()` confirms every feature matches exactly one rule/range correctly —
the classification logic itself is right; only the actual paint step produces nothing.
Diagnosed 2026-09-05 via `mcp__qgis__execute_code`, ~10 isolated tests; not resolved. Two
unrelated bugs found and fixed along the way, both load-bearing for anyone touching this file
next:

1. `QgsLayout.setUnits(QgsUnitTypes.LayoutPixels)` silently breaks text sizing (labels render
   at a fixed ~8px regardless of requested size) — fixed by working in millimeters/points
   internally (`mm()`/`pt()` helpers) while keeping the public API in "design pixels" matching
   the PRD's px spec.
2. `hex_modal`'s native CRS (UWPP_1992, F2/F3, no EPSG code) reads as `isValid() == True` but
   was a red herring for the blank-map bug above — real, unrelated to the renderer issue.

**What Michał can try by hand:** open `lodz_modal.gpkg`'s `hex_modal` layer in the QGIS GUI,
apply a graduated style through the Layer Properties dialog (not via `saveNamedStyle()`/PyQGIS
scripting) on the same field, and see whether it renders on the canvas and prints via Layout
Manager — that isolates whether this is a scripting-API-specific issue or a genuine QGIS 3.40.5
rendering bug. The `.qml` files this script already produced
(`styles/flagship-lodz-tram-share.qml`, `styles/flagship-lodz-transfer-premium.qml`) can be
applied to `hex_modal` via *Layer → Properties → Style → Load Style* to skip re-specifying the
classes.

## What is gitignored

`network_static/`, `gtfs_static/`, `*.gpkg`, `out/`, `__pycache__/` — data, not code. Only the
`.py` scripts, `.gitignore`, `COLUMNS.md`, `styles/` (`.qml` + `palette.md`) and this
`README.md` are versioned, per `CLAUDE.md`'s "wersjonujemy kod i dokumentację, nie dane".
