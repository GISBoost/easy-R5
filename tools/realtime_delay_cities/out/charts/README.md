# out/charts/

`transfer_ring_<city>_<res>m.png` — the transfer-zone hypothesis test per city:
population-weighted mean `net_delta` (realized-P50 minus static, 30 min,
07:00-09:00) binned by 1 km distance from the city's population-weighted
centroid. Same ColorBrewer RdBu-7 zero-isolated colours as the maps. Built by
`../../chart_distance_delta.py`.

`.csv` / `.json` next to each PNG carry the exact plotted values, the centre
coordinate, a source SHA-256, and the machine-readable verdict
(`dip` true/false, worst ring, depth vs the other rings). Rolled up by
`../../cross_city_summary.py` into `../HYPOTHESIS.md`.

Only the PNGs are versioned (see `../../.gitignore`); regenerate the rest.
