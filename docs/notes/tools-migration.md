# Migrating the R5-based tools out of easy-OTP

Inventory and plan for moving the r5r/R5 research tooling from `GISBoost/easy-OTP` into this
repo, so that easy-OTP is purely the OTP world and Easy-R5 owns everything R5. Decision recorded
in [ADR-0003](../adr/0003-migrate-r5-tools.md).

## What moves

Counts are git-**tracked** files as of 2026-09-02 (generated data — `.osm.pbf`, GTFS zips,
`network.dat`, rasters, logs — is gitignored and simply does not travel).

| Folder in easy-OTP | Tracked files | What it is | Uses R5? |
|---|---|---|---|
| `tools/accessibility_lodz/` | 49 | Łódź pilot: service accessibility vs. income, then students vs. universities (P50/P85 methods A/C). Source of truth for Łódź. | yes — r5r `accessibility()` |
| `tools/accessibility_cities/` | 81 | Same pipeline generalised to Warszawa, Kraków, Gdańsk, Poznań, Szczecin (+ GZM, Kielce) | yes — r5r `accessibility()` |
| `tools/isochrones_lodz/` | 15 | Isochrone sweeps feeding the `mapy-analizy/izochrony-transport` web map, all 6 cities, static + rt variants | yes — r5r `isochrone()` |
| `tools/ses_income_lodz/` | 16 | Proxy income index per census tract; **input** to the two accessibility studies, no R5 of its own | no, but only these consumers |

**Decided (2026-09-02): all four move**, plus the workflow. After the first three leave, nothing
in easy-OTP consumes `ses_income_lodz`, so leaving it behind would orphan it.

The five R scripts that actually call r5r:

```
accessibility_cities/run_accessibility.R
accessibility_lodz/run_accessibility.R
accessibility_lodz/run_accessibility_hex.R
accessibility_lodz/run_accessibility_students_{A,C_p85,P50,STATIC}.R
isochrones_lodz/compute_isochrones{,_city}.R
isochrones_lodz/dry_run_isochrone{,_city}.R
isochrones_lodz/verify_departure_date.R
```

Plus CI: **`.github/workflows/isochrones-cities.yml`** ("isochrones — compute city isochrones
(r5r)", `workflow_dispatch` only) moves with `isochrones_lodz/`.

## What stays in easy-OTP

`family_a_reconstruction/`, `transit_charts/`, `chart_lab/`, `analysis/`, `rt_diagnose/`,
`network/`, `i18n/`, `lines-diagram/`, `rt-lodz-feed-test/` — all OTP/GTFS-RT world, no R5.
`network/` is a guide to preparing a custom `.osm.pbf`; it is engine-agnostic and useful to both,
so **cross-link it rather than copy it**.

## Cross-references that break

Grep found exactly three places outside the moved folders that name them — a clean boundary:

1. `tools/README.md` — the folder table (drop 4 rows, add a "moved to Easy-R5" pointer line).
2. `tools/ses_income_lodz/README.md` — names its two consumers (only relevant if SES stays).
3. `.github/workflows/isochrones-cities.yml` — moves wholesale.

Also update: easy-OTP's root `README.md` suite table (add an `Easy-R5` row next to `easy-GTFS-RT`
and `gtfs-dashboard`), and prune the now-dead `tools/isochrones_lodz/*` entries from easy-OTP's
`.gitignore` while adding them here.

## How to move it

**Default — plain copy (recommended).** History for these folders stays reachable in
`GISBoost/easy-OTP`, the narrative history that matters is already inside `RESEARCH_LOG.md` /
`HANDOFF.md` / `MULTI_CITY_ANALYSIS.md`, and this costs one commit:

```
# in easy-R5
cp -r ../easy-OTP/tools/{accessibility_lodz,accessibility_cities,isochrones_lodz,ses_income_lodz} tools/
cp ../easy-OTP/.github/workflows/isochrones-cities.yml .github/workflows/
# commit: "chore(tools): import r5r accessibility/isochrone tooling from easy-OTP
#          (history: github.com/GISBoost/easy-OTP before <sha>)"
```

**If commit history must travel — stock git, no `git-filter-repo` needed:**

```
# in easy-OTP, once per folder
git subtree split --prefix=tools/accessibility_lodz -b split/accessibility_lodz

# in easy-R5
git remote add otp ../easy-OTP
git fetch otp split/accessibility_lodz
git subtree add --prefix=tools/accessibility_lodz otp split/accessibility_lodz
```

Repeat per folder, then `git remote remove otp`. Do this **before** the first real Easy-R5 commits
so the import sits at the base of the history.

**Then, in easy-OTP, as a separate PR/commit:** delete the four folders and the workflow, update
the two READMEs and `.gitignore`, and add the pointer line. Deleting is what makes the migration
real — two live copies of `run_accessibility.R` is the failure mode to avoid.

## The R question

Easy-R5's plugin rule is **ZERO R**, same as easy-OTP. That rule governs `easy_r5/`, not
`tools/` — exactly as `tools/` in easy-OTP is exempt from the no-`pip install` rule. The migrated
scripts keep running under r5r as they do today; nothing is rewritten as part of the move.

The interesting medium-term move is the reverse one: **once Easy-R5's own R5 runner works, port
`run_accessibility.R` and `compute_isochrones_city.R` onto it.** That deletes the R dependency
from the research pipeline, and it is the best possible dogfooding — those scripts encode real
parameters (07:00 departure, 120-minute window, 90-minute cap, step decay, cutoffs 15/30/45/60,
500 m hex origins, per-city grid overrides) and a real cost profile (Warszawa's OOM, GZM's size)
that the plugin has to survive anyway. Treat "reproduce the Łódź result through the plugin" as an
acceptance test, not a nice-to-have.
