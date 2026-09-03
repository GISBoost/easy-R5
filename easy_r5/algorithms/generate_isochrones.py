"""GenerateIsochrones: travel-time isochrone polygons from N origin points.

R5 has no native isochrone output — no engine version ships one. Every consumer
does the same thing (``docs/notes/r5-engine-primer.md`` §5):

* **r5r** ``isochrone()`` — R5 travel times to a grid, then contours them in R
  with the ``isoband`` package;
* **r5py** — hex grid of destinations, a travel-time matrix, then polygonise
  in Python (shapely);
* **Conveyal Analysis** — a travel-time grid, contoured in the browser.

This algorithm is the QGIS equivalent: a regular destination grid → a one-origin
matrix (shared ``MatrixBase`` machinery) → a TIN-interpolated travel-time raster
→ ``gdal:contour_polygon`` per cutoff. Same marching-squares contouring r5r's
``isoband`` does, just in GDAL. Contouring is run once per cutoff so a failure on
one (r5r hit a deterministic isoband bug on a fragmented surface) is reported and
skipped without losing the others.
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
    QgsVectorLayer,
    QgsWkbTypes,
)

from ..core import job_spec
from ..core.matrix import utm_epsg
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
            "(GRID_SPACING, metres), runs a one-origin matrix against it, "
            "interpolates the times to a raster (TIN) and marching-squares "
            "contours each cutoff — the same approach r5r/r5py/Conveyal use; "
            "R5 itself has no isochrone output.\n\n"
            "One output feature per (origin, cutoff), tagged origin_id and "
            "cutoff_min, in the origin layer's CRS. Polygons are cumulative — "
            "the 30-minute area contains the 15-minute one. Interior holes are "
            "kept where an area is genuinely unreachable (a lake, a rail yard, a "
            "street-network gap); noise smaller than a few grid cells is dropped.\n\n"
            "Contouring runs once per cutoff, so a failure on one is reported "
            "and skipped without losing the rest. Grid cost is quadratic in "
            "1/GRID_SPACING and blocked above ~400k points. MAX_WALK_TIME "
            "defaults to max(CUTOFFS) — lossless and the biggest speed lever."
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

        # One contour = one travel-time surface = one percentile. A list would
        # produce polygons mislabelled with every requested percentile at once.
        try:
            pcts = job_spec.parse_percentiles(
                self.parameterAsString(parameters, self.PERCENTILES, context))
        except job_spec.JobSpecError as exc:
            raise QgsProcessingException(str(exc))
        if len(pcts) != 1:
            raise QgsProcessingException(self.tr(
                "Isochrones need exactly one percentile (got {}). Run the tool once "
                "per percentile.").format(len(pcts)))

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

            percentile = res["percentiles"][0]
            times = self._times_by_origin(matrix_csv, percentile)
            to_out = QgsCoordinateTransform(metric, origins_crs, context.transformContext())
            grid_xy = {f["gid"]: f.geometry().asPoint() for f in grid_layer.getFeatures()}

            meta_values = [meta.get("departure_time"), meta.get("time_window"), percentile,
                           meta.get("r5_version"), meta.get("network_hash"),
                           meta.get("run_date"), meta.get("modes")]
            written = 0
            for origin_id in res["origin_ids"]:
                per = times.get(origin_id, {})
                if not per:
                    feedback.pushWarning(
                        self.tr("Origin {} reached no grid cell — no isochrone.").format(origin_id))
                    continue
                written += self._contour_isochrones(
                    per, grid_xy, spacing, cutoffs, metric, to_out, origin_id, meta_values,
                    sink, feedback, context,
                )
            feedback.pushInfo(self.tr("{} isochrone polygons written.").format(written))
            apply_style(context, sink_id, "isochrones.qml")
            return {self.OUTPUT_LAYER: sink_id}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # --- grid ----------------------------------------------------------

    def _metric_crs(self, source, context):
        """A metre-based working CRS for buffering: the UTM zone under the origins'
        centroid. Only used internally for the grid, raster and contour geometry;
        the output layer is written back in the origin layer's own CRS."""
        ext = source.sourceExtent()
        c = source.sourceCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if c != wgs84:
            ext = QgsCoordinateTransform(c, wgs84, context.transformContext()) \
                .transformBoundingBox(ext)
        lon, lat = ext.center().x(), ext.center().y()
        epsg = utm_epsg(lon, lat)
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
        # ESTIMATE_FIRST samples origins, and isochrones have one — so it never
        # fires here. The cost is in the grid instead; warn if it is large.
        if n > 100_000:
            feedback.pushWarning(self.tr(
                "~{:,.0f} grid cells is a heavy one-origin run. If it is too slow, "
                "raise GRID_SPACING or use fewer / closer origins.").format(n))

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

    def _time_raster(self, per, grid_xy, spacing, metric, cutoffs, context):
        """TIN-interpolate the origin's travel times over the whole grid to a raster.

        Every grid cell gets a value: its travel time if reached, otherwise a
        sentinel well above the largest cutoff so the outermost contour closes at
        the reachable edge rather than at the convex hull of reached cells.
        """
        sentinel = float(max(cutoffs) * 3 + 60)
        lyr = QgsVectorLayer("Point?crs={}".format(metric.authid()), "iso_t", "memory")
        dp = lyr.dataProvider()
        dp.addAttributes([QgsField("t", QVariant.Double)])
        lyr.updateFields()
        feats = []
        xs = []
        ys = []
        for gid, xy in grid_xy.items():
            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(xy))
            f.setAttributes([float(per.get(gid, sentinel))])
            feats.append(f)
            xs.append(xy.x())
            ys.append(xy.y())
        dp.addFeatures(feats)
        lyr.updateExtents()
        context.temporaryLayerStore().addMapLayer(lyr)

        ext = QgsRectangle(min(xs) - spacing, min(ys) - spacing,
                           max(xs) + spacing, max(ys) + spacing)
        return processing.run("qgis:tininterpolation", {
            "INTERPOLATION_DATA": "{}::~::0::~::0::~::0".format(lyr.id()),
            "METHOD": 0, "EXTENT": ext, "PIXEL_SIZE": max(10.0, spacing / 2.0),
            "OUTPUT": "TEMPORARY_OUTPUT",
        }, context=context, feedback=None)["OUTPUT"]

    def _contour_isochrones(self, per, grid_xy, spacing, cutoffs, metric, to_out,
                            origin_id, meta_values, sink, feedback, context):
        """One cumulative polygon per cutoff, marching-squares contoured.

        The 30-minute polygon fully contains the 15-minute one. Interior rings
        are **kept** where the surface genuinely never dips under the cutoff — a
        lake, a rail yard, a street-network gap. Rings smaller than a few grid
        cells are dropped as interpolation noise. Contouring runs once per cutoff
        so one failure does not lose the rest.
        """
        try:
            raster = self._time_raster(per, grid_xy, spacing, metric, cutoffs, context)
        except Exception as exc:  # noqa: BLE001
            feedback.pushWarning(
                self.tr("Origin {}: could not build the travel-time raster ({}).").format(
                    origin_id, exc))
            return 0

        min_ring = spacing * spacing * 4.0
        written = 0
        for c in cutoffs:
            try:
                bands = processing.run("gdal:contour_polygon", {
                    "INPUT": raster, "BAND": 1, "INTERVAL": 0, "EXTRA": "-fl {}".format(c),
                    "FIELD_NAME_MIN": "lmin", "FIELD_NAME_MAX": "lmax",
                    "CREATE_3D": False, "IGNORE_NODATA": False, "OFFSET": 0,
                    "OUTPUT": "TEMPORARY_OUTPUT",
                }, context=context, feedback=None)["OUTPUT"]
                lyr = bands if not isinstance(bands, str) else QgsVectorLayer(bands, "b", "ogr")
                inside = [
                    QgsGeometry(ft.geometry()) for ft in lyr.getFeatures()
                    if ft["lmax"] is not None and ft["lmax"] <= c + 1e-6
                    and ft.geometry() and not ft.geometry().isEmpty()
                ]
                if not inside:
                    continue
                geom = QgsGeometry.unaryUnion(inside).makeValid()
                trimmed = geom.removeInteriorRings(min_ring)
                if trimmed is not None and not trimmed.isEmpty():
                    geom = trimmed
                if geom.isEmpty():
                    continue
                geom.transform(to_out)
                if not geom.isMultipart():
                    geom.convertToMultiType()
                out = QgsFeature(self._out_fields())
                out.setGeometry(geom)
                out.setAttributes([str(origin_id), c] + meta_values)
                sink.addFeature(out, QgsFeatureSink.FastInsert)
                written += 1
            except Exception as exc:  # noqa: BLE001
                feedback.pushWarning(
                    self.tr("Origin {}: cutoff {} min failed to contour ({}) — skipped.").format(
                        origin_id, c, exc))
        return written

    @staticmethod
    def _out_fields():
        f = QgsFields()
        f.append(QgsField("origin_id", QVariant.String))
        f.append(QgsField("cutoff_min", QVariant.Int))
        f.append(QgsField("departure_time", QVariant.String))
        f.append(QgsField("time_window", QVariant.String))
        f.append(QgsField("percentile", QVariant.Int))
        f.append(QgsField("r5_version", QVariant.String))
        f.append(QgsField("network_hash", QVariant.String))
        f.append(QgsField("run_date", QVariant.String))
        f.append(QgsField("modes", QVariant.String))
        return f
