"""Self-check of the canopy mask logic (py scripts/test_canopy.py): thin objects and small patches go, crowns stay,
big smooth tall structures (viaduct decks, flat roofs) go with their edges."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.argv = ["x"]
import canopy_mask as M  # noqa: E402

m = np.zeros((200, 200), bool)
m[50:80, 50:80] = True          # 15 x 15 m crown
m[100:160, 100] = True          # 1-px pole / wire line (0.5 m wide)
m[10:13, 10:13] = True          # 1.5 x 1.5 m = 2.25 m2 speck, below min_patch_m2
out = M.clean(m)
assert out[60, 60] and out.sum() > 0.9 * 900, "crown must survive"
assert not out[100:160, 100].any(), "pole must be removed"
assert not out[10:13, 10:13].any(), "small patch must be removed"

cand = np.zeros((200, 200), bool)
cand[:, 80:120] = True                              # 20 m wide tall band (a deck)
std = np.full((200, 200), 200, np.uint8)            # rough everywhere (200 cm) ...
std[:, 84:116] = 3                                  # ... except the flat interior (3 cm); the 2 m rim stays rough
st = M.structures(cand, std)
assert st[:, 85:115].all() and st[:, 80:84].all(), "smooth deck and its rough rim must be removed"
rough = np.zeros((200, 200), bool); rough[20:60, 20:60] = True
assert not M.structures(rough, np.full((200, 200), 150, np.uint8)).any(), "rough crowns must stay"
print("canopy mask logic OK")
