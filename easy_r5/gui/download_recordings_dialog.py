"""The 'Download transit recordings' dialog.

A dumb picker: fetch the gtfs-dashboard manifest once, drive three cascading
combos (city -> month -> day) + a variant + a folder, then delegate the actual
work to the ``easyr5:downloadrealizedgtfs`` Processing algorithm. All logic lives
in that algorithm and in ``core/gtfs_dashboard`` — this file is only wiring.

The manifest is fetched synchronously on first open (~1-2 s, memoised in
``core.gtfs_dashboard`` for the rest of the session). If that freeze ever
matters, move it to a ``QgsTask``; it was not worth the extra machinery for v0.2.
"""

from __future__ import annotations

from pathlib import Path

import processing
from qgis.core import QgsProcessingException, QgsProcessingFeedback
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from ..core import gtfs_dashboard, settings


def _tr(string: str) -> str:
    return QApplication.translate("DownloadRecordingsDialog", string)


class _ProgressFeedback(QgsProcessingFeedback):
    """Bridges the algorithm's progress/cancel to a modal QProgressDialog."""

    def __init__(self, dialog: QProgressDialog):
        super().__init__()
        self._pd = dialog
        self.progressChanged.connect(lambda v: self._pd.setValue(int(v)))

    def isCanceled(self) -> bool:  # noqa: N802 — Qt name
        return self._pd.wasCanceled()


class DownloadRecordingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Download transit recordings"))
        self._manifest = None
        self._build_ui()

    # --- construction ------------------------------------------------

    def _build_ui(self):
        v = QVBoxLayout(self)

        self._status = QLabel(_tr("Connecting to the server…"))
        self._status.setWordWrap(True)
        v.addWidget(self._status)

        form = QFormLayout()
        self._city = QComboBox()
        self._month = QComboBox()
        self._day = QComboBox()
        self._variant = QComboBox()
        for label in gtfs_dashboard.VARIANT_LABELS:
            self._variant.addItem(_tr(label))
        form.addRow(_tr("City:"), self._city)
        form.addRow(_tr("Month:"), self._month)
        form.addRow(_tr("Day:"), self._day)
        form.addRow(_tr("Variant:"), self._variant)

        self._folder = QgsFileWidget()
        self._folder.setStorageMode(QgsFileWidget.GetDirectory)
        self._folder.setFilePath(settings.get("transit_data_folder", ""))
        form.addRow(_tr("Download into:"), self._folder)
        v.addLayout(form)

        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        v.addWidget(self._detail)

        row = QHBoxLayout()
        row.addStretch(1)
        self._retry = QPushButton(_tr("Retry"))
        self._retry.clicked.connect(self._load_manifest)
        self._retry.hide()
        self._btn_download = QPushButton(_tr("Download"))
        self._btn_download.clicked.connect(self._do_download)
        btn_close = QPushButton(_tr("Close"))
        btn_close.clicked.connect(self.reject)
        row.addWidget(self._retry)
        row.addWidget(self._btn_download)
        row.addWidget(btn_close)
        v.addLayout(row)

        self._city.currentIndexChanged.connect(self._on_city)
        self._month.currentIndexChanged.connect(self._on_month)
        self._day.currentIndexChanged.connect(self._refresh_detail)
        self._variant.currentIndexChanged.connect(self._refresh_detail)

        self._set_inputs_enabled(False)

    def showEvent(self, event):  # noqa: N802 — Qt name
        super().showEvent(event)
        if self._manifest is None:
            QTimer.singleShot(0, self._load_manifest)

    # --- manifest --------------------------------------------------

    def _set_inputs_enabled(self, on: bool):
        for w in (self._city, self._month, self._day, self._variant,
                  self._folder, self._btn_download):
            w.setEnabled(on)

    def _load_manifest(self):
        self._retry.hide()
        self._status.setText(_tr("Connecting to the server…"))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            cache_str = settings.get("cache_folder", "")
            self._manifest = gtfs_dashboard.fetch_manifest(
                url=settings.get("manifest_url", "") or None,
                cache_dir=Path(cache_str) if cache_str else None,
            )
        except gtfs_dashboard.ManifestError as exc:
            QApplication.restoreOverrideCursor()
            self._status.setText("⚠ " + str(exc))
            self._retry.show()
            self._set_inputs_enabled(False)
            return
        QApplication.restoreOverrideCursor()

        gen = self._manifest.get("generated_at") or "?"
        note = _tr(" (offline copy)") if gtfs_dashboard.is_stale(self._manifest) else ""
        self._status.setText(_tr("Recordings list from {}{}").format(gen, note))

        self._city.blockSignals(True)
        self._city.clear()
        for key, name in gtfs_dashboard.cities(self._manifest):
            self._city.addItem(name, key)
        self._city.blockSignals(False)
        self._set_inputs_enabled(True)
        self._on_city()

    def _on_city(self):
        key = self._city.currentData()
        self._month.blockSignals(True)
        self._month.clear()
        if key:
            for m in gtfs_dashboard.months(self._manifest, key):
                self._month.addItem(m)
        self._month.blockSignals(False)
        self._on_month()

    def _on_month(self):
        key = self._city.currentData()
        month = self._month.currentText()
        self._day.blockSignals(True)
        self._day.clear()
        if key and month:
            for d in gtfs_dashboard.days(self._manifest, key, month):
                mark = "  ⚠ " + _tr("partial") if d["status"] == "partial" else ""
                self._day.addItem(d["date"] + mark, d)
        self._day.blockSignals(False)
        self._refresh_detail()

    def _refresh_detail(self):
        day = self._day.currentData()
        if not day:
            self._detail.setText("")
            self._btn_download.setEnabled(False)
            return

        available = [i for i, v in enumerate(gtfs_dashboard.VARIANTS)
                     if day["assets"].get(v)]
        model = self._variant.model()
        for i in range(self._variant.count()):
            model.item(i).setEnabled(i in available)
        if self._variant.currentIndex() not in available and available:
            self._variant.setCurrentIndex(available[0])

        current = gtfs_dashboard.VARIANTS[self._variant.currentIndex()]
        self._btn_download.setEnabled(bool(day["assets"].get(current)))
        self._detail.setText(
            _tr("Partial coverage — some trips keep their scheduled times.")
            if day["status"] == "partial" else ""
        )

    # --- download -------------------------------------------------

    def _do_download(self):
        key = self._city.currentData()
        day = self._day.currentData()
        folder = self._folder.filePath().strip()
        if not key or not day:
            return
        if not folder:
            QMessageBox.warning(self, _tr("Download"), _tr("Choose a download folder."))
            return
        settings.set_("transit_data_folder", folder)

        params = {
            "CITY": key,
            "DATE": day["date"],
            "VARIANT": self._variant.currentIndex(),
            "TARGET_FOLDER": folder,
        }
        pd = QProgressDialog(_tr("Downloading…"), _tr("Cancel"), 0, 100, self)
        pd.setWindowModality(Qt.WindowModal)
        pd.setMinimumDuration(0)
        feedback = _ProgressFeedback(pd)
        self._btn_download.setEnabled(False)
        try:
            result = processing.run(
                "easyr5:downloadrealizedgtfs", params, feedback=feedback)
        except QgsProcessingException as exc:
            QMessageBox.warning(self, _tr("Download failed"), str(exc))
            return
        finally:
            pd.close()
            self._btn_download.setEnabled(True)

        out = result.get("OUTPUT_FOLDER", folder)
        box = QMessageBox(self)
        box.setWindowTitle(_tr("Download complete"))
        box.setText(_tr(
            "Saved to:\n{}\n\nThis folder is now the default 'Folder of GTFS "
            "feeds' in 'Build R5 network'.").format(out))
        open_btn = box.addButton(_tr("Open folder"), QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(out))
