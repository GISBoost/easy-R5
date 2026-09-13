"""Shared configuration for the Lodzkie na mapach 2026 competition map pipeline.

Scope: accessibility-to-POI map for wojewodztwo lodzkie, two tracks:
  - voivodeship-wide, static GTFS, hex 1000 m
  - Lodz city, static vs realized (P50) GTFS, hex 250 m

See docs/lodzkie-na-mapach-2026-metodologia.md (repo root) for the competition brief,
and the approved plan for the full pipeline design.
"""
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "work"
OUT = HERE / "out"
STYLES = HERE / "styles"

# ---------------------------------------------------------------------------
# Analysis date. Thursday, school year in session (rural Lodzkie transit is
# dominated by school runs -- a summer date would understate accessibility).
# Lodz manifest entry for this date: status=ok, coverage 06:00-22:00,
# 307018 observations matched (gtfs-dashboard/manifest.json).
# ---------------------------------------------------------------------------
ANALYSIS_DATE = "2026-09-10"

# CRS: everything metric work happens in PUWG 1992 (EPSG:2180), matching the
# census-precinct data (SU_BREC_2021_OBW) and every prior tools/ analysis.
# Never EPSG:4326 for grid spacing -- degrees, not meters.
METRIC_CRS = "EPSG:2180"

# ---------------------------------------------------------------------------
# Hex grids
# ---------------------------------------------------------------------------
HEX_SPACING_WOJ_M = 1000  # confirmed/adjusted after E6 calibration
HEX_SPACING_LODZ_M = 250

# ---------------------------------------------------------------------------
# Base data sources
# ---------------------------------------------------------------------------
GEOFABRIK_PBF_URL = "https://download.geofabrik.de/europe/poland/lodzkie-latest.osm.pbf"
PBF_WOJ = WORK / "pbf" / "lodzkie-latest.osm.pbf"
PBF_LODZ = WORK / "pbf" / "lodz.osm.pbf"

PRG_GPKG = HERE / "lodzkie_base.gpkg"  # layers: gminy, powiaty, wojewodztwo (EPSG:4258)

# GUS census precinct geometry + population (read-only, shared with other tools/)
SU_BREC_SHP = (
    HERE.parent.parent / ".." / "easy-OTP" / "docs" / "gis" / "SU_BREC_2021_OBW"
    / "SU_BREC_2021_OBW.shp"
)
LUDNOSC_XLSX = HERE.parent.parent / ".." / "easy-OTP" / "docs" / "gis" / "ludnosc_nsp_2021.xlsx"

# TERYT prefix for wojewodztwo lodzkie
TERYT_WOJ = "10"

# ---------------------------------------------------------------------------
# GTFS inventory (E1) -- confirmed feeds as of 2026-09-13 research pass.
# Each entry: key -> dict(name, url, operator, coverage note, has_rt)
# "girlc.at" URLs verified HTTP 200 + plausible agency/stops bbox inside Lodzkie.
# tribus.zip / plusbus.zip on girlc.at were checked and REJECTED: their stop
# bboxes sit in Warmia-Mazury / Podlasie, nothing to do with Lodzkie.
# ---------------------------------------------------------------------------
GTFS_FEEDS = {
    "lodz": {
        "name": "MPK Lodz",
        "url": "https://otwarte.miasto.lodz.pl/wp-content/uploads/2025/06/GTFS.zip",
        "has_rt": True,  # recorded in easy-GTFS-RT, key "lodz"
        "license": "CC-BY 4.0 (otwarte.miasto.lodz.pl)",
    },
    "lka_bus": {
        "name": "Lodzka Kolej Aglomeracyjna / KKA - buses",
        "url": "https://gtfs.kasznia.net/static/sanitized/lka_bus.zip",
        "has_rt": False,
        "license": "CC-BY 4.0 (kasznia.net)",
    },
    "polish_trains": {
        "name": "Unified Poland rail feed (incl. LKA, PKP IC, Polregio, KM)",
        "url": "https://mkuran.pl/gtfs/polish_trains.zip",
        "has_rt": False,
        "license": "CC-BY 4.0 (mkuran.pl / kasmar00 remix)",
        "note": (
            "kasznia.net's lka_train.zip is nominally deprecated in favour of this "
            "unified feed, but CONFIRMED BROKEN for our analysis date (E1, 2026-09-13): "
            "calendar_dates.txt shows a nationwide timetable-edition boundary right at "
            "2026-09-10 -- only 1 service_id / 96 trips active that day (vs 350-475/day "
            "from 2026-09-14 onward once the new edition ramps up). This is CLAUDE.md "
            "gotcha #1 (silent near-walk-only) triggered by the feed itself, verified by "
            "reading calendar_dates.txt directly, not a parsing bug. USED ONLY for the "
            "gmina-level inventory (E1, shows which gminy have ANY rail stop e.g. PKP "
            "Intercity/Polregio mainline) -- NOT used for routing on 2026-09-10. See "
            "'lka_train' below for the feed actually used for LKA routing."
        ),
    },
    "lka_train": {
        "name": "Lodzka Kolej Aglomeracyjna (rail only) + Kolej Waskotorowa Rogow-Rawa-Biala",
        "url": "https://gtfs.kasznia.net/static/sanitized/lka_train.zip",
        "has_rt": False,  # RT exists only via TripUpdates (family_b_realized), check at run time
        "license": "CC-BY 4.0 (kasznia.net)",
        "note": (
            "Site labels this 'deprecated' in favour of polish_trains.zip, but for our "
            "narrow need (LKA only, not nationwide PKP/Polregio) it is demonstrably the "
            "better source: stable 340 trips/day across 2026-09-07..09-13 (checked "
            "directly), calendar_dates window extends to 2026-12-12 (comfortably covers "
            "the 2026-11-02 submission deadline). feed_version 2026-06-16 -- stale but "
            "internally consistent for our date. USE THIS for LKA in net_lodz_static / "
            "net_lodz_p50, not polish_trains. Realized LKA (TripUpdates via "
            "easy-OTP/tools/family_b_realized, started collecting 2026-09-09, ~2 day "
            "source retention) -- check at run time whether a 2026-09-10 P50 actually "
            "exists before claiming rail is part of the realized-vs-static delta."
        ),
    },
    "kutno": {
        "name": "MZK Kutno",
        "url": "https://api.zbiorkom.live/api6-open/kutno/gtfs/default",
        "has_rt": False,
        "license": "unclear -- zbiorkom.live aggregator, verify before publishing",
    },
    "aleksandrow_lodzki": {
        "name": "Aleksandrow Lodzki (Urzad Miejski)",
        "url": "https://files.girlc.at/gtfs/aleksandrow_lodzki.zip",
        "has_rt": False,
        "license": "CC0 (girlc.at)",
        "note": (
            "CONFIRMED (E1, 2026-09-13): feed has no calendar.txt, only "
            "calendar_dates.txt whose earliest entry is 2026-09-13 (today, at "
            "download time) -- it is a rolling ~2-week-ahead export that cannot "
            "cover the analysis date 2026-09-10 (3 days in the past relative to "
            "download day). 0 active trips that day is a publication-window gap, "
            "not a real zero-service Thursday. Excluded from the 2026-09-10 "
            "network build; gmina flagged 'GTFS static (nie pokrywa daty analizy)'."
        ),
    },
    "opoczno_mpk": {
        "name": "MPK Opoczno",
        "url": "https://files.girlc.at/gtfs/opoczno.zip",
        "has_rt": False,
        "license": "CC0 (girlc.at)",
    },
    "opoczno_pks": {
        "name": "PKS Opoczno",
        "url": "https://files.girlc.at/gtfs/pks_opoczno.zip",
        "has_rt": False,
        "license": "CC0 (girlc.at)",
    },
    "rozprza": {
        "name": "Gmina Rozprza",
        "url": "https://files.girlc.at/gtfs/rozprza.zip",
        "has_rt": False,
        "license": "CC0 (girlc.at)",
    },
    "tomaszow_mazowiecki": {
        "name": "MZK Tomaszow Mazowiecki",
        "url": "https://files.girlc.at/gtfs/tomaszow_mazowiecki.zip",
        "has_rt": False,
        "license": "CC0 (girlc.at)",
    },
}

# Checked and confirmed to have NO published GTFS as of 2026-09-13, via
# girlc.at direct-URL probing + dane.gov.pl dataset/institution search +
# direct operator portal inspection (rozklady.zdium-piotrkow.pl has no GTFS
# export, HTML timetables only):
GTFS_NOT_FOUND = [
    "Piotrkow Trybunalski (ZDiUM)", "Sieradz (MPK Sieradz)", "Belchatow",
    "Radomsko", "Skierniewice", "Zdunska Wola", "Wielun", "Lowicz",
    "Zgierz", "Pabianice", "Glowno", "Brzeziny", "Lask",
]

# ---------------------------------------------------------------------------
# Accessibility run parameters (defaults; E6 calibration may adjust batch/heap)
# ---------------------------------------------------------------------------
DEPARTURE_TIME = "07:00"
TIME_WINDOW_MIN = 120
PERCENTILE = "50"
DECAY = "STEP"
# 45 min dropped 2026-09-13 (Michal): only 30 min going forward, less noise
# in the attribute tables and in the summary CSVs. Existing out/*.csv from
# before this change still have 45-min rows -- harmless, just unused by any
# future compute_metrics.py run against this config.
CUTOFFS = "30"

# Placeholders, set by calibrate.py after E6:
BATCH_SIZE = None
JAVA_HEAP_GB = None
MAX_WALK_TIME = None

# ---------------------------------------------------------------------------
# E5 network folders (assembled 2026-09-13, work/networks/<name>/gtfs/).
# Each folder = exactly one GTFS-build variant, never mixed (static vs
# realized share trip_id/stop_id and must never share a build directory).
# ---------------------------------------------------------------------------
# net_woj_static : lodz(static,pinned 2026-09-10 release) + lka_bus + lka_train
#                  + kutno + opoczno_mpk + opoczno_pks + rozprza + tomaszow_mazowiecki
#                  EXCLUDES aleksandrow_lodzki (feed doesn't cover 2026-09-10)
#                  and polish_trains (broken for this date, see GTFS_FEEDS note)
# net_woj_lodzrt : same set, lodz swapped for the pinned P50 realized zip
# net_lodz_static: lodz(static, pinned) + lka_train only
# net_lodz_p50   : lodz(P50, pinned) + lka_train (UNCHANGED -- see below)
#
# LKA REALIZED DECISION (2026-09-13): NOT attempted for this date. A raw
# TripUpdates snapshot for 2026-09-10 IS archived (GitHub release
# polish-trains-tripupdates-raw-2026-09, asset polish_trains_updates_2026-09-10.pb.gz,
# confirmed to exist), so it is technically retrievable. Not used because:
# (a) family_b_realized/README.md states single-day P50 is thin/unreliable
#     by design ("~1-3 observations per segment"; the method's real value is
#     multi-day pooling over 15-20+ days, which we don't have yet);
# (b) the static feed needed to anchor it must be "polish_trains.zip as it
#     was on the service day" -- our current download is post-timetable-edition
#     and may not retain the old trip_id set at all.
# DECISION: LKA static schedule is used UNCHANGED on both sides of the Lodz
# static-vs-P50 comparison. The realized-vs-static delta for Lodz measures
# ZDiT (bus+tram) only; LKA contributes identical accessibility in both runs
# by construction. This must be stated plainly in the map's methodology text
# -- it is the plan's own designed fallback (docs note: "ŁKA statyczna po
# obu stronach + wyraźne zastrzeżenie, że delta = ZDiT"), reached because
# the realized path was tried and found unreliable for one day, not skipped.
NETWORKS_DIR = WORK / "networks"
