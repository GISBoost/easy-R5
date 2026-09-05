"""RunAccessibility: cumulative-opportunity accessibility per origin.

A layer on top of the travel-time matrix (PRD 4.5). The shared machinery runs
the exact same one-to-many computation as RunTravelTimeMatrix; this class adds
the opportunity fields, cutoffs and decay function, then sums in Python
(``core/accessibility.py``) — R5 has no usable native path (spike 2026-09-02).

The long CSV output (``id,opportunity,percentile,cutoff,accessibility``) is the
same shape r5r emits, so ``docs/notes/validation-gdansk.md`` can diff the two.
"""

from __future__ import annotations

import csv
import json
import shutil
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)

from ..core import accessibility
from ..core.styling import apply_style
from ._matrix_base import MatrixBase

_META_FIELDS = ("r5_version", "network_hash", "run_date", "departure_time",
                "time_window", "percentile", "modes", "transit_submodes", "decay")


class RunAccessibility(MatrixBase, QgsProcessingAlgorithm):
    OPPORTUNITY_FIELDS = "OPPORTUNITY_FIELDS"
    CUTOFFS = "CUTOFFS"
    DECAY = "DECAY"
    OUTPUT_CSV = "OUTPUT_CSV"
    OUTPUT_LAYER = "OUTPUT_LAYER"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("RunAccessibility", string)

    def name(self) -> str:
        return "runaccessibility"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Run accessibility")

    def group(self) -> str:
        return self.tr("Analysis")

    def groupId(self) -> str:  # noqa: N802
        return "analysis"

    def createInstance(self):  # noqa: N802
        return RunAccessibility()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "For each origin, counts the opportunities (jobs, schools, shops…) at "
            "destinations reachable within each cutoff, weighted by a decay "
            "function of travel time. Runs the same matrix as RunTravelTimeMatrix "
            "then sums in Python.\n\n"
            "OPPORTUNITY_FIELDS are numeric columns on the destination layer. "
            "STEP decay (count everything at or under the cutoff) is the default "
            "and what accessibility studies use; LOGISTIC and EXPONENTIAL taper.\n\n"
            "Output: a long CSV (id, opportunity, percentile, cutoff, "
            "accessibility) and an ORIGINS copy with acc_<opp>_p<pct>_c<cutoff> "
            "fields."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self._add_matrix_params(self.tr("Percentiles (1-99, ascending, up to 5)"))
        self.addParameter(
            QgsProcessingParameterField(
                self.OPPORTUNITY_FIELDS, self.tr("Opportunity fields on the destination layer"),
                parentLayerParameterName=self.DESTINATIONS,
                type=QgsProcessingParameterField.Numeric, allowMultiple=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.CUTOFFS, self.tr("Cutoffs (minutes, comma-separated)"),
                defaultValue="15,30,45,60",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.DECAY, self.tr("Decay function"),
                options=list(accessibility.DECAYS), defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_CSV, self.tr("Output accessibility CSV (long)"),
                fileFilter=self.tr("CSV files (*.csv)"),
            )
        )
        sink = QgsProcessingParameterFeatureSink(
            self.OUTPUT_LAYER, self.tr("Output layer (origins + accessibility fields)"),
        )
        self.addParameter(sink)

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        out_csv = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context))
        opp_fields = self.parameterAsFields(parameters, self.OPPORTUNITY_FIELDS, context)
        decay = list(accessibility.DECAYS)[self.parameterAsEnum(parameters, self.DECAY, context)]
        max_trip = self.parameterAsInt(parameters, self.MAX_TRIP_DURATION, context)

        try:
            cutoffs = sorted({int(c) for c in
                              self.parameterAsString(parameters, self.CUTOFFS, context)
                              .replace(",", " ").split()})
        except ValueError:
            raise QgsProcessingException(self.tr("Cutoffs must be whole numbers of minutes."))
        if not cutoffs or cutoffs[0] < 1:
            raise QgsProcessingException(self.tr("Give at least one positive cutoff."))
        if not opp_fields:
            raise QgsProcessingException(self.tr("Select at least one opportunity field."))

        # A cutoff above MAX_TRIP_DURATION would silently truncate the matrix and
        # under-count the larger cutoffs — bump the trip budget to cover them.
        if max(cutoffs) > max_trip:
            feedback.pushWarning(self.tr(
                "MAX_TRIP_DURATION ({t} min) is below the largest cutoff ({c} min) — "
                "raising it to {c} so accessibility is not under-counted."
            ).format(t=max_trip, c=max(cutoffs)))
            parameters = {**parameters, self.MAX_TRIP_DURATION: max(cutoffs)}
            max_trip = max(cutoffs)

        # Lossless walk cap: max(cutoffs) for STEP; the tapered functions have
        # weight beyond the cutoff, so they need the full trip budget.
        walk_fallback = max(cutoffs) if decay == accessibility.STEP else max_trip

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_acc_"))
        try:
            matrix_csv = tmp / "matrix.csv"
            res = self._run_matrix(
                parameters, context, feedback, tmp=tmp, matrix_csv=matrix_csv,
                walk_fallback=walk_fallback, dest_extra_fields=opp_fields,
            )
            opportunities = accessibility.read_opportunities(res["dests_csv"], opp_fields)

            feedback.pushInfo(self.tr("Summing accessibility ({} decay)…").format(decay))
            rows = list(accessibility.compute_accessibility(
                matrix_csv, opportunities, res["origin_ids"], cutoffs, decay
            ))
            self._write_long_csv(out_csv, rows)

            meta = {**res["meta"], "decay": decay}
            Path(str(out_csv) + ".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            feedback.pushInfo(self.tr("Wrote {n} rows to {p}").format(n=len(rows), p=out_csv))

            sink_id = self._write_layer(parameters, context, res, rows, meta)
            apply_style(context, sink_id, "accessibility.qml")
            return {self.OUTPUT_CSV: str(out_csv), self.OUTPUT_LAYER: sink_id}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # --- outputs -------------------------------------------------------

    @staticmethod
    def _write_long_csv(path, rows):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["id", "opportunity", "percentile", "cutoff", "accessibility"]
            )
            writer.writeheader()
            writer.writerows(rows)

    def _write_layer(self, parameters, context, res, rows, meta):
        pivot = {}
        for r in rows:
            key = "acc_{}_p{}_c{}".format(r["opportunity"], r["percentile"], r["cutoff"])
            pivot.setdefault(r["id"], {})[key] = r["accessibility"]
        acc_field_names = sorted({k for v in pivot.values() for k in v})

        origins_src = self.parameterAsSource(parameters, self.ORIGINS, context)
        out_fields = QgsFields(origins_src.fields())
        for name in acc_field_names:
            out_fields.append(QgsField(name, QVariant.Double))
        for name in _META_FIELDS:
            out_fields.append(QgsField(name, QVariant.String))

        sink, sink_id = self.parameterAsSink(
            parameters, self.OUTPUT_LAYER, context, out_fields,
            origins_src.wkbType(), origins_src.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException(self.tr("Could not create the output layer."))

        # Match features to results by the id value when ORIGIN_ID_FIELD is set,
        # not by iteration position — some providers don't guarantee a stable
        # feature order between two getFeatures() calls. With no id field the id
        # is a zero-padded running index (same rule as points.stable_ids).
        id_field = self.parameterAsString(parameters, self.ORIGIN_ID_FIELD, context)
        fidx = origins_src.fields().lookupField(id_field) if id_field else -1
        width = max(1, len(str(len(res["origin_ids"]) - 1))) if res["origin_ids"] else 1

        meta_values = [meta.get(k) for k in _META_FIELDS]
        kept = 0
        for feat in origins_src.getFeatures():
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                continue
            oid = str(feat.attribute(fidx)) if fidx >= 0 else "{:0{w}d}".format(kept, w=width)
            kept += 1
            per_origin = pivot.get(oid, {})
            out = QgsFeature(out_fields)
            out.setGeometry(geom)
            out.setAttributes(
                list(feat.attributes())
                + [per_origin.get(n, 0) for n in acc_field_names]
                + meta_values
            )
            sink.addFeature(out, QgsFeatureSink.FastInsert)
        return sink_id
