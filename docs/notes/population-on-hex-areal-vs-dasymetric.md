# Population on a hex grid — areal vs. dasymetric — 2026-09-10

**Verdict:** `easyr5:populationoverlay` (and the reference model it ports) is
*areal interpolation* — fine as a default, but it puts phantom residents on
unpopulated land. For any analysis where you read per-hexagon population (not
just a city-wide weighted mean), redistribute onto OSM building footprints
instead. `tools/realtime_delay_cities/dasymetric_pop.py` does this for the
delay-accessibility grids; the same approach belongs in a future
`DasymetricPopulationOverlay` if the plugin ever needs one.

## What the current tool does

`easy_r5/algorithms/population_overlay.py` ports
`easy-OTP/docs/reference-R/ludnosc_studentow_model_qgis.py` exactly:

```
density = precinct_population / precinct_area        # persons / m², UNIFORM over the polygon
split precinct by hex edges
piece_pop = piece_area × density
hex_pop = Σ piece_pop
```

It is mass-preserving and correct *as areal interpolation*. The assumption it
bakes in — uniform population density across the whole census precinct — is
false wherever a precinct contains fields, forest, rail yards, water or port
land, which inside a Polish city boundary is common.

## Measured failure (Kraków, NSP 2021 precincts)

| hex | areal pop | OSM buildings in hex | reality |
|---|--:|--:|---|
| #178 | 3.8 | 0 | fields + railway; 66 % of the hex is a 287-person precinct that is 2.7 % built |
| #143 | 0.27 | 0 | 9-person precinct over 1.8 km² |

City-wide, areal put **2.8 % of Kraków's population** (≈ 22 600 people) into
hexagons that contain no residential building at all, and mislocated ~23 % of
the population by ≥ 1 hexagon relative to a building-based estimate.

## The fix — binary dasymetric mapping (Mennis 2003)

Per precinct, redistribute `population` proportional to **OSM building
footprint area** (residential-ish `building=*`, non-residential values
excluded — see `dasymetric_pop.EXCL_BUILDINGS`). Uniform-areal fallback for the
few precincts with no residential building (0–14 per city, ≤ 564 people).
Storeys (`building:levels`) deliberately **not** used — PL coverage is uneven
(20–90 %) and footprint-only vs footprint×levels differ by < 4 % of population.

Implementation: rasterise buildings to a 10 m built/not-built raster (cached),
`native:zonalstatisticsfb` sum per (hex ∩ precinct) fragment, redistribute in
Python. Mass preserved to 0.000 % in all 6 cities.

## Effect on the delay analysis

Population-weighted `net_delta` headlines moved ≤ 0.05; the transfer-ring
hypothesis verdict (2 confirm / 9 deny) was identical. What changed: 20–70 % of
hexagons dropped out as genuinely empty, and the *unweighted* per-hex means and
gain/loss counts got cleaner. See `tools/realtime_delay_cities/FINDINGS.md` §0.

## When areal is still fine

City-wide population-weighted means where the weight is `pop_total`: a hexagon
with a phantom 4 people barely moves a mean that is dominated by hexagons with
hundreds. The areal default is only a problem when a phantom hexagon is
*counted* (unweighted stats, hexagon tallies, "how many hexes improved"),
which is exactly what a per-hexagon map invites a reader to do.
