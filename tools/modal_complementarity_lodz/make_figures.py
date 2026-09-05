"""F4 -- cartography for the flagship Lodz modal-complementarity analysis.

Builds all three figures via QgsPrintLayout (PyQGIS), per PRD SS6-SS7:
  P1  docs/img/flagship-lodz-tram-share-{pl,en}.png     -- hero image
  P2  docs/img/flagship-lodz-transfer-premium-{pl,en}.png
  P3  docs/img/flagship-lodz-modal-bars.png             -- Abar^m x cutoff bar chart

Rendered at 2x (2400x1440) then downscaled to the delivered 1200x720, per PRD
SS7's "render 2x, export 1x" instruction (crisper text/lines after downscale).

Palette: tools/modal_complementarity_lodz/styles/palette.md (validated with the
dataviz skill's validate_palette.js -- do not hand-edit a hex without re-running it).
Layer styles saved to tools/modal_complementarity_lodz/styles/*.qml.

Must run inside the QGIS Python environment (qgis.core + processing).
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsFillSymbol,
        QgsGeometry,
        QgsLayout,
        QgsLayoutExporter,
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsLayoutItemShape,
        QgsLayoutSize,
        QgsLineSymbol,
        QgsPointXY,
        QgsProject,
        QgsGraduatedSymbolRenderer,
        QgsRendererRange,
        QgsUnitTypes,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QRectF, QSize, Qt
    from qgis.PyQt.QtGui import QColor, QFont, QFontMetrics
    import processing
except ImportError as exc:  # pragma: no cover -- guard for plain `py` runs
    raise SystemExit(
        "make_figures.py needs qgis.core + processing. Run it inside the QGIS "
        "Python console or via mcp__qgis__execute_code."
    ) from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GPKG = HERE / "lodz_modal.gpkg"
OUT = HERE / "out"
STYLES = HERE / "styles"
IMG_DIR = REPO / "docs" / "img"

SCALE = 2  # render at 2x, downscale to the delivered size
W1X, H1X = 1200, 720
CANVAS_W, CANVAS_H = W1X * SCALE, H1X * SCALE
LEFT_W = round(0.34 * CANVAS_W)
MARGIN = 32 * SCALE

BG = "#FAF8F4"
NO_ACCESS = "#E6E3DE"
NO_RESIDENTS = QColor(0, 0, 0, 0)
BOUNDARY_LINE = "#B9B4AC"
TRAM_LINE = "#3a3a38"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"

P1_BOUNDS = [0.0, 0.05, 0.15, 0.25, 0.40, 0.55, 0.70, 1.01]
P1_COLORS = ["#87b3e8", "#619be1", "#3a82d9", "#256cc0", "#1e569a", "#164173", "#0f2b4d"]
P2_BOUNDS = [-0.0001, 0.0000001, 0.05, 0.10, 0.20, 1.5]
P2_COLORS = ["#f0906a", "#ea5d25", "#b03f11", "#822e0d", "#541e08"]

K_THRESHOLD = 1000
HEXAGONS_TOTAL = 1479

DISCLAIMER = {
    "pl": (
        "Wyłączenie tramwaju w modelu jest miarą zależności, nie prognozą polityki "
        "transportowej: model nie uruchamia komunikacji zastępczej, nie przenosi "
        "pasażerów i nie zmienia rozkładu autobusów."
    ),
    "en": (
        "Removing the tram in this model is a measure of dependency, not a "
        "transport-policy forecast: the model does not run replacement buses, "
        "does not move passengers, and does not change bus schedules."
    ),
}


def load_run_meta():
    return json.loads((OUT / "run_meta.json").read_text(encoding="utf-8"))


def load_city_summary():
    with open(OUT / "city_summary.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --- tram network inset -----------------------------------------------------

def load_tram_shape_ids(gtfs_zip):
    with zipfile.ZipFile(gtfs_zip) as z:
        routes = list(csv.DictReader(io.TextIOWrapper(z.open("routes.txt"), encoding="utf-8-sig")))
        tram_routes = {r["route_id"] for r in routes if r["route_type"] == "0"}
        trips = csv.DictReader(io.TextIOWrapper(z.open("trips.txt"), encoding="utf-8-sig"))
        return {t["shape_id"] for t in trips if t["route_id"] in tram_routes and t.get("shape_id")}


def build_tram_layer(gtfs_zip, target_crs):
    shape_ids = load_tram_shape_ids(gtfs_zip)
    with zipfile.ZipFile(gtfs_zip) as z:
        rows = list(csv.DictReader(io.TextIOWrapper(z.open("shapes.txt"), encoding="utf-8-sig")))
    by_shape = {}
    for r in rows:
        sid = r["shape_id"]
        if sid not in shape_ids:
            continue
        by_shape.setdefault(sid, []).append(
            (int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"]))
        )
    mem = QgsVectorLayer("LineString?crs=EPSG:4326", "tram_shapes", "memory")
    feats = []
    for pts in by_shape.values():
        pts.sort(key=lambda p: p[0])
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat) for _, lon, lat in pts]))
        feats.append(feat)
    mem.dataProvider().addFeatures(feats)
    mem.updateExtents()
    reprojected = processing.run(
        "native:reprojectlayer",
        {"INPUT": mem, "TARGET_CRS": target_crs, "OUTPUT": "TEMPORARY_OUTPUT"},
    )["OUTPUT"]
    line_symbol = QgsLineSymbol.createSimple({"color": TRAM_LINE, "width": "0.5"})
    reprojected.renderer().setSymbol(line_symbol)
    return reprojected


# --- hex_modal styling -------------------------------------------------------

def _fill_symbol(color):
    if isinstance(color, QColor):
        color = "{},{},{},{}".format(color.red(), color.green(), color.blue(), color.alpha())
    return QgsFillSymbol.createSimple({"style": "solid", "color": color, "outline_style": "no"})


# QgsRuleBasedRenderer was found (2026-09-05) to render nothing in this QGIS
# 3.40.5 build -- confirmed with the simplest possible rule tree (one root,
# one catch-all child, solid fill) via mcp__qgis__execute_code; a plain
# QgsGraduatedSymbolRenderer (the same renderer type easy_r5/styles/
# accessibility.qml already uses successfully) works. Classifying by a CASE
# expression instead of a bare field name folds the two sentinel classes
# ("no residents" -> -2, "no access" -> -1) into the same numeric ranges
# machinery, no extra computed field needed.
_NO_RESIDENTS_SENTINEL = -2.0
_NO_ACCESS_SENTINEL = -1.0


def _classify_expression(field):
    return (
        'CASE WHEN "pop_total" IS NULL OR "pop_total" = 0 THEN {no_res} '
        'WHEN "{f}" IS NULL THEN {no_acc} '
        'ELSE "{f}" END'
    ).format(f=field, no_res=_NO_RESIDENTS_SENTINEL, no_acc=_NO_ACCESS_SENTINEL)


def build_graduated_renderer(field, bounds, colors, class_labels, no_access_label):
    ranges = [
        QgsRendererRange(
            _NO_RESIDENTS_SENTINEL - 0.5, _NO_RESIDENTS_SENTINEL + 0.5,
            _fill_symbol(NO_RESIDENTS), "No residents",
        ),
        QgsRendererRange(
            _NO_ACCESS_SENTINEL - 0.5, _NO_ACCESS_SENTINEL + 0.5,
            _fill_symbol(NO_ACCESS), no_access_label,
        ),
    ]
    lower = bounds[0]
    for upper, color, label in zip(bounds[1:], colors, class_labels):
        ranges.append(QgsRendererRange(lower, upper, _fill_symbol(color), label))
        lower = upper
    renderer = QgsGraduatedSymbolRenderer(_classify_expression(field), ranges)
    return renderer


def style_hex_layer(layer, field, bounds, colors, class_labels, no_access_label, qml_path):
    layer.setRenderer(build_graduated_renderer(field, bounds, colors, class_labels, no_access_label))
    layer.triggerRepaint()
    layer.saveNamedStyle(str(qml_path))


# --- layout building ---------------------------------------------------------
#
# QgsLayout with layout.setUnits(QgsUnitTypes.LayoutPixels) was found
# (2026-09-05) to silently break text sizing in QGIS 3.40.5 -- QgsTextFormat
# AND QgsLayoutItemLabel.setFont() both collapse to a ~8px system-default
# font regardless of the requested size, while plain shapes/maps position
# correctly. Millimeters + point-sized fonts (the traditional QGIS layout
# convention) render correctly. So everything here stays "design pixels" at
# the API surface (matching the PRD's px spec) and converts to mm/pt only at
# the two points that touch QGIS geometry/font objects: `mm()` and `pt()`.

DPI = 300.0
_PX_TO_MM = 25.4 / DPI
_PX_TO_PT = 72.0 / DPI


def mm(px_value):
    return px_value * _PX_TO_MM


def pt(px_value):
    return px_value * _PX_TO_PT


def new_layout(project, width=CANVAS_W, height=CANVAS_H):
    layout = QgsLayout(project)
    layout.initializeDefaults()
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(mm(width), mm(height), QgsUnitTypes.LayoutMillimeters))
    page_symbol = QgsFillSymbol.createSimple({"style": "solid", "color": BG, "outline_style": "no"})
    page.setPageStyleSymbol(page_symbol)
    return layout


def add_label(layout, text, x, y, w, h, size_px, color=INK_PRIMARY, bold=False, align=Qt.AlignLeft):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    font = QFont("Sans Serif")
    font.setBold(bold)
    font.setPointSizeF(pt(size_px))
    item.setFont(font)
    item.setFontColor(QColor(color))
    item.setHAlign(align)
    item.attemptSetSceneRect(QRectF(mm(x), mm(y), mm(w), mm(h)))
    layout.addLayoutItem(item)
    return item


def text_width(text, size_px, bold=False):
    """Pixel width at the design scale -- pure Qt QFontMetrics, unaffected by
    the QGIS layout-unit bug (it never touches a QgsLayout)."""
    font = QFont("Sans Serif")
    font.setBold(bold)
    font.setPixelSize(size_px)
    return QFontMetrics(font).horizontalAdvance(text)


def add_map(layout, project, layers, extent, x, y, w, h, crs):
    item = QgsLayoutItemMap(layout)
    item.attemptSetSceneRect(QRectF(mm(x), mm(y), mm(w), mm(h)))
    item.setLayers(layers)
    item.setCrs(crs)
    item.zoomToExtent(extent)
    item.setFrameEnabled(False)
    layout.addLayoutItem(item)
    return item


def add_rect(layout, x, y, w, h, color, stroke=None):
    item = QgsLayoutItemShape(layout)
    item.setShapeType(QgsLayoutItemShape.Rectangle)
    item.attemptSetSceneRect(QRectF(mm(x), mm(y), mm(w), mm(h)))
    sym = QgsFillSymbol.createSimple({
        "style": "solid", "color": color,
        "outline_style": "solid" if stroke else "no",
        "outline_color": stroke or "#000000", "outline_width": "0.5",
    })
    item.setSymbol(sym)
    layout.addLayoutItem(item)
    return item


def add_progress_swatch(layout, x, y, w, h, fraction, fill_color, empty_color="#DAD7D0"):
    """A little inline progress bar -- the "[..] legend woven into the sentence" motif."""
    add_rect(layout, x, y, w, h, empty_color)
    filled_w = max(2, round(w * fraction))
    add_rect(layout, x, y, filled_w, h, fill_color)


def export_layout(
    layout, out_path_2x, out_path_final, width_px=CANVAS_W, height_px=CANVAS_H,
    final_w=W1X, final_h=H1X,
):
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.imageSize = QSize(width_px, height_px)
    exporter.exportToImage(str(out_path_2x), settings)
    from qgis.PyQt.QtGui import QImage
    img = QImage(str(out_path_2x))
    scaled = img.scaled(final_w, final_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    scaled.save(str(out_path_final))
    out_path_2x.unlink()


# --- P1 / P2 hero composition ------------------------------------------------

def build_hero(lang, field, bounds, colors, class_labels, no_access_label, title, method_text,
               legend_before, legend_fraction, legend_after, interpretation, source_line,
               out_name, gtfs_zip):
    project = QgsProject()
    # hex_modal's native CRS (UWPP_1992, no EPSG code) was found (2026-09-05) to
    # render as a blank QgsLayoutItemMap despite crs().isValid() == True -- a
    # standard EPSG-coded CRS renders fine. Reproject everything used in a map
    # item to EPSG:2180 (the real system this custom CRS approximates).
    map_crs = QgsCoordinateReferenceSystem("EPSG:2180")

    hex_layer_raw = QgsVectorLayer(f"{GPKG}|layername=hex_modal", "hex_modal", "ogr")
    hex_layer = processing.run(
        "native:reprojectlayer", {"INPUT": hex_layer_raw, "TARGET_CRS": map_crs, "OUTPUT": "TEMPORARY_OUTPUT"}
    )["OUTPUT"]
    style_hex_layer(
        hex_layer, field, bounds, colors, class_labels, no_access_label, STYLES / f"{out_name}.qml"
    )

    boundary_src = REPO / "tools" / "accessibility_lodz" / "lodz_hex_boundary.geojson"
    boundary_raw = QgsVectorLayer(str(boundary_src), "boundary", "ogr")
    boundary = processing.run(
        "native:reprojectlayer", {"INPUT": boundary_raw, "TARGET_CRS": map_crs, "OUTPUT": "TEMPORARY_OUTPUT"}
    )["OUTPUT"]
    boundary_sym = QgsLineSymbol.createSimple({"color": BOUNDARY_LINE, "width": "0.3"})
    boundary.renderer().setSymbol(boundary_sym)

    tram_layer = build_tram_layer(gtfs_zip, map_crs)
    project.addMapLayers([boundary, hex_layer, tram_layer])

    layout = new_layout(project)

    x = MARGIN
    w = LEFT_W - 2 * MARGIN
    y = MARGIN
    title_size = 30 * SCALE
    add_label(layout, title, x, y, w, 130 * SCALE, title_size, bold=True)
    y += 150 * SCALE

    method_size = 13 * SCALE
    add_label(layout, method_text, x, y, w, 140 * SCALE, method_size, color=INK_SECONDARY)
    y += 155 * SCALE

    # legend sentence, woven: text ending in a swatch, continuation directly below
    # (an inline text-swatch-text single line was tried and dropped 2026-09-05:
    # QgsLayoutItemLabel does not wrap/clip the trailing segment reliably at
    # this column width, so it overflowed into the map).
    seg1_w = text_width(legend_before, method_size, bold=False)
    add_label(layout, legend_before, x, y, min(seg1_w + 4 * SCALE, w), 24 * SCALE, method_size)
    swatch_w = 90 * SCALE
    swatch_x = x + min(seg1_w, w - swatch_w - 4 * SCALE) + 4 * SCALE
    add_progress_swatch(
        layout, swatch_x, y + 4 * SCALE, swatch_w, 12 * SCALE, legend_fraction, colors[-2]
    )
    y += 30 * SCALE
    add_label(layout, legend_after, x, y, w, 24 * SCALE, method_size)
    y += 34 * SCALE

    interp_size = 13 * SCALE
    add_label(layout, interpretation, x, y, w, 90 * SCALE, interp_size, color=INK_SECONDARY)
    y += 100 * SCALE

    disclaimer_size = 12 * SCALE
    add_label(layout, DISCLAIMER[lang], x, y, w, 90 * SCALE, disclaimer_size,
              color=INK_PRIMARY, bold=True)

    # source micro-line, bottom of left column
    source_size = 9 * SCALE
    add_label(layout, source_line, x, CANVAS_H - MARGIN - 60 * SCALE, w, 60 * SCALE,
              source_size, color=INK_MUTED)

    # map
    map_x = LEFT_W
    map_w = CANVAS_W - LEFT_W
    map_extent = hex_layer.extent()
    add_map(layout, project, [boundary, hex_layer], map_extent,
            map_x, 0, map_w, CANVAS_H, map_crs)

    # inset: tram network for comparison, bottom-right
    inset_w, inset_h = 400, 280
    inset_x = CANVAS_W - inset_w - MARGIN
    inset_y = CANVAS_H - inset_h - MARGIN - 30 * SCALE
    add_rect(layout, inset_x - 6, inset_y - 6, inset_w + 12, inset_h + 12, "#FFFFFF",
             stroke="#B9B4AC")
    add_map(layout, project, [tram_layer], tram_layer.extent(),
            inset_x, inset_y, inset_w, inset_h, map_crs)
    inset_label = {"pl": "sieć tramwajowa dla porównania", "en": "tram network, for comparison"}[lang]
    add_label(layout, inset_label, inset_x, inset_y + inset_h + 2, inset_w, 24 * SCALE,
              9 * SCALE, color=INK_MUTED, align=Qt.AlignHCenter)

    out_2x = OUT / f"{out_name}_2x.png"
    out_final = IMG_DIR / f"{out_name}-{lang}.png"
    export_layout(layout, out_2x, out_final)
    print(f"[ok] wrote {out_final} ({out_final.stat().st_size / 1024:.0f} KB)")


# --- P3 bar chart -------------------------------------------------------------

def build_bars():
    rows = load_city_summary()
    cutoffs = sorted({int(r["cutoff"]) for r in rows})
    cases = ["W", "T", "B", "TB"]
    case_colors = {"W": INK_MUTED, "T": "#2a78d6", "B": "#eb6834", "TB": "#4a3aa7"}
    case_labels = {"W": "pieszo", "T": "tramwaj", "B": "autobus", "TB": "cała sieć"}

    by_case_cutoff = {(r["case"], int(r["cutoff"])): float(r["acc_weighted_mean"]) for r in rows}
    subadd_by_cutoff = {int(r["cutoff"]): r["subadd_city"] for r in rows if r["case"] == "TB"}

    project = QgsProject()
    layout = new_layout(project, width=1600 * SCALE, height=900 * SCALE)
    cw, ch = 1600 * SCALE, 900 * SCALE

    chart_x, chart_y = 120 * SCALE, 180 * SCALE
    chart_w, chart_h = cw - 2 * 120 * SCALE, ch - 320 * SCALE
    max_val = max(by_case_cutoff.values()) * 1.15

    add_label(layout, "Dostępność ważona populacją, wg przypadku modalnego i progu czasowego",
              chart_x, 30 * SCALE, chart_w, 50 * SCALE, 22 * SCALE, bold=True)

    # legend row
    lx = chart_x
    for case in cases:
        add_rect(layout, lx, 90 * SCALE, 20 * SCALE, 20 * SCALE, case_colors[case])
        lbl_w = text_width(case_labels[case], 14 * SCALE) + 30 * SCALE
        add_label(layout, case_labels[case], lx + 26 * SCALE, 88 * SCALE, lbl_w, 24 * SCALE, 14 * SCALE)
        lx += 26 * SCALE + lbl_w

    group_w = chart_w / len(cutoffs)
    bar_w = group_w / (len(cases) + 1.5)
    for gi, cutoff in enumerate(cutoffs):
        group_x = chart_x + gi * group_w
        add_label(layout, f"{cutoff} min", group_x, chart_y + chart_h + 8 * SCALE,
                  group_w, 30 * SCALE, 16 * SCALE, align=Qt.AlignHCenter)
        for ci, case in enumerate(cases):
            val = by_case_cutoff[(case, cutoff)]
            bar_h = chart_h * (val / max_val)
            bx = group_x + (ci + 0.5) * bar_w
            by = chart_y + chart_h - bar_h
            add_rect(layout, bx, by, bar_w * 0.85, bar_h, case_colors[case])
            add_label(layout, f"{val/1000:.0f}k", bx - 10 * SCALE, by - 22 * SCALE,
                      bar_w + 20 * SCALE, 20 * SCALE, 11 * SCALE, color=INK_SECONDARY,
                      align=Qt.AlignHCenter)
        # no_transfer dashed marker on the TB bar
        nt_val = None
        for r in rows:
            if r["case"] == "no_transfer" and int(r["cutoff"]) == cutoff:
                nt_val = float(r["acc_weighted_mean"])
        if nt_val is not None:
            tb_bx = group_x + (len(cases) - 1 + 0.5) * bar_w
            nt_y = chart_y + chart_h - chart_h * (nt_val / max_val)
            add_rect(layout, tb_bx - 4 * SCALE, nt_y, bar_w * 0.85 + 8 * SCALE, 2 * SCALE, INK_PRIMARY)
        subadd = subadd_by_cutoff.get(cutoff, "")
        add_label(layout, f"subadd={subadd}", group_x, chart_y - 26 * SCALE, group_w, 20 * SCALE,
                  11 * SCALE, color=INK_MUTED, align=Qt.AlignHCenter)

    add_label(
        layout,
        "Czarna kreska na słupku „cała sieć” = najlepszy pojedynczy tryb (tramwaj lub autobus, "
        "bez przesiadki). Odstęp między kreską a szczytem słupka to premia za przesiadkę "
        "międzymodalną. subadd < 1 = tryby się częściowo dublują (sub-addytywność).",
        chart_x, ch - 100 * SCALE, chart_w, 80 * SCALE, 13 * SCALE, color=INK_SECONDARY,
    )

    out_2x = OUT / "bars_2x.png"
    out_final = IMG_DIR / "flagship-lodz-modal-bars.png"
    export_layout(layout, out_2x, out_final, width_px=int(cw), height_px=int(ch),
                  final_w=1600, final_h=900)
    print(f"[ok] wrote {out_final} ({out_final.stat().st_size / 1024:.0f} KB)")


def main():
    print("=== F4: make_figures ===")
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    STYLES.mkdir(exist_ok=True)
    meta = load_run_meta()
    filtered = meta["hexagons_filtered_by_K"]
    gtfs_zip = HERE / "gtfs_static" / "lodz_static_gtfs_2026-08-21.zip"

    city = {(r["case"], int(r["cutoff"])): r for r in load_city_summary()}
    tb30 = float(city[("TB", 30)]["acc_weighted_mean"])
    b30 = float(city[("B", 30)]["acc_weighted_mean"])
    no_transfer30 = float(city[("no_transfer", 30)]["acc_weighted_mean"])
    tram_share_city = (tb30 - b30) / tb30
    transfer_premium_rel_city = (tb30 - no_transfer30) / tb30

    source_line = (
        "ZDiT Lodz GTFS 2026-08-24 . OpenStreetMap . GUS NSP 2021 . computed in QGIS with "
        "Easy-R5 on Conveyal R5 7.6 . CC BY 4.0 . reliability threshold K={k} people, "
        "{f}/{n} hexagons filtered . github.com/GISBoost/easy-R5"
    ).format(k=K_THRESHOLD, f=filtered, n=HEXAGONS_TOTAL)

    p1_titles = {"pl": "Dokad nie dojade,\njesli zniknie\ntramwaj?", "en": "Where I couldn't\nget to, if the tram\ndisappeared"}
    p1_method = {
        "pl": ("Mapa pokazuje udzial celow osiagalnych w 30 minut, ktore znikaja, gdy z sieci "
               "usunac tramwaj (autobus zostaje). Siatka 500 m, odjazd 07:00-09:00 w dzien "
               "powszedni, mediana. Populacja jako cel dostepnosci."),
        "en": ("The map shows the share of destinations reachable within 30 minutes that "
               "disappear if the tram is removed from the network (bus stays). 500 m grid, "
               "07:00-09:00 departure window, median. Population as the destination weight."),
    }
    p1_interp = {
        "pl": "Ciemne heksagony leza wzdluz korytarzy tramwajowych (patrz inset).",
        "en": "Dark hexagons line up along the tram corridors (see inset).",
    }
    p1_legend_before = {"pl": "Bez tramwaju przecietny mieszkaniec traciloby", "en": "Without the tram, the average resident would lose"}
    p1_legend_after = {"pl": "swojego 30-minutowego zasiegu.", "en": "of their 30-minute reach."}

    for lang in ("pl", "en"):
        build_hero(
            lang, "tram_share_pop_p50_c30", P1_BOUNDS, P1_COLORS,
            ["0-5%", "5-15%", "15-25%", "25-40%", "40-55%", "55-70%", ">70%"],
            {"pl": "brak dostepu transportem w 30 min", "en": "no transit access in 30 min"}[lang],
            p1_titles[lang], p1_method[lang], p1_legend_before[lang], tram_share_city,
            p1_legend_after[lang], p1_interp[lang], source_line,
            "flagship-lodz-tram-share", gtfs_zip,
        )

    p2_titles = {"pl": "Gdzie Lodz dziala\njako jedna siec,\na nie jako dwie?", "en": "Where does Lodz\nwork as one network,\nnot two?"}
    p2_method = {
        "pl": ("Mapa pokazuje, jaka czesc 30-minutowego zasiegu istnieje TYLKO dzieki przesiadce "
               "tramwaj-autobus -- czego zaden z trybow nie dalby osobno. Siatka 500 m, "
               "07:00-09:00, mediana."),
        "en": ("The map shows how much of the 30-minute reach exists ONLY because of an "
               "intermodal tram-bus transfer -- neither mode alone would give it. 500 m grid, "
               "07:00-09:00, median."),
    }
    p2_interp = {
        "pl": "Wysoka premia oznacza, ze tramwaj i autobus uzupelniaja sie w tym miejscu, nie dubluja.",
        "en": "A high premium means tram and bus complement, not duplicate, each other here.",
    }
    p2_legend_before = {"pl": "Dzieki przesiadce przecietny mieszkaniec zyskuje dodatkowo", "en": "Thanks to the transfer, the average resident gains an extra"}
    p2_legend_after = {"pl": "zasiegu niedostepnego zadnym trybem osobno.", "en": "of reach no single mode would give alone."}

    for lang in ("pl", "en"):
        build_hero(
            lang, "transfer_premium_rel_pop_p50_c30", P2_BOUNDS, P2_COLORS,
            ["0%", "0-5%", "5-10%", "10-20%", ">20%"],
            {"pl": "brak dostepu transportem w 30 min", "en": "no transit access in 30 min"}[lang],
            p2_titles[lang], p2_method[lang], p2_legend_before[lang], transfer_premium_rel_city,
            p2_legend_after[lang], p2_interp[lang], source_line,
            "flagship-lodz-transfer-premium", gtfs_zip,
        )

    build_bars()
    print("=== F4 done ===")


if __name__ == "__main__":
    main()
