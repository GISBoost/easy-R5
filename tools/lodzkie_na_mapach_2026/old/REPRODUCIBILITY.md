# Odtwarzalność — co jest gotowe, co trzeba zrobić dla innych warunków/parametrów

Pytanie: czy te przebiegi (E1–E9) da się w pełni odtworzyć dla innej daty, innych
cutoffów, innej siatki, innego zestawu feedów? Krótka odpowiedź: **tak, w większości
mechanicznie — zmiana paru wartości w `config.py` i ponowne odpalenie skryptów — ale są
trzy realne miejsca, gdzie "zmień parametr i uruchom" nie wystarczy**, opisane niżej.
Znalazłem je dopiero pisząc ten dokument (nie wszystkie były oczywiste wcześniej).

## Co jest już w pełni parametryczne (zmień w `config.py`, odpal ponownie)

| Parametr | Gdzie w `config.py` | Co trzeba ponownie uruchomić |
|---|---|---|
| Data analizy | `ANALYSIS_DATE` | wszystko od E1 w dół (patrz Pułapka 1) |
| Percentyl, okno odjazdu, godzina | `PERCENTILE`, `TIME_WINDOW_MIN`, `DEPARTURE_TIME` | tylko E7 (`run_accessibility.py`) — resumability przez `.params.json` sam wykryje zmianę i przeliczy |
| Cutoffy (progi czasowe) | `CUTOFFS` | tylko E7 + E8 (`compute_metrics.py`) |
| Funkcja zaniku | `DECAY` | tylko E7 + E8 |
| Rozmiar siatki | `HEX_SPACING_WOJ_M`, `HEX_SPACING_LODZ_M` | E3 (populacja + siatki) → E4 (przycięcie POI do granicy Łodzi) → E7 → E8 — pełny łańcuch, bo origins się zmieniają |
| Batch/heap R5 | `BATCH_SIZE`, `JAVA_HEAP_GB`, `MAX_WALK_TIME` | tylko E7 |
| Próg przycięcia kategorii POI | `MIN_COUNT_PER_POWIAT`, `MIN_POWIATY_COVERED` w `prepare_poi.py` | E4 → E7 → E8 (inny zestaw `OPPORTUNITY_FIELDS`) |

Mechanizmy, które **już działają poprawnie** i nie wymagają nic dodatkowego:

- **Cache sieci R5** (`easyr5:buildnetwork`) — kluczowany hashem wejść (OSM + GTFS) +
  wersją R5. Zmiana zawartości folderu GTFS albo PBF automatycznie wymusza przebudowę,
  bez mojego udziału.
- **Wznawianie przebiegów** (`run_accessibility.py`) — każdy z 4 przebiegów zapisuje
  `.params.json`; jeśli parametry się nie zmieniły, przebieg jest pomijany. Zmiana
  `CUTOFFS`/`PERCENTILE`/itd. w `config.py` automatycznie wymusi ponowne policzenie
  tylko tego, co się zmieniło.
- **Cache POI** (`poi_all_raw` w gpkg) — ekstrakcja z PBF (25–30 min) jest zapisana raz;
  zmiana progu przycięcia kategorii (punkt niżej w tabeli) czyta z cache'u, nie z PBF.

## Trzy realne luki (naprawione dziś, ale trzeba o nich wiedzieć)

### Pułapka 1 — feedy GTFS są migawką dnia pobrania, nie funkcją daty analizy

To jest **najważniejsze ograniczenie całego pipeline'u**. `otwarte.miasto.lodz.pl/.../GTFS.zip`
czy `api.zbiorkom.live/.../gtfs/default` zwracają **aktualny, bieżący** rozkład w momencie
pobrania — nie archiwum historyczne. Złapałem to wprost na `aleksandrow_lodzki.zip`: jego
`calendar_dates.txt` zaczyna się dokładnie od dnia pobrania i sięga ~2 tygodnie naprzód.
Pobranie tego samego URL-a jutro da **inną zawartość**.

**Naprawione dziś:** `inventory_gtfs.download_feed()` cache'uje teraz pod
`work/gtfs_raw/<ANALYSIS_DATE>/<key>.zip`, nie płasko pod `work/gtfs_raw/<key>.zip`. Zmiana
`ANALYSIS_DATE` w `config.py` i ponowne uruchomienie `inventory_gtfs.main()` **automatycznie
pobierze świeże pliki**, zamiast po cichu użyć starego cache'u z innej daty.

**Czego to NIE naprawia:** jeśli chcesz przeliczyć dla daty **z przeszłości** (nie "dziś"),
większość operatorów **nie ma żadnego archiwum** — dostajesz to, co jest opublikowane teraz,
i tyle. Jedyny wyjątek to Łódź, bo `gtfs-dashboard`/`easy-GTFS-RT` trzyma **przypięte**
migawki per dzień (`lodz_static_gtfs_<data>.zip`, `..._p50.zip`, `..._p85.zip` — dokładnie
to, czego użyłem zamiast live-feedu). Dla reszty województwa (Kutno, Opoczno, Rozprza,
Tomaszów) nie ma takiego mechanizmu — **odtworzenie analizy dla innej, historycznej daty jest
możliwe tylko dla Łodzi**, dla reszty województwa zawsze dostaniesz "aktualny" rozkład tych
operatorów, niezależnie jaką datę wpiszesz w `ANALYSIS_DATE`. To trzeba jasno napisać w
metodyce mapy, jeśli ktoś kiedyś zapyta "czy mogę to sprawdzić dla marca".

### Pułapka 2 — złożenie folderów GTFS pod sieci było ręczne, nie skryptowe

Pierwsze uruchomienie złożyło `work/networks/*/gtfs/` przez pojedyncze komendy `cp` w mojej
sesji terminala — działało, ale nie zostawiało po sobie nic, co dałoby się uruchomić drugi
raz bez pamiętania, co dokładnie wpisałem. **Naprawione dziś:** `assemble_networks.py` —
`NETWORK_SPEC` to teraz jawny słownik "który plik trafia do którego folderu", w kodzie, nie
w historii terminala. `py assemble_networks.py` jest idempotentny (nie nadpisuje istniejących
plików bez `--force`).

### Pułapka 3 — bufor budynków (dasymetria) i raster PBF nie są kluczowane hashem wejść

`work/dasym/<target>_bld.tif` cache'uje się po **nazwie** (`woj`/`lodz`), nie po hashu
wejściowego PBF. Jeśli pobierzesz nowszy `lodzkie-latest.osm.pbf` z Geofabrika (aktualizacje
co tydzień), stary raster budynków **zostanie użyty po cichu**, bez ostrzeżenia. To nie jest
naprawione dziś — do zrobienia, jeśli kiedyś odświeżacie PBF: ręcznie skasować
`work/dasym/*.tif` przed ponownym uruchomieniem `dasymetric_population.py`, albo (lepiej,
niezrobione) dopisać hash PBF do nazwy pliku cache'u, tak jak `easyr5:buildnetwork` już to
robi dla sieci R5.

## Przepis krok po kroku — inna data (Łódź, bo tylko tam jest to w pełni możliwe)

1. `config.py`: `ANALYSIS_DATE = "<nowa-data>"`.
2. Sprawdź w `gtfs-dashboard/manifest.json`, czy dla tej daty istnieje wpis
   `cities.lodz.days[].date == <nowa-data>` ze `status: "ok"` i kompletem `assets`
   (`static_gtfs`, `p50`, `p85`) — jeśli nie, nie ma czym zbudować pary static/RT dla tego dnia.
3. Pobierz przypięte pliki z tego wpisu (`curl` na `release_url`+`assets.*`) do
   `work/gtfs_raw/lodz_static_gtfs_<data>.zip` i `lodz_realized_<data>_p50.zip`.
4. `py inventory_gtfs.py` w QGIS (odświeży resztę feedów pod nową datą; sprawdź w wyniku,
   czy `aleksandrow_lodzki`/`polish_trains`-owe problemy z Pułapki 1 się powtarzają dla tej
   konkretnej daty — mogą nie, mogą tak, zależy od kalendarza akurat pobranego pliku).
5. Zaktualizuj `assemble_networks.py`'s `NETWORK_SPEC` (dwie linie z nazwą pliku Łodzi).
6. `py assemble_networks.py --force`.
7. `py validate_gtfs.py --all` — musi być PASS, zanim ruszysz dalej.
8. W QGIS: `build_networks.main()` (sieci R5 same się przebudują, bo hash GTFS się zmienił).
9. `calibrate.main()` — jednorazowy pomiar, żeby potwierdzić, że nowy dzień/sieć nie ma
   innej charakterystyki wydajnościowej (nowe kursy, inna złożoność).
10. `run_accessibility.main()`, potem `compute_metrics.main()`, potem `style_layers.apply_all()`.

## Przepis — inne cutoffy/percentyl/okno (najtańsza zmiana)

1. `config.py`: zmień `CUTOFFS`/`PERCENTILE`/`DEPARTURE_TIME`/`TIME_WINDOW_MIN`.
2. `run_accessibility.main()` — resumability sam wykryje zmianę parametrów i przeliczy
   wszystkie 4 przebiegi (sieci **nie** trzeba przebudowywać — to nie zmienia GTFS/OSM).
3. `compute_metrics.main()`.

## Przepis — inna siatka (np. 500 m zamiast 1000 m dla województwa)

Najdroższa zmiana, bo rusza wszystko od populacji w dół:
1. `config.py`: `HEX_SPACING_WOJ_M = 500`.
2. `prepare_population.main()` — nowa siatka, nowa dasymetria (nowy raster, bo `apply()`
   przelicza się dla nowej liczby heksagonów, choć plik `.tif` zostaje ten sam — samo
   przypisanie ludności jest per-hex, więc to musi przejść od nowa).
3. `prepare_poi.main()` — tylko krok 4 (przycięcie do `hex_grid_lodz`/nowego zasięgu) się
   zmienia; ekstrakcja z PBF (krok 1) korzysta z cache'u `poi_all_raw` bez zmian.
4. `run_accessibility.main()`, `compute_metrics.main()`, `style_layers.apply_all()`.

**Uwaga do kalibracji:** przy mniejszej siatce (więcej origins) czas przebiegu rośnie liniowo
(zmierzone: 0,039 s/origin) — dla 500 m spodziewaj się ~4× więcej heksagonów niż przy 1000 m,
czyli ~4× dłuższego przebiegu. `calibrate.py` warto odpalić ponownie, nie zakładać, że stara
liczba się utrzyma.
