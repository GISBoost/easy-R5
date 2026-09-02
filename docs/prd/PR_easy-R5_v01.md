# PRD — Easy-R5 v0.1 (fundament: sieć, macierz, dostępność, izochrony)

**Status:** Draft
**Data:** 2026-09-02
**Autor metody i właściciel projektu:** Michał Kaczorowski
**Kontekst:** `CLAUDE.md`, `CONTEXT.md`, ADR-0001/0002/0003, `docs/notes/*`.
R5 v7.6, Java 21, QGIS 3.22 LTR+.
**Podstawa faktograficzna:** `docs/notes/spike-r5-probe-2026-09-02.md` — wszystkie liczby
w sekcji 2 pochodzą z realnego uruchomienia R5 na sieci Gdańska, nie z dokumentacji.

> Ten PRD opisuje **wyłącznie v0.1** — minimalny, ale kompletny łańcuch: pobierz silnik →
> zbuduj sieć → policz macierz czasów → policz dostępność → narysuj izochrony.
> Scenariusze sieciowe, itineraria i metryka „minut obsługi" mają własne PRD (v0.2+).
> **Nie wybiegaj naprzód** — sekcja 9 wymienia wprost, czego w v0.1 nie ma.

---

## 1. Cel

Wtyczka QGIS, która daje analitykowi bez R, condy i Dockera dostęp do silnika R5:
macierze czasów przejazdu i dostępność skumulowaną liczone **jeden-do-wielu w oknie
odjazdów**, w tempie nieosiągalnym dla easy-OTP, z wynikiem jako gotowa, ostylowana
warstwa QGIS.

Miara sukcesu v0.1: **użytkownik odtwarza wynik `run_accessibility.R` dla Gdańska
wewnątrz QGIS-a, nie dotykając R** (sekcja 6, M4).

## 2. Zweryfikowana baza techniczna

Zmierzone 2026-09-02 na tej maszynie (Windows 10, Temurin 25, R5 `v7.5.1`, sieć Gdańska:
`network.dat` 106 MB, 1619 przystanków, 573 tripPatterns, 196 913 wierzchołków ulic;
1389 origins, 956 destinations, okno 07:00 +120 min, WALK+TRANSIT, cap 90 min).
**Te liczby są wiążące dla projektu UI i domyślnych parametrów.**

| Fakt | Wartość | Konsekwencja projektowa |
|---|---|---|
| Single-file source launcher (`java -cp r5.jar Probe.java`) | działa; narzut kompilacji ≈ 0,8 s | ADR-0001 potwierdzony; `javac` przy setupie usuwa nawet ten narzut |
| Wczytanie `network.dat` (106 MB) | **1179 ms** | wznowienie procesu jest tanie; batchowanie origins jest bezpieczne |
| Pierwszy origin (linkowanie pointsetu + `EgressCostTable`) | **914 ms** | koszt jednorazowy **na pointset**, nie na origin |
| Kolejny origin | **39 ms**, przy 200 origins **16 ms/origin** | 1389 origins ≈ **22 s**. Jeden proces musi obsłużyć wiele origins — nigdy proces na origin |
| `AnalysisWorkerTask.MAX_PERCENTILES` | 5; `validatePercentiles()` rzuca `IllegalArgumentException` przy 6 | UI ogranicza wybór do maks. 5 percentyli, walidacja po stronie Pythona |
| `FastRaptorWorker` | „Performing 120 total iterations (1 per minute)" | okno 120 min = 120 minut odjazdu; percentyle to redukcja tego rozkładu |
| `recordTravelTimeHistograms=true` + `TravelTimeResult.getHistogram(target)` | zwraca `int[120]` — liczba minut odjazdu dla każdego czasu przejazdu | **rozkład per minuta odjazdu jest dostępny** → metryka „minut obsługi" wykonalna (v0.2) |
| Natywna dostępność R5 (`recordAccessibility=true`) | `NullPointerException: task.destinationPointSetKeys is null` | R5 liczy dostępność tylko przez warstwę storage Conveyala → **dostępność liczymy w Pythonie** |
| `OneOriginResult` | `travelTimes`, `accessibility`, `paths`, `density` | v0.1 używa wyłącznie `travelTimes` |
| Nieosiągalne | `Integer.MAX_VALUE` (2147483647) | sentinel → `NULL` w warstwie, nigdy 2147483647 w wyniku |
| Jednostka czasu | **minuty** (int) | jak w OTP; bez konwersji |
| Java 25 na R5 7.5.1 | działa; ostrzeżenie `sun.misc.Unsafe` z Kryo | pin na 21 i **zawsze pełna ścieżka do binarki**, nigdy `java` z PATH |
| Linkowanie punktów | 956/956 dopięte do ulic | brak dopięcia to realny błąd do obsłużenia, nie teoria |
| GTFS Gdańska | tylko `calendar_dates.txt`, service_id per dzień | ostrzeżenie r5r „<20% services running" to **fałszywy alarm** dla takich feedów → walidujemy liczbą kursów w dniu, nie udziałem serwisów |
| QGIS na tej maszynie | 3.40.5, Python 3.12.9; `numpy`, `pandas`, `geopandas`, `shapely`, `pyproj`, `openpyxl` obecne | **nie wolno na tym polegać** — target to 3.22, gdzie `geopandas`/`pandas` mogą nie istnieć. Kod używa wyłącznie stdlib + PyQGIS + `osgeo` |

### 2.1 Lekcje z produkcyjnych uruchomień r5r (`tools/`, sierpień 2026)

Trzy błędy już raz kosztowały czas i jeden z nich **trafił na produkcję**. PRD projektuje je na
wylot; agent nie ma prawa ich powtórzyć.

| Lekcja | Dowód | Konsekwencja dla v0.1 |
|---|---|---|
| **Cicha degradacja do walk-only.** Gdy 0 kursów GTFS jest aktywnych w zadanej dacie, R5 **nie zgłasza błędu** — zwraca wyniki „tylko pieszo" dla każdego origin i każdej godziny | GZM: release miał `service_id` aktywny wyłącznie 2026-08-28, data zahardkodowana na 2026-08-24; błędny wynik był opublikowany do 2026-08-31 | Walidacja daty to **twarda blokada**, nie ostrzeżenie (§5.3), plus **detektor walk-only po przebiegu** (§5.8) |
| **`max_walk_time` to największa dźwignia wydajności, nie parametr kosmetyczny.** Bez limitu R5 przeszukuje nieograniczony promień pieszy dla każdego dojścia/odejścia/przesiadki | GZM 2026-08-29: cap na 45 min (= największy cutoff) dał **10,2× przyspieszenie** (1,14 → 0,11 s/origin) przy **0,0000%** różnicy powierzchni izochron | Domyślna wartość **wyprowadzana**, nie stała: `max_walk_time = max_trip_duration` (macierz) lub `max(cutoffs)` (dostępność). Cap na tej wartości jest **bezstratny** — noga piesza dłuższa niż całe okno nie może należeć do podróży mieszczącej się w oknie |
| **Koszt skaluje się złożonością sieci, nie liczbą origins.** Warszawa: 668 origins kosztowało 2,4–3,4× więcej na origin niż miasta z 1350–1633 origins | benchmark CI 2026-08-26: warszawa 0,171 vs gdansk 0,071 s/origin-godzinę; Warszawa OOM przy 2546 origins w jednym wywołaniu (`FastRaptorWorker.copyMultiRoundState`) | Szacowanie czasu **musi opierać się na pomiarze na próbce** tej konkretnej sieci (§5.9), nigdy na przeliczniku „ms × liczba origins". Batch ogranicza pamięć **niezależnie** od wielkości miasta |

Dodatkowo, jako punkt odniesienia dla pozycjonowania obu wtyczek: ten sam benchmark mierzy
`easyotp:generateisochrones` na **3,0 s/origin-godzinę** (dominuje start JVM + serwera OTP na
wywołanie) wobec **0,05–0,17 s/origin-godzinę** dla r5r/R5. To **20–60×** różnicy i to jest
powód istnienia tej wtyczki.

## 3. Architektura

### 3.1 Podział odpowiedzialności

```
QGIS / Python                          proces Java (jedyny plik .java)        R5
─────────────────────────────────      ──────────────────────────────        ──────────────
parametry Processing                   czyta job.json                        TransportNetwork
 → job.json (temp)          ────────►  buduje RegionalTask                   TravelTimeComputer
 uruchomienie procesu                  pętla po origins w zakresie           OneOriginResult
 parsowanie stdout (postęp)  ◄────────  PROGRESS/INFO/ERROR na stdout
 anulowanie = kill(pid)                pisze CSV
 CSV → warstwa QGIS         ◄────────  DONE <plik> <wiersze>
 dostępność, izochrony, statystyka strefowa, klasyfikacja, style, raporty
```

**Reguła podziału:** Java robi wyłącznie routing. Wszystko inne — Python.
Jeśli agent rozważa dopisanie czegoś do Javy, co da się policzyć z macierzy czasów,
odpowiedź brzmi nie.

### 3.2 Kontrakt runnera (`easy_r5/java/EasyR5Runner.java`)

Wywołanie (dwa równoważne tryby, patrz M1):

```
java -Xmx<heap> -cp <r5-all.jar>            <cacheDir>/EasyR5Runner.java <job.json>   # source launcher
java -Xmx<heap> -cp <r5-all.jar>;<cacheDir> EasyR5Runner              <job.json>   # skompilowany
```

**Musi zostać jednym plikiem** (jedna jednostka kompilacji; Java 21 nie ma multi-file source
programs). Klasy pakietowo-prywatne w tym samym pliku są OK.

#### Protokół stdout (jedna linia = jedna wiadomość, UTF-8, `\n`)

```
INFO      <tekst>                     — do logu Processing (feedback.pushInfo)
PROGRESS  <done> <total>              — pasek postępu; nie rzadziej niż co 1 s
WARN      <kod> <tekst>               — ostrzeżenie (np. UNLINKED_POINTS)
ERROR     <kod> <tekst>               — błąd; runner kończy się kodem 1
RESULT    <klucz>=<wartość>           — pojedynczy fakt (dla command=info)
DONE      <ścieżka> <liczba_wierszy>  — sukces; ostatnia linia, kod wyjścia 0
```

Kody błędów (stabilne, Python mapuje je na komunikaty dla użytkownika):
`NETWORK_VERSION_MISMATCH`, `NETWORK_READ_FAILED`, `OUT_OF_MEMORY`, `NO_POINTS_LINKED`,
`DATE_NO_SERVICE`, `BAD_JOB_SPEC`, `IO_ERROR`.

#### `command: "build"`

```json
{
  "command": "build",
  "osm": "C:/data/gdansk.osm.pbf",
  "gtfs": ["C:/data/gdansk_gtfs.zip"],
  "out_network": "C:/cache/<hash>/network.dat",
  "out_summary": "C:/cache/<hash>/network.json"
}
```

`network.json` (czytany przez UI, m.in. do walidacji daty):

```json
{
  "r5_version": "7.6", "network_format_version": "nv4",
  "built_at": "2026-09-02T14:22:08", "timezone": "Europe/Warsaw",
  "feeds": ["gdansk_gtfs"], "stops": 1619, "trip_patterns": 573,
  "street_vertices": 196913,
  "bounds": {"min_lon": 18.3, "min_lat": 54.2, "max_lon": 18.9, "max_lat": 54.5},
  "service_days": {"2026-08-24": 4212, "2026-08-25": 4230, "...": 0}
}
```

`service_days` = **liczba kursów aktywnych w danym dniu** dla każdego dnia w zakresie feedu
(cap 90 dni). To ono, a nie udział `service_id`, rozstrzyga, czy data ma sens.

#### `command: "matrix"`

```json
{
  "command": "matrix",
  "network": ".../network.dat",
  "origins": ".../origins.csv",
  "destinations": ".../destinations.csv",
  "origin_range": [0, 500],
  "date": "2026-08-25",
  "departure_time": "07:00",
  "time_window_minutes": 120,
  "percentiles": [50],
  "max_trip_duration_minutes": 90,
  "max_walk_time_minutes": 90,
  "walk_speed_kmh": 3.6,
  "bike_speed_kmh": 12.0,
  "max_rides": 3,
  "monte_carlo_draws": 5,
  "access_modes": ["WALK"],
  "egress_modes": ["WALK"],
  "direct_modes": ["WALK"],
  "transit_modes": ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"],
  "write_unreachable": false,
  "out_csv": ".../matrix_000.csv"
}
```

Mapowanie na `RegionalTask` — **przepis sprawdzony w spike'u, nie zmieniaj bez powodu**:

```java
r.scenario = new Scenario(); r.scenario.id = "id"; r.scenarioId = "id";
r.zoneId = network.getTimeZone();
r.fromLat / r.fromLon        = origin
r.walkSpeed                  = walk_speed_kmh / 3.6f      // R5 chce m/s
r.streetTime = r.maxTripDurationMinutes = max_trip_duration_minutes
r.maxWalkTime = max_walk_time_minutes; r.maxRides; r.bikeTrafficStress = 3
r.directModes / accessModes / egressModes = EnumSet<LegMode>
r.transitModes               = EnumSet<TransitModes>
r.date                       = LocalDate
r.fromTime                   = sekundy od północy
r.toTime                     = fromTime + time_window_minutes * 60
r.monteCarloDraws; r.makeTauiSite = false;
r.recordTimes = true; r.recordAccessibility = false;
r.percentiles                = int[] (≤5, rosnąco, 1..99)
r.destinationPointSets       = new PointSet[]{ freeFormPointSet }
new TravelTimeComputer(r, network).computeTravelTimes()
```

**`max_walk_time_minutes` — nie jest opcjonalne i nie jest kosmetyczne.** R5 bez limitu
przeszukuje nieograniczony promień pieszy przy każdym dojściu, odejściu i przesiadce; to był
faktyczny sterownik kosztu GZM (§2.1). Runner **zawsze** ustawia `r.maxWalkTime`. Python
wyprowadza domyślną wartość jako `max_trip_duration_minutes` (macierz) lub `max(cutoffs)`
(dostępność) — cap na tej wartości jest bezstratny, bo pojedyncza noga piesza dłuższa niż całe
okno podróży nie może należeć do podróży mieszczącej się w tym oknie. Wartość **niższa** niż
ta granica jest dopuszczalna, ale to już świadomy kompromis „szybciej za cenę utraty tras
z długim dojściem" i UI musi to powiedzieć wprost.

`FreeFormPointSet` budujemy z `DataOutputStream` w kolejności: `writeInt(n)`, n×`writeUTF(id)`,
n×`writeDouble(lat)`, n×`writeDouble(lon)`, n×`writeDouble(opportunity)` — opportunity w v0.1
zawsze `1.0` (liczy się w Pythonie). **Pointset budujemy raz na proces** i współdzielimy
między origins — to jest ta oszczędność 914 ms → 39 ms.

CSV wynikowy (format długi, nagłówki zgodne z r5r dla porównywalności):

```
from_id,to_id,travel_time_p50[,travel_time_p85,...]
```

Domyślnie wiersze tylko dla par osiągalnych (`tt <= max_trip_duration_minutes`).
`Integer.MAX_VALUE` nigdy nie trafia do pliku.

#### `command: "info"`

Wczytuje `network.dat` i wypisuje `RESULT` z zawartością `network.json` (bez przebudowy) —
używane przez `TestR5Setup` i przy walidacji daty dla istniejącej sieci.

### 3.3 Moduły Pythona (`easy_r5/core/`)

| Moduł | Odpowiedzialność |
|---|---|
| `runner.py` | budowa linii komend, uruchomienie procesu, parsowanie protokołu stdout, postęp, anulowanie, sprzątanie w `finally`, mapowanie kodów błędów na komunikaty |
| `job_spec.py` | budowa i walidacja JSON-a zadania (percentyle ≤5 i rosnące, tryby, zakres dat) |
| `network_cache.py` | katalog cache po `sha256(osm) + sha256(gtfs...) + r5_version`; odczyt/zapis `network.json`; wykrycie nieaktualnej wersji |
| `java_env.py` | ścieżki do JDK i jara z QSettings, weryfikacja SHA-256, kompilacja runnera do cache, detekcja RAM i dobór `-Xmx` |
| `points.py` | warstwa QGIS → CSV origins/destinations (reprojekcja do EPSG:4326, walidacja geometrii, stabilne `id`) |
| `matrix.py` | scalanie CSV z batchy, wczytanie do struktury wynikowej, budowa warstw/tabel |
| `accessibility.py` | dostępność skumulowana (step / logistic / exponential) liczona z macierzy |
| `settings.py` | klucze QSettings **z własnym prefiksem** `easy_r5/…` — nigdy wspólne z easy-OTP |

Testy jednostkowe (`easy_r5/test/`) muszą działać **poza QGIS-em** dla: `job_spec`,
`network_cache`, `accessibility`, parsera protokołu i doboru heap-u. Wzorzec: `easy_otp/test/`.

### 3.4 Zarządzanie pamięcią i batchowaniem

- `-Xmx` domyślnie `min(0.6 × RAM_total, 12 GB)`, minimum 2 GB; użytkownik może nadpisać
  (parametr zaawansowany + QSettings). Wykrycie RAM: Windows `ctypes.GlobalMemoryStatusEx`,
  Linux `/proc/meminfo`, macOS `sysctl hw.memsize`. Brak detekcji → 4 GB i `pushWarning`.
- Batch origins: domyślnie **500**, parametr zaawansowany (100–5000). Każdy batch = jeden
  proces = jeden plik CSV; Python scala. Anulowanie ubija bieżący proces i przerywa pętlę.
- Wykrycie OOM: kod wyjścia ≠ 0 **lub** `OutOfMemoryError` w stderr → komunikat:
  *„R5 zabrakło pamięci (heap X GB). Zmniejsz gęstość siatki origins, zmniejsz batch
  (obecnie N) albo zwiększ heap w ustawieniach wtyczki."* — nigdy surowy stack trace.
  Precedens z `tools/`: Warszawa 500 m padała przy 12 GB, ratunkiem była siatka 1000 m.

## 4. Algorytmy Processing (v0.1)

Provider: `id="easyr5"`, `name="Easy-R5"`. Grupy: `Setup`, `Diagnostics`, `Analysis`.
Wszystkie stringi widoczne dla użytkownika w `self.tr()`.

### 4.1 `DownloadR5` (Setup)

| Parametr | Typ | Domyślnie |
|---|---|---|
| `TARGET_FOLDER` | Folder | `~/easy-r5` |
| `DOWNLOAD_JDK` | Boolean | True |
| `DOWNLOAD_R5` | Boolean | True |

Działanie: Temurin **21 JDK** przez API Adoptium (`feature_version=21`, `image_type=jdk`,
`os`/`architecture` z platformy) + `r5-v7.6-all.jar` z GitHub Releases. Weryfikacja
**SHA-256** (stała w kodzie; release R5 publikuje tylko `.md5`/`.sha1`, więc sumę wyliczamy
raz i pinujemy — nie osłabiamy do MD5). Zapis ścieżek do QSettings. Kompilacja runnera do
`<TARGET_FOLDER>/runner_cache/`. Komunikat o rozmiarze pobrania (~240 MB) w `shortHelpString`.

**Wzorzec:** `easy_otp/algorithms/download_jre.py` — bezpieczne rozpakowanie ZIP, brak
wymogu admina, `nosec` tam gdzie Bandit krzyczy.

### 4.2 `TestR5Setup` (Diagnostics)

Sprawdza kolejno i raportuje **każdy krok osobno** (nie „wszystko albo nic"):
JDK istnieje i `-version` zwraca 21+ → jar istnieje i SHA-256 się zgadza → runner kompiluje
się/jest w cache → `command=info` na wskazanej sieci (opcjonalnie) → jedno trywialne
zapytanie o czas przejazdu. Wynik: tekst + `RESULT`-y w logu.

### 4.3 `BuildNetwork` (Setup)

| Parametr | Typ | Domyślnie |
|---|---|---|
| `OSM_PBF` | File (`*.osm.pbf`) | — |
| `GTFS_FOLDER` | Folder (wszystkie `*.zip`) | — |
| `CACHE_FOLDER` | Folder | z QSettings |
| `FORCE_REBUILD` | Boolean (advanced) | False |

Wynik: ścieżka do `network.dat` + wypisane w logu podsumowanie z `network.json`
(feedy, przystanki, zakres dat z `service_days`, strefa czasowa, bounds).
Cache: pomiń budowę, jeśli hash wejść + wersja R5 się zgadzają.

### 4.4 `RunTravelTimeMatrix` (Analysis) — algorytm flagowy

| Parametr | Typ | Domyślnie / uwagi |
|---|---|---|
| `NETWORK` | File `network.dat` | z cache |
| `ORIGINS` | VectorLayer (punkty) | reprojekcja do 4326 |
| `ORIGIN_ID_FIELD` | Field | opcjonalne; brak → `$id` |
| `DESTINATIONS` | VectorLayer (punkty) | jak wyżej |
| `DEST_ID_FIELD` | Field | jw. |
| `DATE` | String `yyyy-MM-dd` | walidacja przez `service_days` |
| `DEPARTURE_TIME` | String `HH:mm` | `07:00` |
| `TIME_WINDOW` | Number (min) | `120` |
| `PERCENTILES` | String, lista | `50`; **maks. 5**, rosnąco, 1–99 |
| `MAX_TRIP_DURATION` | Number (min) | `90` |
| `MAX_WALK_TIME` | Number (min), advanced | **puste = `MAX_TRIP_DURATION`** (bezstratny cap). Wartość mniejsza przyspiesza, ale gubi trasy z długim dojściem — ostrzeżenie w logu |
| `WALK_SPEED` | Number (km/h) | `3.6` |
| `MAX_RIDES` | Number | `3` |
| `MODE` | Enum | `TRANSIT+WALK` (dom.), `WALK`, `BICYCLE`, `CAR` |
| `MONTE_CARLO_DRAWS` | Number (advanced) | `5` |
| `BATCH_SIZE` | Number (advanced) | `500` |
| `ESTIMATE_FIRST` | Boolean (advanced) | `True` — pomiar na próbce przed pełnym przebiegiem (§5.9) |
| `JAVA_HEAP_GB` | Number (advanced) | auto |
| `OUTPUT_CSV` | FileDestination | format długi |
| `OUTPUT_LAYER` | VectorDestination (opcjonalny) | linie OD albo tabela |

Zachowanie: twarda walidacja daty **przed** startem (§5.3), pomiar na próbce (§5.9), detektor
walk-only po przebiegu (§5.8). Postęp z `PROGRESS`. Anulowanie w każdej chwili. Pary nieosiągalne pomijane
(lub `NULL`, gdy użytkownik chce pełną macierz — parametr `INCLUDE_UNREACHABLE`, advanced).

### 4.5 `RunAccessibility` (Analysis)

Nadbudowa nad macierzą; **liczona w Pythonie** (R5 natywnej ścieżki nie udostępnia — sekcja 2).

| Parametr | Typ | Domyślnie |
|---|---|---|
| jak w `RunTravelTimeMatrix` | | |
| `OPPORTUNITY_FIELDS` | Fields (wielokrotny wybór z DESTINATIONS) | — |
| `CUTOFFS` | String, lista minut | `15,30,45,60` |
| `DECAY` | Enum | `STEP` (dom.), `LOGISTIC`, `EXPONENTIAL` |
| `MAX_WALK_TIME` | Number (min), advanced | puste = `max(CUTOFFS)` — dla `STEP` bezstratne i najszybsze; dla `LOGISTIC`/`EXPONENTIAL` (ogon poza cutoffem ma wagę) puste = `MAX_TRIP_DURATION` |
| `OUTPUT_LAYER` | VectorDestination | kopia ORIGINS + pola wyniku |

Pole wynikowe: `acc_<opportunity>_p<percentyl>_c<cutoff>` (np. `acc_total_p50_c30`).
Dodatkowo pola metody: `r5_version`, `run_date`, `departure_time`, `time_window`,
`percentile`, `decay` — **wymagane**, żeby mapa dała się później zinterpretować.
CSV długi (`id,opportunity,percentile,cutoff,accessibility`) — **ten sam układ co r5r**,
co umożliwia diff w M4.

### 4.6 `GenerateIsochrones` (Analysis)

Siatka regularna destinations (parametr `GRID_SPACING`, domyślnie 250 m, w metrycznym CRS
lokalnym) → macierz z 1 origin → raster czasu przejazdu (`gdal:gridnearest`/rasteryzacja
punktów) → `gdal:contour_polygon` dla `CUTOFFS`. Wynik: warstwa poligonowa z polami
`cutoff_min`, `origin_id`, `departure_time`, `percentile`.

`MAX_WALK_TIME` domyślnie `max(CUTOFFS)` — dla izochron to cap **bezstratny** i jednocześnie
największa dźwignia wydajności (GZM: 10,2×, §2.1). Konturowanie potrafi się wywrócić na
mocno pofragmentowanej powierzchni (r5r trafił na deterministyczny błąd isoband dla jednej
godziny w Warszawie); przy błędzie GDAL-a algorytm ma zaraportować, której wartości cutoff
dotyczy, i dokończyć pozostałe, zamiast przerywać całość.

**Uzasadnienie:** R5 nie produkuje poligonów; ani r5r, ani r5py, ani Conveyal Analysis nie
robią tego w Javie. Konturowanie zostaje w QGIS.

### 4.7 `GenerateHexGrid` (Analysis)

Port z `easy_otp/algorithms/generate_hex_grid.py` bez zmian semantyki (siatka jest
niezależna od silnika). Uzasadnienie duplikacji: użytkownik nie może być zmuszany do
instalacji drugiej wtyczki dla siatki, która jest wejściem do wszystkiego.

## 5. Reguły UX i obsługi błędów (obowiązkowe)

1. **Żaden stack trace Javy nie trafia do użytkownika.** Każdy kod `ERROR` ma polski/angielski
   komunikat z konkretną radą. Pełny log Javy idzie do `feedback.pushDebugInfo`.
2. **Metoda zapisana w wyniku.** Każda warstwa wynikowa niesie pola: `r5_version`,
   `network_hash`, `run_date`, `departure_time`, `time_window`, `percentile`, `modes`.
   Dwie mapy różniące się tylko percentylem wyglądają identycznie — to główny sposób,
   w jaki użytkownik może źle odczytać własny wynik.
3. **Walidacja daty przed startem = twarda blokada.** Jeśli `service_days[DATE] == 0`,
   algorytm **nie startuje**: „W dniu `<data>` feed nie ma żadnych aktywnych kursów.
   Najbliższe dni z kursami: `<lista 3>`." Powód: R5 w takiej sytuacji **nie zgłasza błędu**,
   tylko cicho zwraca wyniki pieszo-only (§2.1, przypadek GZM). Ominięcie wyłącznie przez
   jawny parametr zaawansowany `ALLOW_NO_SERVICE=True`, opisany jako diagnostyczny.
   Podstawą jest liczba **kursów** aktywnych w dniu (z `calendar.txt` **i**
   `calendar_dates.txt`), nigdy udział `service_id` — feedy typu Gdańsk/GZM mają po jednym
   `service_id` na dzień i heurystyka „udziału" daje fałszywy alarm albo fałszywy spokój.
4. **Anulowanie działa zawsze**: `feedback.isCanceled()` sprawdzane między batchami i przy
   każdej linii `PROGRESS`; proces ubijany; pliki tymczasowe sprzątane w `finally`.
5. **Nieosiągalne = NULL**, nigdy 2147483647 i nigdy 0.
6. **Ostrzeżenie o niedopiętych punktach** (`WARN NO_POINTS_LINKED` / częściowe) — z liczbą
   i podpowiedzią o zbyt małym zasięgu OSM albo punktach poza siecią.
7. **Ostrzeżenie o kosztowności** przed startem, na podstawie pomiaru z §5.9 — nie z
   przelicznika teoretycznego. Powyżej ~30 min: wyraźne `pushWarning` z liczbą, nie blokada.

8. **Detektor walk-only po przebiegu (obowiązkowy).** Dla trybu `TRANSIT+WALK` runner liczy
   i raportuje `RESULT transit_used_pairs=<n>` — liczbę par OD, których czas przejazdu jest
   krótszy niż czas dojścia pieszo dla tej samej pary. Jeśli **0**, Python przerywa z błędem:
   „Wynik nie zawiera ani jednej podróży transportem — R5 policzył same trasy piesze.
   Najczęstsza przyczyna: data bez kursów albo GTFS niedopasowany do sieci." To druga,
   niezależna od walidacji daty siatka bezpieczeństwa na dokładnie ten błąd, który w `tools/`
   przeszedł do publikacji.

9. **Pomiar przed przebiegiem (`ESTIMATE_FIRST`, domyślnie włączony).** Przed pełnym
   uruchomieniem runner liczy próbkę **15 origins rozłożonych systematycznie** po całym
   zbiorze i raportuje zmierzony `s/origin` oraz ekstrapolację na cały zbiór.
   Powód: koszt zależy od **złożoności sieci**, nie od liczby origins — Warszawa z 668
   origins była 2,4–3,4× droższa na origin niż Gdańsk z 1389 (§2.1). Wzorzec:
   `tools/isochrones_lodz/dry_run_isochrone_city.R`, który powstał dokładnie po tym, jak dwa
   przebiegi CI dla Warszawy padły po ~4 h każdy. Próbka kosztuje sekundy i chroni godziny.

## 6. Kamienie milowe

Rozwój pod `0.0.x`, `experimental=True`. Bump do **0.1.0** dopiero po M5.
Po każdym kamieniu: test w QGIS → review → poprawki → commit.

### M1 — szkielet wtyczki + silnik na dysku
**Zakres:** struktura wtyczki (`__init__.py`/`classFactory`, `easy_r5_plugin.py` z
`initGui`/`unload`, `provider.py`, `metadata.txt`, `LICENSE`, `resources/icon.svg`),
`DownloadR5`, `TestR5Setup`, runner z `command=info`.
**Kryteria akceptacji:**
- Wtyczka ładuje się w QGIS 3.22 i 3.40, provider widoczny w Toolbox, `unload()` czyści.
- `DownloadR5` pobiera JDK 21 i jar, weryfikuje SHA-256, zapisuje ścieżki w QSettings,
  kompiluje runner do cache.
- `TestR5Setup` przechodzi wszystkie kroki na czystym profilu QGIS.
- Testy jednostkowe: `job_spec`, parser protokołu, dobór heap-u.
**Weryfikacja przez człowieka:** instalacja z ZIP na czystym profilu; brak praw admina;
odinstalowanie nie zostawia procesu Javy.

### M2 — budowa sieci
**Zakres:** `command=build` w runnerze, `BuildNetwork`, `network_cache`, `service_days`.
**Kryteria akceptacji:**
- Sieć Gdańska (`gdansk.osm.pbf` + `gdansk_gtfs.zip`) buduje się i `network.json` raportuje
  1619 przystanków, 573 tripPatterns, strefę `Europe/Warsaw`, feed `gdansk_gtfs`.
- Powtórne uruchomienie z tymi samymi wejściami **nie przebudowuje** sieci.
- Zmiana wersji R5 unieważnia cache; `NETWORK_VERSION_MISMATCH` daje czytelny komunikat.
- `service_days` dla `2026-08-25` > 0, dla daty spoza feedu = 0.
**Weryfikacja przez człowieka:** budowa sieci dla własnego miasta; sprawdzenie, że OOM przy
dużym PBF daje radę, a nie stack trace.

### M3 — macierz czasów przejazdu
**Zakres:** `command=matrix`, `RunTravelTimeMatrix`, batchowanie, postęp, anulowanie,
obsługa OOM, `points.py`, `matrix.py`.
**Kryteria akceptacji:**
- 1389 origins × 956 destinations (Gdańsk, 07:00 +120 min, P50, cap 90) kończy się
  **poniżej 2 minut** na maszynie referencyjnej i produkuje CSV.
- Anulowanie w połowie: proces Javy znika z listy procesów w ≤2 s, brak plików tymczasowych.
- Percentyle: 6 wartości → błąd walidacji **przed** uruchomieniem Javy.
- Wynik dla znanego origin jest zgodny z sondą (`docs/reference/probe/`) co do minuty.
- **Data bez kursów blokuje start** i podpowiada najbliższe dni z kursami (test: 2026-01-01
  na feedzie Gdańska).
- **Detektor walk-only** zgłasza błąd, gdy żadna para nie korzysta z transportu (test:
  uruchomienie z `ALLOW_NO_SERVICE=True` na dacie bez kursów musi skończyć się tym błędem,
  a nie cichym wynikiem).
- `MAX_WALK_TIME` puste → runner dostaje wartość równą `MAX_TRIP_DURATION` (widoczne w logu
  job spec), nigdy `null`/brak limitu.
- `ESTIMATE_FIRST` raportuje s/origin i ekstrapolację przed pełnym przebiegiem.
**Weryfikacja przez człowieka:** porównanie kilku par OD z wyszukiwarką przewoźnika;
uruchomienie na własnej warstwie punktowej w innym CRS.

### M4 — dostępność + odtworzenie wyniku referencyjnego
**Zakres:** `accessibility.py`, `RunAccessibility`, style warstw.
**Kryteria akceptacji (najważniejsze w całym PRD):**
- Uruchomienie dla Gdańska z parametrami `run_accessibility.R` (07:00, okno 120 min,
  cap 90 min, `step`, cutoffy 15/30/45/60, `gdansk_hex_origins.csv`,
  `gdansk_service_destinations.csv`) daje wynik **porównywalny z
  `gdansk_service_accessibility.csv`**: identyczny układ kolumn, ta sama liczba wierszy,
  a różnice wartości wyjaśnione i udokumentowane (Monte Carlo, wersja R5 7.5.1 vs 7.6,
  data odjazdu — data użyta przez r5r nie jest zapisana w repo i trzeba ją odtworzyć).
- Warstwa wynikowa niesie komplet pól metody z sekcji 5.2.
**Weryfikacja przez człowieka:** mapa dostępności Gdańska obok tej z `tools/` — wzrokowo
ten sam wzorzec przestrzenny.

### M5 — izochrony + wydanie 0.1.0
**Zakres:** `GenerateIsochrones`, `GenerateHexGrid`, style, README, `metadata.txt` (changelog),
tłumaczenie PL (`.ts`/`.qm`), `KNOWN_ISSUES.md`.
**Kryteria akceptacji:**
- Izochrony 15/30/45 min z jednego punktu w Gdańsku wyglądają sensownie i nie mają dziur
  wynikających z rasteryzacji.
- Wtyczka przechodzi walidację pakietu QGIS (sekcja 7) i instaluje się z ZIP-a.
**Weryfikacja przez człowieka:** pełna ścieżka od zera na czystym profilu: pobierz → zbuduj →
policz → zobacz mapę.

## 7. Zgodność z repozytorium wtyczek QGIS (checklista)

Na podstawie oficjalnej dokumentacji PyQGIS (Plugins):

- [ ] `metadata.txt` w UTF-8, komplet pól: `name, qgisMinimumVersion, description, about,
      version, author, email, repository, tracker, homepage, category, icon, license, tags,
      experimental, hasProcessingProvider=yes`.
- [ ] `__init__.py` z `classFactory(iface)`; klasa wtyczki z `__init__`, `initGui`, `unload`.
- [ ] `unload()` wyrejestrowuje provider i rozłącza sygnały — bez wycieków przy przeładowaniu.
- [ ] `LICENSE` (GPL-3.0-or-later) w katalogu wtyczki.
- [ ] Tłumaczenia: `easy_r5.pro`, `i18n/easy_r5_pl.ts` → `.qm`; `tr()` z kontekstem = nazwa klasy.
- [ ] Zasoby z własnym prefiksem (bez kolizji z innymi wtyczkami).
- [ ] `experimental=True` do czasu wydania 0.1.0.
- [ ] Brak jakiegokolwiek `pip install` w kodzie wtyczki.
- [ ] Operacje długie w Processing (feedback + cancel), nic nie blokuje GUI w nieskończoność.

## 8. Ryzyka

| Ryzyko | Prawdopodobieństwo | Mitigacja |
|---|---|---|
| R5 zmieni API przy podbiciu wersji | wysokie (upstream tak zapowiada) | pin wersji, minimalna powierzchnia runnera, `command=info` jako smoke test po podbiciu |
| Runner przekroczy jeden plik `.java` | średnie | trzymać w Javie tylko routing; przy przekroczeniu — osobne repo MIT z jarem (jak `easy-GTFS-RT`) |
| `sun.misc.Unsafe` zniknie w przyszłej Javie i Kryo padnie | średnie, odległe | pin na Temurin 21; nie używać `java` z PATH |
| OOM u użytkownika na dużym obszarze | wysokie | auto-heap, batch, komunikat z radą, dokumentacja gęstości siatki |
| **Cichy walk-only** — użytkownik publikuje mapę policzoną bez transportu | wysokie (zdarzyło się w `tools/`) | twarda walidacja daty (§5.3) **plus** niezależny detektor po przebiegu (§5.8); dwa mechanizmy, bo jeden już raz zawiódł |
| Nieograniczony promień pieszy zjada wydajność | wysokie, jeśli agent nie ustawi `maxWalkTime` | runner ustawia go **zawsze**; wartość wyprowadzana, test jednostkowy na job spec |
| Rozbieżność wyników vs r5r zinterpretowana jako błąd | średnie | M4 wymaga **udokumentowania** różnic, nie ich ukrycia |

## 9. Poza zakresem v0.1

Scenariusze sieciowe (modyfikacje R5); szczegółowe itineraria i `paths`; taryfy i pareto;
metryka „minut obsługi" z histogramów (v0.2 — mechanizm potwierdzony, ale wymaga własnego
projektu UI i nazewnictwa, żeby nie udawać metryki easy-OTP); GTFS-RT w jakiejkolwiek
postaci; `PopulationOverlay` i `PrepareStudentLayer` (zostają w easy-OTP, link krzyżowy);
`TemporalDensityResult`; wielowątkowość po stronie Javy (batch procesów wystarcza).

## 10. Materiały dla agenta

- `docs/notes/spike-r5-probe-2026-09-02.md` — pełny raport z pomiarów + kod sond.
- `docs/reference/probe/Probe.java`, `Probe3.java` — działający kod wywołujący R5;
  **od tego zaczyna się `EasyR5Runner.java`**, nie od pustego pliku.
- `docs/notes/r5-engine-primer.md` — mapa klas R5 i pułapki.
- `../easy-OTP/easy_otp/` — wzorce: `download_jre.py`, `otp_server.py` (zarządzanie procesem),
  `generate_hex_grid.py`, `provider.py`, układ testów.
- `tools/accessibility_cities/` (po migracji) — dane referencyjne i parametry;
  `gdansk/` ma komplet: `network.dat`, origins, destinations i wynik r5r do porównania w M4.
- `tools/isochrones_lodz/` (po migracji) — **przeczytaj nagłówki tych plików, zanim napiszesz
  kod**: `compute_isochrones_city.R` (cap `max_walk_time`, batching, historia OOM Warszawy
  i cichego walk-only GZM), `verify_departure_date.R` (logika walidacji daty, w tym pułapka
  zależnego od lokalizacji `weekdays()`), `benchmark_summary.csv` (zmierzone przepustowości
  r5r vs wtyczka easy-OTP).
