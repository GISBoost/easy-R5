"""Headless PyQGIS bootstrap: starts QgsApplication and registers the Easy-R5 provider.

Run scripts with QGIS's interpreter, e.g.
  "C:/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat" scripts/make_grid.py
The plugin itself cannot be loaded by qgis_process (initGui needs iface), so the provider
is added by hand; Processing algorithms then run exactly as in the GUI (answers PRD O16).
"""
import sys

QGIS_PLUGINS = "C:/Program Files/QGIS 3.40.4/apps/qgis-ltr/python/plugins"
REPO = __file__.replace("\\", "/").rsplit("/tools/", 1)[0]


_keep = []  # the provider must stay referenced, or its Python algorithms are GC'd


def start():
    sys.path[:0] = [QGIS_PLUGINS, REPO]
    from qgis.core import QgsApplication
    QgsApplication.setOrganizationName("QGIS")      # same QSettings store as the desktop profile
    QgsApplication.setOrganizationDomain("qgis.org")
    QgsApplication.setApplicationName("QGIS3")
    app = QgsApplication([], False)
    app.initQgis()
    from processing.core.Processing import Processing
    Processing.initialize()
    from easy_r5.provider import EasyR5Provider
    provider = EasyR5Provider()
    _keep.append(provider)
    QgsApplication.processingRegistry().addProvider(provider)
    return app
