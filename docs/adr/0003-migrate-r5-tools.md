# ADR-0003 — Move the R5/r5r tooling out of easy-OTP into Easy-R5

- **Status:** **Accepted** (2026-09-02, Michał) — scope confirmed as all four folders plus the
  workflow; not executed yet.
- **Date:** 2026-09-02
- **Detail:** [`docs/notes/tools-migration.md`](../notes/tools-migration.md)

## Context

`GISBoost/easy-OTP` currently hosts, under `tools/`, four folders and one CI workflow that have
nothing to do with OpenTripPlanner: the r5r-based accessibility studies (Łódź and 6 more cities),
the r5r isochrone sweeps feeding `mapy-analizy/izochrony-transport`, and the SES income layer they
join against. That is ~161 tracked files of R5 work living in the OTP repository.

They ended up there for a good reason — easy-OTP was the only repo at the time. With Easy-R5
existing, the split is obvious, and the two repos then have clean, explainable identities: one per
routing engine, each with its plugin plus the research tooling that uses that engine.

## Decision

Move `tools/accessibility_lodz/`, `tools/accessibility_cities/`, `tools/isochrones_lodz/`,
`tools/ses_income_lodz/` and `.github/workflows/isochrones-cities.yml` into this repo, under the
same `tools/` convention easy-OTP uses (standalone, outside the plugin, own environments, own
READMEs). Delete them from easy-OTP in a separate commit and leave a pointer.

Plain copy plus an attribution line in the import commit is enough; `git subtree split` is
documented in the notes if history must travel.

`tools/network/` stays in easy-OTP and is cross-linked, being engine-agnostic.

## Consequences

- easy-OTP's README/`tools/README.md` tables shrink and gain an `Easy-R5` row; both repos gain a
  "companion repository" line, matching how `easy-GTFS-RT` and `gtfs-dashboard` are already
  presented.
- The published blog posts and web maps (`gisboost.github.io/analizy/…`,
  `mapy-analizy/izochrony-transport`, `uczelnie-dostepnosc`) keep working — they consume outputs,
  not source paths — but their "code lives here" links need updating wherever they point at
  easy-OTP.
- The isochrones CI workflow's history of runs stays in easy-OTP; the workflow itself continues in
  Easy-R5. Re-dispatching it after the move is the migration's smoke test.
- Easy-R5 starts life with a real, working R5 pipeline and real reference results — which is
  exactly what the plugin needs to be validated against.
- Licensing: Easy-R5 is GPL-3.0-or-later like easy-OTP, so moving GPL code between them is a
  non-issue.

## Alternative considered

**Leave everything in easy-OTP and only build the plugin here.** Rejected: it keeps R5 work in the
OTP repo permanently, makes the "one repo per engine" story incoherent, and leaves the plugin
without its natural validation set.
