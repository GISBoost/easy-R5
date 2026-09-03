# Claude Code prompt — Easy-R5 **M4**: accessibility + reproducing the r5r result

> Paste below the line into Claude Code, in the `easy-R5` repo, clean tree. English in code,
> Polish in chat. Implement **M4 only** — isochrones are M5. No new branch. M3 must be working.

---

## ✅ Implementation status (2026-09-03)

**Implemented, committed on `main`** (`f5a78d7`..`d5554a5`). `core/accessibility`
(**STEP is a strict `travelTime < cutoff`** — verified from R5's
`StepDecayFunction` bytecode), `RunAccessibility`, the shared `MatrixBase` mixin,
`docs/notes/validation-gdansk.md`. Unit tests for the decay boundary, unreachable
→ 0, multiple opportunity columns, an origin with nothing reachable.

**The milestone's real deliverable is done and is an exact match:** with r5r's
unrecorded departure date reconstructed as **2026-08-24**, Easy-R5 reproduces
**every one of the 27 780 rows** of `gdansk_service_accessibility.csv`
identically (RMSE 0.00), despite R5 7.6 vs r5r's 7.5.1. The date-reconstruction
table and the strict-`<` finding are written up in `validation-gdansk.md`.

**Still needs Michał:** the Gdańsk accessibility map next to the one in
`tools/accessibility_cities/out/` — same spatial pattern? (numbers already exact.)

Full picture: [`../handoffs/2026-09-03_M3-M5-implementation.md`](../handoffs/2026-09-03_M3-M5-implementation.md).

## Context to load first

- `docs/prd/PR_easy-R5_v01.md` — **§4.5**, **§5.2** (method fields in the output), **§6 M4**.
- `docs/notes/spike-r5-probe-2026-09-02.md` §"Native accessibility" — **R5 cannot compute this
  for us**: `recordAccessibility = true` dies with
  `NullPointerException: task.destinationPointSetKeys is null`, because R5 pulls opportunity
  grids through Conveyal's object storage. Accessibility is computed in Python from the matrix.
  Do not spend an afternoon rediscovering this.
- `tools/accessibility_cities/run_accessibility.R` — the reference implementation, 40 lines.
  Every parameter in it is the parameter this milestone must match.
- `tools/accessibility_cities/gdansk/` — the reference dataset: `gdansk_hex_origins.csv`
  (1389), `gdansk_service_destinations.csv` (956, with `opp0..opp3,total`),
  `gdansk_service_destinations_slugmap.json`, and r5r's own output
  `gdansk_service_accessibility.csv`.
- `tools/accessibility_lodz/COLUMNS.md` — what each output column means. Read it before naming
  yours; "opportunity count" and "population covered" are not the same thing and the study
  documents the confusion.

## Why this milestone exists

Cumulative-opportunity accessibility is what every one of these studies actually computed, and
what a planner actually asks for ("how many schools within 30 minutes"). It is also the
milestone that proves the plugin is *correct*: r5r already produced an answer for Gdańsk with
known parameters, so we have ground truth. A matrix that runs fast but produces different
accessibility numbers is a broken plugin, and only this comparison will show it.

## Goal

`RunAccessibility` producing per-origin accessibility for each opportunity column, cutoff and
percentile — plus a documented comparison against r5r's Gdańsk output.

## What to build

### `core/accessibility.py`
Pure function over the matrix: for each origin, opportunity column, percentile and cutoff, sum
opportunities weighted by the decay function.

- `STEP` — weight 1 below the cutoff, 0 above. This is what all the studies used
  (`decay_function = "step"`, `cutoffs = c(15, 30, 45, 60)`).
- `LOGISTIC`, `EXPONENTIAL` — implement, but keep `STEP` the default.

No pandas, no numpy dependency assumptions — QGIS 3.22 may have neither. Plain Python over the
CSV is fast enough at this size; if it is not, say so with a measurement rather than adding a
dependency.

### `algorithms/run_accessibility.py`
PRD §4.5 parameters. `MAX_WALK_TIME` defaults to `max(CUTOFFS)` for `STEP` (lossless, and the
big speed lever) but to `MAX_TRIP_DURATION` for the decay functions with a tail beyond the
cutoff — getting this backwards silently truncates the tail.

Outputs: ORIGINS copy with `acc_<opportunity>_p<percentile>_c<cutoff>` fields, plus the method
fields from PRD §5.2 (`r5_version`, `network_hash`, `run_date`, `departure_time`, `time_window`,
`percentile`, `modes`, `decay`). Long CSV `id,opportunity,percentile,cutoff,accessibility` —
**the same shape r5r emits**, so the comparison below is a plain diff.

### The comparison (this is the milestone's real deliverable)
Reproduce r5r's Gdańsk run: 07:00, 120-min window, 90-min cap, step decay, cutoffs 15/30/45/60,
`WALK`+`TRANSIT`, the two CSVs above. Then compare to `gdansk_service_accessibility.csv` and
write up the result in `docs/notes/validation-gdansk.md`:

- identical column layout and row count;
- distribution of differences per cutoff (max, mean, share of exactly-equal rows);
- an explanation of every systematic difference you find.

Known sources of legitimate difference, to check before suspecting a bug: **the departure date
r5r used is not recorded anywhere in the repo** and must be reconstructed (the run log only shows
a build timestamp and a spurious "<20% of services" warning — that warning is a false alarm for
Gdańsk's `calendar_dates`-only feed, not evidence of a bad date); Monte Carlo draws;
R5 7.5.1 (r5r) vs the pinned 7.6; and r5r's own default walk speed and `max_walk_time`.

**Document the differences, do not hide them and do not tune parameters until the numbers match.**
A tuned match proves nothing; an explained difference proves the pipeline is understood.

## Acceptance criteria

- `RunAccessibility` runs end-to-end on Gdańsk and writes both outputs.
- `docs/notes/validation-gdansk.md` exists and answers: same shape? how different? why?
- Unit tests for `accessibility.py`: step decay at exactly the cutoff boundary, an unreachable
  pair contributing 0, multiple opportunity columns, and an origin with no reachable
  destinations (must be 0, not NULL, not missing).
- The output layer carries every method field; a run with a different percentile produces a
  visibly different value in that field.

## What you must NOT do

- Do not try to make R5 compute accessibility natively — it cannot, and the spike proved it.
- Do not add numpy/pandas/geopandas as a hard requirement.
- Do not "fix" a mismatch with r5r by adjusting parameters until it disappears.

## Report to Michał when done

1. The Gdańsk accessibility map next to the one in `tools/accessibility_cities/out/` — same
   spatial pattern?
2. The summary table from `validation-gdansk.md`.
3. Runtime versus r5r's own (~7 s for the routing part on this dataset).
