"""Assemble one QGIS project (delay_cities.qgz) with every city's hex_delay
and hex_net_opportunities, grouped per city, styled with the manual
zero-isolated diverging classification from style_delay_layers.py.

Per city group (250 m first, then 500 m where it exists):
  hex_net_opportunities   styled on net_delta   (visible)
  hex_delay               styled on delta_school (hidden; swap the field in
                          Symbology for pharmacy/university/mall -- same 7 classes)
  boundary                outline only
Only the first city's group is expanded / visible.

Run inside the QGIS Python env, e.g. mcp__qgis__execute_code.
"""

from __future__ import annotations

from pathlib import Path

from qgis.core import (
    QgsLayerTreeGroup, QgsLineSymbol, QgsProject, QgsVectorLayer,
)

import cities as C
import style_delay_layers as sd
from prepare_data import gpkg_path

HERE = Path(__file__).resolve().parent
LODZ_DIR = HERE.parent / "realtime_delay_lodz"
PROJECT = HERE / "delay_cities.qgz"

ORDER = ["lodz"] + list(C.CITIES)
DISPLAY = {**{k: v[0] for k, v in C.CITIES.items()}, "lodz": "Łódź"}


def _gpkg(city, res):
    if city == "lodz":
        return LODZ_DIR / ("delay_lodz.gpkg" if res == 250 else "delay_lodz_500m.gpkg")
    return gpkg_path(city, res)


def _resolutions(city):
    return (250, 500) if city == "lodz" else C.CITIES[city][1]


def _add(group, gpkg, layername, style_fn, title, visible):
    lyr = QgsVectorLayer(f"{gpkg}|layername={layername}", title, "ogr")
    if not lyr.isValid():
        print(f"[skip] {title}: cannot load {gpkg.name}|{layername}")
        return
    style_fn(lyr)
    QgsProject.instance().addMapLayer(lyr, False)
    node = group.addLayer(lyr)
    node.setItemVisibilityChecked(visible)


def _boundary_style(lyr):
    lyr.setRenderer(lyr.renderer())
    sym = QgsLineSymbol.createSimple({"color": "#333333", "width": "0.4"})
    from qgis.core import QgsSingleSymbolRenderer
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))


def main():
    proj = QgsProject.instance()
    proj.clear()
    root = proj.layerTreeRoot()

    for ci, city in enumerate(ORDER):
        cgroup = root.addGroup(DISPLAY[city])
        cgroup.setExpanded(ci == 0)
        cgroup.setItemVisibilityChecked(ci == 0)
        for ri, res in enumerate(_resolutions(city)):
            gpkg = _gpkg(city, res)
            if not gpkg.exists():
                print(f"[skip] {city} {res}m -- {gpkg.name} missing")
                continue
            rgroup = cgroup.addGroup(f"{res} m")
            rgroup.setExpanded(ci == 0 and ri == 0)
            rgroup.setItemVisibilityChecked(ci == 0 and ri == 0)
            _add(rgroup, gpkg, "hex_net_opportunities", sd.style_net_delta,
                 f"net Δ ({res} m)", visible=True)
            _add(rgroup, gpkg, "hex_delay", lambda l: sd.style_delta_field(l, "school"),
                 f"delta_school ({res} m)", visible=False)
            _add(rgroup, gpkg, "boundary", _boundary_style, f"boundary ({res} m)", visible=True)

    proj.write(str(PROJECT))
    print(f"[ok] wrote {PROJECT}")


if __name__ == "__main__":
    main()
