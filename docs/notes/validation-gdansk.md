# Validation: `RunAccessibility` vs r5r, Gdańsk

**Result: an exact match.** With r5r's departure date reconstructed as
**2026-08-24**, Easy-R5's `RunAccessibility` reproduces every one of the 27 780
rows of `tools/accessibility_cities/gdansk/gdansk_service_accessibility.csv`
**identically** — RMSE 0.00, max absolute difference 0 — even though Easy-R5 runs
R5 7.6 and r5r ran R5 7.5.1.

This is the milestone's real deliverable (PRD M4): a fast matrix that produces
*different* accessibility numbers is a broken plugin. It does not.

## What was compared

| | r5r (ground truth) | Easy-R5 |
|---|---|---|
| engine | R5 7.5.1 via r5r 2.4.0 | R5 7.6 via `EasyR5Runner` |
| network | `nv4`, built 2026-08-23 | `nv5`, freshly built from the same `gdansk.osm.pbf` + `gdansk_gtfs.zip` |
| origins / destinations | `gdansk_hex_origins.csv` (1389) / `gdansk_service_destinations.csv` (956) | same |
| opportunities | `opp0..opp3`, `total` | same |
| departure | 07:00, 120-min window | same |
| max trip duration | 90 min | 90 min |
| decay / cutoffs | `step`, 15/30/45/60 | `STEP`, 15/30/45/60 |
| percentile | 50 | 50 |
| accessibility computed by | r5r's own Java (`recordAccessibility` is unusable standalone — spike 2026-09-02) | `core/accessibility.py`, in Python over the matrix CSV |

Output shape is identical: `id,opportunity,percentile,cutoff,accessibility`,
27 780 rows (1389 origins × 5 opportunity columns × 4 cutoffs), same key set.

## The departure date

r5r's `run_accessibility.R` takes the departure date as a command-line argument;
it is **not** recorded in the repo (the run log shows only a build timestamp of
2026-08-23 and the spurious "less than 20% of transit services running" warning —
a false alarm for Gdańsk's `calendar_dates`-only feed, not evidence of a bad
date). The feed serves 2026-08-22 … 2026-09-05.

Reconstructed by running the matrix on each candidate and diffing:

| departure date | rows exactly equal | mean Δ | RMSE | max \|Δ\| |
|---|---|---|---|---|
| 2026-08-22 (Sat) | 56.6 % | −3.38 | 13.76 | 266 |
| **2026-08-24 (Mon)** | **100.0 %** | **0.000** | **0.00** | **0** |
| 2026-08-25 (Mon) | 97.5 % | −0.03 | 1.37 | 117 |

2026-08-24 it is — the Monday that the SES study's 2026-08-22 Saturday recording
was "patched forward" to. Saturday service is visibly sparser; the neighbouring
Monday (08-25) is close but not identical (a handful of origins near routes whose
schedule differs day-to-day).

## The step-decay boundary

The one code decision that mattered: **R5's `StepDecayFunction` is a strict
`travelTime < cutoff`**, not `<=`. Verified from the 7.6 bytecode:

```
computeWeight(int cutoff, int travelTime):
    if (travelTime >= cutoff) return 0.0;
    return 1.0;
```

Travel times in the matrix are whole minutes and cutoffs are round numbers, so a
destination sitting *exactly* on a cutoff is common. With `<=`, Easy-R5 over-counted
with a bias that grew with the cutoff (mean Δ +0.4 at 15 min → +4.7 at 60 min,
only 30 % of 60-min rows exact). Switching to strict `<` to match R5 took the
2026-08-24 run to an exact match. `core/accessibility.py` and its unit test both
encode `<`.

## R5 7.5.1 vs 7.6

No effect on this network / date / parameter set: the 2026-08-24 match is exact.
Version differences remain a legitimate source of divergence for other inputs and
are not claimed to be zero in general — only measured as zero here.

## Reproducing

```
# 1. build the network (once)
EasyR5Runner  build.json      # osm + gtfs -> network.dat (nv5)

# 2. QGIS: Processing → Easy-R5 → Run accessibility
#    NETWORK      = the built network.dat
#    ORIGINS      = gdansk_hex_origins.csv  (id,lon,lat)   ORIGIN_ID_FIELD = id
#    DESTINATIONS = gdansk_service_destinations.csv         DEST_ID_FIELD  = id
#    OPPORTUNITY_FIELDS = opp0, opp1, opp2, opp3, total
#    DATE = 2026-08-24  DEPARTURE_TIME = 07:00  TIME_WINDOW = 120
#    MAX_TRIP_DURATION = 90  CUTOFFS = 15,30,45,60  DECAY = STEP  PERCENTILES = 50
#
# 3. diff OUTPUT_CSV against tools/accessibility_cities/gdansk/gdansk_service_accessibility.csv
```

Matrix run time on the reference machine: ~1 min 45 s for 1389 × 956 (this
includes the per-origin walk-only companion pass; the routing r5r reports for the
same job is ~14 s of its ~30 s total — Easy-R5 trades wall time for the
independent walk-only guard).
