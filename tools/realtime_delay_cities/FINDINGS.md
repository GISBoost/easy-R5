# Findings — realized-GTFS delay vs. accessibility, 6 cities

Static vs realized-P50 GTFS, 30 min accessibility, 07:00–09:00, per hexagon,
4 destination categories. Łódź from `../realtime_delay_lodz/` (2026-08-21), the
other 5 from this folder (2026-08-24). Population-weighted city means over
comparable hexagons (static baseline > 0).

## 0. Population on the hex grid — dasymetric, not areal (2026-09-10)

The first pass weighted each hexagon by `easyr5:populationoverlay` output, which
is *areal interpolation*: it spreads a census precinct's GUS population at
uniform density across the whole precinct polygon. Inside a city boundary that
puts phantom residents on port land, rail yards, fields and forest — e.g.
Kraków hex #178 got ~4 people from a 287-person precinct that is 2.7 % built,
its hexagon covering only tracks and fields; hex #143 got 0.27 from a 9-person /
1.8 km² precinct.

`dasymetric_pop.py` now redistributes each precinct's population onto the
**OSM building footprint** only (binary dasymetric mapping, Mennis 2003),
mass-preserving, with a uniform-areal fallback for the handful of precincts
that have no residential building. Hexagons whose dasymetric population is
below 0.5 are dropped from `hex_grid` — "nobody lives here, it is not part of a
*population* accessibility study". `siatka` (the full grid outline on the web
map) is kept.

Effect, all 6 cities: precinct population totals preserved to 0.000 %; 10–27 %
of population shifts toward built-up land at 250 m; 20–70 % of hexagons drop
out as empty (Szczecin highest — Międzyodrze, port, Puszcza Bukowa are all
inside the city limits); **< 4 % of population sat in a now-dropped hexagon**
(relocated, not lost). The population-weighted `net_delta` headlines move by
≤ 0.05 and **every conclusion below is unchanged** — the fix removes noise from
the unweighted means and hexagon counts, not signal from the story.

## 1. The transfer-zone hypothesis is **refuted as a general pattern**

Łódź showed a sharp dip in `net_delta` at the **2–3 km ring** (−2.4, an order of
magnitude worse than any other ring) and we asked whether that is a universal
"transfer-dependent belt gets hit hardest" effect.

It is not. `out/HYPOTHESIS.md`: **only Łódź** (both 250 m and 500 m) has a
mid-ring dip (2–3 km ring −2.48 / −2.00 after the dasymetric re-run, still an
order of magnitude below any other ring). In the other 5 cities the worst 1 km
ring is either the very centre (Kraków, 0–1 km) or the outskirts (6–15 km) —
never the 1–4 km belt. 2 confirm / 9 deny, unchanged from the areal pass.

What the 5 cities show instead is a **monotone radial gradient**: `net_delta`
is most favourable in the dense core and declines outward (Poznań 500 m: inner
ring +6.5 → outer rings ≈ −0.7; Warszawa: +8.6 → −0.03). The core is where
realized-vs-static differences help the most, not where they hurt the most —
the opposite of the hypothesis. Łódź's 2–3 km dip looks like a Łódź-specific
network feature (worth its own look), not a transferable law.

## 2. The city-wide sign is a property of the *static schedule*, not of "delays"

| City | 250 m net Δ | 500 m net Δ | all categories same sign? |
|---|--:|--:|:--:|
| **Warszawa** | — | **+3.45** | yes, + |
| **Poznań** | **+2.84** | **+2.64** | yes, + |
| **Szczecin** | **+2.45** | **+2.07** | yes, + |
| **Gdańsk** | +0.16 | −0.02 | no (≈ 0) |
| **Łódź** | −0.30 | +0.14 | no (≈ 0) |
| **Kraków** | **−0.81** | **−0.95** | yes, − |

The sign is stable across category **and** resolution within a city — it is not
MAUP noise (except in Gdańsk and Łódź, the two near-zero cities, where it
naturally flips). Verified for Poznań with a full 5132 × 681 origin–destination
travel-time matrix on both networks (`out/probe_poznan_*.csv`):

- realized minus static travel time: mean **−0.33 min**, 41 % of O-D pairs
  faster in realized, 26 % slower, 33 % unchanged;
- POI reachable within 30 min: **160 589 → 165 010 (+2.7 %)**;
- POI crossing **into** the 30-min ring: **9 119 gains vs 4 698 losses**.

So in Poznań, Szczecin and Warszawa the realized-P50 schedule is genuinely
**tighter** than the published static timetable during the morning peak — the
static schedule carries visible peak padding, and the median of what vehicles
actually did beats it. In Kraków the static schedule is already tight
(`validate_gtfs`: only ~1 % of peak trips run >30 s faster in realized, ~9 %
slower) so realized loses. Gdańsk and Łódź sit in between.

**Takeaway:** "static vs realized-P50" is not a clean *delay* measure. It is
*realized median running time* vs *scheduled running time*, and whether that is
a penalty or a bonus depends on how conservatively the operator writes its
timetable. Quote it as "reachability change from schedule to realized median",
not "the cost of delays", and always with the resolution and the day.

## 2b. Weighted vs. unweighted — the headline is population-weighted

Every `net Δ` above is **population-weighted** (`out/cross_city_net.csv`,
`FINDINGS.md` §2). The plain per-hexagon mean is ~1.5–2× smaller, because the
gaining hexagons are the dense central ones (`out/hex_breakdown.csv`, after the
§0 dasymetric re-run):

| City | res | net Δ pop-weighted | net Δ unweighted | hex gain | hex loss | hex unchanged | no baseline |
|---|--:|--:|--:|--:|--:|--:|--:|
| Warszawa | 500 | **+3.45** | +1.73 | 884 (46%) | 438 (23%) | 582 | 117 |
| Poznań | 250 | **+2.84** | +1.26 | 1021 (38%) | 678 (25%) | 1010 | 224 |
| Poznań | 500 | +2.64 | +1.09 | 295 (35%) | 201 (24%) | 359 | 115 |
| Szczecin | 250 | **+2.45** | +1.33 | 678 (42%) | 279 (17%) | 658 | 141 |
| Gdańsk | 250 | +0.16 | +0.05 | 650 (30%) | 635 (29%) | 913 | 403 |
| Kraków | 250 | **−0.81** | −0.54 | 463 (12%) | 963 (25%) | 2424 | 436 |
| Kraków | 500 | −0.95 | −0.47 | 119 (10%) | 250 (22%) | 774 | 201 |

(% is of *comparable* hexagons; "no baseline" = static already reached 0,
excluded.) Even in the strong-positive cities it is not a landslide — a third to
two thirds of the comparable hexagons are unchanged; the effect is a ~1.5–2:1
gain:loss ratio that population weighting turns into a big mean because the
gains sit downtown. Gdańsk is a near-perfect 650:635 wash.

## 2c. Which trips moved — tram vs. bus, morning peak (`out/gtfs_shift_by_traction.csv`)

Trip classified by mean (realized − static) arrival over its stops on the
analysis day, first departure 07:00–09:00: >+30 s late, <−30 s early.

| City | tram late / early | bus late / early | net Δ sign |
|---|---|---|:--:|
| Poznań | 5% / **43%** | 16% / 29% | **+** |
| Szczecin | 2% / **41%** | 10% / 25% | **+** |
| Warszawa | 20% / **31%** (med −13 s) | 19% / **39%** (med −12 s) | **+** |
| Gdańsk | 22% / 30% | **41%** / 19% | ≈ 0 |
| Łódź | **41%** / 10% | 19% / 36% | ≈ 0 |
| Kraków | **46%** / 2% | 0% / 0%¹ | **−** |

¹ Kraków's realized feed leaves peak-hour bus trips at their scheduled times
(no RT rewrite in that window) — the −0.8 is carried entirely by trams, which
run 46% late. The morning-peak tram/bus early-vs-late balance predicts the sign
of every city's `net_delta` exactly.

## 3. Category detail

`out/cross_city_delay.csv`. Same story per category — the city sign dominates.
School and pharmacy (many POI, most hexagons comparable) carry the signal;
university (few POI, ~75 % of hexagons zero-baseline) is small and noisy
everywhere, as in Łódź. The zero-baseline exclusion still matters: 15–75 % of
in-scope hexagons per category have no static access to lose or gain and are
(correctly) NULL, not 0.

## 3b. Compute time (2026-09-09, one QGIS/R5 process, cold)

| City | resolutions | wall clock | 250 m static / realized pass | notes |
|---|---|--:|---|---|
| Szczecin | 250 + 500 | **8m 44s** | 3m20s / 2m57s | 5946 origins, simple network |
| Gdańsk | 250 + 500 | **13m 03s** | 5m05s / 4m03s | networks were cache-warm |
| Poznań | 250 + 500 | **15m 59s** | ~6m / 5m27s | middle of the pack |
| Kraków | 250 + 500 | **21m 12s** | ~8m / 7m12s | 6338 origins (most) + dense multi-operator net |
| Warszawa | 500 only | **23m 00s** | 500 m: 9m34s / 8m58s | 500 MB network.dat, 2546 origins |

**Poznań was not the slow one** — Kraków and Warszawa took longer. What ran
long *on Poznań* was the separate verification probe: a full 5132 × 681
origin–destination travel-time **matrix** on both networks (~8 min static +
~14 min realized ≈ 22 min), run once to confirm §2. Unlike `RunAccessibility`
(one number per origin) the matrix writes every O-D pair — 2.6 M rows per side.

R5's per-origin cost scales with **network complexity, not origin count**
(easy-R5 CLAUDE.md): Kraków is slowest because it has both the most hexagons
and the densest tram+bus network; Warszawa is slow per-origin on a half-GB
graph; Szczecin is quick despite 5946 origins because its network is small.

## 4. Per-run diagnostics

`out/run_stats.csv` — gate (static vs realized active trips, all matched
exactly), hex / population / POI counts, per-category comparable vs
zero-baseline counts, approximate pass durations. All 5 feeds passed
`validate_gtfs.py` before any R5 build.

## What to do with this

- The web map (`mapy-analizy/opoznienia-dostepnosc`, city switcher) is the
  right way to show it — the radial gradient and the per-city sign flip are
  both obvious on the map, and the legend already isolates 0.
- Don't headline "delays cost X opportunities" city-to-city — headline the
  **contrast**: same method, opposite outcome, because the schedules differ.
- Łódź's 2–3 km dip deserves a follow-up specifically about Łódź's network
  (which routes / transfers drive that ring) before it is quoted as a mechanism.
