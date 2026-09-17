"""CompareScenarios: one numeric field, two runs, one difference layer (PR_easy-R5_v03.md R-2).

Joins by an id field, not by geometry. Refuses to diff runs whose method fields
(percentile, decay, window, ...) differ — two maps that differ only by method
are the most likely way a user misreads their own result.
"""

from __future__ import annotations

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
)

from ..core import compare
from ..core.styling import apply_categories

_OUT_FIELDS = (("value_a", QVariant.Double), ("value_b", QVariant.Double), ("diff", QVariant.Double),
               ("pct_change", QVariant.Double), ("status", QVariant.String))


class CompareScenarios(QgsProcessingAlgorithm):
    LAYER_A = "LAYER_A"
    LAYER_B = "LAYER_B"
    JOIN_FIELD = "JOIN_FIELD"
    JOIN_FIELD_B = "JOIN_FIELD_B"
    FIELD = "FIELD"
    FIELD_B = "FIELD_B"
    ALLOW_METHOD_MISMATCH = "ALLOW_METHOD_MISMATCH"
    OUTPUT = "OUTPUT"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("CompareScenarios", string)

    def name(self) -> str:
        return "comparescenarios"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Compare scenarios")

    def group(self) -> str:
        return self.tr("Scenarios")

    def groupId(self) -> str:  # noqa: N802
        return "scenarios"

    def createInstance(self):  # noqa: N802
        return CompareScenarios()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Compares one numeric field between two result layers of the same places — "
            "e.g. accessibility before (LAYER_A) and after (LAYER_B) a timetable change or "
            "a scenario — and writes value_a, value_b, diff (B - A), pct_change and status "
            "(better / worse / same / only_a / only_b). Features are matched by the id "
            "field, not by geometry.\n\n"
            "If both layers carry run-method fields (percentile, decay, time_window, "
            "departure_time, modes), they must match; otherwise the difference mixes a "
            "method change into the result and the algorithm stops. run_date, scenario and "
            "network_hash may differ — that is what is being compared.\n\n"
            "'better' means a higher value in B: right for accessibility, service minutes "
            "and 2SFCA, reversed for travel times."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterFeatureSource(self.LAYER_A, self.tr("Layer A (before / baseline)")))
        self.addParameter(QgsProcessingParameterFeatureSource(self.LAYER_B, self.tr("Layer B (after / scenario)")))
        self.addParameter(QgsProcessingParameterField(
            self.JOIN_FIELD, self.tr("Id field (layer A)"), parentLayerParameterName=self.LAYER_A))
        self.addParameter(QgsProcessingParameterField(
            self.JOIN_FIELD_B, self.tr("Id field in layer B (blank = same name)"),
            parentLayerParameterName=self.LAYER_B, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, self.tr("Field to compare (layer A)"), parentLayerParameterName=self.LAYER_A,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_B, self.tr("Field in layer B (blank = same name)"), parentLayerParameterName=self.LAYER_B,
            type=QgsProcessingParameterField.DataType.Numeric, optional=True))
        allow = QgsProcessingParameterBoolean(
            self.ALLOW_METHOD_MISMATCH, self.tr("Compare even if the run methods differ"), defaultValue=False)
        allow.setFlags(allow.flags() | QgsProcessingParameterDefinition.Flag.FlagAdvanced)
        self.addParameter(allow)
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Comparison")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        src_a = self.parameterAsSource(parameters, self.LAYER_A, context)
        src_b = self.parameterAsSource(parameters, self.LAYER_B, context)
        if src_a is None or src_b is None:
            raise QgsProcessingException(self.tr("Both layers are required."))
        join_a = self.parameterAsString(parameters, self.JOIN_FIELD, context)
        join_b = self.parameterAsString(parameters, self.JOIN_FIELD_B, context) or join_a
        field_a = self.parameterAsString(parameters, self.FIELD, context)
        field_b = self.parameterAsString(parameters, self.FIELD_B, context) or field_a
        for src, names, label in ((src_a, (join_a, field_a), "A"), (src_b, (join_b, field_b), "B")):
            missing = [n for n in names if src.fields().lookupField(n) < 0]
            if missing:
                raise QgsProcessingException(
                    self.tr("Layer {l} has no field(s): {f}").format(l=label, f=", ".join(missing)))

        feats_a = self._by_id(src_a, join_a, "A")
        feats_b = self._by_id(src_b, join_b, "B")

        blocking, info = compare.method_mismatches(self._meta(src_a, feats_a), self._meta(src_b, feats_b))
        for field, va, vb in info:
            feedback.pushInfo(self.tr("{f}: A = {a}, B = {b}").format(f=field, a=", ".join(va), b=", ".join(vb)))
        if blocking:
            text = "; ".join("{}: A = {}, B = {}".format(f, ", ".join(a), ", ".join(b)) for f, a, b in blocking)
            if not self.parameterAsBool(parameters, self.ALLOW_METHOD_MISMATCH, context):
                raise QgsProcessingException(self.tr(
                    "The two runs used different methods ({t}). The difference would mix the "
                    "method change into the result. Re-run one of them, or set "
                    "ALLOW_METHOD_MISMATCH (Advanced).").format(t=text))
            feedback.pushWarning(self.tr("Comparing despite method differences: {t}").format(t=text))

        out_fields = QgsFields(src_a.fields())
        for name, qtype in _OUT_FIELDS:
            if out_fields.lookupField(name) >= 0:
                raise QgsProcessingException(
                    self.tr("Layer A already has a field named '{}' — rename it first.").format(name))
            out_fields.append(QgsField(name, qtype))
        sink, sink_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields, src_a.wkbType(), src_a.sourceCrs())
        if sink is None:
            raise QgsProcessingException(self.tr("Could not create the output layer."))

        rows = []
        n_attrs = src_a.fields().count()
        for key, fa in feats_a.items():
            fb = feats_b.get(key)
            row = compare.diff_row(fa[field_a], fb[field_b] if fb is not None else None, in_b=fb is not None)
            rows.append(row)
            self._add(sink, out_fields, fa.geometry(), list(fa.attributes()), row)
        for key, fb in feats_b.items():
            if key in feats_a:
                continue
            row = compare.diff_row(None, fb[field_b], in_a=False)
            rows.append(row)
            if src_b.sourceCrs() == src_a.sourceCrs():
                geom = fb.geometry()
            else:
                geom = None  # ponytail: no reprojection for only_b rows; add if layers differ in CRS
            attrs = [None] * n_attrs
            attrs[src_a.fields().lookupField(join_a)] = fb[join_b]
            self._add(sink, out_fields, geom, attrs, row)

        s = compare.summarize(rows)
        c = s["counts"]
        feedback.pushInfo(self.tr(
            "better {b}, worse {w}, same {s}, only in A {oa}, only in B {ob}; "
            "sum of diff {sd:.4g}, mean {md}").format(
                b=c.get("better", 0), w=c.get("worse", 0), s=c.get("same", 0),
                oa=c.get("only_a", 0), ob=c.get("only_b", 0), sd=s["sum_diff"],
                md="{:.4g}".format(s["mean_diff"]) if s["mean_diff"] is not None else "-"))
        apply_categories(context, sink_id, "status", [
            ("better", "#1a9641", self.tr("better in B")),
            ("worse", "#d7191c", self.tr("worse in B")),
            ("same", "#bdbdbd", self.tr("no change")),
            ("only_a", "#fdae61", self.tr("only in A")),
            ("only_b", "#abd9e9", self.tr("only in B")),
        ])
        return {self.OUTPUT: sink_id}

    def _by_id(self, source, field, label):
        out = {}
        idx = source.fields().lookupField(field)
        for f in source.getFeatures():
            key = f.attribute(idx)
            key = None if key is None else str(key)
            if key in (None, "", "NULL"):
                continue
            if key in out:
                raise QgsProcessingException(
                    self.tr("Layer {l}: id '{k}' appears more than once in field {f}.").format(
                        l=label, k=key, f=field))
            out[key] = f
        return out

    @staticmethod
    def _meta(source, feats):
        names = [n for n in compare.STRICT_FIELDS + compare.EXPECTED_TO_DIFFER
                 if source.fields().lookupField(n) >= 0]
        return {n: [f[n] for f in feats.values()] for n in names}

    @staticmethod
    def _add(sink, fields, geom, attrs, row):
        out = QgsFeature(fields)
        if geom is not None:
            out.setGeometry(geom)
        out.setAttributes(attrs + list(row))
        sink.addFeature(out, QgsFeatureSink.Flag.FastInsert)
