"""Per-day npz (ci_hourly.py) -> month layers: median over the month's days, fine types summed to the 4 meta-categories.

    py scripts/aggregate.py [--pop <lodzkie_base.gpkg>]

Writes data/seasons.npz: arr uint16 [month, hour, meta, hex], plus data/summary.json: population-weighted mean count per
(month, hour, meta). Population: hex_lodz_all.pop_total of the competition base (250 m hexes) joined to the 5662 apartment_finder
hexes by centroid (both grids come from the same recipe, so a centroid falls inside a single hex).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config.yaml", encoding="utf-8"))
svc = yaml.safe_load(open(HERE.parent / "apartment_finder/config/services.yaml", encoding="utf-8"))
META = svc["meta"]
TYPES = list(svc["types"])
assert sorted(t for v in META.values() for t in v) == sorted(TYPES)


def population(gpkg):
    import geopandas as gpd
    cent = gpd.read_file(HERE.parent / "apartment_finder/data/grid.gpkg", layer="hex_centroids").sort_values("hex_id")
    hexes = gpd.read_file(gpkg, layer="hex_lodz_all")[["pop_total", "geometry"]].to_crs(cent.crs)
    j = gpd.sjoin(cent, hexes, how="left", predicate="within")
    j = j[~j.index.duplicated()].sort_values("hex_id")
    return j.pop_total.fillna(0).values, int(j.pop_total.isna().sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", default=str(HERE.parent / "lodzkie_na_mapach_2026/lodzkie_base.gpkg"))
    a = ap.parse_args()
    months, hours = list(cfg["months"]), cfg["hours"]
    out = []
    for m, days in cfg["months"].items():
        zs = [np.load(HERE / "data" / (d + ".npz")) for d in days]
        assert all(list(z["hours"]) == hours and [str(t) for t in z["types"]] == TYPES for z in zs), m
        assert len(zs) % 2 == 1
        med = np.median(np.stack([z["arr"] for z in zs]), axis=0).astype(np.uint16)      # [hour, type, hex]
        out.append(np.stack([med[:, [TYPES.index(t) for t in ts], :].sum(axis=1) for ts in META.values()], axis=1))
    arr = np.stack(out)                                                                   # [month, hour, meta, hex]
    np.savez_compressed(HERE / "data/seasons.npz", arr=arr, months=np.array(months), hours=np.array(hours),
                        meta=np.array(list(META)))
    pop, missing = population(a.pop)
    w = pop / pop.sum()
    mean = (arr * w).sum(axis=-1)                                                         # [month, hour, meta]
    summ = {"months": months, "hours": hours, "meta": list(META), "hexes": arr.shape[-1], "hexes_without_pop_match": missing,
            "pop_weighted_mean": {m: {k: [round(float(v), 2) for v in mean[i, :, j]] for j, k in enumerate(META)}
                                  for i, m in enumerate(months)}}
    json.dump(summ, open(HERE / "data/summary.json", "w", encoding="utf-8"), indent=1)
    print("hexes without population match:", missing)
    for m in months:
        print(m, {k: v[:3] + ["..."] for k, v in summ["pop_weighted_mean"][m].items()})


if __name__ == "__main__":
    main()
