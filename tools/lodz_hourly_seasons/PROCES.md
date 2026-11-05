# PROCES: od nagrań GTFS-RT do mapy „Łódź godzina po godzinie”

Dokument opisuje cały łańcuch pracy konkursowej „Łódzkie na mapach 2026” (kategoria II, autor: Michał Kaczorowski)
oraz strony interaktywnej, która z niej powstała. Jest pisany tak, żeby współautor mógł odtworzyć wynik od surowych danych
albo wejść w dowolny etap. Stan na 2026-11-05.

Ścieżki są względne wobec `easy-R5/tools/lodz_hourly_seasons/` (ten katalog), chyba że zaznaczono inaczej.
Nie wszystko jest w git, patrz sekcja 10 („Co gdzie leży i co jest na remote”).

## 1. Pytanie i wynik w jednym akapicie

**Pytanie:** ile miejsc (szkoły, przychodnie, sklepy, kultura) osiągniesz z domu w 30 minut komunikacją miejską w Łodzi,
godzina po godzinie od 6:00 do 22:00, i jak zmienia się to między sierpniem, wrześniem i październikiem 2026,
gdy rozkłady są **rzeczywiste (zrealizowane)**, a nie planowane?

**Wynik:** średnia ważona ludnością liczba miejsc w 30 min spada w ciągu dnia tylko o ok. 1% (sierpień 509,1, październik 504,2),
ale rozkład jest bardzo nierówny: **16 osiedli zyskuje (268 tys. mieszkańców), 9 traci (260 tys.), 11 bez zmian (145 tys.)**.
Najgorsza godzina to 14:00 (−21,5 miejsca, −4,3%), najlepsza 20:00 (+11,6, +2,3%). Największe zyski: Montwiłła-Mireckiego +42,7,
Koziny +29,2, Górniak +26,7. Największe straty: Katedralna −51,0, Piastów-Kurak −39,7, Śródmieście-Wschód −32,5.

**Ważne ograniczenie interpretacji:** różnica sierpień–październik łączy dwa efekty, których metoda nie rozdziela:
zmianę rozkładu jazdy (sierpień = rozkład wakacyjny, zmieniony ok. 17.08) i zmianę opóźnień (średnio ok. 6–13 s w sierpniu,
ok. 40–55 s w październiku według gtfs-dashboard). Trzy dni na miesiąc to mała próba, nie robiono testów istotności.

## 2. Łańcuch w pigułce

```
nagrywanie GTFS-RT VehiclePositions                       (easy-GTFS-RT, codziennie)
        │  rekonstrukcja „zrealizowanego” GTFS (percentyl 50 opóźnień)   (easy-OTP, Family A)
        ▼
GitHub Release  lodz-realized-<dzień> / lodz-realized-<miesiąc>           (asset lodz_realized_<dzień>_p50.zip)
        │  wybór 9 dni (3 na miesiąc) wg gtfs-dashboard                  (config.yaml)
        ▼
ci_hourly.py (GitHub Actions, 1 job = 1 dzień, 16 uruchomień R5)         (workflow lodz-hourly-seasons.yml)
        │  data/<dzień>.npz   uint16 [godzina, typ(21), heks]
        ▼
aggregate.py   mediana z 3 dni → 4 metakategorie → data/seasons.npz, summary.json
        │
        ├─► export_web.py + export_hexinfo.py  →  strona MapLibre (mapy-analizy)
        │
        └─► export_submission.py → osiedla_stats.py → build_podklad.py → build_siec.py → build_qr.py
              │  shapefile'e EPSG:2180, hekso-osiedla, podkład OSM, sieć GTFS, kody QR
              ▼
            QGIS: build_qgz.py → build_plansza.py → export_plansza.py
              ▼
            add_pdf_links.py → make_zip.py → submission/michal_kaczorowski.zip
```

## 3. Dane wejściowe i skąd są

| Dane | Źródło | Jak zebrane | Gdzie leży |
|---|---|---|---|
| **Pozycje pojazdów (GTFS-RT VehiclePositions)** Łodzi | otwarte dane ZDiT Łódź | nagrywane codziennie w workflow `easy-GTFS-RT` (publiczne repo, GitHub Actions) | niewersjonowane surowe; wynik w Releases |
| **Zrealizowany GTFS (P50)** | rekonstrukcja z nagrań, narzędzie Family A (`easy-OTP/tools/family_a_reconstruction`) | każda stacja/kurs dostaje czas „co się faktycznie wydarzyło” (percentyl 50), rekonstrukcja opisana w `easy-GTFS-RT/HOW-IT-WORKS.md` (PL: `HOW-IT-WORKS.pl.md`) | GitHub Releases `GISBoost/easy-GTFS-RT`, tag `lodz-realized-<dzień>-phone` lub miesięczny `lodz-realized-<YYYY-MM>`; lokalnie `data/gtfs/<dzień>/` |
| Przegląd dni i jakości nagrań | `gtfs-dashboard` (gisboost.github.io/gtfs-dashboard), `manifest.json` z Releases API | codziennie 04:00 UTC | publiczne |
| **OSM Łodzi** (sieć pieszą i miejsca) | Geofabrik `lodzkie-latest.osm.pbf` | wycięcie bbox (19.1672, 51.6035)–(19.7404, 51.9155) z `completeWays=yes` w jobie `osm` workflow'u | artefakt CI; lokalnie `../lodzkie_na_mapach_2026/work/pbf/lodz.osm.pbf` |
| **Miejsca (POI)** | OSM, 21 typów w 4 metakategoriach (`../apartment_finder/config/services.yaml`), z buforem 1,2 km poza miastem | `../apartment_finder/scripts/service_pois.py` (QGIS), ok. 4500 punktów | `../apartment_finder/inputs/service_pois.csv` |
| **Siatka** 5662 heksów, 250 m (`hex250-v1`), środek w granicy miasta | `../apartment_finder/scripts/make_grid.py` | | `../apartment_finder/data/grid.gpkg`, `inputs/lodz250_hex_origins.csv` |
| **Ludność** | GUS NSP 2021, rozdzielona dasymetrycznie na heksy (budynki OSM) | w pracy konkursowej bazie `lodzkie_base.gpkg`, warstwa `hex_lodz_all.pop_total` | `../lodzkie_na_mapach_2026/lodzkie_base.gpkg`; służy **tylko do wag** |
| **Osiedla** (36) | OSM `admin_level=11`, przycięte do miasta | | `../tram_failure_lodz/grids/h250.gpkg`, warstwa `osiedla` |
| Sieć linii i przystanków do mapy | GTFS ZDiT z 10.09.2026 | `build_siec.py` | `data/gtfs/2026-09-10/` |

Typy miejsc (21 → 4 grupy):
- **edukacja:** przedszkole, szkoła, uczelnia
- **zdrowie:** przychodnia, szpital, apteka
- **handel i usługi:** supermarket, sklep osiedlowy, centrum handlowe, targowisko, poczta, urząd
- **kultura i rekreacja:** biblioteka, dom kultury, kino, teatr, muzeum, plac zabaw, siłownia, basen, boisko

## 4. Dobór dni (`config.yaml`)

Trzy dni robocze (wt–czw) na miesiąc, wybrane 2026-11-01 z manifestu gtfs-dashboard (status `ok`, pełne pokrycie 06–22):

| Miesiąc | Dni |
|---|---|
| sierpień | 2026-08-04, 05, 13 |
| wrzesień | 2026-09-08, 09, 10 |
| październik | 2026-10-06, 07, 08 |

Kryteria: ten sam `service_id` w obrębie miesiąca (rozkład sierpniowy zmienił się ok. 17.08: 9363 → 9892 kursów; wrzesień i październik stabilne);
średnie opóźnienie i udział zmienionych kursów zbliżone do typowych dla miesiąca; pominięto dni nietypowe (12.08, 25–26.08, 17–18.09, 14.10 = dzień wolny od zajęć).
Warstwa miesiąca to **mediana z 3 dni** dla każdego heksa i godziny (liczba nieparzysta, więc mediana jest realną wartością).

Bez ŁKA: zrealizowany feed kolejowy jest niewiarygodny, a statyczny zatarłby efekt opóźnień. Bez wariantu statycznego: celem jest pomiar wpływu opóźnień.

## 5. Obliczenia routingowe (`scripts/ci_hourly.py`, workflow `.github/workflows/lodz-hourly-seasons.yml` w `easy-R5`)

Silnik: **Conveyal R5 v7.6** przez wtyczkę Easy-R5 (`easy_r5.core`), Java 21, pinowany jar `r5-v7.6-all.jar`.

Workflow `workflow_dispatch`: job `plan` (9 dni z `config.yaml`), job `osm` (jedno wspólne wycięcie OSM, żeby różnice między miesiącami pochodziły tylko z transportu),
job `compute` (jeden na dzień, 120 min limit, 11 GB sterty).
Dla dnia: pobranie `lodz_realized_<dzień>_p50.zip` z Releases, budowa sieci raz, guard „czy w dniu jest ruch” (ochrona przed cichym wynikiem tylko pieszym),
potem **16 uruchomień macierzowych R5, po jednym na godzinę 06…21**.

Parametry R5 dla każdego uruchomienia:

| Parametr | Wartość |
|---|---|
| Początki | 5662 środki heksów |
| Cele | ok. 4500 POI (OSM) |
| Okno odjazdu | 60 minut od `h:00` (godzina zegarowa) |
| Percentyl | 50 po minutach odjazdu w oknie |
| Maks. czas podróży | 30 min (`cutoff_min`) |
| Maks. czas dojścia | 30 min (ucięcie równe progowi nie traci informacji) |
| Chód | 3,6 km/h, dostęp i dojście pieszo |
| Przesiadki | bez limitu |
| Monte Carlo | wg `../apartment_finder/config/scenarios.yaml` |

Z macierzy czasów liczone jest `count_within`: dla każdego heksa liczba POI z `travel_time_p50 ≤ 30`, osobno dla każdego z 21 typów.
(Nie używamy `count_services.py`, bo obcina do 255, a centrum może to przekroczyć.)
Wynik dnia: `data/<dzień>.npz`, tablica uint16 `[godzina, typ, heks]`; zapis jest wznawialny godzina po godzinie.

## 6. Agregacja (`scripts/aggregate.py`)

1. Dla każdego miesiąca mediana z 3 dni (`np.median` po osi dni), asercje: te same godziny i typy we wszystkich dniach, nieparzysta liczba dni.
2. Sumowanie 21 typów do 4 metakategorii → `data/seasons.npz`, tablica uint16 `[miesiąc, godzina, meta, heks]`.
3. `data/summary.json`: średnia ważona ludnością liczba miejsc dla każdej kombinacji (miesiąc, godzina, meta). Ludność z warstwy `hex_lodz_all.pop_total`
   dopasowana do 5662 heksów po centroidzie (obie siatki mają ten sam przepis, centroid wpada w jeden heks; 0 heksów bez dopasowania).

## 7. Strona interaktywna (`mapy-analizy/lodz-dostepnosc-godzinowa/`)

URL (nie zmieniać, jest w kodzie QR na planszy): <https://gisboost.github.io/mapy-analizy/lodz-dostepnosc-godzinowa/>.
Vanilla JS, MapLibre GL 4.7.1 (unpkg z SRI), bez build stepu, rastrowy podkład OSM (odwracany w trybie ciemnym), słupki `fill-extrusion`
sterowane `feature-state`.

Dane strony generują dwa skrypty:
- `scripts/export_web.py` → `data/counts.bin` (uint16 LE, układ `[miesiąc][meta][godzina][heks]`), `data/hex.geojson` (5662 heksów, EPSG:4326, kolejność = `hex_id` = kolumna w `counts.bin`), `data/manifest.json` (układ, nazwy, średnie ważone).
- `scripts/export_hexinfo.py` → `data/hexinfo.json`: osiedle zawierające środek heksa i najbliższy słupek przystankowy (tramwaj, jeśli słupek leży w 20 m od linii tramwajowej, inaczej autobus) wraz z odległością. Czyta dane z `submission/dane/` (czyli wymaga wcześniej kroku 8).

Szczegóły architektury, designu i testowania: `mapy-analizy/HANDOFF_strona_godzinowa.md` (plik lokalny) oraz `mapy-analizy/PLAN_dostepnosc-godzinowa-lodz.md`.
Commity strony: `7c18999` (pierwsza wersja), `abaf14d` (MapLibre 2D/3D, mobilny arkusz), `70e35b5` (ekran ładowania, animacje), `cf8ce741` (inspekcja domyślnie wyłączona, osiedle i przystanek w opisie, gesty arkusza, poprawka migania).

## 8. Paczka konkursowa i plansza

Regulamin wymaga: `.shp` lub `.gdb` (GeoPackage nie jest wymieniony), projektu (`.qgz`), plików graficznych (pdf/png/jpg/tiff) z wydrukiem mapy,
Załącznika nr 1, układu EPSG:2180 lub 4326, nazwy `imie_nazwisko.zip`.

Kolejność odtwarzania (zachować):

1. `py scripts/aggregate.py` → `data/seasons.npz`
2. `py scripts/export_submission.py` → shapefile'e w `submission/dane/` (EPSG:2180) i `slownik_pol.csv`. Nazwy pól ≤ 10 znaków, więc każdy miesiąc i każda różnica to osobna warstwa z polami `<kat>_<gg>` (kat: all, edu, zdr, han, kul; gg: 06…21), różnice z prefiksem `d`. Zygzaki w obrysie z szumu 1e-10 m naprawia `shapely.set_precision(0.001)`.
3. `py scripts/osiedla_stats.py` → `hekso_osiedla.shp`, `osiedla_statystyki.csv`, pole `osiedle` w warstwach heksów. Heks trafia do osiedla zawierającego jego środek (5410 z 5662), statystyki ważone ludnością (powierzchnią, gdy brak ludności), średnia z 16 godzin; „zyskuje/traci”, gdy |zmiana| > 2 miejsca. **Uwaga: krok 2 nadpisuje pole `osiedle`, więc krok 3 zawsze po nim.**
4. `py scripts/build_podklad.py` → OSM jako shapefile'e (drogi, tramwaje, kolej, rzeki) z marginesem 1,5 km
5. `py scripts/build_siec.py` → `siec_linie.shp`, `siec_przystanki.shp` (GTFS z 10.09.2026) i `plansze/stats.json` z liczbami drukowanymi na planszy
6. `py scripts/build_qr.py` → kody QR (SVG): mapa interaktywna i repo `GISBoost/easy-R5`
7. W QGIS (konsola Pythona, `exec(open(...).read())`): `build_qgz.py` (warstwy i skala), `build_plansza.py` (warstwy planszy, motywy, układ A2), `export_plansza.py` (PDF i PNG 200 dpi)
8. `py scripts/add_pdf_links.py` (dokleja klikalne linki do PDF jako przyrostową aktualizację; `--check` weryfikuje), potem `py scripts/make_zip.py` → `submission/michal_kaczorowski.zip`

Skala (stałe okrągłe progi, wspólne dla wszystkich godzin, miesięcy i kategorii): wartości 1–4, 5–9, 10–24, 25–49, 50–99, 100–199, 200–399, 400–799, 800+;
zmiana ±1–4, 5–19, 20–49, 50–99, ≥100; zero nie jest rysowane.

Plansza A2 pionowa (420×594 mm), tytuł „Ile miasta tracimy po wakacjach?”: mapa główna (średnia z dnia), kolumna statystyk, wykres 16 godzin, ranking 36 osiedli,
najgorsza (14:00) i najlepsza (20:00) godzina, mapa sieci z GTFS, dwa klikalne QR. **Mistrzem układu jest `lodz_godzinowa.qgz`, nie `build_plansza.py`:** ma ręczne poprawki autora; ponowne uruchomienie skryptu je skasuje.

Pułapki:
- QGIS wywala się przy automatycznej legendzie, legendy są ręcznymi prostokątami i etykietami.
- Otwarty projekt blokuje shapefile'e; przed `export_submission.py` wyczyść projekt (`QgsProject.instance().clear()`).
- Po każdym ponownym eksporcie PDF trzeba ponownie uruchomić `add_pdf_links.py`. PNG nie ma linków.
- `QFont.setLetterSpacing` rozstawia znaki w `QgsTextFormat`; nie używać.

Dokumenty o planszy: `HANDOFF_plansza.md`, `AUDYT_planszy.md`, `RESEARCH_plansze.md`, `PROMPT_audyt_planszy.md`, `CHECKLISTA_wysylka.md`.

## 9. Wyniki końcowe

Pliki wynikowe w `submission/` (lokalne, 164 MB, w `.gitignore`):
- `michal_kaczorowski.zip` (paczka; Załącznik nr 1 dokładany ręcznie, zob. `zalacznik/`), `lodz_godzinowa.qgz`
- `dane/`: `hex_sierpien`, `hex_wrzesien`, `hex_pazdziernik`, `roznica_paz_sie`, `roznica_paz_wrz`, `roznica_wrz_sie`, `hekso_osiedla`, `granica_heksow`, `podklad/`, `siec/`, `slownik_pol.csv`, `osiedla_statystyki.csv`
- `plansze/plansza_A2_mapa_zmian_osiedli.pdf` i `.png`, `opis/opis_metody.pdf`

Liczby kluczowe: średnia ważona o 8:00 sierpień 518,9 / wrzesień 510,3 / październik 515,8; średnia z całego dnia (16 godzin): sierpień 509,1, październik 504,2 (−1,0%; `plansze/stats.json`, pole `day_*`; pole `gtfs_day` = 2026-09-10 dotyczy tylko mapy sieci); ok. 300 tys. z 697 tys. mieszkańców ma mniej miejsc w zasięgu w październiku niż w sierpniu, ok. 335 tys. więcej.

## 10. Co gdzie leży i co jest na remote (stan na 2026-11-05)

Repo `easy-R5` jest publiczne. W gicie są tylko skrypty obliczeniowe i eksport strony. Skrypty planszy i paczki konkursowej,
`HANDOFF_plansza.md` i `AUDYT_planszy.md` są **celowo w `.gitignore`** (lokalne) i przekazywane osobno w paczce.

| Co | Gdzie | Remote |
|---|---|---|
| `ci_hourly.py`, `aggregate.py`, `export_web.py`, `export_hexinfo.py`, `config.yaml`, `README.md`, workflow `lodz-hourly-seasons.yml` | `easy-R5/tools/lodz_hourly_seasons/` | tak (`main`) |
| Skrypty planszy i paczki: `export_submission.py`, `osiedla_stats.py`, `build_podklad.py`, `build_siec.py`, `build_qr.py`, `build_qgz.py`, `build_plansza.py`, `export_plansza.py`, `add_pdf_links.py`, `make_zip.py` | `scripts/` | **nie** (ignorowane), w paczce dla współautora |
| `HANDOFF_plansza.md`, `AUDYT_planszy.md` (i robocze `PROMPT_*`, `RESEARCH_*`, `CHECKLISTA_*`) | ten katalog | **nie** (ignorowane) |
| Wyniki dni, `seasons.npz`, GTFS | `data/` | **nie** (dane się nie wersjonuje); GTFS odtwarzalny z Releases |
| Paczka konkursowa i plansze | `submission/` | **nie** (ignorowane) |
| Strona | `mapy-analizy/lodz-dostepnosc-godzinowa/` | tak (`GISBoost/mapy-analizy`) |
| Dane wejściowe GTFS | Releases `GISBoost/easy-GTFS-RT`, dashboard `GISBoost/gtfs-dashboard` | tak, publiczne |

### Zależności spoza tego katalogu (ten sam repo `easy-R5`)

| Potrzebne | Skąd | W gicie? |
|---|---|---|
| Konfiguracja usług i scenariuszy R5 (`services.yaml`, `scenarios.yaml`), lista POI (`inputs/service_pois.csv`, ok. 4500 punktów), środki heksów (`inputs/lodz250_hex_origins.csv`), `prepare_gtfs.py`, `ci_matrices.py`, `make_grid.py`, `service_pois.py` | `../apartment_finder/` | **tak** |
| Geometria siatki `grid.gpkg` (5662 heksów) | `../apartment_finder/data/grid.gpkg` (2 MB, odtwarzalna przez `make_grid.py`) | nie (`data/` ignorowane) |
| Ludność na heksach `hex_lodz_all.pop_total` (dasymetria GUS NSP 2021 po budynkach OSM) | `../lodzkie_na_mapach_2026/lodzkie_base.gpkg` (168 MB); skrypty: `../lodzkie_na_mapach_2026/old/{prepare_population,dasymetric_population}.py` | skrypty tak, gpkg nie |
| OSM Łodzi | `../lodzkie_na_mapach_2026/work/pbf/lodz.osm.pbf` (27 MB), w CI wycinany z Geofabrik | nie |
| Osiedla (36, OSM `admin_level=11`) | warstwa `osiedla` w `../tram_failure_lodz/grids/h250.gpkg` (3 MB) | nie (`*.gpkg` ignorowane) |

Wniosek: **samo obliczenie godzinowe (`ci_hourly.py`) odtwarza się wyłącznie z gita i publicznych Releases.** Do agregacji z wagami ludnościowymi
potrzebny jest `lodzkie_base.gpkg`, a do osiedli `h250.gpkg`; tych plików w gicie nie ma.

### Jak udostępnić dane współautorowi
Do repo nie wrzucamy danych ani Releases (żeby nie mieszać z wydaniami wtyczki). Współautor dostaje paczkę osobno (dysk lub mail):
wyniki obliczeń (`data/*.npz`, `summary.json`, `config.yaml`), skrypty planszy i paczki, oba pliki `.md` oraz małe pliki `.gpkg` (`grid.gpkg`, `h250.gpkg`);
`lodzkie_base.gpkg` (168 MB) i `lodz.osm.pbf` (27 MB) tylko jeśli ma liczyć od zera. Paczka konkursowa (`michal_kaczorowski.zip`) osobno.

## 11. Znane ograniczenia (do artykułu)

- Zmiana między miesiącami łączy zmianę rozkładu i opóźnień; metoda ich nie rozdziela. Kontrfaktyczny wariant „ten sam rozkład, różne opóźnienia” wymagałby np. porównania wrzesień–październik (ten sam `service_id`).
- Trzy dni na miesiąc, brak testów istotności i przedziałów ufności. Zmiany rzędu kilku miejsc mieszczą się w zmienności dobowej.
- Liczba miejsc nie uwzględnia wielkości ani jakości; kompletność OSM jest nierówna. Heksy brzegowe łapią część sąsiednich gmin (bufor 1,2 km).
- Osiedla mają od 5 do ok. 400 heksów, granice są heksowe (250 m). Próg „bez zmian” (2 miejsca) jest umowny.
- Dane tylko dla Łodzi (tylko tu istnieje nagrywanie GTFS-RT w tej konfiguracji).
- Zrealizowany GTFS jest rekonstrukcją (percentyl 50, interpolacja); jakość zależy od pokrycia nagrań, zob. `HOW-IT-WORKS.md` w `easy-GTFS-RT`.
- Dane przetworzone z pomocą generatywnej AI (zapis w opisie metody).
