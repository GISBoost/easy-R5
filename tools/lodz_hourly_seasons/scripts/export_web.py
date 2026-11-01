"""data/seasons.npz + summary.json -> the web page data (mapy-analizy/lodz-dostepnosc-godzinowa/data/).

    py scripts/export_web.py [--out ../../../mapy-analizy/lodz-dostepnosc-godzinowa/data]

counts.bin: little-endian uint16, layout [month][meta][hour][hex] (one frame = one contiguous run of `hexes` values).
hex.geojson: the 5662 hexes of the apartment_finder grid (EPSG:4326, 5 decimals), feature order = hex_id = column in counts.bin.
manifest.json: layout + names, so the page hardcodes none of it.
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str((HERE.parents[2] / "mapy-analizy/lodz-dostepnosc-godzinowa/data")))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(HERE / "data/seasons.npz")
    arr = z["arr"]                                              # [month, hour, meta, hex]
    n = arr.shape[-1]
    arr.transpose(0, 2, 1, 3).astype("<u2").tofile(out / "counts.bin")   # -> [month, meta, hour, hex]

    import geopandas as gpd
    g = gpd.read_file(HERE.parent / "apartment_finder/data/grid.gpkg", layer="hex_grid").sort_values("hex_id")
    assert list(g.hex_id) == list(range(n)), "hex_id must be 0..n-1 in column order"
    g = g.to_crs(4326)[["hex_id", "geometry"]]
    g.to_file(out / "hex.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    s = json.load(open(HERE / "data/summary.json", encoding="utf-8"))
    man = {"months": s["months"], "hours": s["hours"], "meta": s["meta"], "hexes": n, "layout": "month,meta,hour,hex uint16 LE",
           "pop_weighted_mean": s["pop_weighted_mean"]}
    json.dump(man, open(out / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for f in ("counts.bin", "hex.geojson", "manifest.json"):
        print(f, round((out / f).stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
