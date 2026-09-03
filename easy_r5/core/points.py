"""Turn a QGIS point layer into the ``id,lon,lat`` CSV the R5 runner reads.

``stable_ids`` is pure stdlib and unit-tested. ``write_points_csv`` touches the
QGIS API (CRS transform, geometry) and is exercised by the pipeline tests, not
the unit suite — the test harness stubs QGIS with MagicMock.

The CSV column order (``id,lon,lat``) and the 6-decimal rounding match
``docs/reference/probe/Probe.java`` so a matrix result can be compared to the
probe origin for origin.
"""

from __future__ import annotations

import csv


def stable_ids(values, n):
    """Return ``n`` unique string ids.

    ``values`` None -> zero-padded row indices (``"0001"``); the width tracks
    ``n`` so ids sort lexicographically in file order. ``values`` given -> each
    stringified; raises ``ValueError`` if the result has duplicates, because the
    matrix keys OD pairs by id and a collision silently merges rows.
    """
    if values is None:
        width = max(1, len(str(n - 1))) if n else 1
        return ["{:0{w}d}".format(i, w=width) for i in range(n)]
    ids = [str(v) for v in values]
    if len(set(ids)) != len(ids):
        raise ValueError(
            "The chosen id field has duplicate values — pick a unique field "
            "or leave it blank to use the feature id."
        )
    if any(c in v for v in ids for c in (",", '"', "\n", "\r")):
        raise ValueError(
            "An id contains a comma, quote or newline — the runner reads a plain "
            "id,lon,lat CSV. Pick a cleaner id field."
        )
    return ids


def write_points_csv(source, context, feedback, id_field, out_path, *, label="points"):
    """Write ``source`` as ``id,lon,lat`` in EPSG:4326. Returns (ids, skipped).

    Rejects a non-point layer (``ValueError``). Features with null/empty
    geometry are skipped with a warning; a multipoint uses its centroid.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsWkbTypes,
    )

    if QgsWkbTypes.geometryType(source.wkbType()) != QgsWkbTypes.PointGeometry:
        raise ValueError(
            "{} layer must be a point layer (got {}).".format(
                label, QgsWkbTypes.displayString(source.wkbType())
            )
        )

    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    src_crs = source.sourceCrs()
    transform = (
        QgsCoordinateTransform(src_crs, wgs84, context.transformContext())
        if src_crs != wgs84
        else None
    )

    raw_ids = []
    coords = []
    skipped = 0
    field_idx = source.fields().lookupField(id_field) if id_field else -1
    for feat in source.getFeatures():
        geom = feat.geometry()
        if geom.isNull() or geom.isEmpty():
            skipped += 1
            if feedback is not None:
                feedback.pushWarning(
                    "{} feature {} has no geometry — skipped.".format(label, feat.id())
                )
            continue
        pt = geom.centroid().asPoint()
        if transform is not None:
            pt = transform.transform(pt)
        raw_ids.append(feat.attribute(field_idx) if field_idx >= 0 else None)
        coords.append((round(pt.x(), 6), round(pt.y(), 6)))

    id_values = None if field_idx < 0 else raw_ids
    ids = stable_ids(id_values, len(coords))

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "lon", "lat"])
        for pid, (lon, lat) in zip(ids, coords):
            writer.writerow([pid, lon, lat])

    return ids, skipped


def read_points_csv(path):
    """Read an ``id,lon,lat`` CSV back into ``{id: (lon, lat)}`` (floats).

    Used to place the optional OD-line output — the algorithm already wrote this
    file for the runner, so re-reading it is cheaper than threading coordinates
    through the whole call.
    """
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["id"]] = (float(row["lon"]), float(row["lat"]))
    return out
