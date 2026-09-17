"""Processing provider for Easy-R5."""

from qgis.core import QgsProcessingProvider

from .algorithms.build_network import BuildNetwork
from .algorithms.build_scenario import BuildScenario
from .algorithms.check_transit_data import CheckTransitData
from .algorithms.compare_scenarios import CompareScenarios
from .algorithms.download_r5 import DownloadR5
from .algorithms.download_realized_gtfs import DownloadRealizedGtfs
from .algorithms.generate_isochrones import GenerateIsochrones
from .algorithms.population_overlay import PopulationOverlay
from .algorithms.prepare_population_layer import PreparePopulationLayer
from .algorithms.run_accessibility import RunAccessibility
from .algorithms.run_competitive_accessibility import RunCompetitiveAccessibility
from .algorithms.run_service_minutes import RunServiceMinutes
from .algorithms.run_travel_time_matrix import RunTravelTimeMatrix
from .algorithms.summarize_accessibility_equity import SummarizeAccessibilityEquity
from .algorithms.test_r5_setup import TestR5Setup


class EasyR5Provider(QgsProcessingProvider):
    def id(self) -> str:  # noqa: A003 — Qt API name
        return "easyr5"

    def name(self) -> str:
        return "Easy-R5"

    def longName(self) -> str:  # noqa: N802 — Qt API name
        return "Easy-R5 — transit accessibility via Conveyal R5"

    def loadAlgorithms(self) -> None:  # noqa: N802 — Qt API name
        self.addAlgorithm(DownloadR5())
        self.addAlgorithm(DownloadRealizedGtfs())
        self.addAlgorithm(BuildNetwork())
        self.addAlgorithm(TestR5Setup())
        self.addAlgorithm(CheckTransitData())
        self.addAlgorithm(RunTravelTimeMatrix())
        self.addAlgorithm(RunAccessibility())
        self.addAlgorithm(RunServiceMinutes())
        self.addAlgorithm(RunCompetitiveAccessibility())
        self.addAlgorithm(SummarizeAccessibilityEquity())
        self.addAlgorithm(GenerateIsochrones())
        self.addAlgorithm(PreparePopulationLayer())
        self.addAlgorithm(PopulationOverlay())
        self.addAlgorithm(BuildScenario())
        self.addAlgorithm(CompareScenarios())
