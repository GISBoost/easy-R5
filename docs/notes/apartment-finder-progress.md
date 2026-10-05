# „Gdzie mieszkać w Łodzi?" — postęp i kontekst dla kolejnego agenta

Ostatnia aktualizacja: 2026-10-05, ok. 12:00. **Czytaj najpierw ten plik**, potem PRD i prompt.

| Dokument | Rola |
|---|---|
| [`docs/prd/PR_easy-R5_apartment-finder.md`](../prd/PR_easy-R5_apartment-finder.md) | **Co** budujemy: zakres, decyzje (§4), model punktacji, pipeline, kamienie milowe (§13). Źródło prawdy dla zakresu. |
| [`docs/prompts/easy-R5_apartment-finder_prompt.md`](../prompts/easy-R5_apartment-finder_prompt.md) | **Jak** pracować: zasady, warunki zatrzymania i eskalacji (np. I1/I3 złamany → stop i pytanie). |
| **ten plik** | **Gdzie jesteśmy**: co zrobione, co nie, jak wznowić, otwarte decyzje. |
| [`docs/notes/apartment-finder-m0.md`](apartment-finder-m0.md) | Raport M0 (liczby, rozpoznanie danych, propozycje odpowiedzi O3–O16). |
| [`tools/apartment_finder/README.md`](../../tools/apartment_finder/README.md) | Pipeline: skrypty, konfiguracja, uruchomienie, ograniczenia metody. |
| `../mapy-analizy/gdzie-mieszkac-lodz/` (+ `README.md`) | Frontend (osobne repo `mapy-analizy`). |

Reguły repo (CLAUDE.md, oba poziomy): **nie commituj/nie pushuj bez prośby**, jedno repo = jeden commit, komunikaty po
angielsku, dane nie są wersjonowane, `py` zamiast `python`, `gh` tylko pełną ścieżką
`C:\Program Files\GitHub CLI\gh.exe`. Michał poprosił o pracę **na obu repo** (`easy-R5` i `mapy-analizy`) i o krótkie
raporty „do jakiego etapu przechodzisz" zamiast zatrzymań po każdym kamieniu.

## Decyzje Michała z czatu (2026-10-05), poza PRD §4

- Siatka: własna hex **250 m** (nie H3). Pory dnia: rano 07–09, południe 11–14, **popołudniowy szczyt 15–18 (dodany)**,
  cały dzień 06–22. Domyślny kierunek rano „do celu" (analiza w PRD §5.2a; **poprawka**: oba kierunki z jednej macierzy,
  „do celu" = kolumna, „od celu" = wiersz).
- Dni: 28.09, 29.09, 30.09, 01.10, 02.10.2026 (zatwierdzone). Cena: **pusty slot**, Michał poszuka danych i prześle.
- Podkład mapy: **kafle OSM jak na innych stronach mapy-analizy** (świadomy wyjątek od zakazu z promptu).
- M5 liczone w **GitHub Actions** (workflow `apartment-finder-matrices.yml`). Pieszo/rower/auto lokalnie.
- I1 (ŁKA): wybrano „napraw przed M5" → monotoniczna naprawa w `aggregate.py` z twardym limitem 1e-6 par.
- Zgoda na commit+push na `main` w easy-R5 (zrobiony: `de843f5`). W `mapy-analizy` **nic nie zacommitowano**.
- Rozmiar: jeśli dane są za duże, można rozważyć **osobne repo na dane** — najpierw kodowanie i treści.
- Michał ma otwarty QGIS (**MCP QGIS działa**, `mcp__qgis__ping` → pong) i chce sam sprawdzić warstwy hałasu.

## Stan kamieni milowych (PRD §13)

| M | Stan | Szczegóły |
|---|---|---|
| M0 rozpoznanie | **zrobione** | `apartment-finder-m0.md`. Headless (O16): TAK (`scripts/_qgis_env.py`). |
| M1 siatka + warstwy statyczne | **zrobione** | 5662 heksów; `static_layers.csv`. Poprawka zieleni: hex z centrum **wewnątrz** terenu zieleni ma 0 m (wcześniej liczono do brzegu, 836 heksów zaniżonych). |
| M2 hałas | **zrobione, czeka na kontrolę Michała w QGIS** | `fetch_noise.py` + `noise_layers.py` (rasteryzacja 10 m). Udziały powierzchni ≥ N dB; progi poniżej najniższego raportowanego poziomu = brak danych. Do kontroli: rastery 10 m (`py scripts/noise_layers.py --dump-rasters` → `data/noise/check/*.npy`, GeoTIFF-y zbudowane i załadowane do otwartego QGIS jako grupa „Halas - kontrola” razem z warstwą heksów `hex_layers.geojson` i terenami zieleni). Uwaga: model akustyczny pokrywa obszar zbliżony do granic miasta; brzeg bywa uciety — heks poza zasięgiem modelu ma udział 0, nie „brak danych”. **Licencja mapy akustycznej niepotwierdzona.** |
| M3 auto | **zrobione** | `car_speeds.py`; współczynnik zwolnienia autobusu względem jego swobodnej prędkości (postoje się znoszą). Bezpośrednie dane ≈ 15% długości dróg; kontrast rano/popołudnie tylko ≈ 3%. Kontrola ręczna ~5–10 tras vs planer: **do zrobienia przez Michała**. |
| M4 pilotaż | **zrobione** | 1 dzień, pora rano, 15 scenariuszy. I1: 3 pary / 32 mln (artefakt limitu marszu, naprawiany), I2/I3/I4 OK. Rozmiar i czas zmierzone. **Pilotaż 150 m na fragmencie: NIE zrobiony** (PRD §13 M4). |
| M5 pełne liczenie | **zrobione 2026-10-05** | Run 37290363728: 15 jobów (5 dni × rano/południe/popołudnie) ok; 5 jobów „allday" anulowanych, **okno „cały dzień" porzucone decyzją Michała** (zbyt szerokie; usunięte z `config/time_windows.yaml`, `run_all.sh`, `run_nontransit.sh`). I1/I3 ok we wszystkich 15 przebiegach; `aggregate.py` i `export_web.py` przeszły, `data/m` = 41 scenariuszy, ok. 245 MB. Strona przetestowana na pełnych danych (3 okna, brak błędów w konsoli). **Hosting (decyzja 2026-10-05, wariant B):** dane w osobnym repo `gdzie-mieszkac-lodz-data` (lokalnie `easy/gdzie-mieszkac-lodz-data/`, `export_web.py` pisze tam; strona czyta `../../gdzie-mieszkac-lodz-data/`), jednokomitowa gałąź `gh-pages` nadpisywana `--force`. Repo **utworzone** (publiczne, puste: `GISBoost/gdzie-mieszkac-lodz-data`), skrypt `scripts/publish_data.sh` jest (próba przeszła, 248 MB); **dane jeszcze nie wypchnięte** (`--push` po zgodzie). Licencja hałasu: Michał uznał mapę za informację publiczną (2026-10-05). Wariant 2 (Release asset + Actions) odłożony na później, opis w README pipeline'u. Do posprzątania: klucze `win_allday` w `i18n.js`, kolumny `freq_*_allday`, `allday_car` w `data/`. |
| M6 frontend | **zrobione, przetestowane lokalnie na pełnych danych** | `mapy-analizy/gdzie-mieszkac-lodz/`. Nie sprawdzone: telefon, EN, karta „dlaczego ten wynik" na pełnych danych, test na żywo (Pages). |
| M7 cena, QA, README, wdrożenie | **nie zrobione** | patrz „Do zrobienia". Wdrożenie dopiero po zgodzie Michała. |

## Co dokładnie zostało do zrobienia (kolejność)

1. **Dokończyć M5:** `gh run view 37290363728 --repo GISBoost/easy-R5` (powinno być `completed/success`). Jeśli joby padły:
   zobacz logi, popraw `scripts/ci_matrices.py`, uruchom ponownie (`gh workflow run apartment-finder-matrices.yml`; skrypt
   jest wznawialny na poziomie scenariusza, ale artefakty nie przenoszą się między runami). Pobierz wyniki:
   `gh run download 37290363728 --repo GISBoost/easy-R5 --dir tools/apartment_finder/_dl`, rozpakuj `*.npz`/`*.json`
   do `tools/apartment_finder/data/matrices/<dzień>/` (artefakty mają nazwę `apt-matrices-<dzień>-<pora>`).
2. Sprawdź `data/nontransit.log` (ma kończyć się `NONTRANSIT_FINISHED`; walk/bike/car leżą w `data/matrices/2026-10-02/`).
3. `py scripts/check_invariants.py <dzień> <pora>` dla każdej pary (I1–I4; I1/I3 złamany powyżej tolerancji = **STOP i pytanie**).
4. `py scripts/aggregate.py` (mediana 5 dni, naprawa I1, raport I5 w `data/agg/i5_report.json`).
5. `py scripts/export_web.py` (zapisuje do `easy/gdzie-mieszkac-lodz-data/`, osobne repo danych). Sprawdź rozmiar katalogu `data/`
   (cel: dobrze poniżej 1 GB razem z resztą repo; `mapy-analizy` ma już ok. 600 MB treści + .git 212 MB, więc może być
   potrzebne **osobne repo na macierze** — wtedy zmienić ścieżkę `data/m/` w `app.js` na adres zewnętrzny z CORS i `Range`).
6. Test strony na pełnych danych (zob. „Jak testować"), PL/EN, telefon, wszystkie 4 pory, ŁKA wł./wył., P50/P85.
7. M7: cena (pusty slot już jest w UI), README (są), zastrzeżenia (są w stopce), wpis w `sitemap.xml` w `mapy-analizy`
   (przy wdrożeniu), raport licencji źródeł. **Pilotaż 150 m** (M4) — nadal otwarty.
8. Zaproponuj Michałowi commity (jeden na repo): easy-R5 (zmiany po `de843f5`: poprawka zieleni, hałas, `aggregate.py`,
   `run_nontransit.sh`, PRD/notes/progress) i `mapy-analizy` (cały folder `gdzie-mieszkac-lodz/` + karta w `index.html`,
   `i18n.js`, `README.md`). **Nie commituj bez prośby.**

## Otwarte decyzje i pytania do Michała

- **Licencja danych hałasu** (UMŁ) — serwis jej nie podaje; Michał uznał mapę za informację publiczną (2026-10-05), odnotowane w README repo danych.
- **Podkład OSM:** hotlink jak na innych stronach (decyzja Michała), ale polityka OSM tego zabrania przy większym ruchu.
- **Wiek OSM:** pieszo/rower/auto liczone lokalnie na wycinku z 23.08.2026, CI liczy transport na bieżącym Geofabrik.
  Ujednolicenie: wrzucić `lodz.osm.pbf` jako release w easy-R5 i podać `osm_release` w workflow (wymaga zgody — publikacja).
- **Rozmiar / hosting macierzy** (zob. pkt 5 wyżej), być może osobne repo lub Cloudflare R2.
- **Parametry krzywych** (`config/curves.yaml`) i okna czasowe — propozycje Claude Code, do zatwierdzenia przez Michała.
- **Progi hałasu z rozporządzenia (O13)** nie są założone w pipeline; strona stosuje próg użytkownika (domyślnie
  Lden 65/65/60 dB hard, 60/60/55 soft). Zweryfikować z rozporządzeniem przed publikacją.
- **ŁKA realized** to 1 dzień = 1 przebieg każdego kursu (cienka próbka, pre-release w easy-GTFS-RT).
- Nazwa i adres podstrony: robocza `gdzie-mieszkac-lodz` (O1).

## Znane ograniczenia i pułapki (nie odkrywaj od nowa)

- **Zieleń:** wejścia = wierzchołki obrysu terenów ≥ 1 ha co 100 m (nie centroid!), plus 0 m dla heksa z centrum w środku.
- **Statyczny feed ŁKA w release to krajowy feed kolejowy** (7591 kursów/dzień); `prepare_gtfs.py` filtruje go do kursów
  ŁKA z wersji zrealizowanej (331/dzień). Realized P50/P85 zawiera tylko ŁKA.
- **Hałas:** warstwy mają różne dolne granice (droga od 55 dB Lden / 50 dB Ln; tramwaj/kolej mają pasmo „poniżej X" z
  ujemnym LMIN, pomijane). Serwer UMŁ czasem zwraca timeout — `fetch_noise.py` ponawia i wznawia.
- Wtyczka nie startuje w `qgis_process` (potrzebuje `iface`); skrypty dodają provider ręcznie i **muszą go trzymać w
  referencji** (inaczej GC → „Error creating algorithm from createInstance()"); ustaw org/app name QSettings na QGIS/QGIS3.
- R5 raportuje pełne minuty: odległości pieszo liczone przy 1,2 km/h (1 min = 20 m), cap 2 km.
- `network.dat` nie jest wersjonowany (CLAUDE.md); cache w `data/networks/` i `_ci_work/`. Ścieżki do `BuildNetwork` muszą
  być bezwzględne.
- `export_web.py` regeneruje `manifest.json` z tego, co leży w `data/m/` (nie tylko z bieżącego przebiegu).
- Po `--only` w eksporcie sprawdź, że `manifest.json` nadal wymienia wszystkie scenariusze.
- Format macierzy `HXM1` i kodowanie różnicowe: nagłówek `scripts/export_web.py`, dekoder `app.js` (`readVector`);
  zweryfikowane dekodowaniem w Pythonie (zgodne ze źródłem).

## Jak testować

- Strona: `cd easy && py -m http.server 8766` (katalog nadrzędny obu repo), potem `http://localhost:8766/mapy-analizy/gdzie-mieszkac-lodz/`.
- Silnik punktacji: `node mapy-analizy/gdzie-mieszkac-lodz/score.test.js`.
- Stan przez URL, np. cel na Piotrkowskiej: hex 2236 (`#s=` + JSON, zob. `saveHash` w `app.js`).
- Chrome MCP: zrzuty ekranu często wygasają przy obciążonym CPU; stan sprawdzaj przez `javascript_tool`.
- Pipeline lokalnie: interpreter QGIS `C:/Program Files/QGIS 3.40.4/bin/python-qgis-ltr.bat scripts/<skrypt>.py`; reszta `py`.

## Mapa plików

`tools/apartment_finder/` (easy-R5): `config/*.yaml` (wszystkie parametry), `scripts/` (patrz README tego folderu),
`inputs/lodz250_hex_origins.csv` (zamrożona siatka dla CI), `data/` (gitignored: grid, static, noise, car, networks,
matrices, agg), `_ci_work/` (gitignored). `.github/workflows/apartment-finder-matrices.yml`.
`mapy-analizy/gdzie-mieszkac-lodz/`: `index.html`, `app.js`, `score.js`, `score.test.js`, `i18n.js`, `styles.css`,
`README.md`, `data/` (generowane).

## Poprawki po testach Michała (2026-10-05, wieczór) — zrobione lokalnie, NIE wypchnięte

- **Hałas (UI i punktacja):** suwak = *ważność ciszy* (opis przy suwakach), ocena stopniowana z trzech progów
  (kara 1/3 przy L, 2/3 przy L+5, pełna przy L+10 dB; `noisePenalty` w `score.js`), jeden blok na źródło
  (ważność + próg komfortu + wymaganie twarde z **wpisywanym %** i wyborem dB w krokach 5 dB mapy źródłowej),
  szyny i przemysł zwinięte w „Pozostałe źródła". Heksy poza zasięgiem modelu akustycznego (14) = brak danych
  (`noise_layers.py`, wymaga ponownej publikacji `layers.json`). Stan w hashu: klucz `nc`.
- **Dochodzenie „P50 i ŁKA nic nie zmieniają":** aplikacja działa poprawnie (dekodowanie zgodne z danymi, liczby na stronie
  = liczby z macierzy). Przyczyny: bez celów czas przejazdu nie wchodzi do wyniku (dodano komunikat); P50 ≈ rozkład
  (średnio +0,3 min rano, +0,8 popołudniu; P85: +4,5/+5,5 min i 7–8% par traci dostępność); ŁKA zmienia czas
  tylko dla części par (do Pl. Wolności: +5 z 5662 heksów w limicie 45 min; do CKD przy Czechosłowackiej: +92).
  Dodano przy celu informację „ŁKA zmienia czas do tego celu o ≥ 2 min dla N heksów".
- **Usługi codzienne:** tylko zaplanowane (wersja 3: 5 kryteriów „co najmniej X placówek w Y min", jeden tryb na kryterium; hybryda dokładny R5 + skrót na macierzach; testy wykonalności zrobione), patrz [`apartment-finder-uslugi-plan.md`](apartment-finder-uslugi-plan.md).

## Usługi codzienne (2026-10-05, wieczór) — wdrożone lokalnie

5 kryteriów „co najmniej X placówek w ≤ Y min”, jeden tryb na kryterium; **dokładna metoda** (R5: środek heksa → współrzędne
placówki, także do 1,2 km za granicą miasta). Skrypty: `service_pois.py` (OSM → `inputs/service_pois.csv`, 1837 punktów),
`service_counts.py` + `count_services.py` + `run_services.sh` (walk, bike, car×3 pory, TP × pora × rozkład/P50/P85 × ŁKA × 5 dni;
przesiadki bez limitu), `export_services.py` (mediana po dniach → `gdzie-mieszkac-lodz-data/services/`). Frontend: sekcja „Usługi
w zasięgu” (`app.js`, `score.js`: `serviceScore`, test w `score.test.js`), stan w hashu `sv`. **Po zmianie danych:** `export_services.py`,
potem `publish_data.sh --push` (za zgodą). Szczegóły i uzasadnienie wyboru metody: [`apartment-finder-uslugi-plan.md`](apartment-finder-uslugi-plan.md).
