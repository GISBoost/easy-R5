# PRD — Easy-R5 v0.3 · scenariusze, porównanie, kontrola GTFS, równość, 2SFCA

**Status:** ✅ zaimplementowane, 2026-09-17. `metadata.txt` `0.3.0`. Każda sekcja zweryfikowana
przez QGIS MCP na sieci łódzkiej (`tools/f1_smoke_test_lodz`): CheckTransitData na realnym GTFS,
scenariusz z narysowaną linią tramwajową (para 953→587: 63 → 14 min), porównanie dostępności
przed/po, 2SFCA zgodne z niezależnym przeliczeniem z macierzy, podsumowanie równościowe zgodne
z ręcznym. 254 testy pytest zielone, flake8 czysto.
**Data:** 2026-09-17
**Autor:** Michał Kaczorowski
**Kontekst wymagany do pracy:** ten plik + `CLAUDE.md` + `CONTEXT.md` +
`docs/notes/roadmap-candidates.md` (T1-B, T1-C, T2-E, T2-F, T2-G) +
`docs/notes/r5-engine-primer.md` + `docs/prd/PR_easy-R5_v02_service-minutes.md` (wzorzec
rozszerzania komendy `matrix`).

> Ten PRD obejmuje **pięć** pozycji z `roadmap-candidates.md`, wybranych 2026-09-17 jako
> największy wpływ na użytkownika i funkcje unikalne w ekosystemie QGIS. Każda sekcja R-X
> jest samodzielna. Kolejność implementacji: R-3 → R-1 → R-2 → R-5 → R-4.

---

## 0. Po co to jest i dlaczego te pięć

| # | Funkcja | Pytanie użytkownika | Dlaczego unikalne |
|---|---|---|---|
| R-1 | `BuildScenario` + parametr `SCENARIO` | „co jeśli puścimy tu tramwaj / zlikwidujemy linię 86 / autobusy pojadą wolniej?” | OTP 1.5 tego nie umie wcale. R5 stosuje modyfikacje **w pamięci, bez przebudowy sieci**. Jedyna wtyczka QGIS z podobną funkcją (Accessibility Calculator) edytuje pliki GTFS i przelicza wszystko od nowa. |
| R-2 | `CompareScenarios` | „która dzielnica straciła po zmianie rozkładu?” | Bez tego scenariusz daje dwie mapy, które trzeba porównywać wzrokiem. |
| R-3 | `CheckTransitData` | „czy ten GTFS w ogóle nadaje się do analizy na 24 sierpnia?” | Łapie najgorszy incydent projektu (cichy walk-only, GZM 08.2026) **zanim** ktoś zbuduje sieć. |
| R-4 | `SummarizeAccessibilityEquity` | „ilu mieszkańców dociera do szpitala w 30 min?” | Pytanie głównej persony (`product-scope.md`) i drugi wymiar ubóstwa transportowego z Zalecenia Komisji (UE) 2025/1021. Dziś kończy się w arkuszu. |
| R-5 | `RunCompetitiveAccessibility` (2SFCA) | „ile lekarzy przypada na mieszkańca, licząc konkurencję o te same przychodnie?” | Standard w literaturze zdrowia/edukacji; w QGIS brak implementacji transportowej (tylko ArcGIS/R/Python). |

**Poza zakresem całego v0.3:** `DownloadTransitData`, natywna powierzchnia R5
`TRAVEL_TIME_SURFACE`, taryfy, wysokości, tłumaczenia PL nowych stringów (issue #1).

---

## R-1. Scenariusze sieci — `BuildScenario` + parametr `SCENARIO`

### R-1.1 Fakty z silnika (zweryfikowane 2026-09-17)

`javap` na `r5-v7.6-all.jar` + spike na sieci łódzkiej (`tools/f1_smoke_test_lodz`,
855 wzorców, 138 tras):

- `Scenario{id, modifications}`; `scenario.applyToTransportNetwork(network)` zwraca kopię sieci
  (spike: **1,5 s**) — `TravelTimeComputer` sam scenariusza nie stosuje, liczy na sieci, którą
  dostanie.
- JSON modyfikacji: Jackson z `type` (`add-trips`, `remove-trips`, `adjust-speed`,
  `adjust-frequency`, …). **Trzeba `JsonUtilities.lenientObjectMapper`** — zwykły mapper odrzuca
  pole `type` (`UnrecognizedPropertyException`).
- Id tras i kursów w sieci mają prefiks feedu: `lodz_static_gtfs_2026-08-21:1`,
  `lodz_static_gtfs_2026-08-21:11493_1`. `RouteInfo.route_id` jest bez prefiksu (`1`),
  `route_short_name` = `1`. `TripPattern.routeId` ma prefiks, `routeIndex` wskazuje `RouteInfo`.
- `add-trips`: przystanek nowy = `StopSpec` **z samymi `lat`/`lon`** (podanie `id`/`name` razem
  ze współrzędnymi to błąd „A reference to an existing id should not include coordinates”).
  `frequencies[]` = `PatternTimetable{hopTimes[n-1], dwellTimes[n], headwaySecs, startTime,
  endTime, monday..sunday, entryId}`. `mode` = GTFS `route_type`.
- `adjust-frequency{route, entries[{sourceTrip, headwaySecs, startTime, endTime, dni, entryId}],
  retainTripsOutsideFrequencyEntries}` — kopiuje czasy przejazdu z `sourceTrip`.
- Błędy modyfikacji lądują w `modification.errors`, a `applyToTransportNetwork` rzuca
  `ScenarioApplicationException`.
- Spike: remove-trips + adjust-speed (×0,5, „Changed speed on 1089 trips”) + adjust-frequency
  (5 min) + add-trips (2 przystanki, dwukierunkowo) — wszystko bez błędów.

### R-1.2 Decyzje

1. **Nie nowa komenda Javy i nie nowy algorytm analizy.** Opcjonalny pole job-speca
   `scenario` w komendzie `matrix` i opcjonalny, zaawansowany parametr `SCENARIO` w
   `MatrixBase`. Dzięki temu scenariusz działa od razu w `RunTravelTimeMatrix`,
   `RunAccessibility`, `RunServiceMinutes`, `GenerateIsochrones` i `RunCompetitiveAccessibility`,
   a detektor walk-only zostaje jedno-źródłowy (liczy na zmienionej sieci).
2. **Plik scenariusza = natywny JSON R5 + trzy typy „easy-”** rozwijane w Javie, bo tylko Java zna
   id wzorców i kursów:
   - `easy-remove-routes {routes}` → `remove-trips {routes: [pełne id]}`;
   - `easy-adjust-speed {routes, scale}` → `adjust-speed {routes, scale}`;
   - `easy-set-headway {routes, headway_minutes, start, end}` → jeden `adjust-frequency` na trasę,
     **jeden wpis na kierunek, na wzorcu z największą liczbą kursów** (`sourceTrip` = jego pierwszy
     kurs), wszystkie dni, `retainTripsOutsideFrequencyEntries=true`. `AdjustFrequency` czyści
     wszystkie wzorce trasy i odtwarza kursy tylko z wpisów (javap), więc warianty (skrócone,
     zjazdowe) znikają w oknie zamiast dostać pełną częstotliwość każdy — poprawka po review;
     pierwsza wersja dawała wpis każdemu wzorcowi i zwielokrotniała kursowanie. Łódź, linia 86:
     „Cleared 6 patterns, creating 2 new trip schedules”.
   - Wpis w `routes` jest dopasowywany warstwami, pierwsza z trafieniem wygrywa: **pełne id**
     (`feed:route_id`) → **`route_id`** → **`route_short_name`**. Zero dopasowań →
     `ERROR SCENARIO_INVALID`; więcej niż jedna trasa → `WARN SCENARIO` z listą; zawsze `INFO` z
     rozwiązanym id.
   - Natywne typy R5 przechodzą bez zmian — zaawansowany użytkownik może napisać plik ręcznie.
3. **Nowa linia z warstwy liniowej QGIS**: każdy wierzchołek = przystanek. Czasy między
   przystankami z odległości po kole wielkim / prędkości (min. 1 s). Brak własnego snapowania
   do ulic — R5 linkuje nowe przystanki do sieci ulic sam.
4. **Metoda w wyniku**: `meta["scenario"]` = `"<nazwa pliku>:<sha256[:8]>"` albo `"baseline"`;
   pole `scenario` w warstwach `RunAccessibility` / `RunCompetitiveAccessibility`.
5. **Detektor walk-only** schodzi z błędu do ostrzeżenia **tylko** dla scenariusza, który usuwa
   kursy (`easy-remove-routes`, `remove-trips`, `remove-stops`). Każdy inny scenariusz zostawia twardy
   błąd — to klasa incydentu GZM.
6. **Monte Carlo (poprawka znaleziona przy review, dotyczy całej wtyczki):** R5 traktuje
   `monteCarloDraws` jako **łączną** liczbę losowań w oknie (`iterationsPerMinute =
   ceil(draws / minuty_okna)`, javap `ProfileRequest`). Parametr „draws per minute” był więc
   w praktyce 1 losowaniem na minutę. Runner mnoży teraz przez długość okna (jak r5r), a
   histogram minut obsługi dzieli przez liczbę iteracji na minutę, żeby wynik został w 0–120.
   Dotyczy tylko sieci z kursami częstotliwościowymi (każda nowa linia ze scenariusza,
   `frequencies.txt` Warszawy): tam liczenie jest dłuższe — zmierzone 1,4× na Łodzi z jedną dodaną
   linią (okno 120 min), teoretycznie do 5× dla sieci złożonej głównie z kursów częstotliwościowych
   — ale powtarzalne i zgodne z opisem parametru. Sieci bez częstotliwości (Gdańsk, walidacja r5r) — bez zmian.
7. **Znany artefakt silnika:** dodanie trasy częstotliwościowej może zmienić P50 pojedynczej,
   niezwiązanej pary o 1 min (Łódź: 1 z 144 par, 74 → 75), bo R5 przełącza sposób iterowania dla
   sieci z częstotliwościami. Wynik jest powtarzalny (dwa przebiegi = identyczny CSV).

### R-1.3 `BuildScenario` — parametry

| Parametr | Typ | Domyślnie | Uwagi |
|---|---|---|---|
| `NEW_LINES` | warstwa liniowa, opcj. | — | każdy obiekt = nowa linia, wierzchołki = przystanki |
| `NEW_LINE_MODE` | enum TRAM/SUBWAY/RAIL/BUS/FERRY | BUS | → `route_type` 0/1/2/3/4 |
| `SPEED_KMH` | double | 25 | średnia prędkość komercyjna między przystankami |
| `DWELL_SECONDS` | int | 30 | postój na przystanku |
| `HEADWAY_MINUTES` | double | 10 | co ile kursuje |
| `SERVICE_START` / `SERVICE_END` | HH:mm | 05:00 / 23:00 | zakres kursowania, każdy dzień tygodnia |
| `BIDIRECTIONAL` | bool | True | |
| `REMOVE_ROUTES` | string opcj. | — | lista po przecinku (`86, Z2` albo pełne id) |
| `SPEED_ROUTES` + `SPEED_SCALE` | string + double | — / 1.0 | `0.8` = 20% wolniej |
| `HEADWAY_ROUTES` + `NEW_HEADWAY_MINUTES` + `HEADWAY_START` / `HEADWAY_END` | | — / 10 / 05:00 / 23:00 | nowa częstotliwość istniejących tras |
| `OUTPUT_SCENARIO` | plik `.json` | | |

Brak jakiejkolwiek modyfikacji → błąd. `SPEED_SCALE` ≤ 0 → błąd. Nazwy tras bierzesz z
`OUTPUT_ROUTES` algorytmu `CheckTransitData` (R-3).

### R-1.4 Edge cases

| Sytuacja | Zachowanie |
|---|---|
| Linia z < 2 wierzchołkami | błąd z id obiektu |
| Multilinia | każda część = osobna linia |
| Nieznana trasa w `REMOVE_ROUTES` | Java: `ERROR SCENARIO_INVALID Route 'X' not found in the network` |
| Błąd modyfikacji R5 | `ERROR SCENARIO_INVALID <typ>: <błędy R5>` |
| Plik scenariusza nie jest JSON / brak `modifications` | `QgsProcessingException` przed startem Javy |
| Przystanek poza zasięgiem sieci ulic | ostrzeżenie R5 → `WARN SCENARIO` |

### R-1.5 Kryteria akceptacji

- pytest (`test_scenario.py`, `test_job_spec.py`) zielone, flake8 czysto.
- QGIS MCP, sieć Łodzi: nowa szybka linia między dwoma odległymi punktami skraca czas tej pary;
  `REMOVE_ROUTES` i `SPEED_SCALE=0.5` nie skracają czasu żadnej pary względem baseline.

---

## R-2. `CompareScenarios`

### R-2.1 Decyzje

1. **Jedno pole na przebieg**, stałe nazwy wyjścia (`value_a`, `value_b`, `diff`, `pct_change`,
   `status`). Kilka pól = kilka przebiegów. Styl: renderer kategorii na `status` budowany w kodzie
   (`styling.apply_categories`), bo wynik może być punktowy albo poligonowy, a stały QML ma jeden
   typ symbolu.
2. **Złączenie po polu id**, nie po geometrii.
3. **Pola metody muszą się zgadzać**, jeśli są w obu warstwach: `percentile`, `decay`,
   `time_window`, `departure_time`, `modes`, `catchment`, `max_trip_duration_minutes`,
   `max_walk_time_minutes`, `walk_speed_kmh`, `max_rides`, `monte_carlo_draws` (te pięć
   ostatnich warstwy wynikowe niosą od v0.3).
4. **`HIGHER_IS_BETTER`** (domyślnie tak): dostępność, minuty obsługi, 2SFCA — pusta wartość = 0.
   Wyłączone dla czasów przejazdu: niższy = lepszy, pusta wartość = nieosiągalne, więc utrata
   połączenia to `worse` bez liczbowego `diff`, nigdy „poprawa”. Id złączenia normalizowane
   (`12`, `12.0`, `"12"` to ten sam klucz); obiekty `only_b` w innym CRS są reprojektowane. Różnica → błąd z listą (albo
   `ALLOW_METHOD_MISMATCH`). Mogą się różnić (to jest cel porównania): `run_date`, `network_hash`,
   `scenario`, `transit_submodes`, `r5_version` (ostatnie → ostrzeżenie).

### R-2.2 Parametry

`LAYER_A` (przed), `LAYER_B` (po), `JOIN_FIELD`, `JOIN_FIELD_B` (opcj.; domyślnie ta sama
nazwa), `FIELD` (numeryczne), `FIELD_B` (opcj.), `ALLOW_METHOD_MISMATCH` (zaawansowany),
`OUTPUT`.

### R-2.3 Wyjście

Geometria i atrybuty A (albo B dla `only_b`) + `value_a`, `value_b`, `diff = B − A`,
`pct_change = 100·diff/A` (NULL gdy A = 0 lub brak), `status`: `better` (diff > 0), `worse`,
`same`, `only_a`, `only_b`. Log: liczba lepiej/gorzej/bez zmian, suma i średnia `diff`.

**Kryteria:** `test_compare.py` zielony; w QGIS porównanie dostępności baseline vs scenariusz
daje warstwę ze stylem, a porównanie dwóch przebiegów o różnym percentylu kończy się błędem.

---

## R-3. `CheckTransitData` — kontrola GTFS przed budową sieci

### R-3.1 Decyzje

1. Czysty Python (`core/gtfs_check.py`), reużywa parserów z `core/gtfs_calendar.py`. Zero R5.
2. **Raport powstaje zawsze**; błędy nie przerywają algorytmu (chyba że `FAIL_ON_ERROR`).
3. Obsługiwane `route_type` w R5 7.6 (zweryfikowane `javap`, `TransitLayer.getTransitModes`):
   0–7, 11, 12, 100–1499. Pozostałe (8–10, 13–99, ≥ 1500) → R5 rzuca
   `IllegalArgumentException` → ERROR.

### R-3.2 Sprawdzenia

| Poziom | Sprawdzenie |
|---|---|
| ERROR | brak `stops.txt` / `routes.txt` / `trips.txt` / `stop_times.txt` |
| ERROR | brak `calendar.txt` i `calendar_dates.txt` albo zero dni z kursami |
| ERROR | `DATE` podana i 0 kursów tego dnia (+ 3 najbliższe dni z kursami) |
| ERROR | `route_type` nieobsługiwany przez R5 7.6 |
| ERROR | ≥ 50% wspólnych `trip_id` między dwoma zipami (P50/P85 i static w jednym folderze); mniej → WARN |
| ERROR | zduplikowany `feed_id` między zipami (brak `feed_id` = nazwa pliku, jak w R5; `DuplicateFeedException`) |
| ERROR | `EXTENT` podany, a żaden przystanek w nim nie leży |
| WARN | `trips.route_id` / `trips.service_id` / `stop_times.trip_id` / `stop_times.stop_id` bez rekordu |
| WARN | kursy bez `stop_times` |
| WARN | przystanki z `0,0` / poza zakresem / bez współrzędnych |
| WARN | brak `agency_timezone` albo różne strefy w feedach |
| WARN | `EXTENT` podany, część przystanków poza nim |
| WARN | dni w zakresie kalendarza bez kursów (liczba) |
| INFO | zakres kalendarza, kursy/dzień min/mediana/max, liczba tras wg typu, bbox przystanków, brak `shapes.txt`, obecny `frequencies.txt` |

### R-3.3 Parametry i wyjścia

`GTFS` (plik `.zip` albo folder z zipami), `DATE` (opcj.), `EXTENT` (opcj.), `FAIL_ON_ERROR`
(zaawansowany, False), `OUTPUT_REPORT` (HTML), `OUTPUT_SERVICE_DAYS` (CSV `date,trips`),
`OUTPUT_ROUTES` (CSV `feed,route_id,short_name,long_name,route_type,trips`). Wynik `ERRORS`,
`WARNINGS` (liczby).

**Kryteria:** `test_gtfs_check.py` (zipy budowane w teście) zielony; w QGIS na GTFS Łodzi:
data z kursami → 0 błędów kalendarza, data bez kursów → ERROR z najbliższymi dniami.

---

## R-4. `SummarizeAccessibilityEquity`

### R-4.1 Decyzje

1. Czysty Python (`core/equity.py`), działa na **dowolnej** warstwie z polem populacji i polami
   liczbowymi — wyjście `RunAccessibility`, `RunCompetitiveAccessibility` albo cokolwiek innego.
2. Wszystkie statystyki **ważone populacją**. NULL / ujemna populacja → wiersz pominięty
   (licznik w logu); NULL dostępność → traktowana jako 0 (osoba bez dostępu, nie brak danych).
3. Gini ważony: `G = Σ_i Σ_j w_i w_j |x_i − x_j| / (2 · W² · μ)` liczony w O(n log n) po sortowaniu.
   μ = 0 albo jakakolwiek wartość ujemna (np. pole `diff`) → Gini = NULL.
4. Kwantyle ważone: najmniejsze x, dla którego skumulowana waga ≥ q·W.

### R-4.2 Parametry i wyjścia

`INPUT`, `POPULATION_FIELD`, `ACCESSIBILITY_FIELDS` (wiele), `THRESHOLD` (1.0),
`GROUP_FIELD` (opcj.), `OUTPUT_TABLE` (warstwa bez geometrii / CSV:
`grp, field, population, pop_at_least, share_at_least, pop_zero, share_zero, mean, p10, p25,
p50, p75, p90, gini`), `OUTPUT_REPORT` (HTML: jedno zdanie po ludzku na pole, tabela, pola metody
z warstwy wejściowej). Wiersz `grp = "ALL"` zawsze, plus po jednym na grupę.

**Kryteria:** `test_equity.py` (Gini = 0 dla równego rozkładu, znany przypadek, kwantyle,
pomijanie NULL) zielony; w QGIS udział populacji zgadza się z ręcznym przeliczeniem.

---

## R-5. `RunCompetitiveAccessibility` — 2SFCA

### R-5.1 Metoda

Luo & Wang (2003) 2SFCA, z opcjonalnym zanikiem (wariant E2SFCA-like, jak w
`accessibility.decay_weight`):

- krok 1 (podaż): `R_j = S_j / Σ_k P_k · w(t_kj)` dla `t_kj < d₀`;
- krok 2 (popyt): `A_i = Σ_j R_j · w(t_ij)`;
- `w` = STEP (klasyczny 2SFCA), LOGISTIC albo EXPONENTIAL; `d₀` = `CATCHMENT_MINUTES`;
- wynik skalowany: `A_i · PER_POPULATION` (np. lekarzy na 1000 mieszkańców).
- Podaż bez popytu w zlewni → `R_j = 0`, ostrzeżenie z liczbą.

### R-5.2 Decyzje

1. **Jeden bieg macierzy** (origins = lokalizacje popytu, destinations = podaż). `MatrixBase`,
   jak `RunAccessibility`; `SCENARIO` działa automatycznie.
2. **Jeden percentyl** (wspólny parametr `PERCENTILES`, walidowany do dokładnie jednej wartości,
   domyślnie 50) — mieszanie percentyli w jednym indeksie nie ma interpretacji.
3. Populacja trafia do CSV origins jako dodatkowa kolumna (`origin_extra_fields` w `_run_matrix`).
4. Suma kontrolna w logu: `Σ_i A_i·P_i = Σ_j S_j` dla podaży z niezerowym popytem (własność
   2SFCA — cała podaż jest rozdzielona).

### R-5.3 Parametry i wyjścia

Wspólne z `MatrixBase` (`PERCENTILES` = jedna wartość), `POPULATION_FIELD`
(origins), `CAPACITY_FIELD` (destinations), `CATCHMENT_MINUTES` (30), `DECAY` (STEP),
`PER_POPULATION` (1000), `OUTPUT_LAYER` (origins + `fca`, meta), `OUTPUT_SUPPLY_LAYER`
(opcj.: destinations + `supply_ratio`, `demand_in_catchment`), `OUTPUT_CSV`
(`id,population,fca`).

**Kryteria:** `test_fca.py` (ręcznie policzony przykład 2×2 i własność zachowania podaży)
zielony; w QGIS wartości dla 2 origins zgadzają się z ręcznym przeliczeniem z macierzy.
