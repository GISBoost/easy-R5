# Claude Code prompt — Easy-R5 **F2**: dane do analizy flagowej

> Wklej poniżej linii do Claude Code, w repo `easy-R5`, czysty tree. Kod po angielsku,
> rozmowa po polsku. **F1 musi być zrobione i zacommitowane.** Implementuj wyłącznie F2 —
> żadnych przebiegów R5 poza budową sieci. Nowego brancha nie twórz.

---

> ## ⚠ AKTUALIZACJA v2 (2026-09-05)
>
> **Data analizy zmienia się z 2026-08-24 na 2026-08-21 (piątek)** — musi być dniem, który
> nagrały oba operatory (ZDiT i ŁKA). Uzasadnienie i tabela wspólnych dni:
> [`../prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`](../prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md) §3.2.
> Bramka „9 893 kursy" nadal obowiązuje — feed ZDiT obsługuje 2026-08-21 tą samą liczbą kursów.
> Po tym kamieniu idzie **F2b** (feed ŁKA), dopiero potem F3.


## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` — **§3** (dane, ze zweryfikowanymi liczbami),
  **§4.3** (warstwa celów), **§9 F2** (kryteria akceptacji).
- `tools/accessibility_lodz/COLUMNS.md` — **przeczytaj przed nazwaniem czegokolwiek.**
  „opportunity count" i „population covered" to nie to samo i ten projekt już się na tym
  potknął.
- `tools/accessibility_lodz/STUDENTS_ANALYSIS.md` §1.3 — ograniczenie point-in-polygon
  (640/1479 heksagonów), które ten kamień ma naprawić.
- `tools/accessibility_cities/HOWTO_MANUAL.md` — konwencja budowy siatki.
- `easy_r5/algorithms/population_overlay.py`, `build_network.py` — algorytmy do użycia.

## Po co ten kamień istnieje

Analiza ma cztery przebiegi różniące się **wyłącznie** listą trybów. Wszystko inne — sieć,
origins, destinations, data — musi być identyczne i policzone **raz**, zanim ruszy F3.
Ten kamień produkuje ten „raz".

## Katalog

Wszystko nowe idzie do `tools/modal_complementarity_lodz/`, z własnym `README.md`
w konwencji pozostałych folderów `tools/`. Dane wejściowe **czytaj** z
`tools/accessibility_lodz/` i `tools/ses_income_lodz/` — **nie kopiuj** ich (poza GTFS-em,
patrz niżej) i **nie modyfikuj**.

## Co zbudować

### 1. Sieć

`BuildNetwork` (algorytm wtyczki, przez `processing.run("easyr5:buildnetwork", …)`):

- OSM: `tools/accessibility_lodz/lodz.osm.pbf`
- GTFS: **osobny katalog** `tools/modal_complementarity_lodz/gtfs_static/` zawierający
  **wyłącznie** `lodz_static_gtfs_2026-08-21.zip` (skopiowany). Powód: zrealizowane feedy
  P50/P85 mają te same `trip_id` i nie mogą trafić do jednego katalogu budowy — a leżą obok
  w `accessibility_lodz/`.
- wyjście: `tools/modal_complementarity_lodz/network_static/`

**Bramka:** `network.json` musi raportować **9 893** aktywne kursy na `2026-08-24`.
Inna liczba → zatrzymaj się i zgłoś, nie „jedź dalej".

### 2. Odpowiedz na pytanie z PRD §3.2

W `routes.txt` są linie `route_type=0` o nazwach `Z1, Z2, P1, P2, R8, O`. Sprawdź
`route_long_name` / `route_desc` i **napisz w `README.md` tego folderu, czym one są**
(np. tramwaje zastępcze). Nie usuwaj ich z danych, nie zgaduj.

### 3. Origins

Z `tools/accessibility_lodz/lodz_hex500.gpkg`, warstwa `hex500`: wyciągnij **czystą** warstwę
`hex_grid` (tylko `hex_id` + geometria poligonu, 1 479 obiektów) i `hex_centroids`
(`hex_id` + punkt). Zapisz do `tools/modal_complementarity_lodz/lodz_modal.gpkg`.
Nie ciągnij za sobą 74 kolumn z poprzedniego badania.

### 4. Populacja — area-weighted

`PopulationOverlay` z `tools/ses_income_lodz/lodz.gpkg`, warstwa `obwody_spisowe`,
pole `population` → pole `pop_total` na `hex_grid`.

- 18 obwodów ma `population = NULL` (supresja GUS). Traktuj je jako brak danych, **nie zero**;
  udokumentuj, ile powierzchni miasta to obejmuje.
- Kontrola: `Σ pop_total` w granicach **1%** sumy `population` obwodów leżących w granicy
  miasta. Wypisz obie liczby.
- Kontrola: liczba heksagonów z `pop_total > 0` musi być **wyraźnie większa niż 640**
  (tyle miał pilotaż metodą point-in-polygon). Jeżeli wyjdzie ~640, overlay nie zadziałał —
  zatrzymaj się.

### 5. Usługi — POI na heksagony

`tools/accessibility_lodz/lodz_services.csv`
(1 328 POI, kategorie `education / health /culture / groceries`) 
→ pola `srv_education, srv_health, srv_culture, srv_groceries, srv_total` 
na `hex_grid`, przez zliczenie punkt-w-poligonie.

Kontrola: `Σ srv_total = 1 328` — żaden POI zgubiony, żaden podwójnie. POI poza siatką
(jeśli są) wymień w logu.

### 6. Warstwa celów

`hex_destinations` = `hex_centroids` + pola `pop_total, srv_total, srv_education, srv_health,
srv_culture, srv_groceries`. To jest **jedna** warstwa celów dla wszystkich czterech
przebiegów F3.

Dodatkowo `poi_destinations` = dokładne punkty z `lodz_services.csv` z polami
`srv_total` (=1) i per kategoria — potrzebne w F3 tylko do przebiegu kontrolnego (PRD §9 F3,
korelacja Spearmana ≥ 0,95).

### 7. `README.md` folderu

W stylu pozostałych `tools/*/README.md`: co to jest, skąd dane, jak odtworzyć, co jest
gitignored, i wynik kontroli z punktów 4–5 jako konkretne liczby.

### 8. `.gitignore`

`network_static/`, `gtfs_static/`, `*.gpkg`, `out/`, `__pycache__/` — zgodnie z regułą repo
„wersjonujemy kod i dokumentację, nie dane". `README.md` i skrypty **są** wersjonowane.

## Czego NIE ruszać

- Niczego w `tools/accessibility_lodz/`, `tools/accessibility_cities/`, `tools/ses_income_lodz/`.
- `easy_r5/` — F1 skończone, tu nie ma zmian we wtyczce.
- Nie licz żadnej dostępności. To F3.

## Kryteria akceptacji

- [ ] `network.json`: 9 893 kursy na 2026-08-24.
- [ ] `Σ pop_total` w granicach 1% sumy obwodowej; obie liczby w `README.md`.
- [ ] Heksagonów z `pop_total > 0` istotnie więcej niż 640.
- [ ] `Σ srv_total = 1 328`.
- [ ] `lodz_modal.gpkg` zawiera `hex_grid`, `hex_centroids`, `hex_destinations`,
      `poi_destinations`.
- [ ] Pytanie o linie `Z1/Z2/P1/P2/R8/O` odpowiedziane w `README.md`.
- [ ] Skrypty odtwarzalne od zera jednym poleceniem (`py prepare_data.py`), `flake8` czysto.

## Co musi sprawdzić Michał

1. Otwórz `lodz_modal.gpkg` w QGIS — czy `pop_total` wygląda sensownie przestrzennie
   (gęsto w centrum, rzadko na peryferiach, bez dziur w środku miasta)?
2. Czy suma populacji ~670 tys. zgadza się z tym, co wiesz o Łodzi?
3. Czy warstwa `hex_destinations` ma 1 479 punktów i komplet pól?
