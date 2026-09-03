"""BuildNetwork: build a cached R5 network.dat + network.json from an OSM extract
and a folder of GTFS feeds.

The cache is keyed by the content hash of the inputs plus the R5 version, so an
unchanged re-run returns instantly and an R5 upgrade rebuilds automatically.
network.json carries ``service_days`` — the per-date active trip count — which
M3 uses to refuse running on a date with no service (R5 silently returns
walk-only results otherwise).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFile,
)

from ..core import (
    gtfs_calendar,
    java_env,
    job_spec,
    network_cache,
    pins,
    runner,
    settings,
)


class BuildNetwork(QgsProcessingAlgorithm):
    OSM_PBF = "OSM_PBF"
    GTFS_FOLDER = "GTFS_FOLDER"
    CACHE_FOLDER = "CACHE_FOLDER"
    FORCE_REBUILD = "FORCE_REBUILD"
    NETWORK_DAT = "NETWORK_DAT"
    NETWORK_JSON = "NETWORK_JSON"

    def tr(self, string: str) -> str:
        return QCoreApplication.translate("BuildNetwork", string)

    def name(self) -> str:
        return "buildnetwork"

    def displayName(self) -> str:  # noqa: N802
        return self.tr("Build R5 network")

    def group(self) -> str:
        return self.tr("Setup")

    def groupId(self) -> str:  # noqa: N802
        return "setup"

    def createInstance(self):  # noqa: N802
        return BuildNetwork()

    def shortHelpString(self) -> str:  # noqa: N802
        return self.tr(
            "Builds an R5 network.dat from one OSM .pbf extract and every .zip "
            "GTFS feed in a folder, and writes a network.json summary that "
            "includes service_days (active trip count per date, 90-day window).\n\n"
            "The result is cached under CACHE_FOLDER/<hash>/ keyed by the input "
            "file contents and the pinned R5 version; an unchanged re-run returns "
            "at once. FORCE_REBUILD ignores the cache.\n\n"
            "Building can take minutes on a large PBF. Run 'Download R5 engine "
            "and Java 21' first."
        )

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(
            QgsProcessingParameterFile(
                self.OSM_PBF,
                self.tr("OSM extract (.osm.pbf)"),
                behavior=QgsProcessingParameterFile.File,
                extension="pbf",
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.GTFS_FOLDER,
                self.tr("Folder of GTFS feeds (every .zip inside is used)"),
                behavior=QgsProcessingParameterFile.Folder,
                # 'Download transit recordings…' saves its last output here
                defaultValue=settings.get("last_gtfs_folder", "") or None,
            )
        )
        cache = QgsProcessingParameterFile(
            self.CACHE_FOLDER,
            self.tr("Network cache folder (blank = plugin default)"),
            behavior=QgsProcessingParameterFile.Folder,
        )
        cache.setFlags(cache.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(cache)

        force = QgsProcessingParameterBoolean(
            self.FORCE_REBUILD, self.tr("Force rebuild (ignore the cache)"),
            defaultValue=False,
        )
        force.setFlags(force.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(force)

        self.addOutput(QgsProcessingOutputString(self.NETWORK_DAT, self.tr("network.dat path")))
        self.addOutput(QgsProcessingOutputString(self.NETWORK_JSON, self.tr("network.json path")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        osm = Path(self.parameterAsFile(parameters, self.OSM_PBF, context))
        gtfs_folder = Path(self.parameterAsFile(parameters, self.GTFS_FOLDER, context))
        cache_param = self.parameterAsFile(parameters, self.CACHE_FOLDER, context)
        force = self.parameterAsBool(parameters, self.FORCE_REBUILD, context)

        if not osm.is_file():
            raise QgsProcessingException(self.tr("OSM file not found: {}").format(osm))
        gtfs_paths = sorted(gtfs_folder.glob("*.zip"))
        if not gtfs_paths:
            raise QgsProcessingException(
                self.tr("No .zip GTFS feeds in folder: {}").format(gtfs_folder)
            )

        try:
            env = java_env.resolve_env(settings.all_settings())
        except java_env.JavaEnvError as exc:
            raise QgsProcessingException(str(exc))

        cache_folder = Path(cache_param) if cache_param else self._default_cache_folder()
        key = network_cache.cache_key(osm, gtfs_paths, pins.R5_VERSION)
        cd = network_cache.cache_dir(cache_folder, key)

        if not force and network_cache.is_complete(cd):
            feedback.pushInfo(self.tr(
                "Cache hit: {} — inputs and R5 version unchanged, skipping build."
            ).format(cd))
            self._log_summary(network_cache.load_summary(cd), feedback)
            return self._outputs(cd)

        cd.mkdir(parents=True, exist_ok=True)
        network_cache.wipe(cd)

        mb, warn = java_env.heap_mb_for(
            java_env.detect_ram_bytes(), settings.get_java_heap_gb()
        )
        if warn:
            feedback.pushWarning(warn)

        tmp = Path(tempfile.mkdtemp(prefix="easy_r5_build_"))
        try:
            job = job_spec.build_build_job(
                osm, gtfs_paths,
                network_cache.network_dat(cd), network_cache.network_json(cd),
            )
            cmd = java_env.build_java_command(
                env, java_env.xmx_arg(mb), job_spec.write_job(job, tmp),
                extra_jvm_args=["-Djava.io.tmpdir=" + str(tmp)],
            )
            feedback.pushInfo(self.tr("Building the network — this can take a few minutes…"))
            runner.run_job(
                cmd, feedback, cwd=tmp, stderr_log=tmp / "stderr.log",
                r5_version=pins.R5_VERSION,
            )
        except runner.RunnerCancelled:
            network_cache.wipe(cd)
            raise QgsProcessingException(self.tr("Network build cancelled by user."))
        except runner.RunnerError as exc:
            network_cache.wipe(cd)
            raise QgsProcessingException(str(exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # The runner wrote the structural network.json; add service_days (Python).
        summary = json.loads(network_cache.network_json(cd).read_text(encoding="utf-8"))
        feedback.pushInfo(self.tr("Computing service_days from the GTFS calendar…"))
        summary["service_days"] = gtfs_calendar.compute_service_days(gtfs_paths)
        network_cache.network_json(cd).write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        self._log_summary(summary, feedback)
        return self._outputs(cd)

    # --- helpers --------------------------------------------------------

    def _default_cache_folder(self):
        base = settings.get("cache_folder", "")
        if base:
            return Path(base)
        target = settings.get("target_folder", "") or str(Path.home() / "easy-r5")
        return Path(target) / "networks"

    def _outputs(self, cd):
        return {
            self.NETWORK_DAT: str(network_cache.network_dat(cd)),
            self.NETWORK_JSON: str(network_cache.network_json(cd)),
        }

    def _log_summary(self, summary, feedback):
        feedback.pushInfo(self.tr("Network summary:"))
        feedback.pushInfo("  feeds: {}".format(", ".join(summary.get("feeds", []))))
        feedback.pushInfo("  stops: {}".format(summary.get("stops")))
        feedback.pushInfo("  trip patterns: {}".format(summary.get("trip_patterns")))
        feedback.pushInfo("  routes: {}".format(summary.get("routes")))
        feedback.pushInfo("  timezone: {}".format(summary.get("timezone")))
        feedback.pushInfo("  R5 version: {}".format(summary.get("r5_version")))
        b = summary.get("bounds") or {}
        if b:
            feedback.pushInfo("  bounds: {},{} .. {},{}".format(
                b.get("min_lon"), b.get("min_lat"), b.get("max_lon"), b.get("max_lat")
            ))

        service_days = summary.get("service_days") or {}
        served = sorted(d for d, n in service_days.items() if n > 0)
        if served:
            feedback.pushInfo(self.tr(
                "  served dates: {} .. {} — {} of {} days in the window have trips."
            ).format(served[0], served[-1], len(served), len(service_days)))
        elif service_days:
            feedback.pushWarning(self.tr(
                "  This feed has NO active service anywhere in the {}-day window — "
                "every date would produce walk-only results. Check the GTFS release."
            ).format(len(service_days)))
