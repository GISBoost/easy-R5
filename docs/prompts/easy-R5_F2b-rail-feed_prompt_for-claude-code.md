# Claude Code prompt — Easy-R5 **F2b**: feed ŁKA i wspólna sieć trzymodalna

> **PARKED (2026-09-05, sesja 2).** Nie uruchamiać teraz — aktywny plan to v1 (dwa tryby,
> bez kolei). Patrz `docs/notes/flagship-analysis-decision.md` v3 i
> `docs/notes/lka-gtfs-audit.md`. Ten prompt wraca do życia razem z PRD v2-rail.

> Wklej poniżej linii do Claude Code, w repo `easy-R5`, czysty tree. Kod po angielsku,
> rozmowa po polsku. **F2 musi być zrobione i zacommitowane.** Implementuj wyłącznie F2b —
> żadnych przebiegów dostępności. Nowego brancha nie twórz.

---

## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md` — **§3 w całości**, zwłaszcza **§3.3
  (lista rzeczy do zweryfikowania)** i **§3.4 (dwie sieci)**. Ten PRD nadpisuje v1 tam, gdzie
  się różnią.
- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` §4.2 — parametry, które zostają bez zmian.
- `docs/notes/roadmap-candidates.md` — sekcja o `conveyal/r5` #1001 (rozszerzone `route_type`).
- `docs/notes/r5-engine-primer.md` §6 — dlaczego zrealizowany i statyczny feed nie mogą leżeć
  w jednym katalogu budowy.
- `easy_r5/algorithms/download_realized_gtfs.py`, `easy_r5/core/gtfs_dashboard.py` — tędy
  pobiera się nagrania; klucz miasta to **`lka`**.

## Po co ten kamień istnieje

Analiza rośnie z dwóch trybów do trzech. Kolej aglomeracyjna nie jest jeszcze w żadnym pliku
w tym repo, a jej feed jest **niezweryfikowany** — autor PRD nie mógł go pobrać. Ten kamień
sprowadza go, audytuje i dokłada do sieci. Jeżeli feed okaże się nieużywalny w R5, lepiej
dowiedzieć się teraz, przed ośmioma przebiegami, niż po narysowaniu map.

## Co zrobić

### 1. Pobrać feed statyczny ŁKA

`https://cdn.zbiorkom.live/gtfs/lodz-lka.zip` (źródło: `GISBoost/easy-GTFS-RT`,
`config/cities.json`, klucz `lka`). Zapisać do
`tools/modal_complementarity_lodz/gtfs_lka/`.

### 2. Audyt feedu — **sześć pytań z PRD §3.3, wszystkie odpowiedzieć w `README.md` folderu**

1. **`route_type`** w `routes.txt` — rozkład wartości. Jeżeli feed używa rozszerzonych typów
   (100–117) zamiast `2`, **R5 7.6 może je porzucić bez żadnego komunikatu**
   ([conveyal/r5 #1001](https://github.com/conveyal/r5/issues/1001)). Wtedy: zrobić **kopię
   feedu** z `route_type` przemapowanym na `2`, oryginał zostawić nietknięty, i opisać mapowanie
   w `README.md`. **Nie modyfikować pobranego oryginału w miejscu.**
2. **Stacje w granicach Łodzi** — ile, gdzie, i czy wszystkie leżą wewnątrz wycinka
   `lodz.osm.pbf`. Wypisać listę z nazwami i współrzędnymi.
3. **Kalendarz** — czy feed obsługuje **2026-08-21**. Jeżeli nie → przejść na **2026-08-20**
   i zgłosić to, bo zmienia datę całej analizy.
4. **Agencje** — decyzja Michała: **tylko ŁKA**. Cokolwiek innego (PolRegio, PKP IC, …)
   odfiltrować po `agency_id` i zapisać, ile kursów odpadło.
5. **Przycięcie do obszaru** — usunąć kursy, których żaden przystanek nie leży w bboxie
   (granica Łodzi + ~5 km). Przy przycinaniu kursów przechodzących zachować **monotoniczne
   `stop_sequence`** i oryginalne czasy. Zapisać, ile kursów i przystanków zostało.
6. **Liczba kursów ŁKA aktywnych 2026-08-21** — do `README.md`, obok 9 893 kursów ZDiT. Ta
   liczba sama w sobie jest wynikiem: pokazuje skalę oferty kolejowej wobec miejskiej.

### 3. Pobrać nagrania zrealizowane ŁKA (pod F6)

Algorytmem wtyczki *Setup → Download realized GTFS*
(`easyr5:downloadrealizedgtfs`), miasto **`lka`**, dzień **2026-08-21**, warianty **P50 i P85**.
Do `tools/modal_complementarity_lodz/gtfs_lka_realized/<wariant>/`.

Kontrola przed pobraniem: manifest ma dla `lka` **33 dni** (2026-08-02 → 2026-09-04), a
2026-08-21 ma status `ok` i komplet P50/P85/static. Jeżeli manifest pokazuje coś innego —
zatrzymać się i zgłosić, bo to znaczy, że dane się zmieniły od czasu pisania PRD.

### 4. Przebudować sieci

Dwa katalogi, **nigdy jeden** — zrealizowany i statyczny dzielą `trip_id`:

| katalog | GTFS |
|---|---|
| `network_static/` | ZDiT static 2026-08-21 **+ ŁKA static (po audycie)** |
| `network_p85/` | ZDiT realized P85 2026-08-21 **+ ŁKA realized P85 2026-08-21** |

`BuildNetwork` przez `processing.run("easyr5:buildnetwork", …)`, jeden `.osm.pbf`
(`lodz.osm.pbf`), folder GTFS z **dwoma** zipami.

**Bramka:** `network.json` obu sieci musi raportować niezerową liczbę aktywnych kursów na
2026-08-21, a suma powinna być **wyraźnie większa** niż 9 893 z samego ZDiT. Jeżeli jest równa
9 893, feed ŁKA nie wszedł do sieci — zatrzymać się.

### 5. Sonda routingu — **zanim ktokolwiek policzy dostępność**

Najtańszy możliwy test, że R5 faktycznie wozi pociągiem. Jedna macierz `RunTravelTimeMatrix`:

- origins: 3–5 punktów tuż przy stacjach ŁKA w Łodzi (z punktu 2 audytu),
- destinations: te same punkty,
- `MODE = TRANSIT + WALK`, `TRANSIT_SUBMODES = RAIL`, data 2026-08-21, odjazd 07:00, okno 120,
- porównanie: ten sam przebieg z `MODE = WALK`.

**Oczekiwane:** przynajmniej jedna para stacja→stacja ma czas przejazdu **istotnie krótszy**
w wariancie `RAIL` niż pieszo. Jeżeli wszystkie czasy są identyczne z pieszymi — R5 nie widzi
kursów kolejowych, najpewniej przez rozszerzone `route_type` (punkt 1 audytu). Wtedy: wrócić do
punktu 1, przemapować, przebudować sieć, powtórzyć sondę. **Nie przechodzić do F3 przed
zieloną sondą** — to jest ta sama pułapka co niezmiennik `I4` w F3, tylko wykryta 20 minut
wcześniej i za jedną setną kosztu.

Wynik sondy → `out/rail_probe.json`.

### 6. `README.md` folderu i `.gitignore`

Rozszerzyć istniejące o wszystko powyżej. Wersjonujemy kod i `README.md`, nie dane
(`gtfs_lka*/`, `network_*/`).

## Czego NIE ruszać

- `easy_r5/` — zero zmian we wtyczce. `RAIL` jest już w `_TRANSIT_MODES`, parametr z F1 wystarcza.
- Danych z F2 (siatka, populacja, warstwa celów) — **poza datą**, która zmienia się na 2026-08-21.
- Oryginalnego pobranego feedu ŁKA — poprawki idą do kopii.
- Nie licz dostępności. To F3.

## Kryteria akceptacji

- [ ] Sześć pytań audytu z PRD §3.3 ma odpowiedzi z liczbami w `README.md`.
- [ ] `network_static/network.json` i `network_p85/network.json` raportują kursy na 2026-08-21,
      a łączna liczba przewyższa 9 893.
- [ ] **Sonda routingu zielona** — istnieje para stacji szybsza koleją niż pieszo.
- [ ] Jeżeli trzeba było przemapować `route_type` — mapowanie opisane, oryginał nietknięty.
- [ ] Data całej analizy potwierdzona jako 2026-08-21 (albo świadomie przesunięta na 2026-08-20
      z uzasadnieniem).
- [ ] `flake8` czysto; skrypty odtwarzalne od zera.

## Co musi sprawdzić Michał

1. Czy lista stacji ŁKA w granicach Łodzi zgadza się z tym, co wiesz o mieście — nic nie
   brakuje, nic nie doszło z zewnątrz?
2. Czy liczba kursów ŁKA na dzień roboczy wygląda sensownie (rząd wielkości, nie sto razy za dużo)?
3. Sonda: czy para stacji, którą agent wybrał, to faktycznie relacja, którą ktoś przejechałby
   pociągiem, a nie dwa punkty na tym samym peronie?
