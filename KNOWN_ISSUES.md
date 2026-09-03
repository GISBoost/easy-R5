# Known issues — Easy-R5

Every entry here has a matching GitHub issue (CLAUDE.md policy).

| # | Issue | Summary | Workaround | Status |
|---|---|---|---|---|
| 1 | [#1](https://github.com/GISBoost/easy-R5/issues/1) | The Polish translation is machine-translated (local LLM) and now lags: strings added by the 0.1.x review fixes and the whole 0.2 downloader (`DownloadRealizedGtfs`, the recordings dialog) are English-only until the next `.ts` pass. | None — untranslated strings fall back to English; the plugin works in both. | Human review + re-`lupdate` planned before `experimental=False` |
| 2 | [#2](https://github.com/GISBoost/easy-R5/issues/2) | Isochrone detail is limited by `GRID_SPACING` — a coarse grid gives lumpy contours. | Lower `GRID_SPACING` (quadratic cost). | Contour quality fixed in 0.1.0 (TIN + marching-squares); resolution knob remains |

## Not bugs, but worth knowing

- **`experimental=True`** in `metadata.txt` until every M1–M5 acceptance criterion has
  passed on a clean install on Michał's machine (`DownloadR5` real download, `BuildNetwork`
  on a large PBF, the full pipeline from the QGIS dialog). M3 and M4 are agent-verified
  end-to-end; M4 reproduces r5r's Gdańsk accessibility exactly (`docs/notes/validation-gdansk.md`).
- **The travel-time matrix runs a walk-only companion pass per origin** to feed the
  walk-only detector (PRD §5.8). This roughly doubles routing wall time versus the raw
  r5r figure — a deliberate trade for the independent safety check.
- **R5 has no stable API.** The pinned version (`r5-v7.6-all.jar`) is load-bearing; a
  `network.dat` built by another R5 will not load and the runner reports
  `NETWORK_VERSION_MISMATCH`.
