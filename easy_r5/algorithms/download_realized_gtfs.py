"""DownloadRealizedGtfs: fetch one realized (P50/P85) or scheduled GTFS feed for
a city + date from the gtfs-dashboard index, into a folder ready for BuildNetwork.

This is the mechanics behind the *Plugins ▸ Easy-R5 ▸ Download transit
recordings…* dialog, and is usable on its own from the toolbox / a model. The
design and rationale (why an algorithm + a dialog, not one or the other) are in
``docs/prd/PR_easy-R5_v02_realized-gtfs.md``.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingMultiStepFeedback,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
)

from ..core import downloads, gtfs_dashboard, pins, settings

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DownloadRealizedGtfs(QgsProcessingAlgorithm):
    CITY = "CITY"
    DATE = "DATE"
    VARIANT = "VARIANT"
    TARGET_FOLDER = "TARGET_FOLDER"
    MANIFEST_URL = "MANIFEST_URL"
    FORCE_REDOWNLOAD = "FORCE_REDOWNLOAD"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("DownloadRealizedGtfs", string)

    def name(self) -> str:
        return "downloadrealizedgtfs"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Download realized GTFS")

    def group(self) -> str:
        return self.tr("Setup")

    def groupId(self) -> str:  # noqa: N802
        return "setup"

    def createInstance(self):  # noqa: N802
        return DownloadRealizedGtfs()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Downloads one realized (P50 / P85) or scheduled GTFS feed for a city "
            "and date from GISBoost's gtfs-dashboard index, into a folder you can "
            "hand straight to 'Build R5 network'.\n\n"
            "For a pick-from-a-list interface use Plugins ▸ Easy-R5 ▸ 'Download "
            "transit recordings…'. This algorithm takes the raw values so it also "
            "works in models and batch.\n\n"
            "CITY is the manifest key (e.g. 'lodz', not 'Łódź'). Realized and "
            "scheduled feeds share trip / stop ids and land in separate folders. "
            "No checksum is published — the download is only CRC-checked and "
            "sniffed for the GTFS files."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterString(
            self.CITY, self.tr("City key (from the manifest, e.g. 'lodz')")))
        self.addParameter(QgsProcessingParameterString(
            self.DATE, self.tr("Date (yyyy-MM-dd)")))
        self.addParameter(QgsProcessingParameterEnum(
            self.VARIANT, self.tr("Variant"),
            options=[self.tr(x) for x in gtfs_dashboard.VARIANT_LABELS], defaultValue=0))
        self.addParameter(QgsProcessingParameterFile(
            self.TARGET_FOLDER, self.tr("Download into folder"),
            behavior=QgsProcessingParameterFile.Folder,
            defaultValue=settings.get("transit_data_folder", "") or None))

        murl = QgsProcessingParameterString(
            self.MANIFEST_URL, self.tr("Manifest URL (blank = default)"), optional=True)
        murl.setFlags(murl.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(murl)

        force = QgsProcessingParameterBoolean(
            self.FORCE_REDOWNLOAD, self.tr("Re-download even if already present"),
            defaultValue=False)
        force.setFlags(force.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(force)

        self.addOutput(QgsProcessingOutputString(
            self.OUTPUT_FOLDER, self.tr("GTFS folder (for Build R5 network)")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        try:
            return self._run(parameters, context, feedback)
        except downloads.DownloadCancelled:
            feedback.pushWarning(self.tr("Cancelled by user."))
            return {}
        except (downloads.DownloadError, gtfs_dashboard.ManifestError) as exc:
            raise QgsProcessingException(str(exc))

    def _run(self, parameters, context, feedback):
        city = self.parameterAsString(parameters, self.CITY, context).strip()
        date = self.parameterAsString(parameters, self.DATE, context).strip()
        variant = gtfs_dashboard.VARIANTS[
            self.parameterAsEnum(parameters, self.VARIANT, context)]
        target_str = self.parameterAsFile(parameters, self.TARGET_FOLDER, context)
        murl = self.parameterAsString(parameters, self.MANIFEST_URL, context).strip()
        force = self.parameterAsBool(parameters, self.FORCE_REDOWNLOAD, context)

        if not city:
            raise QgsProcessingException(self.tr("CITY is required."))
        if not _DATE_RE.match(date):
            raise QgsProcessingException(self.tr(
                "DATE must be yyyy-MM-dd (e.g. 2026-08-24); got '{}'.").format(date))
        if not target_str:
            raise QgsProcessingException(self.tr("Choose a download folder."))
        target = Path(target_str)

        multi = QgsProcessingMultiStepFeedback(5, feedback)

        # 0 — pre-flight + manifest
        multi.setCurrentStep(0)
        downloads.check_writable(target)
        target.mkdir(parents=True, exist_ok=True)
        settings.set_("transit_data_folder", str(target))
        cache_str = settings.get("cache_folder", "")
        cache_dir = Path(cache_str) if cache_str else target
        manifest = gtfs_dashboard.fetch_manifest(
            url=(murl or settings.get("manifest_url", "") or None),
            cache_dir=cache_dir, feedback=multi)
        if gtfs_dashboard.is_stale(manifest):
            multi.pushWarning(self.tr(
                "Offline — using a cached recordings list ({}).").format(
                    manifest.get("_error", "")))
        age = gtfs_dashboard.generated_age_hours(manifest)
        if age is not None and age > 48:
            multi.pushWarning(self.tr(
                "The recordings list was generated {:.0f} h ago — the pipeline may "
                "have stalled.").format(age))

        # 1 — resolve the asset URL
        multi.setCurrentStep(1)
        asset_url = gtfs_dashboard.resolve_asset(manifest, city, date, variant)
        if gtfs_dashboard.day_status(manifest, city, date) == "partial":
            multi.pushWarning(self.tr(
                "The {date} recording is partial (gaps in coverage) — some trips "
                "keep their scheduled times.").format(date=date))
        multi.pushInfo(self.tr("Asset: {}").format(asset_url))

        # 2 — target dir, one per variant (realized / scheduled share ids)
        multi.setCurrentStep(2)
        variant_dir = (target / "transit-recordings" / city / date
                       / gtfs_dashboard.VARIANT_DIRNAME[variant])
        zip_name = asset_url.rsplit("/", 1)[-1] or "feed.zip"
        zip_path = variant_dir / zip_name

        existing = sorted(variant_dir.glob("*.zip")) if variant_dir.is_dir() else []
        if existing and not force and gtfs_dashboard.zip_is_gtfs(existing[0]):
            multi.pushInfo(self.tr("Already downloaded: {}").format(existing[0]))
            settings.set_("last_gtfs_folder", str(variant_dir))
            return {self.OUTPUT_FOLDER: str(variant_dir)}

        downloads.check_free_space(target, 200)
        variant_dir.mkdir(parents=True, exist_ok=True)
        for stale in variant_dir.glob("*.zip"):
            stale.unlink()

        # 3 — download
        multi.setCurrentStep(3)
        multi.pushInfo(self.tr("Downloading {}…").format(zip_name))
        downloads.download_file(asset_url, zip_path, feedback=multi,
                                user_agent=pins.USER_AGENT)

        # 4 — integrity (no checksum is published)
        multi.setCurrentStep(4)
        try:
            bad_member = zipfile.ZipFile(zip_path).testzip()
        except zipfile.BadZipFile:
            zip_path.unlink(missing_ok=True)
            raise QgsProcessingException(self.tr(
                "The downloaded file is not a valid zip — try again."))
        if bad_member is not None:
            zip_path.unlink(missing_ok=True)
            raise QgsProcessingException(self.tr(
                "The downloaded file is corrupt (CRC error in '{}') — try again."
            ).format(bad_member))
        missing = gtfs_dashboard.zip_missing_gtfs(zip_path)
        if missing:
            zip_path.unlink(missing_ok=True)
            raise QgsProcessingException(self.tr(
                "The download does not look like a GTFS feed (missing: {}). "
                "Report it at github.com/GISBoost/easy-GTFS-RT."
            ).format(", ".join(missing)))

        settings.set_("last_gtfs_folder", str(variant_dir))
        multi.setProgress(100)
        multi.pushInfo(self.tr(
            "GTFS ready: {dir}\nUse this folder as 'Folder of GTFS feeds' in "
            "'Build R5 network'.").format(dir=variant_dir))
        return {self.OUTPUT_FOLDER: str(variant_dir)}
