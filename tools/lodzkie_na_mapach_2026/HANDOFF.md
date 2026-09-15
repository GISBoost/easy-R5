# Łódzkie na mapach 2026 — HANDOFF

**Stan na 2026-09-13, koniec sesji.** Ten plik jest napisany tak, żeby kolejna sesja (ten
sam agent po `/compact`, albo inny agent) mogła kontynuować **bez ponownego odkrywania
niczego z tego, co już zweryfikowane**. Wszystkie liczby tu podane mają pokrycie w plikach
w `out/` i `lodzkie_base.gpkg` — żadna nie jest "z pamięci".

**Interpretacja wyników i dalsze poprawki merytoryczne — Michał robi to z następnym
agentem po `/compact`.** Ten dokument opisuje **co zostało zrobione i jak**, nie wyciąga
wniosków z liczb poza tym, co zostało już bezpośrednio zweryfikowane (bramki, sanity checki).
Tam gdzie coś wymaga interpretacji, jest to wprost oznaczone w sekcji 9.

## 1. Czym to jest

Praca konkursowa na **Łódzkie na mapach 2026** (kategoria II — absolwenci 2026),
**termin zgłoszenia: 2 listopada 2026, 23:59**, przez `lodzkienamapach.lodzkie.pl`
(hasło: `lodzkienamapach`). Regulamin i pełny kontekst decyzyjny:
[`../../docs/lodzkie-na-mapach-2026-metodologia.md`](../../docs/lodzkie-na-mapach-2026-metodologia.md)
— **ale ten plik ma jedno nieaktualne zdanie**: mówi "RT: Łódź, Kutno, ŁKA", a w praniu
RT (nagrywanie GTFS-RT w `easy-GTFS-RT`) istnieje **tylko dla Łodzi** (zweryfikowane E1,
sekcja 6 niżej). Ktoś powinien to poprawić przy okazji E10.

Mapa jest **dwutorowa**:
1. **Poziom wojewódzki** (całe 18 219 km², statyczny GTFS wszystkich potwierdzonych
   operatorów) — spełnia kryterium regulaminu "wielkość obszaru objętego opracowaniem".
2. **Poziom Łodzi** (statyczny rozkład vs zrealizowany P50 z 2026-09-10) — bo dane
   o realizacji (GTFS-RT) istnieją tylko dla miasta.

Metoda jest skalą "realtime_delay_lodz"/"realtime_delay_cities" (patrz
`../realtime_delay_lodz/README.md`, `../realtime_delay_cities/README.md`) — te dwa
foldery są **wzorcem metodologicznym**, z którego świadomie skopiowano/zaadaptowano
wzorce (dasymetria budynkowa, delta static-vs-RT z zerem-jako-NULL, styl RdBu-7).

## 1a. 2026-09-13: oba blokujące bugi wtyczki naprawione, analiza Łodzi (21 kategorii) dokończona

Po pierwotnym HANDOFF trwały dalsze prace (3-dniowa analiza robustness delty Łódź,
rozszerzenie Łodzi do 21 kategorii POI) -- chwilowo przerwane, bo natrafiono na krytyczny
bug wtyczki, **od tego czasu naprawiony w osobnej sesji i zweryfikowany** (`easy-R5`
commity `25d9825`, `e09189d`, oba tickety zamknięte). Pełny log, dokładny opis obu bugów
(łącznie z prawdziwą przyczyną, nie tylko objawami) i finalne liczby:
[`MULTIDAY_LODZ_NOTES.md`](MULTIDAY_LODZ_NOTES.md). W skrócie:

- **[easy-R5 issue #5](https://github.com/GISBoost/easy-R5/issues/5)** (`KNOWN_ISSUES.md`
  #4) -- przyczyna wcale NIE była limitem liczby destynacji, jak podejrzewano pierwotnie:
  w projekcie QGIS wisiała otwarta warstwa `poi_targets_lodz` z zapamiętanym, nieaktualnym
  schematem (12 pól/3535 obiektów) sprzed rozszerzenia tej samej tabeli na dysku do 23
  pól/4161 obiektów -- `lookupField()` na nieaktualnym schemacie trafiał w niewłaściwe
  kolumny względem aktualnego układu wierszy. Naprawione: `write_points_csv()` teraz
  rzuca czytelny błąd zamiast cicho podstawiać 0 pod brakujące/przesunięte pole.
- **[easy-R5 issue #4](https://github.com/GISBoost/easy-R5/issues/4)** (enhancement) --
  pętla originów w `EasyR5Runner.java` teraz równoległa (pula wątków = liczba rdzeni),
  zwalidowana jako bajt-w-bajt identyczna ze starą sekwencyjną wersją. Efekt: 4 przebiegi
  po 4260 originów × 21 kategorii, które zajęłyby ~15-20 min każdy, zajęły ~140s każdy.
- `CUTOFFS` w `config.py` -- `"30"` (bez 45 min), w mocy dla wszystkich przebiegów Łodzi.
- **Przy okazji wznowienia znaleziono i naprawiono DRUGI, niezależny bug** -- tym razem we
  własnym skrypcie tej analizy (`merge_split_lodz_categories.py`, workaround na powyższy
  bug wtyczki z poprzedniej sesji): nadpisywał poprawne wartości starych 10 kategorii
  trywialnymi zerami z pliku pomocniczego. Wykryty sanity checkiem (dwie różne kategorie
  o identycznej wartości dla każdego z 4260 originów -- niemożliwe bez buga), wszystkie
  scalone (`_merged21.csv`) liczby z tamtej próby odrzucone, przeliczone od zera
  bezpośrednio (workaround już niepotrzebny, skoro bug wtyczki naprawiony). Szczegóły
  i finalne, zweryfikowane liczby: `MULTIDAY_LODZ_NOTES.md`.

## 2. Status: co jest zrobione, co nie

| Etap | Status | Co dokładnie |
|---|---|---|
| E1 — inwentaryzacja GTFS | ✅ zrobione, zweryfikowane | `inventory_gtfs.py` |
| E2 — granice + PBF | ✅ zrobione (w ramach E3) | pobranie Geofabrik, wycinek Łodzi (osmosis) |
| E3 — populacja na heksagonach | ✅ zrobione, zweryfikowane | `prepare_population.py` + `dasymetric_population.py` |
| E4 — POI | ✅ zrobione, zweryfikowane | `prepare_poi.py` |
| E5 — sieci R5 | ✅ zrobione (4 sieci) | `assemble_networks.py` + `build_networks.py` |
| E6 — kalibracja | ✅ zrobione | `calibrate.py` |
| E7 — 4 przebiegi dostępności | ✅ zrobione (Łódź: 21 kategorii finalne 2026-09-13; A1 wojewódzki przeliczony 2026-09-14 z poprawionymi parkami) | `run_accessibility.py`; **A2 (podmiana feedu Łodzi na RT) świadomie NIE przeliczony** -- Michał 2026-09-14: ta tura bierze pod uwagę tylko statyczny GTFS dla województwa, delta zostaje do ewentualnej kolejnej tury |
| E8 — delty, maska RT | ✅ zrobione (Łódź: 21 kategorii + 3-dniowy robustness finalne 2026-09-13; poziom wojewódzki przeliczony 2026-09-14) | `compute_metrics.py`; nowa `compute_level_layer()`/`main_woj_level()` -- poziom bez delty, patrz sekcja 6.6a |
| E9 — kartografia | 🟡 częściowo | style gotowe dla 10-kategoriowego układu (`style_layers.py`, projekt `lodzkie_2026.qgz`) -- **do sprawdzenia po rozszerzeniu Łodzi do 21 kategorii** (nazwy pól się nie zmieniły, ale liczba kategorii/zakres `total` tak); **plansze drukowe (layouty) NIE zrobione** |
| E10 — pakiet zgłoszeniowy | ❌ nie zaczęte | zip z GPKG + QGZ + wydrukami + załącznik 1; poprawka literówki w metodologii |

**Następny krok, jeśli ktoś kontynuuje:** E9 layouty (`mcp__qgis__create_layout` +
`add_layout_map`/`add_layout_legend` na wzór `realtime_delay_lodz/delay_lodz.qgz`'s
`plansza_mapy`/`plansza_mapy_en`), potem E10.

## 3. Kluczowe decyzje (z uzasadnieniem — żeby nie trzeba było pytać drugi raz)

Wszystkie ustalone z Michałem 2026-09-13, w trakcie tej samej sesji:

| Decyzja | Wybór | Uzasadnienie |
|---|---|---|
| Zakres RT | tylko Łódź + mapa braków | RT-recording w `easy-GTFS-RT` istnieje tylko dla `lodz` (zweryfikowane) |
| ŁKA w Łodzi | **uwzględniona**, ale statyczna po obu stronach | patrz sekcja 6.5 — realized ŁKA sprawdzone i świadomie odrzucone jako niewiarygodne dla jednego dnia |
| Metryka | skumulowana liczba POI ≤30/45 min, P50, okno 07:00–09:00 | jak `realtime_delay_lodz` |
| Data analizy | **2026-09-10** (czwartek) | rok szkolny (nie wakacje), Łódź ma `status: ok` w manifeście RT |
| Siatka | województwo **1000 m**, Łódź **250 m** | kalibracja E6 potwierdziła: 1000 m bezpieczne czasowo/pamięciowo |
| Kategorie POI | 10 z 21 kandydatów, próg **≥5 obiektów w ≥18/24 powiatach** | ustalone z góry przed zobaczeniem wyników (patrz sekcja 6.4) |
| Populacja | dasymetria budynkowa (nie areal), NSP2021 | metoda z `realtime_delay_cities/dasymetric_pop.py`, przeskalowana na województwo |

## 4. Struktura katalogu — plik po pliku

```
tools/lodzkie_na_mapach_2026/
├── config.py                 -- WSZYSTKIE parametry pipeline'u (data, cutoffy, siatki,
│                                 lista feedów GTFS z URL-ami i notatkami o problemach)
├── inventory_gtfs.py          -- E1: pobiera feedy, liczy kursy aktywne per data,
│                                 przypisuje przystanki do gmin (spatial join), pisze
│                                 warstwę gminy_gtfs + out/gtfs_inventory_gminy.csv
├── prepare_population.py      -- E3 część 1: obwody spisowe -> join populacji z xlsx ->
│                                 siatki heksagonalne (dissolve+buffer+creategrid)
├── dasymetric_population.py   -- E3 część 2: dasymetria budynkowa (raster 10m, OSM
│                                 buildings, mass-preserving split) -> pop_total per hex
├── prepare_poi.py             -- E4: ekstrakcja ~20 kategorii POI z PBF, coverage per
│                                 powiat, przycięcie wg progu, warstwy docelowe (punkty,
│                                 jeden-hot pola srv_<kategoria>)
├── assemble_networks.py       -- E5 prerekwizyt: składa work/networks/*/gtfs/ z
│                                 config.py (NAPISANE PO FAKCIE -- pierwszy raz zrobione
│                                 ręcznymi `cp`, teraz skryptowe i idempotentne)
├── validate_gtfs.py           -- E5 bramka: czysty stdlib, sprawdza że każdy feed w
│                                 każdym folderze sieci ma >0 aktywnych kursów na
│                                 ANALYSIS_DATE, monotoniczne stop_times, i że pary
│                                 static/realized mają identyczny zbiór trip_id + sensowny
│                                 rozkład przesunięć czasowych. URUCHOM PRZED KAŻDYM
│                                 buildnetwork -- to jest zabezpieczenie przed gotchą #1
│                                 z CLAUDE.md (cichy walk-only)
├── build_networks.py          -- E5: woła easyr5:buildnetwork dla 4 sieci
├── calibrate.py                -- E6: pomiar s/origin na próbce (powiat pabianicki) przed
│                                 pełnym przebiegiem
├── run_accessibility.py       -- E7: woła easyr5:runaccessibility dla A1/A2/A3a/A3b,
│                                 zapisuje .params.json (wznawianie) + .csv.meta.json
├── compute_metrics.py         -- E8: delty (realized-static, zero=NULL), podsumowania
│                                 ważone populacją, maska wiarygodności RT
├── style_layers.py            -- E9: klasyfikacje RdBu-7 (delta), sekwencyjna rampa
│                                 (poziom), kategoryzowana (maska RT, pokrycie GTFS)
├── config.py, lodzkie_base.gpkg, lodzkie_2026.qgz  -- patrz niżej
├── REPRODUCIBILITY.md         -- jak odtworzyć dla innej daty/cutoffów/siatki + 3 realne
│                                 luki w odtwarzalności (feedy = migawka dnia, cache
│                                 rastra budynków nie kluczowany hashem PBF, itd.)
├── HANDOFF.md                 -- ten plik
├── out/                       -- WYNIKI (CSV, GPKG) -- patrz sekcja 7
└── work/                      -- dane robocze, NIE wersjonować (gitignored jak reszta repo)
    ├── prg/                   -- PRG (granice administracyjne) surowe + wypakowane
    ├── pbf/                   -- lodzkie-latest.osm.pbf (125MB, Geofabrik) + lodz.osm.pbf
    │                             (27MB, wycięty osmosis --bounding-box completeWays=yes)
    ├── gtfs_raw/               -- cache pobranych feedów GTFS, KLUCZOWANY DATĄ
    │   ├── <data>/<key>.zip    --   (feedy z config.GTFS_FEEDS, live/rolling downloads)
    │   └── lodz_static_gtfs_<data>.zip, lodz_realized_<data>_p50/p85.zip
    │                            --   (przypięte per-dzień release'y z gtfs-dashboard,
    │                                 już date-qualified nazwą pliku)
    ├── networks/<nazwa>/gtfs/  -- 4 foldery, każdy = jeden wariant sieci (patrz sekcja 6.5)
    ├── networks/<nazwa>/cache/<hash>/network.dat+.json  -- zbudowane sieci R5 (168-236 MB każda)
    └── dasym/{woj,lodz}_bld.tif -- rastry budynków 10m (cache, NIE kluczowany hashem PBF!)
```

## 5. Dane źródłowe

| Dane | Źródło | Gdzie leży | Uwagi |
|---|---|---|---|
| Granice administracyjne | PRG, dane.gov.pl dataset 726, aktualizacja 2026-07-30 | `work/prg/`, warstwy `gminy`/`powiaty`/`wojewodztwo` w gpkg | 177 gmin, 24 powiaty; suma powierzchni 18194,6 km² vs GUS 18219 km² (0,13%) |
| Ludność | GUS NSP2021, `easy-OTP/docs/gis/ludnosc_nsp_2021.xlsx` (arkusz "Łódzkie") + `SU_BREC_2021_OBW.shp` (obwody spisowe, cała PL) | tylko odczyt, `config.SU_BREC_SHP`/`LUDNOSC_XLSX` | suma województwa = **2 410 286** (spis, nie mylić z nowszym szacunkiem GUS BDL ~2 328 825 — różne roczniki) |
| OSM | Geofabrik `lodzkie-latest.osm.pbf` | `work/pbf/` | żadnego Overpassa — wszystko czytane lokalnie przez OGR |
| GTFS | 9 feedów, patrz `config.GTFS_FEEDS` | `work/gtfs_raw/` | pełna lista + uzasadnienia w sekcji 6.1 |

## 6. Pipeline szczegółowo

### 6.1 E1 — inwentaryzacja GTFS (`inventory_gtfs.py`)

**Co robi:** pobiera każdy feed z `config.GTFS_FEEDS`, liczy aktywne kursy na
`ANALYSIS_DATE` (port logiki z `easy_r5/core/gtfs_calendar`: `calendar.txt` wg dnia
tygodnia + `calendar_dates.txt` wyjątki), buduje warstwę punktową wszystkich przystanków
ze wszystkich feedów, przypisuje je do gmin przez `native:joinattributesbylocation`
(indeks przestrzenny, nie pętla), klasyfikuje każdą z 177 gmin do jednej z 4 klas.

**Potwierdzone feedy** (`config.GTFS_FEEDS`):

| Klucz | Operator | Kursy 09-10 | Uwaga |
|---|---|---:|---|
| `lodz` | MPK Łódź | 10272 | pinned release, nie live URL (patrz 6.5) |
| `lka_bus` | ŁKA/KKA autobusy | 290 | |
| `lka_train` | ŁKA + Kolej Wąskotorowa Rogów-Rawa-Biała | 340 | **UŻYWANY zamiast `polish_trains`**, patrz niżej |
| `kutno` | MZK Kutno | 333 | |
| `opoczno_mpk` | MPK Opoczno | 248 | |
| `opoczno_pks` | PKS Opoczno | 293 | |
| `rozprza` | Gmina Rozprza | 69 | |
| `tomaszow_mazowiecki` | MZK Tomaszów Maz. | 465 | |
| `polish_trains` | ujednolicony rozkład kolejowy PL (mkuran.pl) | 96 (!) | **WYKLUCZONY z routingu** — patrz 6.5 |
| `aleksandrow_lodzki` | Aleksandrów Łódzki | 0 | **WYKLUCZONY z routingu** — feed nie pokrywa 09-10 (kalendarz zaczyna się 09-13, dzień pobrania) |

**Sprawdzone i BEZ GTFS** (girlc.at + dane.gov.pl datasets/institutions + bezpośrednio
portal operatora): Piotrków Trybunalski, Sieradz, Bełchatów, Radomsko, Skierniewice,
Zduńska Wola, Wieluń, Łowicz, Zgierz, Pabianice, Głowno, Brzeziny, Łask.

**Wynik** (`out/gtfs_inventory_gminy.csv`, warstwa `gminy_gtfs`):
13 gmin "GTFS static + RT" · 92 "GTFS static" · 72 "brak danych". (Klasa "GTFS static,
nie pokrywa daty analizy" istnieje w kodzie, ale po podmianie feedu żadna gmina finalnie
w niej nie została — sprawdź `feeds_uncovered_date` w CSV, jeśli interesuje Cię surowy
stan przed decyzją o wykluczeniu.)

**Bramka:** suma ludności z NSP2021 = 2 410 286, dokładnie zgodna z wierszem
"województwo" w arkuszu GUS (różnica 0,0000%).

### 6.2 E3 — populacja (`prepare_population.py` + `dasymetric_population.py`)

**`prepare_population.py`:**
1. Filtruje `SU_BREC_2021_OBW.shp` (cała Polska, 189569 obiektów) do województwa
   (`WW='10'`) → 14038 obwodów. CRS w pliku źródłowym nie ma kodu EPSG (custom WKT) —
   parametry matchują dokładnie EPSG:2180, więc `setCrs()` na sztywno.
2. Buduje słownik `(gmina_teryt_7, rejon_6, obwod) -> populacja` z xlsx, iterując
   sekwencyjnie i śledząc bieżącą gminę/rejon (bo w pliku GUS obwód spisowy ma w kolumnie
   "Symbol" tylko swój numer, nie pełny klucz — trzeba go złożyć z poprzedzających wierszy
   "rejon statystyczny" i "gmina/delegatura/miasto/obszar wiejski"). **Ważne:** Łódź jako
   miasto na prawach powiatu jest w pliku GUS rozbita na 5 delegatur
   (`Łódź-{Bałuty,Górna,Polesie,Śródmieście,Widzew}`, kody `1061029/039/049/059/069`),
   NIE ma jednego wiersza "gmina m. Łódź" — to samo dotyczy 28 gmin miejsko-wiejskich
   (rozbite na "miasto" + "obszar wiejski"). Właściwe strukturki do sumowania:
   `{"gmina miejska","gmina wiejska","miasto","obszar wiejski","delegatura"}` — NIE
   `"gmina miejsko-wiejska"` (to wiersz-rodzic, zsumowanie obu dałoby podwójne liczenie).
3. Join populacji na obwody → 13880/14038 dopasowanych (99,9%), suma 2 409 303
   (różnica 0,041% vs GUS — bramka ≤1%, przeszła).
4. Buduje granice metodą "stepped dissolve" (`native:buffer +1m` → `-1m` →
   `multiparttosingleparts`) — zwykły `native:dissolve` na 14000+ poligonach fragmentuje
   się na dziesiątki części (znany problem, patrz `realtime_delay_cities/rebuild_boundary.py`).
5. Siatki heksagonalne `native:creategrid TYPE=4` (hexagon), CRS EPSG:2180: województwo
   1000 m (21585 surowych heksagonów), Łódź 250 m (5662 — **dokładnie tyle samo, ile
   w `realtime_delay_lodz`**, dobry sanity check).

**`dasymetric_population.py`** (port `realtime_delay_cities/dasymetric_pop.py`,
uogólniony z "miasto" na "dowolny target"):
1. Rasteryzacja budynków OSM (10 m, tylko "budynek mieszkalny-podobny" — czarna lista
   ~80 wartości `building=` typu garage/industrial/retail/school/hospital/...) do
   `work/dasym/<target>_bld.tif`. **Skala:** cała województwo to ~180 mln komórek przy
   10 m — to jest normalny rozmiar rastra (~180 MB), NIE potrzeba kafelkowania per
   powiat (wcześniejszy szacunek w planie "1,8×10¹¹ komórek" był błędem jednostek o
   czynnik 1000).
2. Bufor bbox w NATYWNYM CRS warstwy budynków (EPSG:4326) przed reprojekcją — unika
   transformowania całej warstwy budynków województwa przed przycięciem.
3. Podział ludności obwodu na fragmenty hex×obwód (`native:intersection`) ważone
   sumą zbudowanych komórek rastra we fragmencie (`native:zonalstatisticsfb`);
   fallback na podział po powierzchni tam, gdzie obwód nie ma żadnych budynków.
4. Odcięcie heksagonów `pop_total < 0,5`.

**Wyniki:**
- Województwo: 21585 → **16864 zaludnionych** heksagonów. Suma `pop_total` =
  2 409 302,81 vs spis 2 410 286 = **-0,041%** (identyczność księgowa, nie przybliżenie).
- Łódź: 5662 → **4260 zaludnionych**. Suma `pop_total` = 697 147,69 — **wyższa** niż
  ludność samej Łodzi (670 642 z delegatur), bo heksagony na granicy miasta łapią
  fragment sąsiednich gmin (Zgierz, Pabianice itd.) — to jest efekt brzegowy siatki,
  nie błąd (heksagon "należy" do Łodzi, jeśli przecina granicę, ale realnie leżąca w nim
  ludność bywa z sąsiedniej gminy).
- 15 obwodów w okolicach Łodzi nie miało żadnych budynków (fallback na powierzchnię),
  2776 osób.

### 6.3 E4 — POI (`prepare_poi.py`)

**Co robi:** ekstrakcja punktów+poligonów z `lodzkie.osm.pbf` (warstwy OGR `points` i
`multipolygons`, ŻADNEGO Overpassa), 21 kandydackich kategorii z metodologii konkursowej
(edukacja/zdrowie/kultura-rekreacja/handel-usługi). Poligony → centroidy; węzły
duplikujące już policzony poligon usuwane (`native:extractbylocation PREDICATE=disjoint`).
**Cache'owane w gpkg** (`poi_all_raw`, pole `category`) — ekstrakcja z PBF trwa 25-30 min
(string-scan warstwy punktów całego województwa 20-krotnie), więc kolejne uruchomienia
z innym progiem odcięcia czytają z cache'u, nie z PBF ponownie.

**Próg odcięcia, ustalony PRZED zobaczeniem wyników:** kategoria zostaje, jeśli ma
**≥5 obiektów w ≥18 z 24 powiatów**.

| Kategoria | Suma PL | Powiaty ≥5 | Werdykt |
|---|---:|---:|---|
| przedszkole | 556 | 20/24 | **OK** |
| szkoła | 993 | 24/24 | **OK** |
| przychodnia | 625 | 24/24 | **OK** |
| apteka | 887 | 24/24 | **OK** |
| park | 776 | 24/24 | **OK** |
| plac zabaw | 2527 | 24/24 | **OK** |
| boisko/obiekt sportowy | 3229 | 24/24 | **OK** |
| supermarket | 919 | 24/24 | **OK** |
| poczta | 266 | 19/24 | **OK** |
| urząd gminy | 531 | 24/24 | **OK** |
| uczelnia | 109 | 1/24 | odrzucona |
| szpital | 55 | 1/24 | odrzucona |
| biblioteka | 227 | 15/24 | odrzucona |
| dom kultury | 204 | 16/24 | odrzucona |
| kino | 34 | 1/24 | odrzucona |
| teatr | 52 | 3/24 | odrzucona |
| muzeum | 108 | 4/24 | odrzucona |
| siłownia | 105 | 6/24 | odrzucona |
| basen | 157 | 11/24 | odrzucona |
| centrum handlowe | 135 | 9/24 | odrzucona |
| targowisko | 122 | 10/24 | odrzucona |

Pełne dane per powiat: `out/poi_coverage_powiaty.csv`.

**Uwaga do interpretacji (dla Michała/następnego agenta):** odrzucone kategorie dzielą
się na dwie różne przyczyny, które próg mechanicznie nie rozróżnia: (a) **realna
rzadkość** — szpital/uczelnia/kino to sensownie ~1 na powiat, próg ≥5 jest dla nich
niewłaściwym testem kompletności OSM, nie oznacza luki w danych; (b) **prawdopodobna
luka OSM** — biblioteka/dom kultury/basen/centrum handlowe są bliżej progu (15-19/24)
i mogą faktycznie brakować w części powiatów. Warto to rozstrzygnąć przed finalną mapą,
czy któreś z (a) wrócić jako osobna, rzadsza warstwa mimo nieprzejścia progu.

**Poprawka 2026-09-13: duże parki dostają kilka punktów na obwodzie, nie jeden centroid.**
Michał zauważył wizualnie (`mcp__qgis__render_map` na Lesie Łagiewnickim), że pojedynczy
geometryczny centroid źle reprezentuje ogromny, nieregularny poligon — Las Łagiewnicki ma
1339,8 ha i **52 km obwodu**; ktoś stojący na jego skraju, kilka km od centroidu, wychodził
w analizie jako "park nieosiągalny", mimo że wchodzi do lasu z domu. Sprawdzone liczbami:
45 z 194 poligonów parkowych w wycinku Łodzi przekracza 5 ha. Naprawione w
`prepare_poi.py`: `_park_destination_points()` — parki ≤5 ha bez zmian (pojedynczy
centroid), parki >5 ha dostają `_n_boundary_points(area_ha) = clamp(round(sqrt(area_ha)/3), 4, 12)`
punktów rozłożonych równomiernie po obwodzie (`native:polygonstolines` +
`native:pointsalonglines`, dystans = obwód/N, liczony per-polygon w pętli, nie
per-warstwa, żeby dużo mniejszy park nie dostał tego samego N co Las Łagiewnicki).
Pierwsza wersja miała stałe N=4 dla każdego dużego parku — sprawdzona wizualnie i uznana
za zbyt rzadką dla największych przypadków, stąd skalowanie. Wynik: Las Łagiewnicki (12 pkt),
Park na Zdrowiu 209,6 ha (5 pkt), Las Chełmy 120,9 ha i większość pozostałych dużych
parków (4 pkt, dolny próg). Województwo: park 776→1273 obiektów, Łódź (przycięta):
~326→335. **Uwaga:** to podniosło liczbę obiektów `poi_targets_woj`/`poi_all_raw` dla
całego województwa (cache w gpkg), ale przebiegi A1/A2 (dostępność wojewódzka) NIE zostały
przeliczone ponownie — są teraz oparte o starą (jednopunktową) wersję parków, dopóki ktoś
nie odpali `run_accessibility.main(["A1_woj_static","A2_woj_lodzrt"])` ponownie. Przebiegi
A3a/A3b (Łódź) **zostały przeliczone** z nowymi punktami (patrz sekcja 6.7 — delta dla
`park` wyraźnie się zmieniła: -0,683→-1,090 @30min).

**Warstwy docelowe** (destynacje dla R5 — **pojedyncze punkty POI, NIE zagregowane do
heksagonów** — wzorzec z `realtime_delay_lodz`, zwalidowany w `modal_complementarity_lodz`
jako ρ=0,9886 vs agregacja hex): `poi_targets_woj` (11859 punktów po poprawce parków,
**10 kategorii** — próg ≥5-w-≥18/24-powiatów, tabela wyżej), pola `srv_<kategoria>`
jednostkowe 0/1. `poi_targets_lodz` (4161 punktów, **wszystkie 21 kandydackich
kategorii** — decyzja Michała 2026-09-13, patrz `MULTIDAY_LODZ_NOTES.md`: Łódź ma
trywialnie dość obiektów każdej kategorii, więc próg kalibrowany pod rzadkość wiejską
nie ma tu zastosowania. **To jest metodologiczna różnica względem województwa, którą
trzeba opisać wprost w dokumentacji końcowej (E10): Łódź badana innym zestawem kategorii
POI niż reszta województwa (21 vs 10).**

### 6.4 E5 — sieci R5

**4 warianty** (`config.py`, sekcja `NETWORKS_DIR`; złożenie: `assemble_networks.py`):

| Sieć | OSM | GTFS | Rozmiar `network.dat` |
|---|---|---|---:|
| `net_woj_static` | `lodzkie.osm.pbf` | 8 feedów (lodz static + lka_bus + lka_train + kutno + opoczno×2 + rozprza + tomaszow) | 236 MB |
| `net_woj_lodzrt` | `lodzkie.osm.pbf` | jak wyżej, `lodz` podmieniony na P50 | 236 MB |
| `net_lodz_static` | `lodz.osm.pbf` (wycinek) | lodz static + lka_train | 168 MB |
| `net_lodz_p50` | `lodz.osm.pbf` | lodz P50 + lka_train (**niezmieniony**) | 168 MB |

**Dlaczego `lka_train` niezmieniony między static/p50:** zrealizowany ŁKA (TripUpdates,
`easy-OTP/tools/family_b_realized`) jest METODOLOGICZNIE dostępny — surowy snapshot dla
2026-09-10 istnieje w archiwum GitHuba (`polish-trains-tripupdates-raw-2026-09`) — ale
**świadomie nieużyty**: narzędzie samo dokumentuje, że P50 z jednego dnia jest zbyt
rzadkie (1-3 obserwacje na segment), realna wartość metody jest przy 15-20+ dniach
poolowanych. Decyzja: ŁKA statyczna po obu stronach, delta Łodzi mierzy **wyłącznie
ZDiT**. Trzeba to napisać wprost w opisie metodyki mapy.

**Aktualizacja 2026-09-13 — sprawdzone ponownie, bo Michał dodał na dashboard 5 dni
zrealizowanego ŁKA (09-08..09-12).** Pobrany i zwalidowany `validate_gtfs.py`'s własnymi
funkcjami: **wszystkie 5 dni zawodzi bramkę "0 aktywnych kursów"** dla dnia, którego
formalnie dotyczą (09-08 do 09-11: 0 aktywnych; 09-12, sobota: 274, jedyny przechodzący).
Zlecony osobny agent (`easy-GTFS-RT`, patrz niżej) znalazł prawdziwą przyczynę: granica
edycji rozkładu `polish_trains.zip` (mkuran.pl) wypada dokładnie na 2026-09-12 — dla ŁKA
żaden `service_id` nie ma w kalendarzu daty wcześniejszej. Workflow `family_b_lka_build.yml`
zawsze ściąga *dzisiejszy* `polish_trains.zip` niezależnie jak odległa jest budowana data,
więc każdy dzień sprzed granicy edycji dostaje puste ("cichy walk-only") rozkłady w
zrealizowanym pliku. **Decyzja: ŁKA zostaje statyczna po obu stronach dla tego zgłoszenia**
— realny zrealizowany ŁKA wymaga naprawy po stronie `easy-GTFS-RT`/`easy-OTP`, poza
zakresem tej mapy. Agent naprawił (nieskomitowane) `family_b_lka_build.yml`, dodając
twardy gate, który failuje build zamiast cicho publikować pustą "zrealizowaną" wersję —
patrz `easy-GTFS-RT/.github/workflows/family_b_lka_build.yml` (zmiana czeka na przegląd
Michała, nie scommitowana, żadna zmiana w `easy-OTP`).

**Dlaczego `lka_train.zip`, nie `polish_trains.zip`:** `polish_trains.zip` (ujednolicony
krajowy feed kolejowy, mkuran.pl) ma granicę edycji rozkładu **dokładnie na 2026-09-10**
— tylko 96 kursów tego dnia vs 350-475/dzień od 09-14. Sprawdzone wprost na
`calendar_dates.txt` (nie zgadywane). `lka_train.zip` (nominalnie "zdeprecjonowany" na
stronie kasznia.net, ale dedykowany tylko ŁKA) ma stabilne 340 kursów/dzień
09-07..09-13 — użyty zamiast.

**Bramka:** `validate_gtfs.py --all` — wszystkie 4 foldery PASS (żaden feed nie ma zera
aktywnych kursów, pary static/realized mają identyczny zbiór `trip_id`, rozkład przesunięć
Łodzi: mediana 0s, p05=-76s, grossly_early=0,07% — zdrowy, nieuszkodzony feed).

**Znaleziony bug wtyczki easy-R5** (zgłoszony jako
[GitHub issue #3](https://github.com/GISBoost/easy-R5/issues/3), wpisany do
`../../KNOWN_ISSUES.md` #3): `ALLOW_NO_SERVICE`/dead-date-guard w
`easyr5:runtraveltimematrix`/`runaccessibility` czyta `network.json`'s `service_days`,
które `gtfs_calendar.compute_service_days` ucina do 90 dni **od najwcześniejszej daty w
kalendarzu KTÓREGOKOLWIEK feedu w folderze** (nie per-feed, nie wokół daty routingu).
`lka_train.zip`'s kalendarz zaczyna się 2025-12-14 → okno kończy się 2026-03-13 → bramka
fałszywie zgłasza "brak serwisu" na 2026-09-10, mimo że każdy feed ma tego dnia realne
kursy (niezależnie zweryfikowane przez `validate_gtfs.py`). **Obejście zastosowane w
`calibrate.py` i `run_accessibility.py`: `ALLOW_NO_SERVICE=True`** — to jest potwierdzony
fałszywy alarm, nie ślepe wyłączenie zabezpieczenia; gdyby ktoś zmienił zestaw feedów,
warto ponownie zweryfikować przez `validate_gtfs.py`, że to założenie nadal trzyma.

### 6.5 E6 — kalibracja (`calibrate.py`)

Próbka 892 origins z powiatu pabianickiego (TERYT `1005`) na `net_woj_static`:
**0,039 s/origin**, 8,2% par w zasięgu 30 min, 18,5% w 45 min (potwierdza, że transit
routing realnie działa, nie same piesze trasy). Ekstrapolacja na pełne 16864 origins:
~11 min/przebieg. Wniosek: siatka 1000 m i domyślny `BATCH_SIZE=500` są bezpieczne,
żadnych korekt.

### 6.6 E7 — cztery przebiegi (`run_accessibility.py`)

| Run | Sieć | Origins | Destynacje | Wiersze CSV | Network hash |
|---|---|---:|---:|---:|---|
| A1_woj_static | net_woj_static | hex_woj_centroids (16864) | poi_targets_woj (11375) | 337280 | 095fcc7c871945a1 |
| A2_woj_lodzrt | net_woj_lodzrt | jak wyżej | jak wyżej | 337280 | 6d645fa82506a989 |
| A3a_lodz_static | net_lodz_static | hex_lodz_centroids (4260) | poi_targets_lodz (4161, **21 kategorii** od 2026-09-13) | 89460 | 73b1bdf387f132b7 |
| A3b_lodz_p50 | net_lodz_p50 | jak wyżej | jak wyżej | 89460 | 9f04d7de7b4cb4b0 |

A3a/A3b policzone PONOWNIE 2026-09-13, dwukrotnie tego samego dnia: raz po poprawce
dużych parków (sekcja 6.3, wtedy jeszcze 10 kategorii), potem jeszcze raz po rozszerzeniu
Łodzi do **21 kategorii** i naprawie dwóch krytycznych bugów (opis: sekcja 1a,
pełny log i finalne liczby: `MULTIDAY_LODZ_NOTES.md`) — sieć bez zmian (hash ten sam),
tylko destynacje/kategorie. Wiersze CSV: 89460 = 21 kategorii x 1 cutoff (30 min,
`CUTOFFS="30"` od 2026-09-13) x 4260 origins. A1/A2 (wojewódzkie) NIE zostały przeliczone
od poprawki parków — patrz zastrzeżenie w sekcji 6.3 i otwarte pytanie #4 (sekcja 9).

Parametry: `DATE=2026-09-10`, `DEPARTURE_TIME=07:00`, `TIME_WINDOW=120`, `PERCENTILE=50`,
`CUTOFFS="30"` (Łódź; A1/A2 wojewódzkie nadal na starym `"30,45"` z ich ostatniego
przebiegu), `DECAY=STEP` (indeks enum 0 — **UWAGA:** `DECAY` w
`easyr5:runaccessibility` to Enum, string `"STEP"` rzuca `QgsProcessingException` —
`run_accessibility.py`'s `_DECAY_ENUM` robi mapping, pamiętaj o tym przy zmianie DECAY
w `config.py`). Sanity check sum per kategoria/cutoff dla A1 — patrz `poi_coverage_powiaty.csv`
i logi w tym pliku sekcja 6.3; wszystkie kategorie mają rozsądny, nie-zdegenerowany
rozkład (8-24% heksagonów z >0 dostępności w 30 min, rosnące przy 45 min).

### 6.6a E7/E8 — 2026-09-14: A1 wojewódzki przeliczony, tylko statyczny GTFS

Michał: "teraz przechodzimy do powtórzenia analizy dla całego województwa, bierzemy pod
uwagę tylko statyczny gtfs" -- potwierdzone pytaniem wprost: **ta tura liczy tylko poziom
(A1), nie deltę A2-A1**. `A2_woj_lodzrt` (podmiana feedu Łodzi na P50) świadomie nie
przeliczona; `hex_woj_delta`/`Delta_wojewodztwo` **zostają nietknięte i nadal są stare**
(sprzed poprawki dużych parków, `CUTOFFS="30,45"`) -- nie pokazywać jako aktualne.

Co zrobione:
1. `run_accessibility.run_one("A1_woj_static", ...)` -- rerun wymuszony automatycznie,
   bo `CUTOFFS` w configu zmienił się z `"30,45"` na `"30"` (decyzja Michała z
   2026-09-13), więc `already_done()` nie dopasował starych params.json niezależnie od
   zmiany POI. **Ważna obserwacja przy okazji: `already_done()` porównuje tylko słownik
   parametrów (w tym URI warstwy), nie hash zawartości pliku/tabeli -- gdyby CUTOFFS się
   nie zmienił, sama poprawka parków (ta sama nazwa warstwy `poi_targets_woj`, więcej
   wierszy) NIE zostałaby wykryta jako powód do rerunu.** To nie jest naprawione (nie w
   zakresie tej tury), tylko odnotowane -- przy każdej zmianie zawartości warstwy bez
   zmiany innych parametrów trzeba ręcznie skasować `.params.json` albo wymusić rerun.
2. Zweryfikowane PRZED użyciem: `poi_targets_woj` na dysku = 11859 obiektów/10 pól `srv_*`
   (zgodne z opisem poprawki parków, sekcja 6.3), `hex_woj_centroids` = 16864, sieć
   `net_woj_static` niezmieniona (hash `095fcc7c871945a1`, nie wymaga rebuildu -- POI to
   destynacje, nie wejście do budowy sieci). Zero procesów `java.exe` w tle przed startem.
3. Przebieg: 206,9 s (10 kategorii x 16864 originów x 1 cutoff = 168640 wierszy CSV,
   dokładnie tyle ile oczekiwane). Sanity check sum per kategoria: 6,7-23,4% heksagonów
   niezerowych na 30 min -- ten sam rząd wielkości co kalibracja E6 (8,2% na próbce
   powiatu pabianickiego), nie zdegenerowane (nie wszystko-zero, nie wszystko-max).
4. **Nowa funkcja `compute_metrics.compute_level_layer()`/`main_woj_level()`** (poziom
   bez delty -- nie ma z czym porównywać, skoro nie liczymy A2) -> nowa warstwa
   `hex_woj_level` (pola `level_<kategoria>_c30` + `level_total_c30`, 16864 heksagonów,
   0 brakujących) + `out/woj_level_summary.csv` (średnia ważona populacją per kategoria).
   `total` ważony populacją = **151,6** POI osiągalnych w 30 min (nieważony: średnia 6,08,
   maks. 1295 -- w centrum Łodzi). `hex_woj_delta`/`Delta_wojewodztwo` NIE nadpisane.
5. `style_layers.py`'s poziom wojewódzki przestylowany na `hex_woj_level`/`level_total_c30`
   (był: `hex_woj_delta`/`base_total_c30`, źle bo ta warstwa jest stara). Warstwa projektu
   `Poziom_wojewodztwo` przepięta (`setDataSource`) na `hex_woj_level`, widoczna domyślnie
   razem z `Granica_wojewodztwo` (reszta grupy `Wojewodztwo` zostaje OFF, jak dotychczas).
6. Wizualna weryfikacja (`render_map`, cały zasięg województwa): wyraźny hotspot w Łodzi
   (ciemnoniebieski, >120 POI/30min), mniejsze skupiska dokładnie przy pozostałych
   miastach powiatowych z GTFS (Sieradz, Piotrków Trybunalski, Kutno, Bełchatów, Tomaszów
   Maz., Skierniewice itd.), reszta województwa blado-żółta (0-5) -- zgodne z oczekiwaniem
   z E1 (większość gmin ma słaby lub żaden GTFS). Zdrowy rozsądek geograficzny: PASS.
7. Projekt zapisany (`save_project`).

**Nie zrobione w tej turze (świadomie, poza zakresem):** A2/delta wojewódzka, RT maska
wojewódzka (już istnieje z poprzedniej tury, niezmieniona, nadal ważna -- nie zależy od
POI), plansze drukowe, pakiet zgłoszeniowy.

### 6.6b E7/E8 — 2026-09-14: "delta" wojewódzka przedefiniowana jako wzrost 30→60 min

Michał zauważył, że warstwa `Delta_wojewodztwo` w QGIS pokazywała stare dane (sprzed
poprawki parków, patrz 6.6a) i zaproponował inne podejście: skoro nie ma RT dla
województwa, niech "delta" oznacza **wzrost liczby osiągalnych POI, gdy próg czasowy
podwoi się z 30 na 60 min** — sprawdzenie, czy dostępność rośnie liniowo z budżetem
czasu, czy nie. Druga poprawka: **poziom 0 nie powinien być kolorowany** — heksagon bez
żadnego osiągalnego POI ma wyglądać jak biała plama, nie jak najniższy odcień koloru
(bo to wprowadzało w błąd — "trochę dostępności" i "zero dostępności" wyglądały tak samo).

**Wykonane:**
1. `run_accessibility.py`: `RUNS` dostał opcjonalny klucz `"cutoffs"` (analogicznie do
   wcześniejszego `"date"`) i nowy wpis `A1_woj_static_thresholds` — te same
   sieć/origins/destinations co `A1_woj_static`, ale `CUTOFFS="30,60"` w jednym
   przebiegu (tańsze niż dwa osobne — R5 i tak przeszukuje do `MAX_TRIP_DURATION`
   domyślnie 90 min, więc 60 min nie wymaga szerszego przeszukiwania niż to, co już
   robił przebieg na 30 min; sumowanie kosztuje grosze). Czas: **221,2 s** — praktycznie
   tyle samo co przebieg tylko-na-30-min (207 s), potwierdza że to nie przeszukiwanie
   jest droższe, tylko sumowanie, które jest tanie.
2. `compute_metrics.compute_threshold_sensitivity_layer()` — nowa warstwa
   `hex_woj_thresholds`: `level_<kat>_c30`, `level_<kat>_c60`, `growth_<kat>` (c60-c30),
   `ratio_<kat>` (c60/c30, `None` gdy c30=0 — nie da się policzyć ilorazu z zera, ten sam
   konwencja co reszta projektu).
3. `population_weighted_threshold_summary()` — **złapany i naprawiony własny bug** przy
   pierwszym przebiegu: pole `hexagons_still_zero_at_c60` liczyło naprawdę
   "heksagony z c30=0" (niezależnie od c60!), nie "nadal zero przy 60 min". Naprawione —
   rozdzielone na `hexagons_emerged_c30_zero_c60_positive` (zero na 30 min, coś na 60 —
   "odblokowane" szerszym budżetem) i `hexagons_still_zero_at_c60` (zero na obu). Dodany
   też `ratio_of_pop_weighted_sums` (iloraz sum, nie średnia ilorazów per-heksagon) —
   znacznie mniej wrażliwy na heksagony z maleńkim mianownikiem (c30=1→c60=9 liczy się
   tyle samo co c30=100→c60=200 w naiwnej średniej ilorazów, co zawyża wynik).

**Wynik (`out/woj_threshold_summary.csv`), kategoria `total`:**

| Miara | Wartość |
|---|---:|
| `ratio_of_pop_weighted_sums` | **5,63×** |
| `mean_ratio_c60_c30_pop_weighted` (naiwna średnia ilorazów, zawyżona) | 8,68× |
| `mean_growth_c60_c30_pop_weighted` | +701,9 POI |
| heksagony z dostępem już na 30 min | 5930 (35,2%) |
| heksagony "odblokowane" dopiero na 60 min | 7039 (41,7%) |
| heksagony nadal zero na 60 min | 3895 (23,1%) |

**Odpowiedź na pytanie Michała wprost: NIE, dostępność NIE podwaja się przy podwojeniu
progu czasowego — rośnie ~5,6× (iloraz sum, miara odporna na wartości odstające) do ~8,7×
(naiwna średnia per-heksagon).** To silnie nieliniowy efekt, spójny z siecią transitową
typu hub-and-spoke — krótki budżet czasu ledwo wychodzi poza zasięg pieszy, dłuższy
odblokowuje całe dodatkowe linie/przesiadki. Prawie 42% heksagonów przechodzi z "zero" do
"cokolwiek" dopiero między 30 a 60 min — to jest osobna, ważna liczba do mapy/opisu:
**przy progu 30 min prawie 2/3 województwa (65%: 41,7%+23,1%) nie ma żadnego dostępu do
żadnej z 10 kategorii POI.**

**Kartografia:** `style_layers.sequential_level_renderer()` dostał parametr `min_value`
(domyślnie 0,5) — zakresy klas zaczynają się od 0,5, więc heksagon z wartością dokładnie 0
nie mieści się w żadnym zakresie i QGIS nie rysuje dla niego symbolu (ten sam mechanizm
"brak symbolu" co przy NULL w warstwach delty). Zweryfikowane wizualnie
(`render_map`) — widoczna, spora różnica: dużo więcej białych plam niż wcześniej, kiedy
zero i "1-4 POI" dostawały ten sam blady żółty kolor. Nowa `sequential_growth_renderer()`
(sekwencyjna pomarańczowo-brązowa rampa, bo `growth_<kat>` z definicji ≥0, nie potrzeba
izolowanego zera jak przy delcie static-vs-RT) zastosowana do `growth_total`.

**Warstwy projektu zaktualizowane** (bez zmiany nazw, żeby nie psuć czegokolwiek innego
w projekcie): `Poziom_wojewodztwo` → `hex_woj_level`/`level_total_c30` z nowym
zero-wykluczającym rendererem; `Delta_wojewodztwo` → przepięta na
`hex_woj_thresholds`/`growth_total` z nowym rendererem wzrostu. Domyślnie widoczna:
`Delta_wojewodztwo` (tak jak Michał miał włączone, kiedy zgłosił problem), `Poziom_wojewodztwo`
wyłączona. Projekt zapisany.

**Nie zrobione / do decyzji:** czy tę samą korektę (0 bez koloru) zastosować też do
`Poziom_Lodz` (na razie nietknięta — ten sam problem tam prawdopodobnie występuje, ale
poza zakresem tego polecenia); czy `hex_lodz` też dostanie wersję progową 30/60 min.

### 6.7 E8 — delty i maska RT (`compute_metrics.py`)

**Formuła delty** (identyczna jak `realtime_delay_lodz`): `delta = realized - static`,
**NULL gdy `static == 0`** (nie liczone jako 0 — heksagon bez dostępności w ogóle nie ma
czego "stracić"). `net_delta_n` liczy ile kategorii wzięło udział w sumie "total"
(21 dla Łodzi od 2026-09-13, 10 dla województwa — patrz niżej).

**Wyniki — Łódź (static vs P50), ważone populacją, tylko heksagony porównywalne.
Przeliczone 2026-09-13, finalnie po rozszerzeniu do 21 kategorii i naprawie obu
krytycznych bugów wtyczki (sekcja 1a). Pełna tabela wszystkich 21 kategorii + 3-dniowy
robustness check: `MULTIDAY_LODZ_NOTES.md`. Tylko `total`, dla orientacji (30 min,
`CUTOFFS="30"` — 45 min nie liczone już od zmiany configu):**

| Dzień | Δ total @30min |
|---|---:|
| 2026-09-08 (wt) | -11,820 |
| 2026-09-09 (śr) | -13,138 |
| **2026-09-10 (czw, główny)** | **-12,149** |
| średnia 3 dni | -12,369 |

Wszystkie 21 kategorii ujemne (nie tylko `total`) — jednorodny znak z oryginalnej
10-kategoriowej analizy potwierdza się także na pełnym zestawie i na 3 niezależnych
dniach; to NIE jest szum jednego dnia ani artefakt małego zestawu kategorii.

Kierunek znaku nie zmienił się (nadal ujemny wszędzie — patrz zastrzeżenie niżej), ale
`park` stał się bardziej ujemny: więcej punktów dostępu (rozłożonych po obwodzie zamiast
jednego centroidu) oznacza więcej heksagonów faktycznie porównywalnych blisko dużych
parków, więc metryka jest czulsza na zmianę P50 w tamtych rejonach.

**Wyniki — województwo (static vs Łódź-RT-podmieniona), ta sama metoda:** ten sam
kierunek (wszędzie ujemne), mniejsze bezwzględnie (bo delta poza Łodzią z definicji = 0,
tylko heksagony w/koło Łodzi mają niezerową wartość) — `total` @30min = -3,646,
@45min = -9,194. Pełne liczby: `out/woj_delta_summary.csv`.

**Uwaga do interpretacji (WPROST dla Michała/następnego agenta, nie rozstrzygnięte
tutaj):** delta jest **ujemna we wszystkich 10 kategoriach jednocześnie**, w obu skalach.
Sprawdzone, że to NIE jest błąd w skrypcie delty — porównałem surowe sumy z obu
przebiegów R5 wprost (bez pośrednictwa `compute_metrics.py`) i spadek jest **w samych
danych R5** (1-4% względnego spadku sumy dostępności między static a P50). Manifest
`easy-GTFS-RT` podaje dla 2026-09-10: `mean_delay_sec=27,19`, `pct_changed=38,46%`.
Mechanizm prawdopodobny: przy `DECAY=STEP` i sztywnym cutoffie nawet mały medianowy
przesunięcie potrafi "wypchnąć" pojedyncze przesiadki poza próg, a efekt jest silniejszy
w oknie porannego szczytu (07:00-09:00) niż sugeruje dobowa średnia opóźnień. **To jest
mechanistycznie wiarygodne, ale nie jest to samo co "udowodnione" — Michał chce omówić
to z następnym agentem, w szczególności czy jednorodny znak jest realnym zjawiskiem tego
konkretnego czwartku czy wymaga dodatkowej weryfikacji (np. drugi dzień do porównania).**
Michał zwrócił uwagę, że **rozkład przestrzenny delty jest ważniejszy niż sam znak** —
mapa (`lodzkie_2026.qgz`, warstwa `Delta_wojewodztwo`/`Delta_Lodz`) pokazuje realną
zmienność skoncentrowaną ciasno wokół centrum Łodzi, reszta województwa to "0, bez
zmian" (bo poza Łodzią żaden feed się nie zmienia między A1/A2).

**Maska wiarygodności RT** (`rt_coverage_mask` w `compute_metrics.py`, promień dojścia
800 m, `native:joinattributesbylocation METHOD=0` — **UWAGA: METHOD=1 to "tylko pierwsze
dopasowanie", nie "one-to-many"; sprawdzone przez `get_algorithm_help`, żeby się nie
pomylić drugi raz**):

| Klasa | Łódź (4260 hex) | Województwo (16864 hex) |
|---|---:|---:|
| RT pełne | 3284 | 415 |
| RT częściowe | 650 | 93 |
| brak danych o realizacji | 326 | 16356 |

Dokładnie taki wynik, jakiego oczekiwano — RT pokrywa niemal całą Łódź, prawie nic poza
nią. NULL-owanie "brak danych" (zamiast liczenia jako 0) jest wprost wymogiem Michała
z notatki metodologicznej (kryterium b regulaminu).

### 6.8 E9 — kartografia (`style_layers.py`, projekt `lodzkie_2026.qgz`)

**Zrobione:** klasyfikacja RdBu-7 z izolowanym zerem dla delt (krawędzie na
połówkach — `0,5/1,5/3,5` × skala, `total` skalowany ×3 bo to suma 10 kategorii),
sekwencyjna rampa 6-klasowa dla map poziomu, kategoryzowana dla maski RT (z wypełnieniem
"diagonal" dla "brak danych") i pokrycia GTFS gmin. Wszystko zweryfikowane wizualnie
(`get_canvas_screenshot`) — renderuje się poprawnie, nie tylko "nie crashuje".

**Struktura projektu:** dwie grupy warstw, `Wojewodztwo` i `Lodz`, każda z: Delta,
RT_maska, Poziom, POI, Granica (+ w grupie wojewódzkiej: `Gminy_pokrycie_GTFS`,
`Powiaty`). Domyślnie widoczne tylko warstwy Delta + Granica + Powiaty (reszta OFF,
włączana ręcznie w QGIS).

**NIE zrobione:** plansze drukowe (layouty PL/EN, wzorem
`realtime_delay_lodz/delay_lodz.qgz`'s `plansza_mapy`/`plansza_mapy_en`) — to jest
następny krok. Michał explicite powiedział, że nie trzeba domykać składu do końca
("mapki wrzucam na arkusz i ustawiam") — wystarczy szkielet z mapą + legendą.

**Dwa realne błędy złapane i naprawione po drodze (WAŻNE dla każdego, kto edytuje
`style_layers.py` dalej):**
1. **QGIS 3.40.5 access violation crash** w `QgsGraduatedSymbolRenderer::clone` —
   przyczyna: linia `renderer.setClassificationMethod(None)` w pierwszej wersji kodu
   przekazywała null tam, gdzie QGIS oczekuje `QgsClassificationMethod*` i nie
   sprawdza tego przed `clone()`. Usunięte. **Nigdy nie wołaj `setClassificationMethod`
   dla ręcznych zakresów (`QgsRendererRange`) — nie jest potrzebne.**
2. **Uszkodzona geometria `boundary_woj`/`boundary_lodz`** — prawdopodobnie skutek
   pięciu szybkich zapisów `QgsVectorFileWriter.writeAsVectorFormatV3` pod rząd do
   TEGO SAMEGO pliku gpkg w jednym uruchomieniu `prepare_population.main()`. Naprawione
   przez odtworzenie granic z już zweryfikowanych siatek heksagonalnych
   (`hex_grid_woj`/`hex_grid_lodz`) i natychmiastową weryfikację odczytem z dysku po
   zapisie. **Jeśli znowu zobaczysz zdegenerowaną/spiczastą geometrię po zapisie
   kilku warstw pod rząd do jednego gpkg — sprawdź `ogrinfo -so -al` na tej
   warstwie zanim uznasz dane za dobre.**

Osobny, niepowiązany bug: `native:joinattributesbylocation`'s `METHOD` enum —
`METHOD=1` to "tylko pierwsze dopasowanie" (one-to-one), **nie** "one-to-many". Złapane
przez `mcp__qgis__get_algorithm_help` przed użyciem w masce RT (sekcja 6.7) — gdyby
zostało błędne, każdy heksagon miałby ucięte do maksymalnie 1 przystanku w promieniu.

## 7. Warstwy w `lodzkie_base.gpkg` (26 warstw)

| Warstwa | Geometria | Rola |
|---|---|---|
| `powiaty`, `wojewodztwo`, `gminy` | Multi Polygon | surowe PRG, referencyjne |
| `gminy_gtfs` | Multi Polygon | E1 wynik — klasa pokrycia GTFS per gmina |
| `obwody_spisowe_raw` | Multi Polygon | SU_BREC przefiltrowany do województwa, bez populacji |
| `obwody_spisowe` | Multi Polygon | + pole `population` (join z xlsx) |
| `hex_grid_woj`, `hex_grid_lodz` | Polygon | surowe siatki, bez populacji |
| `hex_{woj,lodz}_all` | Multi Polygon | + `pop_total` (dasymetria), WSZYSTKIE heksagony |
| `hex_{woj,lodz}_pop` | Multi Polygon | jak wyżej, tylko `pop_total >= 0,5` |
| `hex_{woj,lodz}_centroids` | Point | centroidy `_pop` — to są ORIGINS dla R5 |
| `poi_all_raw` | Point | cache WSZYSTKICH 21 kandydackich kategorii POI |
| `poi_targets_woj` | Point | 10 przetrwałych kategorii (próg ≥5-w-≥18/24-powiatów), pola `srv_*`, DESTINATIONS dla R5 |
| `poi_targets_lodz` | Point | **21 kategorii** (wszystkie kandydackie — decyzja Michała 2026-09-13, Łódź badana innym zestawem niż województwo), pola `srv_*`, DESTINATIONS dla R5 |
| `calib_origins` | Point | próbka z E6, powiat pabianicki |
| `hex_{woj,lodz}_delta` | Multi Polygon | E8 wynik — poziom + delta per kategoria + total (UWAGA: `hex_woj_delta` stary, sprzed poprawki parków — patrz 6.6a) |
| `hex_woj_level` | Multi Polygon | E8 wynik 2026-09-14 — poziom wojewódzki bez delty (`level_<kat>_c30`, `level_total_c30`), tylko statyczny GTFS, aktualny |
| `hex_woj_thresholds` | Multi Polygon | E8 wynik 2026-09-14 — "delta" przedefiniowana jako wzrost dostępności 30→60 min (`level_<kat>_c{30,60}`, `growth_<kat>`, `ratio_<kat>`), patrz 6.6b |
| `hex_lodz_delta_multiday` | Multi Polygon | E8 wynik — 3-dniowy robustness check (śred. delta + rozrzut dzień-do-dnia), tylko Łódź |
| `hex_{woj,lodz}_rt_mask` | Multi Polygon | E8 wynik — klasa wiarygodności RT |
| `boundary_woj`, `boundary_lodz` | Polygon | granice do kartografii (odtworzone, patrz 6.8) |

## 8. Gdzie są liczby (bez powtarzania ich tutaj)

- `out/gtfs_inventory_gminy.csv` — E1, per gmina
- `out/poi_coverage_powiaty.csv` — E4, per powiat × kategoria
- `out/calib_matrix.csv` — E6, surowa próbka OD
- `out/acc_{A1,A2,A3a,A3b}_*.csv` — E7, surowe wyniki R5 (długi format R5: `id,opportunity,percentile,cutoff,accessibility`)
- `out/{lodz,woj}_delta_summary.csv` — E8, podsumowanie ważone populacją (woj: stare, patrz 6.6a)
- `out/woj_level_summary.csv` — E8, poziom wojewódzki bez delty, ważony populacją, aktualny (2026-09-14)

## 9. Otwarte pytania do interpretacji (NIE rozstrzygnięte w tej sesji — do rozmowy Michała z następnym agentem)

1. **Jednorodny ujemny znak delty** (sekcja 6.7) — **od 2026-09-13 potwierdzony jako
   robustny**: ujemny w każdej z 21 kategorii (nie tylko oryginalnych 10) i stabilny co
   do znaku i rzędu wielkości w 3 niezależnych dniach (wt/śr/czw), nie tylko w
   2026-09-10 (pełne liczby: `MULTIDAY_LODZ_NOTES.md`).
   **2026-09-14 — przyczyna wyjaśniona (nie tylko potwierdzona jako nieszumowa):**
   ta sama analiza policzona dla 4 dni sierpniowych (wakacje) dała efekt ~8,4x mniejszy
   i dużo mniej jednorodny (73% ujemnych komórek vs 98% we wrześniu, jeden dzień netto
   dodatni) — potwierdzone niezależnie przez surowe dane opóźnień z `easy-GTFS-RT`
   (mean_delay 6-10s w sierpniu vs 27s we wrześniu, ~18% vs 38% kursów zmienionych).
   Wniosek: to nie jest cecha strukturalna Łodzi, tylko efekt związany z powrotem do
   szkoły/pracy po wakacjach (realnie gorsza punktualność, zmierzona dwoma niezależnymi
   sposobami). Pełny opis: `MULTIDAY_LODZ_NOTES.md` sekcja "2026-09-14: wakacje vs rok
   szkolny". CZY i JAK ten wniosek ma trafić na mapę/w opisie — wciąż decyzja Michała.
2. **Kategorie POI na granicy progu** (biblioteka 15/24, dom kultury 16/24, basen 11/24,
   centrum handlowe 9/24) — realna luka OSM czy realna rzadkość? Wpływa na to, czy
   dodać je z powrotem jako osobną, jawnie oznaczoną warstwę.
3. **`docs/lodzkie-na-mapach-2026-metodologia.md`** ma nieaktualne zdanie o RT dla
   Kutna/ŁKA — do poprawki przy E10.
4. **A1 wojewódzki przeliczony 2026-09-14** z poprawionymi parkami (sekcja 6.6a) --
   `hex_woj_level`/`Poziom_wojewodztwo` są teraz aktualne i to jest źródło prawdy dla
   poziomu wojewódzkiego. **A2 (podmiana feedu Łodzi na RT) i `hex_woj_delta`/
   `Delta_wojewodztwo` pozostają nieprzeliczone i stare** (przed poprawką parków,
   `CUTOFFS="30,45"`) -- to świadoma decyzja zakresu tej tury (Michał: tylko statyczny
   GTFS), nie zaległość. Jeśli kiedyś wraca się do delty wojewódzkiej: odpalić
   `run_accessibility.main(["A2_woj_lodzrt"])`, potem dopiero `compute_metrics.main()`'s
   woj-część (ta wciąż istnieje, nietknięta, obok nowego `main_woj_level()`).
5. **Zrealizowana ŁKA nie weszła do mapy** (sekcja 6.4) — zbadana 2026-09-13, wszystkie
   5 dostępnych dni (09-08..09-11) fałszywie pokazują 0 aktywnych kursów z powodu granicy
   edycji rozkładu `polish_trains.zip` 2026-09-12; realna naprawa wymaga zmiany w
   `easy-GTFS-RT`/`easy-OTP` (poza zakresem tej mapy). Fix na gate w
   `family_b_lka_build.yml` czeka nieskomitowany na przegląd Michała.
6. **Plansze drukowe** — jaki układ, ile wstawek, PL/EN czy tylko PL na start.

## 10. Powiązane dokumenty

- [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) — jak odtworzyć dla innej daty/parametrów/siatki
- [`../../docs/lodzkie-na-mapach-2026-metodologia.md`](../../docs/lodzkie-na-mapach-2026-metodologia.md) — brief konkursowy (jedno zdanie nieaktualne, patrz sekcja 1)
- [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md) — wpis #3 (bug wtyczki, service_days cap)
- [GitHub issue #3](https://github.com/GISBoost/easy-R5/issues/3) — pełny opis buga
- [`../realtime_delay_lodz/README.md`](../realtime_delay_lodz/README.md), [`../realtime_delay_cities/README.md`](../realtime_delay_cities/README.md) — wzorzec metodologiczny, z którego ta analiza jest skalowaną adaptacją
