"""Stub the QGIS / GDAL imports so the pure-Python core is testable outside QGIS.

Mirrors the pattern used across easy_otp/test/. The core modules under test
(job_spec, runner, java_env) import no qgis; this only matters for a transitive
import of core.settings.
"""

import sys
from unittest.mock import MagicMock


class _FakeQgsProcessingException(RuntimeError):
    pass


if "qgis" not in sys.modules:
    _core = MagicMock()
    _core.QgsProcessingException = _FakeQgsProcessingException
    sys.modules["qgis"] = MagicMock()
    sys.modules["qgis.core"] = _core
    sys.modules["qgis.PyQt"] = MagicMock()
    sys.modules["qgis.PyQt.QtCore"] = MagicMock()
    sys.modules["qgis.PyQt.QtWidgets"] = MagicMock()

if "osgeo" not in sys.modules:
    sys.modules["osgeo"] = MagicMock()
    sys.modules["osgeo.gdal"] = MagicMock()

if "processing" not in sys.modules:
    sys.modules["processing"] = MagicMock()
