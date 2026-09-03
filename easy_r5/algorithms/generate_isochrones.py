"""GenerateIsochrones: travel-time isochrone polygons from N origin points.

R5 does not produce polygons (r5r/r5py/Conveyal all contour outside Java —
``docs/notes/r5-engine-primer.md`` §5), so this builds a regular destination
grid, runs a one-origin matrix against it (shared ``MatrixBase`` machinery),
rasterises the travel times and contours each cutoff in QGIS/GDAL.

If contouring fails for one cutoff (a fragmented surface can break GDAL — r5r
hit a deterministic isoband failure once), that cutoff is reported and skipped;
the others still come out.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import processing
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsRectangle,
    QgsWkbTypes,
)

from ..core.styling import apply_style
from ._matrix_base import MatrixBase


class GenerateIsochrones(MatrixBase, QgsProcessingAlgorithm):
    CUTOFFS = "CUTOFFS"
    GRID_SPACING = "GRID_SPACING"
    OUTPUT_LAYER = "OUTPUT_LAYER"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("GenerateIsochrones", string)

    def name(self) -> str:
        return "generateisochrones"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Generate isochrones")

    def group(self) -> str:
        return self.tr("Analysis")

    def groupId(self) -> str:  # noqa: N802
        return "analysis"

    def createInstance(self):  # noqa: N802
        return GenerateIsochrones()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Travel-time isochrone polygons from one or more origin points, for "
            "one or more cutoffs. Builds a regular destination grid "
            "(GRID_SPACING, metres), runs a one-origin matrix against it, then "
            "contours each cutoff.\n\n"
            "One output feature per (origin, cutoff), tagged origin_id and "
            "cutoff_min. Polygons are cumulative — the 30-minute area contains "
            "the 15-minute one. Interior holes are kept where an area is "
            "genuinely unreachable (a lake, a rail yard, a street-network gap).\n\n"
            "R5 does not contour — that is done here. If one cutoff fails it is "
            "reported and skipped; the rest still come out. Grid cost is "
            "quadratic in 1/GRID_SPACING and blocked above ~400k points. "
            "MAX_WALK_TIME defaults to max(CUTOFFS) — lossless and the biggest "
            "speed lever."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self._add_matrix_params(
            self.tr("Percentiles (1-99, ascending, up to 5)"), with_destinations=False
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.CUTOFFS, self.tr("Cutoffs (minutes, comma-separated)"),
                defaultValue="15,30,45",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GRID_SPACING, self.tr("Grid spacing (metres)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=250, minValue=25,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LAYER, self.tr("Output isochrones"),
                type=QgsProcessing.TypeVectorPolygon,
            )
        )

    _MAX_GRID_POINTS = 400_000

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        spacing = self.parameterAsInt(parameters, self.GRID_SPACING, context)
        try:
            cutoffs = sorted({int(c) for c in
                              self.parameterAsString(parameters, self.CUTOFFS, context)
                              .replace(",", " ").split()})
        except ValueError:
            raise QgsProcessingException(self.tr("Cutoffs must be whole numbers of minutes."))
        if not cutoffs or cutoffs[0] < 1:
            raise QgsProcessingException(self.tr("Give at least one positive cutoff."))

        origins_src = self.parameterAsSource(parameters, self.ORIGINS, context)
        if origins_src is None:
            raise QgsProcessingException(self.tr("Origin points are required."))
        origins_crs = origins_src.sourceCrs()
        if not origins_crs.isValid():
            raise QgsProcessingException(
                self.tr("The origin layer has no valid CRS — set it before running."))

        metric = self._metric_crs(origins_src, context)
        grid_layer = self._build_grid(origins_src, context, metric, spacing, cutoffs, feedback)

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_iso_"))
        try:
            matrix_csv = tmp / "matrix.csv"
            res = self._run_matrix(
                parameters, context, feedback, tmp=tmp, matrix_csv=matrix_csv,
                walk_fallback=max(cutoffs), dests_source=grid_layer, dest_id_field="gid",
            )
            meta = res["meta"]

            # output in the origin layer's CRS, like RunAccessibility
            sink, sink_id = self.parameterAsSink(
                parameters, self.OUTPUT_LAYER, context, self._out_fields(),
                QgsWkbTypes.MultiPolygon, origins_crs,
            )
            if sink is None:
                raise QgsProcessingException(self.tr("Could not create the output layer."))

            times = self._times_by_origin(matrix_csv, res["percentiles"][0])
            to_out = QgsCoordinateTransform(metric, origins_crs, context.transformContext())
            grid_xy = {f["gid"]: f.geometry().asPoint() for f in grid_layer.getFeatures()}

            meta_values = [meta.get(k) for k in ("departure_time", "percentiles", "r5_version",
                                                 "network_hash", "run_date", "modes")]
            written = 0
            for origin_id in res["origin_ids"]:
                per = times.get(origin_id, {})
                if not per:
                    feedback.pushWarning(
                        self.tr("Origin {} reached no grid cell — no isochrone.").format(origin_id))
                    continue
                written += self._blob_isochrones(
                    per, grid_xy, spacing, cutoffs, to_out, origin_id, meta_values, sink, feedback
                )
            feedback.pushInfo(self.tr("{} isochrone polygons written.").format(written))
            apply_style(context, sink_id, "isochrones.qml")
            return {self.OUTPUT_LAYER: sink_id}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # --- grid ----------------------------------------------------------

    def _metric_crs(self, source, context):
        """A metre-based working CRS for buffering: the UTM zone under the origins'
        centroid. Only used internally for the grid + blob geometry; the output
        layer is written back in the origin layer's own CRS."""
        ext = source.sourceExtent()
        c = source.sourceCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if c != wgs84:
            ext = QgsCoordinateTransform(c, wgs84, context.transformContext()) \
                .transformBoundingBox(ext)
        lon, lat = ext.center().x(), ext.center().y()
        zone = min(60, max(1, int((lon + 180) / 6) + 1))
        epsg = (32600 if lat >= 0 else 32700) + zone
        metric = QgsCoordinateReferenceSystem("EPSG:{}".format(epsg))
        if not metric.isValid():
            raise QgsProcessingException(
                self.tr("Could not derive a metric CRS for the origins (EPSG:{}).").format(epsg))
        return metric

    def _build_grid(self, source, context, metric, spacing, cutoffs, feedback):
        to_metric = QgsCoordinateTransform(source.sourceCrs(), metric, context.transformContext())
        ext = to_metric.transformBoundingBox(source.sourceExtent())
        # reach padding: ~0.9 km per cutoff-minute (≈ 54 km/h) covers transit /
        # car within a metro area without an absurdly large grid
        pad = max(cutoffs) * 900
        ext = QgsRectangle(ext.xMinimum() - pad, ext.yMinimum() - pad,
                           ext.xMaximum() + pad, ext.yMaximum() + pad)
        n = (ext.width() / spacing) * (ext.height() / spacing)
        if n > self._MAX_GRID_POINTS:
            raise QgsProcessingException(self.tr(
                "Grid would be ~{n:,.0f} points ({w:.0f} x {h:.0f} m at {s} m). Increase "
                "GRID_SPACING or use fewer / closer origins."
            ).format(n=n, w=ext.width(), h=ext.height(), s=spacing))
        feedback.pushInfo(
            self.tr("Destination grid: up to ~{:,.0f} points at {} m (clipped to origin reach).")
            .format(n, spacing))

        grid = processing.run("native:creategrid", {
            "TYPE": 0, "EXTENT": ext, "HSPACING": spacing, "VSPACING": spacing,
            "HOVERLAY": 0, "VOVERLAY": 0, "CRS": metric, "OUTPUT": "memory:",
        }, context=context, feedback=None)["OUTPUT"]
        # keep only cells within `pad` of an origin — drops the bbox corners that
        # spread origins would otherwise fill with unreachable points
        origins_layer = source.materialize(QgsFeatureRequest())
        origins_metric = processing.run("native:reprojectlayer", {
            "INPUT": origins_layer, "TARGET_CRS": metric, "OUTPUT": "memory:",
        }, context=context, feedback=None)["OUTPUT"]
        grid = processing.run("native:extractwithindistance", {
            "INPUT": grid, "REFERENCE": origins_metric, "DISTANCE": pad, "OUTPUT": "memory:",
        }, context=context, feedback=None)["OUTPUT"]
        grid.dataProvider().addAttributes([QgsField("gid", QVariant.String)])
        grid.updateFields()
        gi = grid.fields().lookupField("gid")
        grid.startEditing()
        for i, f in enumerate(grid.getFeatures()):
            grid.changeAttributeValue(f.id(), gi, "g{}".format(i))
        grid.commitChanges()
        return grid

    # --- per-origin contouring --------------------------------------

    def _times_by_origin(self, matrix_csv, percentile):
        import csv

        col = "travel_time_p{}".format(percentile)
        out = {}
        with open(matrix_csv, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                v = row.get(col, "")
                if v != "":
                    out.setdefault(row["from_id"], {})[row["to_id"]] = int(v)
        return out

    def _blob_isochrones(self, per, grid_xy, spacing, cutoffs, to_out, origin_id,
                         meta_values, sink, feedback):
        """One filled polygon per cutoff: the union of reachable grid cells.

        Cumulative — the 30-minute polygon fully contains the 15-minute one.
        Interior rings are **kept**: an unreachable pocket inside the reachable
        area (a lake, a rail yard, a gap in the street network) is a real
        no-service hole and belongs in the isochrone. Only sub-cell specks are
        smoothed away by the close/open pass. Robust where GDAL contouring is
        not; one cutoff failing does not stop the rest.
        """
        r = spacing * 0.72  # > half-diagonal of a spacing-sized cell
        written = 0
        for c in cutoffs:
            try:
                squares = [
                    QgsGeometry.fromPointXY(grid_xy[gid]).buffer(r, 1)
                    for gid, tt in per.items()
                    if tt < c and gid in grid_xy
                ]
                if not squares:
                    continue
                blob = QgsGeometry.unaryUnion(squares)
                # round the staircase and fill sub-cell specks, keeping real holes
                blob = blob.buffer(spacing * 0.5, 4).buffer(-spacing * 0.5, 4).makeValid()
                if blob.isEmpty():
                    continue
                blob.transform(to_out)
                if not blob.isMultipart():
                    blob.convertToMultiType()
                out = QgsFeature(self._out_fields())
                out.setGeometry(blob)
                out.setAttributes([str(origin_id), c] + meta_values)
                sink.addFeature(out, QgsFeatureSink.FastInsert)
                written += 1
            except Exception as exc:  # noqa: BLE001
                feedback.pushWarning(
                    self.tr("Origin {}: cutoff {} min failed ({}) — skipped.").format(
                        origin_id, c, exc))
        return written

    @staticmethod
    def _out_fields():
        f = QgsFields()
        f.append(QgsField("origin_id", QVariant.String))
        f.append(QgsField("cutoff_min", QVariant.Int))
        f.append(QgsField("departure_time", QVariant.String))
        f.append(QgsField("percentile", QVariant.String))
        f.append(QgsField("r5_version", QVariant.String))
        f.append(QgsField("network_hash", QVariant.String))
        f.append(QgsField("run_date", QVariant.String))
        f.append(QgsField("modes", QVariant.String))
        return f
