# Jak zrobić tę analizę ręcznie, samą wtyczką (bez skryptów)

Ten plik zakłada, że **nie** chcesz odpalać `prepare_data.py` / `run_accessibility.py` /
`compute_delay.py` przez `mcp__qgis__execute_code`, tylko klikać w Processing Toolbox
tak, jak zrobiłby to zwykły użytkownik wtyczki Easy-R5 — bez Pythona, bez MCP, bez
żadnego dodatkowego narzędzia poza samym QGIS-em i algorytmami z providera **Easy-R5**
oraz **natywnymi** algorytmami QGIS. Dokładnie ta sama analiza, ten sam wynik — tylko
rozpisany na kroki do wykonania w GUI.

Wszystkie nazwy algorytmów poniżej to ich **wyszukiwane hasła w Processing Toolbox**
(`Ctrl+Alt+M` albo *Processing → Toolbox*) — wpisz kawałek nazwy w pole szukania na
górze panelu.

## Krok 0 — czego potrzebujesz

Te pliki muszą już u Ciebie leżeć (patrz `README.md` tego folderu — wszystko pochodzi z
wcześniejszych analiz, nic nowego nie trzeba pobierać):

- `tools/accessibility_lodz/lodz.osm.pbf`
- `tools/accessibility_lodz/lodz_static_gtfs_2026-08-21.zip`
- `tools/accessibility_lodz/lodz_realized_2026-08-21_p50.zip`
- `tools/ses_income_lodz/lodz.gpkg` (warstwa `obwody_spisowe`)
- `tools/accessibility_lodz/lodz_universities.csv`

Wtyczka Easy-R5 musi być zainstalowana i włączona, a silnik R5 + Java 21 już pobrane
(*Setup → Download R5 engine and Java 21*, jednorazowo).

## Krok 1 — dwie sieci R5

R5 buduje sieć z **jednego** `.osm.pbf` + folderu GTFS — a static i realized-P50 nie
mogą leżeć w tym samym folderze (dzielą `trip_id`/`stop_id`, "jeden wariant = jeden
folder"). Więc:

1. Utwórz dwa puste foldery, np. `gtfs_static/` i `gtfs_realized_p50/`, i skopiuj do
   nich odpowiednio `lodz_static_gtfs_2026-08-21.zip` i
   `lodz_realized_2026-08-21_p50.zip` (po jednym zipie w każdym).
2. **Easy-R5 → Setup → Build R5 network**: `OSM_PBF = lodz.osm.pbf`,
   `GTFS_FOLDER = gtfs_static/`, `CACHE_FOLDER` = nowy folder np. `network_static/`.
   Uruchom. W wyniku (`NETWORK_JSON`) sprawdź `service_days["2026-08-21"]` — powinno
   wyjść **9893** aktywnych kursów (to jest bramka: jeśli 0, to cichy walk-only, nie
   kontynuuj).
3. Powtórz identycznie dla `gtfs_realized_p50/` → `CACHE_FOLDER = network_realized_p50/`.
   `service_days["2026-08-21"]` musi wyjść **też 9893** (te same kursy, tylko przepisane
   czasy) — jeśli liczba się różni, coś jest nie tak z feedem, zatrzymaj się.
4. Zanotuj ścieżki do obu plików `network.dat` (są w `network_json`'s `NETWORK_DAT`, albo
   po prostu w `network_static/<hash>/network.dat`) — będą Ci potrzebne w Kroku 6.

## Krok 2 — granica miasta i siatka heksagonalna 250 m

1. Wczytaj `obwody_spisowe` z `tools/ses_income_lodz/lodz.gpkg` (*Layer → Add Layer →
   Add Vector Layer*).
2. **Dissolve** (natywny): `INPUT = obwody_spisowe`, bez pola dissolve (scal wszystko w
   jeden poligon) → `boundary`.
3. **Create grid**: `TYPE = Hexagon (Polygon)`, `HSPACING = VSPACING = 250`,
   `EXTENT` → przycisk "..." → *Calculate from Layer* → `boundary`, `CRS` → "..." →
   *From Layer* → `obwody_spisowe` (to jest UWPP_1992/PL-1992, metryczny — **nie**
   zostawiaj domyślnego EPSG:4326, bo spacing 250 wyszłoby w stopniach) → `grid`.
4. **Extract by location**: `INPUT = grid`, `PREDICATE = intersect`,
   `INTERSECT = boundary` → `hex_clip`.
5. **Field Calculator** na `hex_clip`: nowe pole `hex_id`, typ *Integer*, formuła
   `@row_number` → `hex_grid_bare`.

## Krok 3 — populacja (dogfooding `PopulationOverlay`)

1. **Extract by expression** na `obwody_spisowe`: `"population" IS NOT NULL` →
   `obwody_valid` (precyzje GUS-owskie tajemnicze obwody z `population = NULL` zostają
   wykluczone, nie zerowane).
2. **Easy-R5 → Analysis → Population overlay**: `HEX_GRID = hex_grid_bare`,
   `POPULATION_LAYER = obwody_valid`, `POPULATION_FIELD = population` → `hex_pop_raw`.
   Wynik ma nowe pole nazwane po prostu `population` (zagregowana, area-weighted liczba
   ludności na heksagon) — obok oryginalnego `hex_id`.
3. (Opcjonalnie, dla czytelności) **Field Calculator**: nowe pole `pop_total` (Double) =
   `"population"` → `hex_pop`.
4. Sanity check ręcznie w tabeli atrybutów / *Field Calculator → statystyki*: suma
   `pop_total` po heksagonach powinna być w promilach zgodna z sumą `population` po
   `obwody_valid` (u nas: 670223 vs 669995, różnica 0,034%). Jeśli się rozjeżdża o
   więcej niż ~1%, coś nie zadziałało — nie idź dalej.
5. **Centroids**: `INPUT = hex_pop`, `ALL_PARTS = False` → `hex_centroids` (origins do
   Kroku 6).

## Krok 4 — POI z `.osm.pbf` (offline, bez Overpass)

GDAL-owy driver OSM widzi w jednym `.osm.pbf` kilka podwarstw. Wczytaj **dwie**:
*Layer → Add Layer → Add Vector Layer*, wskaż `lodz.osm.pbf`, w oknie wyboru warstw
źródłowych zaznacz osobno `points` i `multipolygons` (dodadzą się jako dwie warstwy).

Szkoły, apteki i centra handlowe są w OSM mapowane **czasem jako punkt, czasem jako
budynek** (poligon) — żeby nie policzyć tej samej szkoły dwa razy, bierzemy centroid
poligonu tam gdzie jest, a punkt tylko tam, gdzie budynku nie ma. Dla każdej z trzech
kategorii (`school`/`amenity`, `pharmacy`/`amenity`, `mall`/`shop`) powtórz:

1. **Extract by expression** na `multipolygons`: `"amenity" = 'school'` (albo
   `"shop" = 'mall'` dla mall) → `mp_<kategoria>`.
2. **Centroids**: `INPUT = mp_<kategoria>` → `mp_<kategoria>_c`.
3. **Extract by expression** na `points`: `"other_tags" LIKE '%"amenity"=>"school"%'`
   (uwaga: na warstwie `points` nie ma osobnej kolumny `amenity` — trzeba filtrować
   `other_tags`, tak jak GDAL go zapisuje) → `pts_<kategoria>`.
4. **Extract by location**: `INPUT = pts_<kategoria>`, `PREDICATE = disjoint`,
   `INTERSECT = mp_<kategoria>` → `pts_<kategoria>_standalone` (odsiewa punkty leżące
   na już policzonym budynku).
5. **Merge vector layers**: `mp_<kategoria>_c` + `pts_<kategoria>_standalone` →
   `poi_<kategoria>`.
6. **Field Calculator** na `poi_<kategoria>`: cztery nowe pola typu *Integer*,
   `srv_school`, `srv_pharmacy`, `srv_university`, `srv_mall` — ustaw `1` na polu
   odpowiadającym bieżącej kategorii, `0` na pozostałych trzech (osobne wywołanie Field
   Calculatora na każde pole, albo raz z formułą `CASE WHEN ... THEN 1 ELSE 0 END`).

  Oczekiwane liczby (u nas, do porównania): 311 szkół (280 poligonów + 31 punktów), 350
  aptek (6 + 344), 58 centrów handlowych (57 + 1). Jeśli wyjdzie <5 w którejś kategorii,
  filtr jest zły — nie kontynuuj.

Uczelnie mają już gotowy, wyekstrahowany plik (nie trzeba filtrować `.osm.pbf`):

7. *Layer → Add Layer → Add Delimited Text Layer*: `lodz_universities.csv`,
   `X field = lon`, `Y field = lat`, `Geometry CRS = EPSG:4326` → `poi_university_raw`.
8. **Field Calculator**: te same 4 pola `srv_*`, tym razem `srv_university = 1`,
   reszta `0`.

Na koniec:

9. **Merge vector layers**: `poi_school` + `poi_pharmacy` + `poi_mall` +
   `poi_university_raw` → `poi_targets_raw`.
10. **Field Calculator** na `poi_targets_raw`: nowe pole `poi_id` (Integer) =
    `@row_number` (unikalny identyfikator do `DEST_ID_FIELD` w Kroku 6 — prostszy niż
    odtwarzanie `osm_id`/`osm_way_id` ręcznie) → `poi_targets`.

## Krok 5 — sprawdź, czy wszystko jest gotowe

Powinieneś mieć: `hex_centroids` (z `hex_id`), `poi_targets` (z `poi_id` i czterema
`srv_*`), i dwa `network.dat` z Kroku 1.

## Krok 6 — dwa przebiegi Run accessibility

**Easy-R5 → Analysis → Run accessibility**, dwa razy, z identycznymi parametrami poza
`NETWORK`:

| Parametr | Wartość |
|---|---|
| `ORIGINS` | `hex_centroids` |
| `ORIGIN_ID_FIELD` | `hex_id` |
| `DESTINATIONS` | `poi_targets` |
| `DEST_ID_FIELD` | `poi_id` |
| `DATE` | `2026-08-21` |
| `OPPORTUNITY_FIELDS` | `srv_school`, `srv_pharmacy`, `srv_university`, `srv_mall` (zaznacz wszystkie cztery) |
| `CUTOFFS` | `30` |
| `DEPARTURE_TIME`, `TIME_WINDOW`, `PERCENTILES`, `MODE`, `DECAY`, `MAX_WALK_TIME` | **zostaw domyślne** — `07:00`, `120` (czyli okno 7:00–9:00), `50`, *TRANSIT + WALK*, *STEP*, puste (bezstratny limit) — to jest dokładnie to, czego potrzebuje ta analiza |

1. `NETWORK` = `network_static/<hash>/network.dat`, `OUTPUT_LAYER` zapisz jako plik
   (np. *Save Vector Layer As... → GeoPackage* → `acc_static.gpkg`).
2. `NETWORK` = `network_realized_p50/<hash>/network.dat`, `OUTPUT_LAYER` →
   `acc_realized.gpkg`.

Obie warstwy wyjściowe mają pola `acc_srv_school_p50_c30`, `acc_srv_pharmacy_p50_c30`,
`acc_srv_university_p50_c30`, `acc_srv_mall_p50_c30` (liczba osiągalnych punktów danej
kategorii w 30 min).

⚠️ Przy 5662 origins to potrafi trwać na tyle długo, że QGIS **przestanie odpowiadać**
(pasek "Not Responding") — to normalne, silnik R5 dalej liczy w tle, po prostu poczekaj
(nie zabijaj procesu). Zobacz notatkę w `README.md` tego folderu.

## Krok 7 — delta i `base0` bez Pythona

**Delta=0 nie zawsze znaczy "brak zmiany"** — jeśli statyczny wynik już był 0 (miejsce
poza 30-minutowym zasięgiem tej kategorii niezależnie od opóźnień), `0-0=0` zaszumiłby
wynik. Dlatego heksagony z zerowym punktem odniesienia trzeba oznaczyć osobno, nie
zerować.

1. **Join attributes by field value**: `INPUT = acc_static`, `FIELD = hex_id`,
   `INPUT_2 = acc_realized`, `FIELD_2 = hex_id`, `PREFIX = r_` (żeby pola drugiej
   warstwy nie nadpisały pierwszej — dostaniesz np. `r_acc_srv_school_p50_c30`) →
   `acc_joined`.
2. **Field Calculator** na `acc_joined`, dla każdej z 4 kategorii, nowe pole
   `delta_<kategoria>` (Double), formuła (przykład dla school):
   ```
   CASE WHEN "acc_srv_school_p50_c30" = 0
        THEN NULL
        ELSE "r_acc_srv_school_p50_c30" - "acc_srv_school_p50_c30"
   END
   ```
3. Analogicznie nowe pole `base0_<kategoria>` (Integer):
   ```
   CASE WHEN "acc_srv_school_p50_c30" = 0 THEN 1 ELSE 0 END
   ```
4. **Join attributes by field value** (drugi join — żeby wrócić do poligonów zamiast
   punktowych origins i doczepić populację): `INPUT = hex_pop` (poligony, ma
   `pop_total`), `FIELD = hex_id`, `INPUT_2 = acc_joined`, `FIELD_2 = hex_id` →
   `hex_delay_raw`.
5. **Retain fields**: zostaw tylko `hex_id`, `pop_total`, cztery `delta_*`, cztery
   `base0_*` → `hex_delay`.

Sanity check (Field Calculator → statystyki albo *Properties → Fields* na `delta_school`
z filtrem `base0_school = 0`): rozkład nie może być samymi zerami/NULL-ami. U nas:
3867/5662 heksagonów porównywalnych, średnia ważona populacją −0,131.

## Krok 8 — warstwa "hero": `hex_net_opportunities`

Jedna liczba na heksagon — suma `delta_<kategoria>` po tych kategoriach, które akurat
były porównywalne (kategorię z `base0=1` pomijamy, nie zerujemy — inaczej jeden brak
bazy zafałszowałby sumę).

1. **Field Calculator** na `hex_delay`, nowe pole `net_delta` (Double):
   ```
   CASE
     WHEN "delta_school" IS NULL AND "delta_pharmacy" IS NULL
          AND "delta_university" IS NULL AND "delta_mall" IS NULL
     THEN NULL
     ELSE coalesce("delta_school", 0) + coalesce("delta_pharmacy", 0)
          + coalesce("delta_university", 0) + coalesce("delta_mall", 0)
   END
   ```
2. Nowe pole `net_delta_n` (Integer) — ile z 4 kategorii weszło do sumy (sprawdź to
   pole, zanim uwierzysz skrajnej wartości `net_delta` — mogła ją wygenerować jedna
   kategoria, nie cztery):
   ```
   (CASE WHEN "delta_school" IS NOT NULL THEN 1 ELSE 0 END)
   + (CASE WHEN "delta_pharmacy" IS NOT NULL THEN 1 ELSE 0 END)
   + (CASE WHEN "delta_university" IS NOT NULL THEN 1 ELSE 0 END)
   + (CASE WHEN "delta_mall" IS NOT NULL THEN 1 ELSE 0 END)
   ```
3. **Retain fields**: `hex_id`, `pop_total`, `net_delta`, `net_delta_n` →
   `hex_net_opportunities`.

## Krok 9 — legenda: ręczne, wyśrodkowane na zerze klasy (nie automatyczne)

**Nie używaj automatycznego "Equal Interval" ani "Quantile"** — `delta` to mała liczba
całkowita z realnym, znaczącym zerem, a rozkład jest mocno wyzerowany z długim ogonem
(np. `delta_school` przy 250 m: 2361/3867 porównywalnych heksagonów to dokładnie 0, ale
zakres sięga od -14 do +10). Automatyczna klasyfikacja wrzuci np. `[-2, +2]` do jednego
przedziału — "brak zmiany" i "strata 2 punktów" wyjdą tym samym kolorem, czyli dokładnie
tą niejednoznacznością, o którą pytałeś.

*Properties → Symbology → Graduated*, pole `delta_<kategoria>` (albo `net_delta` na
`hex_net_opportunities`), dowolna metoda tylko po to, żeby dostać 7 wierszy — potem
**podwójny klik na każdy zakres**, żeby wpisać ręcznie dokładne granice i kolor:

| klasa | `delta_<kategoria>` | `net_delta` | kolor (ColorBrewer RdBu-7) |
|---|---|---|---|
| 1 | ≤ -4 | ≤ -6 | `#b2182b` ciemna czerwień |
| 2 | -3 .. -2 | -5 .. -2 | `#d6604d` czerwień |
| 3 | -1 | -1 | `#f4a582` blady czerwony |
| 4 | **0 (brak zmiany)** | **0 (brak zmiany)** | `#f7f7f7` blady szary — celowo *obecny*, nie pusty |
| 5 | +1 | +1 | `#92c5de` blady niebieski |
| 6 | +2 .. +3 | +2 .. +5 | `#4393c3` niebieski |
| 7 | ≥ +4 | ≥ +6 | `#2166ac` ciemny niebieski |

Granice wpisuj na wartościach `.5` (np. `-3.5`, nie `-4` albo `-3`), żeby żadna liczba
całkowita nie trafiła dokładnie na granicę klasy — bez tego QGIS może przypisać ją do
niewłaściwego przedziału.

Heksagony z `NULL` (brak bazy — `base0_<kategoria>=1`, albo wszystkie 4 kategorie NULL
dla `net_delta`) **nie pasują do żadnej klasy i renderer nie rysuje dla nich żadnego
symbolu** — są całkowicie przezroczyste, wizualnie odróżnione od klasy "0", która ma
widoczne (choć blade) wypełnienie. To jest zamierzone: "nie dotyczy" vs "sprawdzone, bez
zmian" to dwie różne rzeczy, obie różne od "mała realna zmiana" (blady czerwony/niebieski).

Powtórz dla każdej z 4 kategorii (jedna warstwa `hex_delay`, zmieniasz tylko pole w
symbologii — nie potrzeba czterech kopii warstwy) i dla `net_delta` na
`hex_net_opportunities`. Zapisz projekt.

To jest dokładnie ta sama analiza i te same liczby co w skryptowej wersji (`README.md`)
— tylko krok po kroku w GUI, bez Pythona i bez MCP.

## Inna rozdzielczość siatki (np. 500 m zamiast 250 m)

Sieci R5 (Krok 1) i `poi_targets` (Krok 4) **nie zależą od rozmiaru heksagonu** — nie
trzeba ich przebudowywać. Zmienia się tylko Krok 2 (`HSPACING = VSPACING = 500` zamiast
`250`) i nazwy plików wyjściowych w Krokach 6-7, żeby nie nadpisać wyniku dla 250 m
(np. `acc_static_500m.gpkg`, `hex_delay_500` jako osobna warstwa/plik). Zobacz
`README.md`'s sekcję "250 m vs 500 m" — wynik dla szkół i aptek **zmienia znak** między
rozdzielczościami (MAUP), więc warto mieć obie, nie tylko jedną.
