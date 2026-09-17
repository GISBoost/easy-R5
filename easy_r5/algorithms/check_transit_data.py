"""CheckTransitData: GTFS pre-flight diagnostics before a network build (PR_easy-R5_v03.md R-3).

Thin Processing wrapper over ``core/gtfs_check.py`` — no R5, no Java.
"""

from __future__ import annotations

import csv
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)

from ..core import gtfs_check


class CheckTransitData(QgsProcessingAlgorithm):
    GTFS = "GTFS"
    WHOLE_FOLDER = "WHOLE_FOLDER"
    DATE = "DATE"
    EXTENT = "EXTENT"
    FAIL_ON_ERROR = "FAIL_ON_ERROR"
    OUTPUT_REPORT = "OUTPUT_REPORT"
    OUTPUT_SERVICE_DAYS = "OUTPUT_SERVICE_DAYS"
    OUTPUT_ROUTES = "OUTPUT_ROUTES"
    ERRORS = "ERRORS"
    WARNINGS = "WARNINGS"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("CheckTransitData", string)

    def name(self) -> str:
        return "checktransitdata"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Check transit data (GTFS)")

    def group(self) -> str:
        return self.tr("Diagnostics")

    def groupId(self) -> str:  # noqa: N802
        return "diagnostics"

    def createInstance(self):  # noqa: N802
        return CheckTransitData()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Checks GTFS feeds before you build a network: calendar span and active "
            "trips per day, whether DATE has any service (R5 silently returns walk-only "
            "results otherwise), route types R5 7.6 cannot read, broken references "
            "between files, stop coordinates, stops outside EXTENT, and a realized "
            "(P50/P85) feed sharing a folder with its static feed.\n\n"
            "Pick a GTFS .zip; by default every .zip in its folder is checked together, "
            "the way Build R5 network reads them. The report is always written; errors only stop the "
            "algorithm when FAIL_ON_ERROR is set.\n\n"
            "The routes CSV lists route_id and short names — use them in Build scenario."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterFile(
            self.GTFS, self.tr("GTFS .zip file"),
            behavior=QgsProcessingParameterFile.Behavior.File, fileFilter="GTFS (*.zip)",
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.WHOLE_FOLDER,
            self.tr("Check every .zip in that folder, as Build R5 network would"),
            defaultValue=True,
        ))
        date = QgsProcessingParameterString(
            self.DATE, self.tr("Analysis date to check (yyyy-MM-dd, optional)"), optional=True)
        self.addParameter(date)
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT, self.tr("Study area / OSM extent (optional)"), optional=True))
        fail = QgsProcessingParameterBoolean(
            self.FAIL_ON_ERROR, self.tr("Fail the algorithm when errors are found"), defaultValue=False)
        fail.setFlags(fail.flags() | QgsProcessingParameterDefinition.Flag.FlagAdvanced)
        self.addParameter(fail)
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_REPORT, self.tr("Report (HTML)"), fileFilter=self.tr("HTML files (*.html)")))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_SERVICE_DAYS, self.tr("Active trips per day (CSV)"),
            fileFilter=self.tr("CSV files (*.csv)"), optional=True, createByDefault=False))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_ROUTES, self.tr("Routes (CSV)"),
            fileFilter=self.tr("CSV files (*.csv)"), optional=True, createByDefault=False))
        self.addOutput(QgsProcessingOutputNumber(self.ERRORS, self.tr("Errors")))
        self.addOutput(QgsProcessingOutputNumber(self.WARNINGS, self.tr("Warnings")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        src = Path(self.parameterAsFile(parameters, self.GTFS, context))
        if src.is_dir():
            zips = sorted(src.glob("*.zip"))
        elif src.is_file():
            # BuildNetwork reads every zip in the folder, so the cross-feed checks
            # (shared trip_ids, duplicate feed_id) only mean something over all of them.
            zips = (sorted(src.parent.glob("*.zip"))
                    if self.parameterAsBool(parameters, self.WHOLE_FOLDER, context) else [src])
        else:
            raise QgsProcessingException(self.tr("GTFS path not found: {}").format(src))
        if not zips:
            raise QgsProcessingException(self.tr("No .zip files in {}").format(src))

        date = self.parameterAsString(parameters, self.DATE, context).strip() or None
        extent = None
        if parameters.get(self.EXTENT) not in (None, ""):
            wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
            rect = self.parameterAsExtent(parameters, self.EXTENT, context, wgs84)
            if not rect.isNull() and not rect.isEmpty():
                extent = (rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum())

        feedback.pushInfo(self.tr("Checking {n} feed(s)…").format(n=len(zips)))
        result = gtfs_check.check_feeds(zips, date=date, extent=extent)

        for issue in result["issues"]:
            line = "{}: {}".format(issue.level, issue.message)
            if issue.level == gtfs_check.ERROR:
                feedback.reportError(line)
            elif issue.level == gtfs_check.WARN:
                feedback.pushWarning(line)
            else:
                feedback.pushInfo(line)

        report = self.parameterAsFileOutput(parameters, self.OUTPUT_REPORT, context)
        Path(report).write_text(
            gtfs_check.render_html(result, title="GTFS check: " + ", ".join(z.name for z in zips)),
            encoding="utf-8",
        )
        outputs = {self.OUTPUT_REPORT: report}

        days_csv = self.parameterAsFileOutput(parameters, self.OUTPUT_SERVICE_DAYS, context)
        if days_csv:
            with open(days_csv, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["date", "trips"])
                w.writerows(sorted(result["service_days"].items()))
            outputs[self.OUTPUT_SERVICE_DAYS] = days_csv

        routes_csv = self.parameterAsFileOutput(parameters, self.OUTPUT_ROUTES, context)
        if routes_csv:
            fields = ["feed", "route_id", "short_name", "long_name", "route_type", "trips"]
            with open(routes_csv, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(result["routes"])
            outputs[self.OUTPUT_ROUTES] = routes_csv

        errors = result["summary"]["errors"]
        warnings = result["summary"]["warnings"]
        outputs.update({self.ERRORS: errors, self.WARNINGS: warnings})
        feedback.pushInfo(self.tr("{e} error(s), {w} warning(s). Report: {p}").format(
            e=errors, w=warnings, p=report))
        if errors and self.parameterAsBool(parameters, self.FAIL_ON_ERROR, context):
            raise QgsProcessingException(
                self.tr("{e} error(s) in the GTFS data — see the report: {p}").format(e=errors, p=report))
        return outputs
