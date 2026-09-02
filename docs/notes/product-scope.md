# Who Easy-R5 is for, and what it should therefore contain

Not a PRD. A scope sketch, written before any milestone planning, so the first PRD has a target
to aim at. See [`r5-vs-otp.md`](r5-vs-otp.md) for why the algorithm list differs from easy-OTP's.

## Target user

The same person easy-OTP was built for, and deliberately **not** the person `r5r`/`r5py` already
serve well:

**Primary — the QGIS-native analyst.** A transport or urban planner in a city hall, a transit
authority, a consultancy, or an NGO. Has QGIS installed and knows the Processing toolbox. Does
**not** have R, conda, Docker, a Python environment they control, or (often) local admin rights.
Wants an answer — "how many residents reach a hospital within 30 minutes by transit", "which
district got worse after the timetable change" — as a styled layer, not as a data frame.

**Secondary — the student / researcher.** Needs a defensible, reproducible accessibility indicator
for a thesis or a paper, and needs to explain the method in text. Cares that the departure-time
window and percentile are explicit and recorded in the output.

**Explicitly not the target.** Someone comfortable writing `r5r` or `r5py` in a notebook. They
already have a faster, more flexible path; Easy-R5 competing there is pointless. If they land here
anyway, the plugin should at least not lie to them: same engine, same pinned version, results
comparable to a notebook run.

### What that implies, concretely

- **Install = install the plugin.** One setup algorithm downloads the JDK and the R5 jar (~240 MB
  total, first run only). No terminal, no environment variables, no admin.
- **Windows first**, Linux/macOS supported. That is where the users are, and it is where the
  Kryo-file-locking and long-path problems live.
- **Laptop-sized defaults.** 16 GB RAM, no cluster. Heap sized from available memory, origins
  batched automatically, and an OOM must produce *"reduce the grid density / raise the heap"*,
  not a Java stack trace. This is the failure the existing r5r pipeline hit repeatedly.
- **Cancellable, with a real progress bar.** Runs take minutes to hours.
- **Outputs are QGIS layers with styles**, plus CSV/XLSX for reporting — not bare CSVs.
- **Bilingual UI (EN/PL)** from the start, as in easy-OTP v0.5+.
- **The method is recorded in the output.** Departure date/time, window length, percentile(s),
  cutoffs, modes, R5 version, feed ids — as fields or layer metadata. Two runs that look alike
  and differ in percentile are the single most likely way a user misreads their own map.

## Candidate algorithm list (sketch, not a commitment)

Grouped the way easy-OTP groups its provider. `Setup/` and `Analysis/` only — there is no
`Realtime/` section, because R5 cannot ingest GTFS-RT (see `r5-vs-otp.md`).

**Setup/**
- `DownloadR5` — Temurin 21 JDK + pinned `r5-vX.Y-all.jar`, checksum-verified (mirrors easy-OTP's
  `DownloadJre`).
- `DownloadTransitData` — OSM extract + GTFS; port from easy-OTP nearly unchanged.
- `BuildNetwork` — `.osm.pbf` + GTFS folder → `network.dat`, cached by input hash + R5 version,
  reporting feed ids, service calendar range and network bounds back to the user.

**Diagnostics/**
- `TestR5Setup` — Java present and version 21, jar present and hashed, network loads, one trivial
  route succeeds. The equivalent of `TestOtpServer`, and the first thing to write.

**Analysis/**
- `RunTravelTimeMatrix` — N×M, departure window, percentiles. The flagship.
- `RunAccessibility` — opportunities + cutoffs + decay (step / logistic / exponential) →
  accessibility per origin. This is what every migrated `tools/` script computes.
- `GenerateIsochrones` — travel-time grid → contoured polygons in QGIS.
- `GenerateHexGrid` — port from easy-OTP (or reuse easy-OTP's; decide once).
- `PopulationOverlay`, `PrepareStudentLayer` — same question.
- `CompareScenarios` — two runs → delta layer. Cheap to build once the matrix exists, and the
  thing planners actually ask for.
- *(later)* `RunScenarioAnalysis` — R5 network modifications (a new line, a closed street). The
  real long-term differentiator versus easy-OTP; needs its own PRD.

## Non-goals for v0.1

Detailed itineraries; fare calculation; pareto frontiers; anything realtime; the Conveyal Analysis
backend; a bundled routing server.
