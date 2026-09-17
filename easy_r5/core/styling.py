"""Auto-apply a bundled QML style to a Processing output layer.

Usage in ``processAlgorithm`` after ``parameterAsSink``:

    from ..core.styling import apply_style
    apply_style(context, sink_id, "isochrones.qml")

Keeps a module-level reference to each post-processor — QGIS holds only a weak
reference and would otherwise garbage-collect it before the layer loads.
"""

from __future__ import annotations

from pathlib import Path

_STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"
_KEEPALIVE = []


def apply_style(context, dest_id, qml_name):
    """Load ``styles/<qml_name>`` onto the completed layer for ``dest_id``."""
    qml = _STYLES_DIR / qml_name
    if not qml.is_file() or not dest_id:
        return
    try:
        from qgis.core import QgsProcessingLayerPostProcessorInterface

        class _StylePP(QgsProcessingLayerPostProcessorInterface):
            def postProcessLayer(self, layer, context, feedback):  # noqa: N802
                layer.loadNamedStyle(str(qml))
                layer.triggerRepaint()

        pp = _StylePP()
        _KEEPALIVE.append(pp)
        context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(pp)
    except Exception:  # nosec B110 — styling is cosmetic, never fail the run for it
        pass


def apply_categories(context, dest_id, field, categories):
    """Categorized renderer on ``field``: ``categories`` = [(value, "#rrggbb", label), ...].

    Built in code rather than a bundled QML because the symbol must match the
    output's geometry type (points or hex polygons), which a static QML cannot.
    """
    if not dest_id:
        return
    try:
        from qgis.PyQt.QtGui import QColor
        from qgis.core import (
            QgsCategorizedSymbolRenderer,
            QgsProcessingLayerPostProcessorInterface,
            QgsRendererCategory,
            QgsSymbol,
        )

        class _CategoriesPP(QgsProcessingLayerPostProcessorInterface):
            def postProcessLayer(self, layer, context, feedback):  # noqa: N802
                cats = []
                for value, color, label in categories:
                    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                    symbol.setColor(QColor(color))
                    cats.append(QgsRendererCategory(value, symbol, label))
                layer.setRenderer(QgsCategorizedSymbolRenderer(field, cats))
                layer.triggerRepaint()

        pp = _CategoriesPP()
        _KEEPALIVE.append(pp)
        context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(pp)
    except Exception:  # nosec B110 — styling is cosmetic, never fail the run for it
        pass
