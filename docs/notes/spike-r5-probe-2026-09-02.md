# Spike: driving R5 as a subprocess — measured, 2026-09-02

Purpose: settle ADR-0001 and open questions 5–9 by running R5 rather than reading about it.
Everything below is a measurement or a stack trace from this machine, not documentation.

**Verdict: ADR-0001 works.** A one-file Java program, compiled by the JDK's single-file source
launcher against the stock R5 jar, loaded a real 106 MB network and computed one-to-many travel
times in ~3 seconds wall clock including compilation.

## Setup

| | |
|---|---|
| Machine | Windows 10, Temurin **25.0.1** (JDK, `javac` present) |
| R5 jar | `r5-v7.5-1-gf3631e9-all.jar` (61.5 MB) — already on disk in r5r's cache |
| Network | `tools/accessibility_cities/gdansk/network.dat`, 106 MB, built by r5r 2.4.0 / R5 7.5.1, format `nv4` |
| Data | 1389 hex origins, 956 service destinations, both from the SES study |
| Request | 07:00, 120-minute window, WALK access/egress, all transit modes, cap 90 min |
| Probe source | [`../reference/probe/Probe.java`](../reference/probe/Probe.java), [`Probe3.java`](../reference/probe/Probe3.java) |

Run as:

```
java -Xmx8g -cp <r5-all.jar> Probe.java <network.dat> <origins.csv> <destinations.csv> 2026-08-25
```

## Results

### Architecture (ADR-0001)

- **Single-file source launcher works** with a 61.5 MB classpath jar. Total wall clock 2962 ms,
  of which 2168 ms was inside the JVM → **compilation costs ~0.8 s**. Pre-compiling with `javac`
  at setup removes even that.
- **Java 25 runs R5 7.5.1** fine. The only complaint is `WARNING: sun.misc.Unsafe::arrayBaseOffset
  has been called by com.esotericsoftware.kryo.unsafe.UnsafeUtil`, i.e. Kryo uses an API slated
  for removal. Reason to pin Temurin 21 *and* always invoke the recorded binary rather than
  whatever `java` is on PATH.

### Costs

| Step | Time |
|---|---|
| `KryoNetworkSerializer.read()` on 106 MB | **1179 ms** |
| First origin (includes linking the 956-point set + building `EgressCostTable` for 1619 stops) | **914 ms** |
| Second origin (linkage cached) | **39 ms** |
| 200 origins, one process, shared point set | 3233 ms → **16.2 ms/origin** |
| Extrapolated: 1389 origins × 956 destinations | **~22 s** |

Design consequences: batch many origins per process; build the `FreeFormPointSet` **once** per
process and reuse it; process startup (~1.2 s) is cheap enough that chunking for memory safety
costs almost nothing.

### Percentiles (open questions 5 and 6)

- `AnalysisWorkerTask.MAX_PERCENTILES` = **5**.
- `validatePercentiles()` with six values → `IllegalArgumentException: Maximum number of
  percentiles allowed is 5`. So the limit is real; validate in Python before spawning Java.
- Five percentiles in one request works and returns a `[5][956]` int array.

### The per-departure-minute distribution — **available** (open question 5)

`FastRaptorWorker` logs `Performing 120 total iterations (1 per minute); boarding MONTE_CARLO;
frequencies false` for a 120-minute window: R5 already routes once per departure minute, and
percentiles are a reduction over that.

With `task.recordTravelTimeHistograms = true`, `TravelTimeResult.getHistogram(target)` returns
an **`int[120]`** — how many departure minutes produced each travel time in minutes. Real output
for one destination (P50 = 79 min):

```
[61]=1 [62]=2 [63]=3 [64]=3 … [87]=4 [88]=3 [89]=3     (sums to 98 of 120 departure minutes)
```

The 22 missing samples are departure minutes from which the destination was not reachable within
the cap. That is exactly the shape needed for easy-OTP's "for how many minutes of the window is
this within T?" metric: `sum(hist[0..T])`. **Scheduled for v0.2**, with its own name — it is not
numerically identical to easy-OTP's OTP-based metric and must not pretend to be.

### Native accessibility — **not usable standalone**

`recordAccessibility = true` with `cutoffsMinutes` + `StepDecayFunction` fails:

```
NullPointerException: Cannot read the array length because "task.destinationPointSetKeys" is null
```

R5's built-in accessibility is wired to Conveyal's object-storage layer for opportunity grids.
r5r reaches the same conclusion — it computes accessibility in its own Java code. **Easy-R5
computes accessibility in Python from the travel-time matrix.** `OneOriginResult` exposes
`travelTimes`, `accessibility`, `paths`, `density`; v0.1 uses only the first.

### Other observations

- Travel times are **minutes** (int); unreachable is `Integer.MAX_VALUE` (2147483647).
- All 956 destination points linked to the street network; partial linking is a real error case
  to handle, and R5 reports it (`Linked 956 of 956 PointSet points to streets for mode WALK`).
- The Gdańsk feed has **no `calendar.txt`**, only `calendar_dates.txt` with one `service_id` per
  day. r5r's "less than 20% of transit services running on the selected date" warning is a false
  alarm for this very common Polish feed shape — count *trips active on the date* instead.

## What the probe does not answer

- Whether `TravelTimeComputer` itself calls `validatePercentiles()` (the probe called it
  explicitly). Irrelevant in practice: Python validates first.
- Whether vanilla Conveyal `r5-v7.6-all.jar` behaves identically to the r5r-shipped 7.5.1 jar
  used here, and whether `saveShapes` can be set from a build-config JSON instead of needing
  r5py's fork. Re-run this probe against 7.6 in M1.
- Network **build** cost (this used a network r5r had already built). Measure in M2.
