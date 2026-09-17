"""SummarizeAccessibilityEquity: "how many residents reach ..." (PR_easy-R5_v03.md R-4).

Population-weighted statistics over any layer with a population field and
numeric accessibility fields; the maths lives in ``core/equity.py``.
"""

from __future__ import annotations

from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)

from ..core import compare, equity

_COLUMNS = (("grp", QVariant.String), ("field", QVariant.String), ("population", QVariant.Double),
            ("pop_at_least", QVariant.Double), ("share_at_least", QVariant.Double),
            ("pop_zero", QVariant.Double), ("share_zero", QVariant.Double), ("mean", QVariant.Double),
            ("p10", QVariant.Double), ("p25", QVariant.Double), ("p50", QVariant.Double),
            ("p75", QVariant.Double), ("p90", QVariant.Double), ("gini", QVariant.Double))


class SummarizeAccessibilityEquity(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    POPULATION_FIELD = "POPULATION_FIELD"
    ACCESSIBILITY_FIELDS = "ACCESSIBILITY_FIELDS"
    THRESHOLD = "THRESHOLD"
    GROUP_FIELD = "GROUP_FIELD"
    OUTPUT_TABLE = "OUTPUT_TABLE"
    OUTPUT_REPORT = "OUTPUT_REPORT"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("SummarizeAccessibilityEquity", string)

    def name(self) -> str:
        return "summarizeaccessibilityequity"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Summarize accessibility equity")

    def group(self) -> str:
        return self.tr("Analysis")

    def groupId(self) -> str:  # noqa: N802
        return "analysis"

    def createInstance(self):  # noqa: N802
        return SummarizeAccessibilityEquity()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Answers 'how many residents reach at least THRESHOLD of something': for each "
            "accessibility field, the population-weighted share at or above the threshold, "
            "the population with none, the weighted mean, quantiles (p10-p90) and Gini "
            "coefficient — for the whole layer and, optionally, per GROUP_FIELD (e.g. district).\n\n"
            "Typical input: the output of Run accessibility or Run competitive accessibility "
            "on a grid from Population overlay (the population field is carried over). An empty "
            "accessibility value counts as 0 (no access); features with empty or negative "
            "population are skipped.\n\n"
            "Writes a table and an HTML report with one plain-language sentence per field and "
            "the run method (percentile, date, scenario ...) found in the layer."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, self.tr("Accessibility layer")))
        self.addParameter(QgsProcessingParameterField(
            self.POPULATION_FIELD, self.tr("Population field"), parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.ACCESSIBILITY_FIELDS, self.tr("Accessibility fields"), parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric, allowMultiple=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, self.tr("Threshold (count residents with a value at or above it)"),
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=1.0))
        self.addParameter(QgsProcessingParameterField(
            self.GROUP_FIELD, self.tr("Group by (optional, e.g. district)"), parentLayerParameterName=self.INPUT,
            optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_TABLE, self.tr("Equity summary table"), type=QgsProcessing.SourceType.TypeVector))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_REPORT, self.tr("Report (HTML)"), fileFilter=self.tr("HTML files (*.html)")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.tr("No input layer."))
        pop_field = self.parameterAsString(parameters, self.POPULATION_FIELD, context)
        acc_fields = self.parameterAsFields(parameters, self.ACCESSIBILITY_FIELDS, context)
        if not acc_fields:
            raise QgsProcessingException(self.tr("Select at least one accessibility field."))
        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        group_field = self.parameterAsString(parameters, self.GROUP_FIELD, context) or None

        method_names = [n for n in compare.STRICT_FIELDS + compare.EXPECTED_TO_DIFFER
                        if source.fields().lookupField(n) >= 0]
        wanted = [pop_field] + list(acc_fields) + ([group_field] if group_field else []) + method_names
        records = [{n: f[n] for n in wanted} for f in source.getFeatures()]
        rows = equity.summarize_layer(records, pop_field, acc_fields, threshold, group_field)

        skipped = max((r["skipped"] for r in rows if r["grp"] == "ALL"), default=0)
        if skipped:
            feedback.pushWarning(self.tr(
                "{n} feature(s) with empty or negative population were skipped.").format(n=skipped))
        for r in rows:
            if r["grp"] == "ALL":
                feedback.pushInfo(equity.sentence(r, threshold))

        fields = QgsFields()
        for name, qtype in _COLUMNS:
            fields.append(QgsField(name, qtype))
        sink, sink_id = self.parameterAsSink(parameters, self.OUTPUT_TABLE, context, fields,
                                             QgsWkbTypes.Type.NoGeometry)
        if sink is None:
            raise QgsProcessingException(self.tr("Could not create the output table."))
        for r in rows:
            feat = QgsFeature(fields)
            feat.setAttributes([r[name] for name, _t in _COLUMNS])
            sink.addFeature(feat, QgsFeatureSink.Flag.FastInsert)

        method = {n: sorted({str(rec[n]) for rec in records if rec[n] not in (None, "")}) for n in method_names}
        report = self.parameterAsFileOutput(parameters, self.OUTPUT_REPORT, context)
        Path(report).write_text(equity.render_html(rows, threshold, method), encoding="utf-8")
        return {self.OUTPUT_TABLE: sink_id, self.OUTPUT_REPORT: report}
