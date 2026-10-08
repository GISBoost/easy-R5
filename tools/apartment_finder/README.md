# apartment_finder — „Gdzie mieszkać w Łodzi?"

Pipeline danych dla publicznego narzędzia wyboru lokalizacji mieszkania w Łodzi. Frontend leży w repo
[`mapy-analizy`](https://github.com/GISBoost/mapy-analizy) (`gdzie-mieszkac-lodz/`); tu jest wszystko, co liczy
dane, które ta strona wyświetla. Specyfikacja: `docs/prd/PR_easy-R5_apartment-finder.md`, notatki z rozpoznania:
`docs/notes/apartment-finder-m0.md`.

**Wersja metody:** `apt-v1` (siatka `hex250-v1`, warstwy `static-v1` / `noise-v1`, korony drzew `canopy-v2`, auto `car-v1`, krzywe `curves-v1`).
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
| Usługi: placówki OSM (21 typów w 4 metakategoriach, z buforem 1,2 km) | `scripts/service_pois.py` (QGIS) | `data/services/poi.gpkg`, `inputs/service_pois.csv` |
| Usługi: liczba placówek w Y min, **dokładnie** (R5: środek heksa → współrzędne placówki) | `scripts/service_counts.py`, `scripts/count_services.py`, `scripts/run_services.sh` | `data/services/<dzień>/<scenariusz>.npz` |
| Eksport usług (mediana po dniach dla TP) | `scripts/export_services.py` | `<easy>/gdzie-mieszkac-lodz-data/services/*.json` |
| Korony drzew, etap 1: pobranie NMPT+NMT GUGiK 2021 per kafel (960 kafli, strumieniowo), nDSM i chropowatość | `scripts/canopy_tiles.py` (systemowy Python) | `data/canopy/codes/<godło>.tif` |
| Korony drzew, etap 2: maska (≥ 3 m, minus BDOT10k, filtr gładkości i cienkości) | `scripts/canopy_mask.py` | `data/canopy/final_v2/<godło>.tif` |
| Korony drzew, etap 3: udział koron w heksie | `scripts/canopy_hex.py` (QGIS) | `data/canopy/canopy_hex.csv` |
| Korony drzew: obraz podglądu dla strony (WebP, 8 m) | `scripts/canopy_overlay.py` | `<easy>/gdzie-mieszkac-lodz-data/canopy.webp` |
| Ceny, etap 1: transakcje mieszkań z RCN (WFS GUGiK, 345 stron, sortowane po `gid`) | `scripts/price_fetch.py` (systemowy Python) | `data/price/rcn_lokale.csv` |
| Ceny, etap 2: filtr i zł/m² (okno od 2025-07, wolny rynek, 25–120 m²) | `scripts/price_clean.py` | `data/price/price_clean.gpkg` |
| Ceny, etap 3: mediana zasięgu adaptywnego per heks (tylko heksy zamieszkałe) | `scripts/price_hex.py` | `data/price/price_hex.csv` |
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

## Korony drzew (powtórzenie kroków)

Wskaźnik: udział powierzchni heksa pod koronami drzew, 0–1 (mianownik = cała powierzchnia heksa, z budynkami i drogami).
Parametry (próg wysokości, filtry, rozdzielczość podglądu, wersja metody) w `config/canopy.yaml`, krzywa punktacji
w `config/curves.yaml` (`canopy`). Pełny raport z liczbami: `docs/notes/apartment-finder-canopy-m0.md`.

1. Siatka heksów i skorowidze: wejście to `data/grid.gpkg`; lista kafli powstaje ze skorowidza LiDAR 2021
   (WFS GUGiK, `DanePomiaroweLidarEVRF2007`), a adresy NMPT/NMT ze skorowidzów `SkorowidzNMPT2021` i `SkorowidzNMT2021`.
2. BDOT10k powiatu 1061 (GPKG, `source.bdot10k_url` w configu) rozpakować do `data/canopy/bdot/`.
3. `py scripts/canopy_tiles.py --workers 6` (ok. 35 min, ok. 22 GB transferu, wynik 90 MB; wznawialne, ASC kasowane po każdym kaflu).
4. `py scripts/canopy_mask.py --tag v2` (ok. 4 min), potem `python-qgis-ltr.bat scripts/canopy_hex.py final_v2`.
5. `py scripts/canopy_overlay.py` i `py scripts/export_web.py` (kolumna `canopy` w `layers.json` + blok `canopy` w manifeście).

Metoda: nDSM = NMPT − NMT (siatka 0,5 m). Korona = nDSM ≥ 3 m (i ≤ 50 m). Odejmowane: obrysy BDOT10k (budynki, zbiorniki,
wieże, urządzenia techniczne, obiekty sportowe z buforem 1 m; mosty/wiadukty 3 m; maszty 2–3 m), gładkie wysokie płaty
> 30 m² (jezdnie wiaduktów, płaskie dachy spoza BDOT10k) poszerzone o 2,5 m oraz obiekty cieńsze niż ok. 2 m (słupy,
latarnie, druty) i plamy < 10 m². Układy: dane LiDAR/NMPT są w EPSG:2177, siatka w 2180; agregacja po transformacji heksów do 2177.

## Ceny mieszkań (powtórzenie kroków)

Warstwa: mediana ceny transakcyjnej zł/m² z aktów notarialnych (Rejestr Cen Nieruchomości, GUGiK) w okolicy heksa. Parametry
(okno dat, filtr, zasięg, progi) w `config/price.yaml` (`price-v1`), krzywa punktacji w `config/curves.yaml` (`price`).
Raport z liczbami: `docs/notes/apartment-finder-price-m0.md`.

1. `py scripts/price_fetch.py` (ok. 5 min): WFS `mapy.geoportal.gov.pl/wss/service/rcn`, warstwa `ms:lokale`, bbox miasta (oś: północ, wschód),
   strony po 250, **koniecznie `sortBy=gid`** (bez sortowania serwer stronicuje niestabilnie: gubi i powtarza rekordy; skrypt przerywa przy duplikacie `gid`).
2. `py scripts/price_clean.py`: filtr z `price.yaml`; wynik + liczniki odrzuceń w `price_clean.meta.json`.
3. `py scripts/price_hex.py`: dla każdego heksa najmniejszy okrąg (250–1000 m wokół środka) z co najmniej 10 transakcjami z co najmniej 5 różnych
   lokalizacji, mediana ważona odległością; cena zostaje tylko w heksach z co najmniej 1000 m² obrysów budynków mieszkalnych BDOT10k.
4. `py scripts/export_web.py`: kolumny `price_m2`, `price_r`, `price_n` w `layers.json` i blok `price` w manifeście.

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
- Korony drzew: stan z nalotu z kwietnia 2021 (drzewa po nalocie mogły zniknąć lub wyrosnąć; kwiecień = drzewa bez liści, więc mierzymy zasięg koron, nie gęstość ulistnienia). Maska ma pojedyncze fałszywe trafienia (według autora ok. 1–2% zbioru: pozostałości dachów i konstrukcji, krzewy powyżej 3 m); korona nad dachem w pasie 1 m od budynku jest wycięta, więc zabudowa jest lekko niedoszacowana. Korony nad jezdniami wliczają się, jeśli model powierzchni je widzi z góry. Dla jednego kafla (śródmieście) wynik porównano z klasyfikacją chmury punktów (99% pikseli korony ma punkty klasy wysokiej roślinności, 5,8% leży w komórkach klasy „budynek”). Poziom 150 m (bufor sąsiedztwa) sprawdzono i odrzucono: korelacja z heksem 0,93.
- Cena: tylko transakcje z RCN od 2025-07 (ok. 7,7 tys. aktów). **Rejestr dla Łodzi jest prawie pusty dla lat 2019–2024** (po stronie źródła, ten sam obraz w pliku GeoPackage z Geoportalu), więc nie ma trendu ani dłuższej historii; początek okna (VII–IX 2025) jest cienki, a najnowsze akty trafiają do rejestru z opóźnieniem. Cena to mediana okolicy (do 1000 m), nie konkretnego budynku; ma ją 69% heksów zamieszkałych (29% wszystkich), reszta to brak danych (nie 0). Transakcje skupiają się w nowych inwestycjach. Ceny ofertowe deweloperów (dane.gov.pl) nie są jeszcze użyte. Warunki ponownego wykorzystania RCN do potwierdzenia przed publikacją.
- Hałas: mapa akustyczna Łodzi (UMŁ, InterSIT, pomiary 2022). Licencja: informacja publiczna wg autora (2026-10-05).
  Progi dopuszczalne z rozporządzenia nie są założone w pipeline; strona stosuje próg wybrany przez użytkownika.

## Źródła danych

Ceny transakcyjne: Rejestr Cen Nieruchomości (GUGiK, usługa WFS `mapy.geoportal.gov.pl/wss/service/rcn`; od 13.02.2026 bezpłatny, strony transakcji zanonimizowane; warunki ponownego wykorzystania do potwierdzenia przed publikacją). NMPT, NMT, chmura punktów i BDOT10k: Główny Urząd Geodezji i Kartografii (dane otwarte, udostępniane bezpłatnie na podstawie art. 40a ust. 2 Prawa geodezyjnego i kartograficznego; źródło: GUGiK, opendata.geoportal.gov.pl; treść licencji do potwierdzenia przed publikacją), OpenStreetMap (ODbL), GTFS ZDiT Łódź i zrekonstruowany GTFS-RT z `GISBoost/easy-GTFS-RT`, ŁKA (kolej-lka.pl,
TripUpdates PKP PLK przez mkuran.pl), mapa akustyczna Łodzi (Urząd Miasta Łodzi).
