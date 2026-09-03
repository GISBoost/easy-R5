"""Batch-scheduling helpers and result assembly for RunTravelTimeMatrix.

Pure stdlib, unit-tested. The Processing algorithm slices the origin list into
batches (one batch = one R5 process = one CSV, PRD 3.4), then stitches the CSVs
back together here. ``systematic_sample_indices`` picks the ESTIMATE_FIRST probe
origins; ``nearest_served_days`` powers the dead-date error message.

The one QGIS-touching function, ``build_od_lines``, is optional output and lives
here only to keep all matrix-result code in one place.
"""

from __future__ import annotations

import csv
import datetime


def utm_epsg(lon, lat):
    """EPSG code of the UTM zone containing ``(lon, lat)`` (WGS84 degrees).

    GenerateIsochrones needs a metre-based working CRS. Pure so the
    zone/hemisphere arithmetic (a classic off-by-one) is unit-tested without
    QGIS. Zone is clamped to 1..60 for a point exactly on the antimeridian.
    """
    zone = min(60, max(1, int((lon + 180) / 6) + 1))
    return (32600 if lat >= 0 else 32700) + zone


def systematic_sample_indices(n, k=15):
    """Return up to ``k`` row indices spread evenly across ``range(n)``.

    Endpoints included, strictly ascending, de-duplicated. Used to time a
    representative sample of origins before the full run — R5 cost scales with
    where in the network an origin sits, not just the count (PRD 2.1, lesson 3),
    so a contiguous first-k slice would misjudge a city with a dense core.
    """
    if n <= 0:
        return []
    if k >= n:
        return list(range(n))
    if k <= 1:
        return [0]
    step = (n - 1) / (k - 1)
    seen = []
    for i in range(k):
        idx = round(i * step)
        if not seen or idx > seen[-1]:
            seen.append(idx)
    return seen


def merge_batch_csvs(paths, out_path):
    """Concatenate batch CSVs (identical header) into ``out_path``.

    Writes the header once, then every data row in ``paths`` order. Missing or
    empty batch files are skipped. Returns the number of data rows written.
    """
    rows_written = 0
    header_written = False
    with open(out_path, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        for path in paths:
            try:
                fh = open(path, newline="", encoding="utf-8")
            except FileNotFoundError:
                continue
            with fh:
                reader = csv.reader(fh)
                try:
                    header = next(reader)
                except StopIteration:
                    continue
                if not header_written:
                    writer.writerow(header)
                    header_written = True
                for row in reader:
                    if not row:
                        continue
                    writer.writerow(row)
                    rows_written += 1
    return rows_written


def nearest_served_days(service_days, date_iso, k=3):
    """Return the ``k`` dates closest to ``date_iso`` that have active trips.

    ``service_days`` is ``network.json``'s ``{ISO date: active trip count}``.
    Ordered by absolute day distance, ties broken by the earlier date. Days with
    a zero count are ignored. Returns fewer than ``k`` if the feed serves fewer.
    """
    try:
        target = datetime.date.fromisoformat(date_iso)
    except (TypeError, ValueError):
        target = None
    served = [d for d, count in service_days.items() if count]
    if target is None:
        return sorted(served)[:k]
    served.sort(
        key=lambda d: (abs((datetime.date.fromisoformat(d) - target).days), d)
    )
    return served[:k]


def build_od_lines(csv_path, origin_xy, dest_xy, meta, sink, to_crs=None):
    """Add one straight OD line per matrix row to ``sink`` (optional output).

    ``origin_xy`` / ``dest_xy`` map an id to a ``(lon, lat)`` tuple (EPSG:4326).
    ``to_crs`` is an optional ``QgsCoordinateTransform`` applied to each line so
    the sink can carry the caller's CRS. ``meta`` is the run-method dict (PRD 5.2)
    copied onto every feature so two matrices that differ only by percentile are
    still tellable apart. The first travel-time column becomes ``travel_time``.
    """
    from qgis.core import (
        QgsFeature,
        QgsFeatureSink,
        QgsGeometry,
        QgsPointXY,
    )

    added = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        tt_col = next((c for c in reader.fieldnames or [] if c.startswith("travel_time")), None)
        for row in reader:
            o = origin_xy.get(row["from_id"])
            d = dest_xy.get(row["to_id"])
            if o is None or d is None:
                continue
            feat = QgsFeature()
            geom = QgsGeometry.fromPolylineXY(
                [QgsPointXY(o[0], o[1]), QgsPointXY(d[0], d[1])]
            )
            if to_crs is not None:
                geom.transform(to_crs)
            feat.setGeometry(geom)
            tt = row.get(tt_col) if tt_col else ""
            feat.setAttributes(
                [row["from_id"], row["to_id"], float(tt) if tt else None]
                + [meta.get(key) for key in _META_FIELDS]
            )
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            added += 1
    return added


_META_FIELDS = (
    "r5_version",
    "network_hash",
    "run_date",
    "departure_time",
    "time_window",
    "percentile",
    "modes",
)


def od_line_fields():
    """QgsFields for the optional OD-line output layer (see ``build_od_lines``)."""
    from qgis.core import QgsField, QgsFields
    from qgis.PyQt.QtCore import QVariant

    fields = QgsFields()
    fields.append(QgsField("from_id", QVariant.String))
    fields.append(QgsField("to_id", QVariant.String))
    fields.append(QgsField("travel_time", QVariant.Double))
    for name in _META_FIELDS:
        fields.append(QgsField(name, QVariant.String))
    return fields
