"""E8 -- levels, deltas, RT-coverage mask, and population-weighted summaries.

Runs inside QGIS. Depends on the four out/acc_*.csv from run_accessibility.py.

Metric per hex per category: acc_srv_<cat>_p50_c30 and _c45 (R5's own field
naming, easy_r5/algorithms/run_accessibility.py). "Total" sums across all
survivor categories at each cutoff.

Delta rule (same as realtime_delay_lodz / realtime_delay_cities, the
methodological core of the "zly dzien" comparison): delta = NULL wherever
the static baseline is 0 or NULL -- a hexagon with zero baseline access
didn't "lose nothing", it has nothing comparable. Counting it as 0 dilutes
the population-weighted mean with places the metric can't speak to.

RT-coverage mask (this map's own addition, per Michal's explicit
methodological requirement in docs/lodzkie-na-mapach-2026-metodologia.md):
a hexagon's realized-vs-static comparison is only as trustworthy as the
transit stops actually feeding it are recorded in RT. Three classes,
computed from which stops fall within walk range of each hex centroid and
whether those stops belong to an RT-recorded feed (today: ZDiT Lodz only).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config as C

GPKG = C.PRG_GPKG
CUTOFFS = [int(c) for c in C.CUTOFFS.split(",")]


def load_wide(csv_path, survivors, cutoffs):
    """R5's long CSV (id,opportunity,percentile,cutoff,accessibility) ->
    dict hex_id -> {(opportunity, cutoff): value}."""
    import csv as csv_mod

    wide = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv_mod.DictReader(f):
            hid = row["id"]
            key = (row["opportunity"], int(row["cutoff"]))
            wide.setdefault(hid, {})[key] = float(row["accessibility"])
    return wide


def compute_delta_layer(static_csv, realized_csv, hex_layer_name, survivors, out_gpkg, out_name):
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant

    static = load_wide(static_csv, survivors, CUTOFFS)
    realized = load_wide(realized_csv, survivors, CUTOFFS)

    hex_layer = QgsVectorLayer(f"{GPKG}|layername={hex_layer_name}", hex_layer_name, "ogr")
    out = processing.run("native:fixgeometries", {"INPUT": hex_layer, "OUTPUT": "memory:"})["OUTPUT"]

    fields_to_add = []
    for cat in survivors + ["total"]:
        for c in CUTOFFS:
            fields_to_add += [
                QgsField(f"delta_{cat}_c{c}", QVariant.Double, len=12, prec=2),
                QgsField(f"base0_{cat}_c{c}", QVariant.Int),
                QgsField(f"base_{cat}_c{c}", QVariant.Double, len=12, prec=2),
            ]
    fields_to_add.append(QgsField("net_delta_n", QVariant.Int))
    out.dataProvider().addAttributes(fields_to_add)
    out.updateFields()

    out.startEditing()
    idx = {f.name(): out.fields().indexOf(f.name()) for f in fields_to_add}
    missing_hex = []
    for f in out.getFeatures():
        hid = str(f["hex_id"])
        s_vals = static.get(hid)
        r_vals = realized.get(hid)
        if s_vals is None or r_vals is None:
            missing_hex.append(hid)
            continue
        for c in CUTOFFS:
            n_comparable = 0
            for cat in survivors:
                key = (f"srv_{cat}", c)
                s = s_vals.get(key)
                r = r_vals.get(key)
                base0 = s is None or s == 0.0
                out.changeAttributeValue(f.id(), idx[f"base0_{cat}_c{c}"], int(base0))
                out.changeAttributeValue(f.id(), idx[f"base_{cat}_c{c}"], s)
                if not base0 and r is not None:
                    out.changeAttributeValue(f.id(), idx[f"delta_{cat}_c{c}"], r - s)
                    n_comparable += 1
            # total = sum of raw (not delta) across categories, for the "level" map
            s_total = sum(s_vals.get((f"srv_{cat}", c), 0) or 0 for cat in survivors)
            r_total = sum(r_vals.get((f"srv_{cat}", c), 0) or 0 for cat in survivors)
            base0_total = s_total == 0
            out.changeAttributeValue(f.id(), idx[f"base0_total_c{c}"], int(base0_total))
            out.changeAttributeValue(f.id(), idx[f"base_total_c{c}"], s_total)
            if not base0_total:
                out.changeAttributeValue(f.id(), idx[f"delta_total_c{c}"], r_total - s_total)
        out.changeAttributeValue(f.id(), idx["net_delta_n"], n_comparable)
    out.commitChanges()

    if missing_hex:
        print(f"  WARNING: {len(missing_hex)} hexagons in {hex_layer_name} missing from "
              f"accessibility results (static or realized) -- check run coverage")

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = out_name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out, str(GPKG), out.transformContext(), opts)
    print(f"  wrote {out_name} ({out.featureCount()} hexagons, {len(missing_hex)} missing)")
    return out


def compute_level_layer(csv_path, hex_layer_name, survivors, out_gpkg, out_name):
    """Level-only counterpart to compute_delta_layer, for a static-GTFS-only
    pass with no realized side to compare against (voivodeship, 2026-09-14 --
    Michal: this round only takes static GTFS into account, RT swap deferred).
    Writes level_<cat>_c<cutoff> (+ level_total_c<cutoff>), no delta/base0/
    net_delta_n bookkeeping since there is nothing to compare."""
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant

    wide = load_wide(csv_path, survivors, CUTOFFS)

    hex_layer = QgsVectorLayer(f"{GPKG}|layername={hex_layer_name}", hex_layer_name, "ogr")
    out = processing.run("native:fixgeometries", {"INPUT": hex_layer, "OUTPUT": "memory:"})["OUTPUT"]

    fields_to_add = [QgsField(f"level_{cat}_c{c}", QVariant.Double, len=12, prec=2)
                      for cat in survivors + ["total"] for c in CUTOFFS]
    out.dataProvider().addAttributes(fields_to_add)
    out.updateFields()

    out.startEditing()
    idx = {f.name(): out.fields().indexOf(f.name()) for f in fields_to_add}
    missing_hex = []
    for f in out.getFeatures():
        hid = str(f["hex_id"])
        vals = wide.get(hid)
        if vals is None:
            missing_hex.append(hid)
            continue
        for c in CUTOFFS:
            total = 0.0
            for cat in survivors:
                v = vals.get((f"srv_{cat}", c), 0) or 0
                out.changeAttributeValue(f.id(), idx[f"level_{cat}_c{c}"], v)
                total += v
            out.changeAttributeValue(f.id(), idx[f"level_total_c{c}"], total)
    out.commitChanges()

    if missing_hex:
        print(f"  WARNING: {len(missing_hex)} hexagons in {hex_layer_name} missing from "
              f"accessibility results -- check run coverage")

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = out_name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out, str(GPKG), out.transformContext(), opts)
    print(f"  wrote {out_name} ({out.featureCount()} hexagons, {len(missing_hex)} missing)")
    return out


def population_weighted_level_summary(hex_layer, survivors, pop_field="pop_total"):
    rows = []
    for cat in survivors + ["total"]:
        for c in CUTOFFS:
            ws, wt, n = 0.0, 0.0, 0
            for f in hex_layer.getFeatures():
                pop = f[pop_field] or 0
                v = f[f"level_{cat}_c{c}"]
                if v is None:
                    continue
                ws += pop * v
                wt += pop
                n += 1
            mean = ws / wt if wt else None
            rows.append({"category": cat, "cutoff": c, "mean_level_pop_weighted": mean, "hexagons": n})
    return rows


def compute_threshold_sensitivity_layer(csv_path, hex_layer_name, survivors, out_gpkg, out_name,
                                          cutoffs=(30, 60)):
    """'Delta' redefined (Michal, 2026-09-14): with no RT comparison at
    voivodeship scale, this measures how much accessibility GROWS when the
    cutoff doubles (30 -> 60 min) instead of static-vs-realized. Per hex per
    category (+ total): level_<cat>_c30, level_<cat>_c60, growth_<cat>
    (c60-c30), ratio_<cat> (c60/c30, None if c30==0 -- can't compute a ratio
    from zero, and "infinite growth" is not a useful map value). A ratio near
    2.0 means accessibility scales roughly linearly with time budget in that
    area; well above 2.0 means the extra 30 min unlocks a disproportionate
    amount (e.g. reaching a denser hub); well below means diminishing
    returns (most reachable POI were already within 30 min)."""
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant

    wide = load_wide(csv_path, survivors, list(cutoffs))

    hex_layer = QgsVectorLayer(f"{GPKG}|layername={hex_layer_name}", hex_layer_name, "ogr")
    out = processing.run("native:fixgeometries", {"INPUT": hex_layer, "OUTPUT": "memory:"})["OUTPUT"]

    c_lo, c_hi = cutoffs
    cats = survivors + ["total"]
    fields_to_add = []
    for cat in cats:
        fields_to_add += [
            QgsField(f"level_{cat}_c{c_lo}", QVariant.Double, len=12, prec=2),
            QgsField(f"level_{cat}_c{c_hi}", QVariant.Double, len=12, prec=2),
            QgsField(f"growth_{cat}", QVariant.Double, len=12, prec=2),
            QgsField(f"ratio_{cat}", QVariant.Double, len=12, prec=3),
        ]
    out.dataProvider().addAttributes(fields_to_add)
    out.updateFields()

    out.startEditing()
    idx = {f.name(): out.fields().indexOf(f.name()) for f in fields_to_add}
    missing_hex = []
    for f in out.getFeatures():
        hid = str(f["hex_id"])
        vals = wide.get(hid)
        if vals is None:
            missing_hex.append(hid)
            continue
        for cat in cats:
            if cat == "total":
                lo = sum(vals.get((f"srv_{c}", c_lo), 0) or 0 for c in survivors)
                hi = sum(vals.get((f"srv_{c}", c_hi), 0) or 0 for c in survivors)
            else:
                lo = vals.get((f"srv_{cat}", c_lo), 0) or 0
                hi = vals.get((f"srv_{cat}", c_hi), 0) or 0
            out.changeAttributeValue(f.id(), idx[f"level_{cat}_c{c_lo}"], lo)
            out.changeAttributeValue(f.id(), idx[f"level_{cat}_c{c_hi}"], hi)
            out.changeAttributeValue(f.id(), idx[f"growth_{cat}"], hi - lo)
            out.changeAttributeValue(f.id(), idx[f"ratio_{cat}"], (hi / lo) if lo else None)
    out.commitChanges()

    if missing_hex:
        print(f"  WARNING: {len(missing_hex)} hexagons in {hex_layer_name} missing from "
              f"accessibility results -- check run coverage")

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = out_name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out, str(GPKG), out.transformContext(), opts)
    print(f"  wrote {out_name} ({out.featureCount()} hexagons, {len(missing_hex)} missing)")
    return out


def _null_to_none(v):
    """PyQGIS feature[field] can return an invalid QVariant instead of
    Python None for a NULL numeric field (seen here for ratio_<cat>, which
    is legitimately NULL whenever c30==0) -- normalize both to None."""
    if v is None:
        return None
    if hasattr(v, "isNull") and v.isNull():
        return None
    return v


def population_weighted_threshold_summary(hex_layer, survivors, pop_field="pop_total"):
    """Pop-weighted mean ratio (c60/c30, only hexagons with c30>0 -- matches
    the 'can't compute a ratio from zero' rule above) and mean growth
    (c60-c30, all hexagons with data), per category + total. This is the
    number that answers Michal's question directly: does accessibility
    roughly double when the time budget doubles?"""
    rows = []
    for cat in survivors + ["total"]:
        ws_ratio = wt_ratio = 0.0
        n_ratio = 0
        ws_growth = wt_growth = 0.0
        n_growth = 0
        n_emerged = 0       # c30 == 0, c60 > 0 -- "unlocked" by the wider budget
        n_still_zero = 0    # c30 == 0 AND c60 == 0 -- genuinely unreachable either way
        pop_lo_sum = pop_hi_sum = 0.0  # for the ratio-of-sums (outlier-robust) statistic
        for f in hex_layer.getFeatures():
            pop = f[pop_field] or 0
            ratio = _null_to_none(f[f"ratio_{cat}"])
            growth = _null_to_none(f[f"growth_{cat}"])
            lo = _null_to_none(f[f"level_{cat}_c30"])
            hi = _null_to_none(f[f"level_{cat}_c60"])
            if ratio is not None:
                ws_ratio += pop * ratio
                wt_ratio += pop
                n_ratio += 1
            elif lo == 0:
                if hi and hi > 0:
                    n_emerged += 1
                else:
                    n_still_zero += 1
            if growth is not None:
                ws_growth += pop * growth
                wt_growth += pop
                n_growth += 1
            if lo is not None and hi is not None:
                pop_lo_sum += pop * lo
                pop_hi_sum += pop * hi
        rows.append({
            "category": cat,
            # mean of per-hex ratios (only hexes with c30>0) -- sensitive to
            # hexes with a tiny denominator (c30=1 -> c60=9 counts as much as
            # c30=100 -> c60=200), so also report...
            "mean_ratio_c60_c30_pop_weighted": (ws_ratio / wt_ratio) if wt_ratio else None,
            # ...ratio of population-weighted SUMS -- one aggregate number,
            # not an average of per-hex ratios, much less swayed by a few
            # near-zero-denominator hexes. This is the more honest answer to
            # "does it roughly double overall".
            "ratio_of_pop_weighted_sums": (pop_hi_sum / pop_lo_sum) if pop_lo_sum else None,
            "mean_growth_c60_c30_pop_weighted": (ws_growth / wt_growth) if wt_growth else None,
            "hexagons_with_c30_access": n_ratio,
            "hexagons_emerged_c30_zero_c60_positive": n_emerged,
            "hexagons_still_zero_at_c60": n_still_zero,
        })
    return rows


def main_woj_threshold_sensitivity():
    from qgis.core import QgsVectorLayer
    dest = QgsVectorLayer(f"{GPKG}|layername=poi_targets_woj", "d", "ogr")
    survivors = [f.name()[4:] for f in dest.fields() if f.name().startswith("srv_")]

    layer = compute_threshold_sensitivity_layer(
        C.OUT / "acc_A1_woj_static_thresholds.csv", "hex_woj_pop", survivors, GPKG,
        "hex_woj_thresholds",
    )
    summary = population_weighted_threshold_summary(layer, survivors)
    import csv
    with open(C.OUT / "woj_threshold_summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print("wrote out/woj_threshold_summary.csv")
    for r in summary:
        print(f"  {r['category']:20s} ratio={r['mean_ratio_c60_c30_pop_weighted']}"
              f"  growth={r['mean_growth_c60_c30_pop_weighted']}")
    return layer, summary


def main_woj_level():
    """Voivodeship, static-GTFS-only pass (2026-09-14): level from A1 alone,
    no A2/RT delta this round (Michal's explicit scope decision). Writes
    hex_woj_level (does not touch hex_woj_delta, which is stale from before
    the large-park fix and out of scope here -- see HANDOFF.md open Q#4)."""
    from qgis.core import QgsVectorLayer
    dest = QgsVectorLayer(f"{GPKG}|layername=poi_targets_woj", "d", "ogr")
    survivors = [f.name()[4:] for f in dest.fields() if f.name().startswith("srv_")]
    print(f"categories: {survivors}")

    level = compute_level_layer(
        C.OUT / "acc_A1_woj_static.csv", "hex_woj_pop", survivors, GPKG, "hex_woj_level",
    )
    summary = population_weighted_level_summary(level, survivors)
    import csv
    with open(C.OUT / "woj_level_summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print("wrote out/woj_level_summary.csv")
    return {"level": level, "summary": summary}


def population_weighted_summary(hex_layer, survivors, pop_field="pop_total"):
    """Sigma(pop * delta) / Sigma(pop), comparable hexagons only, per
    category per cutoff -- same formula throughout tools/realtime_delay_*."""
    rows = []
    for cat in survivors + ["total"]:
        for c in CUTOFFS:
            ws, wt, n_comp, n_zero = 0.0, 0.0, 0, 0
            for f in hex_layer.getFeatures():
                pop = f[pop_field] or 0
                base0 = f[f"base0_{cat}_c{c}"]
                delta = f[f"delta_{cat}_c{c}"]
                if base0:
                    n_zero += 1
                    continue
                if delta is None:
                    continue
                ws += pop * delta
                wt += pop
                n_comp += 1
            mean = ws / wt if wt else None
            rows.append({"category": cat, "cutoff": c, "mean_delta_pop_weighted": mean,
                         "hexagons_comparable": n_comp, "hexagons_zero_baseline": n_zero})
    return rows


WALK_RADIUS_M = 800  # standard walk-to-transit catchment (~13 min at 3.6 km/h)


def rt_coverage_mask(hex_layer_name, feed_keys, rt_feed_keys, out_gpkg, out_name):
    """Three classes per hex, walk-buffer join against GTFS stops (pattern
    from inventory_gtfs.build_stop_points_layer): 'RT pelne' (every stop
    within WALK_RADIUS_M belongs to an RT-recorded feed), 'RT czesciowe'
    (mixed), 'brak danych o realizacji' (no reachable stop is RT-recorded --
    covers both 'has non-RT stops only' and 'has no stops at all'). This is
    docs/lodzkie-na-mapach-2026-metodologia.md's explicit methodological
    requirement: a hexagon with no RT coverage must be marked as missing
    data, never silently treated as net_delta=0.

    Today only ZDiT Lodz ('lodz') is RT-recorded (see config.GTFS_FEEDS)."""
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).parent))
    import inventory_gtfs
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant

    # Reuse E1's downloader (skip-if-exists) + stop parser for exactly the
    # feeds actually in THIS network -- not the full GTFS_FEEDS dict.
    all_stats = {}
    for key in feed_keys:
        spec = C.GTFS_FEEDS[key]
        path = inventory_gtfs.download_feed(key, spec)
        all_stats[key] = inventory_gtfs.feed_stats(key, spec, path, C.ANALYSIS_DATE)
    stops_layer = inventory_gtfs.build_stop_points_layer(all_stats)

    # walk-radius buffer around hex centroids, in the metric CRS
    hex_layer = QgsVectorLayer(f"{GPKG}|layername={hex_layer_name}", "hex", "ogr")
    centroids = processing.run("native:centroids", {"INPUT": hex_layer, "ALL_PARTS": False, "OUTPUT": "memory:"})["OUTPUT"]
    buffers = processing.run("native:buffer", {
        "INPUT": centroids, "DISTANCE": WALK_RADIUS_M, "SEGMENTS": 8, "DISSOLVE": False, "OUTPUT": "memory:",
    })["OUTPUT"]

    stops_reproj = processing.run("native:reprojectlayer", {
        "INPUT": stops_layer, "TARGET_CRS": hex_layer.crs(), "OUTPUT": "memory:",
    })["OUTPUT"]

    joined = processing.run("native:joinattributesbylocation", {
        "INPUT": buffers, "PREDICATE": [0], "JOIN": stops_reproj,
        "JOIN_FIELDS": ["feed_key"], "METHOD": 0,  # one-to-many: a separate output feature per matching stop (checked via get_algorithm_help -- METHOD=1 is "first match only", which would have silently capped every hex at 1 stop)
        "DISCARD_NONMATCHING": False, "OUTPUT": "memory:",
    })["OUTPUT"]

    from collections import defaultdict
    n_total = defaultdict(int)
    n_rt = defaultdict(int)
    for f in joined.getFeatures():
        hid = f["hex_id"]
        fk = f["feed_key"]
        if fk is None:
            continue
        n_total[hid] += 1
        if fk in rt_feed_keys:
            n_rt[hid] += 1

    out = processing.run("native:fixgeometries", {"INPUT": hex_layer, "OUTPUT": "memory:"})["OUTPUT"]
    out.dataProvider().addAttributes([
        QgsField("n_stops_walkrange", QVariant.Int),
        QgsField("n_rt_stops_walkrange", QVariant.Int),
        QgsField("rt_coverage_class", QVariant.String),
    ])
    out.updateFields()
    out.startEditing()
    idx_tot = out.fields().indexOf("n_stops_walkrange")
    idx_rt = out.fields().indexOf("n_rt_stops_walkrange")
    idx_cls = out.fields().indexOf("rt_coverage_class")
    class_counts = defaultdict(int)
    for f in out.getFeatures():
        hid = f["hex_id"]
        tot = n_total.get(hid, 0)
        rt = n_rt.get(hid, 0)
        if rt == 0:
            cls = "brak danych o realizacji"
        elif rt == tot:
            cls = "RT pelne"
        else:
            cls = "RT czesciowe"
        class_counts[cls] += 1
        out.changeAttributeValue(f.id(), idx_tot, tot)
        out.changeAttributeValue(f.id(), idx_rt, rt)
        out.changeAttributeValue(f.id(), idx_cls, cls)
    out.commitChanges()
    print(f"  rt_coverage_mask ({hex_layer_name}): {dict(class_counts)}")

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = out_name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out, str(out_gpkg), out.transformContext(), opts)
    print(f"  wrote {out_name}")
    return out


def drop_fields(gpkg, layer_name, suffix):
    """Cartography-layer trim: remove attribute columns ending in `suffix`
    (e.g. "_c45") from an already-written layer. The underlying R5 CSVs and
    population_weighted_summary() output keep every cutoff -- this only
    thins the QGIS attribute table for readability (Michal, 2026-09-13:
    hex_lodz_delta had 10 categories x 2 cutoffs x 3 fields, too much to
    read in the attribute table)."""
    from qgis.core import QgsVectorLayer
    lyr = QgsVectorLayer(f"{gpkg}|layername={layer_name}", layer_name, "ogr")
    to_drop = [f.name() for f in lyr.fields() if f.name().endswith(suffix)]
    idxs = [lyr.fields().indexOf(n) for n in to_drop]
    lyr.startEditing()
    lyr.dataProvider().deleteAttributes(idxs)
    lyr.updateFields()
    lyr.commitChanges()
    print(f"  dropped {len(to_drop)} fields ending in '{suffix}' from {layer_name}")


MULTIDAY_DAYS = ["2026-09-08", "2026-09-09", "2026-09-10"]
# Historical note: an earlier pass here pointed at _merged21.csv files, a
# workaround for easy-R5 issue #5 (destinations-field corruption from a stale
# cached QGIS layer). Root-caused and fixed (points.py, commit 25d9825) --
# the runs below go straight against the full 21-category poi_targets_lodz,
# no merge step needed.
MULTIDAY_CSVS = {
    "2026-09-08": "acc_A3b_lodz_p50_2026-09-08.csv",
    "2026-09-09": "acc_A3b_lodz_p50_2026-09-09.csv",
    "2026-09-10": "acc_A3b_lodz_p50.csv",
}


def _day_delta_layer(day_static, day_realized, hex_layer_name, survivors, cutoff, out_gpkg, out_name):
    """Per-hex avg_delta_<cat>_c<cutoff> / spread_<cat>_c<cutoff> /
    base0_<cat>_c<cutoff> across multiple independent realized-vs-static day
    comparisons. day_static/day_realized: dict day -> wide (load_wide
    output), one entry per day being averaged. Delta for a given day is NULL
    wherever THAT day's static value is 0/NULL (same rule as
    compute_delta_layer, applied per day since day_static can differ day to
    day -- see compute_vacation_delta_layer, where two different service_ids
    are active across the 4 days). base0 is True only if every day's static
    was 0/NULL for that hex/category. Shared by compute_multiday_lodz_delta
    (one static schedule reused for every day -> day_static maps every day
    to the SAME wide dict, so this reduces to the single-baseline case) and
    compute_vacation_delta_layer (a different static baseline per day)."""
    import processing
    from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsField
    from qgis.PyQt.QtCore import QVariant

    def value(wide, hid, cat):
        """Single category -> its own srv_<cat> field. "total" has no field
        of its own in R5's output -- it's the sum across every category,
        same convention as compute_delta_layer()'s base_total/delta_total."""
        vals = wide.get(hid)
        if not vals:
            return None
        if cat == "total":
            return sum(vals.get((f"srv_{c}", cutoff), 0) or 0 for c in survivors)
        return vals.get((f"srv_{cat}", cutoff))

    hex_layer = QgsVectorLayer(f"{GPKG}|layername={hex_layer_name}", "hex", "ogr")
    out = processing.run("native:fixgeometries", {"INPUT": hex_layer, "OUTPUT": "memory:"})["OUTPUT"]

    days = list(day_static)
    cats = survivors + ["total"]
    fields_to_add = []
    for cat in cats:
        fields_to_add += [
            QgsField(f"avg_delta_{cat}_c{cutoff}", QVariant.Double, len=12, prec=2),
            QgsField(f"spread_{cat}_c{cutoff}", QVariant.Double, len=12, prec=2),
            QgsField(f"base0_{cat}_c{cutoff}", QVariant.Int),
        ]
    out.dataProvider().addAttributes(fields_to_add)
    out.updateFields()

    idx = {f.name(): out.fields().indexOf(f.name()) for f in fields_to_add}
    out.startEditing()
    for f in out.getFeatures():
        hid = str(f["hex_id"])
        for cat in cats:
            day_deltas = []
            base0 = True
            for day in days:
                s = value(day_static[day], hid, cat)
                if s is None or s == 0.0:
                    continue
                base0 = False
                r = value(day_realized[day], hid, cat)
                if r is not None:
                    day_deltas.append(r - s)
            out.changeAttributeValue(f.id(), idx[f"base0_{cat}_c{cutoff}"], int(base0))
            if day_deltas:
                out.changeAttributeValue(f.id(), idx[f"avg_delta_{cat}_c{cutoff}"], sum(day_deltas) / len(day_deltas))
                out.changeAttributeValue(f.id(), idx[f"spread_{cat}_c{cutoff}"], max(day_deltas) - min(day_deltas))
    out.commitChanges()

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = out_name
    opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(out, str(out_gpkg), out.transformContext(), opts)
    print(f"  wrote {out_name} ({out.featureCount()} hexagons)")
    return out


def compute_multiday_lodz_delta(survivors, out_gpkg, out_name="hex_lodz_delta_multiday"):
    """3-day robustness check (MULTIDAY_LODZ_NOTES.md): static side is ONE
    run (net_lodz_static schedule confirmed identical across all 3 days, see
    notes), realized side is 3 independent day-runs. Spatial layer written
    by the shared _day_delta_layer() helper -- avg_delta = mean of whichever
    days are non-null (comparability doesn't vary by day since static is
    shared, so this is normally all-3-or-none) and spread = max-min across
    days, a cheap day-to-day consistency signal. Attribute table kept to
    30 min only (Michal, 2026-09-13: single-day 21-category table was
    already too wide; a 3-day version needs it even more) -- full 45 min
    detail lives in the per-day CSV summary this also writes."""
    import csv as csv_mod

    static = load_wide(C.OUT / "acc_A3a_lodz_static.csv", survivors, CUTOFFS)
    realized_by_day = {
        day: load_wide(C.OUT / fname, survivors, CUTOFFS)
        for day, fname in MULTIDAY_CSVS.items()
    }

    def value(wide, hid, cat, cutoff):
        vals = wide.get(hid)
        if not vals:
            return None
        if cat == "total":
            return sum(vals.get((f"srv_{c}", cutoff), 0) or 0 for c in survivors)
        return vals.get((f"srv_{cat}", cutoff))

    day_static = {day: static for day in MULTIDAY_DAYS}  # one shared static baseline
    out = _day_delta_layer(day_static, realized_by_day, "hex_lodz_pop", survivors, 30, out_gpkg, out_name)

    # Per-day + averaged population-weighted summary (both cutoffs, full detail --
    # this is a CSV, not the attribute table, so no column-count pressure).
    cats = survivors + ["total"]
    pop_field = "pop_total"
    summary_rows = []
    for cat in cats:
        for c in CUTOFFS:
            per_day_means = {}
            for day in MULTIDAY_DAYS:
                ws, wt, n_comp, n_zero = 0.0, 0.0, 0, 0
                for f in out.getFeatures():
                    pop = f[pop_field] or 0
                    hid = str(f["hex_id"])
                    s = value(static, hid, cat, c)
                    if s is None or s == 0.0:
                        n_zero += 1
                        continue
                    r = value(realized_by_day[day], hid, cat, c)
                    if r is None:
                        continue
                    ws += pop * (r - s)
                    wt += pop
                    n_comp += 1
                mean = ws / wt if wt else None
                per_day_means[day] = mean
                summary_rows.append({"category": cat, "cutoff": c, "day": day,
                                      "mean_delta_pop_weighted": mean,
                                      "hexagons_comparable": n_comp, "hexagons_zero_baseline": n_zero})
            valid = [v for v in per_day_means.values() if v is not None]
            avg3 = sum(valid) / len(valid) if valid else None
            summary_rows.append({"category": cat, "cutoff": c, "day": "avg_3day",
                                  "mean_delta_pop_weighted": avg3,
                                  "hexagons_comparable": "", "hexagons_zero_baseline": ""})

    with open(C.OUT / "lodz_delta_summary_multiday.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv_mod.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)
    print("  wrote out/lodz_delta_summary_multiday.csv")
    return out, summary_rows


# Vacation-vs-school-term check (Michal, 2026-09-14): same question as the
# Sept multiday robustness check ("is the uniform negative delta real?"),
# asked the other way ("is it a September/return-to-school thing, or does
# Lodz do this in August too?"). Unlike Sept, one fixed static baseline does
# NOT cover every day here -- 2026-08-13/14 (Wed/Thu) run service_id
# "11484_11", 2026-08-17/18 (Mon/Tue) run "11489_11" (confirmed distinct via
# validate_gtfs.active_service_ids) -- so each day is paired with its own
# correct static CSV below, not one shared file.
VACATION_DAY_STATIC = {
    "2026-08-13": "acc_A3a_lodz_static_2026-08-13.csv",
    "2026-08-14": "acc_A3a_lodz_static_2026-08-13.csv",  # same service_id as 08-13
    "2026-08-17": "acc_A3a_lodz_static_2026-08-17.csv",
    "2026-08-18": "acc_A3a_lodz_static_2026-08-17.csv",  # same service_id as 08-17
}
VACATION_DAY_REALIZED = {
    "2026-08-13": "acc_A3b_lodz_p50_2026-08-13.csv",
    "2026-08-14": "acc_A3b_lodz_p50_2026-08-14.csv",
    "2026-08-17": "acc_A3b_lodz_p50_2026-08-17.csv",
    "2026-08-18": "acc_A3b_lodz_p50_2026-08-18.csv",
}


def compute_vacation_vs_term_delta(survivors, cutoff=30):
    """Same rule as compute_multiday_lodz_delta (delta = NULL if static
    baseline is 0/NULL, mean population-weighted per category), applied to
    4 independent August weekdays instead of 3 September ones. Each day
    loads its OWN static CSV (see VACATION_DAY_STATIC) -- deliberately not
    reusing compute_multiday_lodz_delta, which hardcodes one shared static
    side. Writes out/lodz_delta_summary_vacation.csv, same shape as the
    Sept multiday summary so the two are directly comparable."""
    import csv as csv_mod
    from qgis.core import QgsVectorLayer

    static_wide = {
        day: load_wide(C.OUT / fname, survivors, [cutoff])
        for day, fname in VACATION_DAY_STATIC.items()
    }
    realized_wide = {
        day: load_wide(C.OUT / fname, survivors, [cutoff])
        for day, fname in VACATION_DAY_REALIZED.items()
    }

    def value(wide, hid, cat):
        vals = wide.get(hid)
        if not vals:
            return None
        if cat == "total":
            return sum(vals.get((f"srv_{c}", cutoff), 0) or 0 for c in survivors)
        return vals.get((f"srv_{cat}", cutoff))

    pop_lyr = QgsVectorLayer(f"{GPKG}|layername=hex_lodz_pop", "h", "ogr")
    pop = {str(f["hex_id"]): (f["pop_total"] or 0) for f in pop_lyr.getFeatures()}
    hex_ids = list(pop)

    days = list(VACATION_DAY_STATIC)
    cats = survivors + ["total"]
    summary_rows = []
    for cat in cats:
        per_day_means = {}
        for day in days:
            s_wide = static_wide[day]
            r_wide = realized_wide[day]
            ws = wt = 0.0
            n_comp = n_zero = 0
            for hid in hex_ids:
                p = pop[hid]
                s = value(s_wide, hid, cat)
                if s is None or s == 0.0:
                    n_zero += 1
                    continue
                r = value(r_wide, hid, cat)
                if r is None:
                    continue
                ws += p * (r - s)
                wt += p
                n_comp += 1
            mean = ws / wt if wt else None
            per_day_means[day] = mean
            summary_rows.append({"category": cat, "cutoff": cutoff, "day": day,
                                  "mean_delta_pop_weighted": mean,
                                  "hexagons_comparable": n_comp, "hexagons_zero_baseline": n_zero})
        valid = [v for v in per_day_means.values() if v is not None]
        avg4 = sum(valid) / len(valid) if valid else None
        summary_rows.append({"category": cat, "cutoff": cutoff, "day": "avg_4day",
                              "mean_delta_pop_weighted": avg4,
                              "hexagons_comparable": "", "hexagons_zero_baseline": ""})

    with open(C.OUT / "lodz_delta_summary_vacation.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv_mod.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)
    print("  wrote out/lodz_delta_summary_vacation.csv")
    return summary_rows


def compute_vacation_delta_layer(survivors, out_gpkg=None, out_name="hex_lodz_delta_vacation", cutoff=30):
    """Spatial counterpart to compute_vacation_vs_term_delta() above, which
    only wrote a CSV (Michal, 2026-09-14: the wakacje-vs-rok-szkolny
    comparison goes on the map too, for E11, not only in report text).
    Reuses _day_delta_layer() -- unlike compute_multiday_lodz_delta, each of
    the 4 August days gets its OWN static baseline (VACATION_DAY_STATIC:
    08-13/14 and 08-17/18 run different active service_id, confirmed via
    validate_gtfs.active_service_ids, see MULTIDAY_LODZ_NOTES.md), so
    day_static is NOT one shared dict repeated per day."""
    out_gpkg = out_gpkg or GPKG
    day_static = {day: load_wide(C.OUT / fname, survivors, [cutoff])
                  for day, fname in VACATION_DAY_STATIC.items()}
    day_realized = {day: load_wide(C.OUT / fname, survivors, [cutoff])
                     for day, fname in VACATION_DAY_REALIZED.items()}
    return _day_delta_layer(day_static, day_realized, "hex_lodz_pop", survivors, cutoff, out_gpkg, out_name)


def main():
    print("=== E8: Lodz static vs P50 delta ===")
    # survivors populated from prepare_poi's decision (E4) -- read the field
    # list off poi_targets_lodz rather than re-deciding here.
    from qgis.core import QgsVectorLayer
    dest = QgsVectorLayer(f"{GPKG}|layername=poi_targets_lodz", "d", "ogr")
    survivors = [f.name()[4:] for f in dest.fields() if f.name().startswith("srv_")]
    print(f"categories: {survivors}")

    lodz_delta = compute_delta_layer(
        C.OUT / "acc_A3a_lodz_static.csv", C.OUT / "acc_A3b_lodz_p50.csv",
        "hex_lodz_pop", survivors, GPKG, "hex_lodz_delta",
    )
    summary = population_weighted_summary(lodz_delta, survivors)
    import csv
    with open(C.OUT / "lodz_delta_summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print("wrote out/lodz_delta_summary.csv")

    # Lodz-only cartography trim (Michal, 2026-09-13) -- keep only the 30 min
    # cutoff in the QGIS attribute table; woj layer is untouched, and
    # lodz_delta_summary.csv above still has both cutoffs.
    drop_fields(GPKG, "hex_lodz_delta", "_c45")

    print("\n=== E8: voivodeship static vs Lodz-RT-swapped delta ===")
    dest_woj = QgsVectorLayer(f"{GPKG}|layername=poi_targets_woj", "d2", "ogr")
    survivors_woj = [f.name()[4:] for f in dest_woj.fields() if f.name().startswith("srv_")]
    woj_delta = compute_delta_layer(
        C.OUT / "acc_A1_woj_static.csv", C.OUT / "acc_A2_woj_lodzrt.csv",
        "hex_woj_pop", survivors_woj, GPKG, "hex_woj_delta",
    )
    summary_woj = population_weighted_summary(woj_delta, survivors_woj)
    with open(C.OUT / "woj_delta_summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary_woj[0].keys()))
        w.writeheader()
        w.writerows(summary_woj)
    print("wrote out/woj_delta_summary.csv")

    print("\n=== E8: RT coverage mask (methodology requirement) ===")
    rt_feed_keys = {"lodz"}  # only ZDiT Lodz is RT-recorded today (config.py)
    lodz_feeds = ["lodz", "lka_train"]
    woj_feeds = ["lodz", "lka_bus", "lka_train", "kutno", "opoczno_mpk",
                 "opoczno_pks", "rozprza", "tomaszow_mazowiecki"]
    rt_mask_lodz = rt_coverage_mask("hex_lodz_pop", lodz_feeds, rt_feed_keys, GPKG, "hex_lodz_rt_mask")
    rt_mask_woj = rt_coverage_mask("hex_woj_pop", woj_feeds, rt_feed_keys, GPKG, "hex_woj_rt_mask")

    return {"lodz_delta": lodz_delta, "woj_delta": woj_delta,
            "lodz_summary": summary, "woj_summary": summary_woj,
            "rt_mask_lodz": rt_mask_lodz, "rt_mask_woj": rt_mask_woj}


if __name__ == "__main__":
    main()
