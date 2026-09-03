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


def write_job(job, tmp_dir):
    """Serialise ``job`` to a uniquely named JSON file in ``tmp_dir``.

    The caller owns the file and must delete it (and ``tmp_dir``) in a
    ``finally`` block.
    """
    tmp_dir = Path(tmp_dir)
    path = tmp_dir / "job_{}.json".format(uuid.uuid4().hex)
    path.write_text(json.dumps(job, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
