"""Rank Lodz tram lines ex ante: which one is "the biggest and most loaded"?

This is the *selection* step and it runs before R5 sees anything. It writes
out/tram_lines.csv and out/selection.json, which build_scenarios.py reads.

The four criteria come from the brief, two of them reworded to be measurable:

  1. tram                -- a filter (gtfs_lines.Feed.tram_routes)
  2. "runs through the population-weighted centre of the city"
                         -- as stated this is a single point, which no line can
                            usefully be said to pass "through". Measured instead as
                            population living within 500 m of the line's stops.
  3. "slows down most between stops near the centre"
                         -- median scheduled segment speed inside 2.5 km of the
                            centroid vs beyond 4 km. Reported, NOT scored: stops sit
                            closer together downtown, so part of every line's drop is
                            braking, not congestion (see README).
  4. top 25% by length   -- as stated, a hard filter at the P75 of tram line length.

  5. vehicle-km per day  -- added. None of the four measures how much service the line
                            actually puts on the street, which is the closest thing to
                            "load" obtainable without passenger counts.

The pick is the best average rank over (2) and (5) among lines passing (4).
Whether the pick is *right* is not settled here -- run_cases.py removes every line in
turn and compute_impact.py checks the ex-ante ranking against the measured one.
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

import gtfs_lines as gl

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

CORRIDOR_SHARE = 0.60   # a line sharing this much of the pick's stops is on its corridor


def measure(feed, points, centre):
    """One row per tram line with real service."""
    rows = []
    trams = feed.tram_routes()
    stops_by_route = {rid: feed.stops_of(rid) for rid in trams}
    for rid in trams:
        others = {s for r2, ss in stops_by_route.items() if r2 != rid for s in ss}
        exclusive = stops_by_route[rid] - others
        inner, outer, n_in, n_out = feed.speed_profile(rid, centre)
        rows.append({
            "route_id": rid,
            "line": feed.routes[rid]["route_short_name"],
            "trips": len(feed.trips_of(rid)),
            "length_km": round(feed.length_km(rid), 2),
            "stops": len(stops_by_route[rid]),
            "veh_km": round(feed.vehicle_km(rid)),
            "peak_departures_per_h": round(feed.peak_departures(rid), 1),
            "pop_500m": round(gl.population_near(stops_by_route[rid], feed, points)),
            "pop_exclusive": round(gl.population_near(exclusive, feed, points)) if exclusive else 0,
            "stops_exclusive": len(exclusive),
            "inner_kmh": round(inner, 1) if inner else None,
            "outer_kmh": round(outer, 1) if outer else None,
            "centre_slowdown_kmh": round(outer - inner, 1) if inner and outer else None,
            "inner_spacing_m": round(feed.mean_stop_spacing_m(rid, centre, True) or 0),
            "outer_spacing_m": round(feed.mean_stop_spacing_m(rid, centre, False) or 0),
        })
    return rows


def rank(rows):
    """Add the criterion flags and the composite ex-ante rank, in place."""
    p75 = statistics.quantiles(sorted(r["length_km"] for r in rows), n=4)[2]
    by_pop = sorted(rows, key=lambda r: -r["pop_500m"])
    by_vkm = sorted(rows, key=lambda r: -r["veh_km"])
    by_slow = sorted([r for r in rows if r["centre_slowdown_kmh"] is not None],
                     key=lambda r: -r["centre_slowdown_kmh"])
    for r in rows:
        r["length_p75_km"] = round(p75, 2)
        r["meets_length"] = int(r["length_km"] >= p75)
        r["rank_pop"] = by_pop.index(r) + 1
        r["rank_veh_km"] = by_vkm.index(r) + 1
        r["rank_slowdown"] = by_slow.index(r) + 1 if r in by_slow else None
        r["score"] = round((r["rank_pop"] + r["rank_veh_km"]) / 2, 1)
    rows.sort(key=lambda r: (not r["meets_length"], r["score"]))
    return p75


def corridor_of(pick, rows, feed):
    """Lines sharing at least CORRIDOR_SHARE of the picked line's stops.

    This is the "closed track" scenario: an infrastructure failure takes out every
    service on the section, not one line. Removing those lines *entirely* overstates
    it (in reality only the trips through the closed section stop), which is why the
    README calls the corridor variant an upper bound.
    """
    pick_stops = feed.stops_of(pick["route_id"])
    out = []
    for r in rows:
        if r["route_id"] == pick["route_id"]:
            continue
        shared = len(pick_stops & feed.stops_of(r["route_id"])) / len(pick_stops)
        if shared >= CORRIDOR_SHARE:
            out.append({"line": r["line"], "route_id": r["route_id"], "share": round(shared, 3)})
    return sorted(out, key=lambda d: -d["share"])


def main():
    OUT.mkdir(exist_ok=True)
    feed = gl.Feed()
    points = gl.population_points()
    centre = gl.weighted_centroid(points)
    rows = measure(feed, points, centre)
    p75 = rank(rows)

    fields = list(rows[0])
    with open(OUT / "tram_lines.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    pick = next(r for r in rows if r["meets_length"])
    corridor = corridor_of(pick, rows, feed)
    tram_pop = gl.population_near({s for r in rows for s in feed.stops_of(r["route_id"])},
                                  feed, points)
    total_pop = sum(p for p, _, _ in points)

    selection = {
        "analysis_date": gl.ANALYSIS_DATE.isoformat(),
        "gtfs": gl.GTFS.name,
        "centre_lon_lat": [round(centre[0], 6), round(centre[1], 6)],
        "tram_lines": len(rows),
        "length_p75_km": round(p75, 2),
        "pick": {k: pick[k] for k in ("line", "route_id", "pop_500m", "veh_km",
                                      "length_km", "centre_slowdown_kmh", "score")},
        "corridor": corridor,
        "population_total": round(total_pop),
        "population_near_any_tram": round(tram_pop),
        "population_near_any_tram_share": round(tram_pop / total_pop, 4),
        "all_lines": [r["line"] for r in rows],
    }
    (OUT / "selection.json").write_text(json.dumps(selection, indent=2, ensure_ascii=False)
                                        + "\n", encoding="utf-8")

    print(f"{len(rows)} tram lines; length P75 = {p75:.2f} km")
    print(f"{tram_pop / total_pop:.1%} of residents live within {gl.WALK_M} m of a tram stop")
    print("\nline  len_km  pop_500m  veh_km  slowdown  P75?  score")
    for r in rows:
        print(f"{r['line']:>5} {r['length_km']:7.2f} {r['pop_500m']:9} {r['veh_km']:7} "
              f"{str(r['centre_slowdown_kmh']):>9} {'yes' if r['meets_length'] else ' no':>5} "
              f"{r['score']:6}")
    print(f"\npick: line {pick['line']} (route_id {pick['route_id']})")
    print("corridor:", ", ".join(f"{c['line']} ({c['share']:.0%})" for c in corridor) or "none")
    print(f"-> {OUT / 'tram_lines.csv'}, {OUT / 'selection.json'}")


if __name__ == "__main__":
    main()
