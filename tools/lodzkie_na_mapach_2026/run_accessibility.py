"""E7 -- the four accessibility runs. Runs inside QGIS (easyr5:runaccessibility).

DO NOT RUN until R5/Java is cleared (see build_networks.py header -- same
constraint, same reason). Depends on E5 networks and E4 destination layers
(poi_targets_woj / poi_targets_lodz) existing already.

Runs:
  A1  -- level, voivodeship          net_woj_static    hex_woj_centroids   x poi_targets_woj
  A2  -- Lodz feed swapped for RT    net_woj_lodzrt    hex_woj_centroids   x poi_targets_woj
  A3a -- Lodz, static                net_lodz_static   hex_lodz_centroids  x poi_targets_lodz
  A3b -- Lodz, realized P50          net_lodz_p50      hex_lodz_centroids  x poi_targets_lodz

Each writes out/acc_<run>.csv (+.gpkg, +.params.json, R5's own .csv.meta.json)
and is resumable: if a run's .params.json already matches, it's skipped
(same convention as tools/realtime_delay_cities/run_accessibility.py).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

GPKG = C.PRG_GPKG

RUNS = {
    "A1_woj_static": {
        "network": C.NETWORKS_DIR / "net_woj_static" / "cache",  # network.dat auto-discovered inside
        "origins": f"{GPKG}|layername=hex_woj_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_woj",
    },
    "A2_woj_lodzrt": {
        "network": C.NETWORKS_DIR / "net_woj_lodzrt" / "cache",
        "origins": f"{GPKG}|layername=hex_woj_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_woj",
    },
    "A3a_lodz_static": {
        "network": C.NETWORKS_DIR / "net_lodz_static" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
    },
    "A3b_lodz_p50": {
        "network": C.NETWORKS_DIR / "net_lodz_p50" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
    },
    # 3-day robustness check (MULTIDAY_LODZ_NOTES.md). Static side reused
    # across all 3 days -- confirmed byte-identical ZDiT schedule and
    # identical active service_id for 09-08/09-09/09-10, so A3a_lodz_static
    # above (rerun with the new 21-category poi_targets_lodz) already IS the
    # static baseline for all three; only the realized side needs 3 runs.
    "A3b_lodz_p50_2026-09-08": {
        "network": C.NETWORKS_DIR / "net_lodz_p50_2026-09-08" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
    },
    "A3b_lodz_p50_2026-09-09": {
        "network": C.NETWORKS_DIR / "net_lodz_p50_2026-09-09" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
    },
    # Vacation-vs-school-term check (Michal, 2026-09-14): is the uniform
    # negative delta a September/return-to-school artifact, or a standing
    # Lodz characteristic? Two static baselines needed (not one, unlike the
    # Sept multiday check) -- 2026-08-13/14 (Wed/Thu) and 2026-08-17/18
    # (Mon/Tue) run different active service_id ("11484_11" vs "11489_11",
    # confirmed via validate_gtfs.active_service_ids), so one fixed DATE
    # cannot stand in for both pairs.
    "A3a_lodz_static_2026-08-13": {
        "network": C.NETWORKS_DIR / "net_lodz_static_2026-08" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
        "date": "2026-08-13",
    },
    "A3a_lodz_static_2026-08-17": {
        "network": C.NETWORKS_DIR / "net_lodz_static_2026-08" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
        "date": "2026-08-17",
    },
    "A3b_lodz_p50_2026-08-13": {
        "network": C.NETWORKS_DIR / "net_lodz_p50_2026-08-13" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
        "date": "2026-08-13",
    },
    "A3b_lodz_p50_2026-08-14": {
        "network": C.NETWORKS_DIR / "net_lodz_p50_2026-08-14" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
        "date": "2026-08-14",
    },
    "A3b_lodz_p50_2026-08-17": {
        "network": C.NETWORKS_DIR / "net_lodz_p50_2026-08-17" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
        "date": "2026-08-17",
    },
    "A3b_lodz_p50_2026-08-18": {
        "network": C.NETWORKS_DIR / "net_lodz_p50_2026-08-18" / "cache",
        "origins": f"{GPKG}|layername=hex_lodz_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_lodz",
        "date": "2026-08-18",
    },
    # Threshold-sensitivity check (Michal, 2026-09-14): with no RT data at
    # voivodeship scale, "delta" is redefined here as the GROWTH in reachable
    # POI when the cutoff doubles (30 -> 60 min), not a static-vs-realized
    # comparison. Same network/origins/destinations as A1_woj_static, just a
    # wider CUTOFFS -- MAX_TRIP_DURATION's plugin default (90 min) already
    # covers 60 min, so this does not re-search a larger radius than the
    # existing A1 run did, only sums the accessibility at one more cutoff.
    "A1_woj_static_thresholds": {
        "network": C.NETWORKS_DIR / "net_woj_static" / "cache",
        "origins": f"{GPKG}|layername=hex_woj_centroids",
        "destinations": f"{GPKG}|layername=poi_targets_woj",
        "cutoffs": "30,60",
    },
    # NOTE 2026-09-13: the *_new11 split-layer workaround for easy-R5 issue #5
    # (destinations-field corruption from a stale cached QGIS layer, not
    # actually a destination-count limit) is no longer needed -- the plugin
    # now fails loudly instead of silently corrupting data (points.py fix,
    # commit 25d9825), and the runs above go straight against the full
    # 21-category poi_targets_lodz. merge_split_lodz_categories.py and the
    # poi_targets_lodz_new11 layer are historical (kept for the record in
    # MULTIDAY_LODZ_NOTES.md), not part of the live pipeline any more.
}


def _network_dat(cache_dir):
    """Exactly one hash subdir per cache folder, per easy-R5 convention --
    a second build would otherwise silently pick the wrong network."""
    hits = list(Path(cache_dir).glob("*/network.dat"))
    if len(hits) != 1:
        raise RuntimeError(f"expected exactly 1 network.dat under {cache_dir}, found {len(hits)}")
    return str(hits[0])


_DECAY_ENUM = {"STEP": 0, "LOGISTIC": 1, "EXPONENTIAL": 2}  # Enum param, index not string


def opportunity_fields(destinations_uri):
    """srv_* fields on the destination layer -- discovered, not hardcoded,
    so a category rejected/added in E4 doesn't need this file edited too."""
    from qgis.core import QgsVectorLayer
    lyr = QgsVectorLayer(destinations_uri, "dest", "ogr")
    return [f.name() for f in lyr.fields() if f.name().startswith("srv_")]


def already_done(out_csv, params):
    p = Path(str(out_csv) + ".params.json")
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text(encoding="utf-8")) == params
    except (json.JSONDecodeError, OSError):
        return False


def run_one(name, spec):
    import processing

    network_dat = _network_dat(spec["network"])
    opp_fields = opportunity_fields(spec["destinations"])
    print(f"=== {name}: opportunity fields = {opp_fields} ===")

    out_csv = C.OUT / f"acc_{name}.csv"
    out_gpkg = C.OUT / f"acc_{name}.gpkg"

    params = {
        "NETWORK": network_dat,
        "ORIGINS": spec["origins"],
        "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": spec["destinations"],
        "DEST_ID_FIELD": "poi_id",
        "DATE": spec.get("date", C.ANALYSIS_DATE),
        "DEPARTURE_TIME": C.DEPARTURE_TIME,
        "TIME_WINDOW": C.TIME_WINDOW_MIN,
        "PERCENTILES": C.PERCENTILE,
        "OPPORTUNITY_FIELDS": opp_fields,
        "CUTOFFS": spec.get("cutoffs", C.CUTOFFS),
        "DECAY": _DECAY_ENUM[C.DECAY],
        "OUTPUT_CSV": str(out_csv),
        "OUTPUT_LAYER": str(out_gpkg),
        # See calibrate.py's comment on the same override: the plugin's
        # dead-date guard reads network.json's service_days, which is capped
        # at 90 days from the earliest feed's calendar (lka_train.zip starts
        # 2025-12-14) and therefore false-positives on our real 2026-09-10
        # date. validate_gtfs.py independently confirmed real, nonzero
        # service per feed on this date -- this is a confirmed
        # false-positive override, not a blind bypass of gotcha #1.
        "ALLOW_NO_SERVICE": True,
    }
    if C.BATCH_SIZE is not None:
        params["BATCH_SIZE"] = C.BATCH_SIZE
    if C.JAVA_HEAP_GB is not None:
        params["JAVA_HEAP_GB"] = C.JAVA_HEAP_GB
    if C.MAX_WALK_TIME is not None:
        params["MAX_WALK_TIME"] = C.MAX_WALK_TIME

    if already_done(out_csv, params):
        print(f"  [skip] {name} already run with identical params")
        return

    import time
    t0 = time.time()
    result = processing.run("easyr5:runaccessibility", params)
    elapsed = time.time() - t0
    print(f"  done in {elapsed:.1f}s -> {result}")

    Path(str(out_csv) + ".params.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    return result


def main(names=None):
    names = names or list(RUNS)
    for name in names:
        run_one(name, RUNS[name])


if __name__ == "__main__":
    main()
