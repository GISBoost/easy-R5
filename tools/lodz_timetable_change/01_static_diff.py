"""Step 0 of S3: diff the Lodz static GTFS variants found by 00_fetch_freeze.py.

    py -I 01_static_diff.py

Groups days by static SHA-256, then per unique feed reports feed_info, calendar validity,
route/trip/stop counts and trips active on each day it was published (trips active on the
day from calendar + calendar_dates, not share of service_id). Consecutive variants are
compared by route set. Writes <data_dir>/static_diff.json and prints a table.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DATA = Path(yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))["data_dir"])


def rows(z: zipfile.ZipFile, name: str):
    if name not in z.namelist():
        return []
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


def active_services(cal, cal_dates, day: dt.date) -> set[str]:
    ymd = day.strftime("%Y%m%d")
    wd = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day.weekday()]
    on = {r["service_id"] for r in cal if r["start_date"] <= ymd <= r["end_date"] and r.get(wd) == "1"}
    for r in cal_dates:
        if r["date"] == ymd:
            (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
    return on


LOOKAHEAD_DAYS = 10  # ponytail: fixed look-ahead; move to config.yaml if it needs tuning


def main() -> None:
    manifest = [json.loads(l) for l in (DATA / "fetch_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    by_hash: dict[str, list[str]] = defaultdict(list)
    for r in manifest:
        if r["kind"] == "static" and r["status"] != "missing":
            by_hash[r["sha256"]].append(r["date"])
    out = []
    for h, days in sorted(by_hash.items(), key=lambda kv: min(kv[1])):
        days.sort()
        z = zipfile.ZipFile(DATA / "raw" / "static" / f"lodz_static_gtfs_{days[0]}.zip")
        routes, trips = rows(z, "routes.txt"), rows(z, "trips.txt")
        cal, cd = rows(z, "calendar.txt"), rows(z, "calendar_dates.txt")
        fi = rows(z, "feed_info.txt")
        svc_by_day = {d: active_services(cal, cd, dt.date.fromisoformat(d)) for d in days}
        active = {d: sum(1 for t in trips if t["service_id"] in svc_by_day[d]) for d in days}
        route_by_trip = {t["trip_id"]: t["route_id"] for t in trips}
        active_routes = {d: sorted({t["route_id"] for t in trips if t["service_id"] in svc_by_day[d]}) for d in days}
        short = {r["route_id"]: r.get("route_short_name", "") for r in routes}
        # Look-ahead: feeds with 3 merged versions (feed_info lists several) carry future days.
        ahead = [(dt.date.fromisoformat(days[-1]) + dt.timedelta(n)).isoformat() for n in range(1, LOOKAHEAD_DAYS + 1)]
        fwd = {}
        for d in ahead:
            sv = active_services(cal, cd, dt.date.fromisoformat(d))
            fwd[d] = {"trips": sum(1 for t in trips if t["service_id"] in sv),
                      "lines": sorted({short[t["route_id"]] for t in trips if t["service_id"] in sv})}
        out.append({
            "forward": fwd,
            "sha256": h, "days": days, "n_routes": len(routes), "n_trips": len(trips),
            "n_stops": len(rows(z, "stops.txt")),
            "feed_info": fi[0] if fi else None,
            "calendar_from": min((r["start_date"] for r in cal), default=None),
            "calendar_to": max((r["end_date"] for r in cal), default=None),
            "n_calendar_dates": len(cd),
            "active_trips_by_day": active,
            "active_lines_by_day": {d: sorted({short[r] for r in rs}) for d, rs in active_routes.items()},
            "files": sorted(z.namelist()),
        })
    for prev, cur in zip(out, out[1:]):
        a, b = set(prev["active_lines_by_day"][prev["days"][-1]]), set(cur["active_lines_by_day"][cur["days"][0]])
        cur["lines_added_vs_prev"], cur["lines_removed_vs_prev"] = sorted(b - a), sorted(a - b)
    (DATA / "static_diff.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} unique statics")
    for v in out:
        d0, d1 = v["days"][0], v["days"][-1]
        print(f"{v['sha256'][:8]} {d0}..{d1} ({len(v['days'])}d) routes={v['n_routes']} trips={v['n_trips']} stops={v['n_stops']} "
              f"cal={v['calendar_from']}..{v['calendar_to']} cd={v['n_calendar_dates']} "
              f"feed_info={(v['feed_info'] or {}).get('feed_version') or (v['feed_info'] or {}).get('feed_start_date')}")
        print(f"   active trips: " + ", ".join(f"{d[5:]}:{n}" for d, n in v["active_trips_by_day"].items()))
        if "lines_added_vs_prev" in v:
            print(f"   +lines {v['lines_added_vs_prev']}  -lines {v['lines_removed_vs_prev']}")


if __name__ == "__main__":
    main()
