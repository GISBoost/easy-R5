# Claude Code prompt — Easy-R5 **M5**: isochrones, hex grid, release 0.1.0

> Paste below the line into Claude Code, in the `easy-R5` repo, clean tree. English in code,
> Polish in chat. Implement **M5 only**, then prepare the 0.1.0 release. No new branch.
> M4 must be working.

---

## Context to load first

- `docs/prd/PR_easy-R5_v01.md` — **§4.6** (isochrones), **§4.7** (hex grid), **§6 M5**,
  **§7** (QGIS plugin repository checklist), **§9** (what stays out of v0.1).
- `docs/notes/r5-engine-primer.md` §5 — why nobody contours in Java, and what r5r/r5py/Conveyal
  do instead.
- `tools/isochrones_lodz/compute_isochrones_city.R` — the `max_walk_time` cap (10.2× on GZM,
  0.0000% area change), the batching, and the deterministic isoband failure at one hour in
  Warszawa that a retry at a different batch size routed around.
- `tools/isochrones_lodz/README.md` — the decision log: why `isochrone()` per origin set the
  budget for the whole web map, and what the grid-density trade-off actually costs.
- `../easy-OTP/easy_otp/algorithms/generate_hex_grid.py` — port target for §4.7.
- `../easy-OTP/easy_otp/algorithms/generate_isochrones.py` — how easy-OTP shaped the same
  algorithm's UI; keep the parameter names recognisable where the semantics genuinely match, and
  deliberately different where they do not.

## Why this milestone exists

Isochrones are how most people first read an accessibility result, and they are the last piece
before the plugin is usable end-to-end by someone who has never heard of a travel-time matrix.
The hex grid comes along because it is the input to everything else and forcing users to install
easy-OTP just to get a grid would be absurd.

Then: ship it. A plugin that works only on the developer's machine is not v0.1.

## What to build

### `GenerateIsochrones` (PRD §4.6)
Regular destination grid in a local metric CRS (`GRID_SPACING`, default 250 m) → one-origin
matrix → travel-time raster → `gdal:contour_polygon` per cutoff. Output polygons carry
`cutoff_min`, `origin_id`, `departure_time`, `percentile`.

- `MAX_WALK_TIME` defaults to `max(CUTOFFS)` — lossless here and the single biggest speed lever.
- Contouring can fail on a fragmented surface. If GDAL errors for one cutoff, report **which**
  cutoff failed and finish the others; do not abort the whole run.
- Grid density is the cost knob and it is quadratic. Warn before generating an absurd grid, and
  reuse M3's `ESTIMATE_FIRST` machinery rather than inventing a second estimator.

### `PreparePopulationLayer` + `PopulationOverlay` (PRD §4.8–4.9)
Ports of easy-OTP's `prepare_student_layer.py` (**renamed** — it reads any GUS NSP 2021 sheet,
not just students) and `population_overlay.py`, plus `core/xlsx_reader.py`.

Two things carry over verbatim and are not up for improvement:

- **XLSX is read in a separate process.** `_elementtree.pyd` clashes with the `libxml2` that
  QGIS's GDAL/Qt stack loads; called from a `QgsTask` worker thread it is a Windows fatal
  exception (access violation in `xmlDictReference`). That is why `xlsx_reader.py` is a
  standalone CLI script.
- **`PopulationOverlay` keeps a Float field.** The QGIS reference model rounded to integers and
  lost fractional residents; easy-OTP fixed that in v0.2.

`openpyxl`: read the PRD §4.8 note first. It proposes adopting easy-OTP's single bootstrap
exception (`core/dependencies.py`, urllib wheel download). **If Michał has not confirmed it in
`CLAUDE.md`, stop and ask** — do not add a pip install against a hard constraint on your own,
and do not silently write your own XLSX parser instead.

### No hex-grid algorithm (PRD §4.7)
Deliberate: easy-OTP's `GenerateHexGrid` wraps `native:creategrid`, and duplicating a stock QGIS
algorithm is not worth a second implementation. Document the recipe in the README instead —
`native:creategrid` TYPE=4 with HSPACING/VSPACING, then `native:extractbylocation` for whole
hexes, exactly as `tools/accessibility_cities/HOWTO_MANUAL.md` step 4 describes. Do not build the
algorithm "for convenience".

### Styles
`styles/` QML for: accessibility (graduated), isochrones (categorised by cutoff), travel-time
matrix OD lines. Load them automatically on the output layers.

### Release 0.1.0
- `metadata.txt`: `version=0.1.0`, `experimental=False` **only if** every M1–M5 acceptance
  criterion passed on Michał's machine — otherwise leave it True and say so.
- Changelog in `metadata.txt`, easy-OTP style.
- Polish translation: `easy_r5.pro`, `i18n/easy_r5_pl.ts` → compiled `.qm`. `tr()` context must
  be the class name or Processing strings will not translate (easy-OTP hit exactly this bug in
  v0.5 — check its i18n prompts under `../easy-OTP/docs/prompts/`).
- `README.md`: replace the "pre-alpha" banner with real usage — install, download engine, build
  network, run an analysis, screenshot of a result.
- `KNOWN_ISSUES.md`: any issue listed **must** have a GitHub Issue (`CLAUDE.md` policy — use the
  full path to `gh.exe`, do not invent labels).
- Walk the whole §7 checklist and paste it ticked into the report.
- Build the plugin ZIP and install it on a clean profile.

## Acceptance criteria

- 15/30/45-minute isochrones from a Gdańsk point look plausible and have no rasterisation holes.
- A deliberately fragmented case (very early morning, sparse service) either produces sane
  polygons or reports which cutoff failed — never a bare GDAL traceback.
- `PreparePopulationLayer` reads a GUS NSP 2021 sheet without crashing QGIS, and matches
  easy-OTP's output on the same file.
- `PopulationOverlay` output has fractional values, not rounded integers.
- The README's hex-grid recipe reproduces `gdansk_hex_origins.csv`'s layout using stock QGIS
  algorithms only.
- Plugin ZIP installs on a clean QGIS profile and every algorithm appears in the toolbox.
- Polish UI actually switches with QGIS's locale.

## What you must NOT do

- Do not implement the service-minutes histogram metric, scenarios, itineraries or anything
  else from PRD §9 — those are v0.2+, with their own PRD.
- Do not contour in Java.
- Do not flip `experimental=False` on untested criteria.

## Report to Michał when done

1. Full path on a clean profile: install → `DownloadR5` → `BuildNetwork` → `RunAccessibility` →
   `GenerateIsochrones`, with timings.
2. Screenshots of the isochrones and the accessibility map.
3. The ticked §7 checklist.
4. What is still `experimental` and why.
