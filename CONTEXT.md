# CONTEXT — Easy-R5

Single-context repo. This file is the glossary; decisions live in [`docs/adr/`](docs/adr/),
background in [`docs/notes/`](docs/notes/).

## What this repo is

A QGIS Processing plugin (`easy_r5/`) that runs transit accessibility analysis on the **Conveyal
R5** routing engine, plus the standalone R5 research tooling under `tools/`. Sibling of
[easy-OTP](https://github.com/GISBoost/easy-OTP), which does the same job on OpenTripPlanner 1.5
and owns everything realtime.

## Glossary

Use these terms; avoid the synonyms listed as "not".

- **R5** — Conveyal's routing engine (`conveyal/r5`, MIT, Java 21). Always the engine itself,
  never a binding. *Not:* "R", which in this repo only ever means the R language.
- **Network** — R5's serialised `network.dat` (Kryo) built from one `.osm.pbf` plus one or more
  GTFS feeds. *Not:* "graph" (that is OTP's word, and easy-OTP's `Graph.obj`).
- **Runner** — the small Java program Easy-R5 ships and executes as a child process to call R5.
  *Not:* "server" — it is a job runner, it does not listen on a port.
- **Job spec** — the JSON document the plugin writes and the runner consumes for one operation
  (build / matrix / …).
- **Origins / destinations** — the point sets of a one-to-many or many-to-many computation.
  Origins are usually hex-grid centroids, destinations usually opportunities.
- **Opportunities** — the countable things at destinations (jobs, school places, university
  buildings, shops). The columns summed by an accessibility computation.
- **Departure window** — the span after the departure time over which R5 varies the departure
  minute (e.g. 07:00 + 120 min). R5's native answer to timetable variability; easy-OTP simulates
  the same thing with one surface per minute.
- **Percentile** — which point of the travel-time distribution over the departure window is
  reported (P50 = median, P85 = a bad-but-not-worst day). R5 accepts at most 5 per task.
- **Cutoff** — a travel-time threshold in minutes used by cumulative-opportunity accessibility
  (15/30/45/60 in the existing studies).
- **Decay function** — how opportunities are weighted by travel time: `step` (cumulative
  opportunity, what the existing studies use), logistic, exponential.
- **Accessibility** — the weighted count of opportunities reachable from an origin. Always say
  which cutoff, percentile and decay; a bare "accessibility" number is meaningless.
- **Isochrone** — a polygon of equal travel time. In Easy-R5 these are **contoured in QGIS from an
  R5 travel-time grid**, not produced by R5 itself.
- **Realized GTFS (P50 / P85)** — a static feed reconstructed from recorded GTFS-RT, produced by
  easy-OTP's `BuildRealizedGtfs` or `tools/family_a_reconstruction`. R5 cannot read GTFS-RT, so
  this is the *only* way realtime information enters Easy-R5. *Not:* "realtime analysis".
- **Static variant / RT variant** — a network built from the scheduled feed vs. one built from the
  realized feed. They share `trip_id`s and therefore need separate network directories.
- **Scenario** — an R5 network modification (new line, closed street, changed speeds) applied at
  request time. Future work; R5's real differentiator over OTP.

## Boundaries

- `easy_r5/` — the plugin. Stock QGIS only: no `pip install`, no R, no GRASS.
- `easy_r5/java/` — the runner source (one file). The only Java in the repo.
- `tools/` — standalone research tooling, outside the plugin, own environments, may use R.
- `docs/reference/` — read-only reference material. Never executed.
