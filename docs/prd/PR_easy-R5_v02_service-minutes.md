# PRD — Easy-R5 v0.2 · Metryka "minut obsługi" (service-minutes reliability)

**Status:** ✅ zaimplementowane, 2026-09-16. `metadata.txt` `0.2.2`. Zweryfikowane
end-to-end przez QGIS MCP: realny routing na sieci łódzkiej (`tools/f1_smoke_test_lodz`),
144 par OD, wszystkie wartości `svc_min_c<cutoff>` w [0,120] i monotonicznie
nierosnące względem cutoffu. 193 testy pytest zielone, flake8 czysto.
**Data:** 2026-09-16
**Autor:** Michał Kaczorowski
**Kontekst wymagany do pracy:** ten plik + `CLAUDE.md` + `CONTEXT.md` +
`docs/notes/roadmap-candidates.md` §T1-A + `docs/notes/r5-engine-primer.md` §3 +
`docs/notes/open-questions.md` #5 + `docs/notes/spike-r5-probe-2026-09-02.md` +
`docs/reference/probe/Probe3.java` (działający wzorzec do portu).

> Ten PRD opisuje **jeden element v0.2**: nowy algorytm `RunServiceMinutes`, który dla
> każdej pary origin-destination liczy, na ilu z 120 minut okna odjazdów dany cel jest
> osiągalny w zadanym progu (cutoff). Reszta zakresu v0.2 (`CompareScenarios`,
> `CheckTransitData`, `DownloadTransitData`) ma osobne PRD. **Nie wybiegaj naprzód.**

---

## 0. Po co to jest

**Problem użytkownika.** P50/P85 mówi "typowy" i "zły dzień", ale ukrywa *jak często*
połączenie w ogóle jedzie. Dwie trasy o identycznym P50=25 min mogą się drastycznie
różnić: jedna ma autobus co 8 minut (cel osiągalny w progu 30 min niemal zawsze), druga
ma jeden kurs w oknie (cel osiągalny tylko wtedy, gdy się na niego trafi). To dokładnie
problem, który r5py i r5r musiały adresować w dokumentacji `departure_time_window`
(r5py #292: domyślne okno 1 h zmieniono, bo użytkownicy nieświadomie próbkowali jedną
minutę i dostawali mylące liczby). Flagowy produkt easy-OTP ma metrykę "minut obsługi" —
użytkownicy Easy-R5 to ci sami ludzie i będą jej oczekiwać.

**Dlaczego to tanie.** R5 i tak routuje **wszystkie 120 minut** okna odjazdów wewnętrznie
przy każdym `TravelTimeComputer.computeTravelTimes()` — percentyle i histogram są
ortogonalne, `recordTravelTimeHistograms=true` tylko włącza zapamiętywanie rozkładu, który
R5 już liczy. Zweryfikowane spike'em 2026-09-02 (`Probe3.java`, działa na realnej sieci).
Redukcja Pythonowa (`sum(hist[0..cutoff])`) to jedna pętla — i tę robi Java (§1.3), nie
Python.

**Zakres.** Jeden nowy algorytm Processing (`RunServiceMinutes`), rozszerzenie komendy
Javy `matrix` o dwa opcjonalne pola job-speca, dwie nowe funkcje w `core/matrix.py`
(addytywne, nie dotykają istniejącego kontraktu `travel_time*`), jedna nowa funkcja
w `core/job_spec.py`.

---

## 1. Decyzja architektoniczna

### 1.1 Nowy algorytm, nie tryb macierzy (ustalone z użytkownikiem)

`RunServiceMinutes` to osobna klasa (`algorithms/run_service_minutes.py`), miksuje
`MatrixBase` jak `RunTravelTimeMatrix`/`RunAccessibility`. Parametr `CUTOFFS` (jak
w `RunAccessibility`) zamiast `PERCENTILES` — `RunServiceMinutes` **nie ma** parametru
percentyli w UI (percentyle i histogram są ortogonalne; wystawianie percentyli tutaj
sugerowałoby użytkownikowi, że są potrzebne, a nie są). Wyjście jest **per para OD**
(jak macierz), **nie** zagregowane per origin (jak dostępność).

### 1.2 Java: rozszerz komendę `matrix`, nie dodawaj `service_minutes`

Dwa nowe opcjonalne pola job-speca dla komendy `matrix`: `record_histograms: bool`
(domyślnie `false`) i `service_minute_cutoffs: [int]` (wymagane, gdy `record_histograms`
jest `true`). Powód: `_run_matrix` (Python, współdzielony przez wszystkie algorytmy
macierzowe) polega na tym, że Java **zawsze** emituje `RESULT transit_used_pairs` —
niezależny detektor "czy cokolwiek pojechało transportem", strażnik przed cichym
walk-only (`CLAUDE.md`, incydent GZM sierpień 2026). Nowa, osobna komenda Javy
musiałaby powielić ten detektor od zera — dwie niezależne implementacje kontrolki
bezpieczeństwa mogą się rozjechać. Reużycie `matrix` trzyma tę logikę w jednym miejscu.

Żeby to działało bez percentyli w UI: Python zawsze wysyła do Javy
`"percentiles": [50]` (stała, wewnętrzna, nigdy nie pokazywana użytkownikowi) —
wyłącznie do istniejącego porównania z przebiegiem pieszym. `baseTask()` zostaje
nietknięty; flaga `recordTravelTimeHistograms` jest ustawiana na obiekcie `task` **po**
`baseTask()`, i **tylko** na głównym (transit) zadaniu — nie na towarzyszącym zadaniu
pieszym, żeby nie dublować pamięci tam, gdzie histogram nikomu nie jest potrzebny.

Protokół `Emit` (INFO/PROGRESS/WARN/ERROR/RESULT/DONE) **zamrożony** — brak nowych
czasowników, tylko inny kształt wiersza CSV.

### 1.3 Redukcja histogramu: Java, nie Python

Java sumuje `hist[0..cutoff]` (włącznie z minutą równą cutoffowi) per żądany cutoff
i emituje **tylko** kolumny `svc_min_c<cutoff>` (int) — nigdy surowej tablicy `int[120]`.
To trzyma granicę procesu małą (garść intów na parę OD, nie 120) i jest tym samym
wzorcem, którym Java już dziś redukuje wewnętrzny rozkład do kolumn percentylowych.

Konsekwencja: **`core/service_minutes.py` nie powstaje.** `RunServiceMinutes` woła
`_run_matrix(..., matrix_csv=out_csv, ...)` dokładnie jak `RunTravelTimeMatrix` —
scalone CSV z batchy **jest** wynikiem końcowym, bez żadnej redukcji po stronie
Pythona.

### 1.4 Brak klasyfikacji na kategorie (świadomie, w odróżnieniu od easy-OTP)

Wyjście to wyłącznie surowa liczba minut (`svc_min_c<cutoff>`, int 0–120,
"liczba z 120 minut okna odjazdów, w których cel jest osiągalny w tym progu"). **Żadnej**
4-kategoriowej klasyfikacji jak `st_class` w easy-OTP
(`"constantly"/"regularly"/"periodically"/"episodically accessible"`).

Powód: kategorie easy-OTP są skalibrowane do okna referencyjnego 960 minut
(06:00–22:00, 961 osobnych przebiegów routingu, jedna rastrowa powierzchnia na minutę,
potem średnia strefowa na sześciokąt). R5 liczy domyślnie okno 120-minutowe w **jednym**
wywołaniu `TravelTimeComputer`, per para OD (nie per komórka heksagonalna po statystyce
strefowej). Te dwie liczby nie są na tej samej skali — przeniesienie progów kategorii
dałoby użytkownikowi fałszywe wrażenie porównywalności z easy-OTP. `CONTEXT.md` dostaje
nowy wpis słownikowy "Service minutes" z jawnym zastrzeżeniem, że to nie ta sama liczba.

---

## 2. Parametry algorytmu (`RunServiceMinutes`)

Współdzielone z `_add_matrix_params(with_percentiles=False)`: `NETWORK`, `ORIGINS`,
`ORIGIN_ID_FIELD`, `DESTINATIONS`, `DEST_ID_FIELD`, `DATE`, `DEPARTURE_TIME`,
`TIME_WINDOW` (domyślnie 120 — to jest samo w sobie długość okna, do którego cutoffy
się odnoszą), `MAX_TRIP_DURATION`, `WALK_SPEED`, `MAX_RIDES`, `MODE`,
`TRANSIT_SUBMODES`, `MAX_WALK_TIME` (advanced), `MONTE_CARLO_DRAWS` (advanced),
`BATCH_SIZE` (advanced), `ESTIMATE_FIRST` (advanced), `ALLOW_NO_SERVICE` (advanced),
`JAVA_HEAP_GB` (advanced). **Brak `PERCENTILES`.**

Własne parametry (wzorowane 1:1 na `RunAccessibility.CUTOFFS`):

| param | typ | domyślnie | uwagi |
|---|---|---|---|
| `CUTOFFS` | `String` | `"15,30,45,60"` | minuty, oddzielone przecinkami, parsowane do posortowanego zbioru intów. **Twardy limit: ≤ 119** (patrz niżej). |
| `INCLUDE_UNREACHABLE` | `Boolean`, advanced | `False` | zachowaj wiersze celów nieosiągalnych w żadnym cutoffie jako jawne wiersze same-zera. |
| `OUTPUT_CSV` | `FileDestination` | — | długi CSV. |
| `OUTPUT_LAYER` | `FeatureSink`, opcjonalny, `createByDefault=False` | — | linie OD, jedno pole int per cutoff. |

Strażnik `MAX_TRIP_DURATION` vs `max(CUTOFFS)`: identyczny jak w `RunAccessibility`
(cutoff większy niż budżet podróży → podnieś budżet i ostrzeż). `MAX_WALK_TIME`
bezstratny fallback = `max(CUTOFFS)` (dojście dłuższe niż największy cutoff nigdy nie
może zmienić wyniku).

**Twardy limit odkryty 2026-09-17 (javap na `r5-v7.6-all.jar`):**
`TravelTimeResult.histograms` jest alokowane jako `new int[nPoints][120]` —
**stały rozmiar, niezależny od `maxTripDurationMinutes`**. `recordHistogramIfEnabled`
robi nieosłonięty zapis `histograms[target][travelTimeSeconds / 60]++` bez sprawdzania
zakresu. Każda osiągalna podróż ≥120 min (co jest możliwe, gdy `MAX_TRIP_DURATION` lub
`CUTOFFS` sięgają ≥120) rzuca `ArrayIndexOutOfBoundsException` **wewnątrz JVM** — dokładnie
ten rodzaj nieczytelnego wyjątku, któremu ma zapobiegać walidacja w `job_spec.py`
(por. `MAX_PERCENTILES`). Stąd: `job_spec.HISTOGRAM_MAX_MINUTES = 119`, walidowane
**zarówno** w `job_spec.build_service_minutes_job` (przed spawnowaniem Javy), **jak i**
wcześniej, przyjaźnie, w `RunServiceMinutes.processAlgorithm` — zarówno dla `CUTOFFS`,
jak i dla `MAX_TRIP_DURATION` (bezpośrednio ustawionego przez użytkownika, niezależnie
od cutoffów).

---

## 3. Job-spec (Java-facing) — dokładny kształt

Nowe pola na istniejącej komendzie `"matrix"`:

```json
{
  "command": "matrix",
  "...": "... wszystkie pola jak dziś ...",
  "percentiles": [50],
  "record_histograms": true,
  "service_minute_cutoffs": [15, 30, 45, 60]
}
```

`percentiles: [50]` jest stałą wewnętrzną (detektor walk-only), nigdy nie pochodzi
z UI `RunServiceMinutes` i nigdy nie trafia do kolumn wyjściowych, gdy
`record_histograms` jest `true`.

## 4. CSV output — dokładny kształt

```
from_id,to_id,svc_min_c15,svc_min_c30,svc_min_c45,svc_min_c60
o1,d1,4,22,58,87
o1,d2,0,0,3,11
```

- Wartości: int, zakres 0–120.
- **Brak pustych komórek.** W przeciwieństwie do macierzy (gdzie pusta komórka = cel
  nieosiągalny), tu `0` już jednoznacznie znaczy "nieosiągalny w tym cutoffie na żadnej
  z 120 minut" — nie ma potrzeby rozróżniać "puste" od "zero".
- Wiersz jest pomijany (chyba że `INCLUDE_UNREACHABLE`), gdy **wszystkie** kolumny
  cutoffów wynoszą 0.
- `.meta.json` sidecar: te same pola co macierz (`r5_version, network_hash, run_date,
  departure_time, time_window, modes, transit_submodes, walk_speed_kmh, max_rides,
  max_trip_duration_minutes, max_walk_time_minutes, monte_carlo_draws,
  origins_sha256, destinations_sha256`), **`"percentile": null`** (nie dotyczy) plus
  nowe pole **`"cutoffs": "15,30,45,60"`**.

## 5. Edge cases i komunikaty błędów

| sytuacja | zachowanie |
|---|---|
| `CUTOFFS` puste albo zawiera wartość `< 1` | `QgsProcessingException`: "Give at least one positive cutoff." (identyczny tekst jak `RunAccessibility`). |
| `CUTOFFS` zawiera wartość `≥ 120` | `QgsProcessingException` — R5's histogram jest stałym zakresem 0-119 min; większy cutoff nie da się zmierzyć. |
| `MAX_TRIP_DURATION ≥ 120` (wprost albo po podniesieniu przez strażnika cutoffów) | `QgsProcessingException` — inaczej R5 rzuciłby `ArrayIndexOutOfBoundsException` w JVM przy pierwszej podróży ≥120 min. |
| `getHistogram(d)` zwraca `null` (cel nigdy nie osiągnięty w żadnej z 120 minut) | traktowane jak wszystkie liczniki = 0, nie błąd. |
| cutoff większy niż `MAX_TRIP_DURATION` | ostrzeżenie + podniesienie budżetu (jak w `RunAccessibility`). |
| data bez aktywnych kursów GTFS (transit run) | ten sam twardy gate co macierz — bez zmian, logika w `_run_matrix`. |
| `record_histograms=true` a `service_minute_cutoffs` puste (po stronie Javy) | `ERROR BAD_JOB_SPEC "'matrix' with record_histograms needs at least one service_minute_cutoffs value."` |

## 6. Kryteria akceptacji

- `easy_r5/test/test_job_spec.py`: nowe testy dla `build_service_minutes_job` — kształt,
  walidacja cutoffów, `record_histograms: True`, `percentiles: [50]` na stałe.
- Wszystkie istniejące testy nadal zielone; `flake8` czysto.
- `EasyR5Runner.java` nadal kompiluje się jednym plikiem przeciw `r5-v7.6-all.jar`
  (ręczna weryfikacja Michała lub agenta z lokalnym JDK 21 + jar — agent nie zakłada,
  że kod „działa" bez tego kroku, `CLAUDE.md` §"Czego NIE testuje agent").
- Ręczna weryfikacja w QGIS (MCP): `RunServiceMinutes` na realnej/testowej sieci,
  kolumny `svc_min_c<cutoff>` w zakresie 0–120, monotonicznie nierosnąco przy
  malejącym cutoffie.
- `CONTEXT.md` ma nowy wpis "Service minutes" z jawnym zastrzeżeniem vs easy-OTP.
- `KNOWN_ISSUES.md` ma wpis o podwojeniu pamięci per origin, z numerem GitHub Issue.

## 7. Poza zakresem tej wersji

| Pomysł | Dlaczego nie teraz |
|---|---|
| Klasyfikacja na kategorie (jak `st_class`) | Różne okno referencyjne niż easy-OTP — patrz §1.4. |
| Własny QML dla warstwy linii OD | Wielopolowa (jedno pole na cutoff) — brak oczywistego jednego pola do stylizacji graduowanej. Dodać, jeśli ktoś tego zażąda. |
| Redukcja histogramu po stronie Pythona | Rozdmuchałoby CSV 120× — patrz §1.3. |
| Osobna komenda Javy `service_minutes` | Zdublowałaby detektor walk-only — patrz §1.2. |

## Źródła

`docs/notes/roadmap-candidates.md` §T1-A, `docs/notes/spike-r5-probe-2026-09-02.md`,
`docs/notes/r5-engine-primer.md` §3, `docs/notes/open-questions.md` #5,
`docs/reference/probe/Probe3.java`, `CLAUDE.md` gotchas (histogram + walk-only).
