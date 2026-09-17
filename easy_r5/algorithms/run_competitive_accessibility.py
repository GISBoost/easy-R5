"""RunCompetitiveAccessibility: 2SFCA over one travel-time matrix (PR_easy-R5_v03.md R-5).

Origins are the demand side (a population field), destinations the supply side
(a capacity field: doctors, school places, beds). Same matrix run as
RunAccessibility; the 2SFCA sums live in ``core/fca.py``.
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
    QgsProcessingParameterNumber,
)

from ..core import accessibility, fca
from ..core.styling import apply_graduated
from ._matrix_base import MatrixBase

_META_FIELDS = ("r5_version", "network_hash", "run_date", "departure_time", "time_window", "percentile",
                "modes", "transit_submodes", "decay", "catchment", "scenario", "max_trip_duration_minutes",
                "max_walk_time_minutes", "walk_speed_kmh", "max_rides", "monte_carlo_draws")


class RunCompetitiveAccessibility(MatrixBase, QgsProcessingAlgorithm):
    POPULATION_FIELD = "POPULATION_FIELD"
    CAPACITY_FIELD = "CAPACITY_FIELD"
    CATCHMENT_MINUTES = "CATCHMENT_MINUTES"
    DECAY = "DECAY"
    PER_POPULATION = "PER_POPULATION"
    OUTPUT_CSV = "OUTPUT_CSV"
    OUTPUT_LAYER = "OUTPUT_LAYER"
    OUTPUT_SUPPLY_LAYER = "OUTPUT_SUPPLY_LAYER"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("RunCompetitiveAccessibility", string)

    def name(self) -> str:
        return "runcompetitiveaccessibility"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Run competitive accessibility (2SFCA)")

    def group(self) -> str:
        return self.tr("Analysis")

    def groupId(self) -> str:  # noqa: N802
        return "analysis"

    def createInstance(self):  # noqa: N802
        return RunCompetitiveAccessibility()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Two-step floating catchment area (2SFCA) accessibility: like Run accessibility, "
            "but opportunities are shared by everyone who can reach them. A clinic with 5 "
            "doctors reachable by 50 000 people counts for less than the same clinic "
            "reachable by 5 000.\n\n"
            "Step 1: each destination's capacity is divided by the population (ORIGINS, "
            "POPULATION_FIELD) that reaches it within CATCHMENT_MINUTES. Step 2: each origin "
            "sums those ratios over the destinations it reaches. The result 'fca' is capacity "
            "per PER_POPULATION residents (e.g. doctors per 1000). STEP decay is the classic "
            "2SFCA; LOGISTIC and EXPONENTIAL weight nearer destinations more (E2SFCA-style) "
            "and drop to 0 at the catchment, so results are sensitive to CATCHMENT_MINUTES.\n\n"
            "Give exactly one percentile. Origins should cover all the population competing "
            "for the destinations, not only the area you want to map."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self._add_matrix_params(self.tr("Percentile (one value, 1-99)"))
        self.addParameter(QgsProcessingParameterField(
            self.POPULATION_FIELD, self.tr("Population field on the origin layer"),
            parentLayerParameterName=self.ORIGINS, type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.CAPACITY_FIELD, self.tr("Capacity field on the destination layer"),
            parentLayerParameterName=self.DESTINATIONS, type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.CATCHMENT_MINUTES, self.tr("Catchment (minutes)"),
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=30, minValue=1))
        self.addParameter(QgsProcessingParameterEnum(
            self.DECAY, self.tr("Decay within the catchment"), options=list(accessibility.DECAYS), defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.PER_POPULATION, self.tr("Express the result per N residents"),
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=1000.0, minValue=1.0))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_CSV, self.tr("Output CSV"), fileFilter=self.tr("CSV files (*.csv)")))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_LAYER, self.tr("Output layer (origins + fca)")))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_SUPPLY_LAYER, self.tr("Supply layer (destinations + ratio)"),
            optional=True, createByDefault=False))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        pop_field = self.parameterAsString(parameters, self.POPULATION_FIELD, context)
        cap_field = self.parameterAsString(parameters, self.CAPACITY_FIELD, context)
        catchment = self.parameterAsInt(parameters, self.CATCHMENT_MINUTES, context)
        decay = list(accessibility.DECAYS)[self.parameterAsEnum(parameters, self.DECAY, context)]
        per_pop = self.parameterAsDouble(parameters, self.PER_POPULATION, context)
        out_csv = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context))
        max_trip = self.parameterAsInt(parameters, self.MAX_TRIP_DURATION, context)
        if len(self.parameterAsString(parameters, self.PERCENTILES, context).replace(",", " ").split()) != 1:
            raise QgsProcessingException(self.tr(
                "Give exactly one percentile — a 2SFCA index mixing percentiles has no meaning."))
        # Checked before routing: a clash would otherwise surface only after the whole matrix ran.
        self._check_clash(self.parameterAsSource(parameters, self.ORIGINS, context), ["fca"])
        if parameters.get(self.OUTPUT_SUPPLY_LAYER) not in (None, ""):
            self._check_clash(self.parameterAsSource(parameters, self.DESTINATIONS, context),
                              ["supply_ratio", "demand_in_catchment"])
        if catchment > max_trip:
            feedback.pushWarning(self.tr(
                "MAX_TRIP_DURATION ({t} min) is below the catchment ({c} min) — raising it to {c}."
            ).format(t=max_trip, c=catchment))
            parameters = {**parameters, self.MAX_TRIP_DURATION: catchment}

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_fca_"))
        try:
            matrix_csv = tmp / "matrix.csv"
            res = self._run_matrix(
                parameters, context, feedback, tmp=tmp, matrix_csv=matrix_csv, walk_fallback=catchment,
                dest_extra_fields=[cap_field], origin_extra_fields=[pop_field],
            )
            pct = res["percentiles"][0]
            population = {k: v[pop_field] for k, v in accessibility.read_opportunities(
                res["origins_csv"], [pop_field]).items()}
            capacity = {k: v[cap_field] for k, v in accessibility.read_opportunities(
                res["dests_csv"], [cap_field]).items()}
            result = fca.two_step_fca(fca.read_matrix_pairs(matrix_csv, pct), population, capacity,
                                      catchment=catchment, decay=decay, per_population=per_pop)

            if result["thin_supply"]:
                feedback.pushWarning(self.tr(
                    "{n} destination(s) are reached by almost nobody: their capacity per resident is "
                    "up to {r:.0f}x the study-wide average, so the few origins reaching them get "
                    "extreme values. This means the origins do not cover everyone competing for "
                    "those destinations — usually destinations outside the study area. Either "
                    "extend the origins beyond it, or clip the destinations to it. Examples: "
                    "{e}").format(n=len(result["thin_supply"]), r=result["worst_thin_factor"],
                                  e=", ".join(result["thin_supply"][:5])))
            if result["unserved_supply"]:
                feedback.pushWarning(self.tr(
                    "{n} destination(s) with capacity have no population within {c} min — their "
                    "capacity is not distributed to anyone.").format(n=result["unserved_supply"], c=catchment))
            spread = sum(result["access"][o] / per_pop * population[o] for o in population)
            feedback.pushInfo(self.tr(
                "Check: supply distributed {d:.4g}, reconstructed from origins {r:.4g}.").format(
                    d=result["distributed_supply"], r=spread))

            meta = {**res["meta"], "decay": decay, "catchment": catchment,
                    "capacity_field": cap_field, "population_field": pop_field, "per_population": per_pop}
            with open(out_csv, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["id", "population", "fca"])
                for o in res["origin_ids"]:
                    w.writerow([o, population.get(o, 0), round(result["access"].get(o, 0.0), 6)])
            Path(str(out_csv) + ".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            origins_src = self.parameterAsSource(parameters, self.ORIGINS, context)
            sink_id = self._write(parameters, self.OUTPUT_LAYER, context, origins_src,
                                  self.parameterAsString(parameters, self.ORIGIN_ID_FIELD, context),
                                  res["origin_ids"], [("fca", result["access"])], meta)
            apply_graduated(context, sink_id, "fca")
            outputs = {self.OUTPUT_CSV: str(out_csv), self.OUTPUT_LAYER: sink_id}
            if parameters.get(self.OUTPUT_SUPPLY_LAYER) not in (None, ""):
                dests_src = self.parameterAsSource(parameters, self.DESTINATIONS, context)
                supply_id = self._write(parameters, self.OUTPUT_SUPPLY_LAYER, context, dests_src,
                                        self.parameterAsString(parameters, self.DEST_ID_FIELD, context),
                                        res["dest_ids"], [("supply_ratio", result["ratio"]),
                                                          ("demand_in_catchment", result["demand"])], meta)
                if supply_id:
                    outputs[self.OUTPUT_SUPPLY_LAYER] = supply_id
            return outputs
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _check_clash(self, source, names):
        clash = [n for n in list(names) + list(_META_FIELDS) if source.fields().lookupField(n) >= 0]
        if clash:
            raise QgsProcessingException(self.tr(
                "The input layer already has field(s) {f} — it looks like an earlier result. Use the "
                "original layer or remove those fields.").format(f=", ".join(clash)))

    def _write(self, parameters, name, context, source, id_field, ids, value_maps, meta):
        """Copy ``source`` + one double field per (field_name, {id: value}) + method fields.

        Matches features to ids the same way RunAccessibility does: by the id field's value,
        or by the zero-padded running index when no id field was chosen.
        """
        fields = QgsFields(source.fields())
        for fname, _values in value_maps:
            fields.append(QgsField(fname, QVariant.Double))
        for mname in _META_FIELDS:
            fields.append(QgsField(mname, QVariant.String))
        sink, sink_id = self.parameterAsSink(parameters, name, context, fields, source.wkbType(),
                                             source.sourceCrs())
        if sink is None:
            return None
        fidx = source.fields().lookupField(id_field) if id_field else -1
        width = max(1, len(str(len(ids) - 1))) if ids else 1
        meta_values = [None if meta.get(k) is None else str(meta.get(k)) for k in _META_FIELDS]
        kept = 0
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                continue
            key = str(feat.attribute(fidx)) if fidx >= 0 else "{:0{w}d}".format(kept, w=width)
            kept += 1
            out = QgsFeature(fields)
            out.setGeometry(geom)
            out.setAttributes(list(feat.attributes()) + [values.get(key, 0.0) for _n, values in value_maps]
                              + meta_values)
            sink.addFeature(out, QgsFeatureSink.Flag.FastInsert)
        return sink_id
