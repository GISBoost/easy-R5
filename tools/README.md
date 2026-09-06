# tools/ — standalone R5 research tooling, outside the plugin

Everything under `tools/` is **outside the QGIS plugin** — none of it is imported by `easy_r5/`,
none of it ships in the plugin ZIP, and none of it needs to run inside QGIS. It is the research
workshop the plugin is being built from: the accessibility and isochrone studies for Polish
cities that first proved this method on R5, each with its own environment.

The repo-wide rules in `CLAUDE.md` (English in code, `py` not `python`) apply here, but the two
hard plugin constraints do **not**: nothing here runs inside QGIS's interpreter, so `pip install`
is fine, and these scripts still use **R + r5r** as they always have. Porting them onto Easy-R5's
own runner once it works is the plan — see
[`../docs/notes/tools-migration.md`](../docs/notes/tools-migration.md) §"The R question".

> **Migrated from `GISBoost/easy-OTP` on 2026-09-02** (ADR-0003). Commit history for these files
> before that date lives in the easy-OTP repository. Cross-repo references you will find inside
> these documents — `easy_otp/core/xlsx_reader.py`, `easy_otp/algorithms/prepare_student_layer.py`,
> `docs/prd/PR_easy-OTP*.md`, `docs/gis/ludnosc_nsp_2021.xlsx` — all point at
> [easy-OTP](https://github.com/GISBoost/easy-OTP), not at paths in this repo. They are left as
> written: these are research logs, and rewriting their history would make them less trustworthy,
> not more.

## Folders

| Folder | What it is |
|---|---|
| [`accessibility_lodz/`](accessibility_lodz/README.md) | Transit-accessibility pilot for Łódź (r5r/R5): general service accessibility vs. income, then student/university accessibility. Source of truth for Łódź. |
| [`accessibility_cities/`](accessibility_cities/README.md) | The same r5r/R5 pipeline generalized to Warszawa, Kraków, Gdańsk, Poznań, Szczecin (plus GZM and Kielce). **Gdańsk is Easy-R5's reference dataset** — PRD M4 diffs the plugin against `gdansk/gdansk_service_accessibility.csv`. |
| [`isochrones_lodz/`](isochrones_lodz/README.md) | Isochrone sweeps (all 6 cities, scheduled + realized variants) feeding [mapy-analizy/izochrony-transport](https://gisboost.github.io/mapy-analizy/izochrony-transport/). Also the source of the hardest-won performance lessons — read the script headers. |
| [`ses_income_lodz/`](ses_income_lodz/README.md) | Proxy income index per census tract for 6 cities (2023 election results × CBOS income survey, **not** real income) — the SES layer the two accessibility studies join against. |
| [`modal_complementarity_lodz/`](modal_complementarity_lodz/README.md) | *(Parked, not the flagship — see that folder's README.)* How much of Łódź's transit reach depends on the tram vs. the bus vs. the transfer between them, on the plugin's own `RunAccessibility` (not r5r) via the `TRANSIT_SUBMODES` parameter — the first flagship attempt; kept as a working dogfooding example. |
| [`realtime_delay_lodz/`](realtime_delay_lodz/README.md) | Where GTFS-RT delays hurt reachability the most: `RunAccessibility` on the static vs. realized-P50 schedule for the same real day, entirely on Easy-R5's own algorithms (no R/r5r, no Overpass at runtime) — the direction we moved to after `modal_complementarity_lodz`. |

## Read these before writing plugin code

Three files encode failures that cost real time and one of which shipped a wrong result to
production. The PRD (§2.1) summarises them, but the originals have the full reasoning:

- `isochrones_lodz/compute_isochrones_city.R` — header comment: the `max_walk_time` cap
  (10.2× speedup, zero result change), origin batching after Warszawa's OOM, and the GZM
  silent walk-only bug.
- `isochrones_lodz/verify_departure_date.R` — how to validate a departure date against a GTFS
  calendar, including the locale-dependent `weekdays()` trap.
- `isochrones_lodz/benchmark_summary.csv` — measured throughput, r5r vs the easy-OTP plugin.

## Generated data is not versioned

`.osm.pbf`, GTFS `.zip`, `network.dat` and r5r build caches, `.gpkg`, result `.csv`, logs — all
gitignored. Each folder's README/HOWTO says how to regenerate them.
