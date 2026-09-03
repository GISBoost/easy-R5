"""Easy-R5 — QGIS plugin for transit accessibility analysis via Conveyal R5."""


def classFactory(iface):  # noqa: N802 — required QGIS entry point name
    from .easy_r5_plugin import EasyR5Plugin
    return EasyR5Plugin(iface)
