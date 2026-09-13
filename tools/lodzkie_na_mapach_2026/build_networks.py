"""E5 -- build the four R5 networks. Runs inside QGIS (uses easyr5:buildnetwork).

DO NOT RUN until R5/Java is cleared to use memory (Michal is gaming as of
2026-09-13 -- he said he'll signal when it's OK). This module only defines
the build calls; nothing here executes at import time.

Networks (see config.py NETWORKS_DIR comment block for the full rationale):
  net_woj_static  -- lodzkie.osm.pbf + 8 confirmed static feeds
  net_woj_lodzrt  -- same OSM, lodz.zip swapped for the pinned P50
  net_lodz_static -- lodz.osm.pbf (city clip) + lodz static + lka_train
  net_lodz_p50    -- lodz.osm.pbf + lodz P50 + lka_train (unchanged)

validate_gtfs.py --all already passed on all four folders (2026-09-13) --
this script assumes that gate, it does not re-run it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

NETWORKS = {
    "net_woj_static": C.PBF_WOJ,
    "net_woj_lodzrt": C.PBF_WOJ,
    "net_lodz_static": C.PBF_LODZ,
    "net_lodz_p50": C.PBF_LODZ,
}


def build_one(name, osm_pbf):
    import processing

    net_dir = C.NETWORKS_DIR / name
    gtfs_folder = net_dir / "gtfs"
    cache_folder = net_dir / "cache"
    cache_folder.mkdir(parents=True, exist_ok=True)

    print(f"=== building {name} ===")
    print(f"  OSM_PBF={osm_pbf}")
    print(f"  GTFS_FOLDER={gtfs_folder} ({len(list(gtfs_folder.glob('*.zip')))} feeds)")

    result = processing.run("easyr5:buildnetwork", {
        "OSM_PBF": str(osm_pbf),
        "GTFS_FOLDER": str(gtfs_folder),
        "CACHE_FOLDER": str(cache_folder),
        "FORCE_REBUILD": False,
    })
    print(f"  NETWORK_DAT={result['NETWORK_DAT']}")
    print(f"  NETWORK_JSON={result['NETWORK_JSON']}")

    import json
    with open(result["NETWORK_JSON"], encoding="utf-8") as f:
        meta = json.load(f)
    sd = meta.get("service_days", {})
    n_active = sd.get(C.ANALYSIS_DATE)
    if n_active is not None:
        print(f"  service_days[{C.ANALYSIS_DATE}] = {n_active}")
        if not n_active:
            raise RuntimeError(
                f"GATE FAILED ({name}): 0 active trips on {C.ANALYSIS_DATE} in the "
                f"BUILT network's own calendar summary -- gotcha #1, silent walk-only."
            )
    elif sd:
        # gtfs_calendar.compute_service_days caps its summary at 90 days from
        # the EARLIEST calendar/calendar_dates entry across ALL feeds in the
        # folder -- confirmed by reading the source (2026-09-13). Combining
        # lka_train.zip (calendar starts 2025-12-14) with a feed whose
        # relevant date is ~9 months later pushes ANALYSIS_DATE outside this
        # cosmetic preview window; it does NOT mean the network lacks
        # service that day. validate_gtfs.py already confirmed real,
        # nonzero service per feed on this date -- that pre-flight check is
        # the actual gate here, not this summary field. The runtime
        # walk-only detector (transit_used_pairs) in RunAccessibility is the
        # remaining safety net if something is still wrong.
        lo, hi = min(sd), max(sd)
        print(f"  service_days summary window is {lo}..{hi} (90-day cap from earliest "
              f"feed) -- does not reach {C.ANALYSIS_DATE}. Not a gate failure; see "
              f"validate_gtfs.py's per-feed pre-flight (already passed) and check "
              f"transit_used_pairs after routing.")
    else:
        raise RuntimeError(f"GATE FAILED ({name}): network.json has no service_days at all")
    return result


def main(names=None):
    names = names or list(NETWORKS)
    results = {}
    for name in names:
        results[name] = build_one(name, NETWORKS[name])
    return results


if __name__ == "__main__":
    main()
