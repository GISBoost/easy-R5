# Transfer-zone hypothesis — verdict

**Hypothesis.** Real-world transit delays degrade reachability most in a *ring*
around the core (the transfer-dependent belt), not uniformly toward the centre.
Test: population-weighted mean `net_delta` (realized-P50 minus static, 30 min,
07:00-09:00) binned by 1 km distance from each city's population-weighted centroid.
A city 'confirms' if its worst 1 km ring sits at 1-4 km, is worse than the
innermost ring, and is at least 0.3 opportunities below the median of the other rings.

| City | res | mean net Δ | worst ring | worst mean | inner ring | worst − median(other) | mid-ring dip? |
|---|--:|--:|---|--:|--:|--:|:--:|
| Gdańsk | 250 | 0.155 | 6-7 | -0.949 | 2.063 | -1.154 | ❌ |
| Gdańsk | 500 | -0.017 | 5-6 | -1.306 | -0.954 | -1.51 | ❌ |
| Kraków | 250 | -0.811 | 0-1 | -3.068 | -3.068 | -3.03 | ❌ |
| Kraków | 500 | -0.947 | 5-6 | -1.307 | 0.333 | -1.108 | ❌ |
| Poznań | 250 | 2.843 | 8-9 | -0.49 | 5.121 | -0.628 | ❌ |
| Poznań | 500 | 2.642 | 6-7 | -0.737 | 6.504 | -1.761 | ❌ |
| Szczecin | 250 | 2.448 | 6-7 | -0.078 | 2.977 | -1.774 | ❌ |
| Szczecin | 500 | 2.074 | 14-15 | -0.237 | 2.115 | -2.196 | ❌ |
| Warszawa | 500 | 3.449 | 14-15 | -0.043 | 8.735 | -2.003 | ❌ |
| Łódź | 250 | -0.3 | 2-3 | -2.484 | 0.791 | -2.594 | ✅ |
| Łódź | 500 | 0.135 | 2-3 | -2.0 | 1.482 | -2.324 | ✅ |

**2 city-resolutions confirm the mid-ring dip, 9 do not.**

See `out/charts/transfer_ring_<city>_<res>m.png` for the per-city bar charts
and `../realtime_delay_lodz/` for the Łódź original (`distance_vs_net_delta_*`).
