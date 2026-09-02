# Easy-R5

A QGIS processing plugin for transit accessibility analysis on the
[**Conveyal R5**](https://github.com/conveyal/r5) routing engine — travel-time matrices,
cumulative-opportunity accessibility and isochrones over a departure-time window, computed inside
QGIS with no R, no conda and no Docker.

> **Status: pre-alpha.** There is no plugin code yet — this repository currently holds the design
> notes, the architecture decisions and the R5 research tooling the plugin is being built from.
> Start at [`CLAUDE.md`](CLAUDE.md) and [`docs/adr/0001-r5-binding.md`](docs/adr/0001-r5-binding.md).

Sibling project: [**easy-OTP**](https://github.com/GISBoost/easy-OTP), the same idea on
OpenTripPlanner 1.5.

| | easy-OTP | Easy-R5 |
|---|---|---|
| Engine | OpenTripPlanner 1.5 (Java 8) | Conveyal R5 (Java 21) |
| Best at | per-minute travel-time surfaces, detailed itineraries, **live GTFS-RT** | one-to-many / many-to-many travel times over a **departure-time window**, cumulative accessibility, scenarios |
| Realtime | yes — records GTFS-RT and reconstructs realized feeds | no — R5 cannot read GTFS-RT; it consumes the realized static feeds easy-OTP produces |

The two are designed to share data: the same OSM extracts, GTFS feeds, hex grids and realized
P50/P85 feeds work in both.

---

## What it will do

- **Travel-time matrix** — N origins × M destinations, with percentiles across a departure window.
- **Accessibility** — cumulative opportunities within cutoffs, with step / logistic / exponential
  decay.
- **Isochrones** — contoured in QGIS from an R5 travel-time grid.
- **Scenario comparison** — two runs, one delta layer.
- **Setup that is actually one click** — the plugin downloads the pinned Temurin JDK and R5 jar;
  nothing else to install.

See [`docs/notes/product-scope.md`](docs/notes/product-scope.md) for the full sketch and
[`docs/notes/r5-vs-otp.md`](docs/notes/r5-vs-otp.md) for what is deliberately *not* here.

## Repository layout

| Path | What it is |
|---|---|
| `easy_r5/` | the QGIS plugin *(not created yet)* |
| `easy_r5/java/` | the one Java source file that drives R5 *(not created yet)* |
| [`CONTEXT.md`](CONTEXT.md) | glossary — the words this project uses |
| [`docs/adr/`](docs/adr/) | architecture decisions |
| [`docs/notes/`](docs/notes/) | engine primer, binding comparison, scope, migration plan, open questions |
| [`tools/`](tools/README.md) | standalone R5 research tooling — accessibility and isochrone studies for 7 Polish cities, migrated from easy-OTP ([ADR-0003](docs/adr/0003-migrate-r5-tools.md)). Gdańsk is the plugin's reference dataset. |

## Requirements (planned)

| Requirement | Version | How to get it |
|---|---|---|
| QGIS | 3.22 LTR or newer | qgis.org — the plugin uses the bundled Python and GDAL |
| Java | **21** (Temurin) | the plugin downloads it |
| R5 | **pinned** — see [ADR-0002](docs/adr/0002-pinned-versions.md) | the plugin downloads it |
| OSM extract | any `.osm.pbf` covering the study area | the plugin can download it |
| GTFS feed(s) | any valid feed | the plugin can download it |

## Licence

GPL-3.0-or-later. R5 itself is MIT (© Conveyal LLC) and is downloaded, not vendored.

## Credits

R5 is developed by [Conveyal](https://www.conveyal.com/). This plugin is not affiliated with
Conveyal. The existing R bindings [`r5r`](https://github.com/ipeaGIT/r5r) (IPEA) and
[`r5py`](https://github.com/r5py/r5py) are not dependencies here, but `r5py`'s source was the
reference for how R5's Java API is used — credit where it is due.
