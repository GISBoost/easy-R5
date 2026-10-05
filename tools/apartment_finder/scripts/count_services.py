"""Count facilities per hex from an R5 travel-time CSV (hex centre -> exact facility coordinates).

  py scripts/count_services.py <times.csv> <out.npz> <levels,comma,separated>

Output: arr uint8 [type, level, hex] = number of facilities of a fine type reached within `level` minutes (type order from
config/services.yaml). System Python (numpy, pandas, yaml).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load(open(HERE / "config/services.yaml", encoding="utf-8"))
crit = list(cfg["types"])
poi = pd.read_csv(HERE / "inputs/service_pois.csv")
tix = poi.crit.map({c: i for i, c in enumerate(crit)}).values
cidx = dict(zip(poi.poi_id, tix))          # string ids (QGIS runs: "<type>/<row>")
by_row = np.asarray(tix)                   # integer ids = row of inputs/service_pois.csv (CI runs, no QGIS)
levels = [int(v) for v in sys.argv[3].split(",")]
N = 5662
acc = np.zeros((len(crit), len(levels), N), np.int32)
for ch in pd.read_csv(sys.argv[1], chunksize=4_000_000):
    c = by_row[ch.to_id.values.astype(int)] if pd.api.types.is_numeric_dtype(ch.to_id) else ch.to_id.map(cidx).values.astype(int)
    h = ch.from_id.values.astype(int)
    t = ch.travel_time_p50.values
    for k, y in enumerate(levels):
        m = t <= y
        np.add.at(acc[:, k, :], (c[m], h[m]), 1)
np.savez_compressed(sys.argv[2], arr=np.minimum(acc, 255).astype(np.uint8), levels=np.array(levels), types=np.array(crit))
print("counted", sys.argv[2], "max", acc.max())
