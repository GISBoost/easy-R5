"""Shared matrix machinery for RunTravelTimeMatrix and RunAccessibility.

``RunAccessibility`` is "a layer on top of the matrix" (PRD 4.5): it runs the
exact same one-to-many computation, then sums opportunities in Python. Rather
than copy the ~150 lines of gates / point export / sampled estimate / batched
processes / walk-only guard, both algorithms mix in ``MatrixBase`` and call
``_run_matrix``, which returns the merged matrix CSV plus the id lists and the
method-metadata dict.

The mixin leans on ``QgsProcessingAlgorithm`` for ``parameterAs*`` and on the
concrete class for ``tr()`` (so each translates in its own context) and the
parameter-name constants it defines.
"""

from __future__ import annotations

import datetime
import math
import time
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingException,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFile,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
)

from ..core import job_spec, java_env, matrix, network_cache, pins, points, runner, settings


def _tr(string: str) -> str:
    """Translate shared-mixin strings under a fixed 'MatrixBase' context.

    The concrete algorithms have their own tr() context (their class name), but
    strings that live here must resolve under one stable context or the .qm
    lookup misses — QGIS's i18n only matches on the exact context.
    """
    return QCoreApplication.translate("MatrixBase", string)


MODE_OPTIONS = ["TRANSIT + WALK", "WALK", "BICYCLE", "CAR"]
_TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"]
# index -> (direct/access/egress LegMode, transit mode list)
MODE_MAP = {
    0: ("WALK", _TRANSIT_MODES),
    1: ("WALK", []),
    2: ("BICYCLE", []),
    3: ("CAR", []),
}
_SLOW_RUN_MINUTES = 30


class MatrixBase:
    """Mixin: shared parameters + the batched matrix run. Not an algorithm itself."""

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
    JAVA_HEAP_GB = "JAVA_HEAP_GB"

    # --- parameter wiring -------------------------------------------------

    def _advanced(self, param):
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

    def _add_matrix_params(self, percentile_help, with_destinations=True):
        self.addParameter(
            QgsProcessingParameterFile(
                self.NETWORK, _tr("R5 network (network.dat)"),
                behavior=QgsProcessingParameterFile.File, extension="dat",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(self.ORIGINS, _tr("Origin points"))
        )
        oid = QgsProcessingParameterField(
            self.ORIGIN_ID_FIELD, _tr("Origin id field (blank = feature id)"),
            parentLayerParameterName=self.ORIGINS, optional=True,
        )
        oid.setFlags(oid.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(oid)
        if with_destinations:
            self.addParameter(
                QgsProcessingParameterFeatureSource(
                    self.DESTINATIONS, _tr("Destination points"))
            )
            did = QgsProcessingParameterField(
                self.DEST_ID_FIELD, _tr("Destination id field (blank = feature id)"),
                parentLayerParameterName=self.DESTINATIONS, optional=True,
            )
            did.setFlags(did.flags() | QgsProcessingParameterDefinition.FlagOptional)
            self.addParameter(did)

        dt = QgsProcessingParameterString(
            self.DATE, _tr("Date (yyyy-MM-dd; required for transit)"), optional=True
        )
        dt.setFlags(dt.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(dt)
        self.addParameter(
            QgsProcessingParameterString(
                self.DEPARTURE_TIME, _tr("Departure time (HH:mm)"), defaultValue="07:00"
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIME_WINDOW, _tr("Departure window (minutes)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=120, minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(self.PERCENTILES, percentile_help, defaultValue="50")
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_TRIP_DURATION, _tr("Max trip duration (minutes)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=90, minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.WALK_SPEED, _tr("Walk speed (km/h)"),
                type=QgsProcessingParameterNumber.Double, defaultValue=3.6, minValue=0.1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_RIDES, _tr("Max transit rides (transfers + 1)"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE, _tr("Travel mode"), options=MODE_OPTIONS, defaultValue=0
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.MAX_WALK_TIME, _tr("Max walk time (minutes; blank = lossless default)"),
                type=QgsProcessingParameterNumber.Integer, optional=True, minValue=1,
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.MONTE_CARLO_DRAWS, _tr("Monte Carlo draws per minute"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=5, minValue=1,
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.BATCH_SIZE, _tr("Origins per batch process"),
                type=QgsProcessingParameterNumber.Integer, defaultValue=500,
                minValue=100, maxValue=5000,
            )
        )
        self._advanced(
            QgsProcessingParameterBoolean(
                self.ESTIMATE_FIRST, _tr("Time a sample of origins first"), defaultValue=True
            )
        )
        self._advanced(
            QgsProcessingParameterBoolean(
                self.ALLOW_NO_SERVICE,
                _tr("Run even if the date has no transit service (diagnostic)"),
                defaultValue=False,
            )
        )
        self._advanced(
            QgsProcessingParameterNumber(
                self.JAVA_HEAP_GB, _tr("Java heap (GB; blank = auto)"),
                type=QgsProcessingParameterNumber.Integer, optional=True, minValue=1,
            )
        )

    # --- the run --------------------------------------------------------

    def _run_matrix(self, parameters, context, feedback, *, tmp, matrix_csv,
                    walk_fallback, include_unreachable=False, dest_extra_fields=None,
                    dests_source=None, dest_id_field=""):
        """Export points, run the batched matrix, merge to ``matrix_csv``.

        ``walk_fallback`` is the value MAX_WALK_TIME takes when left blank
        (max trip duration for the matrix, ``max(cutoffs)`` for step decay).
        Returns a dict: ``origin_ids``, ``dest_ids``, ``origins_csv``,
        ``dests_csv``, ``meta``, ``is_transit``, ``mode_label``.
        """
        network_path = Path(self.parameterAsFile(parameters, self.NETWORK, context))
        if not network_path.is_file():
            raise QgsProcessingException(_tr("Network file not found: {}").format(network_path))
        summary = self._load_summary(network_path)
        service_days = summary.get("service_days") or {}

        origins_src = self.parameterAsSource(parameters, self.ORIGINS, context)
        dests_src = dests_source
        if dests_src is None:
            dests_src = self.parameterAsSource(parameters, self.DESTINATIONS, context)
        if origins_src is None or dests_src is None:
            raise QgsProcessingException(_tr("Origin and destination layers are required."))

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
        origin_id_field = self.parameterAsString(parameters, self.ORIGIN_ID_FIELD, context)
        if dests_source is None:
            dest_id_field = self.parameterAsString(parameters, self.DEST_ID_FIELD, context)

        try:
            percentiles = job_spec.parse_percentiles(
                self.parameterAsString(parameters, self.PERCENTILES, context)
            )
        except job_spec.JobSpecError as exc:
            raise QgsProcessingException(str(exc))

        direct_mode, transit_modes = MODE_MAP[mode]
        is_transit = bool(transit_modes)

        if is_transit and not date:
            raise QgsProcessingException(_tr("A date is required for a transit run."))
        if not date:
            date = datetime.date.today().isoformat()
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise QgsProcessingException(
                _tr("DATE must be yyyy-MM-dd (e.g. 2026-08-24); got '{}'.").format(date)
            )
        try:
            datetime.datetime.strptime(departure_time, "%H:%M")
        except ValueError:
            raise QgsProcessingException(
                _tr("DEPARTURE_TIME must be HH:mm (e.g. 07:00); got '{}'.").format(departure_time)
            )

        if is_transit and not service_days:
            feedback.pushWarning(
                _tr("Cannot verify the date against the feed — network.json has no "
                    "service_days. Rebuild the network so the dead-date guard can run.")
            )
        if is_transit and service_days and int(service_days.get(date, 0)) == 0:
            if not allow_no_service:
                nearest = matrix.nearest_served_days(service_days, date, 3)
                raise QgsProcessingException(
                    _tr(
                        "The GTFS feed has no active trips on {date}. R5 would silently "
                        "return walk-only results. Nearest served days: {days}. "
                        "(Advanced: ALLOW_NO_SERVICE overrides this for diagnostics.)"
                    ).format(date=date, days=", ".join(nearest) or _tr("none in the feed span"))
                )
            feedback.pushWarning(
                _tr("ALLOW_NO_SERVICE: {date} has no transit service — expect a walk-only "
                    "failure after the run.").format(date=date)
            )

        max_walk = self.parameterAsInt(parameters, self.MAX_WALK_TIME, context)
        if self.MAX_WALK_TIME not in parameters or parameters[self.MAX_WALK_TIME] in (None, ""):
            max_walk = walk_fallback
        elif max_walk < walk_fallback:
            feedback.pushWarning(
                _tr("MAX_WALK_TIME ({w} min) is below the lossless default ({d} min): "
                    "faster, but trips with a long walk leg will be missed.").format(
                        w=max_walk, d=walk_fallback)
            )

        try:
            env = java_env.resolve_env(settings.all_settings())
        except java_env.JavaEnvError as exc:
            raise QgsProcessingException(str(exc))
        if self.JAVA_HEAP_GB in parameters and parameters[self.JAVA_HEAP_GB] not in (None, ""):
            heap_override = self.parameterAsInt(parameters, self.JAVA_HEAP_GB, context) or None
        else:
            heap_override = settings.get_java_heap_gb()
        heap_mb, heap_warn = java_env.heap_mb_for(java_env.detect_ram_bytes(), heap_override)
        if heap_warn:
            feedback.pushWarning(heap_warn)

        origins_csv = tmp / "origins.csv"
        dests_csv = tmp / "destinations.csv"
        try:
            origin_ids, o_skipped = points.write_points_csv(
                origins_src, context, feedback, origin_id_field, origins_csv, label="Origin"
            )
            dest_ids, d_skipped = points.write_points_csv(
                dests_src, context, feedback, dest_id_field, dests_csv, label="Destination",
                extra_fields=dest_extra_fields,
            )
        except ValueError as exc:
            raise QgsProcessingException(str(exc))
        if not origin_ids or not dest_ids:
            raise QgsProcessingException(
                _tr("No usable points after dropping empty geometries "
                    "({} origins, {} destinations skipped).").format(o_skipped, d_skipped)
            )
        feedback.pushInfo(
            _tr("{o} origins x {d} destinations = {n} pairs.").format(
                o=len(origin_ids), d=len(dest_ids), n=len(origin_ids) * len(dest_ids)
            )
        )

        job_common = dict(
            network=str(network_path), origins_csv=str(origins_csv),
            destinations_csv=str(dests_csv), date=date, departure_time=departure_time,
            time_window_minutes=time_window, percentiles=percentiles,
            max_trip_duration_minutes=max_trip, max_walk_time_minutes=max_walk,
            walk_speed_kmh=walk_speed, bike_speed_kmh=12.0, max_rides=max_rides,
            monte_carlo_draws=monte_carlo, access_modes=[direct_mode],
            egress_modes=[direct_mode], direct_modes=[direct_mode],
            transit_modes=transit_modes, write_unreachable=include_unreachable,
        )

        n_batches = math.ceil(len(origin_ids) / batch_size)
        multi = QgsProcessingMultiStepFeedback(n_batches + 1, feedback)

        if estimate_first and len(origin_ids) > 15:
            multi.setCurrentStep(0)
            try:
                self._estimate(tmp, origins_csv, origin_ids, job_common, env, heap_mb, multi)
            except runner.RunnerCancelled:
                raise QgsProcessingException(_tr("Cancelled by user."))
        if multi.isCanceled():
            raise QgsProcessingException(_tr("Cancelled by user."))

        batch_csvs = []
        transit_used = 0
        try:
            for b in range(n_batches):
                if multi.isCanceled():
                    raise QgsProcessingException(_tr("Cancelled by user."))
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
                multi.pushInfo(_tr("Batch {b}/{n}: origins {s}-{e}").format(
                    b=b + 1, n=n_batches, s=start, e=end
                ))
                result = runner.run_job(
                    cmd, multi, cwd=tmp, stderr_log=tmp / "stderr_{:02d}.log".format(b),
                    r5_version=pins.R5_VERSION,
                )
                transit_used += int(result.results.get("transit_used_pairs", 0))
                batch_csvs.append(batch_csv)
        except runner.RunnerCancelled:
            raise QgsProcessingException(_tr("Cancelled by user."))
        except runner.RunnerError as exc:
            if exc.code == "OUT_OF_MEMORY":
                raise QgsProcessingException(
                    _tr(
                        "R5 ran out of memory (heap {gb} GB, batch size {bs}). Lower the "
                        "batch size, thin the origin grid, or raise the Java heap in the "
                        "plugin settings."
                    ).format(gb=round(heap_mb / 1024, 1), bs=batch_size)
                )
            raise QgsProcessingException(str(exc))

        rows = matrix.merge_batch_csvs(batch_csvs, matrix_csv)
        feedback.pushInfo(_tr("Matrix: {n} reachable pairs.").format(n=rows))

        if is_transit and transit_used == 0:
            raise QgsProcessingException(
                _tr(
                    "Not one OD pair is faster by transit than on foot — R5 returned "
                    "walk-only results. Most likely the date has no service or the GTFS "
                    "does not match the network."
                )
            )

        meta = {
            "r5_version": summary.get("r5_version", pins.R5_VERSION),
            "network_hash": network_path.parent.name,
            "run_date": date,
            "departure_time": departure_time,
            "time_window": time_window,
            # PRD §5.2 names this output field "percentile" (singular); the value
            # is the whole requested list so two maps that differ only by it are
            # still tellable apart.
            "percentile": ",".join(str(p) for p in percentiles),
            "modes": MODE_OPTIONS[mode],
        }
        return {
            "origin_ids": origin_ids, "dest_ids": dest_ids,
            "origins_csv": origins_csv, "dests_csv": dests_csv,
            "origins_crs": origins_src.sourceCrs(),
            "meta": meta, "percentiles": percentiles,
            "is_transit": is_transit, "mode_label": MODE_OPTIONS[mode],
        }

    # --- helpers -------------------------------------------------------

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
        feedback.pushInfo(_tr("Timing {n} sample origins…").format(n=len(idx)))
        t0 = time.monotonic()
        try:
            result = runner.run_job(cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr_est.log",
                                    r5_version=pins.R5_VERSION)
        except runner.RunnerError as exc:
            feedback.pushWarning(_tr("Estimate run failed ({}). Continuing.").format(exc))
            return
        wall = time.monotonic() - t0
        # The runner reports routing time separately from the one-off setup cost
        # (JVM boot + ~100 MB network deserialize + point-set link). Extrapolate
        # from routing time only — the setup cost is paid once, not per origin.
        try:
            routing = float(result.results.get("routing_seconds", 0.0))
        except (TypeError, ValueError):
            routing = 0.0
        per_origin = (routing or wall) / max(1, len(idx))
        setup_min = max(0.0, wall - routing) / 60 if routing else 0.0
        full_min = per_origin * len(origin_ids) / 60 + setup_min
        feedback.pushInfo(
            _tr("~{s:.2f} s/origin on this network -> ~{m:.1f} min for {n} origins "
                "(+{u:.1f} min one-off setup).").format(
                s=per_origin, m=full_min, n=len(origin_ids), u=setup_min
            )
        )
        if full_min > _SLOW_RUN_MINUTES:
            feedback.pushWarning(
                _tr("Estimated {m:.0f} min — consider fewer origins or a coarser grid.").format(
                    m=full_min
                )
            )
