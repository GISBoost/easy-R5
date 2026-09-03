"""Main plugin class: registers and unregisters the Easy-R5 Processing provider."""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator

from .provider import EasyR5Provider


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
        self.provider = EasyR5Provider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self._translator is not None:
            QCoreApplication.removeTranslator(self._translator)
            self._translator = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
