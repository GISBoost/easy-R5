# Prompts for Claude Code

One file per milestone, paste-ready. Same convention as
[easy-OTP's `docs/prompts/`](https://github.com/GISBoost/easy-OTP/tree/main/docs/prompts):
each prompt names the context to load, why the milestone exists, exactly what to build, the
acceptance criteria, what **not** to touch, and what Michał has to verify by hand afterwards
(the agent has no R5, no QGIS session and no data of its own).

| Prompt | Milestone | Depends on | Status |
|---|---|---|---|
| [`easy-R5_M1-skeleton-and-engine_prompt_for-claude-code.md`](easy-R5_M1-skeleton-and-engine_prompt_for-claude-code.md) | M1 — plugin skeleton, `DownloadR5`, `TestR5Setup`, runner `info` | — | ✅ implemented; ⏳ Michał's clean-profile check |
| [`easy-R5_M2-build-network_prompt_for-claude-code.md`](easy-R5_M2-build-network_prompt_for-claude-code.md) | M2 — `BuildNetwork`, cache, `service_days` | M1 | ✅ implemented; ⏳ Michał's large-PBF check |
| [`easy-R5_M3-travel-time-matrix_prompt_for-claude-code.md`](easy-R5_M3-travel-time-matrix_prompt_for-claude-code.md) | M3 — `RunTravelTimeMatrix` (flagship) | M2 | ✅ implemented + **verified end-to-end vs R5 7.6** |
| [`easy-R5_M4-accessibility_prompt_for-claude-code.md`](easy-R5_M4-accessibility_prompt_for-claude-code.md) | M4 — `RunAccessibility` + Gdańsk validation | M3 | ✅ implemented; **reproduces r5r's Gdańsk output exactly** |
| [`easy-R5_M5-isochrones-and-release_prompt_for-claude-code.md`](easy-R5_M5-isochrones-and-release_prompt_for-claude-code.md) | M5 — isochrones, hex grid, release 0.1.0 | M4 | ✅ implemented + verified in QGIS 3.40; ⏳ clean-profile pipeline |

**Status of all five: see [`../handoffs/2026-09-03_M3-M5-implementation.md`](../handoffs/2026-09-03_M3-M5-implementation.md).**
`metadata.txt` is at `0.1.0`, `experimental=True` until Michał signs off the clean-profile run.

**One milestone per session.** After each: test in QGIS → review → fix blockers → commit → clear.

All five implement [`../prd/PR_easy-R5_v01.md`](../prd/PR_easy-R5_v01.md). If a prompt and the PRD
disagree, the PRD wins and the prompt is the bug.

---

## F — eksperyment z komplementarnością modalną (Łódź) — **sparkowane, nie flagowe**

Osobna seria, niezależna od kamieni v0.1. Implementuje
[`../prd/PR_easy-R5_flagship-lodz-modal.md`](../prd/PR_easy-R5_flagship-lodz-modal.md) (v1: tram
+ bus, dwa tryby); uzasadnienie wyboru kierunku i lista odłożonych pomysłów są w
[`../notes/flagship-analysis-candidates.md`](../notes/flagship-analysis-candidates.md).

**Status (2026-09-06): to był pierwszy szukany kierunek na flagową analizę, nie ten
docelowy.** F1–F5 (poniżej) zaimplementowane i zweryfikowane technicznie — dobry przykład
dogfoodingu `TRANSIT_SUBMODES` (F1, jedyny kamień dotykający `easy_r5/`) na realnej
analizie. Ale zderzenie z literaturą 2025-2026 (`../notes/flagship-analysis-decision.md`)
pokazało, że "counterfactual mode removal" to już dość standardowa metoda — niewystarczająco
odkrywcza na hero image. Przenieśliśmy się na
[`tools/realtime_delay_lodz/`](../../tools/realtime_delay_lodz/README.md) (realne opóźnienia
GTFS-RT vs. dostępność). Seria F zostaje jako ślad tej próby i punkt do ewentualnego powrotu
(np. jako drugorzędny wątek), nie jako aktywny plan — nie kontynuować bez decyzji Michała.

> **Kolej (ŁKA) jest sparkowana.** Audyt feedu ŁKA (`../notes/lka-gtfs-audit.md`) znalazł zły
> statyczny feed pod kluczem `lka` i brak kompatybilnego źródła RT (tylko TripUpdates,
> `family_a_reconstruction` wspiera wyłącznie VehiclePositions). Decyzja i uzasadnienie:
> [`../notes/flagship-analysis-decision.md`](../notes/flagship-analysis-decision.md) (v3, 2026-09-05)
> — **wracamy do v1**: dwa tryby (tram, bus), data przebiegu **2026-08-24** (nie 2026-08-21 —
> ten wybór był uzasadniony tylko potrzebą wspólnego dnia z ŁKA, która już nie obowiązuje).
> `PR_easy-R5_flagship-lodz-modal_v2-rail.md`, `easy-R5_F2b-rail-feed_prompt_for-claude-code.md`
> i `easy-R5_F6-bad-day_prompt_for-claude-code.md`'s v2-scope są **Parked** — punkt powrotu, nie
> aktywny plan. Prompt F2 ma nieaktualny nagłówek „AKTUALIZACJA v2" odwołujący się do tej
> sparkowanej wersji — ignorować go, treść i kryteria akceptacji promptu i tak używają
> 2026-08-24.

| Prompt | Kamień | Zależy od | Status |
|---|---|---|---|
| [`easy-R5_F1-transit-submodes_prompt_for-claude-code.md`](easy-R5_F1-transit-submodes_prompt_for-claude-code.md) | F1 — parametr `TRANSIT_SUBMODES` we wtyczce | v0.1 | ✅ zaimplementowane + zweryfikowane end-to-end w QGIS (real R5 7.6) |
| [`easy-R5_F2-data-prep_prompt_for-claude-code.md`](easy-R5_F2-data-prep_prompt_for-claude-code.md) | F2 — sieć, siatka, populacja area-weighted, POI→heks, warstwa celów | F1 | ✅ zaimplementowane + zweryfikowane w QGIS (`tools/modal_complementarity_lodz/`), data **2026-08-24** |
| ~~`easy-R5_F2b-rail-feed_prompt_for-claude-code.md`~~ | ~~F2b — feed ŁKA~~ | — | **Parked** (kolej poza zakresem) |
| [`easy-R5_F3-runs-and-metrics_prompt_for-claude-code.md`](easy-R5_F3-runs-and-metrics_prompt_for-claude-code.md) | F3 — **4** przebiegi (W/T/B/TB), niezmienniki I1–I3, metryki | F2 | ✅ zaimplementowane + zweryfikowane w QGIS: I1/I2/I3 przechodzą (I3=0,308), ρ_POI=0,9886 |
| [`easy-R5_F4-cartography_prompt_for-claude-code.md`](easy-R5_F4-cartography_prompt_for-claude-code.md) | F4 — hero image + figury | F3 | 🟡 częściowo: P3 gotowy, P1/P2 zablokowane błędem renderowania QGIS 3.40.5 — `tools/modal_complementarity_lodz/README.md` §F4 |
| [`easy-R5_F5-writeup_prompt_for-claude-code.md`](easy-R5_F5-writeup_prompt_for-claude-code.md) | F5 — wyniki, README, teksty | F4 | ✅ zaimplementowane (`docs/notes/flagship-lodz-modal-results.md`, blok w `README.md`, `out/text_pl.md`) — zrobione mimo niepełnego F4 (P1/P2 brakuje), bo teksty nie zależą od samych obrazów; do potwierdzenia z Michałem |
| [`easy-R5_F6-bad-day_prompt_for-claude-code.md`](easy-R5_F6-bad-day_prompt_for-claude-code.md) | F6 *(opcjonalny)* — warstwa „zły dzień": 4 przebiegi na zrealizowanym P85 | F5 | ⏳ *(prompt ma nieaktualny nagłówek v2 z 8 przebiegami — ignorować, robimy 4, jak v1)* |

**F1 jest jedynym kamieniem, który dotyka `easy_r5/`.** F2–F6 to `tools/` i `docs/`.

**Bramka jakości w F3, zatrzymująca:** niezmienniki `I1`–`I3` (PRD §4.6) — jeżeli `transitModes`
jest ignorowane przez R5 albo `A^TB` nie jest zawsze ≥ `max(A^T, A^B)`, analiza w tej postaci
jest nieważna i trzeba się zatrzymać, a nie obchodzić problem.

**Milestone-reviewer:** przy wykonywaniu F2→F6 w jednej sesji, agent `milestone-reviewer`
odpalany jest **raz, po F6**, nie po każdym kamieniu z osobna.
