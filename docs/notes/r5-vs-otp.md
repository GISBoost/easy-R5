# R5 vs OTP 1.5 — what changes, and what Easy-R5 should therefore be

Easy-R5 is not "easy-OTP with a different engine flag". The two engines are good at different
things, and copying easy-OTP's algorithm list one-for-one would produce a worse plugin than
either. This note is the capability map the roadmap should be built from.

## Engine differences that matter

| | OTP 1.5 (easy-OTP) | R5 (Easy-R5) |
|---|---|---|
| Deployment | long-lived HTTP server, graph built separately | no server; one process per job, `network.dat` built separately |
| Java | 8 | 21 |
| Core strength | one trip at a time, rich itineraries, `/isochrone` and `/surface` per request | one-to-many / many-to-many travel times over a **departure-time window** |
| Departure-time variability | you re-run once per minute (easy-OTP's 961 surfaces) | native: window + percentiles in one pass |
| Many-to-many cost | N × M separate requests | one pass per origin |
| GTFS-RT | supported (`stop-time-updater`, live delays) | **not supported at all** |
| Detailed itineraries | `/plan`, well-developed | `detailed_itineraries` exists but is the weaker path |
| Frequency-based routes | approximated | Monte Carlo draws, first-class |
| Scenarios (modify the network) | not really | first-class (`Scenario`, LTS/congestion modifiers, shapefile matcher) |
| Memory profile | graph in server, requests cheap | RAM ≈ origins × network complexity; OOM is the normal failure |

## Consequences for the algorithm roadmap

**Where R5 wins outright — these should be Easy-R5's headline algorithms**

- **Travel-time matrix** (N×M) — easy-OTP's `RunTravelTimeMatrix` is one HTTP request per pair;
  R5 does the same job orders of magnitude faster, and adds percentiles over a departure window
  for free. This is the flagship.
- **Cumulative-opportunity accessibility** — "how many jobs/schools/universities within 30 min",
  with cutoffs and decay functions. easy-OTP has no real equivalent (`RunServiceCoverage` is the
  closest); every `tools/` r5r script does exactly this.
- **Time-window robustness** — P50 vs P85 travel time from one run instead of two pipelines. The
  Łódź study built P50/P85 *feeds* to get at this; R5 gives the distribution directly for the
  scheduled case.
- **Scenarios** — "what if this line existed / this street were closed". R5 is built for it;
  easy-OTP cannot do it at all. Strong differentiator, later milestone.

**Where a port makes sense but the semantics change**

- **Isochrones** — R5 gives a travel-time grid; QGIS contours it (see primer §5). Cheaper and
  smoother than easy-OTP's per-point OTP calls, but the polygons will not be identical to OTP's,
  and comparisons across the two plugins must say so.
- **Service-time / continuity classification** (easy-OTP's flagship 961-surface method) — R5 can
  in principle produce the same "for how many departure minutes is this cell within T?" metric
  much faster, but **only if** the per-departure distribution is reachable
  (`recordTravelTimeHistograms`, or ≤5 percentiles, see primer §3). **Verify before promising
  this.** If it is not reachable, the honest R5 metric is a percentile-based one, and it should be
  named differently rather than pretending to be the same number.
- **Hex grid, population overlay, student layer, XLSX reports** — engine-independent; port the
  code from easy-OTP largely unchanged, or (better) keep them in easy-OTP and tell users to run
  both plugins. Decide once; do not maintain two divergent copies of the same algorithm.

**Where easy-OTP stays the right tool — do not port**

- Anything **GTFS-RT live** (`RunRealtimeAccessibility`, `RecordGtfsRt`, `BuildRealizedGtfs`).
  R5 has no realtime ingestion. Easy-R5's relationship to realtime is strictly *consumption* of
  realized static feeds (P50/P85) that easy-OTP or `family_a_reconstruction` produced — which is
  precisely what the migrated `tools/` pipelines already do.
- **Trip planning / routing with detailed legs** (`RouteViaPoints`, `RunOriginDestinationTimes`
  with leg breakdowns) — OTP's `/plan` is better at this than R5.

## The two-plugin story

The honest positioning, which the README should state plainly:

> **easy-OTP** — what actually ran, minute by minute, including realtime.
> **Easy-R5** — how a network performs across a time window, at scale, and under scenarios.

They share data formats (OSM extract, GTFS, hex grids, realized feeds) deliberately, so a user can
build a realized P50 feed in easy-OTP and analyse it in Easy-R5 on the same grid.
