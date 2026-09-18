"""Write one R5 scenario file per failure case. Runs inside QGIS (uses easyr5:buildscenario).

Three failure modes, because "the line went down" is not one thing:

  removal   -- the line's trips stop existing, nothing replaces them. The upper bound
               for a single line: no operator reacts, no bus is laid on.
  corridor  -- the track is closed, so *every* line using it stops, not just one. This
               is the realistic infrastructure failure, and the only one that actually
               takes the tram away from anyone: in Lodz no single tram line has a stop
               that no other tram line serves (see inputs/tram_lines.csv, pop_exclusive).
               Removing those lines over their whole length overstates it -- in reality
               only the trips through the closed section stop -- so read it as an upper
               bound too.
  bus       -- the line is replaced by a bus on the same alignment, same stops, same
               headway, BUS_SPEED_FACTOR slower. The realistic lower bound.

Plus cascades: the worst N lines together, and every tram line at once. The cascade
membership is decided by measured impact, so build_cascades() runs after run_cases.py
has done the leave-one-out pass.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

try:
    import processing
    from qgis.core import QgsProcessing, QgsVectorLayer
except ImportError as exc:  # pragma: no cover
    raise SystemExit("build_scenarios.py must run inside QGIS.") from exc

import gtfs_lines as gl

HERE = Path(__file__).resolve().parent
GPKG = HERE / "grids" / "h1000.gpkg"   # tram_lines is the same in every grid
SCEN = HERE / "scenarios"
OUT = HERE / "inputs"

BUS_SPEED_FACTOR = 0.80   # replacement bus vs the tram's own between-stop speed
BUS_DWELL_S = 25
SERVICE_START, SERVICE_END = "04:30", "23:30"


def _tmp():
    return QgsProcessing.TEMPORARY_OUTPUT


def selection():
    return json.loads((OUT / "selection.json").read_text(encoding="utf-8"))


def _write(case_id, params):
    SCEN.mkdir(exist_ok=True)
    params = dict(params)
    params["OUTPUT_SCENARIO"] = str(SCEN / f"{case_id}.json")
    processing.run("easyr5:buildscenario", params)
    print(f"[ok] {case_id}.json")
    return params["OUTPUT_SCENARIO"]


def remove_case(case_id, lines):
    """A scenario that deletes the given lines outright."""
    return _write(case_id, {"REMOVE_ROUTES": ", ".join(lines),
                            "NEW_LINE_MODE": 3, "SPEED_KMH": 20.0, "HEADWAY_MINUTES": 10.0,
                            "SERVICE_START": SERVICE_START, "SERVICE_END": SERVICE_END,
                            "SPEED_SCALE": 1.0, "NEW_HEADWAY_MINUTES": 10.0})


def bus_case(case_id, line, feed):
    """Remove the line, put a bus back on the same stops, slower, same headway."""
    lines_layer = QgsVectorLayer(f"{GPKG}|layername=tram_lines", "tram_lines", "ogr")
    if not lines_layer.isValid():
        raise RuntimeError(f"Cannot load tram_lines from {GPKG} -- run prepare_data.py first")
    one = processing.run("native:extractbyexpression", {
        "INPUT": lines_layer, "EXPRESSION": f""""line" = '{line}'""",
        "OUTPUT": _tmp()})["OUTPUT"]
    if one.featureCount() != 1:
        raise RuntimeError(f"expected 1 feature for line {line}, got {one.featureCount()}")

    rid = next(r for r in feed.tram_routes()
               if feed.routes[r]["route_short_name"] == line)
    segs = feed.segments(rid)
    tram_kmh = statistics.median(d / r * 3.6 for d, r, _ in segs)
    headway = round(60 / feed.peak_departures(rid), 1)
    speed = round(tram_kmh * BUS_SPEED_FACTOR, 1)
    print(f"[info] line {line}: tram {tram_kmh:.1f} km/h between stops, "
          f"replacement bus {speed} km/h, headway {headway} min")

    path = _write(case_id, {
        "NEW_LINES": one, "LINE_NAME_FIELD": "line", "NEW_LINE_MODE": 3,  # BUS
        "SPEED_KMH": speed, "DWELL_SECONDS": BUS_DWELL_S, "HEADWAY_MINUTES": headway,
        "SERVICE_START": SERVICE_START, "SERVICE_END": SERVICE_END, "BIDIRECTIONAL": True,
        "REMOVE_ROUTES": line, "SPEED_SCALE": 1.0, "NEW_HEADWAY_MINUTES": 10.0})
    return path, {"tram_kmh": round(tram_kmh, 1), "bus_kmh": speed, "headway_min": headway}


def main():
    sel = selection()
    feed = gl.Feed()
    pick = sel["pick"]["line"]
    corridor = [pick] + [c["line"] for c in sel["corridor"]]
    cases = {}

    for line in sel["all_lines"]:
        cases[f"loo_{line}"] = {"kind": "removal", "lines": [line]}
        remove_case(f"loo_{line}", [line])

    cases["corridor"] = {"kind": "corridor", "lines": corridor}
    remove_case("corridor", corridor)

    cases["all_trams"] = {"kind": "removal", "lines": list(sel["all_lines"])}
    remove_case("all_trams", sel["all_lines"])

    _, bus_meta = bus_case("bus", pick, feed)
    cases["bus"] = {"kind": "bus", "lines": [pick], **bus_meta}

    (OUT / "scenarios.json").write_text(
        json.dumps({"pick": pick, "corridor": corridor, "cases": cases},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[done] {len(cases)} scenarios -> {SCEN}")
    return cases


def build_cascades(worst_lines):
    """Cascade scenarios from the measured leave-one-out ranking (run_cases.py first)."""
    out = {}
    for n in (2, 3, 5):
        if len(worst_lines) >= n:
            case_id = f"cascade_top{n}"
            remove_case(case_id, worst_lines[:n])
            out[case_id] = {"kind": "cascade", "lines": worst_lines[:n]}
    scen = json.loads((OUT / "scenarios.json").read_text(encoding="utf-8"))
    scen["cases"].update(out)
    (OUT / "scenarios.json").write_text(json.dumps(scen, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    print(f"[done] cascades: {list(out)}")
    return out


if __name__ == "__main__":
    main()
