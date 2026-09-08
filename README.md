# easy-R5 — GitHub Pages site

This **orphan `gh-pages` branch** is the source of `https://gisboost.github.io/easy-R5/`.
It shares no history with `main` — it holds only the static site.

Same convention as the other GISBoost static sites
([`mapy-analizy`](https://github.com/GISBoost/mapy-analizy),
[`gtfs-dashboard`](https://github.com/GISBoost/gtfs-dashboard)): vanilla HTML/CSS,
no build step, one design system (Archivo + IBM Plex, the `gtfs-dashboard` palette).

```
index.html      "How QGIS talks to R5" — PL  (gisboost.github.io/easy-R5/)
en/index.html   the same, EN               (gisboost.github.io/easy-R5/en/)
styles.css      shared stylesheet
favicon.svg     the plugin icon (easy_r5/resources/icon.svg)
```

Language switch = the `PL`/`EN` link in the top bar. Theme (light/dark) follows the
OS and can be toggled; the choice is kept in `localStorage`.

Edit the two HTML files directly on this branch and push — Pages redeploys on push
to `gh-pages`. The plugin code, ADRs and notes live on `main`.
