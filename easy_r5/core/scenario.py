"""Build and read R5 scenario files (PR_easy-R5_v03.md R-1).

Pure stdlib — unit-testable outside QGIS. A scenario file is R5's own
modification JSON (``{"id", "modifications": [...]}``) plus three easy-R5
shorthands the Java runner expands against the loaded network, because only it
knows route/pattern/trip ids: ``easy-remove-routes``, ``easy-adjust-speed``,
``easy-set-headway``.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

# GTFS basic route_type per mode offered for a new line.
LINE_MODES = {"TRAM": 0, "SUBWAY": 1, "RAIL": 2, "BUS": 3, "FERRY": 4}

EASY_TYPES = ("easy-remove-routes", "easy-adjust-speed", "easy-set-headway")
# R5 7.6 ModificationTypeResolver names (javap, 2026-09-17).
R5_TYPES = ("add-streets", "add-trips", "adjust-dwell-time", "adjust-frequency", "adjust-speed",
            "modify-streets", "pickup-delay", "remove-stops", "remove-trips", "reroute",
            "road-congestion", "raster-cost", "shapefile-lts", "set-fare-calculator")

_EARTH_RADIUS_M = 6371008.8
_ALL_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class ScenarioError(ValueError):
    """A scenario cannot be built or read."""


def hhmm_seconds(text):
    """'06:30' -> 23400. Raises ScenarioError."""
    try:
        h, m = str(text).strip().split(":")
        h, m = int(h), int(m)
    except ValueError:
        raise ScenarioError("Time must be HH:mm (got {!r}).".format(text))
    if not (0 <= h <= 30 and 0 <= m < 60):
        raise ScenarioError("Time out of range: {!r}.".format(text))
    return h * 3600 + m * 60


def haversine_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def parse_route_list(text):
    """'86, Z2  14' -> ['86', 'Z2', '14'] (commas or whitespace; blanks dropped; order kept, deduped)."""
    out = []
    for token in str(text or "").replace(";", ",").replace(",", " ").split():
        if token not in out:
            out.append(token)
    return out


def line_to_add_trips(coords, *, mode="BUS", speed_kmh=25.0, dwell_seconds=30, headway_minutes=10.0,
                      start="05:00", end="23:00", bidirectional=True, name=""):
    """One ``add-trips`` modification: a stop at every vertex of ``coords`` [(lon, lat), ...] in WGS84.

    Hop times come from great-circle distance / ``speed_kmh`` (at least 1 s).
    Consecutive duplicate vertices are merged.
    """
    if mode not in LINE_MODES:
        raise ScenarioError("Unknown mode {!r}; use one of {}.".format(mode, ", ".join(LINE_MODES)))
    if speed_kmh <= 0:
        raise ScenarioError("Speed must be positive.")
    if headway_minutes <= 0:
        raise ScenarioError("Headway must be positive.")
    if dwell_seconds < 0:
        raise ScenarioError("Dwell time cannot be negative.")
    start_s, end_s = hhmm_seconds(start), hhmm_seconds(end)
    if end_s <= start_s:
        raise ScenarioError("Service end must be after service start.")

    stops = []
    for lon, lat in coords:
        pt = (round(float(lon), 6), round(float(lat), 6))
        if not stops or stops[-1] != pt:
            stops.append(pt)
    if len(stops) < 2:
        raise ScenarioError("A new line needs at least two distinct vertices{}.".format(
            " ({})".format(name) if name else ""))

    speed_ms = speed_kmh / 3.6
    hops = [max(1, int(round(haversine_m(*a, *b) / speed_ms))) for a, b in zip(stops, stops[1:])]
    timetable = {
        "entryId": (name or "line") + "-f",
        "hopTimes": hops,
        "dwellTimes": [int(dwell_seconds)] * len(stops),
        "headwaySecs": int(round(headway_minutes * 60)),
        "startTime": start_s,
        "endTime": end_s,
    }
    timetable.update({d: True for d in _ALL_DAYS})
    mod = {
        "type": "add-trips",
        "mode": LINE_MODES[mode],
        "bidirectional": bool(bidirectional),
        "stops": [{"lon": lon, "lat": lat} for lon, lat in stops],
        "frequencies": [timetable],
    }
    if name:
        mod["comment"] = str(name)
    return mod


def build_scenario(*, new_lines=(), remove_routes=(), speed_routes=(), speed_scale=1.0,
                   headway_routes=(), headway_minutes=10.0, headway_start="05:00",
                   headway_end="23:00", scenario_id="easy-r5-scenario"):
    """Assemble a scenario dict. ``new_lines`` are ready ``add-trips`` dicts."""
    mods = list(new_lines)
    if remove_routes:
        mods.append({"type": "easy-remove-routes", "routes": list(remove_routes)})
    if speed_routes:
        if speed_scale <= 0:
            raise ScenarioError("Speed scale must be positive (0.8 = 20% slower).")
        mods.append({"type": "easy-adjust-speed", "routes": list(speed_routes),
                     "scale": float(speed_scale)})
    if headway_routes:
        if headway_minutes <= 0:
            raise ScenarioError("Headway must be positive.")
        if hhmm_seconds(headway_end) <= hhmm_seconds(headway_start):
            raise ScenarioError("Headway end must be after headway start.")
        mods.append({"type": "easy-set-headway", "routes": list(headway_routes),
                     "headway_minutes": float(headway_minutes),
                     "start": headway_start, "end": headway_end})
    if not mods:
        raise ScenarioError("The scenario has no modifications — add a new line, or list routes "
                            "to remove, slow down or re-time.")
    return {"id": scenario_id, "modifications": mods}


def load_scenario(path):
    """Read and shape-check a scenario file. Returns the dict. Raises ScenarioError."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScenarioError("Cannot read scenario file {}: {}".format(path, exc))
    except ValueError as exc:
        raise ScenarioError("Scenario file {} is not valid JSON: {}".format(path, exc))
    mods = data.get("modifications") if isinstance(data, dict) else None
    if not isinstance(mods, list) or not mods:
        raise ScenarioError("Scenario file {} has no 'modifications' list.".format(path))
    for i, m in enumerate(mods):
        t = m.get("type") if isinstance(m, dict) else None
        if t not in EASY_TYPES + R5_TYPES:
            raise ScenarioError("Modification #{} has unknown type {!r}.".format(i + 1, t))
    return data


def scenario_label(path):
    """'<file name>:<first 8 hex of sha256>' — recorded in the run metadata."""
    path = Path(path)
    return "{}:{}".format(path.name, hashlib.sha256(path.read_bytes()).hexdigest()[:8])
