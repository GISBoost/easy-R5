# CLAUDE.md — Easy-R5 (wtyczka QGIS)

## Czym jest projekt
`Easy-R5` to wtyczka QGIS licząca dostępność transportową na silniku **Conveyal R5**.
Siostra [`easy-OTP`](https://github.com/GISBoost/easy-OTP): ten sam użytkownik, ten sam
styl pracy, inny silnik i inne mocne strony. R5 liczy macierze czasów przejazdu i
dostępność skumulowaną **jeden-do-wielu / wiele-do-wielu w oknie odjazdów**, czyli to,
czego OTP 1.5 nie potrafi zrobić szybko. Docelowo trafia do oficjalnego repozytorium
wtyczek QGIS.

Repo zawiera też `tools/` — samodzielne narzędzia badawcze (analizy dostępności i
izochron dla 6+ miast PL), migrowane z easy-OTP. Patrz ADR-0003.

## Stan projektu (2026-09-02)
**Faza przygotowawcza — nie ma jeszcze kodu wtyczki.** Zebrane są konteksty i decyzje;
ADR-y mają status *Proposed*. **Nie zaczynaj implementacji, dopóki ADR-0001 nie jest
Accepted** — od niego zależy cała warstwa `core/`.

## Źródło prawdy
- **`docs/adr/`** — decyzje architektoniczne. Zacznij od `0001-r5-binding.md` (jak
  wołamy R5), potem `0002-pinned-versions.md` (wersje) i `0003-migrate-r5-tools.md`
  (migracja narzędzi z easy-OTP).
- **`docs/notes/r5-engine-primer.md`** — jak działa R5, które klasy Javy się liczą,
  gdzie są twarde limity. Czytaj **przed** dotknięciem silnika.
- **`docs/notes/bindings-comparison.md`** — r5r vs r5py vs własny runner, z dowodami.
- **`docs/notes/r5-vs-otp.md`** — czym Easy-R5 różni się od easy-OTP i czego **nie**
  portować.
- **`docs/notes/product-scope.md`** — dla kogo to jest i jakie algorytmy z tego wynikają.
- **`docs/notes/open-questions.md`** — co jest nierozstrzygnięte. Jeśli twoje zadanie
  dotyka pozycji z tej listy, rozstrzygnij ją eksperymentem albo zapytaj — nie zgaduj.
- **`CONTEXT.md`** — słownik pojęć. Używaj tych słów, nie synonimów.
- **Repo `easy-OTP`** (`../easy-OTP`) — wzorzec architektury wtyczki: `provider.py`,
  `algorithms/`, `core/`, `metadata.txt`, `DownloadJre`, zarządzanie procesem Javy,
  pasek postępu, anulowanie. **Kopiuj wzorce, nie kopiuj semantyki OTP.**

## Twarde ograniczenia (nie wolno złamać)
- QGIS minimum **3.22 LTR**. Tylko **PyQGIS** + biblioteki z dystrybucji QGIS.
- **ZERO `pip install`** w `easy_r5/`. Pobieranie binariów przy setupie (JDK, jar R5)
  jest dozwolone — tak samo jak `DownloadJre` w easy-OTP. Instalowanie pakietów
  Pythona do interpretera QGIS-a — nie. Dopuszczalne wyjątki, oba wąskie:
  1. `openpyxl` — **wyłącznie** dla `PreparePopulationLayer` / `PopulationOverlay`
     (PRD §4.8), ładowany dokładnie tak jak w easy-OTP (`core/dependencies.py`,
     wheel przez `urllib`, SHA-256, bez `pip`). **Potwierdzone przez Michała
     2026-09-03 (M5).** Bootstrap woła się z `EasyR5Plugin.initGui()` best-effort.
     Fallback rozpakowania: `easy_r5/_vendor/` (gitignored). Nie generalizuj —
     żaden inny pakiet ani żaden inny algorytm.
  2. plan B z ADR-0001 (JPype) — tylko jeśli ADR-0001 zostanie zmieniony świadomą decyzją.
- **ZERO R, ZERO GRASS** w kodzie wtyczki. (Reguła dotyczy `easy_r5/`; `tools/` jest
  z niej wyłączone — patrz niżej.)
- **R5 i Java: dokładnie wersje z ADR-0002** (dziś: `r5-v7.6-all.jar`, Temurin 21).
  Java uruchamiana pełną ścieżką do binarki, nie przez wersję systemową.
- **Nie dziel ustawień z easy-OTP.** Osobne klucze QSettings — user może mieć
  zainstalowane obie wtyczki, jedna z Javą 8, druga z 21.
- **Z easy-OTP nic nie zabieramy — tylko kopiujemy.** Algorytm potrzebny tu i tam
  istnieje w obu repo jako osobna implementacja. Żadnych importów między wtyczkami,
  wspólnych pakietów ani symlinków: zależność między wtyczkami w repozytorium QGIS
  jest gorsza niż duplikat. Kopie mogą się rozejść i to jest akceptowane.
  (Wyjątek historyczny: r5r-owe `tools/` **przeniesiono** w całości 2026-09-02,
  ADR-0003 — to była jednorazowa, zatwierdzona operacja, nie precedens.)
- Licencja: **GPLv3 lub nowsza** (`GPL-3.0-or-later`). R5 jest MIT — kompatybilne.
  Ewentualne repo towarzyszące (gdyby runner urósł do własnego jara) — MIT, jak
  `easy-GTFS-RT`.
- Kod, komentarze, docstringi, stringi UI i komunikaty commitów: **po angielsku**.
  Stringi widoczne dla użytkownika owijać w `self.tr()`. UI docelowo EN + PL.
- **R5 nie czyta GTFS-RT.** Nigdy nie projektuj algorytmu „realtime" w Easy-R5.
  Realtime wchodzi tu wyłącznie jako *zrealizowany statyczny GTFS* (P50/P85) z
  easy-OTP / `family_a_reconstruction`.

## Architektura (docelowa, skrót)
Wtyczka = provider Processing, sekcje jak w easy-OTP, **bez sekcji `Realtime/`**:

```
Setup/       — DownloadR5 (JDK 21 + jar R5), DownloadTransitData, BuildNetwork
Diagnostics/ — TestR5Setup
Analysis/    — RunTravelTimeMatrix (flagowy), RunAccessibility, GenerateIsochrones,
               PreparePopulationLayer, PopulationOverlay, CompareScenarios,
               (później) RunScenarioAnalysis
```

**Bez własnego generatora siatki heksagonalnej** — easy-OTP-owy `GenerateHexGrid` to
opakowanie na `native:creategrid`; nie powielamy generycznego algorytmu QGIS, tylko
opisujemy przepis w README (PRD §4.7).

Logika w `core/`: `r5_runner` (uruchamianie procesu Javy, progress, anulowanie),
`job_spec` (JSON in), `results_reader` (CSV/JSON out), `network_cache`, `settings`,
`time_utils`, `raster_processing`, `zonal`. Duża część tych modułów to port z
easy-OTP — sprawdź tam **zanim napiszesz od zera**.

`easy_r5/java/EasyR5Runner.java` — jedyny plik Javy. Musi zostać **jednym plikiem**
(single-file source launcher do Javy 21 kompiluje jedną jednostkę kompilacji).
Zakres: `build`, `matrix`, później `itinerary`. Wszystko, co nie jest routingiem
(siatki, konturowanie izochron, statystyka strefowa, klasyfikacja, style, raporty),
robi Python/QGIS.

## Workflow pracy (przestrzegaj zawsze)
- **Jeden kamień milowy na raz.** Nie wybiegaj naprzód.
- Przy zmianie dotykającej 3+ plików: **najpierw plan, potem kod.**
- **Nie zgaduj** — gdy coś jest niejasne, sprawdź w `docs/notes/`, a jak i tam nie ma,
  zapytaj. Wpisy oznaczone `[verify]` to hipotezy, nie fakty.
- Nie dodawaj frameworków, zależności ani „ulepszeń" spoza ustalonego zakresu.
- Po każdym kamieniu milowym: test w QGIS → review → napraw blokery → **commit**
  (Conventional Commits: `feat:`, `fix:`, `chore:`).
- **GitHub CLI**: na tym komputerze `gh` w PATH to inne narzędzie Python — zawsze pełna
  ścieżka: `& "C:\Program Files\GitHub CLI\gh.exe"`.
- Nie twórz automatycznie nowych branchy — tylko gdy user o to poprosi.
- Jeśli używasz Pythona w terminalu, wołaj `py`, nie `python`.

## Polityka Known Issues (przestrzegaj zawsze)
- Każdy nowy wpis w `KNOWN_ISSUES.md` lub sekcji „Known issues" w README MUSI mieć
  odpowiadające **GitHub Issue** — utwórz przez `gh.exe issue create` albo wypisz
  gotową komendę dla użytkownika.
- NIE twórz nowych etykiet; używaj istniejących (`bug`, `enhancement`,
  `documentation`, `wontfix`). Pomiń etykietę, jeśli nie istnieje.
- Po utworzeniu issue zaktualizuj `KNOWN_ISSUES.md` numerem i linkiem.
- **Nigdy nie commituj wpisu Known Issue bez numeru issue.**

### Struktura GitHub Issue dla Known Issue
**Title** (max 72 znaki): `<krótki opis>`

**Body** (po angielsku):
```
## Problem
<What breaks and under what conditions.>

## QGIS version(s) affected
<e.g. 3.22 on Windows>

## Steps to reproduce
<Steps, or "N/A — always fails".>

## Workaround
<Workaround, or "None".>

## Status
<Known / Under investigation / Fix planned for vX.Y / Won't fix>
```

## Czego NIE testuje agent (testuje człowiek)
Claude Code nie ma dostępu do Javy 21, jara R5 ani zbudowanej sieci w sensie
uruchomienia pełnego pipeline'u. **Nie zakładaj, że kod „działa".** Po każdym kamieniu
wypisz jasno, co użytkownik ma ręcznie zweryfikować w QGIS i jak.

**Wyjątek: MCP QGIS jest dostępny** (`mcp__qgis__*` — projekt, warstwy, canvas,
Processing, zrzuty ekranu). Pozwala sterować żywym QGIS-em bez udziału użytkownika,
głównie do zadań kartograficznych/wizualizacyjnych i do `tools/`. Nie zmienia to reguły
wyżej dla pipeline'u R5/Javy.

## Gotchas (realne pułapki — pamiętaj)
- **Data bez kursów = cichy walk-only.** R5 nie zgłasza błędu, gdy w zadanej dacie nie ma
  aktywnych kursów GTFS — po prostu zwraca trasy piesze dla wszystkiego. Ten błąd już raz
  trafił na produkcję (GZM, sierpień 2026). Twarda walidacja daty **plus** niezależny
  detektor „czy cokolwiek pojechało transportem" po przebiegu. Liczymy **kursy aktywne
  w dniu** (z `calendar.txt` i `calendar_dates.txt`), nie udział `service_id`.
- **`maxWalkTime` ustawiaj ZAWSZE.** Bez limitu R5 przeszukuje nieograniczony promień pieszy
  przy każdym dojściu/odejściu/przesiadce. Cap na największym cutoffie jest bezstratny
  i dał zmierzone **10,2× przyspieszenie** przy 0,0000% różnicy wyniku (GZM).
- **Koszt zależy od złożoności sieci, nie od liczby origins.** Warszawa (668 origins) była
  2,4–3,4× droższa na origin niż Gdańsk (1389). Szacuj czas pomiarem na próbce tej sieci.
- **Percentyli maks. 5** (`MAX_PERCENTILES`), rosnąco, 1–99 — zweryfikowane, rzuca wyjątkiem.
- **Natywna dostępność R5 nie działa poza Conveyal Analysis** (`destinationPointSetKeys is
  null`). Dostępność liczymy w Pythonie z macierzy czasów.
- **Rozkład per minuta odjazdu jest dostępny**: `recordTravelTimeHistograms=true` +
  `TravelTimeResult.getHistogram(target)` → `int[120]`. To podstawa metryki „minut obsługi"
  (v0.2), ale to **nie jest** ta sama liczba co w easy-OTP — nie nazywaj jej tak samo.
- `FreeFormPointSet` buduj **raz na proces** i współdziel między origins: pierwszy origin
  kosztuje ~900 ms (linkowanie + `EgressCostTable`), każdy kolejny ~16–40 ms.
- **Pamięć to główny tryb awarii R5.** RAM ≈ liczba origins × złożoność sieci.
  Realny przypadek z `tools/`: Warszawa przy siatce 500 m padała na 12 GB sterty —
  ratunkiem była siatka 1000 m (668 origins) i batchowanie. GZM jest dużo droższy niż
  pojedyncze miasto. Sterta ustawiana **przed startem JVM** (`-Xmx` w komendzie).
  OOM ma trafić do użytkownika jako czytelna rada, nie jako stack trace Javy.
- `network.dat` zbudowany inną wersją R5 **nie wczyta się** (`NETWORK_FORMAT_VERSION`).
  Cache sieci kluczuj hashem wejść **plus** wersją R5.
- GTFS statyczny i „zrealizowany" (P50/P85) mają te same `trip_id`/`stop_id` — **nie
  mogą leżeć w jednym katalogu budowy sieci.** Jeden katalog na wariant.
- Jedno wywołanie `TravelTimeComputer` = **jeden origin**. Tam wpina się postęp
  i anulowanie; tam też idzie cały czas wykonania.
- `AnalysisWorkerTask.MAX_PERCENTILES = 5`, percentyle 1–99 rosnąco. Nie projektuj UI
  na „dowolna lista percentyli", zanim nie zweryfikujesz open question #5/#6.
- Izochron **nie robi R5** — R5 daje siatkę czasów przejazdu, kontury liczy QGIS.
- Na Windows: nieudane wczytanie `network.dat` może zostawić otwarty uchwyt pliku
  (to jest dokładnie ten bug, który r5py łata dwoma `input.close()`), przez co pliku
  nie da się skasować ani przebudować.
- R5 **oficjalnie nie ma stabilnego API** — upstream ostrzega, że wrappery muszą
  pinować wersję. Trzymaj powierzchnię runnera minimalną.
- Zasoby sprzątane w `finally` — proces Javy NIE może zostać osierocony, także przy
  anulowaniu i przy wyjątku.
- `osgeo` / GDAL działa tylko wewnątrz interpretera QGIS — dodać guard.
- `metadata.txt` kompletny i zgodny ze specyfikacją wtyczek QGIS; na czas
  developmentu `experimental=True`.

## `tools/` — inne zasady
Wszystko w `tools/` jest **poza wtyczką**: nie jest importowane przez `easy_r5/`, nie
trafia do ZIP-a, nie musi działać w QGIS. Każdy podfolder ma własne środowisko i własny
README. Reguły „ZERO pip install" i „ZERO R" **nie obowiązują** w `tools/` — migrowane
skrypty r5r nadal używają R i to jest w porządku. Docelowo warto je przepiąć na runner
Easy-R5 (dogfooding — patrz `docs/notes/tools-migration.md`).

## .gitignore — nie wersjonować
Dane wejściowe i wyjściowe, `*.osm.pbf`, archiwa GTFS `*.zip`, `network.dat` i katalogi
sieci, `*.jar`, JDK, rastry pośrednie i wynikowe, katalogi robocze, CSV wyników,
`__pycache__/`, `*.pyc`, artefakty QGIS i IDE. Wersjonujemy kod, `styles/`,
`metadata.txt`, dokumentację — nie dane.

## Agent skills

### Issue tracker
Issues i specy żyją jako pliki markdown w `.scratch/`. Patrz `docs/agents/issue-tracker.md`.

### Domain docs
Układ jednokontekstowy — `CONTEXT.md` + `docs/adr/` w korzeniu repo.
Patrz `docs/agents/domain.md`.
