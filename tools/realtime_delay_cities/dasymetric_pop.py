"""Dasymetric population re-estimate for the delay-accessibility hex grids.

Why this exists
---------------
`easyr5:populationoverlay` (used by prepare_data, a port of the reference model
`easy-OTP/docs/reference-R/ludnosc_studentow_model_qgis.py`) is *areal
interpolation*: it assumes every census precinct's population sits at uniform
density across the precinct's whole polygon. For big sparse precincts (port
land, rail yards, allotment gardens, fields and forest inside the city
boundary) that smears "phantom" residents onto hexagons where nobody lives --
e.g. Kraków hex #178 got ~4 people from a 287-person precinct that is only
2.7 % built and whose hex covers only fields and tracks; hex #143 got 0.27
from a 9-person / 1.8 km² precinct.

This module redistributes each precinct's GUS population onto the *built-up*
part only: proportional to OSM building **footprint area** per precinct,
mass-preserving. Precincts with no residential buildings fall back to the old
uniform areal split so nobody is dropped. (Binary dasymetric mapping,
Mennis 2003 -- storeys deliberately not used: OSM `building:levels` coverage
in PL is uneven, per Michał 2026-09-10.)

Then hexagons whose dasymetric population is below `MIN_POP` are removed from
`hex_grid` and `hex_centroids` -- "nobody lives here, it is not part of a
*population* accessibility study". `siatka` (the full grid outline) and
`boundary` are left intact; `siatka` is also the stable geometry source here,
so re-running this is idempotent.

Cost note: the OSM building extract + rasterisation is the slow step (~15-40 s
per city). It is cached to work/dasym/<city>_bld.tif (a 1-byte 10 m built/
not-built raster, a few MB) and reused across both resolutions. Delete that
folder to force a rebuild.

Usage (inside QGIS / mcp__qgis__execute_code)
--------------------------------------------
    import dasymetric_pop as dp
    dp.build_rasters()               # optional: pre-build every city raster
    dp.report("krakow", 250)         # print before/after, change nothing
    dp.apply("krakow", 250)          # rewrite hex_grid/hex_centroids
    dp.apply_all()                   # every city + resolution, incl. Łódź

After apply_*: re-run compute_delay + the downstream roll-ups. No R5 re-run --
per-hex accessibility is geometry-only and unchanged; only the population
weight and the in-scope set of hexagons change.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

try:
    import processing
    from qgis.core import QgsProcessing, QgsVectorFileWriter, QgsVectorLayer
except ImportError as exc:  # pragma: no cover
    raise SystemExit("dasymetric_pop.py runs inside QGIS (mcp__qgis__execute_code).") from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RASTER_DIR = HERE / "work" / "dasym"

MIN_POP = 0.5          # a hex the model puts < 0.5 person in -> not in scope
RASTER_M = 10          # building raster cell (m)
PAD_M = 300            # raster extent padding beyond the grid

# Building values that do not house residents -> excluded from the footprint.
EXCL_BUILDINGS = {
    "no", "garage", "garages", "carport", "shed", "outbuilding", "roof",
    "greenhouse", "greenhouse_horticulture", "construction", "industrial",
    "warehouse", "retail", "commercial", "office", "manufacture",
    "transportation", "service", "hangar", "parking", "hospital", "school",
    "kindergarten", "university", "college", "church", "chapel", "mosque",
    "synagogue", "temple", "cathedral", "civic", "public", "government",
    "train_station", "bridge", "bunker", "military", "stable", "barn",
    "farm_auxiliary", "cowshed", "sty", "slurry_tank", "transformer_tower",
    "kiosk", "hut", "boathouse", "ruins", "collapsed", "abandoned", "tent",
    "grandstand", "tribune", "stadium", "sports_hall", "sports_centre",
    "pavilion", "container", "trailer", "storage_tank", "silo", "digester",
    "gasometer", "water_tower", "cooling_tower", "chimney", "supermarket",
    "kingdom_hall", "shrine", "toilets", "carriageway", "guardhouse",
    "gatehouse", "hotel", "motel", "hostel", "prison", "sauna",
}


def _paths(city: str) -> dict:
    if city == "lodz":
        acc = REPO / "tools" / "accessibility_lodz"
        return {
            "pbf": acc / "lodz.osm.pbf",
            "ses": REPO / "tools" / "ses_income_lodz" / "lodz.gpkg",
            "gpkg": lambda r: (REPO / "tools" / "realtime_delay_lodz" /
                               ("delay_lodz.gpkg" if r == 250 else f"delay_lodz_{r}m.gpkg")),
            "resolutions": (250, 500),
        }
    import cities as C
    p = C.paths(city)
    return {
        "pbf": p["osm_pbf"],
        "ses": p["ses_gpkg"],
        "gpkg": lambda r: HERE / (f"delay_{city}.gpkg" if r == 250 else f"delay_{city}_{r}m.gpkg"),
        "resolutions": C.CITIES[city][1],
    }


def _run(alg, params, out="OUTPUT"):
    return processing.run(alg, params)[out]


def _siatka(city: str):
    """Full clipped grid (never filtered) -- the stable geometry source."""
    P = _paths(city)
    for r in P["resolutions"]:
        lyr = QgsVectorLayer(f'{P["gpkg"](r)}|layername=siatka', "siatka", "ogr")
        if lyr.isValid():
            return lyr, r
    raise RuntimeError(f"no valid siatka for {city}")


def building_raster(city: str, rebuild: bool = False) -> str:
    """Path to the 10 m built/not-built raster for a city (built = burn 1).
    Cached in work/dasym/. One raster serves every resolution."""
    RASTER_DIR.mkdir(parents=True, exist_ok=True)
    out = RASTER_DIR / f"{city}_bld.tif"
    if out.exists() and not rebuild:
        return str(out)

    P = _paths(city)
    ref, _ = _siatka(city)
    crs = ref.crs()
    e = ref.extent()
    excl = ",".join(f"'{v}'" for v in sorted(EXCL_BUILDINGS))
    bld = _run("native:extractbyexpression", {
        "INPUT": f'{P["pbf"]}|layername=multipolygons',
        "EXPRESSION": f'"building" is not null and "building" not in ({excl})',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    bld_p = _run("native:reprojectlayer", {
        "INPUT": bld, "TARGET_CRS": crs, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    n = bld_p.featureCount()
    _run("gdal:rasterize", {
        "INPUT": bld_p, "BURN": 1, "UNITS": 1,
        "WIDTH": RASTER_M, "HEIGHT": RASTER_M,
        "EXTENT": (f"{e.xMinimum() - PAD_M},{e.xMaximum() + PAD_M},"
                   f"{e.yMinimum() - PAD_M},{e.yMaximum() + PAD_M}"),
        "INIT": 0, "DATA_TYPE": 0,  # Byte
        "OUTPUT": str(out),
    })
    print(f"[{city}] building raster: {n} residential-ish buildings -> {out.name}")
    return str(out)


def compute(city: str, spacing_m: int):
    """Return ({hex_id: dasymetric_pop}, {hex_id: old_pop}, stats)."""
    P = _paths(city)
    gpkg = P["gpkg"](spacing_m)
    hg = QgsVectorLayer(f"{gpkg}|layername=hex_grid", "hex_grid", "ogr")
    old = {f["hex_id"]: (f["pop_total"] or 0.0) for f in hg.getFeatures()} if hg.isValid() else {}

    rast = building_raster(city)
    obv = _run("native:extractbyexpression", {
        "INPUT": f'{P["ses"]}|layername=obwody_spisowe',
        "EXPRESSION": '"population" IS NOT NULL',
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    prec_pop = sum(f["population"] for f in obv.getFeatures())

    frag = _run("native:intersection", {
        "INPUT": f"{gpkg}|layername=siatka", "OVERLAY": obv,
        "INPUT_FIELDS": ["hex_id"], "OVERLAY_FIELDS": ["OBJECTID", "population"],
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })
    fz = _run("native:zonalstatisticsfb", {
        "INPUT": frag, "INPUT_RASTER": rast, "RASTER_BAND": 1,
        "COLUMN_PREFIX": "b_", "STATISTICS": [1],  # 1 = sum of built cells
        "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
    })

    all_ids = {f["hex_id"] for f in QgsVectorLayer(f"{gpkg}|layername=siatka", "s", "ogr").getFeatures()}
    by_prec = defaultdict(list)
    for f in fz.getFeatures():
        by_prec[f["OBJECTID"]].append(
            (f["hex_id"], f["b_sum"] or 0.0, f.geometry().area(), f["population"] or 0.0))

    new = defaultdict(float)
    fb_precs = fb_pop = 0.0
    for parts in by_prec.values():
        pop = parts[0][3]
        tb = sum(p[1] for p in parts)
        ta = sum(p[2] for p in parts)
        if tb > 0:
            for hid, b, _a, _ in parts:
                new[hid] += pop * (b / tb)
        elif ta > 0:
            fb_precs += 1
            fb_pop += pop
            for hid, _b, a, _ in parts:
                new[hid] += pop * (a / ta)
    new = {h: new.get(h, 0.0) for h in all_ids}

    new_sum = sum(new.values())
    old_ref = old or {h: 0.0 for h in all_ids}
    stats = {
        "city": city, "spacing_m": spacing_m,
        "prec_pop": prec_pop, "old_sum": sum(old_ref.values()), "new_sum": new_sum,
        "mass_diff_pct": abs(new_sum - prec_pop) / prec_pop if prec_pop else None,
        "fallback_precincts": int(fb_precs), "fallback_pop": fb_pop,
        "hex_total": len(all_ids),
        "hex_lt_minpop_old": sum(1 for v in old_ref.values() if v < MIN_POP),
        "hex_lt_minpop_new": sum(1 for v in new.values() if v < MIN_POP),
        "pop_moved": sum(abs(new[h] - old_ref.get(h, 0.0)) for h in all_ids),
        "pop_reloc_from_dropped": sum(old_ref.get(h, 0.0) for h in all_ids if new[h] < MIN_POP),
    }
    return new, old_ref, stats


def _fmt(s):
    reloc = s["pop_reloc_from_dropped"]
    return (f"[{s['city']} {s['spacing_m']}m] pop precincts={s['prec_pop']:.0f} "
            f"old_hexsum={s['old_sum']:.0f} new_hexsum={s['new_sum']:.0f} "
            f"(mass diff {s['mass_diff_pct']:.3%})\n"
            f"   fallback precincts (no resi building): {s['fallback_precincts']} "
            f"carrying {s['fallback_pop']:.0f} people\n"
            f"   hexes <{MIN_POP}p: {s['hex_lt_minpop_old']} -> {s['hex_lt_minpop_new']} "
            f"of {s['hex_total']}   pop moved between hexes: {s['pop_moved']:.0f} "
            f"({s['pop_moved'] / s['new_sum']:.1%})   "
            f"old pop in now-dropped hexes: {reloc:.0f} ({reloc / s['new_sum']:.1%}, relocated not lost)")


def report(city: str, spacing_m: int):
    new, old, s = compute(city, spacing_m)
    print(_fmt(s))
    worst = sorted(old, key=lambda h: old.get(h, 0.0) - new[h], reverse=True)[:8]
    print("   biggest drops (old -> new):")
    for h in worst:
        print(f"     hex {h}: {old.get(h, 0.0):.2f} -> {new[h]:.2f}")
    return s


def apply(city: str, spacing_m: int, min_pop: float = MIN_POP):
    new, _old, s = compute(city, spacing_m)
    print(_fmt(s))
    gpkg = _paths(city)["gpkg"](spacing_m)
    keep = {h for h, v in new.items() if v >= min_pop}
    ids = ",".join(str(h) for h in sorted(keep))
    pop_map = {h: round(new[h], 2) for h in keep}

    for src_layer, out_layer in (("siatka", "hex_grid"), ("hex_centroids", "hex_centroids")):
        kept = _run("native:extractbyexpression", {
            "INPUT": f"{gpkg}|layername={src_layer}",
            "EXPRESSION": f'"hex_id" IN ({ids})',
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        })
        if kept.fields().indexFromName("pop_total") < 0:
            kept = _run("native:fieldcalculator", {
                "INPUT": kept, "FIELD_NAME": "pop_total", "FIELD_TYPE": 0,
                "FIELD_LENGTH": 12, "FIELD_PRECISION": 2, "FORMULA": "0",
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            })
        kept.startEditing()
        idx = kept.fields().indexFromName("pop_total")
        for f in kept.getFeatures():
            kept.changeAttributeValue(f.id(), idx, pop_map[f["hex_id"]])
        kept.commitChanges()

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = out_layer
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        err = QgsVectorFileWriter.writeAsVectorFormatV3(kept, str(gpkg), kept.transformContext(), opts)
        if err[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"rewrite {out_layer} failed: {err}")

    print(f"   [ok] {gpkg.name}: {len(keep)} hexes kept (dropped {s['hex_total'] - len(keep)}), "
          f"pop_total = dasymetric footprint")
    return s


def build_rasters(rebuild: bool = False):
    import cities as C
    for city in list(C.CITIES) + ["lodz"]:
        building_raster(city, rebuild=rebuild)


def apply_all(min_pop: float = MIN_POP):
    import cities as C
    out = []
    for city in list(C.CITIES) + ["lodz"]:
        for r in _paths(city)["resolutions"]:
            out.append(apply(city, r, min_pop))
    return out
