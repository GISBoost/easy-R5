# R5 engine primer

Everything an agent needs to know about Conveyal R5 before writing a line of Easy-R5.
Facts here were checked against `conveyal/r5` **v7.6** (released 2026-08-01) and the two
existing language bindings (`r5r` 2.4.0, `r5py` main branch) in September 2026. Items marked
**[verify]** are inferences that nobody has run yet — confirm them against a real run before
building on them.

---

## 1. What R5 is

R5 = "Rapid Realistic Routing on Real-world and Reimagined networks". Conveyal's routing engine
behind their web analysis product. Multimodal (walk / bike / car / transit), built around one
idea that OTP 1.5 does not have: **it is designed for one-to-many and many-to-many travel time
computation over a departure-time window, not for planning a single trip.**

Key architectural facts:

- **Network is built once, serialised to `network.dat`** (Kryo). Build inputs = one `.osm.pbf`
  + one or more GTFS `.zip` in a directory. Rebuilding is required when the R5 version changes
  (`NETWORK_FORMAT_VERSION` mismatch throws on load).
- **RAPTOR-family algorithm** (`FastRaptorWorker`), not Dijkstra/A\* over a time-expanded graph.
  This is why it is fast for one-to-many and why memory scales with `origins × network size`.
- **Departure-time window is native.** You give a departure time *and* a window (e.g. 07:00 +
  120 min); R5 routes for many departure minutes inside that window and returns **percentiles**
  of travel time. This is the single biggest difference from easy-OTP's "961 surfaces" approach:
  easy-OTP re-runs OTP once per minute; R5 does the equivalent internally in one pass.
- **No GTFS-RT.** R5 has no realtime feed ingestion at all. Anything realtime has to arrive as a
  *realized static GTFS* (exactly what easy-OTP's `BuildRealizedGtfs` / `family_a_reconstruction`
  produce — the P50/P85 feeds). This is a hard constraint on the Realtime section of Easy-R5.
- **Licence: MIT** (Conveyal LLC). Compatible with a GPL-3.0-or-later plugin.
- **Java 21** (`build.gradle`: `JavaLanguageVersion.of(21)`). Not Java 8, not Java 11.
- **Explicit "no stable API" warning** in R5's own README: third-party wrappers are expected to
  pin an R5 version and may break on upgrade. Both `r5r` and `r5py` pin. Easy-R5 must pin too.

Distribution: GitHub Releases carry a shaded fat jar. `r5-v7.6-all.jar` is **62 MB**, with
`.md5` and `.sha1` siblings (no `.sha256` — easy-OTP's `DownloadJre` verifies SHA-256, so either
switch to SHA-1 verification for this asset or hardcode a SHA-256 computed once and pinned).

```
https://github.com/conveyal/r5/releases/download/v7.6/r5-v7.6-all.jar
```

---

## 2. Entry points that actually exist in the jar

Grep of `v7.6` for `public static void main`:

| Class | What it is | Useful to us? |
|---|---|---|
| `com.conveyal.analysis.BackendMain` | Full Conveyal Analysis backend (needs MongoDB, object storage, auth, a worker cluster) | No — far too heavy |
| `com.conveyal.r5.point_to_point.PointToPointRouterServer` | Debug HTTP server: `--build <dir>`, `--graphs <dir>`, `--isochrones`; endpoints `/plan`, `/metadata`, `/reachedStops`, `/query`, `debug/*` | Partially — it is a *debug* tool, and it exposes **no travel-time-matrix / accessibility endpoint**, i.e. not the thing R5 is good at |
| `com.conveyal.gtfs.CropGTFS`, `ExtractGTFSMode` | GTFS utilities | Maybe, incidentally |
| `com.conveyal.osmlib.main.Converter`, `SpeedSetter` | OSM utilities | Maybe, incidentally |
| `com.conveyal.r5.shapefile.ShapefileMain` | Shapefile matcher for LTS/congestion scenarios | Later, for scenarios |

**Consequence:** there is no off-the-shelf CLI or server in R5 that does what Easy-R5 needs.
Any binding — r5r, r5py, or ours — has to call R5's Java classes directly. See
[`bindings-comparison.md`](bindings-comparison.md) and [ADR-0001](../adr/0001-r5-binding.md).

---

## 3. The Java API surface a binding actually uses

Extracted from `r5py`'s source (it is the cleanest existing map of "which R5 classes matter"):

**Building / loading a network** (`r5py/r5/transport_network.py`):

```java
com.conveyal.r5.transit.TransportNetwork          // the network object
com.conveyal.osmlib.OSM.openOrCreateFile(...)     // read the .osm.pbf
com.conveyal.r5.streets.StreetLayer               // street graph
com.conveyal.r5.transit.TransitLayer              // transit graph
com.conveyal.gtfs.GTFSFeed.writableTempFileFromGtfs(...)
com.conveyal.r5.transit.GtfsTransferLoader
com.conveyal.r5.transit.TransferFinder
com.conveyal.r5.kryo.KryoNetworkSerializer.read/write(File)   // network.dat
com.conveyal.r5.streets.StreetLayer.LINK_RADIUS_METERS        // snapping radius default
com.conveyal.r5.analyst.cluster.TransportNetworkConfig        // build-time config (JSON)
```

**Requesting travel times** (`r5py/r5/regional_task.py`, `travel_time_matrix.py`):

```java
com.conveyal.r5.analyst.cluster.RegionalTask      // the request object (extends AnalysisWorkerTask extends ProfileRequest)
com.conveyal.r5.analyst.FreeFormPointSet          // arbitrary origin/destination points, read from a binary stream
com.conveyal.r5.analyst.TravelTimeComputer(task, network).computeTravelTimes()
com.conveyal.r5.OneOriginResult                   // result for one origin: travel times per destination per percentile
com.conveyal.r5.api.util.LegMode                  // WALK, BICYCLE, CAR, BICYCLE_RENT, CAR_PARK
com.conveyal.r5.api.util.TransitModes             // TRAM, SUBWAY, RAIL, BUS, FERRY, ...
```

One `TravelTimeComputer` call = **one origin → all destinations**, so the "matrix" is a loop over
origins (r5py parallelises it with joblib; r5r batches it in Java). This is where all the runtime
goes and where cancellation/progress must hook in.

**Task types** (`AnalysisWorkerTask.Type`): `TRAVEL_TIME_SURFACE` (binary grid of travel times
from one origin, per percentile) and `REGIONAL_ANALYSIS` (cumulative-opportunity accessibility
values). `FreeFormPointSet` vs `WebMercatorGridPointSet` decides whether destinations are your
own points or a regular grid.

### Hard limits found in the source

- `AnalysisWorkerTask.MAX_PERCENTILES = 5`, percentiles in `1..99`, ascending. **Verified
  2026-09-02:** `validatePercentiles()` throws `IllegalArgumentException` on six values. Validate
  in Python before spawning Java.
- `AnalysisWorkerTask.recordTravelTimeHistograms` (boolean). **Verified:** with it enabled,
  `TravelTimeResult.getHistogram(target)` returns an `int[120]` — how many departure minutes
  produced each travel time. A 120-minute window really does route 120 times
  (`FastRaptorWorker`: "Performing 120 total iterations (1 per minute)"), so the full
  per-departure-minute distribution is retrievable, and easy-OTP's service-minutes metric is
  computable from it. See [`spike-r5-probe-2026-09-02.md`](spike-r5-probe-2026-09-02.md).
- **Native accessibility is not usable standalone.** `recordAccessibility = true` fails with
  `NullPointerException: task.destinationPointSetKeys is null` — R5 fetches opportunity grids
  through Conveyal's storage layer. Compute accessibility from the travel-time matrix instead;
  r5r does the same.
- `N_SINGLE_POINT_CUTOFFS = 121` — 0..120 min cutoffs for single-point analysis. Note the same
  120-minute horizon easy-OTP hits with OTP surfaces.

---

## 4. The r5py patch set (worth copying)

`r5py` does not ship vanilla R5 — it ships `r5py/r5` at tag `v7.6-r5py`, which is **one commit,
four files** ahead of `conveyal/r5` v7.6:

1. `KryoNetworkSerializer.read()` — two added `input.close()` calls on the error paths.
   Without them a failed `network.dat` load leaves the file handle open, and **on Windows the
   file then cannot be deleted or rebuilt**. Directly relevant to a QGIS-on-Windows plugin.
2. `TransitLayer.saveShapes` default flipped `false → true`, so route geometry survives into the
   network (needed for detailed-itinerary line geometry rather than straight stop-to-stop lines).
   The field's own comment says it can also be set from a `transportNetworkConfig` file — so
   **vanilla R5 + a build-config JSON should be equivalent** [verify], which would let Easy-R5
   use the official Conveyal jar instead of a fork.
3. Two CI/publishing changes, irrelevant to us.

So: vanilla R5 is ~fine; only issue 1 is a real functional patch, and it only bites on an error
path. Prefer the official Conveyal release; keep the r5py fork jar as a fallback if Windows file
locking turns out to hurt.

---

## 5. How isochrones are produced (nobody contours in Java)

Neither binding asks R5 for polygons:

- **r5r** has `isochrone()`, which internally computes travel times to a grid and contours them.
- **r5py** (`r5py/r5/isochrones.py`) builds a **hex grid of destinations** (`geohexgrid`), runs a
  travel-time matrix to it, then polygonises + simplifies in Python (`shapely`, `simplification`).
- **Conveyal Analysis** itself requests a `WebMercatorGridPointSet` and gets a travel-time grid
  back, then contours in the browser.

For Easy-R5 this is good news: **the polygon step belongs in QGIS**, where `gdal:contour`,
`native:pixelstopolygons`, and the existing easy-OTP raster/zonal code already live. The Java
side only has to return a travel-time grid or a per-point table.

Also note `tools/isochrones_lodz`'s finding, from the existing r5r work: `isochrone()`'s cost
scales with **origin count** (like OTP), not batched per departure time like
`travel_time_matrix()`. If Easy-R5 builds isochrones from a grid travel-time surface instead, that
cost profile changes — measure before assuming.

---

## 6. Memory and failure modes (from real runs in `easy-OTP/tools`)

These are lessons already paid for in the r5r pipeline; do not relearn them:

- **Always set `maxWalkTime`.** Left unbounded, R5 searches an unlimited walking radius for every
  access, egress and transfer. Capping it at the longest cutoff is provably lossless — a single
  walk leg longer than the whole trip budget cannot be part of a trip inside that budget.
  Measured on GZM (2026-08-29): **10.2× faster** (1.14 → 0.11 s/origin) with **0.0000%**
  difference in isochrone area. This is the single biggest performance lever in the engine.
- **A departure date with no active service degrades silently to walk-only.** R5 does not error
  when zero trips run on the requested date; it returns walking results for every origin and
  hour. This shipped to production for GZM (feed active only 2026-08-28, date hardcoded to
  2026-08-24) and stood until 2026-08-31. Validate the date by counting *trips active on that
  date*, and independently check afterwards that any transit was actually used.
- **Cost scales with network complexity, not origin count.** Warszawa with 668 origins cost
  2.4–3.4× more per origin than Gdańsk with 1389. Estimate from a sample of the real network;
  never extrapolate from another city's throughput.
- For scale: the same benchmark puts `easyotp:generateisochrones` at 3.0 s/origin-hour against
  0.05–0.17 s/origin-hour for r5r — 20–60×, and the reason this plugin exists.

- Heap must be set **before the JVM starts** (`options(java.parameters="-Xmx4G")` in R, `-Xmx` on
  the command line for us). In-process JVMs cannot resize it later — an argument for running R5
  as a subprocess.
- Warszawa at a 500 m origin grid OOM'd at 12 GB heap / 800-origin batches, and separately hit an
  isoband/contour bug at 21:00; the fix was dropping to a **1000 m grid (668 origins)**. Grid
  density is the main cost lever, and per-city overrides are unavoidable.
- GZM (metropolitan area, many feeds) is dramatically more expensive than a single city.
- Batching origins is the standard mitigation, and batch size is the knob CI tunes.
- Static and "realized" (RT-derived) GTFS reuse the same `trip_id`/`stop_id`, so **they cannot
  live in the same build directory** — one network directory per variant.

---

## 7. Sources

- <https://github.com/conveyal/r5> — engine, README ("no stable API" warning), `build.gradle`
  (Java 21), releases (`r5-v7.6-all.jar`), `AnalysisWorkerTask.java` (percentile limits).
- <https://github.com/r5py/r5py> — `src/r5py/r5/*.py` (Java API map), `util/classpath.py`
  (pinned jar URL/SHA-256), `pyproject.toml` (dependency list).
- <https://github.com/r5py/r5/compare/conveyal:v7.6...r5py:v7.6-r5py> — the four-file patch.
- <https://github.com/ipeaGIT/r5r> — `java-r5rcore/` (the R-facing Java wrapper), releases.
- `easy-OTP/tools/accessibility_cities/`, `accessibility_lodz/`, `isochrones_lodz/` — the
  operational experience above.
