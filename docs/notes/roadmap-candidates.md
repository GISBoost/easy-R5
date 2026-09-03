# Roadmap candidates for Easy-R5 v0.2+

**Status:** research note, not a commitment. Sits in `docs/notes/` next to
[`product-scope.md`](product-scope.md) and [`open-questions.md`](open-questions.md) because
that is where "what could this become" thinking lives here. When a candidate below is
chosen, it graduates into a proper PRD under `docs/prd/` — matching easy-OTP's
`PR_easy-OTP_roadmap.md` house style (9-subsection R-X blocks: goal, dependencies,
parameters, step-by-step, reference port, edge cases, error strings, acceptance, spikes).
This file only ranks the ideas and shows the evidence.

**Naming choice:** `roadmap-candidates.md` rather than `PR_easy-R5_v02.md` — this is a
candidate list with sourced justification, not a spec an agent can code from. The v0.2 PRD
is downstream of this.

---

## 1. Method note

Searched September 2026. Primary sources read in full or near-full: the `ipeaGIT/r5r`
issue tracker (#164, #171, #243, #245, #265, #273) and `news`/changelog; the `r5py/r5py`
open-issue list (#323, #386, #418, #434, #441, #502, #543) and the travel-time-matrix
user manual; `conveyal/r5` open issues (#971, #975, #977, #978, #990, #991, #994, #1001)
and the Conveyal User Manual (modification types, glossary, time-window); the
`ask.openrouteservice.org` forum (matrix size limit, QGIS plugin rate-limit threads); the
QGIS plugin repository listings and trackers for the transit/isochrone/matrix plugins
(TravelTime, ORS Tools, GTFS-GO / "GTFS 2 GIS", Transit Reachability Analyser, City
Transport Analyzer); the PyQGIS API reference for `QgsProcessingParameterDateTime`;
GitHub's REST API rate-limit docs and GitHub Pages limits docs; the MobilityData Canonical
GTFS Validator and a *Findings* survey of GTFS errors; and the local repo — the v0.1 PRD,
the R5 primer, the bindings comparison, `tools/` migration note, the `gtfs-dashboard`
PRD + `manifest.sample.json`, and easy-OTP's algorithm set and roadmap PRDs.

Confidence:
- **§2 Tier 1** — high. Each item is either already half-built in easy-OTP, already
  confirmed feasible by the R5 spike, or a direct fix to a production incident this
  project already suffered.
- **§2 Tier 2 / Tier 3** — medium. R5 exposes the primitive in every case (verified
  against the primer and Conveyal docs), but the runner surface grows and none has been
  run here.
- **§3 archival-GTFS downloader** — high on feasibility, medium on the external
  dependency lasting (one static file + one CI job on a personal repo).
- **§4 out of scope** — high. These break a stated hard constraint.

---

## 2. Prioritised feature candidates

### Tier 1 — v0.2 core (cheap, evidenced, low risk)

---

#### T1-A. Service-minutes / reliability metric ("minutes of service")

**What it is.** For a `TRANSIT+WALK` matrix, report not just the P50/P85 travel time but
*for how many of the 120 departure minutes each destination is reachable within T*. R5
routes every one of the 120 minutes in a 2 h window internally
([Conveyal manual, time-window](https://docs.conveyal.com/analysis/methodology)); the
per-minute distribution is retrievable as `int[120]` via
`recordTravelTimeHistograms=true` + `TravelTimeResult.getHistogram(target)` — **already
verified by the 2026-09-02 spike** ([`spike-r5-probe-2026-09-02.md`](spike-r5-probe-2026-09-02.md),
[`open-questions.md` #5](open-questions.md)). The metric is a Python reduction of that
array; nothing new in Java beyond flipping the flag and emitting the histogram.

**User pain / evidence.** A median travel time hides reliability, which is the thing
low-frequency-transit users actually feel. r5py had to change its *default* departure
window because users were unknowingly sampling a single minute and getting misleading
numbers — "the default value for `departure_time_window` in r5py is currently set for
1 hour, while the default value used in r5r is 1 minute … it is recommended to ensure
that `departure_time_window` is set significantly higher than these headway gaps"
([r5py #292](https://github.com/r5py/r5py/issues/292),
[r5py travel-time-matrix manual](https://r5py.readthedocs.io/stable/user-guide/user-manual/travel-time-matrices.html)).
r5r ships a whole vignette on the parameter
([r5r time_window article](https://ipeagit.github.io/r5r/articles/time_window.html)).
easy-OTP's *flagship* is a continuity/service-minutes method (the "961 surfaces"
classification) — Easy-R5's users are the same people and will expect an equivalent.

**How it fits.** R5 primitive: **yes, confirmed.** Post-processing: Python. Constraint
check: clean — this is exactly the "everything non-routing is Python" split. It is
already named as v0.2 scope in [PRD §9](../prd/PR_easy-R5_v01.md) and
[`r5-vs-otp.md`](r5-vs-otp.md), with the explicit caveat that it must **not** be called
by easy-OTP's name because it is not the same number
([primer §3](r5-engine-primer.md), [gotchas in CLAUDE.md](../../CLAUDE.md)).

**Rough effort.** **M.** The Java change is ~15 lines (flag + one more `RESULT`/CSV
column stream). The work is Python: a new `service_minutes.py` core module, a
`RunServiceMinutes` algorithm (or a mode switch on the matrix), the output field naming
that deliberately diverges from easy-OTP, and the UI copy explaining the difference.

**Dependencies / risks.** Doubles the histogram memory per origin (120 ints × targets) —
needs the same batching the matrix already has. Risk of users conflating it with
easy-OTP's metric: mitigated by naming and docs, called out in the PRD already.

**Prior art.** easy-OTP `count_from_surfaces.py` / `run_temporal_accessibility.py` do the
per-minute reduction from OTP surfaces. Conveyal Analysis surfaces the same idea as
"travel time reliability". r5r/r5py expose the raw percentiles but not a service-minutes
reduction.

---

#### T1-B. `CompareScenarios` — before/after delta layer

**What it is.** Take two accessibility (or matrix, or service-minutes) result layers —
same origins, different date / timetable / network — and emit one layer with the
per-origin difference, %-change, and a diverging style. No routing; a keyed join plus
arithmetic.

**User pain / evidence.** This is the *secondary persona's headline question* verbatim
from [`product-scope.md`](product-scope.md): "which district got worse after the timetable
change". It is listed as a v0.1 candidate in product-scope and
[`r5-vs-otp.md`](r5-vs-otp.md) ("the thing planners actually ask for") but did **not**
ship in the 8 v0.1 algorithms ([PRD §0](../prd/PR_easy-R5_v01.md)). The `tools/`
accessibility studies are all fundamentally comparisons (income vs access, P50 vs P85,
static vs realized — [`tools/accessibility_cities/README.md`](../../tools/accessibility_cities/README.md)).
easy-OTP already has `compare_temporal_accessibility.py`.

**How it fits.** No R5 at all. Pure PyQGIS: `QgsVectorLayer` join on the origin id,
field calculator, `apply_style` with a diverging QML. Constraint check: clean.

**Rough effort.** **S.** One algorithm, one style file, one core helper. Half a day. The
only design question is what to do when the two runs used different method parameters —
answer: refuse, and diff the `*.meta.json` sidecars that `RunAccessibility` already
writes ([handoff, M4](../handoffs/2026-09-03_M3-M5-implementation.md)).

**Dependencies / risks.** Needs both inputs to carry the method-metadata fields (they do,
[PRD §5.2](../prd/PR_easy-R5_v01.md)). Low risk.

**Prior art.** easy-OTP `compare_temporal_accessibility.py`; Conveyal Analysis's
"comparison" mode (two scenarios side by side with a difference layer).

---

#### T1-C. `CheckTransitData` — GTFS pre-flight diagnostic

**What it is.** A Diagnostics-group algorithm that reads a GTFS zip (stdlib `zipfile` +
`csv`, no engine) and reports, before anyone builds a network: calendar span and the
**trips-active-per-day histogram** over that span, feed timezone, route-type breakdown,
number of stops and their bounding box, whether that box overlaps a supplied OSM extract,
`shapes.txt` present or not, and any GTFS errors that would make R5 misbehave
(disconnected `trip_id`s, unknown extended route types, empty `calendar`).

**User pain / evidence.** This project's **single worst production incident** was a silent
degrade to walk-only because the hardcoded date had no active service — it "shipped to
production for GZM … and stood until 2026-08-31"
([primer §6](r5-engine-primer.md), [PRD §2.1](../prd/PR_easy-R5_v01.md)). v0.1 added two
guards *at analysis time*; a pre-flight check catches it at *data-prep time*, which is
where the user can still do something about it. GTFS feeds are pervasively broken —
MobilityData maintains a validator with **72 distinct error rules**
([gtfs-validator rules](https://gtfs-validator.mobilitydata.org/rules.html)), and a
*Findings* survey documents how common spec violations are in real US feeds
([A Survey of Errors in GTFS Static Feeds](https://findingspress.org/article/116694)).
R5 itself has open bugs where a single feed error corrupts routing — "when feed contains
critical errors all trips end up in one pattern"
([conveyal/r5 #978](https://github.com/conveyal/r5/issues/978)) and dropped extended
route types ([#1001](https://github.com/conveyal/r5/issues/1001)). r5py users hit
`GTFSFileError` on `transfers.txt` with no guidance
([r5py #502](https://github.com/r5py/r5py/issues/502)).

**How it fits.** No R5 — pure Python over the zip. The trips-per-day logic already exists
as `service_days` in the runner's `build` command
([PRD §3.2](../prd/PR_easy-R5_v01.md)); this exposes it *without* a network build and adds
the other checks. Constraint check: clean.

**Rough effort.** **S–M.** ~150 lines of Python + one algorithm. The `calendar.txt` ×
`calendar_dates.txt` trip-counting is the fiddly part and is already specified and
implemented for the runner.

**Dependencies / risks.** Must count *trips*, not `service_id` share — feeds like
Gdańsk/GZM have one `service_id` per day and the "share" heuristic gives false alarms
([PRD §5.3](../prd/PR_easy-R5_v01.md)). Already understood here.

**Prior art.** MobilityData Canonical GTFS Validator (Java, too heavy to bundle, but the
rule list is the reference); easy-OTP's feed-freshness checks in the RT world; Conveyal's
build-time feed warnings.

---

#### T1-D. Complete the `Setup/` group: `DownloadTransitData` + `DownloadRealizedGtfs`

**What it is.** Two Setup algorithms:
1. `DownloadTransitData` — OSM extract (Geofabrik) + scheduled GTFS (Mobility Database /
   Transitland) for a named area. A near-verbatim port of easy-OTP's R2.
2. `DownloadRealizedGtfs` — connect to the `gtfs-dashboard` manifest, pick city + day +
   variant (P50 / P85 / static), download the one asset. **Detailed in §3.**

**User pain / evidence.** "Finding the right OSM extract" and "finding and downloading
GTFS for the operators serving an area" are called out as real barriers in easy-OTP's
roadmap ("wymagają od użytkownika samodzielnego nawigowania na Geofabriku i w bazach
GTFS" — [`PR_easy-OTP_roadmap.md` §R2](../../../easy-OTP/docs/prd/PR_easy-OTP_roadmap.md)).
People use the Mobility Database / Transitland precisely because *finding* a feed is hard
([mobilitydatabase.org](https://mobilitydatabase.org/)). [`product-scope.md`](product-scope.md)
lists `DownloadTransitData` in the Setup group; [`open-questions.md` #14](open-questions.md)
already resolved "duplicate, don't cross-depend on easy-OTP". The realized-GTFS path is
the *only* way realtime information can enter Easy-R5 at all
([`CONTEXT.md`](../../CONTEXT.md), [`r5-vs-otp.md`](r5-vs-otp.md)) and there is a
ready-made index for it.

**How it fits.** No R5. All stdlib `urllib` + `json` + `zipfile`, exactly the pattern in
[`download_r5.py`](../../easy_r5/algorithms/download_r5.py) (`_download` with
progress/cancel, `_safe_zipextract`, QSettings). Constraint check: clean — binary
downloads at setup are explicitly allowed.

**Rough effort.** `DownloadTransitData` **M** (Geofabrik index traversal + a GTFS source
API); `DownloadRealizedGtfs` **S** (see §3 — ~60 new lines on top of existing plumbing).

**Dependencies / risks.** Transitland v2 needs a key for volume; the Mobility Database
has a stable catalog CSV/API. For the realized path: the manifest and its CI job must
keep running (§3). Realized (P50/P85) and static feeds share `trip_id`/`stop_id` and
**must not** land in the same build directory — one dir per variant
([primer §6](r5-engine-primer.md), [`CONTEXT.md`](../../CONTEXT.md)).

**Prior art.** easy-OTP `download_transit_data.py`, `download_jre.py`; the
`gtfs-dashboard` frontend already does exactly the manifest → city → day → asset
drill-down in vanilla JS ([`gtfs-dashboard/README.md`](../../../gtfs-dashboard/README.md)).

---

### Tier 2 — v0.3 (higher value, more runner surface)

---

#### T2-E. `RunScenarioAnalysis` — R5 network modifications

**What it is.** Apply an R5 `Scenario` (a list of modifications) at request time and route
against the modified network: add a trip pattern (a new line, from a QGIS line layer),
remove trips/stops, adjust speed or dwell time, reroute. Then diff against the baseline
(reuses T1-B). This is the item [`product-scope.md`](product-scope.md) and
[`r5-vs-otp.md`](r5-vs-otp.md) both flag as *the* long-term differentiator versus
easy-OTP, and [`CONTEXT.md`](../../CONTEXT.md) calls "R5's real differentiator over OTP".

**User pain / evidence.** "What if this tram line existed / this street were closed" is
the core planning question OTP 1.5 **cannot answer at all**
([`r5-vs-otp.md`](r5-vs-otp.md) capability table). It is the entire reason Conveyal
Analysis exists — R5 was "developed to power Conveyal's web-based interface for scenario
planning" ([conveyal/r5 README](https://github.com/conveyal/r5)). The modification
vocabulary is mature and documented: add-trip-pattern, adjust-speed, adjust-dwell-time,
remove-stops, remove-trips, reroute, plus a shapefile→modifications importer
([Conveyal manual, modification types](https://docs.conveyal.com/edit-scenario/modifications)).
easy-OTP's own roadmap explicitly punts car-dependency / scale problems "to the easy-r5
plugin" ([`PR_easy-OTP_roadmap.md`](../../../easy-OTP/docs/prd/PR_easy-OTP_roadmap.md)).

**How it fits.** R5 primitive: **first-class.** `Scenario` + `Modification` subclasses
are in the pinned jar. The runner already builds a (currently empty) `Scenario` object
for every matrix request ([PRD §3.2 recipe](../prd/PR_easy-R5_v01.md)) — this fills it in
from a job-spec block. Building the modification JSON from QGIS layers (line geometry →
stop sequence → `AddTripPattern`) is Python. Constraint check: mostly clean, but it
**grows the single-file runner**, which is the documented risk ceiling
([`bindings-comparison.md`](bindings-comparison.md), [PRD §8](../prd/PR_easy-R5_v01.md)).

**Rough effort.** **L.** Needs its own PRD (the PRD already says so, §9). The routing side
is small; the modeling side (turning a drawn line into a valid `AddTripPattern` with
stops, dwell times, a frequency or a timetable, and snapping to the street layer) is
where the work is. Shapefile matcher (`ShapefileMain`) is in the jar but is a debug tool
([primer §2](r5-engine-primer.md)).

**Dependencies / risks.** Runner size vs the one-file limit — if scenarios push it over,
the fallback is a separate MIT repo with a real jar, like `easy-GTFS-RT`
([PRD §8](../prd/PR_easy-R5_v01.md)). R5's "no stable API" warning bites hardest here
because `Modification` classes are less exercised by r5r/r5py than the matrix path.

**Prior art.** Conveyal Analysis (the reference implementation of the whole feature);
r5r has no scenario support; r5py has none. This would be a genuine
*first* for a desktop-GIS transit tool.

---

#### T2-F. Population-weighted accessibility + equity summary (one-click)

**What it is.** Chain `PopulationOverlay` → `RunAccessibility` → a summary: "X % of
residents / Y people reach ≥1 hospital within 30 min by transit at P85", plus a
distribution (deciles, a Lorenz curve / Gini, a histogram) and a short text report. Today
the user must run three algorithms and do the last step in a spreadsheet.

**User pain / evidence.** This *is* the primary-persona headline question, quoted in
[`product-scope.md`](product-scope.md): "how many residents reach a hospital within 30
minutes by transit". The whole `tools/accessibility_*` body of work is this computation
done by hand, and it was published as journalism
("[61% obszaru zamieszkanego przez studentów bez dostępu do uczelni w pół godziny](https://gisboost.github.io/analizy/dostepnosc-uczelnie/)"
— [`tools/accessibility_cities/README.md`](../../tools/accessibility_cities/README.md)).
[`product-scope.md`](product-scope.md) demands "an answer … as a styled layer" and "the
method recorded in the output" — a summary report is the missing last mile.

**How it fits.** No R5 — it orchestrates existing algorithms + arithmetic + a report
writer. `PreparePopulationLayer` / `PopulationOverlay` already ship. Constraint check:
clean.

**Rough effort.** **S–M.** Mostly glue and a report template (HTML/CSV — no new deps;
the openpyxl exception already covers XLSX if wanted). The design question is how much
of a "model" (Processing model / graphical modeler export) versus a coded algorithm.

**Dependencies / risks.** Needs a population layer on the same origins as the
accessibility run — document the recipe (it is the same hex grid). Low risk.

**Prior art.** Conveyal Analysis reports "regional analysis" percentiles against an
opportunity dataset directly; the Accessibility Toolbox for ArcGIS bundles the
population-weighting step; easy-OTP stops at the per-hex number.

---

#### T2-G. Competitive accessibility (2SFCA / gravity with a demand side)

**What it is.** Cumulative-opportunity accessibility ignores that opportunities are
*consumed* — a hospital reachable by 200 k people is not as accessible as the raw count
says. Add a two-step-floating-catchment-area (or gravity) mode: step 1 computes a
supply-to-demand ratio at each destination from the reverse matrix + a population layer,
step 2 sums those ratios back to origins with the decay function.

**User pain / evidence.** 2SFCA and its variants are the standard method in the
health/education accessibility literature — "a special case of a gravity model … developed
to measure spatial accessibility to primary care physicians", "intuitive to interpret and
easy to implement in a GIS environment"
([2SFCA method, Wikipedia](https://en.wikipedia.org/wiki/Two-step_floating_catchment_area_method);
[Spatial accessibility of primary health care utilising 2SFCA](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3520708/)).
The secondary persona ([`product-scope.md`](product-scope.md)) needs "a defensible,
reproducible accessibility indicator for a thesis" — cumulative opportunity is the weakest
of the common indicators and reviewers know it.

**How it fits.** No R5 beyond a second (transposed) matrix, which the engine already
produces. All post-processing: Python over the matrix + the population layer. Constraint
check: clean. Reuses `PopulationOverlay`.

**Rough effort.** **M.** The math is short and well-documented; the work is a clean
parameter design (catchment cutoff, decay, whether to use enhanced/3SFCA variants) and
not over-scoping it.

**Dependencies / risks.** Needs a demand (population) layer and a supply-capacity field
on destinations. Risk of scope creep into "every 2SFCA variant ever published" — pick one
(Wang's enhanced 2SFCA) and stop.

**Prior art.** Accessibility Toolbox for R/ArcGIS; `access` (Python) and `SpatialAcc`
(R); no QGIS-native transit implementation exists — ORS Tools and QNEAT3 stop at
matrices.

---

#### T2-H. Native travel-time raster surface (better isochrones, `TRAVEL_TIME_SURFACE`)

**What it is.** For a single origin, ask R5 for its native `TRAVEL_TIME_SURFACE` task —
a `WebMercatorGridPointSet` travel-time grid, per percentile — instead of building a
FreeForm destination grid ourselves and interpolating. Output the raster directly (useful
on its own for QGIS raster analysis) and contour it as now.

**User pain / evidence.** [`KNOWN_ISSUES.md` #2 / issue #2](../../KNOWN_ISSUES.md):
isochrone detail is bounded by `GRID_SPACING`, and a coarse grid gives lumpy contours;
the resolution knob has quadratic cost. R5's grid surface is the mechanism Conveyal
Analysis itself uses ("requests a `WebMercatorGridPointSet` and gets a travel-time grid
back, then contours in the browser" — [primer §5](r5-engine-primer.md)) and it is
resolution-controlled by a zoom level, not an O(n²) point count.

**How it fits.** R5 primitive: **yes** — `AnalysisWorkerTask.Type.TRAVEL_TIME_SURFACE` is
in the jar ([primer §3](r5-engine-primer.md)). It is a different result type in the
runner (binary grid, not a per-point CSV), so a real chunk of new Java — but still purely
routing output. Contouring stays in QGIS. Constraint check: clean.

**Rough effort.** **M.** New runner result path + grid decoding in Python. The contour
code from v0.1 is reused unchanged.

**Dependencies / risks.** The grid is Web Mercator; reprojection to the working CRS is
one more transform (the isochrone algorithm already derives a metric UTM CRS —
[handoff, CRS](../handoffs/2026-09-03_M3-M5-implementation.md)). Grid decode format needs
verifying against 7.6.

**Prior art.** Conveyal Analysis (native); r5r `isochrone()` builds a grid then contours
in R; r5py builds a hex grid then polygonises in Python — nobody contours in Java, which
is why the QGIS split is right ([primer §5](r5-engine-primer.md)).

---

### Tier 3 — later / niche

---

#### T3-I. Elevation-weighted walking and cycling

**What it is.** Feed a DEM raster into the network build so R5 weights street edges by
slope (Tobler's hiking function for walk, a slope factor for bike). A `DEM` parameter on
`BuildNetwork`; the runner passes it through `TransportNetworkConfig`.

**User pain / evidence.** R5 gained native elevation weighting in v6.7, and r5r's response
was to *delete its own* slope pre-processing and use R5's — "R5 started considering
elevation data as of v6.7. We can remove our elevation calculations from r5r"
([r5r #243](https://github.com/ipeaGIT/r5r/issues/243),
[r5r #171](https://github.com/ipeaGIT/r5r/issues/171),
[r5r #164](https://github.com/ipeaGIT/r5r/issues/164)). conveyal/r5 has an open bug that
elevation cost is not applied to transfers
([#991](https://github.com/conveyal/r5/issues/991)) — so it is real and in use. Matters
for hilly cities and for any serious cycling-accessibility work.

**How it fits.** R5 primitive: **native since 6.7**, and 7.6 is pinned. It is a
build-config setting ([primer §3](r5-engine-primer.md): `TransportNetworkConfig`), so the
change is to `BuildNetwork` + the runner's `build` command + the cache key (DEM hash).
Constraint check: clean.

**Rough effort.** **M.** Small runner change; the work is DEM handling (CRS, resolution,
nodata) and cache invalidation.

**Dependencies / risks.** Bigger networks; another cache-key input. `saveShapes` / build
config JSON path needs verifying against vanilla 7.6
([`open-questions.md` #7](open-questions.md)).

---

#### T3-J. Fare-aware / monetary-cost accessibility

**What it is.** "How many jobs can I reach within 45 min **and** €4.00" — R5 can bound
routing by a fare budget using a configurable transfer-based fare calculator.

**User pain / evidence.** r5r shipped exactly this: "leverages R5's capability of
considering monetary costs … demonstrated through Porto Alegre examples showing how
accessibility differs dramatically between unlimited spending and a R$ 5.00 transport
budget" ([r5r #245](https://github.com/ipeaGIT/r5r/issues/245),
[r5r fare_structure article](https://ipeagit.github.io/r5r/articles/fare_structure.html)).
Equity analysis is a natural fit for the researcher persona.

**How it fits.** R5 primitive: **yes** (`InRoutingFareCalculator`), but it is
transfer-based only — no zone or distance fares — and needs a hand-written fare-config
JSON per city. Constraint check: clean but heavy.

**Rough effort.** **L.** The fare config is the hard part (r5r spent a release on it and
still can't do zonal systems). Low priority until a user actually asks.

---

#### T3-K. Temporal isochrones / isochrone-over-time

**What it is.** One origin, many departure times (e.g. 06:00–10:00 every 30 min) → a
stack of isochrones showing how reach shrinks off-peak. easy-OTP has
`generate_isochrones_over_time.py`.

**User pain / evidence.** Off-peak collapse is a standard planning concern; easy-OTP built
a dedicated algorithm for it ([easy-OTP `PR_easy-OTP_v06.md` N-2](../../../easy-OTP/docs/prd/PR_easy-OTP_v06.md)).
Lower urgency than the reliability metric (T1-A), which answers a similar question in one
run.

**How it fits.** Loop the existing isochrone algorithm over departure times; all Python.
**S–M.** Partly subsumed by T1-A.

---

## 3. The archival-GTFS downloader — feasibility verdict

### Verdict: **feasible and small.** Ship it in v0.2 as `DownloadRealizedGtfs`.

It is ~90 % existing plumbing. The real work is ~60 lines: fetch one static JSON, populate
two dropdowns, download one file to the right directory. The single genuine dependency is
external and outside this repo's control (below).

### Primary-source facts backing it

**GitHub Pages static file vs the REST API rate limit.** GitHub's REST API allows
**60 requests/hour unauthenticated, 5 000/hour authenticated**, and "some endpoints, like
the search endpoints, have more restrictive limits"
([GitHub REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)).
`manifest.json` is **not** served from `api.github.com` — it is a plain file on
`gisboost.github.io`, served through Fastly's CDN, the same path as `raw.githubusercontent.com`
and github.com's own assets ([Fastly / GitHub case study](https://www.fastly.com/customers/github)).
GitHub Pages has a **soft 100 GB/month bandwidth** limit and may return HTTP 429 only
under sustained abusive request rates
([GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits);
[community discussion 153352](https://github.com/orgs/community/discussions/153352)). One
`GET manifest.json` per plugin invocation (a few KB) is nowhere near any of these — it is
**effectively unlimited**. By contrast, hitting the Releases *API*
(`api.github.com/repos/GISBoost/easy-GTFS-RT/releases`) to discover assets would be
capped at 60/hour and would need tag-pattern matching.

**The manifest already carries direct asset URLs — no API call needed.** Confirmed from
[`gtfs-dashboard/manifest.sample.json`](../../../gtfs-dashboard/manifest.sample.json): each
`cities.<key>.days[]` entry has `date`, `status` (`ok` / `partial`), and an `assets`
object with **fully-qualified** `https://github.com/GISBoost/easy-GTFS-RT/releases/download/<tag>/<file>`
URLs for `p50`, `p85`, `static_gtfs` (plus `diff_chart`, `diff_summary`, `tidy_table`,
any of which may be `null`). So the plugin needs exactly: `GET manifest.json` → build a
city dropdown from `display_name` and a day dropdown from `days[].date` → `GET` the one
URL under `assets`. Release-asset downloads are also CDN-served, not REST-API-limited.

**QGIS 3.22 date parameter.** `QgsProcessingParameterDateTime` exists **since QGIS 3.14**
and is present in 3.22 (verified against the 3.22.4-Białowieża API reference); it supports
`Date`, `DateTime`, and `Time` types
([PyQGIS `QgsProcessingParameterDateTime`](https://api.qgis.org/api/3.22/classQgsProcessingParameterDateTime.html)).
So a native date picker *is* available — worth adopting for `RunTravelTimeMatrix`'s `DATE`
parameter (today a plain `String`, [PRD §4.4](../prd/PR_easy-R5_v01.md)). **But for this
downloader an `Enum` is still the right control**, because only the specific days present
in the manifest exist as downloads — a free date field would invite 404s. Populate the day
`Enum` from `days[].date`, annotated with `status`.

**The manifest schema and its refresh job.** The manifest is regenerated **from scratch**
daily (`cron: 0 8 * * *` + `workflow_dispatch`) by `gtfs-dashboard`'s
`refresh-manifest.yml`, reading `easy-GTFS-RT`'s public Releases API
([`gtfs-dashboard/README.md`](../../../gtfs-dashboard/README.md),
[`gtfs-dashboard/PRD.md` §4](../../../gtfs-dashboard/PRD.md)). Top-level shape:
`{ generated_at, source_repo, cities: { <key>: { display_name, days: [ { date, release_tag,
release_url, created_at, status, assets: {...}, delay_stats } ] } } }`.

### The elegant shape (sketch, not a spec)

Clone [`easy_r5/algorithms/download_r5.py`](../../easy_r5/algorithms/download_r5.py) — it
already has `_download` (chunked, progress, cancel, `.tmp` rename), `_check_writable`,
`_check_disk`, `_safe_zipextract`, and the `settings` / QSettings pattern. New code:

1. `processAlgorithm` step 0: `GET https://gisboost.github.io/gtfs-dashboard/manifest.json`
   with the existing `urllib` + `User-Agent` helper. On 404 / network error, fail with a
   message pointing at `github.com/GISBoost/easy-GTFS-RT/releases` — same graceful
   degradation the dashboard frontend does.
2. Parameters: `CITY` (Enum, from `display_name`), `DAY` (Enum, from `days[].date` +
   `status`), `VARIANT` (Enum: `p50` / `p85` / `static_gtfs`), `TARGET_FOLDER` (Folder,
   default from QSettings).
3. Resolve the one URL: `manifest["cities"][key]["days"][i]["assets"][variant]`. If `null`,
   fail cleanly ("no P85 build for Łódź 2026-07-13").
4. Download + unzip into a **variant-segregated** directory —
   `<target>/transit/<city>/<date>/<variant>/` — because realized (`p50`/`p85`) and
   `static_gtfs` share `trip_id`/`stop_id` and cannot coexist in one network-build dir
   ([primer §6](r5-engine-primer.md), [`CONTEXT.md`](../../CONTEXT.md)). Save the path to
   QSettings; it feeds straight into `BuildNetwork`'s `GTFS_FOLDER`.
5. No SHA verification is possible — the manifest carries no hashes. Mitigate with a
   Content-Length check and unzip-integrity check (`ZipFile.testzip()`). Note this as a
   known gap versus `DownloadR5` (which pins a SHA-256).

**The one real dependency:** the manifest must keep existing at a stable URL with a stable
schema, which means (a) the `gtfs-dashboard` repo and its daily CI job keep running, and
(b) someone keeps publishing realized feeds via the `easy-GTFS-RT` pipeline. Both are
personal-infrastructure, single-maintainer. The plugin must treat a missing/garbled
manifest as a routine error, not a crash, and the docs must say "this indexes GISBoost's
recordings, which cover ~12 cities on specific days — it is not a general GTFS source"
(that is `DownloadTransitData`'s job).

---

## 4. Explicitly out of scope

| Idea that surfaced | Why it is out |
|---|---|
| **Any live GTFS-RT ingestion in R5** (a "realtime accessibility" algorithm reading a TripUpdates feed) | R5 has no GTFS-RT support at all — a hard engine fact ([primer §1](r5-engine-primer.md), [`r5-vs-otp.md`](r5-vs-otp.md)). Realtime enters Easy-R5 *only* as a realized static feed (P50/P85), which is T1-D / §3. |
| **Real-time / single-trip journey planning** ("plan me a trip now") | OTP's `/plan` is better at this; [`r5-vs-otp.md`](r5-vs-otp.md) says do not port it. R5's `detailed_itineraries` is "the weaker path" — r5py's own trackers confirm it ([r5py #386](https://github.com/r5py/r5py/issues/386), [#418](https://github.com/r5py/r5py/issues/418), [#441](https://github.com/r5py/r5py/issues/441)). A minimal `itinerary` runner command stays a *possibility* (bindings-comparison §D-3) but never a flagship. |
| **r5r / r5py as a plugin dependency** (to get fares, elevation, isochrones "for free") | r5r needs R; r5py needs ~16 pip packages including compiled wheels — both rejected in [`bindings-comparison.md`](bindings-comparison.md) and [`CLAUDE.md`](../../CLAUDE.md). Their *source* stays the reference for how to call R5; their *code* never ships. |
| **Bundling the MobilityData GTFS Validator** for T1-C | It is a full Java app with its own release cadence. T1-C reimplements only the handful of checks that matter to R5, in Python. |
| **Conveyal Analysis backend / a bundled routing server** | Needs MongoDB, object storage, auth, a worker cluster ([primer §2](r5-engine-primer.md)). Explicit v0.1 non-goal ([PRD §9](../prd/PR_easy-R5_v01.md)); nothing changes that. |
| **Native R5 accessibility** (`recordAccessibility=true`) | Fails standalone with `destinationPointSetKeys is null` — only works inside Conveyal's storage layer ([primer §3](r5-engine-primer.md), [`open-questions.md`](open-questions.md)). Accessibility stays a Python computation over the matrix. |
| **Own hex-grid generator** | `native:creategrid` already does it; documented as a recipe, not an algorithm ([PRD §4.7](../prd/PR_easy-R5_v01.md)). |
| **GTFS-Flex / demand-responsive transit** | R5 has no GTFS-Flex support; not on Conveyal's roadmap for the pinned line. Revisit only if the pinned R5 version moves and adds it. |
| **Generalising the `openpyxl` bootstrap to other packages** | The one narrow exception is `openpyxl` for `PreparePopulationLayer` only ([`CLAUDE.md`](../../CLAUDE.md)). No report writer, chart library, or 2SFCA helper may add a second. |

---

## 5. Sources

### Local (this repo and siblings)
- `docs/prd/PR_easy-R5_v01.md` — v0.1 PRD; §0 status, §9 deferred scope, §2.1 the three production lessons.
- `docs/notes/r5-engine-primer.md` — R5 class map, hard limits, memory/failure modes.
- `docs/notes/r5-vs-otp.md` — capability map; what not to port.
- `docs/notes/product-scope.md` — target users and the candidate algorithm list.
- `docs/notes/open-questions.md` — spike answers (#5 histograms, #7 vanilla-vs-fork, #14 duplicate download).
- `docs/notes/bindings-comparison.md` — why not r5r / r5py / JPype.
- `docs/notes/spike-r5-probe-2026-09-02.md` — the measured R5 facts.
- `docs/notes/tools-migration.md` — the dogfooding path: port `run_accessibility.R` onto the runner.
- `docs/handoffs/2026-09-03_M3-M5-implementation.md` — what shipped in v0.1, CRS handling, i18n.
- `KNOWN_ISSUES.md` — issue #2 (isochrone resolution).
- `easy_r5/algorithms/download_r5.py` — the download/verify/extract pattern to clone.
- `../easy-OTP/docs/prd/PR_easy-OTP_roadmap.md` — R2/R3 (DownloadTransitData / DownloadJre) specs and house style.
- `../easy-OTP/docs/prd/PR_easy-OTP_v06.md` — N-1..N-6 algorithm specs (isochrones-over-time, service coverage, OD matrix).
- `../easy-OTP/easy_otp/algorithms/` — `compare_temporal_accessibility.py`, `generate_isochrones_over_time.py`, `download_transit_data.py`.
- `../gtfs-dashboard/README.md`, `PRD.md`, `manifest.sample.json` — manifest schema, refresh CI, hosting.
- `../gtfs-dashboard` published site: <https://gisboost.github.io/gtfs-dashboard/>

### r5r (ipeaGIT)
- <https://github.com/ipeaGIT/r5r/issues/245> — fare calculator feature.
- <https://github.com/ipeaGIT/r5r/issues/243> — use R5 native elevation weighting.
- <https://github.com/ipeaGIT/r5r/issues/171> — temporary elevation solution (DEM raster).
- <https://github.com/ipeaGIT/r5r/issues/164> — isochrones and topography.
- <https://ipeagit.github.io/r5r/articles/time_window.html> — the departure-window vignette.
- <https://ipeagit.github.io/r5r/articles/fare_structure.html> — monetary cost routing.
- <https://ipeagit.github.io/r5r/news/index.html> — changelog.

### r5py
- <https://github.com/r5py/r5py/issues/292> — default `departure_time_window` (the sampling footgun).
- <https://github.com/r5py/r5py/issues/386> — R5 detailed-itinerary limitations, be explicit in docs.
- <https://github.com/r5py/r5py/issues/418> — restricted number of returned itineraries.
- <https://github.com/r5py/r5py/issues/441> — capture suboptimal paths.
- <https://github.com/r5py/r5py/issues/502> — `GTFSFileError` on `transfers.txt`.
- <https://github.com/r5py/r5py/issues/543> — travel-time breakdown (access/wait/in-vehicle/egress).
- <https://github.com/r5py/r5py/issues/323> — separate docs on accessibility measures.
- <https://r5py.readthedocs.io/stable/user-guide/user-manual/travel-time-matrices.html> — window guidance.

### Conveyal R5 + Analysis
- <https://github.com/conveyal/r5> — README (scenario-planning purpose, no stable API).
- <https://github.com/conveyal/r5/issues/978> — feed critical errors collapse trips into one pattern.
- <https://github.com/conveyal/r5/issues/1001> — unhandled extended route types.
- <https://github.com/conveyal/r5/issues/991> — elevation cost not used for transfers.
- <https://docs.conveyal.com/edit-scenario/modifications> — modification types (add trip pattern, adjust speed/dwell, reroute, remove).
- <https://docs.conveyal.com/analysis/methodology> — departure-window methodology.

### OpenTripPlanner / OpenRouteService (comparison pain)
- <https://docs.opentripplanner.org/en/latest/Analysis/> — OTP2 dropped batch analytics, points users at R5.
- <https://ask.openrouteservice.org/t/matrix-api-3500-route-limit/5331> — the 3 500-cell matrix ceiling.
- <https://ask.openrouteservice.org/t/qgis-ors-plugin-rate-limit-exceeded/1903> — ORS Tools QGIS 429s, no throttling.
- <https://ask.openrouteservice.org/t/overquerylimit-error-isochrones-in-qgis/439> — isochrone rate-limit in QGIS.

### QGIS plugins (state of the art)
- <https://plugins.qgis.org/plugins/travel_time_platform_plugin/> — TravelTime (API-based, paid).
- <https://plugins.qgis.org/plugins/ORStools/> — ORS Tools (API-based, rate-limited).
- <https://plugins.qgis.org/plugins/qgis_gtfs_plugin/> — GTFS 2 GIS (visualisation + network isochrones, no departure-window routing).
- <https://plugins.qgis.org/plugins/transit_reachability_analyser/> — Transit Reachability Analyser (OTP-backed, one origin → stops).
- <https://api.qgis.org/api/3.22/classQgsProcessingParameterDateTime.html> — date parameter, since 3.14.

### GTFS ecosystem
- <https://gtfs-validator.mobilitydata.org/rules.html> — 72 GTFS error rules.
- <https://github.com/MobilityData/gtfs-validator> — Canonical GTFS Schedule Validator.
- <https://findingspress.org/article/116694> — *A Survey of Errors in GTFS Static Feeds from the United States*.
- <https://mobilitydatabase.org/> — the feed catalog people use to find feeds.

### GitHub infrastructure (for §3)
- <https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api> — 60/h unauth, 5 000/h auth, search stricter.
- <https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits> — 100 GB/month soft bandwidth, 429 on abuse.
- <https://github.com/orgs/community/discussions/153352> — Pages rate-limiting behaviour in practice.
- <https://www.fastly.com/customers/github> — Fastly serves Pages / raw / github.com assets.

### Accessibility method (for T2-G)
- <https://en.wikipedia.org/wiki/Two-step_floating_catchment_area_method> — 2SFCA definition and GIS fit.
- <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3520708/> — 2SFCA for primary health care, method assessment.
- <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4661662/> — enhanced variable 2SFCA.
