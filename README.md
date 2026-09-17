# Easy-R5

A QGIS processing plugin for transit accessibility analysis on the
[**Conveyal R5**](https://github.com/conveyal/r5) routing engine — travel-time matrices,
cumulative-opportunity accessibility and isochrones over a departure-time window, computed inside
QGIS with no R, no conda and no Docker.

> **Status: 0.3.0, experimental.** All fifteen algorithms work; the travel-time matrix and
> accessibility are verified end-to-end (accessibility reproduces r5r's Gdańsk output
> *exactly* — [`docs/notes/validation-gdansk.md`](docs/notes/validation-gdansk.md)).
> New in 0.3.0, each verified on a real Łódź network: **network scenarios** (draw a new line,
> remove or re-time routes — R5 applies them in memory) with **Compare scenarios**, a **GTFS
> pre-flight check**, **2SFCA competitive accessibility** and a **population-weighted equity
> summary** — see [`docs/prd/PR_easy-R5_v03.md`](docs/prd/PR_easy-R5_v03.md).
> The flag stays `experimental` until a clean-install run of the full pipeline is signed
> off. See [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).

Sibling project: [**easy-OTP**](https://github.com/GISBoost/easy-OTP), the same idea on
OpenTripPlanner 1.5.

**How it works:** [*How QGIS talks to R5*](https://gisboost.github.io/easy-R5/) — Easy-R5 runs
the R5 jar as a child process through one small Java file, not through r5r (needs R) or r5py
(16 pip packages).

![Lost opportunities — delays vs. accessibility in Łódź](tools/realtime_delay_lodz/out/boards/hero.jpg)

**Current flagship result:** [`tools/realtime_delay_lodz/`](tools/realtime_delay_lodz/README.md) —
accessibility computed on Łódź's *static* GTFS schedule compared against the *realized P50*
schedule (the median of what vehicles actually did), same day, same network otherwise. The
board above shows the net change in reachable schools, pharmacies, universities and shopping
malls within a 30-minute trip once those real-world delays are applied — red hexagons lose
access, blue gain it. The two zoomed insets contrast the dense city centre, where overlapping
routes absorb a late vehicle, against a ring roughly 2 km further out, where access depends on
one specific transfer — miss it, and the wait is a full headway, not a few extra seconds.

| | easy-OTP | Easy-R5 |
|---|---|---|
| Engine | OpenTripPlanner 1.5 (Java 8) | Conveyal R5 (Java 21) |
| Best at | per-minute travel-time surfaces, detailed itineraries, **live GTFS-RT** | one-to-many / many-to-many travel times over a **departure-time window**, cumulative accessibility |
| Realtime | yes — records GTFS-RT and reconstructs realized feeds | no — R5 cannot read GTFS-RT; it consumes the realized static feeds easy-OTP produces |

The two are designed to share data: the same OSM extracts, GTFS feeds and hex grids work in
both.

---

## What it does

Processing toolbox → **Easy-R5**:

| Group | Algorithm | Does |
|---|---|---|
| Setup | **Download R5 engine and Java 21** | fetches Temurin 21 + `r5-v7.6-all.jar` (SHA-256 pinned), compiles the runner. No admin rights. |
| Setup | **Download realized GTFS** | pick a city + date + variant (realized P50/P85 or scheduled), download from GISBoost's gtfs-dashboard index into a folder ready for Build R5 network. |
| Setup | **Build R5 network** | one `.osm.pbf` + a folder of GTFS `.zip` → cached `network.dat` + a `network.json` summary with a per-date active-trip count. |
| Diagnostics | **Test R5 setup** | checks the JDK, jar and runner independently. |
| Diagnostics | **Check transit data (GTFS)** | before building: calendar span and active trips per day, whether your `DATE` has service, route types R5 cannot read, broken references between files, stops outside the study area, a realized feed sharing a folder with its static feed. HTML report + routes CSV (the names to use in *Build scenario*). |
| Analysis | **Run travel time matrix** | N origins × M destinations, percentiles over a departure window, batched processes, sampled time estimate, hard dead-date gate + post-run walk-only detector. Long CSV out. `TRANSIT_SUBMODES` narrows which transit modes R5 routes over (e.g. `TRAM` only, or `TRAM, BUS`) — blank means all. |
| Analysis | **Run accessibility** | opportunities reachable per origin / cutoff / percentile (STEP / LOGISTIC / EXPONENTIAL decay), summed in Python from the matrix. Long CSV + an ORIGINS copy with `acc_<opp>_p<pct>_c<cutoff>` fields. Same `TRANSIT_SUBMODES` narrowing as the matrix — run once for `TRAM` and once for `BUS` to compare modal accessibility. |
| Analysis | **Run service minutes** | for each origin-destination pair, how many of the departure window's minutes (120 by default) reach the destination within each cutoff — from R5's per-minute travel-time histogram, reduced in Java. Long CSV (`svc_min_c<cutoff>` per cutoff, values 0-120). **Not** the same number as easy-OTP's service-time classification (`otp_mean`/`st_class`) — different mechanism, different reference window; see [`docs/prd/PR_easy-R5_v02_service-minutes.md`](docs/prd/PR_easy-R5_v02_service-minutes.md). |
| Analysis | **Run competitive accessibility (2SFCA)** | two-step floating catchment area: capacity (doctors, school places) shared by the population that can reach it within a catchment — e.g. doctors per 1000 residents. STEP = classic 2SFCA, LOGISTIC / EXPONENTIAL = E2SFCA-style weighting. |
| Analysis | **Summarize accessibility equity** | population-weighted share of residents at or above a threshold, residents with none, mean, p10–p90, Gini — overall and per district. Table + HTML report with one plain-language sentence per field. |
| Analysis | **Generate isochrones** | cumulative travel-time polygons, one per (origin, cutoff): a destination grid → one-origin matrix → TIN raster → `gdal:contour_polygon` per cutoff (the approach r5r/r5py/Conveyal all use — R5 has no isochrone output). Unreachable pockets stay as holes. |
| Analysis | **Prepare population layer** | joins a GUS NSP 2021 sheet to census-tract geometry. |
| Analysis | **Population overlay** | area-weighted population onto a hex grid (fractional, not rounded). |
| Scenarios | **Build scenario** | a scenario file: new lines drawn as QGIS line features (each vertex a stop; speed, headway, service hours), existing routes removed, sped up / slowed down, or given a new headway. Feed it to the `SCENARIO` parameter (Advanced) of every matrix, accessibility, service-minutes, isochrone and 2SFCA run — nothing is rebuilt. |
| Scenarios | **Compare scenarios** | two result layers of the same places, one field → `value_a`, `value_b`, `diff`, `pct_change`, `status` (better / worse / same), styled. Refuses to diff runs with different percentile / decay / window. |

Isochrones are contoured **in QGIS** — R5 has no isochrone output (neither does r5r's or
r5py's engine call; both grid-and-contour, like this). There is no hex-grid
algorithm: use stock `native:creategrid` (recipe below).

See [`docs/notes/product-scope.md`](docs/notes/product-scope.md) and
[`docs/notes/r5-vs-otp.md`](docs/notes/r5-vs-otp.md) for what is deliberately *not* here
(itineraries, GTFS-RT; scenarios shipped in 0.3.0, the service-minutes metric in 0.2.2).

## Quick start

1. **Install** — Easy-R5 is not yet in the QGIS plugin repository. Either copy the
   `easy_r5/` folder into your QGIS profile's `python/plugins/`, or build a ZIP from a
   checkout (`py tools/build_plugin_zip.py` → `builds/easy_r5-<version>.zip`) and use
   *Plugins → Manage and Install → Install from ZIP*. Then enable it.
2. **Download the engine** — run *Setup → Download R5 engine and Java 21*, pick a target folder
   in your user profile. One-time, ~200 MB (Temurin 21 JDK + the R5 jar).
3. **Get data** — you supply the OSM extract (`.osm.pbf` from [Geofabrik](https://download.geofabrik.de/)
   or [BBBike](https://extract.bbbike.org/)) and the GTFS feed(s) (`.zip`) for your study area.
   For a *realized* feed (what actually ran on a given day, P50/P85) or that day's scheduled
   feed, see **Archival / realized GTFS** below.
4. **Check the feed** — *Diagnostics → Check transit data (GTFS)* with the date you plan to
   analyse. Zero errors means the network build and the date gate will not surprise you.
5. **Build a network** — *Setup → Build R5 network*: the `.osm.pbf` and a folder holding your
   GTFS `.zip`(s). Cached by content hash + R5 version, so re-runs are instant.
6. **Analyse** — *Run travel time matrix*, *Run accessibility* or *Run service minutes*: the
   network from step 4, an origins point layer, a destinations point layer, a `DATE` the feed
   actually serves (the run is blocked otherwise), a departure time and window. Output layers
   are styled automatically (except *Run service minutes*, which has no single field to style
   a gradient by — see its PRD).
7. **What if?** — *Scenarios → Build scenario* (draw a line, list routes to remove), then re-run
   step 6 with the file in `SCENARIO` (Advanced) and *Compare scenarios* against the baseline
   run. *Summarize accessibility equity* turns either run into "X% of residents reach …".
   Step-by-step instructions for each of these are in **Guides** below.

The Gdańsk reference data — 1389 origins, 956 destinations, the r5r ground-truth output — is in
[`tools/accessibility_cities/gdansk/`](tools/accessibility_cities/gdansk/); the exact-match
comparison is in [`docs/notes/validation-gdansk.md`](docs/notes/validation-gdansk.md).

![Isochrones from Gdańsk Główny — 15 / 30 / 45 min, 07:00, transit + walk](docs/img/isochrones-gdansk.png)

## Guides — the newer algorithms, step by step

The table above says what each algorithm is for. This section explains, for the algorithms added
in 0.2.2 and 0.3.0, **what question each one answers, how it works inside, how to run it, and what
to watch out for.** All of them live in the Processing toolbox under **Easy-R5**. Every parameter
named in `CAPITALS` below is the parameter's id; in the dialog it has a readable label, and the
ones marked *Advanced* are under the dialog's *Advanced parameters* fold.

A typical study chains them like this:

```
Check transit data ─► Build R5 network ─► Run accessibility / Run competitive accessibility
                                              │  (baseline)        │  (with SCENARIO = file)
                         Build scenario ──────┘                    │
                                              └──► Compare scenarios ◄┘
                                                        │
                            Summarize accessibility equity (either run, or both)
```

### Check transit data (GTFS) — *Diagnostics*

**Question it answers:** "Can I trust this GTFS for an analysis on this date — before I spend
minutes building a network?"

**Why it exists.** When a GTFS feed has no trips on the chosen date, R5 does not fail — it quietly
returns walking-only travel times, and the map looks plausible. That exact mistake once reached a
published result. Easy-R5 already blocks such runs at analysis time; this algorithm catches the
problem earlier, while you can still pick another feed or date.

**How it works.** Pure Python reading the `.zip` files; no Java, no network build. It reads the
calendar the same way the analysis-time date check does (weekday patterns in `calendar.txt`,
additions and removals in `calendar_dates.txt`) and counts **trips actually running on each day**.
It then checks the files against each other and against what R5 7.6 can read.

**How to use it.**
1. Open *Check transit data (GTFS)*.
2. `GTFS` — pick one GTFS `.zip`. With `WHOLE_FOLDER` ticked (default) every `.zip` in the same
   folder is checked together, because *Build R5 network* reads the whole folder. Untick it if the
   zip sits among unrelated downloads.
3. `DATE` — the date you intend to analyse, `yyyy-MM-dd`. Optional, but it is the most useful check.
4. `EXTENT` — optional: your study area (e.g. *Calculate from layer* → your OSM or boundary layer).
5. `OUTPUT_REPORT` — where to save the HTML report. Optionally also `OUTPUT_SERVICE_DAYS` (a CSV of
   trips per date) and `OUTPUT_ROUTES` (a CSV of every route — you will want this for scenarios).
6. Run, then open the HTML report in a browser.

**Reading the report.** Findings are sorted ERROR → WARN → INFO, followed by a bar chart of trips
per day.

| Level | Examples | What to do |
|---|---|---|
| ERROR | no trips on `DATE` (the report lists the 3 nearest served days); a required file missing; a `route_type` R5 7.6 cannot read (it supports 0–7, 11, 12, 100–1499); a realized P50/P85 feed and its scheduled feed in one folder; two feeds with the same feed id; no stop inside `EXTENT` | fix before building — the build or the analysis would fail or silently mislead |
| WARN | trips pointing at routes/stops that do not exist; stops at 0,0; part of the stops outside `EXTENT`; days inside the calendar with no service | usually survivable, but read them |
| INFO | calendar span, trips per day (min/median/max), routes per type, stop bounding box | context |

`ERRORS` and `WARNINGS` are also returned as numbers. `FAIL_ON_ERROR` (*Advanced*) makes the
algorithm itself fail when there are errors — useful inside a model.

---

### Scenarios — "what if?" (*Build scenario* + the `SCENARIO` parameter)

**Question it answers:** "What happens to travel times / accessibility if we add this tram line,
close route 86, slow the buses down, or run route 14 every 5 minutes?"

**How it works.** A scenario is a small `.json` file listing **modifications** to the transit
network. You never edit GTFS and never rebuild the network: when an analysis algorithm gets a
scenario file, the Java runner loads the normal `network.dat`, asks R5 to apply the modifications
to an **in-memory copy** (about 1–2 s), recomputes walking transfers for any new stops, and routes
on that copy. The saved network stays untouched, so the baseline is always one run away.

Four kinds of modification are available from the dialog:

| Modification | What R5 does |
|---|---|
| **New line** (from a line layer) | adds a new route: a stop at each vertex, runs both ways (default) every `HEADWAY_MINUTES` between `SERVICE_START` and `SERVICE_END`, every day |
| **Remove routes** | deletes every trip of the listed routes |
| **Change speed** | scales the running time of the listed routes (`SPEED_SCALE` 0.8 = 20% slower, 1.25 = 25% faster) |
| **New headway** | replaces the timetable of the listed routes, between `HEADWAY_START` and `HEADWAY_END`, with a regular service every `NEW_HEADWAY_MINUTES`; trips outside that window are kept. Each direction keeps its busiest variant; short-turn and depot variants inside the window are dropped rather than each getting the full frequency |

Routes are named the way passengers know them (`86`, `Z2`) — or by GTFS `route_id`, or
`feed:route_id` when several feeds share a name. The exact list is in *Check transit data*'s
`OUTPUT_ROUTES` CSV. A name that matches nothing stops the analysis with a clear error; a name
that matches several routes produces a warning listing them.

#### Step by step: add a new tram line and measure its effect

**1. Draw the line in QGIS.** The new line is an ordinary QGIS line layer — you draw it by hand.
The one rule: **every vertex you click is a stop**, in the order you click them.

1. *Layer → Create Layer → New Temporary Scratch Layer…* (or *New GeoPackage Layer…* if you want to
   keep it after closing QGIS).
2. Geometry type **LineString**, any CRS (it is reprojected automatically). Optionally add a text
   field `name`. OK.
3. Select the layer, *Toggle Editing* (pencil icon), then *Add Line Feature* (Ctrl+.).
4. Left-click once **at each stop location**, first stop to last — typically at intersections or
   where a stop would really be. **Do not add vertices for bends** of the track: each vertex
   becomes a stop.
5. Right-click to finish the line, type a name if you added the field, OK.
6. Repeat for more lines if you want, then *Save Layer Edits* and toggle editing off.

The drawn path between stops is **not** followed. Only the stop positions matter: the travel time
between two consecutive stops is their straight-line distance divided by `SPEED_KMH`, plus
`DWELL_SECONDS` at each stop. `SPEED_KMH` is therefore a speed *over straight-line distance* —
roughly 10–20% below the timetable speed along the real track, because the track is longer than
the straight line:

| Mode | `SPEED_KMH` |
|---|---|
| Tram in a city | **18–22** (the default is 20) |
| City bus in traffic | 15–20 |
| Bus on its own lane / BRT | 20–25 |
| Metro | 25–35 |
| Regional rail | 45–60 |

The log prints each line's end-to-end travel time — compare it with a similar existing line before
trusting the result. New stops are linked to the nearest street, and R5 recomputes walking
transfers between them and the existing stops, so passengers can change between the new line and
the existing network.

**2. Build the scenario file.** Open *Build scenario*:

| Parameter | Example |
|---|---|
| `NEW_LINES` | your drawn layer |
| `LINE_NAME_FIELD` | `name` (optional) |
| `NEW_LINE_MODE` | `TRAM` |
| `SPEED_KMH` | `20` |
| `HEADWAY_MINUTES` | `7.5` |
| `SERVICE_START` / `SERVICE_END` | `05:00` / `23:00` — must cover your analysis departure time **plus** its window |
| `OUTPUT_SCENARIO` | e.g. `…/scenarios/new_tram.json` |

Leave `REMOVE_ROUTES` etc. empty, or combine them in the same file (for example, the new tram
plus removing the bus it replaces). The log prints each new line's stop count and end-to-end time
— check that the time is plausible.

**3. Run the baseline.** Run *Run accessibility* (or any matrix-based algorithm) as usual, with
`SCENARIO` empty. Save the output layer to a file, e.g. `acc_baseline.gpkg`.

**4. Run the scenario.** Run the **same algorithm with exactly the same parameters**, and in
*Advanced parameters* set `SCENARIO` to `new_tram.json`. Save to `acc_new_tram.gpkg`. The output
layer gets a `scenario` field (`new_tram.json:<checksum>`; the baseline says `baseline`), so the
two layers can never be confused later.

**5. Compare.** *Compare scenarios* with `LAYER_A` = baseline, `LAYER_B` = scenario (see below).

The same `SCENARIO` parameter works in *Run travel time matrix*, *Run accessibility*, *Run service
minutes*, *Generate isochrones* and *Run competitive accessibility*.

**Things to know.**
- A scenario that removes routes can leave some trips walking-only; the analysis then warns
  instead of failing. For any other scenario, "not one pair uses transit" is still a hard error,
  because it almost always means a wrong date or a feed that does not match the map.
- Scenario lines run as a regular service ("every N minutes"), so R5 randomises where in the
  headway a passenger arrives — see *Speed of scenario runs* below.
- Advanced users can hand-write the JSON with any of R5's own modification types
  (`add-trips`, `remove-trips`, `adjust-speed`, `adjust-frequency`, `remove-stops`, `reroute`, …).

---

### Compare scenarios — *Scenarios*

**Question it answers:** "Where did it get better or worse, and by how much?"

**How it works.** Joins two result layers **by an id field** (not by location), takes one numeric
field from each and writes a copy of layer A with `value_a`, `value_b`, `diff` (= B − A),
`pct_change` and `status`: `better`, `worse`, `same`, `only_a`, `only_b`. The output is coloured
by `status`.

It refuses to compare runs whose **method** differs — percentile, decay, departure time, window,
modes, catchment, maximum trip time, maximum walk, walking speed, maximum rides, Monte Carlo draws
— because such a difference mixes a method change into the result. It reports, but accepts,
differences that are the point of a comparison: date, network, scenario, transit sub-modes.

**How to use it.**
1. `LAYER_A` — before / baseline; `LAYER_B` — after / scenario.
2. `JOIN_FIELD` — the id field (the same origin id you used in the analysis). `JOIN_FIELD_B` only
   if it is named differently in B.
3. `FIELD` — the value to compare, e.g. `acc_jobs_p50_c30`; `FIELD_B` only if named differently.
4. `HIGHER_IS_BETTER` — **on** for accessibility, service minutes and 2SFCA (an empty value counts
   as 0). **Off** for travel times: lower is better, and an empty value means "unreachable", so a
   lost connection shows as `worse`, never as a gain.
5. Run. The log summarises better / worse / same counts and the mean change.

`ALLOW_METHOD_MISMATCH` (*Advanced*) overrides the method check — only when you really mean to
compare, say, P50 with P85.

**Comparing on a hex grid.** *Compare scenarios* keeps layer A's geometry, whatever it is, so the
result can be points or polygons. Accessibility runs need **point** origins, so a hex-grid study
has two equally good routes to a filled hex map:

- *Compare first, then join.* Run the comparison on the two accessibility outputs (hex centroids),
  then **Processing → `native:joinattributestable`**: input = your hex polygons, field = the hex
  id, input 2 = the comparison layer, field 2 = the same id. Style the joined hexes by `diff` or
  `status`.
- *Join first, then compare.* Join each accessibility output to a copy of the hex polygons, then
  compare the two polygon layers directly — the output is already hexagonal and coloured by
  `status`.

Either way the hex id must be a real field on the origins (use it as `ORIGIN_ID_FIELD` in the
analysis), not the QGIS feature id.

It is also the tool for **timetable changes** and **scheduled vs realized** comparisons: run the
same analysis on two networks and compare.

---

### Run competitive accessibility (2SFCA) — *Analysis*

**Question it answers:** "How many doctors (school places, beds …) are there **per 1000
residents**, counting that everyone who can reach a clinic competes for it?"

*Run accessibility* counts what you can reach — a clinic with 5 doctors counts as 5 for everyone
within 30 minutes, however many people that is. 2SFCA (two-step floating catchment area, Luo &
Wang 2003) shares the supply among the people who can reach it.

**How it works.** One travel-time matrix from demand points (origins, with population) to supply
points (destinations, with capacity), then two steps in Python:

1. For each destination: `ratio = capacity ÷ population that reaches it within CATCHMENT_MINUTES`.
2. For each origin: sum the ratios of every destination it reaches within the catchment, then
   multiply by `PER_POPULATION`.

With `DECAY = STEP` this is classic 2SFCA. `LOGISTIC` / `EXPONENTIAL` give nearer destinations
more weight (an E2SFCA-style variant); the weight still drops to 0 at the catchment, so results
are sensitive to `CATCHMENT_MINUTES`. The log checks the method's own identity: all supply that
anyone can reach is distributed — no more, no less.

**How to use it.**
1. `ORIGINS` — population points, e.g. hex-grid centroids with a population field from *Population
   overlay*. They must cover **everyone who competes** for the destinations, not only the area you
   want to map, or the supply looks less crowded than it is.
2. `POPULATION_FIELD` — the population field on the origins.
3. `DESTINATIONS` + `CAPACITY_FIELD` — the facilities and their capacity (doctors, places, beds).
4. `CATCHMENT_MINUTES` — e.g. 30. `PERCENTILES` — **one** value (50 by default).
5. `PER_POPULATION` — 1000 gives "per 1000 residents".
6. The date, time, mode and other travel parameters are the same as in *Run accessibility*;
   `SCENARIO` works too.
7. Outputs: `OUTPUT_LAYER` (origins + `fca`), optional `OUTPUT_SUPPLY_LAYER` (facilities +
   `supply_ratio` and `demand_in_catchment` — which facilities are overloaded), `OUTPUT_CSV`.

#### Step by step: doctors per 1000 residents

**1. Prepare the demand side (origins).** You need points that carry population.
1. Build a hex grid over the study area and take its centroids (see *Hex grid* below), keeping a
   unique `hexid` field.
2. Get population onto them: *Prepare population layer* (a GUS NSP sheet joined to census-tract
   geometry) → *Population overlay* (area-weighted population onto the hex grid) → centroids, or
   any population field you already have.
3. Make sure the grid covers **everyone who competes** for the facilities, not only the district
   you want to map — otherwise a clinic looks less crowded than it is. A ring of roughly the
   catchment's width beyond your area of interest is the usual compromise.

**2. Prepare the supply side (destinations).** A point layer of facilities with a numeric capacity
field: doctors, school places, hospital beds, counter positions. If you only have locations, add a
field with `1` in each — the result is then "facilities per 1000 residents", which is still
competitive, just coarser.

**3. Run it.** *Run competitive accessibility (2SFCA)*:

| Parameter | Value |
|---|---|
| `NETWORK` | your `network.dat` |
| `ORIGINS` / `ORIGIN_ID_FIELD` | hex centroids / `hexid` |
| `POPULATION_FIELD` | e.g. `pop_total` |
| `DESTINATIONS` / `DEST_ID_FIELD` | clinics / their id |
| `CAPACITY_FIELD` | e.g. `doctors` |
| `DATE`, `DEPARTURE_TIME`, `TIME_WINDOW` | a served weekday, e.g. `2026-08-24`, `07:00`, `120` |
| `CATCHMENT_MINUTES` | `30` |
| `DECAY` | `STEP` (classic 2SFCA) |
| `PERCENTILES` | `50` — exactly one value |
| `PER_POPULATION` | `1000` |
| `OUTPUT_LAYER` / `OUTPUT_SUPPLY_LAYER` / `OUTPUT_CSV` | files, not temporary layers, if you want to compare later |

**4. Read the result.** The origins layer gets `fca`: capacity per 1000 residents available to the
people living there, given the competition. A hex with `fca = 1.6` has 1.6 doctors per 1000
residents within reach; the national or regional average is the natural yardstick. The log prints
a check line — the supply distributed to origins equals the supply anyone can reach — and warns
about facilities nobody reaches. The optional supply layer shows, per facility, `supply_ratio`
(capacity per person) and `demand_in_catchment` (how many people can reach it): that is where
"this clinic serves 40 000 people" comes from.

**5. Take it further.**
- Add `SCENARIO` to ask "does the new tram line change who can reach the hospital?".
- Feed the output to *Summarize accessibility equity* to get "X% of residents have fewer than 1
  doctor per 1000 within 30 minutes".
- Compare two runs (`fca` field) with *Compare scenarios*.

**Pitfalls.**
- The result is on a **different scale** from *Run accessibility* — never compare the two numbers
  directly, and always say the catchment and percentile next to the number.
- Changing `CATCHMENT_MINUTES` changes every value; it is a modelling choice, not a detail.
- A capacity field with zeros is fine; empty/negative counts as 0.

---

### Summarize accessibility equity — *Analysis*

**Question it answers:** "What share of residents can reach at least one hospital within 30
minutes — and is access spread evenly or concentrated?"

**How it works.** Takes any layer that has a population field and numeric accessibility fields
(typically the output of *Run accessibility* or *Run competitive accessibility* on a population
grid — those outputs keep the origin layer's fields). Every statistic is **weighted by
population**, so it speaks about people, not hexagons:

| Column | Meaning |
|---|---|
| `population` | residents counted |
| `pop_at_least`, `share_at_least` | residents with a value ≥ `THRESHOLD` |
| `pop_zero`, `share_zero` | residents with no access at all |
| `mean` | population-weighted mean |
| `p10` … `p90` | the value below which 10% … 90% of residents fall |
| `gini` | inequality of access, 0 = everyone equal, towards 1 = concentrated in few places |

An empty accessibility value counts as 0 (no access); a feature with empty or negative population
is skipped and counted in the log.

**How to use it.**
1. `INPUT` — the accessibility layer.
2. `POPULATION_FIELD` — e.g. the field from *Population overlay*.
3. `ACCESSIBILITY_FIELDS` — one or more, e.g. `acc_hospitals_p50_c30`.
4. `THRESHOLD` — `1` answers "reaches at least one"; `500` answers "reaches at least 500 jobs".
5. `GROUP_FIELD` — optional, e.g. a district name joined to the grid: adds one row per district.
6. Outputs: `OUTPUT_TABLE` (a table layer, one row per group × field) and `OUTPUT_REPORT` (HTML with
   a plain-language sentence per field, e.g. *"ALL: 52.6% of residents (15 000 of 28 500) have
   acc_jobs_p50_c30 ≥ 500; 0.0% have none."*, and the run method recorded in the layer — percentile,
   date, scenario …).

#### Step by step: "how many residents reach a hospital in 30 minutes?"

**1. Get accessibility and population onto the same features.** The easiest path: run
*Run accessibility* (or *Run competitive accessibility*) with `ORIGINS` = the population grid
centroids, `ORIGIN_ID_FIELD` = the hex id, and the population field already on that layer — the
output copies every origin attribute, so it carries both the population and `acc_*` fields.
If your population lives in a different layer, join it first with `native:joinattributestable`.

**2. Run the summary.** *Summarize accessibility equity*:

| Parameter | Value |
|---|---|
| `INPUT` | the accessibility output layer |
| `POPULATION_FIELD` | `pop_total` |
| `ACCESSIBILITY_FIELDS` | e.g. `acc_hospitals_p50_c30` (pick several at once if you want) |
| `THRESHOLD` | `1` — "at least one hospital". Use `500` for "at least 500 jobs", `1.0` for "at least 1 doctor per 1000" on a 2SFCA layer |
| `GROUP_FIELD` | optional — a district name, a rural/urban flag, an income class |
| `OUTPUT_TABLE`, `OUTPUT_REPORT` | the table and the HTML report |

**3. Read the report.** The first line is the sentence you can quote: *"ALL: 52.6% of residents
(15 000 of 28 500) have acc_jobs_p50_c30 ≥ 500; 0.0% have none."* Then the table:

- `share_at_least` — the headline number, weighted by people.
- `share_zero` — the group that has nothing at all, usually the politically relevant one.
- `p10` — what the worst-served tenth of residents actually gets; `p50` the median resident.
- `gini` — how unevenly access is spread: 0 means everyone has the same, higher means it is
  concentrated in a few places. Useful *between* comparable runs (before vs after, city vs city),
  not as an absolute grade.
- With `GROUP_FIELD`, one row per district plus the `ALL` row: that is the "which district is worst
  off" table.

**4. Use it in a comparison.** Run the same summary on the baseline and on a scenario and quote the
difference in people: "the new tram line brings 12 300 more residents within 30 minutes of a
hospital, and the share with no access falls from 9% to 4%". That is the sentence a council reads;
the map is the evidence next to it.

**Pitfalls.**
- An empty accessibility value counts as 0 — right for accessibility, wrong for a travel-time
  field. Do not point this algorithm at travel times.
- Features with empty or negative population are skipped; the count appears as a warning.
- `gini` is left empty for a field that contains negative values (a `diff` field, for instance),
  because the coefficient is not defined there.

---

### Run service minutes — *Analysis*

**Question it answers:** "Not just *how long* the trip takes, but *how often* the destination is
reachable in time" — a trip with a 25-minute median can be every 8 minutes or once an hour.

**How it works.** R5 already routes every minute of the departure window. This algorithm keeps
R5's per-minute distribution and counts, for each origin–destination pair and each cutoff, **how
many departure minutes arrive within the cutoff** (`svc_min_c30` = 90 means: leaving at 90 of the
120 minutes gets you there within 30 minutes).

**How to use it.** Like *Run travel time matrix*, but with `CUTOFFS` (e.g. `15,30,45,60`) instead
of percentiles. Cutoffs and `MAX_TRIP_DURATION` must stay **below 120 minutes** (R5 records this
distribution over a fixed 120-minute range). Output: a CSV with `from_id, to_id, svc_min_c<cutoff>…`,
values 0–120, and optional OD lines.

This is **not** the same number as easy-OTP's service-time classification — a different method
and reference window. Do not compare the two.

---

### Monte Carlo draws — what they are, and the speed of scenario runs

**The problem they solve.** Easy-R5 never routes a single departure: it routes **every minute** of
the departure window (120 by default) and reports percentiles over those minutes. For a route with
a real timetable that is enough — departure 07:13 either catches the 07:15 bus or it does not.
But some routes are published as *"every 10 minutes"* with no exact times: GTFS `frequencies.txt`
(Warsaw, for example), every line you add with *Build scenario*, and every route you give a new
headway. For those, "leaving at 07:13" has no defined answer — the next vehicle could come in 10
seconds or in 10 minutes.

**What R5 does.** For each departure minute it draws several random timetables consistent with the
headway, routes each, and treats every draw as one observation. `MONTE_CARLO_DRAWS` (*Advanced*,
default 5 per minute, the same default as r5r) says how many. So a 120-minute window with
frequency routes is 600 routings per origin instead of 120.

**Where it shows up.** The parameter sits on every matrix-based algorithm (travel time matrix,
accessibility, service minutes, isochrones, 2SFCA) because they all share the same run, but it
**only has an effect when the network actually contains frequency routes** — that is, when you use
a scenario line or a new headway, or your GTFS has `frequencies.txt`. On a plain scheduled feed R5
does one pass per minute whatever you set.

More draws mean a more stable answer: with too few, two identical runs can disagree by a minute or
two purely by luck, and a comparison would show "changes" that are noise. The defaults are chosen
so that this does not happen.

**The 0.3.0 fix.** Easy-R5 used to pass this number to R5 as-is, but R5 reads it as a total for the
whole window — so the default gave about **one** sample per minute, not five. Results for frequency
routes were noisy and two identical runs could differ, which would make *Compare scenarios* report
changes that are not there. 0.3.0 passes it correctly, and identical runs now produce identical
results.

**What it costs.**
- **Networks without frequency routes** (most Polish scheduled GTFS, with no scenario): no change
  at all — R5 does one pass per minute regardless of this setting.
- **With frequency routes:** slower, in proportion to how much of the network runs by frequency.
  Measured on Łódź with one drawn tram line and a 120-minute window: routing took **~1.4×** as long
  as the same network without it. A network where most routes are frequency-based can approach
  the theoretical **5×**.
- For a quick first look, set `MONTE_CARLO_DRAWS` to `1` — as fast as before, but noisier. Use the
  default for anything you publish or compare.

## Archival / realized GTFS

*Setup → Download realized GTFS*, or **Plugins → Easy-R5 → Download transit recordings…**
for a pick-from-a-list dialog, fetches a feed from
[GISBoost's gtfs-dashboard](https://gisboost.github.io/gtfs-dashboard/) — the index of
recordings produced by the [`easy-GTFS-RT`](https://github.com/GISBoost/easy-GTFS-RT)
pipeline for ~25 cities on specific days. Pick a city, a day, and a variant:

- **Realized P50 / P85** — the timetable rewritten to match what vehicles actually did that
  day (median, or the conservative 85th percentile). This is the *only* way realtime
  information enters Easy-R5; R5 does not read GTFS-RT.
- **Scheduled** — the static GTFS as published for that day.

It downloads into `…/transit-recordings/<city>/<date>/<variant>/`, ready to hand to
*Build R5 network*. Realized and scheduled feeds share trip / stop ids, so each variant gets
its own folder. This is **not** a general GTFS source — for feeds outside GISBoost's
recordings, download from the operator or [Mobility Database](https://mobilitydatabase.org/).
No checksum is published for these assets, so the download is CRC-checked and sniffed for the
GTFS files, nothing stronger.

## Hex grid — use stock QGIS

Easy-R5 ships no hex-grid algorithm. To reproduce `gdansk_hex_origins.csv`'s layout:

1. **Processing → `native:creategrid`** — `TYPE = Hexagon`, `HSPACING = VSPACING = 500`
   (metres), `GRID EXTENT` = your study area, `GRID CRS` = a metric CRS (e.g. EPSG:2180).
2. **`native:extractbylocation`** — keep only hexes that *are within* / *intersect* the
   study-area boundary.
3. **`native:centroids`** — the origin points; add an `id` field with the Field Calculator
   (`@row_number` or a stable code) and export `id,lon,lat` after reprojecting to EPSG:4326.

(See `tools/accessibility_cities/HOWTO_MANUAL.md` step 4.)

## Earlier experiment: modal complementarity

**Kept as a dogfooding example, not the flagship result:** four `Run accessibility` passes on
one network — walk / tram+walk / bus+walk / full network, varying only `TRANSIT_SUBMODES` —
asked how much of Łódź depends on its trams, and it worked end-to-end (27.5% of the city's
30-minute reach disappears without the tram, 21.7% without the bus, 13.6% only via the
tram↔bus transfer; real R5 7.6). We moved away from leading with this once literature review
showed "counterfactual mode removal" is a fairly standard method by 2025-2026 standards —
current direction is [`tools/realtime_delay_lodz/`](tools/realtime_delay_lodz/README.md) (real
GTFS-RT delays vs. service reachability). This one stays as a proof that `TRANSIT_SUBMODES`
dogfoods correctly, and a candidate to revisit later.
[How we measured it →](docs/notes/flagship-lodz-modal-results.md) ·
[reproduce it →](tools/modal_complementarity_lodz/README.md)

## How it works

Easy-R5 runs the R5 engine as a **child process**, not as an in-process library —
which is what r5r and r5py do, and both need dependencies a stock QGIS cannot
install (R, or 16 pip packages). Python builds a job and reads the result; the
child process does the routing and nothing else:

```
  ┌─ QGIS · Python / PyQGIS
  │
  │   a Processing algorithm collects the parameters
  │   core/runner.py   builds job.json, spawns the child process,
  │                    reads its stdout, kills it on cancel
  │   matrix.py / accessibility.py / isochrones (contoured in QGIS)
  │        →  styled QGIS layer  (+ r5_version, run_date, … fields)
  │
  └───────────────┐   job.json ↓    stdout: PROGRESS / DONE / ERROR  + CSV ↑
                  │   a pipe + temp files — no JVM inside QGIS
  ┌───────────────┘
  │   child process · JVM (Temurin 21)
  │
  │   EasyR5Runner.java   one .java file, the only Java we maintain:
  │        reads job.json  →  builds a RegionalTask
  │        loops over origins  →  com.conveyal.r5.TravelTimeComputer
  │        writes matrix_000.csv,  streams progress lines
  │   r5-v7.6-all.jar   the official Conveyal build, unmodified
  │
  └─ separate PID · its own -Xmx heap · an R5 OOM ≠ a QGIS crash

  Java does routing only. Grids, contouring, zonal statistics,
  classification, styling and reports are all Python / QGIS.
```

Rough sketch — the full reasoning (why a subprocess, why one `.java` file, why
not r5r or r5py) is in
[**How QGIS talks to R5**](https://gisboost.github.io/easy-R5/).

## Repository layout

| Path | What it is |
|---|---|
| `easy_r5/` | the QGIS plugin |
| `easy_r5/java/EasyR5Runner.java` | the one Java source file that drives R5 (`build`, `matrix`) |
| [`CONTEXT.md`](CONTEXT.md) | glossary — the words this project uses |
| [`docs/adr/`](docs/adr/) | architecture decisions |
| [`docs/notes/`](docs/notes/) | engine primer, binding comparison, scope, migration plan, open questions |
| [`tools/`](tools/README.md) | standalone R5 research tooling — accessibility and isochrone studies for 7 Polish cities, migrated from easy-OTP ([ADR-0003](docs/adr/0003-migrate-r5-tools.md)). Gdańsk is the plugin's reference dataset. |

## Requirements

| Requirement | Version | How to get it |
|---|---|---|
| QGIS | 3.22 LTR or newer (developed on 3.40) | qgis.org — the plugin uses the bundled Python and GDAL |
| Java | **21** (Temurin) | *Download R5 engine and Java 21* fetches it |
| R5 | **pinned** `r5-v7.6-all.jar` — see [ADR-0002](docs/adr/0002-pinned-versions.md) | same algorithm, SHA-256 verified |
| OSM extract | any `.osm.pbf` covering the study area | you supply it (Geofabrik, BBBike) |
| GTFS feed(s) | any valid feed | you supply it (the operator, transitfeeds, MobilityData) |
| `openpyxl` (optional) | 3.1.5 | **only** *Prepare population layer* / *Population overlay* need it. The plugin fetches the pure-Python wheel from PyPI (SHA-256 verified, no `pip`) on first load; if that fails it prints a one-line manual-install hint. Every other algorithm works without it. |

## Licence

GPL-3.0-or-later. R5 itself is MIT (© Conveyal LLC) and is downloaded, not vendored.

## Credits

R5 is developed by [Conveyal](https://www.conveyal.com/). This plugin is not affiliated with
Conveyal. The existing R bindings [`r5r`](https://github.com/ipeaGIT/r5r) (IPEA) and
[`r5py`](https://github.com/r5py/r5py) are not dependencies here, but `r5py`'s source was the
reference for how R5's Java API is used — credit where it is due.
