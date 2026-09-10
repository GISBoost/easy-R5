"""Per-city inputs for the realized-GTFS delay analysis, generalized from
`../realtime_delay_lodz/` to 5 more cities (Gdańsk, Warszawa, Poznań, Kraków,
Szczecin) for the same real day 2026-08-24.

Every input already exists locally from earlier sessions -- nothing is
downloaded here:

  osm_pbf       tools/isochrones_lodz/<city>_network_static/<city>.osm.pbf
  gtfs_static   tools/isochrones_lodz/<city>_network_static/<city>_static_gtfs_2026-08-24.zip
  gtfs_realized tools/isochrones_lodz/<city>_network_rt/<city>_realized_2026-08-24_p50.zip
  ses_gpkg      tools/ses_income_lodz/<city>.gpkg   (layer obwody_spisowe, field population)
  universities  tools/accessibility_cities/<city>/<city>_universities.csv

Resolutions per city: 250 m + 500 m, except Warszawa (500 m only -- a 250 m
grid over the whole city is a real R5 memory/time risk, per easy-R5 CLAUDE.md).

Unlike the Łódź script there is NO hard-coded expected trip count: prepare_data
builds the static network, reads service_days[DATE] from network.json as the
reference, and asserts the realized network reports the identical count for the
same day (realized = rewritten times for the same trips, not a different
service). MIN_TRIPS is only a floor to catch a silent walk-only feed.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent                       # .../easy-R5
ISO = REPO / "tools" / "isochrones_lodz"
SES = REPO / "tools" / "ses_income_lodz"
ACC_CITIES = REPO / "tools" / "accessibility_cities"

ANALYSIS_DATE = "2026-08-24"
MIN_TRIPS = 3000       # any real PL city day is >>this; below => walk-only, stop

# city -> (display_name, resolutions_m)
CITIES = {
    "gdansk":   ("Gdańsk",   (250, 500)),
    "warszawa": ("Warszawa", (500,)),
    "poznan":   ("Poznań",   (250, 500)),
    "krakow":   ("Kraków",   (250, 500)),
    "szczecin": ("Szczecin", (250, 500)),
}


def paths(city: str) -> dict:
    if city not in CITIES:
        raise KeyError(f"unknown city {city!r}; known: {sorted(CITIES)}")
    return {
        "osm_pbf": ISO / f"{city}_network_static" / f"{city}.osm.pbf",
        "gtfs_static": ISO / f"{city}_network_static" / f"{city}_static_gtfs_{ANALYSIS_DATE}.zip",
        "gtfs_realized": ISO / f"{city}_network_rt" / f"{city}_realized_{ANALYSIS_DATE}_p50.zip",
        "ses_gpkg": SES / f"{city}.gpkg",
        "universities": ACC_CITIES / city / f"{city}_universities.csv",
    }


def check_inputs(city: str) -> None:
    missing = [k for k, p in paths(city).items() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"{city}: missing inputs {missing} -> {paths(city)}")
