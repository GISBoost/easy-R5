"""RunTravelTimeMatrix: one-to-many / many-to-many travel times over a departure
window, computed by R5 and written as a long-format CSV.

This is the flagship algorithm — R5 answers one origin against every destination
in ~20 ms after a per-point-set setup, so the whole matrix is a loop over
origins, batched into separate processes to bound memory (PRD 3.4). The Java
runner does the routing; everything else (layer -> CSV, date gate, estimate,
batch merge, walk-only check, OOM message) is here.

Two guards against the silent walk-only failure that shipped wrong for GZM
(PRD 2.1): a hard date gate before any Java starts, and a post-run detector on
``transit_used_pairs``.
"""

from __future__ import annotations

import datetime
import json
import math
import shutil
import tempfile
import time
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsWkbTypes,
)

from ..core import job_spec, java_env, matrix, network_cache, pins, points, runner, settings

_MODE_OPTIONS = ["TRANSIT + WALK", "WALK", "BICYCLE", "CAR"]
_TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"]
# TRANSIT + WALK, WALK, BICYCLE, CAR -> (direct/access/egress LegMode, transit modes)
_MODE_MAP = {
    0: ("WALK", _TRANSIT_MODES),
    1: ("WALK", []),
    2: ("BICYCLE", []),
    3: ("CAR", []),
}
_SLOW_RUN_MINUTES = 30


class RunTravelTimeMatrix(QgsProcessingAlgorithm):
    NETWORK = "NETWORK"
    ORIGINS = "ORIGINS"
    ORIGIN_ID_FIELD = "ORIGIN_ID_FIELD"
    DESTINATIONS = "DESTINATIONS"
    DEST_ID_FIELD = "DEST_ID_FIELD"
    DATE = "DATE"
    DEPARTURE_TIME = "DEPARTURE_TIME"
    TIME_WINDOW = "TIME_WINDOW"
    PERCENTILES = "PERCENTILES"
    MAX_TRIP_DURATION = "MAX_TRIP_DURATION"
    MAX_WALK_TIME = "MAX_WALK_TIME"
    WALK_SPEED = "WALK_SPEED"
    MAX_RIDES = "MAX_RIDES"
    MODE = "MODE"
    MONTE_CARLO_DRAWS = "MONTE_CARLO_DRAWS"
    BATCH_SIZE = "BATCH_SIZE"
    ESTIMATE_FIRST = "ESTIMATE_FIRST"
    ALLOW_NO_SERVICE = "ALLOW_NO_SERVICE"
    INCLUDE_UNREACHABLE = "INCLUDE_UNREACHABLE"
    JAVA_HEAP_GB = "JAVA_HEAP_GB"
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
        self.addParameter(
            QgsProcessingParameterFile(
                self.NETWORK, self.tr("R5 network (network.dat)"),
                behavior=QgsProcessingParameterFile.File, extension="dat",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.ORIGINS, self.tr("Origin points"))
        )
        origin_id = QgsProcessingParameterField(
            self.ORIGIN_ID_FIELD, self.tr("Origin id field (blank = feature id)"),
            parentLayerParameterName=self.ORIGINS, optional=True,
        )
        origin_id.setFlags(origin_id.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(origin_id)

        self.addParameter(
            QgsProcessingParameterFeatureSource(self.DESTINATIONS, self.tr("Destination points"))
        )
        dest_id = QgsProcessingParameterField(
            self.DEST_ID_FIELD, self.tr("Destination id field (blank = feature id)"),
            parentLayerParameterName=self.DESTINATIONS, optional=True,
        )
        dest_id.setFlags(dest_id.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(dest_id)

        date_param = QgsProcessingParameterString(
            self.DATE, self.tr("Date (yyyy-MM-dd; required for transit)"), optional=True
        )
        date_param.setFlags(date_param.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(date_param)
        self.addParameter(
            QgsProcessingParameterString(
                self.DEPARTURE_TIME, self.tr("Departure time (HH:mm)"), defaultValue="07:00"
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIME_WINDOW, self.tr("Departure window (minutes)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=120, minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.PERCENTILES, self.tr("Percentiles (1-99, ascending, up to 5)"),
                defaultValue="50",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_TRIP_DURATION, self.tr("Max trip duration (minutes)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=90, minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WALK_SPEED, self.tr("Walk speed (km/h)"),
                type=QgsProcessingParameterNumber.Double, defaultValue=3.6, minValue=0.1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_RIDES, self.tr("Max transit rides (transfers + 1)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE, self.tr("Travel mode"), options=_MODE_OPTIONS, defaultValue=0
            )
        )

        self._advanced(
            QgsProcessingParameterNumber(
                self.MAX_WALK_TIME, self.tr("Max walk time (minutes; blank = max trip duration)"),
                type=QgsProcessingParameterNumber.Integer, optional=True, minValue=1,
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.MONTE_CARLO_DRAWS, self.tr("Monte Carlo draws per minute"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=5, minValue=1,
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.BATCH_SIZE, self.tr("Origins per batch process"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=500,
                minValue=100, maxValue=5000,
            )
        )
        self._advanced(
            QgsProcessingParameterBoolean(
                self.ESTIMATE_FIRST, self.tr("Time a sample of origins first"), defaultValue=True
            )
        )
        self._advanced(
            QgsProcessingParameterBoolean(
                self.ALLOW_NO_SERVICE,
                self.tr("Run even if the date has no transit service (diagnostic)"),
                defaultValue=False,
            )
        )
        self._advanced(
            QgsProcessingParameterBoolean(
                self.INCLUDE_UNREACHABLE,
                self.tr("Keep unreachable pairs as blank-value rows"), defaultValue=False,
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.JAVA_HEAP_GB, self.tr("Java heap (GB; blank = auto)"),
                type=QgsProcessingParameterNumber.Integer, optional=True, minValue=1,
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

    def _advanced(self, param):
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

    # --- run -----------------------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        network_path = Path(self.parameterAsFile(parameters, self.NETWORK, context))
        if not network_path.is_file():
            raise QgsProcessingException(self.tr("Network file not found: {}").format(network_path))
        summary = self._load_summary(network_path)
        service_days = summary.get("service_days") or {}

        origins_src = self.parameterAsSource(parameters, self.ORIGINS, context)
        dests_src = self.parameterAsSource(parameters, self.DESTINATIONS, context)
        if origins_src is None or dests_src is None:
            raise QgsProcessingException(self.tr("Origin and destination layers are required."))

        date = self.parameterAsString(parameters, self.DATE, context).strip()
        departure_time = self.parameterAsString(parameters, self.DEPARTURE_TIME, context).strip()
        time_window = self.parameterAsInt(parameters, self.TIME_WINDOW, context)
        max_trip = self.parameterAsInt(parameters, self.MAX_TRIP_DURATION, context)
        walk_speed = self.parameterAsDouble(parameters, self.WALK_SPEED, context)
        max_rides = self.parameterAsInt(parameters, self.MAX_RIDES, context)
        mode = self.parameterAsEnum(parameters, self.MODE, context)
        monte_carlo = self.parameterAsInt(parameters, self.MONTE_CARLO_DRAWS, context)
        batch_size = self.parameterAsInt(parameters, self.BATCH_SIZE, context)
        estimate_first = self.parameterAsBool(parameters, self.ESTIMATE_FIRST, context)
        allow_no_service = self.parameterAsBool(parameters, self.ALLOW_NO_SERVICE, context)
        include_unreachable = self.parameterAsBool(parameters, self.INCLUDE_UNREACHABLE, context)
        origin_id_field = self.parameterAsString(parameters, self.ORIGIN_ID_FIELD, context)
        dest_id_field = self.parameterAsString(parameters, self.DEST_ID_FIELD, context)
        out_csv = Path(self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context))

        # Gate 1: percentiles — R5 throws an opaque error on >5 / non-ascending.
        try:
            percentiles = job_spec.parse_percentiles(
                self.parameterAsString(parameters, self.PERCENTILES, context)
            )
        except job_spec.JobSpecError as exc:
            raise QgsProcessingException(str(exc))

        direct_mode, transit_modes = _MODE_MAP[mode]
        is_transit = bool(transit_modes)

        # Gate 2: dead date — hard block for transit runs (PRD 5.3).
        if is_transit and not date:
            raise QgsProcessingException(self.tr("A date is required for a transit run."))
        if not date:
            # Non-transit run: R5 still needs a parseable date; it does not affect the result.
            date = datetime.date.today().isoformat()
        if is_transit and service_days and int(service_days.get(date, 0)) == 0:
            if not allow_no_service:
                nearest = matrix.nearest_served_days(service_days, date, 3)
                raise QgsProcessingException(
                    self.tr(
                        "The GTFS feed has no active trips on {date}. R5 would silently "
                        "return walk-only results. Nearest served days: {days}. "
                        "(Advanced: ALLOW_NO_SERVICE overrides this for diagnostics.)"
                    ).format(date=date, days=", ".join(nearest) or self.tr("none in the feed span"))
                )
            feedback.pushWarning(
                self.tr("ALLOW_NO_SERVICE: {date} has no transit service — expect a walk-only "
                        "failure after the run.").format(date=date)
            )

        # Gate 3: walk-time cap — always numeric, lossless at max_trip.
        max_walk = self.parameterAsInt(parameters, self.MAX_WALK_TIME, context)
        if self.MAX_WALK_TIME not in parameters or parameters[self.MAX_WALK_TIME] in (None, ""):
            max_walk = max_trip
        elif max_walk < max_trip:
            feedback.pushWarning(
                self.tr("MAX_WALK_TIME ({w} min) is below MAX_TRIP_DURATION ({t} min): faster, "
                        "but trips with a long walk leg will be missed.").format(w=max_walk, t=max_trip)
            )

        try:
            env = java_env.resolve_env(settings.all_settings())
        except java_env.JavaEnvError as exc:
            raise QgsProcessingException(str(exc))
        heap_override = self.parameterAsInt(parameters, self.JAVA_HEAP_GB, context) or None
        if self.JAVA_HEAP_GB not in parameters or parameters[self.JAVA_HEAP_GB] in (None, ""):
            heap_override = settings.get_java_heap_gb()
        heap_mb, heap_warn = java_env.heap_mb_for(java_env.detect_ram_bytes(), heap_override)
        if heap_warn:
            feedback.pushWarning(heap_warn)

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_matrix_"))
        try:
            origins_csv = tmp / "origins.csv"
            dests_csv = tmp / "destinations.csv"
            try:
                origin_ids, o_skipped = points.write_points_csv(
                    origins_src, context, feedback, origin_id_field, origins_csv, label="Origin"
                )
                dest_ids, d_skipped = points.write_points_csv(
                    dests_src, context, feedback, dest_id_field, dests_csv, label="Destination"
                )
            except ValueError as exc:
                raise QgsProcessingException(str(exc))
            if not origin_ids or not dest_ids:
                raise QgsProcessingException(
                    self.tr("No usable points after dropping empty geometries "
                            "({} origins, {} destinations skipped).").format(o_skipped, d_skipped)
                )
            feedback.pushInfo(
                self.tr("{o} origins x {d} destinations = {n} pairs.").format(
                    o=len(origin_ids), d=len(dest_ids), n=len(origin_ids) * len(dest_ids)
                )
            )

            job_common = dict(
                network=str(network_path),
                origins_csv=str(origins_csv),
                destinations_csv=str(dests_csv),
                date=date, departure_time=departure_time,
                time_window_minutes=time_window, percentiles=percentiles,
                max_trip_duration_minutes=max_trip, max_walk_time_minutes=max_walk,
                walk_speed_kmh=walk_speed, bike_speed_kmh=12.0, max_rides=max_rides,
                monte_carlo_draws=monte_carlo,
                access_modes=[direct_mode], egress_modes=[direct_mode],
                direct_modes=[direct_mode], transit_modes=transit_modes,
                write_unreachable=include_unreachable,
            )

            n_batches = math.ceil(len(origin_ids) / batch_size)
            multi = QgsProcessingMultiStepFeedback(n_batches + 1, feedback)

            if estimate_first and len(origin_ids) > 15:
                multi.setCurrentStep(0)
                self._estimate(
                    tmp, origins_csv, origin_ids, job_common, env, heap_mb, multi
                )
            if multi.isCanceled():
                raise QgsProcessingException(self.tr("Cancelled by user."))

            batch_csvs = []
            transit_used = 0
            for b in range(n_batches):
                if multi.isCanceled():
                    raise QgsProcessingException(self.tr("Cancelled by user."))
                multi.setCurrentStep(b + 1)
                start = b * batch_size
                end = min(len(origin_ids), start + batch_size)
                batch_csv = tmp / "matrix_{:06d}.csv".format(start)
                job = job_spec.build_matrix_job(
                    origin_range=[start, end], out_csv=str(batch_csv), **job_common
                )
                cmd = java_env.build_java_command(
                    env, java_env.xmx_arg(heap_mb), job_spec.write_job(job, tmp),
                    extra_jvm_args=["-Djava.io.tmpdir=" + str(tmp)],
                )
                multi.pushInfo(self.tr("Batch {b}/{n}: origins {s}-{e}").format(
                    b=b + 1, n=n_batches, s=start, e=end
                ))
                result = runner.run_job(
                    cmd, multi, cwd=tmp, stderr_log=tmp / "stderr_{:02d}.log".format(b),
                    r5_version=pins.R5_VERSION,
                )
                transit_used += int(result.results.get("transit_used_pairs", 0))
                batch_csvs.append(batch_csv)

            rows = matrix.merge_batch_csvs(batch_csvs, out_csv)
            feedback.pushInfo(self.tr("Wrote {n} rows to {p}").format(n=rows, p=out_csv))

            # Guard 2: nothing used transit -> the walk-only failure (PRD 5.8).
            if is_transit and transit_used == 0:
                raise QgsProcessingException(
                    self.tr(
                        "Not one OD pair is faster by transit than on foot — R5 returned "
                        "walk-only results. Most likely the date has no service or the GTFS "
                        "does not match the network."
                    )
                )

            meta = self._write_meta(out_csv, summary, network_path, date, departure_time,
                                    time_window, percentiles, _MODE_OPTIONS[mode])

            outputs = {self.OUTPUT_CSV: str(out_csv)}
            od_sink = self._build_od_layer(
                parameters, context, out_csv, origins_csv, dests_csv, meta
            )
            if od_sink is not None:
                outputs[self.OUTPUT_LAYER] = od_sink
            return outputs

        except runner.RunnerCancelled:
            raise QgsProcessingException(self.tr("Cancelled by user."))
        except runner.RunnerError as exc:
            if exc.code == "OUT_OF_MEMORY":
                raise QgsProcessingException(
                    self.tr(
                        "R5 ran out of memory (heap {gb} GB, batch size {bs}). Lower the "
                        "batch size, thin the origin grid, or raise the Java heap in the "
                        "plugin settings."
                    ).format(gb=round(heap_mb / 1024, 1), bs=batch_size)
                )
            raise QgsProcessingException(str(exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # --- helpers -----------------------------------------------------------

    def _load_summary(self, network_path):
        try:
            return network_cache.load_summary(network_path.parent)
        except (OSError, ValueError):
            return {}

    def _estimate(self, tmp, origins_csv, origin_ids, job_common, env, heap_mb, feedback):
        idx = matrix.systematic_sample_indices(len(origin_ids), 15)
        lines = origins_csv.read_text(encoding="utf-8").splitlines()
        sample_csv = tmp / "origins_sample.csv"
        sample_csv.write_text(
            "\n".join([lines[0]] + [lines[i + 1] for i in idx]) + "\n", encoding="utf-8"
        )
        job = job_spec.build_matrix_job(
            origin_range=[0, len(idx)], out_csv=str(tmp / "estimate.csv"),
            **{**job_common, "origins_csv": str(sample_csv)},
        )
        cmd = java_env.build_java_command(
            env, java_env.xmx_arg(heap_mb), job_spec.write_job(job, tmp),
            extra_jvm_args=["-Djava.io.tmpdir=" + str(tmp)],
        )
        feedback.pushInfo(self.tr("Timing {n} sample origins…").format(n=len(idx)))
        t0 = time.monotonic()
        try:
            runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr_est.log",
                           r5_version=pins.R5_VERSION)
        except runner.RunnerError as exc:
            feedback.pushWarning(self.tr("Estimate run failed ({}). Continuing.").format(exc))
            return
        per_origin = (time.monotonic() - t0) / max(1, len(idx))
        full_min = per_origin * len(origin_ids) / 60
        feedback.pushInfo(
            self.tr("~{s:.2f} s/origin on this network -> ~{m:.1f} min for {n} origins.").format(
                s=per_origin, m=full_min, n=len(origin_ids)
            )
        )
        if full_min > _SLOW_RUN_MINUTES:
            feedback.pushWarning(
                self.tr("Estimated {m:.0f} min — consider fewer origins or a coarser grid.").format(
                    m=full_min
                )
            )

    def _write_meta(self, out_csv, summary, network_path, date, departure_time,
                    time_window, percentiles, modes):
        meta = {
            "r5_version": summary.get("r5_version", pins.R5_VERSION),
            "network_hash": network_path.parent.name,
            "run_date": date,
            "departure_time": departure_time,
            "time_window": time_window,
            "percentiles": ",".join(str(p) for p in percentiles),
            "modes": modes,
        }
        Path(str(out_csv) + ".meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        return meta

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
