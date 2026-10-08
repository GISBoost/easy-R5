# Łódzki Ośrodek Geodezji (ŁOG): zasoby cenowe i walidacja modelu cen

Data: 2026-10-08. Rozpoznanie na zlecenie Michała. Dotyczy warstwy cen (`price-v1`, `apartment-finder-price-m0.md`).

## Co publikuje ŁOG (Dział Monitoringu Rynku Nieruchomości)
Strona: https://log.lodz.pl/monitoring-rynku-nieruchomosci/ . **ŁOG prowadzi RCN dla Łodzi** (raport 2025: dane z Rejestru Cen Nieruchomości prowadzonego przez ŁOG,
uzupełnione analizą treści aktów). Czyli dziura 2019–2024 z krajowego WFS to problem eksportu, nie rejestru: ŁOG ma pełne dane i publikuje z nich agregaty od 2015.

| Zasób | Adres | Co zawiera | Aktualizacja |
|---|---|---|---|
| Raport „Rynek mieszkaniowy w Łodzi w 2025 r." (PDF, 29 str.) | https://log.lodz.pl/wp-content/uploads/2026/09/Rynek-mieszkaniowy-w-Lodzi-w-2025-roku.pdf | średnie, mediany, kwartyle zł/m² (RP/RW, lata 2022–2025), dzielnice, kwartały, miesiące, najdroższe obręby, struktura, powierzchnia | rocznie (+ kwartalne), poprzedni: 2024 |
| Poglądowa mapa cen mieszkań | https://mapa.lodz.pl/portal/apps/webappviewer/index.html?id=e49f8ec3518a48b38c2a7ec766336260 ; serwis REST `RynekMieszkaniowy` | poligony 200 m z klasą średniej ceny zł/m² osobno RP i RW, migawki 2014–III kw. 2026 | kwartalnie/rocznie |
| Mapa transakcji lokalami | https://mapa.lodz.pl/transakcje/ ; REST `transakcje` | 6 379 adresów budynków, per adres tabela: **data transakcji i powierzchnia lokalu (bez ceny)**, 55 023 transakcje 2015–2025 (4–5,6 tys. rocznie) | kwartalnie |
| Mapa koncepcyjna wartości gruntów | https://mapa.lodz.pl/mrn/grunty/ ; REST `mapa_wartosci` | raster IDW wartości jednostkowej gruntu zł/m² (≤70 … >2001), migawki 2015–czerwiec 2026; „charakter poglądowy" | rocznie |
| Tabela cen gruntów niezabudowanych wg przeznaczenia | strona monitoringu | średnie zł/m² (I kw. 2026: jednorodzinna 299, wielorodzinna 1 884, usługowa 408, przemysłowa 260, średnio 384) | kwartalnie (stan 30.09.2026) |
| Raporty PDF: grunty (np. `.../2026/07/Grunty_2025.pdf`), najem mieszkań (09.2025), najem użytkowych (01.2026), pozycja łódzkiego rynku (2022), biura | strona monitoringu | agregaty, bez rekordów | różnie |
| Kontakt | sekretariat@log.lodz.pl, 42 272-68-86 | | |

**Warunki użycia:** raport 2025 (str. 5): „treść raportu i/lub jego fragmenty mogą być powielane i rozpowszechniane pod warunkiem wskazania jego źródła oraz podmiotu, któremu przysługują
prawa autorskie". Dla usług ArcGIS REST i map: brak zapisanej licencji (mapy „poglądowe", wartość nieruchomości wyceniają tylko rzeczoznawcy). Dla danych z REST pytać ŁOG przed publikacją.

## Serwer ArcGIS REST (Intersit, `https://mapa.lodz.pl/3/rest/services`) — publiczny, bez klucza
Folder główny ma 48 usług, w tym (EPSG:102175 = ETRS89 / zmodyfikowane TM, ale `outSR=2180` działa; `maxRecordCount` 1000, **bez paginacji**, zapytania z `resultRecordCount` i statystyk zwracają błąd; trzeba dzielić `where` po OBJECTID):
- `RynekMieszkaniowy` (MapServer): warstwy 0–61 = grupy „Stan na III kwartał 2026 / 2025 / 2024 / 2023, II kw. 2022 … 2015, III kw. 2014" × (rynek pierwotny: warstwa „Średnia cena 1 m² [zł]", rynek wtórny: j.w.).
  Pole `SR_CENA` (tekst z klasą, np. „6 501 - 7 500", „≥ 7 501"), poligony kwadratów 200 m (RP: 87, RW: 937 w III kw. 2026). Dodatkowo `Adresy` (62, 65 038 punktów), `Działki` (63, 157 515), `Budynki` (64).
- `transakcje/0`: punkty adresowe + tabela HTML transakcji (data, powierzchnia). `transakcje_log/0` („mapa wew."): 5 328 punktów `ROK` 2014+, `WYCENA_TRA`, `WARTOSC_CE` (wartość gruntu zł/m², mediana w próbce 144): to dane o **gruntach**, nie mieszkaniach; nazwa wskazuje mapę wewnętrzną, użycie tylko po zgodzie.
- `mapa_wartosci`: warstwy 5 `Obręby` (215, pole `NR_BREBU`), 6 `Dzielnice` (5, `DZIELNICA`), 8–21 raster wartości gruntu (identify zwraca `Pixel Value` w zł/m²).
- Inne w folderze: `dzialki_na_sprzedaz`, `zielen_*`, `Komunikacja_miejska` itd. (poza tematem cen).

## Walidacja modelu cen względem ŁOG (średnie zł/m², RCN wolny rynek)
Nasze 7 660 transakcji VII 2025 – IX 2026 (WFS GUGiK) vs raport ŁOG (rok 2025; zakres: wolnorynkowe, bez najemców, bonifikat, zamian, darowizn; **cena RP netto bez 8% VAT**):

| | ŁOG 2025 | nasze | uwagi |
|---|---|---|---|
| średnia wszystkich | 8 003 (Q3 8 045, Q4 7 966) | 2025 Q3 9 131, Q4 8 942 | nasze o ok. 12–13% wyższe |
| rynek pierwotny, średnia | 8 507 (mediana 8 351), netto | 2025 H2 9 656 | +13,5%; po VAT 8% ŁOG = 9 188, nasze +5% |
| rynek wtórny, średnia | 7 775 (mediana 7 539) | 2025 H2 8 281, Q4 8 249 | +6% |
| Śródmieście / Widzew / Polesie / Górna / Bałuty | 8 695 / 8 256 / 8 245 / 7 734 / 7 607 | 9 738 / 8 880 / 9 425 / 7 955 / 8 135 (2025 H2) | stosunek 1,03–1,14; kolejność ŁOG: Śr > Wid ≈ Pol > Gór > Bał, nasza: Śr > Pol > Wid > Bał > Gór |
| obręb B-48, RP | 10 740 | 11 348 (n=9, całe okno) | +6% |

Wnioski:
1. **Poziom** jest zgodny co do rzędu wielkości, ale nasz jest systematycznie wyższy: RP o ok. 5% po uwzględnieniu VAT (jeśli cena brutto w RCN zawiera VAT, trzeba to potwierdzić w opisie pola `LOK_CENA_BRUTTO`), RW o ok. 6%.
   Możliwe przyczyny poza VAT: krajowy WFS zawiera tylko rekordy z pełną lokalizacją (nowsze, zlokalizowane akty, częściej nowe budynki), nasze okno jest późniejsze (rynek rośnie ok. 0,66% miesięcznie wg ŁOG), inny zakres wykluczeń. Nie rozstrzygnięte.
2. **Różnice między dzielnicami** są podobne (stosunek nasze/ŁOG 1,03–1,14); największa rozbieżność: Polesie (+14%) i Śródmieście (+12%); Górna jest u nas droższa od Bałut, u nich odwrotnie.
3. **Mapa klas ŁOG (200 m) jest słabym wzorcem**: klasy po 1 000 zł kończą się na „≥ 7 501" (55% komórek RW i 80% RP w najwyższej klasie), a średnia miasta to 8 000. Nasza cena heksa mieści się w klasie komórki ±500 zł w 75% (RW) i 81% (RP), ale to w dużej mierze efekt otwartej górnej klasy; korelacja rang 0,19 (RW) i 0,15 (RP).
4. **Wartość gruntu (raster) nie jest dobrym przybliżeniem ceny mieszkań**: 399 heksów z naszą ceną, korelacja rang −0,17. Najtańsza grunt = nowe osiedla na peryferiach, z drogimi mieszkaniami. Nie używać jako zmiennej pomocniczej.

## Co z tego wynika dla nas
- **Największa wartość: dane o transakcjach 2019–2024 istnieją u ŁOG** (55 tys. transakcji, 4–5,6 tys. rocznie, z adresem, datą i powierzchnią), ale bez ceny. Cena z RCN dla tego okresu jest u ŁOG; warto napisać (sekretariat@log.lodz.pl) z prośbą o eksport lub zgodę na użycie danych cen per adres/obręb. Z tym mielibyśmy trend 2022–2026 i trzykrotnie więcej danych na heks.
- Z raportu można przepisać jako parametry kontrolne: średnia i mediana RP/RW 2022–2025, średnie dzielnic i kwartałów 2025, miesięczne średnie (raport ma wykres z miesięczną serią, tabele dla 2022–2025 są na str. 11–18).
- Do rozstrzygnięcia z ŁOG/GUGiK: czy `LOK_CENA_BRUTTO` na RP zawiera VAT; czy do heksów dodać korektę (−8% na RP)? Obecnie wartości nie koryguję.
- Nie robiłem: wizualnej kontroli w QGIS, pobrania całych historycznych migawek klas (RynekMieszkaniowy 2014–2025), analizy pozostałych raportów PDF (najem, grunty).

## Dane ŁOG od 2022 w projekcie (2026-10-08, za zgodą ŁOG)
Pobrane i przeliczone skryptami `scripts/price_log_fetch.py` i `scripts/price_log_hex.py` (config `config/price.yaml`, sekcje `log`, `log_hex`), wyjście w `data/price/log/` (poza gitem):
`log_cells.gpkg` (komórki 200 m z klasą ceny, 5 migawek × RP/RW: II kw. 2022, III kw. 2023, 2024, 2025, 2026), `log_transactions.gpkg` (20 078 transakcji 2022–2025 z datą i powierzchnią, bez ceny), `log_hex.csv` (cena per heks, migawka i rynek).
Oznaczenie źródła przy publikacji: „Łódzki Ośrodek Geodezji".

**Zakres tego, co istnieje:** serwer ŁOG nie wystawia cen pojedynczych transakcji, tylko klasę ceny komórki (`SR_CENA`, klasy po 1 000 zł). Aplikacja ŁOG (web map `0fe5a28b…`) nie ma ukrytych pól cenowych.
Ceny rekordowe od 2022 zostają więc u ŁOG: do uzyskania tylko od nich (eksport RCN).

**Przeliczenie (ta sama idea co `price_hex.py`):** zasięg adaptywny 250–1000 m, min. 5 komórek, mediana ważona odległością, tylko heksy zamieszkałe; wartość komórki = środek klasy, klasa otwarta „≥ X" = X + 500 i flaga „cenzurowana".
| migawka | heksy zamieszkałe z wartością | cenzurowane (>50% wagi w klasie otwartej) |
|---|---|---|
| 2022-Q2 | 58% | 19% |
| 2023-Q3 | 57% | 11% |
| 2024-Q3 | 61% | 21% |
| 2025-Q3 | 60% | 66% |
| 2026-Q3 | 61% | 64% |
Próg klasy otwartej zmienia się (2022: „≥ 6 501", od 2023 „≥ 7 501"), więc od 2025 mapa ŁOG jest w większości „obcięta od góry" (58% komórek w najwyższej klasie) i prawie nie rozróżnia dróższych okolic.

**Zgodność z naszą ceną (heksy z obiema wartościami, ok. 1 400):** korelacja rang 0,24–0,33; bez cenzurowanych ok. 0 (−0,11…0,21). Stosunek naszej mediany do wartości ŁOG maleje 1,41 (2022) → 1,25 (2023) → 1,21 (2024) → 1,06 (2025) → 1,07 (2026),
co zgadza się ze wzrostem cen 2022→2025 z raportu ŁOG (6 520 → 8 003 zł/m², +23%; nasze okno to ceny z 2025/26). Wniosek: **mapa klas ŁOG potwierdza poziom i dryf cen w czasie, ale nie nadaje się do podziału na heksy** (za gruba, obcięta od góry); nie włączona do aplikacji.

**Kontrola kompletności krajowego WFS względem ŁOG (liczba transakcji na miesiąc, ŁOG ma dane do 12.2025):**
| 2025 | VII | VIII | IX | X | XI | XII |
|---|---|---|---|---|---|---|
| ŁOG | 535 | 391 | 394 | 519 | 350 | 425 |
| nasze (WFS po filtrze) | 65 | 33 | 131 | 508 | 484 | 778 |
WFS miał w lipcu–wrześniu 2025 tylko 8–33% transakcji ŁOG, od października pełny wolumen (a w XI–XII więcej: późniejsze dopisywanie do rejestru i inne kryteria). Ten początek okna naszej warstwy jest więc niepełny (próbka cienka i zniekształcona w stronę dosłanych rekordów).
ŁOG 2022–2025: 4 422 / 4 911 / 5 555 / 5 190 transakcji rocznie.
