# apartment_finder — „Gdzie mieszkać w Łodzi?"

Pipeline danych dla publicznego narzędzia wyboru lokalizacji mieszkania w Łodzi. Frontend leży w repo
[`mapy-analizy`](https://github.com/GISBoost/mapy-analizy) (`gdzie-mieszkac-lodz/`); tu jest wszystko, co liczy
dane, które ta strona wyświetla. Specyfikacja: `docs/prd/PR_easy-R5_apartment-finder.md`, notatki z rozpoznania:
`docs/notes/apartment-finder-m0.md`.

**Wersja metody:** `apt-v1` (siatka `hex250-v1`, warstwy `static-v1` / `noise-v1`, auto `car-v1`, krzywe `curves-v1`).
Każdy plik wynikowy niesie wersje w metadanych (`*.meta.json`, `data/matrices/<dzień>/*.json`, `manifest.json`).

## Co jest liczone

| Warstwa | Skrypt | Wynik |
|---|---|---|
| Siatka hex 250 m (5662 heksów, środek w granicach miasta) | `scripts/make_grid.py` | `data/grid.gpkg` |
| Przystanki (tram/bus), częstotliwość per pora dnia, zieleń | `scripts/static_layers.py` | `data/static/static_layers.csv` |
| Hałas (udział powierzchni heksa ≥ N dB; droga, tramwaj, kolej, przemysł; Lden i Ln; rasteryzacja 10 m) | `scripts/fetch_noise.py`, `scripts/noise_layers.py` (systemowy Python) | `data/noise/noise_layers.csv` |
| Auto: współczynniki zwolnienia z autobusów → kopie OSM z `maxspeed` per pora | `scripts/car_speeds.py` | `data/car/lodz_car_<pora>.osm.pbf` |
| Macierze czasów O–D (R5) | `scripts/run_matrices.py`, `scripts/run_all.sh` | `data/matrices/<dzień>/<scenariusz>.npz` |
| Niezmienniki I1–I4 | `scripts/check_invariants.py` | `data/matrices/<dzień>/invariants_<pora>.json` |
| Eksport dla strony | `scripts/export_web.py` | `<easy>/gdzie-mieszkac-lodz-data/` (osobne repo danych, patrz niżej) |

Wszystkie parametry (okna czasowe, dni, progi, krzywe, promienie wygładzania) są w `config/*.yaml`.

## Uruchomienie

Skrypty z „QGIS" wołają wtyczkę Easy-R5 bez GUI (provider dodawany ręcznie, `scripts/_qgis_env.py`) i muszą iść
interpreterem QGIS-a: `"C:/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat" scripts/<skrypt>.py`.
Pozostałe: systemowy Python (`py`; numpy, pandas, shapely, pyproj, pyyaml).

1. Dane wejściowe (nie są wersjonowane): `data/raw/lodz.osm.pbf`; GTFS dni z `config/days.yaml`:
   `py scripts/prepare_gtfs.py` (pobiera z release'ów `GISBoost/easy-GTFS-RT`; statyczny feed ŁKA jest filtrowany do
   kursów ŁKA, bo release zawiera krajowy feed kolejowy).
2. Siatka i warstwy: `make_grid.py`, `static_layers.py` (QGIS), `fetch_noise.py` → `noise_layers.py`.
3. Auto: osmosis (pbf → xml → `car_speeds.py` → xml → pbf per pora), patrz nagłówek `car_speeds.py`.
4. Macierze tranzytowe: workflow GitHub Actions `apartment-finder-matrices.yml` (15 jobów dzień × pora, ok. 2 h;
   `gh workflow run apartment-finder-matrices.yml`, wyniki: `gh run download <id>` do `data/matrices/`). Lokalnie
   to samo robi `bash scripts/run_all.sh` (wznawialne; ok. 2,2 min na scenariusz, ok. 10 h). Pieszo/rower/auto
   (nie zależą od dnia i GTFS): `bash scripts/run_nontransit.sh`.
5. `py scripts/check_invariants.py <dzień> <pora>` (I1–I4), `py scripts/aggregate.py` (mediana po dniach, naprawa I1,
   raport I5) i `py scripts/export_web.py`.

## Publikacja danych (osobne repo, bez historii)

Kod strony jest w `mapy-analizy`, dane (ok. 245 MB) w `GISBoost/gdzie-mieszkac-lodz-data` (Pages z gałęzi `gh-pages`,
ten sam origin, więc bez CORS). Każda regeneracja to ok. 250 MB niekompresowalnych binariów, więc **gałąź jest
jednokomitowa i nadpisywana `--force`** (orphan commit): repo ma rozmiar bieżących danych, nie sumy wersji.
Limity Pages: serwis ≤ 1 GB, 10 buildów/h, ok. 100 GB/mies. transferu (miękki); zapytanie o cel czyta jeden wiersz
przez `Range` (kilka KB), więc transfer to głównie `hex.json` + `layers.json` (ok. 2 MB). Nie publikować częściej
niż potrzeba i nie dokładać `data/m` do `mapy-analizy`. Publikacja: `bash scripts/publish_data.sh` (próba bez
pushowania) i `--push` (nadpisuje gałąź). Wariant 2 na przyszłość, gdyby odświeżanie stało się częste: zip danych jako
Release asset + workflow Actions z `upload-pages-artifact`/`deploy-pages`, wtedy w gicie leży tylko kod.

## Ograniczenia i zastrzeżenia metody

- Narzędzie pokazuje model, nie wyrocznię; nie jest poradą inwestycyjną ani wyceną nieruchomości.
- Czasy „zmierzone" to rekonstrukcja GTFS-RT (P50/P85) z 5 dni roboczych, nie prawda referencyjna. Dane ŁKA
  (zrekonstruowane z TripUpdates) to cienka próbka (1 dzień = 1 przebieg każdego kursu).
- Auto to przybliżenie korków: współczynnik zwolnienia kursu autobusu względem jego własnej, swobodnej prędkości
  (postoje się znoszą), przeniesiony na drogi o tej samej klasie w promieniu 1 km. Bezpośrednie dane obejmują ok. 15%
  długości dróg. Kontrast między porami jest niewielki (rano/popołudnie ok. 3%).
- Odległości po sieci pieszej mają rozdzielczość 20 m (R5 raportuje pełne minuty; liczone przy 1,2 km/h), i są
  liczone od środka heksa. Powyżej 2 km: brak wartości (strona traktuje jako „daleko").
- Czasy w macierzach są obcięte do 60 min i kwantyzowane co 2 min (błąd ≤ 1 min) — patrz `config/export.yaml`.
- Cena: brak danych w tej wersji (pusty slot). Rejestr cen nie ma otwartego API.
- Hałas: mapa akustyczna Łodzi (UMŁ, InterSIT, pomiary 2022). Licencja: informacja publiczna wg autora (2026-10-05).
  Progi dopuszczalne z rozporządzenia nie są założone w pipeline; strona stosuje próg wybrany przez użytkownika.

## Źródła danych

OpenStreetMap (ODbL), GTFS ZDiT Łódź i zrekonstruowany GTFS-RT z `GISBoost/easy-GTFS-RT`, ŁKA (kolej-lka.pl,
TripUpdates PKP PLK przez mkuran.pl), mapa akustyczna Łodzi (Urząd Miasta Łodzi).
