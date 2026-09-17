"""BuildScenario: write an R5 scenario file from QGIS layers (PR_easy-R5_v03.md R-1).

The file feeds the SCENARIO parameter of every matrix-based algorithm; R5
applies it to the network in memory, so nothing is rebuilt. JSON assembly lives
in ``core/scenario.py``; this class only reads the layer and parameters.
"""

from __future__ import annotations

import json
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
)

from ..core import scenario

_MODES = list(scenario.LINE_MODES)


class BuildScenario(QgsProcessingAlgorithm):
    NEW_LINES = "NEW_LINES"
    LINE_NAME_FIELD = "LINE_NAME_FIELD"
    NEW_LINE_MODE = "NEW_LINE_MODE"
    SPEED_KMH = "SPEED_KMH"
    DWELL_SECONDS = "DWELL_SECONDS"
    HEADWAY_MINUTES = "HEADWAY_MINUTES"
    SERVICE_START = "SERVICE_START"
    SERVICE_END = "SERVICE_END"
    BIDIRECTIONAL = "BIDIRECTIONAL"
    REMOVE_ROUTES = "REMOVE_ROUTES"
    SPEED_ROUTES = "SPEED_ROUTES"
    SPEED_SCALE = "SPEED_SCALE"
    HEADWAY_ROUTES = "HEADWAY_ROUTES"
    NEW_HEADWAY_MINUTES = "NEW_HEADWAY_MINUTES"
    HEADWAY_START = "HEADWAY_START"
    HEADWAY_END = "HEADWAY_END"
    OUTPUT_SCENARIO = "OUTPUT_SCENARIO"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("BuildScenario", string)

    def name(self) -> str:
        return "buildscenario"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Build scenario")

    def group(self) -> str:
        return self.tr("Scenarios")

    def groupId(self) -> str:  # noqa: N802
        return "scenarios"

    def createInstance(self):  # noqa: N802
        return BuildScenario()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Writes a scenario file describing changes to the transit network: new lines "
            "drawn in QGIS, existing routes removed, slowed down or sped up, or given a new "
            "headway. Give the file to the SCENARIO parameter (Advanced) of Run travel time "
            "matrix, Run accessibility, Run service minutes, Generate isochrones or Run "
            "competitive accessibility — R5 applies it to the network in memory, nothing is "
            "rebuilt. Then compare against the baseline run with Compare scenarios.\n\n"
            "New lines: every vertex of a line feature is a stop, in drawing order. Travel "
            "time between stops = straight-line distance / SPEED_KMH, so set a realistic "
            "commercial speed. Each line runs every HEADWAY_MINUTES between SERVICE_START "
            "and SERVICE_END on every day.\n\n"
            "Routes are matched by short name (e.g. 86), GTFS route_id, or feed:route_id; "
            "list them comma-separated. Check transit data writes the full route list. "
            "SPEED_SCALE 0.8 = 20% slower, 1.25 = 25% faster."
        )

    def _advanced(self, param):
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.Flag.FlagAdvanced)
        self.addParameter(param)

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.NEW_LINES, self.tr("New lines (vertices = stops)"),
            [QgsProcessing.SourceType.TypeVectorLine], optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.LINE_NAME_FIELD, self.tr("Line name field"), parentLayerParameterName=self.NEW_LINES,
            optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.NEW_LINE_MODE, self.tr("New line mode"), options=_MODES, defaultValue=_MODES.index("BUS")))
        self.addParameter(QgsProcessingParameterNumber(
            self.SPEED_KMH, self.tr("New line speed between stops (km/h)"),
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=25.0, minValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.HEADWAY_MINUTES, self.tr("New line headway (minutes)"),
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=10.0, minValue=0.5))
        self.addParameter(QgsProcessingParameterString(
            self.SERVICE_START, self.tr("New line service start (HH:mm)"), defaultValue="05:00"))
        self.addParameter(QgsProcessingParameterString(
            self.SERVICE_END, self.tr("New line service end (HH:mm)"), defaultValue="23:00"))
        self._advanced(QgsProcessingParameterNumber(
            self.DWELL_SECONDS, self.tr("New line dwell time at each stop (seconds)"),
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=30, minValue=0))
        self._advanced(QgsProcessingParameterBoolean(
            self.BIDIRECTIONAL, self.tr("New lines run both ways"), defaultValue=True))
        self.addParameter(QgsProcessingParameterString(
            self.REMOVE_ROUTES, self.tr("Remove routes (comma-separated)"), optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.SPEED_ROUTES, self.tr("Change speed of routes (comma-separated)"), optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.SPEED_SCALE, self.tr("Speed factor for those routes (0.8 = 20% slower)"),
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=1.0, minValue=0.05))
        self.addParameter(QgsProcessingParameterString(
            self.HEADWAY_ROUTES, self.tr("Set a new headway on routes (comma-separated)"), optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.NEW_HEADWAY_MINUTES, self.tr("New headway for those routes (minutes)"),
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=10.0, minValue=0.5))
        self._advanced(QgsProcessingParameterString(
            self.HEADWAY_START, self.tr("New headway from (HH:mm)"), defaultValue="05:00"))
        self._advanced(QgsProcessingParameterString(
            self.HEADWAY_END, self.tr("New headway until (HH:mm)"), defaultValue="23:00"))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_SCENARIO, self.tr("Scenario file"), fileFilter=self.tr("Scenario (*.json)")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        mode = _MODES[self.parameterAsEnum(parameters, self.NEW_LINE_MODE, context)]
        line_kw = dict(
            mode=mode,
            speed_kmh=self.parameterAsDouble(parameters, self.SPEED_KMH, context),
            dwell_seconds=self.parameterAsInt(parameters, self.DWELL_SECONDS, context),
            headway_minutes=self.parameterAsDouble(parameters, self.HEADWAY_MINUTES, context),
            start=self.parameterAsString(parameters, self.SERVICE_START, context),
            end=self.parameterAsString(parameters, self.SERVICE_END, context),
            bidirectional=self.parameterAsBool(parameters, self.BIDIRECTIONAL, context),
        )
        out_path = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_SCENARIO, context))

        try:
            new_lines = self._new_lines(parameters, context, line_kw, feedback)
            data = scenario.build_scenario(
                new_lines=new_lines,
                remove_routes=scenario.parse_route_list(
                    self.parameterAsString(parameters, self.REMOVE_ROUTES, context)),
                speed_routes=scenario.parse_route_list(
                    self.parameterAsString(parameters, self.SPEED_ROUTES, context)),
                speed_scale=self.parameterAsDouble(parameters, self.SPEED_SCALE, context),
                headway_routes=scenario.parse_route_list(
                    self.parameterAsString(parameters, self.HEADWAY_ROUTES, context)),
                headway_minutes=self.parameterAsDouble(parameters, self.NEW_HEADWAY_MINUTES, context),
                headway_start=self.parameterAsString(parameters, self.HEADWAY_START, context),
                headway_end=self.parameterAsString(parameters, self.HEADWAY_END, context),
                scenario_id=out_path.stem,
            )
        except scenario.ScenarioError as exc:
            raise QgsProcessingException(str(exc))

        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for m in data["modifications"]:
            if m["type"] == "add-trips":
                feedback.pushInfo(self.tr("New line {n}: {s} stops, {m} min end to end.").format(
                    n=m.get("comment", ""), s=len(m["stops"]),
                    m=round(sum(m["frequencies"][0]["hopTimes"]) / 60, 1)))
            else:
                feedback.pushInfo("{}: {}".format(m["type"], ", ".join(m["routes"])))
        feedback.pushInfo(self.tr(
            "Route names are checked against the network when an analysis runs. Wrote {p}").format(p=out_path))
        return {self.OUTPUT_SCENARIO: str(out_path)}

    def _new_lines(self, parameters, context, line_kw, feedback):
        if parameters.get(self.NEW_LINES) in (None, ""):
            return []
        source = self.parameterAsSource(parameters, self.NEW_LINES, context)
        if source is None:
            return []
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if not source.sourceCrs().isValid():
            raise QgsProcessingException(self.tr("The new-lines layer has no valid CRS."))
        xform = QgsCoordinateTransform(source.sourceCrs(), wgs84, context.transformContext())
        name_field = self.parameterAsString(parameters, self.LINE_NAME_FIELD, context)
        out = []
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                feedback.pushWarning(self.tr("Line feature {} has no geometry — skipped.").format(feat.id()))
                continue
            geom.transform(xform)
            parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
            base = str(feat[name_field]) if name_field else "line-{}".format(feat.id())
            for i, part in enumerate(parts):
                name = base if len(parts) == 1 else "{}-{}".format(base, i + 1)
                try:
                    out.append(scenario.line_to_add_trips(
                        [(p.x(), p.y()) for p in part], name=name, **line_kw))
                except scenario.ScenarioError as exc:
                    raise QgsProcessingException("{}: {}".format(name, exc))
        return out
