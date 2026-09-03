"""Main plugin class: registers and unregisters the Easy-R5 Processing provider."""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator

from .provider import EasyR5Provider

_PROVIDER_ID = "easyr5"


class EasyR5Plugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self._translator = None

        locale = QSettings().value("locale/userLocale", "en_US")[:2]
        qm = os.path.join(os.path.dirname(__file__), "i18n", f"easy_r5_{locale}.qm")
        if os.path.exists(qm):
            self._translator = QTranslator()
            self._translator.load(qm)
            QCoreApplication.installTranslator(self._translator)

    def tr(self, message: str) -> str:  # noqa: N802 — QGIS i18n convention
        return QCoreApplication.translate("EasyR5Plugin", message)

    def initGui(self):  # noqa: N802 — required QGIS plugin hook
        registry = QgsApplication.processingRegistry()
        # Defensive: a previous instance whose unload() failed can leave a stale
        # provider registered. Remove it before adding ours.
        stale = registry.providerById(_PROVIDER_ID)
        if stale is not None:
            registry.removeProvider(stale)
        self.provider = EasyR5Provider()
        if not registry.addProvider(self.provider):
            # The registry rejected and destroyed the provider — do not keep a
            # dangling reference (calling removeProvider on it later would crash).
            self.provider = None

    def unload(self):
        if self._translator is not None:
            QCoreApplication.removeTranslator(self._translator)
            self._translator = None

        registry = QgsApplication.processingRegistry()
        try:
            if self.provider is not None:
                registry.removeProvider(self.provider)
        except (RuntimeError, TypeError):
            # self.provider's C++ object is already gone — remove by id instead.
            still_there = registry.providerById(_PROVIDER_ID)
            if still_there is not None:
                registry.removeProvider(still_there)
        finally:
            self.provider = None
