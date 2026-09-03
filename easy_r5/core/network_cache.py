"""Cache a built network by the hash of its inputs plus the R5 version.

Pure stdlib. A network written by one R5 version refuses to load in another
(KryoNetworkSerializer format check), so the R5 version is part of the key — a
version bump invalidates every cached network automatically.

"Complete" is a sentinel pair: both ``network.dat`` and ``network.json`` present.
``network.json`` is written last (and by Python, after service_days is merged in),
so a build that crashed or was cancelled never looks cached. The caller wipes
both before starting a build.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .java_env import sha256_file

_NETWORK_DAT = "network.dat"
_NETWORK_JSON = "network.json"
_KEY_LEN = 16


def cache_key(osm_path, gtfs_paths, r5_version):
    """Deterministic key from input file contents + R5 version.

    Order-independent in the GTFS list (the digests are sorted), so renaming or
    reordering feed files does not churn the cache.
    """
    h = hashlib.sha256()
    h.update(sha256_file(osm_path).encode())
    for digest in sorted(sha256_file(p) for p in gtfs_paths):
        h.update(digest.encode())
    h.update(str(r5_version).encode())
    return h.hexdigest()[:_KEY_LEN]


def cache_dir(base, key):
    return Path(base) / key


def is_complete(cd):
    cd = Path(cd)
    return (cd / _NETWORK_DAT).is_file() and (cd / _NETWORK_JSON).is_file()


def wipe(cd):
    """Remove the sentinel pair. Idempotent."""
    cd = Path(cd)
    for name in (_NETWORK_DAT, _NETWORK_JSON):
        try:
            (cd / name).unlink()
        except FileNotFoundError:
            pass


def network_dat(cd):
    return Path(cd) / _NETWORK_DAT


def network_json(cd):
    return Path(cd) / _NETWORK_JSON


def load_summary(cd):
    return json.loads(network_json(cd).read_text(encoding="utf-8"))
