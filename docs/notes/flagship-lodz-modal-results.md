# Wyniki: komplementarność modalna Łodzi (tramwaj × autobus)

**Data:** 2026-09-05. **Status:** F1–F4 zrobione (F4 częściowo — patrz Ograniczenia).
Wszystkie liczby poniżej mają pokrycie w `tools/modal_complementarity_lodz/out/*.json`
i `.csv` — żadna nie jest „z pamięci".

## 1. Pytanie i metoda w pięciu zdaniach

Ile ze swojego zasięgu transportowego Łódź zawdzięcza tramwajowi, ile autobusowi, a ile temu,
że można się między nimi przesiąść? Metoda to zawężona replika
[Rayaprolu & Levinson (2024), *Transit modal complementarity*](https://doi.org/10.1007/s11116-024-10555-9):
cztery przebiegi dostępności kumulatywnej na jednej sieci — pieszo (`W`), tramwaj+pieszo (`T`),
autobus+pieszo (`B`), cała sieć z przesiadkami (`TB`) — a potem algebra na wynikach.
`tram_share = (A_TB − A_B) / A_TB` mówi, ile zasięgu znika bez tramwaju;
`transfer_premium = A_TB − max(A_T, A_B)` mówi, ile daje sama przesiadka.
Pełna specyfikacja: [`docs/prd/PR_easy-R5_flagship-lodz-modal.md`](../prd/PR_easy-R5_flagship-lodz-modal.md).

## 2. Dane i parametry

| Parametr | Wartość | Źródło |
|---|---|---|
| Data przebiegu | 2026-08-24 (poniedziałek) | `run_meta.json` |
| Aktywne kursy GTFS tego dnia | 9 893 | F2, `network.json` |
| Siatka | heksagony 500 m, 1 479 sztuk | F2 |
| Okno odjazdu | 07:00–09:00 (120 min) | `run_meta.json` |
| Percentyle | 10, 25, 50, 75, 90 | `run_meta.json` |
| Progi | 15, 30, 45, 60 min | `run_meta.json` |
| R5 | 7.6 | `acc_TB.csv.meta.json` |
| Wersja wtyczki Easy-R5 | 0.2.0 | `run_meta.json` |
| Czas czterech przebiegów | W 37,0 s / T 82,6 s / B 93,2 s / TB 104,4 s — **razem 317,2 s (≈5,3 min)** | `run_meta.json` |

## 3. Weryfikacja: czy filtr trybów w ogóle działa

Nikt wcześniej nie używał `TRANSIT_SUBMODES` na ścieżce runnera R5 — to trzeba było
udowodnić, nie założyć.

- **I1** (dodanie trybu nie zmniejsza zasięgu): **0 naruszeń** na **177 480** sprawdzonych
  wierszy (heksagon × cutoff × percentyl × kolumna opportunities).
- **I2** (pełna sieć ≥ najlepszy pojedynczy tryb): **0 naruszeń**.
- **I3** (gdyby R5 ignorował `transitModes`, `T` i `B` byłyby identyczne): **0,308**, próg
  to >0,05. Tramwaj i autobus dają realnie różne wyniki — filtr działa.

Źródło: `out/invariants.json`.

## 4. Wyniki — poziom

Przeciętny mieszkaniec Łodzi (ważenie populacją) ma w zasięgu 30 minut pełną siecią
**Ā_TB(30) = 82 747 osób**. **98,13%** ludności miasta mieszka w heksagonie z dostępem
do ≥1000 osób w 30 min (próg `K`, patrz Ograniczenia).

| Próg | Ā_W | Ā_T | Ā_B | Ā_TB | pokrycie ≥K |
|---|---|---|---|---|---|
| 15 min | 11 188 | 12 058 | 11 713 | 12 666 | 92,66% |
| 30 min | 37 280 | 64 787 | 60 028 | **82 747** | 98,13% |
| 45 min | 72 448 | 197 619 | 186 765 | 258 901 | 99,65% |
| 60 min | 117 123 | 377 701 | 370 769 | 463 590 | 99,87% |

Źródło: `out/city_summary.csv`.

## 5. Wyniki — zależność modalna

Przy 30 minutach, na poziomie miasta:

- **tram_share = 27,5%** — tyle z pełnego zasięgu (Ā_TB) znika, gdyby usunąć tramwaj
  (bezwzględnie: **22 719 osób** mniej, `Ā_TB − Ā_B` = 82 747 − 60 028).
- **bus_share = 21,7%** — tyle znika bez autobusu (bezwzględnie: **17 960 osób**,
  `Ā_TB − Ā_T` = 82 747 − 64 787).
- **walk_share = 45,1%** — tyle zasięgu istnieje już samą pieszo, bez transportu.

Tramwaj waży w Łodzi nieco więcej niż autobus na poziomie miasta (27,5% vs 21,7%), ale
różnica nie jest ogromna — obie sieci są ważne. Przestrzenny rozkład `tram_share` per
heksagon (korytarze wzdłuż linii tramwajowych) miał się pokazać na hero image (P1); mapa
nie została jeszcze wyprodukowana — patrz Ograniczenia i `tools/modal_complementarity_lodz/README.md`
sekcja F4.

## 6. Wyniki — komplementarność

**transfer_premium_rel(30) = 13,6%** miejskiego zasięgu istnieje **tylko** dzięki
przesiadce tramwaj↔autobus (bezwzględnie: **11 229 osób**, `Ā_TB − Ā_no_transfer` =
82 747 − 71 518, gdzie `no_transfer = max(Ā_T, Ā_B)`).

**subadd_city** — sub-addytywność na poziomie miasta, po odjęciu bazy pieszej:

| Próg | subadd_city |
|---|---|
| 15 min | 1,060 |
| 30 min | **0,905** |
| 45 min | 0,779 |
| 60 min | 0,674 |

Przy 30 min i dłużej `subadd < 1`: tramwaj i autobus **częściowo się dublują** — tak jak
w Sydney u Rayaprolu i Levinsona. Ciekawostka: przy 15 min wychodzi **>1** (1,060), czyli
przy bardzo krótkich progach tryby się raczej **uzupełniają**. To spójne z intuicją: na
krótkim dystansie mało jest miejsc, gdzie oba tryby w ogóle nakładają się na siebie (mało
wspólnych obszarów obsługi), więc przesiadka rzadziej "duplikuje" to, co i tak było
osiągalne — a kierunek efektu odwraca się dopiero, gdy przy dłuższym progu obie sieci
zaczynają pokrywać te same obszary miasta. U Rayaprolu i Levinsona korzyść z przesiadki
**rośnie** z progiem (odwrotny kierunek niż nasza malejąca `subadd`, choć to inna miara —
`subadd` maleje, czyli dubel rośnie, niekoniecznie sprzeczne z rosnącą premią bezwzględną,
patrz `transfer_premium` w `out/city_summary.csv`, które w liczbach bezwzględnych **rośnie**
z progiem: 215 → 11 229 → 40 902 → 55 620 osób dla 15/30/45/60 min — czyli oba kierunki są
prawdziwe naraz, bo to różne miary tego samego zjawiska).

Źródło: `out/city_summary.csv`.

## 7. Kontrola na usługach: czy wniosek trzyma się bez populacji

Osobny przebieg na dokładnych 1 328 punktach usług (nie zagregowanych do centroidów
heksagonów) potwierdza: korelacja Spearmana między `srv_total_30min` liczonym na
heksagonach a wersją punktową to **ρ = 0,9886** (n=1 479, próg 0,95). Agregacja POI do
centroidu heksagonu (przesunięcie ≤ ~250 m) nie zniekształca wyniku — metryka usługowa jest
wiarygodna bez zastrzeżeń. Źródło: `out/poi_control.json`.

## 8. Przekrój 20–29 lat

Wśród 594 heksagonów z jednocześnie wiarygodnym `tram_share` i danymi o populacji 20–29 lat,
średni `tram_share` ważony liczbą młodych (24,24%) jest nieco **wyższy** niż ważony całą
populacją (23,53%) — młodzi mieszkają odrobinę bardziej tramwajowo niż ogół, choć różnica
jest niewielka (0,7 pp). Źródło: `out/age_cross_section.json`.

## 9. Ograniczenia

- **To jest miara zależności, nie prognoza.** Wyłączenie tramwaju w modelu nie uruchamia
  komunikacji zastępczej, nie przenosi pasażerów i nie zmienia rozkładu autobusów (PRD §2).
  Odpowiada na „ile z dzisiejszego zasięgu jest dziś obsługiwane przez szyny", nie na „co
  się stanie, jak zamkniemy torowisko".
- **Próg wiarygodności K = 1000 osób** (na `A_TB(30, p50, pop_total)`) filtruje udziały
  (`tram_share`, `bus_share`, `transfer_premium_rel`, `subadd`, `mode_balance`) — **474 z
  1 479 heksagonów (32%)** nie mają tych pól (są `NULL`, nie 0). Absolutne pola (`acc_*`,
  `tram_gain`, `transfer_premium`) zostają.
- **Heksagon liczy sam siebie** — czas przejazdu z heksagona do niego samego wynosi 0, więc
  jego własna populacja zawsze wpada do jego `A`. Nie jest to naprawiane, tak samo jak u
  Rayaprolu i Levinsona.
- **POI zagregowane do centroidów heksagonów** (przesunięcie ≤ ~250 m) — kontrola na
  dokładnych punktach (§7) potwierdza ρ = 0,9886, powyżej progu 0,95.
- **18 obwodów spisowych bez populacji** (supresja GUS), pokrywających 4,32 km² — traktowane
  jako brak danych, nie zero (F2).
- **Jeden dzień, jedno okno, jeden szczyt.** Poniedziałek 2026-08-24, 07:00–09:00. Zero
  wniosków o weekendzie, wieczorze czy międzyszczycie.
- **Jakość OSM dla warstwy usług** — `lodz_services.csv` (1 328 POI) jest tym, czym jest:
  kontrolą kompletności OSM w Łodzi, nie rejestrem urzędowym.
- **Linie `Z1`, `Z2`, `P1`, `P2`, `R8`, `O`** (route_type=0, F2 §3.2): `Z1`/`Z2`/`O` to
  realne linie tramwajowe do realnych przystanków końcowych (nie „zastępcze", jak zakładała
  pierwotna hipoteza PRD); `R8` to samo, tylko 6 kursów/dzień; `P1`/`P2` to linie
  pracownicze (`trip_headsign = "PRZEWÓZ PRACOWNIKÓW"`) — żadna nie została usunięta z
  danych. Pełny opis: `tools/modal_complementarity_lodz/README.md`.
- **Hero image (P1) i mapa premii za przesiadkę (P2) nie zostały wyprodukowane.** Wykres
  słupkowy (P3, §4–6 powyżej) jest gotowy i zweryfikowany; same mapy blokuje nieznaleziony
  błąd renderowania warstw klasyfikowanych (`QgsRuleBasedRenderer`/`QgsGraduatedSymbolRenderer`)
  wewnątrz `QgsLayoutItemMap` w QGIS 3.40.5 — szczegóły i macierz testów w
  `tools/modal_complementarity_lodz/README.md`, sekcja F4. Liczby powyżej (§4–6) nie zależą
  od tych map i są w pełni policzone i zweryfikowane.

## 10. Co dalej

Odłożone kierunki (nie w zakresie tego kamienia): loteria odjazdu (rozrzut po percentylach,
kandydat B), warstwa „zły dzień" na zrealizowanym P85 (F6 — sparkowany razem z koleją ŁKA,
patrz `docs/notes/flagship-analysis-decision.md` v3), analiza sześciu miast. Pełna lista:
[`docs/notes/flagship-analysis-candidates.md`](flagship-analysis-candidates.md).
