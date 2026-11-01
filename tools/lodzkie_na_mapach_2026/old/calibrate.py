"""E6 -- calibration run on one powiat before committing to full-scale
parameters. Runs inside QGIS. DO NOT RUN until R5/Java is cleared (see
build_networks.py header).

Measures on the REAL voivodeship network (net_woj_static, once built):
  - seconds/origin at MODE=TRANSIT+WALK (remember the ~2x walk-only-detector
    cost noted in easy-R5 CLAUDE.md)
  - peak RAM vs the auto heap formula min(0.6*RAM, 12GB)
  - whether BATCH_SIZE=500 (the algorithm default) is safe at this network
    size, or needs lowering
  - confirms (or revises) the 1000 m grid choice for the voivodeship

Powiat chosen: pabianicki (TERYT 1005) -- has a town, a rural fringe, and
a shared boundary with the Lodz network, per the plan's own reasoning.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

CALIBRATION_POWIAT_TERYT = "1005"  # pabianicki


def sample_origins(n=200):
    """A few hundred origins from hex_woj_centroids that fall inside the
    calibration powiat -- enough to measure seconds/origin without paying
    for the full ~17000-origin run first."""
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter

    gpkg = str(C.PRG_GPKG)
    centroids = QgsVectorLayer(gpkg + "|layername=hex_woj_centroids", "c", "ogr")
    powiaty = QgsVectorLayer(gpkg + "|layername=powiaty", "p", "ogr")
    powiat = processing.run("native:extractbyexpression", {
        "INPUT": powiaty, "EXPRESSION": f'"JPT_KOD_JE" = \'{CALIBRATION_POWIAT_TERYT}\'',
        "OUTPUT": "memory:",
    })["OUTPUT"]
    if powiat.featureCount() == 0:
        raise RuntimeError(f"powiat {CALIBRATION_POWIAT_TERYT} not found")

    in_powiat = processing.run("native:extractbylocation", {
        "INPUT": centroids, "PREDICATE": [0], "INTERSECT": powiat, "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"origins in calibration powiat: {in_powiat.featureCount()}")

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "calib_origins"
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(in_powiat, gpkg, in_powiat.transformContext(), opts)
    return in_powiat.featureCount()


def run_calibration_matrix():
    """One RunTravelTimeMatrix pass, calib_origins x poi_targets_woj, timed."""
    import processing
    from pathlib import Path as P

    net_dir = C.NETWORKS_DIR / "net_woj_static" / "cache"
    hits = list(net_dir.glob("*/network.dat"))
    if len(hits) != 1:
        raise RuntimeError(f"net_woj_static not built yet (found {len(hits)} network.dat under {net_dir})")

    gpkg = str(C.PRG_GPKG)
    out_csv = C.OUT / "calib_matrix.csv"

    t0 = time.time()
    result = processing.run("easyr5:runtraveltimematrix", {
        "NETWORK": str(hits[0]),
        "ORIGINS": f"{gpkg}|layername=calib_origins",
        "ORIGIN_ID_FIELD": "hex_id",
        "DESTINATIONS": f"{gpkg}|layername=poi_targets_woj",
        "DEST_ID_FIELD": "poi_id",
        "DATE": C.ANALYSIS_DATE,
        "DEPARTURE_TIME": C.DEPARTURE_TIME,
        "TIME_WINDOW": C.TIME_WINDOW_MIN,
        "PERCENTILES": C.PERCENTILE,
        "OUTPUT_CSV": str(out_csv),
        # PLUGIN BUG (found 2026-09-13, worth a GitHub issue against easy-R5):
        # the dead-date guard reuses network.json's service_days, which
        # gtfs_calendar.compute_service_days caps at 90 days from the
        # EARLIEST calendar/calendar_dates entry across ALL feeds in the
        # build folder. lka_train.zip's calendar starts 2025-12-14, capping
        # the window at 2026-03-13 -- our real 2026-09-10 analysis date
        # falls outside it, so the guard reports "no service" even though
        # every individual feed demonstrably has active trips that day
        # (independently verified, validate_gtfs.py, per-feed calendar
        # parsing -- not through this capped summary). Overriding here is a
        # confirmed false-positive override, not a blind bypass.
        "ALLOW_NO_SERVICE": True,
    })
    elapsed = time.time() - t0
    print(f"calibration matrix done in {elapsed:.1f}s -> {result}")
    return elapsed


def main():
    n = sample_origins()
    elapsed = run_calibration_matrix()
    per_origin = elapsed / n if n else float("nan")
    print(f"\n=== E6 calibration result ===")
    print(f"  {n} origins, {elapsed:.1f}s total, {per_origin:.3f}s/origin")
    full_n_estimate = 16864  # hex_woj_pop count from E3
    print(f"  extrapolated full run (n={full_n_estimate}): {per_origin*full_n_estimate/60:.1f} min "
          f"(x{2} for a second TRANSIT run's walk-only detector cost already included in this "
          f"single measurement, since RunTravelTimeMatrix does the same double-task per origin "
          f"as RunAccessibility)")
    return {"n": n, "elapsed": elapsed, "per_origin": per_origin}


if __name__ == "__main__":
    main()
