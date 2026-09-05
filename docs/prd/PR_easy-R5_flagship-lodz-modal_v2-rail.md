# PRD — analiza flagowa, v2: kolej aglomeracyjna (ŁKA) i odporność sieci

**Status:** Parked (2026-09-05, sesja 2) — decyzja Michała: nie wchodzimy teraz w budowę
ingestii TripUpdates dla ŁKA (patrz `docs/notes/lka-gtfs-audit.md` i
`docs/notes/flagship-analysis-decision.md` v3). **Aktywny plan wrócił do v1**
(`PR_easy-R5_flagship-lodz-modal.md`, dwa tryby). Ten plik zostaje jako gotowy projekt do
podjęcia, kiedy warstwa RT dla kolei będzie odblokowana — nie usuwać, nie przepisywać.
**Data:** 2026-09-05
**Zastępuje** §1, §2, §3, §4.1, §4.4, §4.6, §6, §8 i §10 dokumentu
[`PR_easy-R5_flagship-lodz-modal.md`](PR_easy-R5_flagship-lodz-modal.md) **wszędzie tam, gdzie
się różnią.** Reszta tamtego PRD (§4.2 parametry, §4.3 cele, §4.5 progi i NULL-e, §5 zmiana we
wtyczce, §7 kartografia, §9 kryteria akceptacji, §11 zakres) obowiązuje bez zmian.

> Konwencja jak w `PR_easy-R5_v01.md` / `PR_easy-R5_v02_realized-gtfs.md`: osobny plik zamiast
> przepisywania poprzedniego, żeby historia decyzji została czytelna.

---

## 0. Co się zmienia i dlaczego

Dwa tryby (tramwaj, autobus) rosną do trzech — dochodzi **kolej aglomeracyjna ŁKA**. To nie jest
kosmetyka:

1. **Domyka replikację metody.** Rayaprolu & Levinson (2024) liczą 11 przypadków modalnych dla
   *trzech* trybów (pociąg / tramwaj / autobus). Z dwoma trybami mieliśmy zawężoną wersję. Z
   trzema mamy **pełny, jeden do jednego, projekt badawczy tamtej pracy** — tylko na innym
   mieście i na silniku, który liczy to w minutach zamiast godzin.
2. **Otwiera warstwę odporności**, o którą chodziło Michałowi. Przy trzech trybach można zapytać
   *„ile Twojego zasięgu przetrwa awarię dowolnego jednego trybu"* — a to jest ilościowa wersja
   zdania z jego własnego artykułu o „strefach podwyższonego ryzyka wykluczenia transportowego".
3. **Podpina analizę pod opublikowany artykuł** (§2) i realizuje trzy rzeczy, które ten artykuł
   sam wskazuje jako ograniczenia albo jako przyszłą pracę.

**Weryfikacja, która to odblokowała** (2026-09-05, na `config/cities.json` w `easy-GTFS-RT` i na
`manifest.json` w `gtfs-dashboard`): **ŁKA jest w pipelinie nagrań pod kluczem `lka`**
(`display_name`: „Łódzka Kolej Aglomeracyjna", feed statyczny
`https://cdn.zbiorkom.live/gtfs/lodz-lka.zip`), ma **33 dni nagrań** (2026-08-02 → 2026-09-04),
a z `lodz` dzieli **31 wspólnych dni, w tym 15 dni roboczych ze statusem `ok` po obu stronach
i kompletem P50 / P85 / static**. Czyli warstwa „zły dzień" obejmuje **wszystkie trzy tryby
symetrycznie** — nie ma już problemu „kolej na rozkładzie, reszta zdegradowana".

## 1. Pytanie badawcze (zastępuje §1 v1)

> **Ile ze swojego zasięgu Łódź zawdzięcza tramwajowi, ile autobusowi, ile kolei aglomeracyjnej,
> ile temu, że można się między nimi przesiąść — i ile z tego przetrwa awarię któregokolwiek
> z nich?**

Cztery pytania szczegółowe:

1. **Poziom** — ilu mieszkańców jest w zasięgu 30 minut z przeciętnego zamieszkanego heksagona.
2. **Zależność modalna** — jaka część tego zasięgu znika bez tramwaju, bez autobusu, bez ŁKA.
3. **Komplementarność** — ile dostępności nie daje żaden tryb osobno, tylko dopiero przesiadka.
4. **Odporność** *(nowe)* — ile zasięgu przetrwa wyłączenie **najważniejszego dla danego miejsca**
   trybu; gdzie są heksagony **monomodalne**, czyli takie, które po utracie jednego trybu tracą
   praktycznie wszystko.

## 2. Podpięcie pod opublikowany artykuł (nowa sekcja)

> Kaczorowski, M. & Wróblewski, W. (2026). *Spatio-temporal and demographic distribution of
> public transport accessibility: a GIS-based method using OpenTripPlanner.*
> **European Spatial Research and Policy** 33(2).

To jest artykuł właściciela projektu, więc analiza flagowa nie jest „inspirowana" — jest jego
**bezpośrednią kontynuacją**. Cztery ustalenia z tamtej pracy, które ta analiza podejmuje:

| # | Co mówi artykuł | Status |
|---|---|---|
| R1 | Heksagony w promieniu **500 m od przystanku tramwajowego lub kolei miejskiej** mają średni czas obsługi **≈9,3 h**, pozostałe **≈5,1 h** — **≈1,8×**. Artykuł sam zaznacza, że to porównanie jest „descriptive and spatial rather than a formal statistical test" | do przetestowania kontrfaktycznie |
| R2 | Wokół stacji kolejowych powstają **„accessibility islands"** — wyspy dobrej dostępności, które „can mask weaker accessibility in intermediate areas" | do zmierzenia (§4.4) |
| R3 | Mechanizm: niezależność szyn od kongestii + wysoka częstotliwość → „corridors with the highest level of temporal reliability"; obszary tylko autobusowe → dostępność epizodyczna → „zones of increased risk of transport exclusion" | do zmierzenia jako odporność (§4.4) |
| R4 | Wniosek: „tram communication and metropolitan rail constitute the absolute foundation of transport service continuity", a autobus jest „necessary but merely complementary link … feeding passengers to the main rail axes" | do sprawdzenia — **rozdzielając tramwaj od kolei** |

Artykuł, dla Łodzi, raportuje **72%** populacji 20–29 z dostępem i **38%** w kategorii „stale
dostępne" (Tabela 2: 71 011 osób ogółem, 27 316 stale, 7 517 regularnie, 6 778 okresowo,
9 532 epizodycznie).

### 2.1 Co dokładnie ta analiza zmienia względem artykułu

Trzy różnice, każda do wypisania w tekście wyników:

1. **Korelacja → kontrfaktyk.** Bufor 500 m mierzy *współwystępowanie* szyn i dobrej dostępności.
   Wyłączenie trybu w R5 mierzy *wkład* tego trybu. To są różne pytania i różne liczby.
2. **Tramwaj oddzielony od kolei.** Artykuł łączy je w jednej kategorii „rail". W Łodzi to dwie
   zupełnie różne oferty: **25 linii tramwajowych i 22 206 kursów na dzień roboczy** wobec kolei
   aglomeracyjnej o takcie rzędu godziny. Rozdzielenie jest **testem** tezy R4, nie jej
   potwierdzeniem — i może ją zawęzić do „tramwaj", zamiast „szyny".
3. **Rozkład → zrealizowany.** Artykuł wprost wymienia jako ograniczenie, że feedy „represent
   planned rather than realised timetables, so they do not capture delays, cancellations or
   congestion". Warstwa P85 (kamień F6) zamyka tę lukę — teraz dla wszystkich trzech trybów.

Artykuł wskazuje też wprost **silnik R5 jako naturalny następny krok** („a relatively simple
solution seems to be transitioning to newer solutions such as the R5 engine"). Ta analiza jest
tym krokiem, wykonanym w QGIS-ie zamiast w notatniku.

### 2.2 Replikacja porównania buforowego — obowiązkowa

Żeby dwie liczby dały się zestawić uczciwie, F3 liczy **także** wersję buforową R1, ale **na
naszej metryce**, nie na czasie obsługi:

- `A^TBR(30, p50, pop)` dla heksagonów w promieniu 500 m od przystanku **tramwajowego lub
  stacji ŁKA** vs pozostałe → iloraz średnich.
- To samo osobno dla **tylko tramwaj** i **tylko ŁKA**.

Wynik idzie do tabeli obok liczby kontrfaktycznej, z jawnym zdaniem, że **artykuł mierzył czas
obsługi w oknie 16 h, a my mierzymy dostępność kumulatywną w 30 min — to nie są te same
jednostki i porównujemy kierunek, nie wartość.**

## 3. Dane — co dochodzi (zastępuje §3 v1)

### 3.1 Nowe źródło

| Co | Skąd | Uwagi |
|---|---|---|
| **ŁKA, GTFS statyczny** | `https://cdn.zbiorkom.live/gtfs/lodz-lka.zip` (klucz `lka` w `easy-GTFS-RT/config/cities.json`) | **niezweryfikowany przez autora tego PRD** — patrz §3.3 |
| **ŁKA, feedy zrealizowane P50 / P85** | `gtfs-dashboard`, klucz `lka` — przez algorytm wtyczki *Setup → Download realized GTFS* | 33 dni, 2026-08-02 → 2026-09-04 |

### 3.2 Data przebiegu — **zmiana z 2026-08-24 na 2026-08-21 (piątek)**

Powód: analiza ma teraz dwa operatory i warstwę zrealizowaną, więc **dzień routingu musi być
dniem, który oba operatory faktycznie nagrały**. Zweryfikowane na manifeście:

- `lodz`: 50 dni, 2026-07-14 → 2026-09-04
- `lka`: 33 dni, 2026-08-02 → 2026-09-04
- wspólnych: 31 dni; **dni roboczych ze statusem `ok` po obu stronach i kompletem P50/P85/static: 15**
  (`2026-08-03, 04, 05, 07, 12, 13, 14, 17, 18, 20, 21, 25, 26, 28, 31`)

**Wybór: 2026-08-21 (piątek)** — jest na tej liście, a Łódź ma dla tego dnia **wszystkie trzy
warianty już pobrane w repo** (`lodz_static_gtfs_2026-08-21.zip`,
`lodz_realized_2026-08-21_p50.zip`, `lodz_realized_2026-08-21_p85.zip`). Zero przeliczania od
nowa. Statyczny feed ZDiT obsługuje ten dzień **9 893 kursami** (dzień powszedni).

Rezerwa: **2026-08-20 (czwartek)**, też `ok`/`ok`. Użyć, jeżeli kalendarz feedu ŁKA nie obsługuje
21 sierpnia.

**Koszt tej zmiany:** tracimy dokładną porównywalność z badaniem 6 miast, które liczyło na
2026-08-24 (poniedziałek). Do wypisania w ograniczeniach. Zysk — spójność wszystkich trzech
trybów i obu wariantów sieci — jest większy.

### 3.3 Czego autor tego PRD **nie zweryfikował** — do zrobienia w F2b

Egress tej sesji nie przepuścił `cdn.zbiorkom.live`, więc zawartość feedu ŁKA jest **nieznana**.
Agent F2b **musi** sprawdzić i zapisać w `README.md` folderu, zanim cokolwiek policzy:

1. **`route_type`** w `routes.txt`. Jeżeli feed używa **rozszerzonych typów tras** (100–117,
   np. 106 „Regional Rail") zamiast klasycznego `2`, to **R5 7.6 może je po cichu porzucić** —
   [conveyal/r5 #1001](https://github.com/conveyal/r5/issues/1001), już odnotowane w
   `docs/notes/roadmap-candidates.md`. Objaw: `A^R == A^W` wszędzie (niezmiennik **I4**, §4.6).
   Naprawa: przemapować `route_type` na `2` w kopii feedu, z adnotacją w `README.md`.
2. **Lista stacji w granicach Łodzi** — ile ich jest, gdzie leżą, i czy wszystkie mieszczą się
   w wycinku `lodz.osm.pbf`. Przystanek poza wycinkiem OSM nie podepnie się do sieci pieszej.
3. **Zakres kalendarza** — czy feed obsługuje 2026-08-21. Jeżeli nie, przejść na 2026-08-20.
4. **Agencje w feedzie** — czy to wyłącznie ŁKA. Decyzja Michała (2026-09-05): **tylko ŁKA**.
   Jeżeli feed zawiera PolRegio, PKP IC albo inne, **odfiltrować po `agency_id`** i zapisać, ile
   kursów odpadło.
5. **Kursy poza obszarem** — trip, którego wszystkie stopy leżą poza wycinkiem OSM, jest
   bezużyteczny i tylko obciąża build. Przyciąć feed do bboxa (miasto + ~5 km bufora), zachowując
   monotoniczne `stop_sequence`.
6. **Liczba kursów ŁKA na 2026-08-21** — do `README.md`, obok 9 893 ZDiT. Ta liczba jest sama
   w sobie wynikiem: pokazuje skalę oferty kolejowej wobec miejskiej.

### 3.4 Sieci do zbudowania

Dwa katalogi, nigdy jeden — zrealizowany i statyczny dzielą `trip_id`:

| katalog | zawartość |
|---|---|
| `network_static/` | `lodz.osm.pbf` + ZDiT static 2026-08-21 + **ŁKA static** |
| `network_p85/` *(F6)* | `lodz.osm.pbf` + ZDiT realized P85 2026-08-21 + **ŁKA realized P85 2026-08-21** |

## 4.1 Przypadki modalne (zastępuje §4.1 v1)

**Osiem przebiegów** na jednej sieci — pełna krata podzbiorów trzech trybów plus baza piesza:

| symbol | `MODE` | `TRANSIT_SUBMODES` | co to jest |
|---|---|---|---|
| `W` | WALK | — | baza piesza |
| `T` | TRANSIT + WALK | `TRAM` | tylko tramwaj |
| `B` | TRANSIT + WALK | `BUS` | tylko autobus |
| `R` | TRANSIT + WALK | `RAIL` | tylko ŁKA |
| `TB` | TRANSIT + WALK | `TRAM, BUS` | miasto bez kolei |
| `TR` | TRANSIT + WALK | `TRAM, RAIL` | szyny |
| `BR` | TRANSIT + WALK | `BUS, RAIL` | miasto bez tramwaju |
| `TBR` | TRANSIT + WALK | `TRAM, BUS, RAIL` | pełna sieć |

`RAIL` jest już na liście `_TRANSIT_MODES` w `_matrix_base.py`, więc **kamień F1 nie wymaga
żadnej zmiany** — parametr z §5 v1 obsługuje to bez modyfikacji.

### Odwzorowanie na 11 przypadków Rayaprolu & Levinson (2024)

| ich przypadek | u nas |
|---|---|
| 1–3: pojedyncze tryby | `T`, `B`, `R` — przebiegi |
| 4–7: pary i trójka **z przesiadką międzymodalną** | `TB`, `TR`, `BR`, `TBR` — przebiegi |
| 8–11: pary i trójka **bez przesiadki międzymodalnej** | `max(A^T, A^B)`, `max(A^T, A^R)`, `max(A^B, A^R)`, `max(A^T, A^B, A^R)` — **liczone, nie przeliczane** |

Osiem przebiegów daje komplet jedenastu przypadków. Przy zmierzonej przepustowości (1 479
origins × okno 120 min ≈ 177 tys. przeszukań, ~13 tys./s w pilotażu, plus podwojenie przez
kontrolny przebieg walk-only wtyczki) całość mieści się w kilkunastu minutach na laptopie.

## 4.4 Metryki (zastępuje §4.4 v1)

Notacja jak w v1: `A^m_i` to wynik `RunAccessibility` dla przypadku *m*, heksagona *i*, progu *T*,
percentyla *p*, kolumny opportunities *o*. Headline: `T = 30`, `p = 50`, `o = pop_total`.

### 4.4.1 Poziom

```
level_i      = A^TBR_i
walk_share_i = A^W_i / A^TBR_i
```

### 4.4.2 Zależność modalna — ile znika, gdy tryb zniknie

```
tram_gain_i = A^TBR_i - A^BR_i        rail_gain_i = A^TBR_i - A^TB_i
bus_gain_i  = A^TBR_i - A^TR_i

tram_share_i = tram_gain_i / A^TBR_i    ← METRYKA HERO IMAGE (bez zmian z v1)
bus_share_i  = bus_gain_i  / A^TBR_i
rail_share_i = rail_gain_i / A^TBR_i
```

**Uwaga na definicję.** W v1 `tram_share` był liczony jako `(A^TB − A^B)/A^TB` w świecie
dwutrybowym. Teraz jest liczony **w pełnej sieci**: `(A^TBR − A^BR)/A^TBR`. To jest inna liczba
i inna interpretacja („co znika, gdy z *całej* sieci usunąć tramwaj"). **Nie mieszać wersji** —
w `COLUMNS.md` obie definicje mają być rozpisane, a stare pola z v1 nie mają być reużywane.

### 4.4.3 Komplementarność

```
no_transfer_i      = max(A^T_i, A^B_i, A^R_i)
transfer_premium_i = A^TBR_i - no_transfer_i
transfer_premium_rel_i = transfer_premium_i / A^TBR_i

# premie parami — która przesiadka faktycznie coś daje
prem_TB_i = A^TB_i - max(A^T_i, A^B_i)
prem_TR_i = A^TR_i - max(A^T_i, A^R_i)
prem_BR_i = A^BR_i - max(A^B_i, A^R_i)
```

`prem_TR` to jest liczba, o którą chodzi w tezie R4 artykułu: **czy przesiadka tramwaj↔kolej
w ogóle coś w Łodzi daje.**

### 4.4.4 Sub-addytywność (na składowych po odjęciu bazy pieszej)

```
Ã^m_i    = max(0, A^m_i - A^W_i)
subadd_i = Ã^TBR_i / (Ã^T_i + Ã^B_i + Ã^R_i)      # <1 = tryby się dublują
```

### 4.4.5 Odporność — **nowa rodzina, sedno tego rozszerzenia**

```
loss_T_i = tram_gain_i / A^TBR_i
loss_B_i = bus_gain_i  / A^TBR_i
loss_R_i = rail_gain_i / A^TBR_i

worst_single_loss_i = max(loss_T_i, loss_B_i, loss_R_i)
resilience_i        = 1 - worst_single_loss_i
```

`resilience_i` czyta się wprost: **jaka część dzisiejszego 30-minutowego zasięgu przetrwa
wyłączenie tego trybu, który dla tego miejsca jest najważniejszy.**

```
monomodal_i = 1 gdy worst_single_loss_i ≥ 0.90
dominant_mode_i = argmax(loss_T, loss_B, loss_R)
```

`monomodal_i` jest ilościową wersją zdania R3 z artykułu o „strefach podwyższonego ryzyka
wykluczenia transportowego" — z tą różnicą, że artykuł identyfikował je jako „obszary obsługiwane
tylko autobusem", a my liczymy je **niezależnie od tego, który tryb jest tym jedynym**. Wynik
może pokazać monomodalne obszary tramwajowe, i to też jest ustalenie.

**Do raportu miejskiego:** ilu mieszkańców żyje w heksagonach `monomodal_i = 1`, w rozbiciu na
`dominant_mode_i`. To jest jedno zdanie do posta.

### 4.4.6 „Accessibility islands" — pomiar tezy R2

Na siatce heksagonalnej sąsiedztwo jest jednoznaczne (6 sąsiadów). Dla pierścieni 1–2:

```
island_index_i = A^TBR_i - median(A^TBR_j : j ∈ pierścienie 1-2 wokół i)
```

**Wyspa kolejowa** = heksagon, dla którego jednocześnie:
`island_index_i` w górnym decylu **oraz** `rail_share_i > 0`.

Do raportu: ile jest takich wysp, ilu ludzi w nich mieszka, jaki jest średni spadek `A^TBR`
między wyspą a jej pierścieniem 2. Jeżeli wysp nie ma — to też jest wynik i trzeba go napisać
wprost, a nie przemilczeć.

### 4.4.7 Agregaty miejskie

`Ā^m(T)` ważone populacją dla **wszystkich ośmiu** przypadków plus `no_transfer`, przy każdym
progu 15/30/45/60. Do tego: odsetek ludności z `monomodal_i = 1`, mediana `resilience_i`, i
tabela replikacji buforowej z §2.2.

## 4.6 Niezmienniki (zastępuje §4.6 v1)

`I1` i `I2` z v1 uogólniają się do jednego warunku na całej kracie podzbiorów:

```
I5 (monotoniczność kraty)
    dla każdej pary zbiorów trybów S ⊂ S':  A^S_i ≤ A^S'_i   dla każdego i, T, p, o
    (z A^W jako elementem najmniejszym)

    Konkretnie musi zachodzić m.in.:
      A^W ≤ A^T, A^B, A^R
      A^T, A^B ≤ A^TB ;  A^T, A^R ≤ A^TR ;  A^B, A^R ≤ A^BR
      A^TB, A^TR, A^BR ≤ A^TBR
```

```
I3 (filtr trybów działa — z v1, rozszerzone)
    mean_i |A^T_i - A^B_i| / mean_i A^TBR_i  > 0.05

I4 (kolej NIE została po cichu porzucona)         ← NOWY, krytyczny
    liczba heksagonów z A^R_i > A^W_i  >  0
    oraz: te heksagony leżą w sąsiedztwie stacji ŁKA

    Jeżeli A^R == A^W co do wiersza, R5 nie widzi kursów kolejowych. Najbardziej prawdopodobna
    przyczyna: rozszerzone route_type (conveyal/r5 #1001, §3.3 pkt 1). NIE interpretować tego
    jako "ŁKA nic nie daje" — to jest awaria danych, nie wynik.
```

Naruszenie `I5` albo `I4` = **przerwanie analizy**, nie przypis.

## 6. Produkty — co dochodzi (uzupełnia §6 v1)

| id | produkt |
|---|---|
| P1 | hero image `tram_share` — **bez zmian**, nadal tramwaj vs reszta |
| P2 | premia za przesiadkę — **bez zmian** |
| P3 | wykres `Ā^m` — **rozszerzony do 8 przypadków + `no_transfer`** |
| **P8** | **mapa odporności** `resilience_i` + warstwa `monomodal_i` z kolorem wg `dominant_mode_i` |
| **P9** | mapa `rail_share_i` z zaznaczonymi wyspami (`island_index` w górnym decylu) — **tylko jeżeli `rail_share` ma gdziekolwiek sensowne wartości**; jeżeli nie, zamiast mapy jeden akapit z liczbami |
| **P10** | tabela replikacji: porównanie buforowe 500 m (§2.2) obok liczby kontrfaktycznej |

**Hero image się nie zmienia.** Powód w §12.

## 8. Kamienie (zastępuje §8 v1)

| kamień | co | zmiana |
|---|---|---|
| F1 | `TRANSIT_SUBMODES` | **bez zmian** — `RAIL` już jest w `_TRANSIT_MODES` |
| F2 | sieć, siatka, populacja, warstwa celów | data zmienia się na **2026-08-21** |
| **F2b** | **feed ŁKA: pobranie, audyt §3.3, przycięcie, wspólna sieć** | **NOWY**, po F2 |
| F3 | przebiegi i metryki | **8 przebiegów** zamiast 4; nowe metryki §4.4.5–4.4.7; niezmienniki `I3`–`I5` |
| F4 | kartografia | + P8, P9, P10 |
| F5 | teksty | + sekcja podpięcia pod artykuł (§2) |
| **F6** | **warstwa „zły dzień": te same 8 przebiegów na `network_p85/`** | **awansowany z opcjonalnego** — kolej ma teraz własne nagrania, więc porównanie jest symetryczne |

## 10. Pułapki — co dochodzi (uzupełnia §10 v1)

- **Rozszerzone `route_type` w feedzie kolejowym.** Największe ryzyko całego rozszerzenia.
  Objawia się jako „ŁKA nic nie daje", czyli jako **wynik**, a nie jako błąd. Niezmiennik `I4`
  istnieje wyłącznie po to.
- **Przystanki poza wycinkiem OSM** nie podpinają się do sieci pieszej — cicha strata kursów.
- **Feedy ZDiT i ŁKA muszą dotyczyć tego samego dnia.** Dwa operatory, dwa niezależne nagrania.
- **Zrealizowany i statyczny dzielą `trip_id`** — osobne katalogi sieci, teraz razy dwa operatory.
- **`tram_share` ma w v2 inną definicję niż w v1** (§4.4.2). Nie porównywać liczb między wersjami.
- **Godzinowy takt kolei a okno 120 min.** Przy takcie rzędu godziny mediana i P90 dostępności
  kolejowej mogą się drastycznie różnić. To jest cecha oferty, nie artefakt — ale wynik **musi**
  być raportowany dla percentyla, a nie „ogólnie".
- **Łódź Fabryczna jest dziś stacją czołową.** Tunel średnicowy (Kaliska/Żabieniec ↔ Fabryczna,
  >7,5 km, trzy przystanki podziemne: Koziny, Polesie, Śródmieście) został wstrzymany we wrześniu
  2024 po zawaleniu ściany budynku przy al. 1 Maja; wznowienie prac ogłoszono w styczniu 2026,
  bez podanego terminu oddania. Dopóki tunelu nie ma, pociągi z zachodu i z północy **nie
  przejeżdżają przez miasto**. To jest kluczowy kontekst interpretacyjny i musi być w tekście.

## 12. Uczciwe oczekiwanie co do wyniku (nowa sekcja — przeczytać przed rysowaniem map)

Prawdopodobny wynik dla ŁKA wewnątrz granic Łodzi: **`rail_share` bliski zeru dla większości
heksagonów, z niewielkimi wyspami przy stacjach.** Trzy powody, wszystkie znane z góry:

1. mało stacji w granicach miasta,
2. takt rzędu godziny wobec kilkuminutowego na głównych ciągach tramwajowych,
3. Fabryczna jako stacja czołowa — brak przejazdu przez miasto (tunel, §10).

**To jest wynik, nie porażka.** Jego wartość polega na trzech rzeczach:

- **kwantyfikuje tezę R2** artykułu o wyspach dostępności — pokazuje, jak wąskie one są,
- **zawęża tezę R4**: jeżeli w Łodzi kręgosłupem ciągłości obsługi jest **tramwaj**, a nie
  „szyny" jako kategoria, to jest to doprecyzowanie własnego opublikowanego wniosku na podstawie
  mocniejszej metody — a nie jego podważenie,
- **daje tunelowi liczbę.** Różnica między dzisiejszym `rail_share` a tym, co dałaby linia
  przelotowa, to jest dokładnie pytanie dla `RunScenarioAnalysis` (T2-E,
  `docs/notes/roadmap-candidates.md`). Ta analiza jest jego uzasadnieniem.

Dlatego **hero image zostaje przy `tram_share`** (§6). Mapa, na której nic nie widać, nie jest
mapą flagową — nawet gdy jej pustka jest prawdziwa i ciekawa. Kolej wchodzi jako P8/P9/P10 i jako
akapit, i awansuje na hero **tylko wtedy**, gdy liczby z F3 to uzasadnią.

## 13. Źródła — co dochodzi

- Kaczorowski, M. & Wróblewski, W. (2026), ESRP 33(2) — artykuł podpięty w §2 (PDF u Michała).
- Rayaprolu & Levinson (2024) — <https://doi.org/10.1007/s11116-024-10555-9>
- `GISBoost/easy-GTFS-RT`, `config/cities.json` — klucz `lka`, feed `cdn.zbiorkom.live/gtfs/lodz-lka.zip`
- `GISBoost/gtfs-dashboard`, `manifest.json` — 33 dni `lka`, 31 wspólnych z `lodz`
- conveyal/r5 #1001 (rozszerzone `route_type`) — <https://github.com/conveyal/r5/issues/1001>
- Tunel średnicowy: PLK / lodz.pl, styczeń 2026 — <https://lodz.pl/artykul/tunel-pod-lodzia-jest-przelom-prace-zostana-wznowione-szczegoly-71499/>
