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

### `GenerateHexGrid` (PRD §4.7)
Port from easy-OTP with the same semantics. If you change anything, say why in the commit
message — the existing studies' grids must stay reproducible.

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
- `GenerateHexGrid` reproduces a grid matching the existing `gdansk_hex_origins.csv` layout.
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
