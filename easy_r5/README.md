# Easy-R5

A QGIS Processing plugin for transit accessibility analysis on the
[**Conveyal R5**](https://github.com/conveyal/r5) routing engine — travel-time
matrices, cumulative-opportunity accessibility and isochrones over a
departure-time window, computed inside QGIS with no R, no conda and no Docker.

**Status: 0.1.0, experimental.**

## Quick start

1. Install this plugin (Plugins → Manage and Install → Install from ZIP), enable it.
2. *Setup → Download R5 engine and Java 21* — one-time, ~200 MB (Temurin 21 JDK +
   the pinned `r5-v7.6-all.jar`, SHA-256 verified). No admin rights.
3. Supply an OSM extract (`.osm.pbf`) and GTFS feed(s) (`.zip`) for your area.
4. *Setup → Build R5 network*, then the *Analysis* algorithms.

## Dependencies

- **QGIS 3.22 LTR or newer** — uses the bundled Python and GDAL only.
- **Java 21 (Temurin)** and **R5 7.6** — fetched by *Download R5 engine and Java 21*.
- **openpyxl** (optional) — only *Prepare population layer* / *Population overlay*
  need it. The pure-Python wheel is fetched from PyPI (SHA-256 verified, no `pip`)
  on first load; if that fails, a one-line manual-install hint is shown. Every
  other algorithm runs without it.

## Licence

GPL-3.0-or-later (see `LICENSE`). R5 itself is MIT (© Conveyal LLC) and is
downloaded at setup, not bundled.

Full documentation, ADRs and the validation notes:
https://github.com/GISBoost/easy-R5
