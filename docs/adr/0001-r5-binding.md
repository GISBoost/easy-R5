# ADR-0001 — How Easy-R5 calls the R5 engine

- **Status:** **Accepted** (2026-09-02, Michał)
- **Date:** 2026-09-02
- **Evidence:** [`docs/notes/bindings-comparison.md`](../notes/bindings-comparison.md),
  [`docs/notes/r5-engine-primer.md`](../notes/r5-engine-primer.md)

## Context

Easy-R5 is a QGIS Processing plugin that must run on a **stock QGIS install** — the same rule
easy-OTP lives under: no `pip install`, no R, no conda, no Docker; downloading *binaries*
(a Java runtime, a jar) at setup time is allowed and already precedented (`DownloadJre`).

R5 ships no CLI or server that computes travel-time matrices or accessibility — the only
`main()` classes in `r5-v7.6-all.jar` are the full Conveyal Analysis backend (MongoDB + worker
cluster) and a point-to-point *debug* server. Every existing binding therefore calls R5's Java
classes directly: `r5r` through rJava + its own `r5r_core` jar, `r5py` through JPype.

Neither can be a dependency here: `r5r` requires R (hard "ZERO R" constraint), `r5py` requires 16
Python packages including compiled ones (`jpype1`, `rasterio`, `simplification`, `scikit-learn`)
plus `geopandas` — a conda-shaped tree, not "a single exception".

## Decision

Talk to R5 as a **child process**, the same architectural shape easy-OTP already uses for OTP:

1. Pin and download **Conveyal's official `r5-vX.Y-all.jar`** (see ADR-0002) plus a **Temurin 21
   JDK**, via a `DownloadR5` setup algorithm modelled on easy-OTP's `DownloadJre`.
2. Ship **one Java source file** (`easy_r5/java/EasyR5Runner.java`) in the plugin and run it with
   the single-file source launcher — `java -Xmx… -cp r5-…-all.jar EasyR5Runner.java job.json` —
   or `javac` it once at setup and run the compiled class thereafter.
3. Keep the runner's scope minimal: **build network**, **travel-time matrix / grid**, later
   **detailed itineraries**. Everything downstream — grids, contouring into isochrones, zonal
   statistics, classification, styling, reports — stays in Python/PyQGIS, reusing what easy-OTP
   already solved.
4. Communicate by **JSON job spec in, CSV/JSON out, progress lines on stdout**. No sockets, no
   embedded server, no JVM inside the QGIS process.

## Consequences

**Good**

- Zero Python dependencies; installs cleanly from the QGIS plugin repository.
- Heap is per run (`-Xmx` per invocation), cancellation is `kill(pid)`, an R5 OOM kills the child
  and not QGIS — all of which matter, because the existing r5r pipeline really did OOM at 12 GB
  on Warszawa (primer §6).
- No second repository, no Gradle, no release pipeline for a jar; the Java is source in-tree.

**Bad / accepted risks**

- We own Java code against an API whose upstream README explicitly refuses to keep it stable.
  Mitigated by pinning the R5 version and keeping the runner tiny.
- Needs a **JDK** (~180 MB) rather than a JRE (~45 MB), unless a compiled artefact is shipped.
- Single-file source launcher = **one compilation unit** through Java 21 (multi-file source
  programs are Java 22+). If the runner outgrows one file, it needs a real build — at which point
  reconsider a small companion repo (MIT, like `easy-GTFS-RT`) publishing a jar.
- The person maintaining this now maintains a little Java. That is the whole cost of the decision
  and the reason it is Proposed rather than Accepted.

## Alternatives considered

- **`r5r`** — rejected: requires R.
- **`r5py` as a plugin dependency** — rejected: 16 packages, several compiled.
- **JPype only, with our own Python bindings** (one compiled dep, no Java to write) — **kept as
  documented plan B.** Rejected as the default because an in-process JVM means a fixed heap for
  the lifetime of the QGIS session, no clean cancel, and R5 crashes taking QGIS with them; and
  because bootstrapping a *compiled* wheel into QGIS's interpreter is far more fragile than the
  pure-Python `openpyxl` trick easy-OTP uses today.
- **R5's `PointToPointRouterServer`** (zero Java written, HTTP like easy-OTP) — rejected: it is a
  debug server with no matrix/accessibility endpoint, so it gives up exactly the capability R5 is
  chosen for.
- **Fork `r5r`'s `java-r5rcore` and add a CLI** — rejected: ~250 KB of R-shaped Java
  (`RDataFrame`, JRI) whose Gradle build shells out to R.

## Reversal condition

Plan B (JPype) stays documented. Flip to it only if the runner cannot stay within one compilation
unit *and* a real build pipeline is judged worse than an in-process JVM. Nothing outside
`easy_r5/core/`'s transport layer depends on which of the two is used.
