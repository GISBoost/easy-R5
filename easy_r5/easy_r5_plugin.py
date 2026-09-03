"""Main plugin class: registers and unregisters the Easy-R5 Processing provider."""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .provider import EasyR5Provider

_PROVIDER_ID = "easyr5"
_MENU = "Easy-R5"


class EasyR5Plugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self._translator = None
        self._dl_action = None

        # value() can return None (key present but unset when "Override system
        # locale" is off) — [:2] on None would crash the whole plugin load.
        locale = (QSettings().value("locale/userLocale") or "en_US")[:2]
        qm = os.path.join(os.path.dirname(__file__), "i18n", f"easy_r5_{locale}.qm")
        if os.path.exists(qm):
            self._translator = QTranslator()
            self._translator.load(qm)
            QCoreApplication.installTranslator(self._translator)

    def tr(self, message: str) -> str:  # noqa: N802 — QGIS i18n convention
        return QCoreApplication.translate("EasyR5Plugin", message)

    def initGui(self):  # noqa: N802 — required QGIS plugin hook
        # openpyxl is the one CLAUDE.md-sanctioned bootstrap: PreparePopulationLayer
        # (PRD §4.8) needs it, nothing else does. Best-effort, never blocks startup.
        try:
            from .core.dependencies import ensure_openpyxl, install_openpyxl
            if not ensure_openpyxl():
                install_openpyxl()
        except Exception:  # nosec B110 — a failed optional bootstrap must not break the plugin
            pass

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

        # The one dialog: cascading city/month/day picker for gtfs-dashboard
        # recordings (see easy_r5/gui/). Best-effort — a GUI import error must
        # not take down the provider.
        try:
            icon = QIcon(os.path.join(os.path.dirname(__file__), "resources", "icon.svg"))
            self._dl_action = QAction(
                icon, self.tr("Download transit recordings…"), self.iface.mainWindow())
            self._dl_action.triggered.connect(self._open_download_recordings)
            self.iface.addPluginToMenu(_MENU, self._dl_action)
        except Exception:  # nosec B110 — an optional menu item must not break the plugin
            self._dl_action = None

    def _open_download_recordings(self):
        from .gui.download_recordings_dialog import DownloadRecordingsDialog
        DownloadRecordingsDialog(self.iface.mainWindow()).exec()

    def unload(self):
        if self._dl_action is not None:
            self.iface.removePluginMenu(_MENU, self._dl_action)
            self._dl_action = None

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
