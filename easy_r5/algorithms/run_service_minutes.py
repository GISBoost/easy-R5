"""RunServiceMinutes: how many of the departure window's minutes reach each
destination within a cutoff — a reliability metric, per OD pair.

A layer on top of the travel-time matrix (PR_easy-R5_v02_service-minutes.md),
architecturally closest to RunTravelTimeMatrix: no Python-side reduction, the
merged batch CSV *is* the result. R5 already routes every minute of the
departure window internally; ``recordTravelTimeHistograms`` only exposes that
per-minute distribution, and the runner sums it per cutoff.

Not the same number as easy-OTP's service-time classification (`otp_mean` /
`st_class`) — different mechanism (one R5 call per origin vs. 961 separate
OTP surfaces), different reference window (120 min by default vs. 960 min).
See the PRD §1.4 and CONTEXT.md's "Service minutes" entry.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsWkbTypes,
)

from ..core import job_spec, matrix, points
from ._matrix_base import MatrixBase


class RunServiceMinutes(MatrixBase, QgsProcessingAlgorithm):
    CUTOFFS = "CUTOFFS"
    INCLUDE_UNREACHABLE = "INCLUDE_UNREACHABLE"
    OUTPUT_CSV = "OUTPUT_CSV"
    OUTPUT_LAYER = "OUTPUT_LAYER"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("RunServiceMinutes", string)

    def name(self) -> str:
        return "runserviceminutes"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Run service minutes")

    def group(self) -> str:
        return self.tr("Analysis")

    def groupId(self) -> str:  # noqa: N802
        return "analysis"

    def createInstance(self):  # noqa: N802
        return RunServiceMinutes()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "For each origin-destination pair, counts how many of the departure "
            "window's minutes (120 by default) reach the destination within each "
            "cutoff — a reliability metric that a single percentile travel time "
            "hides. R5 already routes every minute of the window internally; this "
            "reads that per-minute distribution instead of a percentile.\n\n"
            "Output: a long CSV (from_id, to_id, svc_min_c<cutoff> per cutoff), "
            "values 0-120. Cutoffs and MAX_TRIP_DURATION must stay below 120 "
            "minutes — R5's histogram is a fixed 120-minute range.\n\n"
            "This is NOT the same number as easy-OTP's service-time classification "
            "(otp_mean / st_class) — different mechanism (one R5 call per origin "
            "vs. many separate OTP surfaces) and a different reference window. Do "
            "not compare the two directly."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self._add_matrix_params(with_percentiles=False)
        self.addParameter(
            QgsProcessingParameterString(
                self.CUTOFFS, self.tr("Cutoffs (minutes, comma-separated)"),
                defaultValue="15,30,45,60",
            )
        )
        self._advanced(
            QgsProcessingParameterBoolean(
                self.INCLUDE_UNREACHABLE,
                self.tr("Keep destinations unreachable in every cutoff as explicit 0 rows"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_CSV, self.tr("Output service-minutes CSV"),
                fileFilter=self.tr("CSV files (*.csv)"),
            )
        )
        od = QgsProcessingParameterFeatureSink(
            self.OUTPUT_LAYER, self.tr("Output OD lines (optional)"),
            optional=True, createByDefault=False,
        )
        od.setFlags(od.flags() | QgsProcessingParameterDefinition.Flag.FlagOptional)
        self.addParameter(od)

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        out_csv = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context))
        max_trip = self.parameterAsInt(parameters, self.MAX_TRIP_DURATION, context)
        include_unreachable = self.parameterAsBool(parameters, self.INCLUDE_UNREACHABLE, context)

        try:
            cutoffs = sorted({int(c) for c in
                              self.parameterAsString(parameters, self.CUTOFFS, context)
                              .replace(",", " ").split()})
        except ValueError:
            raise QgsProcessingException(self.tr("Cutoffs must be whole numbers of minutes."))
        if not cutoffs or cutoffs[0] < 1:
            raise QgsProcessingException(self.tr("Give at least one positive cutoff."))
        # R5's per-minute histogram is a fixed int[120] (0-119 min) regardless of
        # MAX_TRIP_DURATION — see job_spec.HISTOGRAM_MAX_MINUTES. A cutoff or trip
        # budget at/above 120 would make R5 throw deep inside the JVM instead of a
        # clean error, so this is checked here, before Java ever runs.
        if cutoffs[-1] > job_spec.HISTOGRAM_MAX_MINUTES:
            raise QgsProcessingException(self.tr(
                "Cutoffs must be at most {m} minutes — R5 records the "
                "departure-minute histogram in a fixed 120-minute range (0-{m})."
            ).format(m=job_spec.HISTOGRAM_MAX_MINUTES))

        # A cutoff above MAX_TRIP_DURATION would silently truncate the matrix and
        # under-count the larger cutoffs — bump the trip budget to cover them.
        if max(cutoffs) > max_trip:
            feedback.pushWarning(self.tr(
                "MAX_TRIP_DURATION ({t} min) is below the largest cutoff ({c} min) — "
                "raising it to {c} so the count is not under-reported."
            ).format(t=max_trip, c=max(cutoffs)))
            parameters = {**parameters, self.MAX_TRIP_DURATION: max(cutoffs)}
            max_trip = max(cutoffs)
        if max_trip > job_spec.HISTOGRAM_MAX_MINUTES:
            raise QgsProcessingException(self.tr(
                "MAX_TRIP_DURATION must be at most {m} minutes for this algorithm — "
                "R5 records the departure-minute histogram in a fixed 120-minute "
                "range (0-{m})."
            ).format(m=job_spec.HISTOGRAM_MAX_MINUTES))

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_svcmin_"))
        try:
            res = self._run_matrix(
                parameters, context, feedback, tmp=tmp, matrix_csv=out_csv,
                walk_fallback=max(cutoffs), include_unreachable=include_unreachable,
                service_minute_cutoffs=cutoffs,
            )
            meta = {**res["meta"], "cutoffs": ",".join(str(c) for c in cutoffs)}
            Path(str(out_csv) + ".meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )
            feedback.pushInfo(self.tr("Wrote {p}").format(p=out_csv))

            outputs = {self.OUTPUT_CSV: str(out_csv)}
            od_sink = self._build_od_layer(
                parameters, context, out_csv, res["origins_csv"], res["dests_csv"], meta,
                res["origins_crs"], cutoffs,
            )
            if od_sink is not None:
                outputs[self.OUTPUT_LAYER] = od_sink
            return outputs
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _build_od_layer(self, parameters, context, out_csv, origins_csv, dests_csv, meta,
                        origins_crs, cutoffs):
        if parameters.get(self.OUTPUT_LAYER) in (None, ""):
            return None
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform

        sink, sink_id = self.parameterAsSink(
            parameters, self.OUTPUT_LAYER, context,
            matrix.service_minute_line_fields(cutoffs), QgsWkbTypes.Type.LineString, origins_crs,
        )
        if sink is None:
            return None
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        to_crs = (QgsCoordinateTransform(wgs84, origins_crs, context.transformContext())
                  if origins_crs != wgs84 else None)
        matrix.build_service_minute_lines(
            out_csv, points.read_points_csv(origins_csv), points.read_points_csv(dests_csv),
            meta, cutoffs, sink, to_crs,
        )
        return sink_id
