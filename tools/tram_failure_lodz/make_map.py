"""Render the impact maps. Runs inside QGIS.

net_delta is a small signed number with a meaningful zero and a heavily zero-inflated
distribution, so it gets the same manual, zero-isolated classification as
../realtime_delay_lodz: QGIS's automatic classifiers put "no change" and "lost two
opportunities" in one bucket, which is exactly the distinction the map exists to show.
Class edges sit at half-integers so an integer delta can never land on a boundary.
"""

from __future__ import annotations

from pathlib import Path

try:
    from qgis.core import (
        QgsFillSymbol,
        QgsGraduatedSymbolRenderer,
        QgsLayerTreeGroup,
        QgsLineSymbol,
        QgsMapSettings,
        QgsMapRendererParallelJob,
        QgsProject,
        QgsRendererRange,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor
except ImportError as exc:  # pragma: no cover
    raise SystemExit("make_map.py must run inside QGIS.") from exc

HERE = Path(__file__).resolve().parent
GRIDS_DIR = HERE / "grids"
FIG = HERE / "out" / "figures"
GRID = "h250"


def gpkg(grid_id=None):
    return GRIDS_DIR / f"{grid_id or GRID}.gpkg"


# ColorBrewer RdBu-7. Losses are red; zero is a present, pale grey, not a hole.
CLASSES = [
    (-1e9, -6.5, "#67001f", "traci 7 i więcej"),
    (-6.5, -3.5, "#b2182b", "traci 4–6"),
    (-3.5, -1.5, "#d6604d", "traci 2–3"),
    (-1.5, -0.5, "#f4a582", "traci 1"),
    (-0.5, 0.5, "#f7f7f7", "bez zmiany"),
    (0.5, 1e9, "#92c5de", "zyskuje"),
]


def style_delta(layer, field="net_delta"):
    ranges = []
    for lo, hi, colour, label in CLASSES:
        sym = QgsFillSymbol.createSimple(
            {"color": colour, "outline_color": "#ffffff", "outline_width": "0.06"})
        ranges.append(QgsRendererRange(lo, hi, sym, label))
    renderer = QgsGraduatedSymbolRenderer(field, ranges)
    renderer.setClassAttribute(field)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
    return layer


def render(case, out_name, title_lines=(), width=1500, height=1500, grid_id=None):
    g = gpkg(grid_id)
    hexes = QgsVectorLayer(f"{g}|layername=hex_impact_{case}", f"impact_{case}", "ogr")
    if not hexes.isValid():
        raise RuntimeError(f"missing layer hex_impact_{case}")
    style_delta(hexes)

    trams = QgsVectorLayer(f"{g}|layername=tram_lines", "tram_lines", "ogr")
    trams.setRenderer(trams.renderer().clone())
    trams.renderer().setSymbol(QgsLineSymbol.createSimple(
        {"color": "50,50,50,120", "width": "0.25"}))

    boundary = QgsVectorLayer(f"{g}|layername=boundary", "boundary", "ogr")
    boundary.setRenderer(boundary.renderer().clone())
    boundary.renderer().setSymbol(QgsFillSymbol.createSimple(
        {"color": "255,255,255,0", "outline_color": "80,80,80", "outline_width": "0.3"}))

    settings = QgsMapSettings()
    settings.setLayers([trams, boundary, hexes])
    settings.setBackgroundColor(QColor("white"))
    settings.setOutputSize(QSize(width, height))
    settings.setDestinationCrs(hexes.crs())
    extent = hexes.extent()
    extent.scale(1.05)
    settings.setExtent(extent)

    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / out_name
    job.renderedImage().save(str(path))
    print("[ok]", path, "|", " ".join(title_lines))
    return path


def add_to_project(cases=("loo_5", "corridor", "all_trams")):
    """Put the styled layers in the open project so they can be inspected by hand."""
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group = root.findGroup("Awaria tramwaju")
    if group is None:
        group = QgsLayerTreeGroup("Awaria tramwaju")
        root.insertChildNode(0, group)
    for case in cases:
        lyr = QgsVectorLayer(f"{gpkg()}|layername=hex_impact_{case}", f"strata — {case}", "ogr")
        if not lyr.isValid():
            continue
        style_delta(lyr)
        project.addMapLayer(lyr, False)
        group.addLayer(lyr)
    for name in ("tram_lines", "boundary"):
        lyr = QgsVectorLayer(f"{gpkg()}|layername={name}", name, "ogr")
        if lyr.isValid():
            project.addMapLayer(lyr, False)
            group.addLayer(lyr)
    print("[ok] layers added to the project under 'Awaria tramwaju'")


def main(grid_id="h250"):
    global GRID
    GRID = grid_id
    render("loo_5", f"06_mapa_linia5_{grid_id}.png", ("linia 5 nie jeździ",))
    render("corridor", f"07_mapa_korytarz_{grid_id}.png", ("torowisko 5+16",))
    render("all_trams", f"08_mapa_wszystkie_{grid_id}.png", ("żaden tramwaj",))
    print("[done] maps for", grid_id, "in", FIG)


def main_all(grids=("h250", "h500", "h1000")):
    """The same map on each grid -- the visual half of the MAUP check."""
    for g in grids:
        if gpkg(g).exists():
            main(g)


if __name__ == "__main__":
    main()
