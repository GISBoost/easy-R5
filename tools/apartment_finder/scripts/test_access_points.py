"""Self-check of the island detection used by aggregate.py (I6). Run: py scripts/test_access_points.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aggregate import islands  # noqa: E402

m = np.full((6, 6), 20, np.uint8)
np.fill_diagonal(m, 0)
assert islands(m) == []                       # everything reaches everything
m[2, :] = 255; m[2, 2] = 0                    # hex 2 cannot go anywhere ...
m[:, 2] = 255; m[2, 2] = 0                    # ... and nothing reaches it
assert islands(m) == [2]
m2 = np.full((6, 6), 20, np.uint8); np.fill_diagonal(m2, 0); m2[:, 4] = 255; m2[4, 4] = 0
assert islands(m2) == [4]                     # only a column (as destination) is enough
m3 = np.full((6, 6), 20, np.uint8); np.fill_diagonal(m3, 0); m3[1, 3:] = 255
assert islands(m3) == []                      # a hex that reaches some but not all others is not an island
print("access points OK")
