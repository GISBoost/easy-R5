"""TestR5Setup: independent diagnostic checks for the R5 engine setup.

Each step reports on its own — a failure in step 3 still shows that steps 1 and 2
passed. Step 4 (command=info on a network.dat) is optional.

M1 stops at command=info. PRD 4.2 also mentions a trivial travel-time query as a
final step; that needs command=matrix, which arrives in milestone M3.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFile,
)

from ..core import job_spec, java_env, runner, settings
from ..core import pins


class TestR5Setup(QgsProcessingAlgorithm):
    USE_SAVED_JDK = "USE_SAVED_JDK"
    JDK_PATH = "JDK_PATH"
    NETWORK_DAT = "NETWORK_DAT"
    R5_VERSION = "R5_VERSION"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("TestR5Setup", string)

    def name(self) -> str:
        return "testr5setup"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Test R5 setup")

    def group(self) -> str:
        return self.tr("Diagnostics")

    def groupId(self) -> str:  # noqa: N802
        return "diagnostics"

    def createInstance(self):  # noqa: N802
        return TestR5Setup()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Checks an R5 setup step by step and reports each independently:\n"
            "  1. the Temurin 21 JDK exists and reports Java 21+\n"
            "  2. the R5 jar exists and its SHA-256 matches the pinned value\n"
            "  3. the Java runner is compiled (or the source launcher is usable)\n"
            "  4. (optional) run command=info on a network.dat and print its metadata\n\n"
            "Run 'Download R5 engine and Java 21' first. In milestone M1 the runner "
            "implements only command=info; a full travel-time query arrives in M3."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.USE_SAVED_JDK,
                self.tr("Use the JDK path saved by 'Download R5 engine and Java 21'"),
                defaultValue=True,
            )
        )
        jdk_param = QgsProcessingParameterFile(
            self.JDK_PATH,
            self.tr("Java 21 binary (only if not using the saved path)"),
            behavior=QgsProcessingParameterFile.File,
        )
        jdk_param.setFlags(
            jdk_param.flags()
            | QgsProcessingParameterDefinition.FlagOptional
            | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(jdk_param)

        net_param = QgsProcessingParameterFile(
            self.NETWORK_DAT,
            self.tr("network.dat to probe with command=info (optional)"),
            behavior=QgsProcessingParameterFile.File,
            extension="dat",
        )
        net_param.setFlags(
            net_param.flags() | QgsProcessingParameterDefinition.FlagOptional
        )
        self.addParameter(net_param)

        self.addOutput(
            QgsProcessingOutputString(self.R5_VERSION, self.tr("R5 version"))
        )

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        use_saved = self.parameterAsBool(parameters, self.USE_SAVED_JDK, context)
        jdk_param = self.parameterAsFile(parameters, self.JDK_PATH, context)
        network_dat = self.parameterAsFile(parameters, self.NETWORK_DAT, context)

        r5_version = ""
        ok1, jdk_bin = self._check_jdk(use_saved, jdk_param, feedback)
        ok2 = self._check_jar(feedback)
        ok3 = self._check_runner(ok1, ok2, jdk_bin, feedback)
        ok4, r5_version = self._check_info(ok3, network_dat, feedback)

        applicable = [ok1, ok2, ok3]
        if network_dat:
            applicable.append(ok4)
        if all(applicable):
            feedback.pushInfo(self.tr("All checks passed."))
        else:
            feedback.reportError(
                self.tr("One or more checks failed — see the steps above.")
            )
        return {self.R5_VERSION: r5_version}

    # --- steps -----------------------------------------------------------

    def _check_jdk(self, use_saved, jdk_param, feedback):
        feedback.pushInfo(self.tr("Step 1: Java 21 JDK"))
        if use_saved:
            saved = settings.get("jdk_path", "")
            if not saved:
                feedback.reportError(
                    self.tr(
                        "  No JDK path saved. Run 'Download R5 engine and Java 21', "
                        "or untick 'Use the saved JDK path' and supply one."
                    )
                )
                return False, None
            jdk = Path(saved)
        elif jdk_param:
            jdk = Path(jdk_param)
        else:
            feedback.reportError(
                self.tr("  No JDK path given. Tick 'Use the saved JDK path' or set one.")
            )
            return False, None

        is_ok, version, err = java_env.check_java_version(jdk)
        if is_ok:
            feedback.pushInfo(self.tr("  OK: Java {} at {}").format(version, jdk))
            return True, jdk.parent
        feedback.reportError("  " + err)
        return False, None

    def _check_jar(self, feedback):
        feedback.pushInfo(self.tr("Step 2: R5 jar"))
        saved = settings.get("r5_jar_path", "")
        if not saved:
            feedback.reportError(
                self.tr("  No R5 jar path saved. Run 'Download R5 engine and Java 21'.")
            )
            return False
        jar = Path(saved)
        if not jar.is_file():
            feedback.reportError(self.tr("  R5 jar not found: {}").format(jar))
            return False
        if jar.suffix.lower() != ".jar":
            feedback.reportError(self.tr("  Not a .jar file: {}").format(jar))
            return False
        if not java_env.jar_sanity_ok(jar):
            feedback.reportError(
                self.tr(
                    "  {} does not look like the R5 fat jar (size or contents wrong)."
                ).format(jar)
            )
            return False
        ok, digest = java_env.verify_jar_sha256(jar, pins.R5_JAR_SHA256)
        if not ok:
            feedback.reportError(
                self.tr(
                    "  SHA-256 mismatch for {}.\n  expected {}\n  got      {}\n"
                    "  Re-run 'Download R5 engine and Java 21'."
                ).format(jar, pins.R5_JAR_SHA256, digest)
            )
            return False
        feedback.pushInfo(self.tr("  OK: {} (SHA-256 verified)").format(jar))
        return True

    def _check_runner(self, ok_jdk, ok_jar, jdk_bin, feedback):
        feedback.pushInfo(self.tr("Step 3: Java runner"))
        if not (ok_jdk and ok_jar):
            feedback.reportError(self.tr("  Skipped: fix steps 1 and 2 first."))
            return False
        mode = settings.get("runner_mode", "")
        if mode == "compiled":
            class_dir = Path(settings.get("runner_class_dir", ""))
            if (class_dir / (pins.RUNNER_MAIN_CLASS + ".class")).is_file():
                feedback.pushInfo(self.tr("  OK: compiled runner in {}").format(class_dir))
                return True
            feedback.reportError(
                self.tr("  Compiled runner missing from {}").format(class_dir)
            )
            return False
        if mode == "source":
            src = Path(settings.get("runner_source_path", ""))
            if src.is_file():
                feedback.pushInfo(
                    self.tr("  OK: source launcher will compile the runner per run ({})").format(src)
                )
                return True
            feedback.reportError(self.tr("  Runner source missing from {}").format(src))
            return False
        feedback.reportError(
            self.tr("  Runner not set up. Run 'Download R5 engine and Java 21'.")
        )
        return False

    def _check_info(self, ok_runner, network_dat, feedback):
        feedback.pushInfo(self.tr("Step 4: command=info"))
        if not network_dat:
            feedback.pushInfo(self.tr("  Skipped (no network.dat supplied)."))
            return True, ""
        if not ok_runner:
            feedback.reportError(self.tr("  Skipped: the runner is not ready."))
            return False, ""

        try:
            env = java_env.resolve_env(settings.all_settings())
        except java_env.JavaEnvError as exc:
            feedback.reportError("  " + str(exc))
            return False, ""

        mb, warn = java_env.heap_mb_for(
            java_env.detect_ram_bytes(), settings.get_java_heap_gb()
        )
        if warn:
            feedback.pushWarning("  " + warn)
        xmx = java_env.xmx_arg(mb)

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_info_"))
        try:
            job_path = job_spec.write_job(
                job_spec.build_info_job(network_dat), tmp
            )
            cmd = java_env.build_java_command(env, xmx, job_path)
            result = runner.run_job(
                cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr.log",
                r5_version=pins.R5_VERSION,
            )
        except runner.RunnerCancelled:
            raise
        except runner.RunnerError as exc:
            feedback.reportError("  " + str(exc))
            if exc.code == "NETWORK_VERSION_MISMATCH":
                feedback.pushInfo(
                    self.tr(
                        "  This is expected when the network was built with a "
                        "different R5 version. It confirms the runner loads and the "
                        "version guard works."
                    )
                )
            return False, ""
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        for key, value in result.results.items():
            feedback.pushInfo("  {} = {}".format(key, value))
        r5_version = result.results.get("r5_version", "?")
        feedback.pushInfo(self.tr("  R5 version: {}").format(r5_version))
        return True, r5_version
