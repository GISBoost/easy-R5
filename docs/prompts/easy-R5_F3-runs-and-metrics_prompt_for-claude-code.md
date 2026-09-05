# Claude Code prompt — Easy-R5 **F3**: cztery przebiegi, niezmienniki, metryki

> Wklej poniżej linii do Claude Code, w repo `easy-R5`, czysty tree. Kod po angielsku,
> rozmowa po polsku. **F1 i F2 muszą być zrobione i zacommitowane.** Implementuj wyłącznie
> F3 — kartografia to F4. Nowego brancha nie twórz.

---

> ## ⚠ AKTUALIZACJA v2 (2026-09-05) — przeczytaj przed resztą tego pliku
>
> Analiza urosła z dwóch trybów do trzech (doszła kolej aglomeracyjna **ŁKA**). Ten prompt
> opisuje wersję dwutrybową. Obowiązuje
> [`../prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`](../prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md)
> wszędzie tam, gdzie się różni. W skrócie:
>
> - **osiem przebiegów**, nie cztery: `W, T, B, R, TB, TR, BR, TBR` (PRD v2 §4.1),
> - **data 2026-08-21**, nie 2026-08-24 (PRD v2 §3.2),
> - sieć z **F2b**, nie z F2 — zawiera oba feedy,
> - niezmienniki: `I1`/`I2` zastąpione przez **`I5` (monotoniczność kraty)**, dochodzi
>   **`I4` (kolej nie została po cichu porzucona)** — PRD v2 §4.6,
> - nowe rodziny metryk: **odporność** (§4.4.5), **wyspy dostępności** (§4.4.6),
>   **replikacja porównania buforowego z artykułu** (§2.2),
> - `tram_share` **ma w v2 inną definicję** — liczoną w pełnej sieci trzymodalnej. Nie reużywaj
>   pól z v1 i rozpisz obie definicje w `COLUMNS.md`.
>
> Wszystko poniżej, co nie dotyczy liczby przypadków modalnych, daty i niezmienników, zostaje.


## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` — **§4 w całości**. To jest specyfikacja
  tego kamienia: §4.1 przypadki, §4.2 parametry, §4.4 wzory, §4.5 progi i NULL-e,
  **§4.6 niezmienniki**.
- `docs/notes/r5-engine-primer.md` — zanim dotkniesz silnika.
- `CLAUDE.md`, sekcja *Gotchas* — data bez kursów, `maxWalkTime`, koszt zależny od
  złożoności sieci, pamięć jako główny tryb awarii.
- `tools/accessibility_lodz/STUDENTS_ANALYSIS.md` §2 — **znak percentyli** (p10 czasu =
  najszybsze odjazdy = najwyższa dostępność). Ten błąd już raz tu wystąpił.
- `tools/accessibility_lodz/COLUMNS.md` — nazewnictwo kolumn.

## Po co ten kamień istnieje

To jest cała arytmetyka analizy. Cztery przebiegi `RunAccessibility` na jednej sieci, jednej
warstwie celów i jednej dacie, różniące się **wyłącznie** listą podtrybów transitu — a potem
kilkanaście linijek algebry, które zamieniają je w mapę.

Najważniejsza część tego kamienia **nie jest** liczeniem. Jest nią §4.6: trzy niezmienniki,
które sprawdzają, czy R5 w ogóle respektuje `transitModes` na ścieżce runnera. Nikt tego tu
wcześniej nie robił, a R5 oficjalnie nie ma stabilnego API. Jeżeli `I3` nie przejdzie, wynik
analizy jest nieważny — i to trzeba wykryć teraz, a nie po narysowaniu mapy.

## Co zbudować

### 1. `run_modal_cases.py`

Skrypt PyQGIS w `tools/modal_complementarity_lodz/`, uruchamiany z QGIS-owego Pythona,
wywołujący `processing.run("easyr5:runaccessibility", …)` **cztery razy**:

| id | `MODE` | `TRANSIT_SUBMODES` |
|---|---|---|
| `W` | WALK | — |
| `T` | TRANSIT + WALK | `TRAM` |
| `B` | TRANSIT + WALK | `BUS` |
| `TB` | TRANSIT + WALK | `TRAM, BUS` |

Parametry wspólne — **dokładnie** z PRD §4.2. Trzy, o których łatwo zapomnieć i które psują
wynik po cichu:

- `MAX_RIDES = 3` — przy 1 nie ma przesiadki międzymodalnej i przypadek `TB` traci sens,
- `MAX_WALK_TIME` puste (→ 60) — **nigdy** bez limitu,
- `ALLOW_NO_SERVICE = False` — twarda bramka daty ma zadziałać.

Wyjścia: `out/acc_<id>.csv` + kopia warstwy origins z polami `acc_*`. **Zmierz i zapisz czas
każdego przebiegu** — ta liczba idzie do README („cała analiza: N minut na laptopie").
Zapisz też `out/run_meta.json`: parametry, wersję R5, wersję wtyczki, `transit_submodes`
każdego przebiegu, znacznik czasu.

Skrypt ma być **wznawialny**: jeżeli `out/acc_T.csv` istnieje i jego metadane zgadzają się z
zadanymi parametrami, nie licz go ponownie. Cztery przebiegi × pomyłka w jednym parametrze
to inaczej cztery razy ta sama kara.

### 2. `check_invariants.py`

Osobny plik, bo to jest dowód, a nie krok pipeline'u. Sprawdza dla **każdego** wiersza
(heksagon × cutoff × percentyl × kolumna opportunities):

```
I1   A^W ≤ A^T   ∧   A^W ≤ A^B   ∧   A^W ≤ A^TB
I2   A^TB ≥ max(A^T, A^B)
I3   mean|A^T - A^B| / mean(A^TB)  >  0.05
```

- `I1`/`I2` naruszone → **przerwij**, wypisz 10 przykładowych wierszy z wartościami. To jest
  błąd silnika, parametrów albo joinu, nie szum.
- `I3` niespełnione → **przerwij** i napisz wprost: *R5 prawdopodobnie ignoruje
  `transitModes` na tej ścieżce; analiza w tej postaci jest nieważna.* Fallback (filtrowanie
  GTFS po `route_type` i trzy osobne sieci) opisany w
  `docs/notes/flagship-analysis-candidates.md` §3 — **nie implementuj go z własnej inicjatywy**,
  zgłoś i zapytaj.
- Wynik (przeszło/nie, wartość `I3`, liczba wierszy) → `out/invariants.json` i do
  `docs/notes/flagship-lodz-modal-results.md` w F5.

### 3. `compute_metrics.py`

Wzory z **PRD §4.4**, dokładnie. Wejście: cztery CSV. Wyjście: warstwa `hex_modal` w
`lodz_modal.gpkg` + `out/hex_modal.csv` + `out/city_summary.csv`.

Reguły z **PRD §4.5**, wszystkie twarde:

1. `A^TB = 0` → udziały **`NULL`**, nigdy 0.
2. Próg wiarygodności `K = 1000` (osób, na `A^TB(30, p50, pop_total)`) — poniżej progu
   udziały są `NULL`. `K` i liczba odfiltrowanych heksagonów → `out/run_meta.json`.
3. Zawsze zapisuj wartość bezwzględną **obok** względnej.
4. `pop_total = 0` → poza agregatami ważonymi, na mapie przezroczyste, **nie** w najniższej
   klasie.

Agregaty miejskie (`out/city_summary.csv`): `Ā^m(T)` dla `m ∈ {W, T, B, no_transfer, TB}` i
`T ∈ {15,30,45,60}`, ważone `pop_total`, plus `cov^m(T)` i miejska sub-addytywność.

Nazewnictwo pól — czytelne i jednoznaczne, w stylu `COLUMNS.md`:
`acc_tb_pop_p50_c30`, `tram_gain_pop_p50_c30`, `tram_share_pop_p50_c30`,
`transfer_premium_pop_p50_c30`, `subadd_pop_p50_c30`, …
Dopisz `tools/modal_complementarity_lodz/COLUMNS.md` opisujący **każde** pole. Bez tego
za trzy miesiące nikt (łącznie z Michałem) nie odróżni `tram_gain` od `tram_share`.

### 4. Przebieg kontrolny — POI punktowe

Jeden dodatkowy przebieg: przypadek `TB`, cutoff 30, percentyl 50, cele =
`poi_destinations` (dokładne 1 328 punktów z F2). Policz korelację **Spearmana** między
`srv_total_30min` z tego przebiegu a wersją heksagonalną.

- `ρ ≥ 0,95` → metryka usługowa jest wiarygodna, idzie do tekstu normalnie.
- `ρ < 0,95` → metryka usługowa idzie do tekstu **z zastrzeżeniem**; zgłoś to wyraźnie.

Wynik → `out/poi_control.json`.

### 5. Bez pandas

`csv` + `math` ze stdlib (ew. `numpy`, który QGIS ma). 1 479 wierszy × kilkadziesiąt kolumn
nie potrzebuje pandas, a skrypt ma się uruchamiać w interpreterze QGIS bez instalowania
czegokolwiek — tak samo jak wtyczka.

## Czego NIE ruszać

- `easy_r5/` — F1 skończone. Jeżeli w trakcie znajdziesz błąd we wtyczce, **zgłoś** i zapytaj,
  nie łataj po cichu w środku analizy.
- Danych wejściowych z F2 — jeżeli czegoś brakuje, to jest błąd F2, wróć do niego świadomie.
- Nie rysuj map. To F4.

## Kryteria akceptacji

- [ ] Cztery przebiegi zakończone, czasy zmierzone i zapisane.
- [ ] `I1` i `I2` spełnione dla wszystkich wierszy.
- [ ] `I3` spełnione; wartość zapisana.
- [ ] Kontrola POI: `ρ` policzone i zapisane.
- [ ] Wszystkie udziały `NULL` tam, gdzie `A^TB = 0` lub poniżej `K`.
- [ ] `city_summary.csv` zawiera `Ā^m` dla 5 przypadków × 4 progi.
- [ ] `COLUMNS.md` opisuje każde pole `hex_modal`.
- [ ] `flake8` czysto; skrypty wznawialne.

## Co musi sprawdzić Michał

1. **Sanity mapy roboczej**: załaduj `tram_share_pop_p50_c30` w QGIS z byle jaką rampą —
   czy wysokie wartości układają się w korytarze, które wyglądają jak sieć tramwajowa?
   Jeżeli nie, coś jest nie tak z filtrem trybów, a niezmienniki tego nie złapią.
2. Czy `Ā^TB(30)` jest w rzędzie wielkości, którego się spodziewasz dla Łodzi?
3. Czy `subadd` jest **poniżej 1** (sub-addytywność, jak w literaturze)? Jeżeli wyszło
   powyżej 1, to ciekawy wynik — ale najpierw sprawdź odejmowanie bazy pieszej (`Ã^m`).
