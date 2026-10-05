"""Pack an R5 matrix CSV (from_id,to_id,travel_time_p50[,travel_time_p85]) into a uint8 .npz.

255 = not reached (omitted by R5), minutes are capped at 254. System Python (numpy, pandas).
"""
import sys

import numpy as np
import pandas as pd

N = 5662  # hexes of grid hex250-v1 (data/grid.meta.json); asserted below


def main(csv_path, npz_path):
    out = {}
    for col in ("travel_time_p50", "travel_time_p85"):
        out[col[-3:]] = np.full((N, N), 255, np.uint8)
    for chunk in pd.read_csv(csv_path, chunksize=2_000_000):
        assert chunk.from_id.max() < N and chunk.to_id.max() < N and chunk.from_id.min() >= 0 and chunk.to_id.min() >= 0
        for col in ("travel_time_p50", "travel_time_p85"):
            if col in chunk:
                v = chunk[col].round().clip(0, 254).fillna(255).astype(np.uint8).values  # blank = not reached at that percentile
                out[col[-3:]][chunk.from_id.values, chunk.to_id.values] = v
    out = {k: v for k, v in out.items() if (v != 255).any()}
    np.savez_compressed(npz_path, **out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
