"""Isochrone helpers that are pure enough to test without QGIS —
run: py -m pytest easy_r5/test/test_isochrones.py -v"""

from easy_r5.core.matrix import utm_epsg


def test_utm_epsg_northern_hemisphere():
    assert utm_epsg(18.6, 54.4) == 32634   # Gdańsk, zone 34N
    assert utm_epsg(0.0, 51.5) == 32631    # London, zone 31N


def test_utm_epsg_southern_hemisphere():
    assert utm_epsg(-58.4, -34.6) == 32721  # Buenos Aires, zone 21S


def test_utm_epsg_zone_boundaries_and_clamp():
    assert utm_epsg(-180.0, 0.0) == 32601
    assert utm_epsg(179.999, 0.0) == 32660
    assert utm_epsg(180.0, 0.0) == 32660   # antimeridian clamps to 60, not 61
