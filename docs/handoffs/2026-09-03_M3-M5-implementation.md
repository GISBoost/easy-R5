# Handoff — M3 → M5 implemented, v0.1.0 (2026-09-03)

Same convention as [`easy-OTP/docs/handoffs/`](https://github.com/GISBoost/easy-OTP/tree/main/docs/handoffs).
Written for the next session / the milestone reviewer.

---

## TL;DR

- **All of M1–M5 is implemented and committed on `main`.** `metadata.txt` is at
  `version=0.1.0`, `experimental=True`.
- **8 Processing algorithms.** 120 pytest green, flake8 clean, tree clean.
- **M3 and M4 verified end-to-end against the live R5 7.6 engine** on the Gdańsk
  reference network. M4 (`RunAccessibility`) **reproduces r5r's Gdańsk output
  exactly** — every one of 27 780 rows, RMSE 0.00 — see
  [`../notes/validation-gdansk.md`](../notes/validation-gdansk.md).
- **M5 (isochrones, population layers, release scaffold) verified in QGIS 3.40**
  via the MCP bridge, not against a clean-install pipeline.
- **What still needs Michał:** a clean-profile run of
  install → `DownloadR5` (real download) → `BuildNetwork` (large PBF) →
  `RunAccessibility` / `GenerateIsochrones` from the QGIS dialog; then flip
  `experimental=False` if every M1–M5 acceptance criterion passed.

---

## What was built, milestone by milestone

### M3 — `RunTravelTimeMatrix` (flagship) — commits `b4c5f16`..`88dca58`

| file | what |
|---|---|
| `easy_r5/java/EasyR5Runner.java` | `command: "matrix"` — ports the verified `docs/reference/probe/Probe.java` recipe: `RegionalTask`, `FreeFormPointSet` built **once per process**, one `TravelTimeComputer` call per origin. `r.maxWalkTime` always set. Unreachable cells written blank (never `0`, never `2147483647`). For transit runs, a walk-only companion computation per origin feeds `RESULT transit_used_pairs` (the independent walk-only detector). `findSplit` pre-check warns on unlinked points, aborts only if zero destinations link. |
| `easy_r5/core/job_spec.py` | `build_matrix_job` — the PRD §3.2 shape; `max_walk_time_minutes` is always a positive int (empty/≤0 → `max_trip_duration_minutes`). |
| `easy_r5/core/points.py` | `write_points_csv` — layer → `id,lon,lat` CSV in EPSG:4326, `stable_ids` (unique, no CSV metacharacters), 6-decimal rounding matching Probe. Raises on a missing source CRS. `extra_fields` appends numeric columns (M4 opportunity fields). |
| `easy_r5/core/matrix.py` | `systematic_sample_indices` (ESTIMATE_FIRST probe), `merge_batch_csvs`, `nearest_served_days` (dead-date message), `build_od_lines` (+ optional CRS transform), `od_line_fields`. |
| `easy_r5/algorithms/run_travel_time_matrix.py` | `RunTravelTimeMatrix`, Analysis group. Since `f5a78d7` this is thin — the shared machinery lives in `_matrix_base.MatrixBase`. |

**Gates before any Java, in order:** percentiles (`job_spec.parse_percentiles`) →
dead-date hard block for transit runs (names the 3 nearest served days;
overridable only by advanced `ALLOW_NO_SERVICE`) → `MAX_WALK_TIME` empty →
`MAX_TRIP_DURATION`. Then `ESTIMATE_FIRST` (15 spread origins, measured s/origin
+ extrapolation), then the batched full run (`origin_range` chunks, one process
per batch), then `merge_batch_csvs`, then the post-run walk-only guard
(`transit_used_pairs == 0` in a transit run → fail).

**Verified against R5 7.6 on the Gdańsk network:**
- 1389 × 956, 07:00 +120 min, P50, cap 90 → **1 min 43 s**, 900 533 rows, no
  `2147483647`, `transit_used_pairs = 876 726`.
- origin `0` → `ser_4` P50 = **79 min**, matches `Probe.java` exactly.
- Cancel mid-run via `runner.run_job` → `RunnerCancelled` ~6 s, **no orphan
  `java.exe`**.
- 6 percentiles → validation error before the JVM starts.
- Dead date `2026-01-01` → blocked, lists `2026-08-22/23/24`.
- `ALLOW_NO_SERVICE=True` on a dead date → runs, then fails on the walk-only
  detector.
- EPSG:2180 origins == EPSG:4326 origins (identical CSV).
- `-Xmx48m` → `OUT_OF_MEMORY`, exit 1, actionable message.

### M4 — `RunAccessibility` + Gdańsk validation — commits `f5a78d7`..`d5554a5`

| file | what |
|---|---|
| `easy_r5/algorithms/_matrix_base.py` | **`MatrixBase` mixin** — extracted from M3. Holds the shared parameters (`_add_matrix_params`, with an optional `with_destinations=False`) and the whole batched run (`_run_matrix`, returns the merged matrix CSV + id lists + method-metadata + `origins_crs`). Both `RunAccessibility` and `GenerateIsochrones` mix it in. Its strings go through a module-level `_tr()` bound to context `"MatrixBase"` (see i18n note below). |
| `easy_r5/core/accessibility.py` | `decay_weight` (**STEP is a strict `travelTime < cutoff`**, verified from R5's `StepDecayFunction` bytecode — this is what makes the r5r diff exact; EXPONENTIAL and LOGISTIC provided, unvalidated), `compute_accessibility` (long rows in r5r's layout; origins with nothing reachable → 0, never NULL), `read_opportunities`. |
| `easy_r5/algorithms/run_accessibility.py` | `RunAccessibility` — `OPPORTUNITY_FIELDS` / `CUTOFFS` / `DECAY`; `MAX_WALK_TIME` blank → `max(CUTOFFS)` for STEP, `MAX_TRIP_DURATION` otherwise. Long CSV (`id,opportunity,percentile,cutoff,accessibility` — r5r's exact shape) + an ORIGINS copy with `acc_<opp>_p<pct>_c<cutoff>` fields, in the origin CRS. `<csv>.meta.json` sidecar. |

**Validation ([`../notes/validation-gdansk.md`](../notes/validation-gdansk.md)):**
r5r's departure date is not recorded anywhere in the repo. Reconstructed by
running the matrix on each candidate:

| date | rows exactly equal | RMSE |
|---|---|---|
| 2026-08-22 (Sat) | 56.6 % | 13.76 |
| **2026-08-24 (Mon)** | **100.0 %** (27 780 / 27 780) | **0.00** |
| 2026-08-25 (Mon) | 97.5 % | 1.37 |

With date `2026-08-24` and the strict-`<` step function, Easy-R5 reproduces
`gdansk_service_accessibility.csv` **byte-for-byte** — despite R5 7.6 vs r5r's
7.5.1.

### M5 — isochrones, population layers, release — commits `ecf3896`..`96ab9dc`

| file | what |
|---|---|
| `easy_r5/algorithms/generate_isochrones.py` | `GenerateIsochrones`. **R5 has no native isochrone output** (checked the 7.6 jar; r5r `isochrone()` = grid + `isoband` contour in R, r5py = grid + shapely, Conveyal = grid + browser contour — grid-then-contour *is* the standard). Implementation: full destination grid (metric UTM working CRS) → one-origin matrix via `MatrixBase` → per grid cell, travel time or a sentinel above the cutoffs for unreachable → `qgis:tininterpolation` raster → `gdal:contour_polygon` per cutoff (`INTERVAL 0`, `EXTRA "-fl <c>"`) → union bands ≤ c → `removeInteriorRings(spacing²·4)` (drops interpolation specks, **keeps real unreachable pockets** — merit-correct) → transform to the origin CRS. One contour run per cutoff, so one failure is reported and skipped without losing the rest. Grid clipped to `native:extractwithindistance` of the origins; blocked above ~400 k grid points. |
| `easy_r5/core/dependencies.py` | Trimmed copy of easy-OTP's — **openpyxl only** (no GTFS-RT). urllib wheel + SHA-256, no `pip`. Called best-effort from `EasyR5Plugin.initGui()`. Fallback unpack dir `easy_r5/_vendor/` (gitignored). **openpyxl exception confirmed by Michał 2026-09-03, recorded in `CLAUDE.md`.** |
| `easy_r5/core/xlsx_reader.py` | Verbatim copy — standalone CLI, run as a subprocess (libxml2 clashes with QGIS's Qt stack from a worker thread). |
| `easy_r5/algorithms/prepare_population_layer.py` | `PreparePopulationLayer` — renamed copy of easy-OTP's `prepare_student_layer.py` (it reads any GUS NSP 2021 sheet). |
| `easy_r5/algorithms/population_overlay.py` | `PopulationOverlay` — copy of easy-OTP's; the output field stays **Float** (the QGIS reference model rounded residents to int). |
| `easy_r5/core/styling.py` + `easy_r5/styles/*.qml` | `apply_style` attaches a layer post-processor via `QgsProcessingContext`; `isochrones.qml` / `accessibility.qml` / `od_lines.qml` auto-applied. |
| `easy_r5/easy_r5.pro`, `easy_r5/i18n/easy_r5_pl.ts` + `.qm`, `tools/i18n/build_matrixbase_context.py` | Polish translation, see below. |
| `README.md`, `KNOWN_ISSUES.md`, `docs/img/isochrones-gdansk.png` | Rewritten with real usage + the stock-QGIS hex-grid recipe (PRD §4.7 — no hex-grid algorithm). |

**Verified in QGIS 3.40:**
- All 8 algorithms register.
- Isochrones: single- and multi-origin, EPSG:4326 and EPSG:2180 inputs; nested
  and strictly growing per origin; all geometries valid; unreachable pockets
  kept as interior rings; output in the origin CRS.
- `PreparePopulationLayer` matches easy-OTP's `PrepareStudentLayer` **byte-for-byte**
  on the same GUS NSP file (sum 2207, 0 rows differ).
- `PopulationOverlay` produces fractional hex values (field type `Real`,
  sum 2206.6 / 2207.0).
- Styles auto-apply (categorised on `cutoff_min`, etc.).

---

## Cross-cutting

### CRS

Audited with the `qgis-core-coordinate-systems` skill. All `QgsCoordinateTransform`
calls use the Processing `context.transformContext()`.

- `points.write_points_csv` raises a clear error on a missing source CRS.
- **Every vector output follows the input (origin) CRS** — `RunAccessibility`,
  `GenerateIsochrones`, and the optional OD-line layer. The matrix CSV stays
  lon/lat (WGS84) by design — that is what R5 consumes and what keeps it
  r5r-compatible.
- `GenerateIsochrones` derives a metric working CRS (UTM zone under the origins'
  centroid, string constructor + `isValid()`, zone clamped 1..60) for the grid /
  raster / contour, then transforms the result back to the origin CRS.

Verified: EPSG:2180 origins → matrix rows correct, accessibility + isochrone +
OD-line outputs all carry EPSG:2180, R5 still receives correct lon/lat.

### i18n

`easy_r5_pl.ts` + compiled `easy_r5_pl.qm` — **213/213 strings translated**,
every context. Machine translation via a **local LLM** (`gemma-4-e4b` at
`http://127.0.0.1:1234`, OpenAI-compatible). A human review pass is
[issue #1](https://github.com/GISBoost/easy-R5/issues/1) — a few awkward
renderings (`konturuje`, `cutoff_min` → "minimalny próg").

`_matrix_base.py` routes its strings through a module `_tr(s)` bound to context
`"MatrixBase"` so they resolve under one stable context at runtime — but
`pylupdate5` cannot see them. **Build order:**

```
pylupdate5 -noobsolete easy_r5/easy_r5.pro      # regenerates every other context
py tools/i18n/build_matrixbase_context.py       # scans _tr("...") -> MatrixBase context in the .ts
py <translate script>                           # fills unfinished (LLM); the MatrixBase context is re-translated each run
lrelease easy_r5/i18n/easy_r5_pl.ts             # -> .qm
```

`lrelease` is **not** in this QGIS install — used `pyside6-essentials`
(`pip install --target <dir> pyside6-essentials`, then `<dir>/PySide6/lrelease.exe`).
The translate script used this session lives in the scratchpad
(`.../scratchpad/m3/translate_full.py`), not in the repo.

### Milestone-reviewer response (2026-09-03, later the same day)

The `milestone-reviewer` agent was run against M3, M4, M5. M3/M4 passed with
notes; M5 failed on one hard-constraint breach. Fixes applied (tests + flake8
green, `EasyR5Runner.java` still compiles against the 7.6 jar, one file):

- **M5 blocker — `pip` in the plugin.** `core/dependencies.install_openpyxl`
  had a `subprocess … pip install --user` fallback carried over from easy-OTP.
  Removed (with `import subprocess` and the dead interpreter-locator helpers);
  the only path now is the SHA-256-verified urllib wheel into the user site or
  `easy_r5/_vendor/`, then a "install it yourself" message.
- **OOM robustness (M3).** `-XX:+ExitOnOutOfMemoryError` is now always in the
  JVM args (`java_env.build_java_command`) so an OOM in an R5 ForkJoinPool
  worker can't hang the process; `runner.run_job` matches more JVM OOM markers.
- **Estimate methodology (M3/M5).** The runner now emits `RESULT setup_seconds`
  / `RESULT routing_seconds`; `_estimate` extrapolates from routing time only
  and reports the one-off setup cost separately, instead of dividing the whole
  probe wall-clock (JVM boot + 100 MB deserialize + link) by 15.
- **Gate hardening (M3).** `DATE` / `DEPARTURE_TIME` format-validated in Python
  before the JVM; a transit run against a network with no `service_days` now
  warns instead of silently skipping the dead-date gate; `RunnerCancelled`
  during the estimate is a clean cancel.
- **Method field name (M4/M5).** Output-layer metadata field renamed
  `percentiles` → `percentile` (PRD §5.2 / §4.5 / §4.6). `GenerateIsochrones`
  now requires exactly one percentile, carries `time_window`, and stamps the
  real single percentile value.
- **M4.** `RunAccessibility` raises `MAX_TRIP_DURATION` to `max(CUTOFFS)` when a
  cutoff would otherwise truncate the matrix; the feature↔result join is by id
  value (not iteration position) when `ORIGIN_ID_FIELD` is set; a fractional
  STEP sum (residents from `PopulationOverlay`) keeps decimals instead of being
  truncated to int.
- **Small.** `QSettings().value("locale/userLocale")` guarded against `None`;
  `easy_r5_pl.ts` gained `language="pl"`; `metadata.txt` `about=` updated to the
  real v0.1 algorithm list; large one-origin isochrone grids warn about runtime.
- **Tests.** `test_dependencies.py` (zip-slip guard), `test_isochrones.py`
  (`utm_epsg` moved to `core/matrix.py`), extra `test_accessibility.py` cases
  (unknown decay, exponential zero-cutoff, fractional STEP, `read_opportunities`).
  132 pytest green.

Still open from the reviews (not blockers, deferred): the walk-only companion
computation doubles routing time on transit matrices (§5.8 cost, documented);
`warnUnlinked` reports the global count in every batch log; per-origin `iso_t`
memory layers are only freed at algorithm end.

### Known issues (both have a GitHub issue — CLAUDE.md policy)

- **#1** — Polish translation is fully populated but machine-translated; needs a
  human pass.
- **#2** — isochrone detail is bounded by `GRID_SPACING`; contour *quality* was
  fixed in 0.1.0 (TIN + marching squares), the resolution knob remains.

---

## Environment / how the agent verified

- Java + R5: `C:\Users\Michal\easy-r5\` (`jdk-21.0.12.1+1`, `r5-v7.6-all.jar`,
  `runner_cache/`). QSettings `[easy_r5]` populated. The Java runner is
  recompiled into `runner_cache/` after any `.java` edit.
- Test network built by the agent from `tools/accessibility_cities/gdansk/`
  (`gdansk.osm.pbf` + `gdansk_gtfs.zip`) via the runner's `build` command, with
  `service_days` merged in — kept in the session scratchpad, not the repo.
- The **installed plugin is a copy** at
  `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\easy_r5\` — files are
  synced there and the plugin reloaded via the MCP QGIS bridge for every test.

---

## What is NOT done (for Michał / the next session)

1. **Clean-profile pipeline** (the agent has no clean profile, no real
   Adoptium/GitHub-Releases download, no large PBF):
   - install `easy_r5-0.1.0.zip` on a fresh profile → all 8 algorithms in the
     toolbox;
   - `DownloadR5` — real download, no admin rights, SHA-256;
   - `BuildNetwork` on a large PBF — wall time, peak RAM, cache hit on re-run,
     no orphaned `java.exe` on cancel, OOM → readable message;
   - `TestR5Setup` output;
   - run the matrix / accessibility / isochrones from the **QGIS dialog** on
     Michał's own layers; spot-check OD pairs against the operator's journey
     planner;
   - the Gdańsk accessibility map next to `tools/accessibility_cities/out/` —
     same spatial pattern? (numbers already exact).
2. **Flip `experimental=False`** only if all of the above passes.
3. **Human review of the Polish translation** (issue #1).
4. Minor: the isochrone grid still logs "N of M destinations not near any
   street" (expected — grid over sea / past the network — but noisy); a
   `quiet_unlinked` flag could be threaded to the Java `WARN`.
