# PRD — analiza flagowa Easy-R5: komplementarność modalna w Łodzi

**Status:** Draft
**Data:** 2026-09-05
**Autor metody i właściciel projektu:** Michał Kaczorowski
**Kontekst:** `CLAUDE.md`, `CONTEXT.md`, `docs/notes/flagship-analysis-candidates.md`,
`docs/notes/r5-vs-otp.md`, `docs/notes/r5-engine-primer.md`.
R5 v7.6, Java 21, QGIS 3.22 LTR+, Easy-R5 0.1.0.

> Ten PRD opisuje **jedną analizę** i **jedną małą zmianę we wtyczce**, która ją umożliwia.
> Nie jest to PRD wersji 0.2 — pozostałe pozycje z `roadmap-candidates.md` są nadal
> nierozstrzygnięte i ta analiza nie przesądza żadnej z nich poza T-nowe §5.

## 0. Stan realizacji

| Kamień | Status | Data | Uwagi |
|---|---|---|---|
| F1 — `TRANSIT_SUBMODES` | ✅ zrobione | 2026-09-05 | zweryfikowane end-to-end w QGIS na realnym R5 7.6 |
| F2 — dane | ✅ zrobione | 2026-09-05 | `tools/modal_complementarity_lodz/`; 9893 kursy, populacja w 0,088% tolerancji |
| F3 — przebiegi i metryki | ✅ zrobione | 2026-09-05 | I1/I2/I3 przechodzą (I3=0,308), ρ_POI=0,9886, subadd_city(30)=0,9047 |
| F4 — kartografia | 🟡 częściowo | 2026-09-05 | P3 (wykres) gotowy; P1/P2 (mapy) zablokowane błędem renderowania w QGIS 3.40.5 — patrz `tools/modal_complementarity_lodz/README.md` §F4 |
| F5 — teksty | ✅ zrobione | 2026-09-05 | `docs/notes/flagship-lodz-modal-results.md`, blok w `README.md`, `out/text_pl.md` |
| F6 — zły dzień (P85) | ⏳ sparkowany | — | wymaga nowej, dwutrybowej wersji promptu; patrz `docs/notes/flagship-analysis-decision.md` v3 |

Kolej (ŁKA) sparkowana w całej analizie — patrz `docs/notes/flagship-analysis-decision.md` v3.

---

## 1. Pytanie badawcze

> **Ile ze swojego zasięgu Łódź zawdzięcza tramwajowi, ile autobusowi, a ile temu, że można
> się między nimi przesiąść?**

Trzy pytania szczegółowe:

1. **Poziom** — ilu mieszkańców Łodzi jest w zasięgu 30 minut transportem publicznym z
   przeciętnego zamieszkanego heksagona, i jak ta liczba wygląda przestrzennie?
2. **Zależność modalna** — jaka część tego zasięgu znika, gdy z sieci zniknie tramwaj, a jaka,
   gdy zniknie autobus?
3. **Komplementarność** — ile dostępności **nie daje żadny tryb osobno**, tylko dopiero
   przesiadka między nimi? Czy tramwaj i autobus w Łodzi się **dublują** (sub-addytywność), czy
   **uzupełniają**?

**Po co to jest.** Trzy odbiorcy naraz:

- **README Easy-R5** — jeden obraz na górze pliku, który sprzedaje wtyczkę.
- **Planista** — Łódź remontuje całą sieć tramwajową do 2029 (ze 124 km torowisk zostało 20 km;
  w 2026 startuje pięć placów budowy). Mapa „ile zasięgu zniknie razem z tym korytarzem" jest
  operacyjna, nie akademicka.
- **Wtyczka** — analiza jest dogfoodingiem: zostawia po sobie parametr wyboru podtrybów
  (§5), który jest najtańszą możliwą zapowiedzią `RunScenarioAnalysis` (T2-E).

## 2. Podstawa metodyczna

Metoda jest **zawężoną repliką** opublikowanej:

> Rayaprolu, H. & Levinson, D. (2024). *Transit modal complementarity: measuring the access
> provided by transfers.* Transportation 53(4), 2057–2076.
> <https://doi.org/10.1007/s11116-024-10555-9> (open access, CC BY 4.0)

Autorzy porównują **11 przypadków modalnych** dla Sydney (pociąg / tramwaj / autobus, osobno,
w parach z przesiadkami międzymodalnymi i w parach bez nich), metryką jest
**person-weighted cumulative access to population**, a wynikami: sub-addytywność trybów,
rosnąca korzyść z przesiadki przy dłuższych progach, i zmiana roli „spoiwa" sieci z tramwaju
na autobus po latach 60.

**Co bierzemy:** definicję dostępności kumulatywnej, konstrukcję przypadków „A i B" vs
„A lub B", ważenie populacją, i pojęcie sub-addytywności.
**Czego nie bierzemy:** 160 lat historii, kolei (feed ZDiT jej nie ma), i 11 przypadków —
Łódź ma dwa tryby, więc sensownych przypadków jest **cztery** (§4.1).

Zastrzeżenie do interpretacji, obowiązkowe w każdym podpisie i w każdym tekście:

> Wyłączenie tramwaju w modelu jest **miarą zależności**, nie prognozą polityki transportowej.
> Model nie uruchamia komunikacji zastępczej, nie przenosi pasażerów i nie zmienia rozkładu
> autobusów. Odpowiada na pytanie „ile z dzisiejszego zasięgu jest dziś obsługiwane przez
> szyny", a nie „co się stanie, jak zamkniemy torowisko".

## 3. Dane wejściowe

Wszystko jest już w repo. **Nic nie trzeba pobierać.**

| Co | Ścieżka | Fakty zweryfikowane 2026-09-05 |
|---|---|---|
| Sieć drogowa | `tools/accessibility_lodz/lodz.osm.pbf` | 31,2 MB, wycinek Łodzi |
| Rozkład (GTFS statyczny) | `tools/accessibility_lodz/lodz_static_gtfs_2026-08-21.zip` | 1 agencja (ZDiT), 138 linii — **25 `route_type=0` (tram)**, **113 `route_type=3` (bus)**; 73 868 kursów (22 206 tram / 51 662 bus); 2 382 przystanki; `stop_times` 1 939 985 wierszy; kalendarz wyłącznie przez `calendar_dates.txt`, ważny 2026-08-20 → 2026-12-31 |
| Siatka 500 m | `tools/accessibility_lodz/lodz_hex500.gpkg`, warstwa `hex500` | 1 479 heksagonów, pole `hex_id` |
| Centroidy | `tools/accessibility_lodz/lodz_hex_origins.csv` | `id,lon,lat`, 1 479 wierszy, WGS84 |
| Granica miasta | `tools/accessibility_lodz/lodz_boundary.geojson`, `lodz_hex_boundary.geojson` | — |
| Populacja | `tools/ses_income_lodz/lodz.gpkg`, warstwa `obwody_spisowe` | 3 854 obwody, pole `population`, **suma 669 995**, 18 obwodów z `NULL` (supresja GUS) |
| Usługi (POI OSM) | `tools/accessibility_lodz/lodz_services.csv` | 1 328 POI, kolumny `category,osm_type,osm_id,name,lon,lat`; kategorie `education / health / culture / groceries` |
| *(opcjonalnie, F6)* | `lodz_realized_2026-08-21_p85.zip` | ten sam kalendarz i te same `trip_id` co statyczny — **osobny katalog budowy sieci** |

### 3.1 Data przebiegu — **2026-08-24 (poniedziałek)**

Zweryfikowane bezpośrednio w `calendar_dates.txt`: 9 893 kursy aktywne w tej dacie (dzień
powszedni), wobec 7 704 w sobotę i 7 026 w niedzielę. Ta sama data, której użyto w
`tools/accessibility_cities/` po audycie z 2026-08-23 — dzięki temu wyniki są porównywalne z
poprzednimi badaniami. **`BuildNetwork` ma to potwierdzić w `network.json`** (per-date
active-trip count = 9 893); jeżeli pokaże inną liczbę, przerywamy i szukamy przyczyny, nie
„jedziemy dalej".

### 3.2 Znak zapytania do sprawdzenia przed interpretacją

W liniach `route_type=0` są `Z1`, `Z2`, `P1`, `P2`, `R8`, `O`. **Agent ma sprawdzić w
`routes.txt` (`route_long_name`, `route_desc`) i opisać w wynikach, czym one są.** Jeżeli
`Z1`/`Z2` to *tramwaje zastępcze*, to jest fakt do wymienienia w tekście, nie do
usunięcia z danych. Nie zgadywać.

## 4. Metoda

### 4.1 Przypadki modalne

Cztery przebiegi na **jednej** sieci, różniące się **wyłącznie** listą podtrybów transitu:

| symbol | `MODE` | podtryby transitu | co to jest |
|---|---|---|---|
| `W` | WALK | — | pieszo, bez transportu. **Linia bazowa** |
| `T` | TRANSIT + WALK | `TRAM` | tramwaj + dojście/odejście pieszo |
| `B` | TRANSIT + WALK | `BUS` | autobus + dojście/odejście pieszo |
| `TB` | TRANSIT + WALK | `TRAM, BUS` | pełna sieć, przesiadki międzymodalne dozwolone |

Piąty przypadek — **„tramwaj *albo* autobus, bez przesiadki między trybami"** — **nie wymaga
przebiegu**: to `max(A_T, A_B)` liczone per heksagon. Tak samo definiują go Rayaprolu &
Levinson (przypadki 8–11).

Bazowa linia `W` jest konieczna, bo każdy przebieg transitowy zawiera też trasy czysto
piesze. Bez odjęcia `A_W` metryka sub-addytywności podwójnie liczy to, co i tak jest w
zasięgu spaceru.

### 4.2 Parametry przebiegu (identyczne we wszystkich czterech)

| parametr | wartość | uzasadnienie |
|---|---|---|
| `NETWORK` | `network_static/network.dat` | jeden build, wspólny dla wszystkich przypadków |
| `ORIGINS` | centroidy `hex500` (1 479) | siatka z pilotażu, `hex_id` jako id |
| `DESTINATIONS` | te same centroidy (1 479), z polami `opportunities` | patrz §4.3 |
| `DATE` | `2026-08-24` | §3.1 |
| `DEPARTURE_TIME` | `07:00` | szczyt poranny, zgodnie z pilotażem i 6 miastami |
| `TIME_WINDOW` | `120` | okno 07:00–09:00 |
| `PERCENTILES` | `10,25,50,75,90` | maksimum R5 to 5; **kosztują zero dodatkowego czasu**, a dają darmową warstwę „loterii odjazdu" (kandydat B) na później |
| `CUTOFFS` | `15,30,45,60` | jak w pilotażu; **headline = 30** |
| `DECAY` | `STEP` | dostępność kumulatywna, jak w literaturze i w pilotażu |
| `MAX_TRIP_DURATION` | `60` | = największy cutoff |
| `MAX_WALK_TIME` | puste (→ 60) | **nigdy nie zostawiać bez limitu** — 10,2× przyspieszenia przy 0,0000% różnicy wyniku (lekcja GZM) |
| `MAX_RIDES` | `3` | 2 przesiadki; **kluczowe dla przypadku `TB`** — przy `MAX_RIDES=1` przesiadka międzymodalna jest niemożliwa i cała analiza jest bez sensu |
| `WALK_SPEED` | `3.6` | domyślna wtyczki |
| `MONTE_CARLO_DRAWS` | `5` | domyślna |
| `ALLOW_NO_SERVICE` | `False` | twarda bramka daty ma zadziałać |

**Headline:** `T = 30 min`, `p = 50`, opportunity = `pop_total`.

### 4.3 Cele i „opportunities"

Warstwa celów to **te same centroidy heksagonów**, z polami liczbowymi:

| pole | co to | źródło |
|---|---|---|
| `pop_total` | liczba mieszkańców w heksagonie | `PopulationOverlay` (area-weighted) z `obwody_spisowe.population` |
| `srv_total` | liczba POI usługowych w heksagonie | zliczenie `lodz_services.csv` per heksagon |
| `srv_education`, `srv_health`, `srv_culture`, `srv_groceries` | jw. per kategoria | jw. |

**Dlaczego jedna warstwa celów zamiast dwóch.** `RunAccessibility` przyjmuje wiele
`OPPORTUNITY_FIELDS` naraz, więc jeden przebieg daje komplet metryk — cztery przebiegi
zamiast ośmiu, i obie metryki liczone na **identycznej** geometrii celów, więc porównywalne
co do heksagona.

**Cena:** POI zostaje przesunięte do centroidu swojego heksagona (≤ ~250 m). Dlatego §9
przewiduje **przebieg kontrolny** na dokładnych punktach POI (1 328 celów, tylko przypadek
`TB`, cutoff 30) i wymaga, żeby korelacja Spearmana `srv_total_30min` między wersją
heksagonalną a punktową wyniosła **ρ ≥ 0,95**. Poniżej tego progu metryka usługowa idzie do
tekstu z zastrzeżeniem albo wypada.

**Populacja — poprawka względem pilotażu.** Pilotaż przypisywał populację metodą
*point-in-polygon* (centroid obwodu → heksagon) i dopasował tylko **640/1479** heksagonów
([`STUDENTS_ANALYSIS.md`](../../tools/accessibility_lodz/STUDENTS_ANALYSIS.md) §1.3). Tutaj
używamy `PopulationOverlay`, czyli **nakładania ważonego powierzchnią** — to naprawia znane
ograniczenie i jest samo w sobie argumentem za wtyczką. Kryterium akceptacji: suma
`pop_total` po heksagonach mieści się w **1%** sumy `population` po obwodach leżących w
granicy miasta.

**Heksagon liczy sam siebie.** Czas przejazdu z heksagona do niego samego wynosi 0, więc jego
własna populacja wpada do `A`. Tak samo robią Rayaprolu & Levinson. Do udokumentowania, nie
do „naprawiania".

### 4.4 Metryki

Dla heksagona *i*, progu *T*, percentyla *p* i wybranej kolumny opportunities *o*, gdzie
`A^m` to wynik `RunAccessibility` dla przypadku modalnego *m*:

**Poziom**

```
level_i          = A^TB_i
walk_share_i     = A^W_i / A^TB_i          # ile masz bez transportu w ogóle
```

**Zależność modalna** — ile znika, gdy tryb zniknie:

```
tram_gain_i      = A^TB_i - A^B_i          # bezwzględnie: cele wymagające tramwaju
bus_gain_i       = A^TB_i - A^T_i
tram_share_i     = tram_gain_i / A^TB_i    # 0..1   ← METRYKA HERO IMAGE
bus_share_i      = bus_gain_i  / A^TB_i
mode_balance_i   = (A^T_i - A^B_i) / A^TB_i   # -1..+1, dodatnie = tramwajowy
```

**Komplementarność** — ile daje dopiero przesiadka międzymodalna:

```
no_transfer_i        = max(A^T_i, A^B_i)              # przypadek "T albo B", bez przesiadki
transfer_premium_i   = A^TB_i - no_transfer_i         # bezwzględnie
transfer_premium_rel = transfer_premium_i / A^TB_i    # 0..1
```

**Sub-addytywność** — na składowych *po odjęciu bazy pieszej*:

```
Ã^m_i        = max(0, A^m_i - A^W_i)
subadd_i     = Ã^TB_i / (Ã^T_i + Ã^B_i)     # <1 = tryby się dublują, >1 = uzupełniają
```

**Agregaty miejskie** (to są liczby do nagłówka i do posta):

```
Ā^m(T)  = Σ_i pop_i · A^m_i(T) / Σ_i pop_i        # person-weighted average access
cov^m(T) = Σ_{i: A^m_i ≥ K} pop_i / Σ_i pop_i      # odsetek ludności powyżej progu K
```

`Ā` liczymy dla wszystkich czterech przypadków i dla `no_transfer`, przy każdym cutoffie —
to daje wykres słupkowy z Fig. 3 i jedno zdanie o sub-addytywności na poziomie miasta.

### 4.5 Progi, wartości NULL i pułapka małego mianownika

To jest miejsce, w którym pilotaż się potknął (`total_pct_impact_30min` = −100% w 43 z 285
heksagonów, prawie wszystkie z mianownikiem 1–2). Reguły twarde:

1. **`A^TB_i = 0` → wszystkie udziały są `NULL`**, nie 0. W GPKG jako `NULL`, w CSV jako pusty
   string, na mapie jako osobna klasa „brak dostępu transportem".
2. **Próg wiarygodności `K`.** Udziały (`tram_share`, `bus_share`, `mode_balance`,
   `transfer_premium_rel`, `subadd`) publikujemy **tylko** dla heksagonów z
   `A^TB_i(30, p50, pop_total) ≥ K`. Domyślnie **K = 1 000 osób**; wartość faktycznie użyta i
   liczba odfiltrowanych heksagonów **muszą** trafić do metadanych wyjścia i do podpisu mapy.
3. **Zawsze obok siebie wartość bezwzględna i względna.** Żadna tabela ani mapa nie pokazuje
   samego procentu.
4. **Heksagony bez populacji** (`pop_total = 0`) nie wchodzą do agregatów ważonych i są na
   mapie przezroczyste — **nie** wpadają do najniższej klasy.

### 4.6 Niezmienniki — one są dowodem, że filtr trybów działa

R5 nie ma stabilnego API i nikt tu wcześniej nie używał `transitModes` na ścieżce runnera.
Zamiast ufać, sprawdzamy trzy rzeczy, które **muszą** zachodzić dla **każdego** heksagona,
progu i percentyla. Naruszenie któregokolwiek = przerwanie analizy, nie przypis.

```
I1   A^W_i ≤ A^T_i   ∧   A^W_i ≤ A^B_i   ∧   A^W_i ≤ A^TB_i
     (dodanie środka transportu nie może zmniejszyć zasięgu)

I2   A^TB_i ≥ max(A^T_i, A^B_i)
     (pełna sieć nie może być gorsza niż jej podzbiór)

I3   mean_i |A^T_i - A^B_i| / mean_i A^TB_i  >  0.05
     (gdyby R5 ignorował transitModes, wszystkie trzy przebiegi byłyby identyczne
      co do wiersza — I3 jest jedynym testem, który to wykrywa)
```

`I3` jest testem **negatywnym z premedytacją**: jeżeli okaże się, że `A^T == A^B == A^TB`
identycznie, to znaczy, że filtr jest ignorowany, i cała analiza — nie tylko liczby — jest
nieważna. Wtedy fallbackiem jest filtrowanie GTFS po `route_type` i trzy osobne sieci
(odrzucone jako plan A, patrz `docs/notes/flagship-analysis-candidates.md` §3), a we wtyczce
parametr z §5 dostaje ostrzeżenie w dokumentacji.

## 5. Zmiana we wtyczce — `TRANSIT_SUBMODES`

Jedyna zmiana w `easy_r5/`. Mała, bo `core/job_spec.py` **już** przyjmuje dowolną listę
`transit_modes` (`build_matrix_job`), a runner ją przekazuje. Brakuje wyłącznie kontrolki.

**Dziś** (`easy_r5/algorithms/_matrix_base.py`):

```python
MODE_OPTIONS = ["TRANSIT + WALK", "WALK", "BICYCLE", "CAR"]
_TRANSIT_MODES = ["TRAM", "SUBWAY", "RAIL", "BUS", "FERRY", "CABLE_CAR", "GONDOLA", "FUNICULAR"]
MODE_MAP = {0: ("WALK", _TRANSIT_MODES), 1: ("WALK", []), ...}
```

**Docelowo:**

| element | specyfikacja |
|---|---|
| nazwa | `TRANSIT_SUBMODES` |
| typ | `QgsProcessingParameterEnum(options=_TRANSIT_MODES, allowMultiple=True, optional=True, defaultValue=[])` |
| etykieta | `Transit sub-modes (blank = all)` |
| miejsce | zaraz po `MODE`, **nie** we `FlagAdvanced` — analiza flagowa ma być odtwarzalna z okna dialogowego bez rozwijania „zaawansowanych" |
| pusty wybór | = wszystkie tryby (zachowanie identyczne z dzisiejszym; zero regresji) |
| `MODE != 0` | wybór ignorowany, a w logu leci jedna linia ostrzeżenia; `transit_modes` zostaje `[]` |
| metadane wyjścia | nowe pole `transit_submodes` = `"ALL"` albo `"TRAM,BUS"` — PRD v0.1 §5.2 wymaga, żeby metoda była zapisana w wyniku, a to jest parametr, który **zmienia wynik i nie widać go w nazwie warstwy** |
| `mode_label` | rozszerzony do `"TRANSIT + WALK (TRAM)"`, żeby domyślne nazwy warstw i plików CSV różniły się między przebiegami |
| i18n | nowe stringi w `self.tr()` / `_tr()`; PL zostaje nieprzetłumaczony do czasu przeglądu z issue #1 |
| testy | `job_spec` przepuszcza podzbiór; pusty wybór → 8 trybów; `MODE=WALK` + wybór → `transit_modes == []`; kolejność trybów znormalizowana (żeby cache i metadane były deterministyczne) |
| README | jeden wiersz w tabeli algorytmów + zdanie w opisie `RunTravelTimeMatrix` / `RunAccessibility` |

**Czego ta zmiana NIE robi:** nie dotyka runnera Javy, nie zmienia `job_spec` poza testami,
nie zmienia klucza cache'u sieci (podtryby to parametr *zapytania*, nie *budowy*), nie dodaje
zależności.

## 6. Produkty

| id | produkt | plik |
|---|---|---|
| P1 | **Hero image** — „Ile Łodzi jedzie na szynach?" (mapa `tram_share`) | `docs/img/flagship-lodz-tram-share.png` (1200×720) + wersja PL i EN |
| P2 | Mapa premii za przesiadkę (`transfer_premium_rel`) | `docs/img/flagship-lodz-transfer-premium.png` |
| P3 | Wykres: `Ā^m` per przypadek modalny × cutoff + liczba sub-addytywności | `docs/img/flagship-lodz-modal-bars.png` |
| P4 | Warstwy i tabele | `tools/modal_complementarity_lodz/lodz_modal.gpkg` (`hex_modal`), `out/*.csv` |
| P5 | Opis wyników + zastrzeżenia | `docs/notes/flagship-lodz-modal-results.md` |
| P6 | Blok do README (EN) | wstawka na górze `README.md` |
| P7 | Wersja PL do bloga + post na LinkedIn | `tools/modal_complementarity_lodz/out/text_pl.md` |

P4 zawiera dodatkowo przekrój **20–29 lat** (`pop_20_29` z `lodz_hex_students.csv`) —
jedno zdanie „czy młodzi mieszkają bardziej tramwajowo niż ogół", jako przypis, nie jako
osobna mapa.

## 7. Kartografia hero image (P1)

Gramatyka zapożyczona z r5py, treść własna.

**Płótno.** 1200×720 px @ 2× (czyli render 2400×1440, eksport 1200×720), tło `#FAF8F4`.

**Lewa kolumna** — 0–34% szerokości, marginesy 32 px:

1. **Tytuł**, 3 wiersze, bold, ~30 px: *„Ile Łodzi jedzie na szynach?"* / EN:
   *„How much of Łódź rides on rails?"*
2. **Akapit metody**, ~13 px, ~7 wierszy: co pokazuje mapa — udział celów osiągalnych w 30
   minut, które znikają, gdy z sieci usunąć tramwaj; siatka 500 m; 07:00–09:00, mediana;
   populacja jako cel.
3. **Legenda wpleciona w zdanie** (chwyt z r5py): *„Bez tramwaju przeciętny mieszkaniec
   traciłby [██▓▓░░] swojego 30-minutowego zasięgu."*
4. **Akapit interpretacji**, ~5 wierszy: gdzie leżą korytarze zależności, co znaczy
   sub-addytywność, i **zdanie-zastrzeżenie z §2** (model nie uruchamia zastępczych).
5. **Mikro-akapit źródeł**, ~9 px: `ZDiT Łódź GTFS 2026-08-24 · OpenStreetMap · GUS NSP 2021 ·
   policzone w QGIS wtyczką Easy-R5 na silniku Conveyal R5 7.6 · CC BY 4.0 ·
   github.com/GISBoost/easy-R5`

**Prawa część** — mapa, EPSG:2180, bez ramki:

- heksagony `tram_share` — **7 klas manualnych**: `0–5 / 5–15 / 15–25 / 25–40 / 40–55 /
  55–70 / >70%`; rampa jednobarwna, ciemniejsze = większa zależność od tramwaju;
  obrys heksagonów **wyłączony** (przy 500 m siatka sama tworzy szum),
- klasa **„brak dostępu transportem w 30 min"** — jasny szary `#E6E3DE`, wymieniona w
  legendzie osobno,
- heksagony `pop_total = 0` — przezroczyste,
- granica miasta — linia `#B9B4AC`, 0,6 px,
- **żadnych** linii tramwajowych na mapie głównej. Cały efekt polega na tym, że korytarze
  **rysują się same**. Weryfikacja idzie do **insetu** ~200×140 px w prawym dolnym rogu:
  szkielet sieci tramwajowej z `shapes.txt`, podpisany *„sieć tramwajowa dla porównania"*,
- bez podkładu, bez siatki, bez strzałki północy, bez podziałki (skala jest nieinformatywna
  przy siatce heksagonalnej i tak),
- logo GISBoost i logo Easy-R5 w prawym dolnym rogu, wysokość 24 px.

**Paleta.** Do doboru z `dataviz` — wymagania twarde: sekwencyjna, jednobarwna, bezpieczna
dla deuteranopii, o monotonicznej jasności, czytelna po wydruku w skali szarości, i
**niekonfliktująca z paletą logo** (§ `docs/notes/logo-brief.md`). Nie używać czerwieni —
r5py ma czerwień i wygląda to na kopię.

**Wariant P2** — ta sama kompozycja, inny odcień, klasy `0 / 0–5 / 5–10 / 10–20 / >20%`,
tytuł *„Gdzie Łódź działa jako jedna sieć, a nie jako dwie?"*.

## 8. Kamienie

| kamień | co | prompt |
|---|---|---|
| **F1** | `TRANSIT_SUBMODES` we wtyczce + testy + i18n + README | `docs/prompts/easy-R5_F1-transit-submodes_prompt_for-claude-code.md` |
| **F2** | Sieć, siatka, populacja area-weighted, POI→heks, warstwa celów, walidacja daty | `…_F2-data-prep_…` |
| **F3** | Cztery przebiegi, niezmienniki I1–I3, metryki, GPKG + CSV | `…_F3-runs-and-metrics_…` |
| **F4** | P1, P2, P3 — kartografia | `…_F4-cartography_…` |
| **F5** | P5, P6, P7 — teksty | `…_F5-writeup_…` |
| **F6** *(opcjonalny)* | Warstwa „zły dzień": ta sama czwórka na sieci ze zrealizowanego feedu P85 | do napisania po F5 |

**Jeden kamień na sesję.** Po każdym: test → review → naprawa blokerów → commit.

## 9. Kryteria akceptacji

**F1**
- [ ] Domyślne zachowanie **bit-w-bit** identyczne z 0.1.0 (pusty wybór → 8 trybów). Cały
      istniejący zestaw 120 testów przechodzi bez zmian.
- [ ] Nowe testy: podzbiór przechodzi do `job_spec`; `MODE=WALK` + wybór → `transit_modes == []`;
      kolejność znormalizowana; metadane zawierają `transit_submodes`.
- [ ] `flake8` czysto; stringi w `tr()`.

**F2**
- [ ] `network.json` raportuje **9 893** aktywne kursy na 2026-08-24.
- [ ] `Σ pop_total` po heksagonach mieści się w **1%** `Σ population` obwodów w granicy miasta.
- [ ] Liczba heksagonów z `pop_total > 0` **istotnie większa** niż 640 z pilotażu (jeżeli nie —
      to znaczy, że overlay nie zadziałał; zatrzymać się).
- [ ] `Σ srv_total` po heksagonach = **1 328** (żaden POI nie zgubiony, żaden podwójnie).

**F3**
- [ ] `I1`, `I2` spełnione dla **wszystkich** wierszy. Naruszenie = błąd, nie przypis.
- [ ] `I3` spełnione — filtr trybów działa.
- [ ] Przebieg kontrolny na dokładnych punktach POI: **ρ Spearmana ≥ 0,95** dla
      `srv_total_30min` wobec wersji heksagonalnej.
- [ ] Wszystkie udziały mają `NULL` tam, gdzie `A^TB = 0`; próg `K` i liczba odfiltrowanych
      heksagonów w metadanych.
- [ ] Czas czterech przebiegów zmierzony i zapisany — to jest liczba do README
      („cała analiza: N minut na laptopie").

**F4**
- [ ] P1 czytelny w 100% skali i po zmniejszeniu do 600 px szerokości (miniatura GitHuba).
- [ ] P1 czytelny po konwersji do skali szarości.
- [ ] Klasa „brak dostępu" wizualnie **nie myli się** z najniższą klasą udziału.
- [ ] Zastrzeżenie z §2 fizycznie obecne na obrazie.

**F5**
- [ ] Każda liczba w tekście ma pokrycie w `out/*.csv`. Żadnej liczby „z pamięci".
- [ ] Zastrzeżenia z §4.5 i §2 obecne w P5 i w P6.
- [ ] Post na LinkedIn zgodny z `linkedin-post-style`.

## 10. Pułapki (skrót — pełna lista w `CLAUDE.md`)

- **Data bez kursów = cichy walk-only.** Twarda bramka daty ma zostać włączona
  (`ALLOW_NO_SERVICE=False`). Ten błąd raz już trafił na produkcję (GZM, 2026-08).
- **`MAX_WALK_TIME` zawsze ustawiony.** 10,2× przyspieszenia, zero różnicy wyniku.
- **`MAX_RIDES=3`.** Przy 1 nie ma przesiadki międzymodalnej i przypadek `TB` traci sens.
- **Percentyle dotyczą czasu przejazdu, nie dostępności.** p10 czasu = najszybsze odjazdy =
  **najwyższa** dostępność. W pilotażu ten znak został raz odwrócony —
  [`STUDENTS_ANALYSIS.md`](../../tools/accessibility_lodz/STUDENTS_ANALYSIS.md) §2.
- **Mały mianownik** — §4.5.
- **Zrealizowany i statyczny GTFS mają te same `trip_id`** — osobne katalogi sieci (dotyczy F6).
- **`network.dat` z innej wersji R5 się nie wczyta.** Klucz cache = hash wejść + wersja R5.
- **OSM POI to nie rejestr.** `lodz_services.csv` jest tym, czym jest — kontrolą, nie prawdą.
- **Heksagon liczy sam siebie** (§4.3).

## 11. Czego w tej analizie NIE ma

| Pomysł | Dlaczego nie |
|---|---|
| Sześć miast | osobny projekt; `flagship-analysis-candidates.md` §2D |
| Miasto bez tramwaju jako kontrola | j.w. §2E |
| P50/P85 „zły dzień" | tylko opcjonalny F6, poza rdzeniem |
| 2SFCA / dostępność konkurencyjna | T2-G, nie da się wytłumaczyć w podpisie mapy |
| Prawdziwe scenariusze R5 (`Scenario`) | T2-E, własny PRD |
| Metryka „minut obsługi" | T1-A, jeszcze nie istnieje |
| Twierdzenie „co się stanie po zamknięciu torowiska" | model tego nie liczy — §2 |

## 12. Źródła

- Rayaprolu & Levinson 2024 — <https://doi.org/10.1007/s11116-024-10555-9>
- r5r, słownik trybów — <https://ipeagit.github.io/r5r/reference/travel_time_matrix.html>
- r5py, hero image — <https://r5py.readthedocs.io/stable/>
- Modernizacja sieci tramwajowej Łodzi 2026–2029 — <https://transinfo.pl/infotram/lodz-modernizuje-cala-siec-tramwajowa-do-2029-roku-wyremontowany-zostanie-kazdy-metr-torow/>
- Lokalnie: `docs/notes/flagship-analysis-candidates.md`, `docs/prd/PR_easy-R5_v01.md`,
  `docs/notes/r5-engine-primer.md`, `tools/accessibility_lodz/*`, `tools/ses_income_lodz/*`
