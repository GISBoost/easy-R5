# Claude Code prompt — Easy-R5 **M3**: travel-time matrix (flagship algorithm)

> Paste below the line into Claude Code, in the `easy-R5` repo, clean tree. English in code,
> Polish in chat. Implement **M3 only** — accessibility is M4, isochrones M5. No new branch.
> M1 and M2 must be working.

---

## Context to load first

- `docs/prd/PR_easy-R5_v01.md` — **§2** and **§2.1** (measured facts and the three production
  lessons), **§3.2 `command: "matrix"`** incl. the verified `RegionalTask` recipe and the
  `FreeFormPointSet` binary format, **§3.4** (heap and batching), **§4.4**, **§5** (all nine UX
  rules), **§6 M3**.
- `docs/reference/probe/Probe.java` — **this already does the core of M3.** It builds the task,
  the point set, and calls `TravelTimeComputer`. Port it, do not reinvent it.
- `docs/notes/spike-r5-probe-2026-09-02.md` — the timings your implementation must roughly match.
- `tools/isochrones_lodz/compute_isochrones_city.R` — **read the entire header comment.** It
  carries the batching rationale, the OOM that forced it, and the `max_walk_time` finding.
- `tools/isochrones_lodz/benchmark_summary.csv` — measured throughput per city.

## Why this milestone exists

This is the algorithm the plugin exists for. easy-OTP answers one origin-destination pair per HTTP
request; R5 answers one origin against every destination in ~16 ms after a ~900 ms setup cost that
is paid **per point set, not per origin**. Getting the process/batching structure right here is
what makes 1389 × 956 finish in ~22 seconds instead of hours, and every later algorithm is built
on this one.

## Goal

`RunTravelTimeMatrix`: point layers in, travel-time CSV (and optional layer) out, with progress,
cancellation, sane memory behaviour and the two anti-walk-only safeguards.

## What to build

### Runner: `command: "matrix"`
Per PRD §3.2. Non-negotiable details, all of them load-bearing:

- **Build the `FreeFormPointSet` once per process** and reuse it across origins. The first origin
  pays ~900 ms (point linking + `EgressCostTable` for every stop); subsequent ones ~16–40 ms.
  Rebuilding it per origin would make the plugin ~25× slower and nobody would notice from the
  code alone.
- **Always set `r.maxWalkTime`.** Unbounded, R5 searches an unlimited walking radius for every
  access, egress and transfer. Capping at the trip budget is provably lossless and measured at
  **10.2× faster** on GZM with **0.0000%** result difference. Python passes the value; the runner
  never leaves it unset.
- Honour `origin_range` so Python can batch; stream `PROGRESS done total`.
- Count and report `RESULT transit_used_pairs=<n>` — pairs whose transit travel time beats the
  walk-only time. This is the walk-only detector (PRD §5.8).
- Write only reachable pairs unless `write_unreachable`; `Integer.MAX_VALUE` never reaches the CSV.

### Python
`core/points.py` (layer → CSV, reproject to EPSG:4326, stable ids, reject non-point/empty
geometry), `core/matrix.py` (merge batch CSVs, build outputs), `algorithms/run_travel_time_matrix.py`
(PRD §4.4 parameter table exactly).

Gates, in this order, **before** any Java is spawned:
1. percentiles: ≤5, ascending, 1–99 (R5 throws otherwise — verified);
2. date: `service_days[DATE] == 0` → **refuse to start**, naming the three nearest served days;
   overridable only via the advanced `ALLOW_NO_SERVICE`;
3. `MAX_WALK_TIME` empty → set to `MAX_TRIP_DURATION`; lower → log that it is a deliberate
   speed/completeness trade-off.

Then `ESTIMATE_FIRST` (default on): run 15 systematically-spread origins, report measured
s/origin and the extrapolation. Cost scales with **network complexity**, not origin count —
Warszawa's 668 origins cost 2.4–3.4× more each than Gdańsk's 1389 — so never extrapolate from
another city's number.

After the run: if `transit_used_pairs == 0` in a transit mode, **fail** with the walk-only
message. Two independent guards, because a single one already failed once in production.

OOM: exit code ≠ 0 or `OutOfMemoryError` in stderr → the PRD §3.4 message with the current heap
and batch size, never a stack trace.

## Acceptance criteria

- Gdańsk 1389 × 956, 07:00 +120 min, P50, cap 90 → completes in **under 2 minutes**, CSV written.
- A known origin matches `Probe.java`'s output to the minute.
- Cancel mid-run: the Java process is gone within ~2 s, no temp files left.
- 6 percentiles → validation error before the JVM starts.
- A dead date blocks the run and suggests served days.
- `ALLOW_NO_SERVICE=True` on a dead date → run completes but **fails** on the walk-only detector.
- Job spec always carries a numeric `max_walk_time_minutes` (unit test).
- Origins layer in EPSG:2180 gives the same result as the same points in EPSG:4326.

## What you must NOT do

- No accessibility computation (M4), no isochrones (M5).
- No threading inside Java — batching processes from Python is the concurrency model.
- Do not lower `MAX_WALK_TIME` below the trip budget as a default "optimisation".
- Do not silently drop unreachable pairs into `0` — they are absent or `NULL`.

## Report to Michał when done

1. Run the Gdańsk matrix; paste the estimate line and the total time.
2. Spot-check three OD pairs against the operator's journey planner.
3. Try a deliberately wrong date and confirm both guards fire.
4. Run something too big for the machine and confirm the OOM message is actionable.
