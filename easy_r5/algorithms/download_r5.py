"""DownloadR5: fetch a Temurin 21 JDK and r5-v7.6-all.jar, verify them, save the
paths under the easy_r5/ QSettings namespace, and compile the Java runner.

Modelled on easy_otp/algorithms/download_jre.py. Nothing is shared with
easy-OTP: separate QSettings keys, separate download folder (ADR-0002). x64
only, exactly as easy-OTP — arm64 users are pointed at a manual download.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

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
)

from ..core import java_env, pins, settings

_CHUNK = 64 * 1024
_MIN_FREE_MB = 700  # JDK unpacked + jar


class DownloadR5(QgsProcessingAlgorithm):
    TARGET_FOLDER = "TARGET_FOLDER"
    DOWNLOAD_JDK = "DOWNLOAD_JDK"
    DOWNLOAD_R5 = "DOWNLOAD_R5"
    PLATFORM = "PLATFORM"

    JDK_PATH = "JDK_PATH"
    JDK_VERSION = "JDK_VERSION"
    R5_JAR_PATH = "R5_JAR_PATH"
    RUNNER_MODE = "RUNNER_MODE"

    _PLATFORM_OPTIONS = ["Auto-detect (current system)", "Windows x64", "Linux x64", "macOS x64 (Intel)"]
    _OS_NAMES = ["windows", "linux", "mac"]

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("DownloadR5", string)

    def name(self) -> str:
        return "downloadr5"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Download R5 engine and Java 21")

    def group(self) -> str:
        return self.tr("Setup")

    def groupId(self) -> str:  # noqa: N802
        return "setup"

    def createInstance(self):  # noqa: N802
        return DownloadR5()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Downloads a portable Eclipse Temurin 21 JDK (x64) from the Adoptium "
            "API and r5-v7.6-all.jar from the Conveyal GitHub release, verifies "
            "both (SHA-256), saves their paths under the easy_r5/ QSettings keys, "
            "and compiles the one-file Java runner to <target>/runner_cache/.\n\n"
            "First run downloads ~240 MB (JDK ~180 MB + jar ~62 MB). No "
            "administrator rights are needed. These are NOT shared with easy-OTP "
            "— that plugin uses Java 8.\n\n"
            "Supported platforms: Windows / Linux / macOS x64. On Apple Silicon "
            "or ARM Linux, install Temurin 21 manually from "
            "https://adoptium.net/temurin/releases/?version=21 and point "
            "TestR5Setup at it.\n\n"
            "Re-running on the same folder detects existing files and exits in "
            "seconds."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(
            QgsProcessingParameterFile(
                self.TARGET_FOLDER,
                self.tr("Destination folder for the JDK and R5 jar"),
                behavior=QgsProcessingParameterFile.Folder,
                defaultValue=str(Path.home() / "easy-r5"),
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.DOWNLOAD_JDK, self.tr("Download the Temurin 21 JDK"), defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.DOWNLOAD_R5, self.tr("Download r5-v7.6-all.jar"), defaultValue=True
            )
        )
        plat = QgsProcessingParameterEnum(
            self.PLATFORM,
            self.tr("Platform override"),
            options=[self.tr(s) for s in self._PLATFORM_OPTIONS],
            defaultValue=0,
        )
        plat.setFlags(plat.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(plat)

        self.addOutput(QgsProcessingOutputString(self.JDK_PATH, self.tr("JDK java binary path")))
        self.addOutput(QgsProcessingOutputString(self.JDK_VERSION, self.tr("JDK version")))
        self.addOutput(QgsProcessingOutputString(self.R5_JAR_PATH, self.tr("R5 jar path")))
        self.addOutput(QgsProcessingOutputString(self.RUNNER_MODE, self.tr("Runner mode")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        target = Path(self.parameterAsFile(parameters, self.TARGET_FOLDER, context))
        want_jdk = self.parameterAsBool(parameters, self.DOWNLOAD_JDK, context)
        want_r5 = self.parameterAsBool(parameters, self.DOWNLOAD_R5, context)
        platform_idx = self.parameterAsEnum(parameters, self.PLATFORM, context)

        multi = QgsProcessingMultiStepFeedback(12, feedback)

        # Step 0: pre-flight
        multi.setCurrentStep(0)
        self._check_arch()
        os_name = self._resolve_os(platform_idx)
        self._check_writable(target)
        target.mkdir(parents=True, exist_ok=True)
        runner_cache = target / "runner_cache"
        runner_cache.mkdir(parents=True, exist_ok=True)
        settings.set_("target_folder", str(target))
        multi.pushInfo(self.tr("Target platform: {} x64").format(os_name))

        # Steps 1-6: JDK
        jdk_bin: "Path | None" = None
        jdk_version = ""
        if want_jdk:
            jdk_bin, jdk_version = self._ensure_jdk(target, os_name, multi)
        else:
            saved = settings.get("jdk_path", "")
            if not saved or not Path(saved).exists():
                raise QgsProcessingException(self.tr(
                    "'Download the Temurin 21 JDK' is off and no JDK path is saved. "
                    "Enable it, or run this once with it enabled."
                ))
            jdk_bin = Path(saved)
            jdk_version = settings.get("jdk_version", "")
            multi.pushInfo(self.tr("Using saved JDK: {}").format(jdk_bin))

        if multi.isCanceled():
            multi.pushWarning(self.tr(
                "Cancelled after the JDK phase. The JDK path is saved — run the "
                "algorithm again to fetch the R5 jar."
            ))
            return {}

        # Steps 7-9: R5 jar
        jar_path = target / pins.R5_JAR_FILENAME
        if want_r5:
            jar_path = self._ensure_r5_jar(target, multi)
        else:
            saved = settings.get("r5_jar_path", "")
            if not saved or not Path(saved).is_file():
                raise QgsProcessingException(self.tr(
                    "'Download r5-v7.6-all.jar' is off and no jar path is saved."
                ))
            jar_path = Path(saved)
            multi.pushInfo(self.tr("Using saved R5 jar: {}").format(jar_path))

        if multi.isCanceled():
            return {}

        # Step 10-11: compile the runner
        multi.setCurrentStep(10)
        multi.pushInfo(self.tr("Compiling the Java runner…"))
        source_path = Path(__file__).resolve().parent.parent / "java" / pins.RUNNER_SOURCE_FILENAME
        mode, detail = java_env.compile_runner(
            jdk_bin.parent, jar_path, source_path, runner_cache
        )
        settings.set_("runner_mode", mode)
        settings.set_("runner_source_path", str(source_path))
        settings.set_("runner_class_dir", str(runner_cache))
        if mode == "compiled":
            multi.pushInfo(self.tr("Runner compiled to {}").format(runner_cache))
        else:
            multi.pushWarning(self.tr(
                "Pre-compilation unavailable; the runner will be compiled on each "
                "run (~1 s overhead). Reason: {}"
            ).format(detail))

        multi.setCurrentStep(11)
        multi.setProgress(100)
        return {
            self.JDK_PATH: str(jdk_bin),
            self.JDK_VERSION: jdk_version,
            self.R5_JAR_PATH: str(jar_path),
            self.RUNNER_MODE: mode,
        }

    # --- JDK -------------------------------------------------------------

    def _ensure_jdk(self, target, os_name, multi):
        multi.setCurrentStep(1)
        cached = self._find_java(target)
        if cached:
            is_ok, ver, _ = java_env.check_java_version(cached)
            if is_ok:
                multi.pushInfo(self.tr("Existing Java 21+ found at {}, skipping download.").format(cached))
                settings.set_("jdk_path", str(cached))
                settings.set_("jdk_version", ver)
                return cached, ver
            multi.pushWarning(self.tr(
                "Found a Java at {} that is not 21+ — leaving it; downloading a "
                "Temurin 21 JDK alongside it."
            ).format(cached))

        self._check_disk(target)
        multi.setCurrentStep(2)
        multi.pushInfo(self.tr("Querying the Adoptium API for the latest Temurin 21 JDK…"))
        link, checksum, pkg_name = self._query_adoptium(os_name)

        archive = target / pkg_name
        tmp = target / (pkg_name + ".tmp")
        multi.pushInfo(self.tr("Downloading {}…").format(link))
        self._download(link, tmp, archive, multi, 3, 3)
        if multi.isCanceled():
            return None, ""

        multi.setCurrentStep(6)
        multi.pushInfo(self.tr("Verifying SHA-256…"))
        ok, digest = java_env.verify_jar_sha256(archive, checksum)
        if not ok:
            os.remove(archive)
            raise QgsProcessingException(self.tr(
                "JDK archive checksum does not match the Adoptium API. Expected {}, "
                "got {}. Retry."
            ).format(checksum, digest))

        multi.pushInfo(self.tr("Extracting…"))
        self._extract(archive, target, os_name)
        try:
            os.remove(archive)
        except OSError:
            pass

        binary = self._find_java(target)
        if binary is None:
            raise QgsProcessingException(self.tr(
                "Cannot find bin/java inside the unpacked JDK at {}. Please open an "
                "issue at {}."
            ).format(target, "https://github.com/GISBoost/easy-R5/issues"))
        if os_name != "windows":
            os.chmod(binary, 0o755)  # nosec B103 — executable bit required for the JDK

        is_ok, version, err = java_env.check_java_version(binary)
        if not is_ok:
            raise QgsProcessingException(self.tr(
                "Unpacked JDK reports '{}': {}"
            ).format(version, err))
        multi.pushInfo(self.tr("Java {} OK ({})").format(version, binary))
        settings.set_("jdk_path", str(binary))
        settings.set_("jdk_version", version)
        return binary, version

    def _query_adoptium(self, os_name):
        url = pins.ADOPTIUM_LATEST_URL.format(
            feature=pins.JDK_FEATURE_VERSION, image=pins.JDK_IMAGE_TYPE, os=os_name
        )
        req = urllib_request.Request(url, headers={"User-Agent": pins.USER_AGENT})
        try:
            with urllib_request.urlopen(req, timeout=30) as resp:  # nosec B310 — fixed HTTPS API endpoint
                data = json.loads(resp.read().decode())
        except URLError as exc:
            raise QgsProcessingException(self.tr(
                "Cannot reach the Adoptium API (https://api.adoptium.net). Check "
                "your connection. ({})"
            ).format(exc)) from exc
        if not data:
            raise QgsProcessingException(self.tr(
                "Adoptium has no Temurin 21 JDK x64 build for '{}'. See "
                "https://adoptium.net/temurin/releases/?version=21"
            ).format(os_name))
        pkg = data[0]["binary"]["package"]
        return pkg["link"], pkg["checksum"], pkg["name"]

    # --- R5 jar ---------------------------------------------------------

    def _ensure_r5_jar(self, target, multi):
        multi.setCurrentStep(7)
        jar_path = target / pins.R5_JAR_FILENAME
        if jar_path.is_file() and java_env.jar_sanity_ok(jar_path):
            ok, _ = java_env.verify_jar_sha256(jar_path, pins.R5_JAR_SHA256)
            if ok:
                multi.pushInfo(self.tr("Existing R5 jar found at {}, skipping download.").format(jar_path))
                settings.set_("r5_jar_path", str(jar_path))
                settings.set_("r5_version", pins.R5_VERSION)
                settings.set_("r5_jar_sha256", pins.R5_JAR_SHA256)
                return jar_path

        tmp = target / (pins.R5_JAR_FILENAME + ".tmp")
        multi.setCurrentStep(8)
        multi.pushInfo(self.tr("Downloading {}…").format(pins.R5_JAR_URL))
        self._download(pins.R5_JAR_URL, tmp, jar_path, multi, 8, 1)
        if multi.isCanceled():
            return jar_path

        multi.setCurrentStep(9)
        ok, digest = java_env.verify_jar_sha256(jar_path, pins.R5_JAR_SHA256)
        if not ok:
            try:
                os.remove(jar_path)
            except OSError:
                pass
            raise QgsProcessingException(self.tr(
                "R5 jar SHA-256 does not match the pinned value.\n  expected {}\n"
                "  got      {}\nThe download may be corrupt — retry."
            ).format(pins.R5_JAR_SHA256, digest))
        if not java_env.jar_sanity_ok(jar_path):
            os.remove(jar_path)
            raise QgsProcessingException(self.tr(
                "Downloaded R5 jar failed its structure check. Retry."
            ))
        multi.pushInfo(self.tr("R5 jar OK ({}), SHA-256 verified.").format(jar_path))
        settings.set_("r5_jar_path", str(jar_path))
        settings.set_("r5_version", pins.R5_VERSION)
        settings.set_("r5_jar_sha256", pins.R5_JAR_SHA256)
        return jar_path

    # --- shared helpers (ported from easy-OTP download_jre.py) ----------

    def _check_arch(self):
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            raise QgsProcessingException(self.tr(
                "Automatic download supports x64 only (detected {}). Install "
                "Temurin 21 manually from "
                "https://adoptium.net/temurin/releases/?version=21 and point "
                "TestR5Setup at it."
            ).format(machine))

    def _resolve_os(self, platform_idx):
        if platform_idx == 0:
            mapping = {"win32": "windows", "linux": "linux", "darwin": "mac"}
            os_name = mapping.get(sys.platform)
            if os_name is None:
                raise QgsProcessingException(self.tr(
                    "Unsupported platform '{}'. Use the 'Platform override' parameter."
                ).format(sys.platform))
            return os_name
        return self._OS_NAMES[platform_idx - 1]

    def _check_writable(self, dest):
        parent = dest if dest.is_dir() else dest.parent
        if not parent.is_dir():
            raise QgsProcessingException(self.tr(
                "Folder '{}' does not exist and neither does its parent."
            ).format(dest))
        probe = parent / ".easy_r5_write_test"
        try:
            probe.touch()
            probe.unlink()
        except PermissionError:
            raise QgsProcessingException(self.tr(
                "Cannot write to '{}': administrator rights required. Choose a "
                "folder in your user profile."
            ).format(parent))
        except OSError as exc:
            raise QgsProcessingException(
                self.tr("Cannot write to '{}': {}").format(parent, exc)
            )

    def _check_disk(self, dest):
        free_mb = shutil.disk_usage(dest).free / (1024 * 1024)
        if free_mb < _MIN_FREE_MB:
            raise QgsProcessingException(self.tr(
                "Not enough disk space in '{}'. Need ~{} MB, have {:.0f} MB."
            ).format(dest, _MIN_FREE_MB, free_mb))

    def _download(self, url, tmp, final, multi, step_start, step_count):
        req = urllib_request.Request(url, headers={"User-Agent": pins.USER_AGENT})
        try:
            with urllib_request.urlopen(req, timeout=60) as resp:  # nosec B310 — fixed HTTPS release/API URL
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                with open(tmp, "wb") as fh:
                    while True:
                        if multi.isCanceled():
                            fh.close()
                            self._rm(tmp)
                            return
                        chunk = resp.read(_CHUNK)
                        if not chunk:
                            break
                        fh.write(chunk)
                        done += len(chunk)
                        if total:
                            frac = done / total
                            step = min(step_start + int(frac * step_count),
                                       step_start + step_count - 1)
                            multi.setCurrentStep(step)
                            multi.setProgress(int(((frac * step_count) % 1.0) * 100))
        except URLError as exc:
            self._rm(tmp)
            raise QgsProcessingException(
                self.tr("Download failed ({}): {}").format(url, exc)
            ) from exc
        if multi.isCanceled():
            self._rm(tmp)
            return
        os.rename(tmp, final)

    @staticmethod
    def _rm(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def _safe_zipextract(self, zf, dest):
        dest_root = dest.resolve()
        prefix = str(dest_root) + os.sep
        for member in zf.infolist():
            target = (dest_root / member.filename).resolve()
            if str(target) != str(dest_root) and not str(target).startswith(prefix):
                continue  # skip zip-slip
            zf.extract(member, dest)

    def _safe_tarextract(self, tf, dest):
        dest_root = dest.resolve()
        prefix = str(dest_root) + os.sep
        for member in tf.getmembers():
            if member.isdev() or member.issym() or member.islnk():
                continue  # no device/symlink/hardlink members from a JDK tarball
            target = (dest_root / member.name).resolve()
            if str(target) != str(dest_root) and not str(target).startswith(prefix):
                continue  # skip tar-slip
            tf.extract(member, dest)

    def _extract(self, archive, dest, os_name):
        if os_name == "windows":
            with zipfile.ZipFile(archive) as zf:
                self._safe_zipextract(zf, dest)
        else:
            with tarfile.open(archive) as tf:
                if sys.version_info >= (3, 12):
                    tf.extractall(dest, filter="data")
                else:
                    self._safe_tarextract(tf, dest)

    def _find_java(self, dest):
        binary_name = "java.exe" if sys.platform == "win32" else "java"
        # cross-platform: also look for the other name when using an override
        names = {"java", "java.exe"}
        for root, dirs, files in os.walk(dest):
            depth = len(Path(root).relative_to(dest).parts)
            if depth >= 4:
                dirs.clear()
                continue
            if Path(root).name == "bin":
                for n in (binary_name, *names):
                    if n in files:
                        return Path(root) / n
        return None
