"""Build and validate the JSON job spec handed to EasyR5Runner.

Pure stdlib, no QGIS imports — unit-testable outside the QGIS interpreter.

M1 only produces the ``info`` job. The percentile validator lives here already
because the runner protocol and later milestones (matrix, M3) depend on it and
the M1 test suite covers it.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

# R5's AnalysisWorkerTask.MAX_PERCENTILES, verified 2026-09-02
# (validatePercentiles() throws IllegalArgumentException on six values).
MAX_PERCENTILES = 5

# TravelTimeResult.histograms is allocated as `new int[nPoints][120]` — a fixed
# size, independent of maxTripDurationMinutes (verified 2026-09-17 by javap-
# disassembling com.conveyal.r5.analyst.cluster.TravelTimeResult in the pinned
# r5-v7.6-all.jar: `bipush 120; multianewarray [[I`). recordHistogramIfEnabled
# then does an unguarded `histograms[target][travelTimeSeconds / 60]++` — no
# bounds check. So whenever record_histograms is on, max_trip_duration_minutes
# must stay below 120, or a reachable trip at/above 120 min throws
# ArrayIndexOutOfBoundsException deep inside R5.
HISTOGRAM_MAX_MINUTES = 119


class JobSpecError(ValueError):
    """A job spec is malformed or a parameter is out of the range R5 accepts."""


def validate_percentiles(values):
    """Return ``values`` unchanged, or raise ``JobSpecError``.

    R5 accepts at most 5 percentiles, each an integer in 1..99, strictly
    ascending. Validate here, before spawning Java — R5 throws an opaque
    IllegalArgumentException otherwise.
    """
    values = list(values)
    if not values:
        raise JobSpecError("No percentiles given (need 1 to 5).")
    if len(values) > MAX_PERCENTILES:
        raise JobSpecError(
            "R5 accepts at most {} percentiles (got {}).".format(
                MAX_PERCENTILES, len(values)
            )
        )
    for v in values:
        if not isinstance(v, int) or isinstance(v, bool):
            raise JobSpecError("Percentile {!r} is not an integer.".format(v))
        if not 1 <= v <= 99:
            raise JobSpecError(
                "Percentile {} is out of range (must be 1 to 99).".format(v)
            )
    if any(b <= a for a, b in zip(values, values[1:])):
        raise JobSpecError(
            "Percentiles must be strictly ascending (got {}).".format(values)
        )
    return values


def parse_percentiles(text):
    """Parse a user string like ``"25, 50 ,75"`` into a validated list."""
    tokens = [t for t in text.replace(",", " ").split() if t]
    try:
        values = [int(t) for t in tokens]
    except ValueError as exc:
        raise JobSpecError(
            "Percentiles must be whole numbers separated by commas "
            "(got {!r}).".format(text)
        ) from exc
    return validate_percentiles(values)


def build_info_job(network_path):
    """Build the ``info`` job: load a network.dat and report its metadata."""
    network_path = str(network_path or "").strip()
    if not network_path:
        raise JobSpecError("No network file given for the 'info' command.")
    return {"command": "info", "network": network_path}


def build_build_job(osm_path, gtfs_paths, out_network, out_summary):
    """Build the ``build`` job: build a network.dat + structural network.json."""
    osm_path = str(osm_path or "").strip()
    gtfs = [str(p).strip() for p in gtfs_paths if str(p).strip()]
    out_network = str(out_network or "").strip()
    out_summary = str(out_summary or "").strip()
    if not osm_path:
        raise JobSpecError("No OSM .pbf given for the 'build' command.")
    if not gtfs:
        raise JobSpecError("No GTFS feeds given for the 'build' command.")
    if not out_network or not out_summary:
        raise JobSpecError("'build' needs both out_network and out_summary paths.")
    return {
        "command": "build",
        "osm": osm_path,
        "gtfs": gtfs,
        "out_network": out_network,
        "out_summary": out_summary,
    }


def build_matrix_job(
    *,
    network,
    origins_csv,
    destinations_csv,
    origin_range,
    date,
    departure_time,
    time_window_minutes,
    percentiles,
    max_trip_duration_minutes,
    max_walk_time_minutes,
    walk_speed_kmh,
    bike_speed_kmh,
    max_rides,
    monte_carlo_draws,
    access_modes,
    egress_modes,
    direct_modes,
    transit_modes,
    write_unreachable,
    out_csv,
):
    """Build the ``matrix`` job: one-to-many travel times, PRD 3.2 shape.

    ``max_walk_time_minutes`` is always written as a positive int — an empty or
    non-positive value falls back to ``max_trip_duration_minutes`` (a lossless
    cap: a single walk leg longer than the whole trip budget cannot belong to a
    trip that fits the budget). The runner must never route with an unbounded
    walk radius (PRD 2.1, lesson 2).
    """
    network = str(network or "").strip()
    origins_csv = str(origins_csv or "").strip()
    destinations_csv = str(destinations_csv or "").strip()
    out_csv = str(out_csv or "").strip()
    if not network:
        raise JobSpecError("No network file given for the 'matrix' command.")
    if not origins_csv or not destinations_csv:
        raise JobSpecError("'matrix' needs both origins and destinations CSVs.")
    if not out_csv:
        raise JobSpecError("'matrix' needs an out_csv path.")

    percentiles = validate_percentiles(percentiles)

    trip_dur = int(max_trip_duration_minutes)
    if trip_dur <= 0:
        raise JobSpecError("max_trip_duration_minutes must be positive.")
    try:
        walk_cap = int(max_walk_time_minutes)
    except (TypeError, ValueError):
        walk_cap = 0
    if walk_cap <= 0:
        walk_cap = trip_dur

    direct = [str(m).strip().upper() for m in direct_modes if str(m).strip()]
    access = [str(m).strip().upper() for m in access_modes if str(m).strip()]
    egress = [str(m).strip().upper() for m in egress_modes if str(m).strip()]
    transit = [str(m).strip().upper() for m in transit_modes if str(m).strip()]
    if not direct:
        raise JobSpecError("'matrix' needs at least one direct mode.")

    rng = list(origin_range) if origin_range is not None else None
    if rng is not None and (len(rng) != 2 or rng[0] < 0 or rng[1] < rng[0]):
        raise JobSpecError("origin_range must be [start, end] with 0 <= start <= end.")

    return {
        "command": "matrix",
        "network": network,
        "origins": origins_csv,
        "destinations": destinations_csv,
        "origin_range": rng,
        "date": str(date).strip(),
        "departure_time": str(departure_time).strip(),
        "time_window_minutes": int(time_window_minutes),
        "percentiles": percentiles,
        "max_trip_duration_minutes": trip_dur,
        "max_walk_time_minutes": walk_cap,
        "walk_speed_kmh": float(walk_speed_kmh),
        "bike_speed_kmh": float(bike_speed_kmh),
        "max_rides": int(max_rides),
        "monte_carlo_draws": int(monte_carlo_draws),
        "access_modes": access,
        "egress_modes": egress,
        "direct_modes": direct,
        "transit_modes": transit,
        "write_unreachable": bool(write_unreachable),
        "out_csv": out_csv,
    }


def build_service_minutes_job(
    *,
    network,
    origins_csv,
    destinations_csv,
    origin_range,
    date,
    departure_time,
    time_window_minutes,
    cutoffs,
    max_trip_duration_minutes,
    max_walk_time_minutes,
    walk_speed_kmh,
    bike_speed_kmh,
    max_rides,
    monte_carlo_draws,
    access_modes,
    egress_modes,
    direct_modes,
    transit_modes,
    write_unreachable,
    out_csv,
):
    """Build a ``matrix`` job in service-minutes mode (PR_easy-R5_v02_service-minutes.md §3).

    Same command as ``build_matrix_job`` — the runner's dead-date/walk-only
    detector must stay single-sourced (see the PRD's §1.2). ``percentiles`` is
    always the fixed, internal ``[50]`` (never user-facing); ``cutoffs`` drives
    the ``svc_min_c<cutoff>`` columns Java emits from the departure-minute
    histogram instead of percentile columns.
    """
    cutoffs = sorted({int(c) for c in cutoffs})
    if not cutoffs or cutoffs[0] < 1:
        raise JobSpecError("Give at least one positive cutoff.")
    if cutoffs[-1] > HISTOGRAM_MAX_MINUTES:
        raise JobSpecError(
            "Cutoffs must be at most {} minutes — R5's departure-minute histogram "
            "is a fixed 120-minute range (0-{}).".format(
                HISTOGRAM_MAX_MINUTES, HISTOGRAM_MAX_MINUTES
            )
        )
    if int(max_trip_duration_minutes) > HISTOGRAM_MAX_MINUTES:
        raise JobSpecError(
            "max_trip_duration_minutes must be at most {} minutes when "
            "record_histograms is on — R5's histogram is a fixed 120-minute range "
            "(0-{}) regardless of trip duration; a larger cap corrupts the "
            "recording.".format(HISTOGRAM_MAX_MINUTES, HISTOGRAM_MAX_MINUTES)
        )

    job = build_matrix_job(
        network=network,
        origins_csv=origins_csv,
        destinations_csv=destinations_csv,
        origin_range=origin_range,
        date=date,
        departure_time=departure_time,
        time_window_minutes=time_window_minutes,
        percentiles=[50],
        max_trip_duration_minutes=max_trip_duration_minutes,
        max_walk_time_minutes=max_walk_time_minutes,
        walk_speed_kmh=walk_speed_kmh,
        bike_speed_kmh=bike_speed_kmh,
        max_rides=max_rides,
        monte_carlo_draws=monte_carlo_draws,
        access_modes=access_modes,
        egress_modes=egress_modes,
        direct_modes=direct_modes,
        transit_modes=transit_modes,
        write_unreachable=write_unreachable,
        out_csv=out_csv,
    )
    job["record_histograms"] = True
    job["service_minute_cutoffs"] = cutoffs
    return job


def write_job(job, tmp_dir):
    """Serialise ``job`` to a uniquely named JSON file in ``tmp_dir``.

    The caller owns the file and must delete it (and ``tmp_dir``) in a
    ``finally`` block.
    """
    tmp_dir = Path(tmp_dir)
    path = tmp_dir / "job_{}.json".format(uuid.uuid4().hex)
    path.write_text(json.dumps(job, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
