# Claude Code prompt — Easy-R5 **M2**: network building + date validation

> Paste below the line into Claude Code, in the `easy-R5` repo, clean tree. English in code,
> Polish in chat. Implement **M2 only** — no travel-time matrix yet (M3). No new branch.
> M1 must be merged and working first.

---

## ✅ Implementation status (2026-09-03)

**Implemented and committed on `main`** (`d5b7f2d`..`52847ac`). `EasyR5Runner`
command `build`, `core/gtfs_calendar.compute_service_days` (pure stdlib, all real
Polish feed shapes), `core/network_cache` (key = sha256 of input bytes + R5
version; sentinel = `network.dat` + `network.json`), `BuildNetwork`. Unit tests
for the cache key and `service_days`.

Agent-verified with R5 7.6: Gdańsk builds in ~27 s → 1619 stops / 573 trip
patterns / `Europe/Warsaw`; the freshly built `nv5` network reloads via `info`;
`service_days["2026-08-25"] > 0`, out of span = 0.

**Still needs Michał:** `BuildNetwork` on a large PBF (wall time, peak RAM);
cache hit on re-run; no orphaned `java.exe` after cancelling a build; a foreign
`network.dat` → `NETWORK_VERSION_MISMATCH`.

Full picture: [`../handoffs/2026-09-03_M3-M5-implementation.md`](../handoffs/2026-09-03_M3-M5-implementation.md).

## Context to load first

- `docs/prd/PR_easy-R5_v01.md` — **§3.2 `command: "build"`**, **§4.3 `BuildNetwork`**,
  **§5.3** (date validation as a hard gate), **§6 M2**.
- `docs/notes/r5-engine-primer.md` §1 and §6.
- `docs/reference/probe/Probe.java` — how the network is loaded today.
- `tools/isochrones_lodz/verify_departure_date.R` — **read the whole header and body.** It is the
  reference implementation of "is this date served by this feed", including the trap that
  `weekdays()` is locale-dependent (returns `piatek` under a Polish locale) so you must index a
  fixed English weekday table instead of comparing names.
- `tools/accessibility_cities/HOWTO_MANUAL.md` step 3 — how these networks were built by r5r.
- `../easy-OTP/easy_otp/core/otp_server.py` — graph-cache-by-input-hash pattern.

## Why this milestone exists

Two reasons, one obvious and one that already cost this project a published wrong result.

The obvious one: every analysis needs a `network.dat`, building it is slow, and rebuilding it
when nothing changed is pure waste — hence a cache keyed by input hashes **plus the R5 version**
(a network written by another R5 refuses to load).

The one that matters more: **R5 does not error when the requested departure date has no active
service — it silently returns walk-only results for every origin and hour.** That shipped for GZM
in August 2026 (feed active only on 2026-08-28, date hardcoded to 2026-08-24) and stood published
for a week. The defence starts here: the network summary must carry a per-date count of active
trips, so that M3 can refuse to run on a dead date.

## Goal

`BuildNetwork` produces a cached `network.dat` plus a `network.json` summary that includes
`service_days`, and reports it to the user.

## What to build

### Runner: `command: "build"`
Inputs `osm`, `gtfs[]`, `out_network`, `out_summary` (PRD §3.2). Build the `TransportNetwork`
(follow r5py's sequence documented in `docs/notes/r5-engine-primer.md` §3: OSM → `StreetLayer`
→ `TransitLayer` per feed → `TransferFinder` → `KryoNetworkSerializer.write`), then write
`network.json`.

`service_days`: for every date in the feed's span (cap 90 days), **the number of trips active on
that date**, honouring `calendar.txt` weekday flags, `start_date`/`end_date`, and
`calendar_dates.txt` exceptions (type 1 adds, type 2 removes). Not a count of `service_id`s, and
not a percentage — Polish feeds routinely ship one `service_id` per day (Gdańsk has no
`calendar.txt` at all), which is exactly what makes share-based heuristics useless.

Emit `PROGRESS` during the build; it takes minutes on a large PBF.

### Python: `core/network_cache.py` + `algorithms/build_network.py`
Cache directory keyed by `sha256(osm) + sha256(each gtfs) + r5_version`. On hit, skip the build
and load the existing `network.json`. `FORCE_REBUILD` (advanced) bypasses it. Surface the summary
in the log: feeds, stops, trip patterns, timezone, bounds, and the served date range with the
first/last day that actually has trips.

## Acceptance criteria

- Gdańsk (`tools/accessibility_cities/gdansk/gdansk.osm.pbf` + `gdansk_gtfs.zip`) builds; the
  summary reports 1619 stops / 573 trip patterns / `Europe/Warsaw` / feed `gdansk_gtfs`
  (the numbers r5r produced for the same inputs).
- `service_days["2026-08-25"] > 0`; a date outside the feed span is `0`.
- Re-running with unchanged inputs does **not** rebuild (log says so, and it returns fast).
- Changing the pinned R5 version invalidates the cache.
- A corrupt/foreign `network.dat` yields `NETWORK_VERSION_MISMATCH` with a human message, not a
  Kryo stack trace.
- Unit tests: cache key stability, `service_days` computation against a small synthetic GTFS with
  **both** `calendar.txt` and `calendar_dates.txt`, including a type-2 removal.

## What you must NOT do

- Do not compute travel times, accessibility or isochrones.
- Do not add a second Java file or any dependency.
- Do not "helpfully" pick a departure date for the user — M2 only reports what is served.

## Report to Michał when done

1. Build Gdańsk from scratch; note wall-clock time and peak memory.
2. Run it again unchanged — confirm it is a cache hit.
3. Build his own city; confirm the served date range matches what he expects from the feed.
4. Confirm no orphaned `java.exe` after cancelling a build midway.
