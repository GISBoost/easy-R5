"""Processing provider for Easy-R5."""

from qgis.core import QgsProcessingProvider

from .algorithms.build_network import BuildNetwork
from .algorithms.download_r5 import DownloadR5
from .algorithms.generate_isochrones import GenerateIsochrones
from .algorithms.population_overlay import PopulationOverlay
from .algorithms.prepare_population_layer import PreparePopulationLayer
from .algorithms.run_accessibility import RunAccessibility
from .algorithms.run_travel_time_matrix import RunTravelTimeMatrix
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
        self.addAlgorithm(BuildNetwork())
        self.addAlgorithm(TestR5Setup())
        self.addAlgorithm(RunTravelTimeMatrix())
        self.addAlgorithm(RunAccessibility())
        self.addAlgorithm(GenerateIsochrones())
        self.addAlgorithm(PreparePopulationLayer())
        self.addAlgorithm(PopulationOverlay())
