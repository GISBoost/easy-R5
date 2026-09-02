# PRDs

- **[`PR_easy-R5_v01.md`](PR_easy-R5_v01.md)** — v0.1: pobierz silnik → zbuduj sieć → macierz
  czasów → dostępność → izochrony. Milestones M1–M5 z kryteriami akceptacji i listą kontrolną
  dla człowieka. Status: Draft, gotowy do implementacji.

Konwencja jak w easy-OTP: jeden plik na zakres wersji, kryteria akceptacji pisane jako
checklista dla człowieka (agent nie uruchomi R5 ani QGIS-a użytkownika).

Zanim zaczniesz kodować z PRD, przeczytaj w tej kolejności:

1. [`../adr/0001-r5-binding.md`](../adr/0001-r5-binding.md) — Accepted; jak wołamy R5.
2. [`../notes/spike-r5-probe-2026-09-02.md`](../notes/spike-r5-probe-2026-09-02.md) — zmierzone
   fakty i działający kod wywołujący R5 (`../reference/probe/`).
3. [`../notes/r5-engine-primer.md`](../notes/r5-engine-primer.md) — mapa klas R5 i pułapki.
4. [`../notes/open-questions.md`](../notes/open-questions.md) — co wciąż nierozstrzygnięte.

Planowane kolejne PRD: v0.2 (metryka „minut obsługi" z histogramów + `CompareScenarios`),
v0.3 (scenariusze sieciowe R5).
