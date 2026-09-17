# Known issues — Easy-R5

Every entry here has a matching GitHub issue (CLAUDE.md policy).

| # | Issue | Summary | Workaround | Status |
|---|---|---|---|---|
| 1 | [#1](https://github.com/GISBoost/easy-R5/issues/1) | The Polish translation is machine-translated (local LLM) and now lags: strings added by the 0.1.x review fixes, the whole 0.2 downloader (`DownloadRealizedGtfs`, the recordings dialog), and the `TRANSIT_SUBMODES` parameter (F1) are English-only until the next `.ts` pass. | None — untranslated strings fall back to English; the plugin works in both. | Human review + re-`lupdate` planned before `experimental=False` |
| 2 | [#2](https://github.com/GISBoost/easy-R5/issues/2) | Isochrone detail is limited by `GRID_SPACING` — a coarse grid gives lumpy contours. | Lower `GRID_SPACING` (quadratic cost). | Contour quality fixed in 0.1.0 (TIN + marching-squares); resolution knob remains |
| 3 | [#3](https://github.com/GISBoost/easy-R5/issues/3) | The dead-date guard (`ALLOW_NO_SERVICE`) read `network.json`'s `service_days`, which `gtfs_calendar.compute_service_days` capped at 90 days from the **earliest** calendar entry across **all** feeds in the build folder — not per-feed, not centered on the routing date. A network combining a feed with an old calendar start (e.g. a rail feed starting many months earlier) with feeds relevant to a much later date got a capped summary that missed the real date entirely, so the guard false-positived "no active trips" even though every feed genuinely had service that day. | No longer needed — `compute_service_days` now windows each feed independently (own start, own cap) and sums by date; the default cap is also raised 90 -> 400 days (a defensive ceiling against sentinel `end_date`s, not a scope limit). | Fixed |
| 4 | [#5](https://github.com/GISBoost/easy-R5/issues/5) | Root cause found: **not a destination-count limit at all**. If a `QgsVectorLayer` pointing at the same GeoPackage source is already open in the QGIS project when the underlying table is later widened on disk (columns added, e.g. by another script), that layer's `fields()` stays cached at the old, narrower schema — but `getFeatures()` still returns raw attribute rows shaped like the *current*, wider table. `write_points_csv()`'s `lookupField(name)` then either returns -1 for a genuinely new column (silently coerced to 0) or the *wrong* index for an old one (silently reads a neighbouring column's value instead). Confirmed via `processing.run()` reproduction: `POI_Lodz`, a stale 12-field/3535-feature layer already in the project, corrupted a `RunAccessibility` call against the same source that had since grown to 23 fields/4161 features. | Fixed in `points.write_points_csv()` (`_check_fields_present`): any requested id/opportunity field missing from `source.fields()` now raises immediately with an actionable message, instead of silently defaulting to 0. Does not (cannot, from a Processing algorithm) stop QGIS from caching a stale layer — if you see the new error, remove the layer from the project and re-add it, or restart QGIS. | Fixed (plugin side) |
| 5 | [#6](https://github.com/GISBoost/easy-R5/issues/6) | `RunServiceMinutes` sets `recordTravelTimeHistograms=true` so it can read each destination's per-departure-minute histogram (`int[120]`) — keeping that per-minute distribution in memory for every destination roughly doubles the per-origin memory footprint versus a plain travel-time matrix run. | Lower `BATCH_SIZE` (the same advanced parameter the matrix/accessibility algorithms already expose). | Known — by design |

## Not bugs, but worth knowing

- **`experimental=True`** in `metadata.txt` until every M1–M5 acceptance criterion has
  passed on a clean install on Michał's machine (`DownloadR5` real download, `BuildNetwork`
  on a large PBF, the full pipeline from the QGIS dialog). M3 and M4 are agent-verified
  end-to-end; M4 reproduces r5r's Gdańsk accessibility exactly (`docs/notes/validation-gdansk.md`).
- **The travel-time matrix runs a walk-only companion pass per origin** to feed the
  walk-only detector (PRD §5.8). This roughly doubles routing wall time versus the raw
  r5r figure — a deliberate trade for the independent safety check.
- **R5 has no stable API.** The pinned version (`r5-v7.6-all.jar`) is load-bearing; a
  `network.dat` built by another R5 will not load and the runner reports
  `NETWORK_VERSION_MISMATCH`.
