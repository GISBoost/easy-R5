"""Export daily-service counts to <easy>/gdzie-mieszkac-lodz-data/services/ (JSON, gzipped by the web server).

  py scripts/export_services.py [--out ../../../gdzie-mieszkac-lodz-data/services]

Fine facility types are summed into the meta-categories of config/services.yaml. Transit: median over the days in config/days.yaml (per fine type and hex, count of facilities within Y min); walk/bike/car:
one run (day-independent, stored under the last day). Writes services/<scenario>.json
({"levels":[...],"crit":[...],"c":{crit:[[count per hex] per level]}}) and services/index.json (criteria, levels per mode,
UI defaults, scenario list, version). Scenarios with missing days are skipped and reported.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/services.yaml", encoding="utf-8"))
days = yaml.safe_load(open(HERE / "config/days.yaml", encoding="utf-8"))["days"]
tw = yaml.safe_load(open(HERE / "config/time_windows.yaml", encoding="utf-8"))["windows"]
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str((HERE / "../../../gdzie-mieszkac-lodz-data/services").resolve()))
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
types = list(cfg["types"])
meta = cfg["meta"]
crit = list(meta)
assert sorted(t for v in meta.values() for t in v) == sorted(types), "every fine type must belong to exactly one meta-category"
TIX = {k: [types.index(t) for t in v] for k, v in meta.items()}


def load(day, name):
    p = HERE / "data/services" / day / (name + ".npz")
    return np.load(p) if p.exists() else None


def write(name, arr, levels):
    arr = np.stack([arr[TIX[k]].astype(np.int32).sum(axis=0) for k in crit]).clip(0, 255)   # fine types -> meta-categories
    body = {"levels": [int(v) for v in levels], "crit": crit,
            "c": {c: [arr[i, k].astype(int).tolist() for k in range(len(levels))] for i, c in enumerate(crit)}}
    (out / (name + ".json")).write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")


names = ["walk", "bike"] + ["car_" + w for w in tw] + \
        ["transit_%s_%s_%s" % (w, t, l) for w in tw for t in ("static", "p50", "p85") for l in ("nolka", "lka")]
done, missing = [], []
for name in names:
    kind = name.split("_")[0]
    if kind == "transit":
        parts = [load(d, name) for d in days]
        if any(p is None for p in parts):
            missing.append(name)
            continue
        arr = np.median(np.stack([p["arr"] for p in parts]), axis=0).astype(np.uint8)   # 5 days: an element, so an integer
        levels = parts[0]["levels"]
    else:
        p = load(days[-1], name)
        if p is None:
            missing.append(name)
            continue
        arr, levels = p["arr"], p["levels"]
    write(name, arr, levels)
    done.append(name)
index = {"services_version": cfg["services_version"], "criteria": crit, "composition": meta,
         "levels": {k: v["levels"] for k, v in cfg["modes"].items()}, "defaults": cfg["defaults"], "scenarios": done,
         "note": "exact R5 method: hex centre -> facility coordinates; transit = median over days, transfers unlimited"}
(out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
print("exported", len(done), "scenarios;", "missing:", len(missing), missing[:4], "..." if len(missing) > 4 else "")
