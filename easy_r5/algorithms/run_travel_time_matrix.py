"""RunTravelTimeMatrix: one-to-many / many-to-many travel times over a departure
window, computed by R5 and written as a long-format CSV.

This is the flagship algorithm. The shared machinery — gates, point export,
sampled estimate, batched processes, walk-only guard — lives in
``_matrix_base.MatrixBase``; this class only adds the CSV/OD-line outputs.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFileDestination,
    QgsWkbTypes,
)

from ..core import matrix, points
from ..core.styling import apply_style
from ._matrix_base import MatrixBase


class RunTravelTimeMatrix(MatrixBase, QgsProcessingAlgorithm):
    INCLUDE_UNREACHABLE = "INCLUDE_UNREACHABLE"
    OUTPUT_CSV = "OUTPUT_CSV"
    OUTPUT_LAYER = "OUTPUT_LAYER"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("RunTravelTimeMatrix", string)

    def name(self) -> str:
        return "runtraveltimematrix"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Run travel time matrix")

    def group(self) -> str:
        return self.tr("Analysis")

    def groupId(self) -> str:  # noqa: N802
        return "analysis"

    def createInstance(self):  # noqa: N802
        return RunTravelTimeMatrix()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Computes travel times from every origin point to every destination "
            "point over a departure-time window, using a network built by "
            "BuildNetwork. Output is a long-format CSV: from_id, to_id, and one "
            "travel_time_p<percentile> column per requested percentile "
            "(minutes; unreachable pairs are omitted, or left blank with "
            "INCLUDE_UNREACHABLE).\n\n"
            "The run is blocked if the GTFS feed has no trips on DATE — R5 would "
            "otherwise silently return walk-only results. ESTIMATE_FIRST times a "
            "spread sample of origins and reports an extrapolation before the "
            "full run; cost scales with network complexity, so the estimate is "
            "measured, not guessed.\n\n"
            "Accessibility and isochrones are separate algorithms."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self._add_matrix_params(self.tr("Percentiles (1-99, ascending, up to 5)"))
        self._advanced(
            QgsProcessingParameterBoolean(
                self.INCLUDE_UNREACHABLE,
                self.tr("Keep unreachable pairs as blank-value rows"), defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_CSV, self.tr("Output matrix CSV"),
                fileFilter=self.tr("CSV files (*.csv)"),
            )
        )
        od = QgsProcessingParameterFeatureSink(
            self.OUTPUT_LAYER, self.tr("Output OD lines (optional)"),
            optional=True, createByDefault=False,
        )
        od.setFlags(od.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(od)

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        out_csv = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context))
        max_trip = self.parameterAsInt(parameters, self.MAX_TRIP_DURATION, context)
        include_unreachable = self.parameterAsBool(parameters, self.INCLUDE_UNREACHABLE, context)

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_matrix_"))
        try:
            res = self._run_matrix(
                parameters, context, feedback, tmp=tmp, matrix_csv=out_csv,
                walk_fallback=max_trip, include_unreachable=include_unreachable,
            )
            meta = res["meta"]
            Path(str(out_csv) + ".meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )
            feedback.pushInfo(self.tr("Wrote {p}").format(p=out_csv))

            outputs = {self.OUTPUT_CSV: str(out_csv)}
            od_sink = self._build_od_layer(
                parameters, context, out_csv, res["origins_csv"], res["dests_csv"], meta
            )
            if od_sink is not None:
                outputs[self.OUTPUT_LAYER] = od_sink
                apply_style(context, od_sink, "od_lines.qml")
            return outputs
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _build_od_layer(self, parameters, context, out_csv, origins_csv, dests_csv, meta):
        if parameters.get(self.OUTPUT_LAYER) in (None, ""):
            return None
        from qgis.core import QgsCoordinateReferenceSystem

        sink, sink_id = self.parameterAsSink(
            parameters, self.OUTPUT_LAYER, context,
            matrix.od_line_fields(), QgsWkbTypes.LineString,
            QgsCoordinateReferenceSystem("EPSG:4326"),
        )
        if sink is None:
            return None
        matrix.build_od_lines(
            out_csv, points.read_points_csv(origins_csv), points.read_points_csv(dests_csv),
            meta, sink,
        )
        return sink_id
