# How to talk to R5 from a QGIS plugin: r5r vs r5py vs our own

Evidence behind [ADR-0001](../adr/0001-r5-binding.md). Checked September 2026.

The governing constraint is inherited from easy-OTP and restated in `CLAUDE.md`:
**the plugin must run on a stock QGIS install — no `pip install`, no R, no conda, no Docker.**
Downloading *binaries* at setup time is already accepted practice (easy-OTP's `DownloadJre`
fetches a Temurin JRE and the OTP jar), so "download a jar / a JDK" is allowed;
"install Python packages into QGIS's interpreter" is not.

---

## The four candidates

### A. `r5r` (R package, ipeaGIT)

| | |
|---|---|
| How it calls R5 | rJava, in-process JVM, through **its own wrapper jar** `r5r_core` (~250 KB of Java under `java-r5rcore/`) |
| Requires | R + `rJava` + Java 21 |
| Licence | GPL-3.0-or-later **or** MIT (dual) |
| API | `setup_r5()`, `travel_time_matrix()`, `accessibility()`, `isochrone()`, `detailed_itineraries()`, `pareto_frontier()` |
| Verdict | **Rejected for the plugin.** "ZERO R" is a hard project constraint, and shipping an R runtime inside QGIS is not on the table. |

Still relevant, though: `r5r` is what every existing tool in `easy-OTP/tools` uses, so it defines
the *behaviour* Easy-R5 has to reproduce, and its `java-r5rcore` is a working reference for how to
drive R5 from outside. Note its Java code is shaped around R data frames (`RDataFrame`) and builds
against `JRI.jar`, i.e. it is not reusable as-is without R in the build.

### B. `r5py` (Python package)

| | |
|---|---|
| How it calls R5 | **JPype**, in-process JVM, vanilla-ish R5 classes directly (see the primer's API map) |
| Requires | Python ≥ 3.10, **JDK 21**, and these runtime deps: `ConfigArgParse, filelock, geohexgrid, geopandas, joblib, jpype1, numpy, pandas, psutil, pyproj, rasterio, requests, scikit-learn, shapely, simplification, typing_extensions` |
| Licence | GPL-3.0-or-later or MIT (dual) |
| R5 jar | its own fork, `r5py/r5` tag `v7.6-r5py` (4-file patch, see primer §4), auto-downloaded with SHA-256 check |
| Verdict | **Rejected as a runtime dependency inside QGIS.** 16 packages, several of them compiled (`jpype1`, `rasterio`, `simplification`, `scikit-learn`), plus `geopandas` — this is a conda-shaped dependency tree, not a "single exception". |

`r5py` is nevertheless the **best available blueprint**: its `src/r5py/r5/*.py` is effectively
documentation of which R5 Java classes to call in what order, and it is the reason we know the
fork patch is tiny. Read it; don't ship it.

Note also that r5py's Python API (`TravelTimeMatrix`, `DetailedItineraries`, `Isochrones`) leans
hard on GeoPandas semantics that a QGIS plugin does not need — inside QGIS the natural containers
are `QgsVectorLayer` / `QgsRasterLayer`, so even the API shape would need rewriting.

### C. JPype only — our own thin Python bindings

Drop `r5py`, keep its idea: `pip install jpype1` as the *single* exception, then call
`com.conveyal.r5.*` ourselves from Python and put the results straight into QGIS layers.

- **Pro:** no Java to write; full R5 API; one dependency.
- **Con:** `jpype1` is a **compiled** wheel — the download has to match QGIS's exact Python ABI and
  platform (QGIS 3.22 = Python 3.9; newer QGIS = 3.12), which is a much riskier bootstrap than
  easy-OTP's pure-Python `openpyxl` wheel trick.
- **Con:** the JVM then lives **inside the QGIS process**: an R5 OOM or JVM crash takes QGIS down
  with it, heap size is fixed at first JVM start and cannot change without restarting QGIS, and
  cancelling a long run means interrupting Java from the GUI thread rather than killing a process.
  Given §6 of the primer (real OOMs at 12 GB on Warszawa), this is a genuine operational problem.
- **Verdict:** viable **plan B**, documented, not chosen.

### D. R5 jar + our own runner, as a subprocess ← recommended

Same shape as easy-OTP's proven architecture (start Java as a child process, talk to it, kill it
in `finally`), except the child is not a server but a job runner.

R5 has no CLI that does travel-time matrices (primer §2), so a small amount of Java is
unavoidable. The lazy way to get it, with **no second repository, no Gradle, no jar releases**:

> Ship **one `.java` source file** inside the plugin and compile/run it with the JDK we already
> download, using Java's single-file source launcher (JEP 330, Java 11+):
>
> ```
> java -Xmx8g -cp r5-v7.6-all.jar EasyR5Runner.java job.json
> ```
>
> or compile once at setup (`javac -cp r5-v7.6-all.jar -d <cache> EasyR5Runner.java`) and run the
> class afterwards, to skip the ~1–2 s compile per invocation.

- **Pro:** zero Python dependencies. Zero build tooling. The Java stays *source* in the plugin
  repo, which is also the friendliest possible reading of GPL-3.0 distribution.
- **Pro:** process isolation — heap per run, cancel = kill PID, an R5 OOM kills the child, not QGIS.
- **Pro:** the Java surface stays small, because everything that isn't routing (grids, contouring,
  zonal stats, classification, styling, XLSX) is already solved in Python/QGIS by easy-OTP.
- **Con:** we need a **JDK**, not a JRE (~180 MB vs ~45 MB for Temurin 21) — unless we pre-compile
  and ship a `.class`/jar, which reintroduces a build step.
- **Con:** the single-file launcher allows exactly one compilation unit up to Java 21 (multi-file
  source programs only landed in Java 22), so the runner must stay **one file** — several
  package-private classes in that file are fine, but it caps how big it can get before it needs a
  real build.
- **Con:** we own Java code against an API whose upstream explicitly refuses to keep it stable.
  Mitigation: pin the R5 version (ADR-0002) and keep the runner's surface minimal.

**Minimum runner scope** (everything else stays in Python):

1. `build` — inputs dir (`.osm.pbf` + GTFS zips) → `network.dat`, plus a small JSON summary
   (feed ids, service calendar range, bounds) for validation in the UI.
2. `matrix` — `network.dat` + origins CSV + destinations CSV (or a grid spec) + mode/date/time/
   window/percentiles → travel times CSV, streaming progress lines to stdout for the progress bar.
3. *(later)* `itinerary` — detailed legs, when a "plan a trip" algorithm is wanted.

---

## Side-by-side

| | r5r | r5py | JPype-only | **jar + our runner** |
|---|---|---|---|---|
| Runs on stock QGIS | ✗ (needs R) | ✗ (16 pip deps) | ~ (1 compiled pip dep) | ✓ |
| Java we maintain | none | none | none | ~1 file |
| JVM crash kills QGIS | – | – | ✓ (bad) | ✗ (good) |
| Heap per run | – | – | ✗ | ✓ |
| Cancel = kill process | – | – | ✗ | ✓ |
| Needs JDK (not just JRE) | JDK 21 | JDK 21 | JDK/JRE 21 | JDK 21 (or pre-compile) |
| Breaks when R5 changes | upstream's problem | upstream's problem | ours | ours |

## Recommendation

**D**, with **C** kept as the documented fallback if the Java runner turns out to be a maintenance
tarpit. Neither `r5r` nor `r5py` becomes a dependency of the plugin — but `r5py`'s source stays
the primary reference for *how* to call R5, and `r5r`'s behaviour stays the reference for *what*
the outputs should look like.
