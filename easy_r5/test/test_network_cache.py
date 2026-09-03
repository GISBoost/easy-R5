"""network_cache key stability and sentinel handling. Pure Python.
Run: py -m pytest easy_r5/test/test_network_cache.py -v
"""

from easy_r5.core import network_cache


def _inputs(tmp_path, osm=b"osm-bytes", gtfs=(b"feed-a", b"feed-b")):
    o = tmp_path / "city.osm.pbf"
    o.write_bytes(osm)
    gs = []
    for i, data in enumerate(gtfs):
        g = tmp_path / "feed_{}.zip".format(i)
        g.write_bytes(data)
        gs.append(g)
    return o, gs


def test_cache_key_deterministic(tmp_path):
    o, gs = _inputs(tmp_path)
    k1 = network_cache.cache_key(o, gs, "7.6")
    k2 = network_cache.cache_key(o, gs, "7.6")
    assert k1 == k2 and len(k1) == 16


def test_cache_key_changes_with_r5_version(tmp_path):
    o, gs = _inputs(tmp_path)
    assert network_cache.cache_key(o, gs, "7.6") != network_cache.cache_key(o, gs, "7.7")


def test_cache_key_changes_with_gtfs_content(tmp_path):
    o, gs = _inputs(tmp_path)
    k1 = network_cache.cache_key(o, gs, "7.6")
    gs[0].write_bytes(b"feed-a-modified")
    assert network_cache.cache_key(o, gs, "7.6") != k1


def test_cache_key_changes_with_osm_content(tmp_path):
    o, gs = _inputs(tmp_path)
    k1 = network_cache.cache_key(o, gs, "7.6")
    o.write_bytes(b"different osm")
    assert network_cache.cache_key(o, gs, "7.6") != k1


def test_cache_key_gtfs_order_independent(tmp_path):
    o, gs = _inputs(tmp_path)
    assert network_cache.cache_key(o, gs, "7.6") == network_cache.cache_key(o, list(reversed(gs)), "7.6")


def test_is_complete(tmp_path):
    cd = tmp_path / "abc123"
    cd.mkdir()
    assert not network_cache.is_complete(cd)
    (cd / "network.dat").write_bytes(b"x")
    assert not network_cache.is_complete(cd)
    (cd / "network.json").write_text("{}")
    assert network_cache.is_complete(cd)


def test_wipe_idempotent(tmp_path):
    cd = tmp_path / "abc123"
    cd.mkdir()
    (cd / "network.dat").write_bytes(b"x")
    (cd / "network.json").write_text("{}")
    network_cache.wipe(cd)
    assert not (cd / "network.dat").exists()
    assert not (cd / "network.json").exists()
    network_cache.wipe(cd)  # no raise on already-gone


def test_load_summary(tmp_path):
    cd = tmp_path / "abc123"
    cd.mkdir()
    (cd / "network.json").write_text('{"stops": 1619}', encoding="utf-8")
    assert network_cache.load_summary(cd) == {"stops": 1619}
