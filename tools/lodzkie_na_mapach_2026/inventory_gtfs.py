"""E1 -- GTFS inventory across the 177 gminas of wojewodztwo lodzkie.

Runs inside QGIS (mcp__qgis__execute_code or the QGIS Python console) -- uses
QgsSpatialIndex and QgsVectorLayer, not a standalone script.

Pipeline:
  1. Download every confirmed feed in config.GTFS_FEEDS (skip-if-exists).
  2. Parse stops.txt of each feed, build a point layer.
  3. Assign each stop to a gmina via a spatial index (point-in-polygon).
  4. Count active trips for config.ANALYSIS_DATE per feed (calendar.txt +
     calendar_dates.txt), matching easy_r5/core/gtfs_calendar semantics.
  5. Aggregate to gmina level: which feeds serve it, how many stops, how many
     trips are active on the analysis date, has_rt.
  6. Write out/gtfs_inventory_gminy.csv and a `gminy_gtfs` layer in
     lodzkie_base.gpkg.

Gate: sum(ludnosc) over all 177 gminy (from ludnosc_nsp_2021.xlsx) vs GUS's
published wojewodztwo total (2 328 825) within 1%.
"""
import csv
import io
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

RAW = C.WORK / "gtfs_raw"
RAW.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (easy-R5 lodzkie-na-mapach-2026 research; contact via GISBoost)"


def download_feed(key, spec):
    # Cache keyed by (key, ANALYSIS_DATE): these are LIVE/rolling downloads
    # (today's otwarte.miasto.lodz.pl export, today's zbiorkom.live export,
    # etc.) -- the same URL returns different content on different days
    # (confirmed directly: aleksandrow_lodzki's calendar_dates.txt only
    # extends forward from its download day). Keying by date only, without
    # touching the URL, means changing config.ANALYSIS_DATE and re-running
    # forces a fresh download instead of silently reusing a stale file that
    # was fetched for a different day.
    dest = RAW / C.ANALYSIS_DATE / f"{key}.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    req = urllib.request.Request(spec["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return dest


def download_all():
    results = {}
    for key, spec in C.GTFS_FEEDS.items():
        try:
            path = download_feed(key, spec)
            ok = zipfile.is_zipfile(path)
            results[key] = {"path": path, "ok": ok, "error": None}
            print(f"[{key}] {'OK' if ok else 'NOT A ZIP'} -- {path.stat().st_size} bytes")
        except Exception as e:
            results[key] = {"path": None, "ok": False, "error": str(e)}
            print(f"[{key}] FAILED: {e}")
    return results


def _read_csv(zf, name):
    if name not in zf.namelist():
        return []
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def active_service_ids(zf, target_date):
    """Port of easy_r5/core/gtfs_calendar semantics: calendar.txt weekday +
    date range, exceptions from calendar_dates.txt (1=added, 2=removed)."""
    y, m, d = (int(x) for x in target_date.split("-"))
    tdate = date(y, m, d)
    weekday_field = ["monday", "tuesday", "wednesday", "thursday", "friday",
                      "saturday", "sunday"][tdate.weekday()]

    active = set()
    for row in _read_csv(zf, "calendar.txt"):
        start = row.get("start_date", "")
        end = row.get("end_date", "")
        if not start or not end:
            continue
        sd = date(int(start[:4]), int(start[4:6]), int(start[6:8]))
        ed = date(int(end[:4]), int(end[4:6]), int(end[6:8]))
        if sd <= tdate <= ed and row.get(weekday_field, "0") == "1":
            active.add(row["service_id"])

    for row in _read_csv(zf, "calendar_dates.txt"):
        if row.get("date") != target_date.replace("-", ""):
            continue
        sid = row["service_id"]
        if row.get("exception_type") == "1":
            active.add(sid)
        elif row.get("exception_type") == "2":
            active.discard(sid)
    return active


def feed_stats(key, spec, path, target_date):
    """Returns dict: n_stops, n_trips_active, stops=[(lon,lat,name)], error,
    covers_date (bool), coverage_note (str, only set when covers_date=False
    or the count looks implausible for a weekday)."""
    out = {"n_stops": 0, "n_trips_active": 0, "stops": [], "error": None,
           "covers_date": True, "coverage_note": None}
    try:
        with zipfile.ZipFile(path) as zf:
            stops = _read_csv(zf, "stops.txt")
            out["n_stops"] = len(stops)
            for row in stops:
                try:
                    lon = float(row["stop_lon"])
                    lat = float(row["stop_lat"])
                except (KeyError, ValueError):
                    continue
                out["stops"].append((lon, lat, row.get("stop_name", "")))

            active_sids = active_service_ids(zf, target_date)
            trips = _read_csv(zf, "trips.txt")
            out["n_trips_active"] = sum(1 for t in trips if t.get("service_id") in active_sids)

            # Coverage check: does the feed's calendar/calendar_dates window
            # actually extend to target_date at all? A feed whose earliest
            # calendar_dates entry is AFTER target_date doesn't "have zero
            # service" -- it simply wasn't published yet for that date.
            all_dates = set()
            for row in _read_csv(zf, "calendar_dates.txt"):
                all_dates.add(row.get("date", ""))
            for row in _read_csv(zf, "calendar.txt"):
                if row.get("start_date"):
                    all_dates.add(row["start_date"])
                if row.get("end_date"):
                    all_dates.add(row["end_date"])
            td = target_date.replace("-", "")
            if all_dates and td < min(all_dates):
                out["covers_date"] = False
                out["coverage_note"] = (
                    f"feed's earliest calendar entry is {min(all_dates)}, "
                    f"after analysis date {target_date} -- feed not yet published "
                    f"for this date, not a real zero-service day"
                )
            elif all_dates and td > max(all_dates):
                out["covers_date"] = False
                out["coverage_note"] = (
                    f"feed's latest calendar entry is {max(all_dates)}, "
                    f"before analysis date {target_date} -- feed expired"
                )
    except Exception as e:
        out["error"] = str(e)
    return out


def build_stop_points_layer(all_stats):
    """One memory point layer with every stop from every feed, field feed_key."""
    from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
                            QgsField)
    from qgis.PyQt.QtCore import QVariant

    lyr = QgsVectorLayer("Point?crs=EPSG:4326", "gtfs_stops_all", "memory")
    pr = lyr.dataProvider()
    pr.addAttributes([QgsField("feed_key", QVariant.String),
                       QgsField("stop_name", QVariant.String)])
    lyr.updateFields()
    feats = []
    for key, stats in all_stats.items():
        for lon, lat, name in stats["stops"]:
            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            f.setAttribute("feed_key", key)
            f.setAttribute("stop_name", name)
            feats.append(f)
    pr.addFeatures(feats)
    lyr.updateExtents()
    print(f"stop points layer: {lyr.featureCount()} features")
    return lyr


def assign_stops_to_gminy(stops_layer):
    """Point-in-polygon via QgsSpatialIndex on the gminy layer. Returns
    dict: JPT_KOD_JE -> set(feed_key)."""
    import processing
    from qgis.core import QgsVectorLayer

    gpkg = str(C.PRG_GPKG)
    gminy = QgsVectorLayer(gpkg + "|layername=gminy", "gminy", "ogr")

    res = processing.run("native:joinattributesbylocation", {
        "INPUT": stops_layer,
        "PREDICATE": [0],  # intersects
        "JOIN": gminy,
        "JOIN_FIELDS": ["JPT_KOD_JE", "JPT_NAZWA_"],
        "METHOD": 0,  # one-to-many not needed, one join per stop
        "DISCARD_NONMATCHING": True,
        "PREFIX": "",
        "OUTPUT": "memory:",
    })
    joined = res["OUTPUT"]
    print(f"stops joined to gminy: {joined.featureCount()} / {stops_layer.featureCount()}")

    gmina_feeds = defaultdict(set)
    gmina_stopcount = defaultdict(lambda: defaultdict(int))
    for f in joined.getFeatures():
        kod = f["JPT_KOD_JE"]
        key = f["feed_key"]
        if kod:
            gmina_feeds[kod].add(key)
            gmina_stopcount[kod][key] += 1
    return gmina_feeds, gmina_stopcount


def main():
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant

    print("=== E1: downloading feeds ===")
    dl = download_all()

    print("\n=== E1: computing per-feed stats for", C.ANALYSIS_DATE, "===")
    all_stats = {}
    for key, spec in C.GTFS_FEEDS.items():
        if not dl[key]["ok"]:
            print(f"[{key}] skipped (download failed)")
            continue
        stats = feed_stats(key, spec, dl[key]["path"], C.ANALYSIS_DATE)
        all_stats[key] = stats
        print(f"[{key}] stops={stats['n_stops']} trips_active={stats['n_trips_active']} "
              f"error={stats['error']}")

    print("\n=== E1: spatial join stops -> gminy ===")
    stops_layer = build_stop_points_layer(all_stats)
    gmina_feeds, gmina_stopcount = assign_stops_to_gminy(stops_layer)

    print("\n=== E1: building gminy_gtfs layer ===")
    gminy = QgsVectorLayer(str(C.PRG_GPKG) + "|layername=gminy", "gminy", "ogr")
    # IMPORTANT: gminy.clone() would share the SAME on-disk OGR data source --
    # addAttributes() on the clone's provider then ALTERs the source "gminy"
    # table in place (confirmed the hard way: it happened on the first run).
    # Build a genuine in-memory copy instead, matching the safe pattern used
    # throughout tools/realtime_delay_cities (native:* into "memory:").
    import processing
    out_lyr = processing.run("native:fixgeometries", {"INPUT": gminy, "OUTPUT": "memory:"})["OUTPUT"]
    pr = out_lyr.dataProvider()
    pr.addAttributes([
        QgsField("feeds", QVariant.String),
        QgsField("feeds_uncovered_date", QVariant.String),
        QgsField("n_feeds", QVariant.Int),
        QgsField("n_stops_total", QVariant.Int),
        QgsField("n_trips_active_max", QVariant.Int),
        QgsField("ma_static", QVariant.Int),
        QgsField("ma_rt", QVariant.Int),
        QgsField("gtfs_class", QVariant.String),
    ])
    out_lyr.updateFields()
    out_lyr.startEditing()
    for f in out_lyr.getFeatures():
        kod = f["JPT_KOD_JE"]
        all_feeds_here = sorted(gmina_feeds.get(kod, []))
        # split by whether the feed's own calendar covers the analysis date --
        # a feed with 0 active trips because it hasn't been published for
        # that date yet is a data-coverage gap, not "no service".
        feeds = [k for k in all_feeds_here if all_stats[k]["covers_date"]]
        feeds_uncovered = [k for k in all_feeds_here if not all_stats[k]["covers_date"]]
        n_stops = sum(gmina_stopcount.get(kod, {}).values())
        trips_max = max((all_stats[k]["n_trips_active"] for k in feeds), default=0)
        has_rt = any(C.GTFS_FEEDS[k].get("has_rt") for k in feeds)
        if feeds and has_rt:
            cls = "GTFS static + RT"
        elif feeds:
            cls = "GTFS static"
        elif feeds_uncovered:
            cls = "GTFS static (nie pokrywa daty analizy)"
        elif n_stops > 0:
            cls = "obslugiwana, brak GTFS"
        else:
            cls = "brak danych"
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("feeds"), ",".join(feeds))
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("feeds_uncovered_date"), ",".join(feeds_uncovered))
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("n_feeds"), len(feeds))
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("n_stops_total"), n_stops)
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("n_trips_active_max"), trips_max)
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("ma_static"), int(bool(feeds)))
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("ma_rt"), int(has_rt))
        out_lyr.changeAttributeValue(f.id(), out_lyr.fields().indexOf("gtfs_class"), cls)
    out_lyr.commitChanges()

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = "gminy_gtfs"
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out_lyr, str(C.PRG_GPKG), out_lyr.transformContext(), opts)
    print("wrote layer gminy_gtfs to", C.PRG_GPKG)

    # CSV export
    C.OUT.mkdir(parents=True, exist_ok=True)
    csv_path = C.OUT / "gtfs_inventory_gminy.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["teryt", "gmina", "feeds", "feeds_uncovered_date", "n_feeds", "n_stops_total",
                    "n_trips_active_max", "ma_static", "ma_rt", "gtfs_class"])
        for f in out_lyr.getFeatures():
            w.writerow([f["JPT_KOD_JE"], f["JPT_NAZWA_"], f["feeds"], f["feeds_uncovered_date"], f["n_feeds"],
                        f["n_stops_total"], f["n_trips_active_max"], f["ma_static"],
                        f["ma_rt"], f["gtfs_class"]])
    print("wrote", csv_path)

    # summary
    from collections import Counter
    classes = Counter(f["gtfs_class"] for f in out_lyr.getFeatures())
    print("\n=== Summary ===")
    for cls, n in classes.items():
        print(f"  {cls}: {n} gminy")
    return out_lyr, all_stats


if __name__ == "__main__":
    main()
