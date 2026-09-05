# Analiza flagowa Easy-R5 — kandydaci, dowody, decyzja

**Status:** notatka badawcza, 2026-09-05. Wybrany kierunek ma własny PRD:
[`../prd/PR_easy-R5_flagship-lodz-modal.md`](../prd/PR_easy-R5_flagship-lodz-modal.md).
Ten plik jest zapisem *dlaczego* wybrano ten kierunek i **co odrzucono lub odłożono** —
żeby pozostałe pomysły nie zginęły.

## 1. Czego szukamy

Jednego obrazu na samą górę `README.md`, który w trzy sekundy mówi: *ta wtyczka odpowiada
na pytanie, które cię obchodzi, w skali miasta, w QGIS-ie*. Wzorzec do pobicia to
[r5py – „How well does public transport work for slow walkers?"](https://r5py.readthedocs.io/stable/_images/HowWellDoesPublicTransportWorkForSlowWalkers_1200x720px.png):
1200×720 px, lewa trzecia to kolumna tekstu na kremowym tle (tytuł, akapit metody, legenda
**wpleciona w zdanie**, akapit interpretacji, mikro-akapit źródeł), prawe dwie trzecie to
mapa — siatka komórek w rampie biel→czerwień→prawie-czerń, bez podkładu poza bladym
błękitem wody i cienkimi granicami, bez strzałki północy, bez podziałki, logotypy w prawym
dolnym rogu.

Struktura tamtej mapy to **różnica między dwoma przebiegami** (pieszy 3 km/h vs 6 km/h).
Ta gramatyka jest dobra i warto ją powtórzyć. Pytanie ma być inne i mocniejsze.

Kryteria oceny kandydatów:

| # | Kryterium |
|---|---|
| K1 | Pokazuje to, w czym **R5 jest lepszy** niż OTP 1.5 / API-owe wtyczki QGIS (okno odjazdu, percentyle, wiele-do-wielu w skali miasta) |
| K2 | Czytelny jako **jedna mapa** dla laika i dla planisty |
| K3 | **Odtwarzalny przez użytkownika** samymi algorytmami wtyczki |
| K4 | Nie jest trywialny i ma **zaczepienie w literaturze** |
| K5 | Nie powiela tego, co GISBoost już opublikował |

## 2. Kandydaci

### A. Komplementarność modalna: tramwaj vs autobus vs sieć — **WYBRANY**

Kontrfaktyczne wyłączanie trybów w R5 (`transitModes`): liczymy dostępność osobno dla
`TRAM`, `BUS`, `TRAM+BUS` i `WALK`, i pytamy, ile zasięgu każdego heksagona **znika bez
tramwaju**, ile **znika bez autobusu**, i ile pojawia się dopiero wtedy, gdy wolno się
**przesiąść między trybami**.

Pierwotna intuicja Michała („czy mieszkanie bliżej przystanku tramwajowego daje lepszą
dostępność") w wersji „bliskość przystanku" jest rzeczywiście trywialna — to prawie
tautologia. Wersja kontrfaktyczna nie jest, i ma dokładne zaczepienie w literaturze:

> Rayaprolu, H. & Levinson, D. (2024). *Transit modal complementarity: measuring the access
> provided by transfers.* **Transportation** 53(4), 2057–2076.
> [doi:10.1007/s11116-024-10555-9](https://doi.org/10.1007/s11116-024-10555-9) — open access.

Autorzy liczą **11 przypadków modalnych** dla Sydney 1855–2015 (pociąg / tramwaj / autobus,
osobno, w parach z przesiadkami i w parach bez przesiadek), metryką jest
**person-weighted cumulative access to population**, a głównym wynikiem — że tryby są
**sub-addytywne** (razem dają mniej niż suma osobno, bo się dublują), że korzyść z
przesiadki rośnie z progiem czasowym, i że rola tramwaju jako „spoiwa" sieci przeszła na
autobus po latach 60. To jest dokładnie ta sama arytmetyka, którą Easy-R5 wykonuje jednym
przebiegiem na heksagon.

- **K1** ✅ cztery przebiegi po 1479 origins × 1479 destinations w oknie 120 min to
  ~700 tys. przeszukań; w OTP 1.5 to godziny, w R5 minuty.
- **K2** ✅ mapa „ile Twojego zasięgu jedzie na szynach" rysuje sama z siebie korytarze
  tramwajowe — dowód wizualny, którego nie trzeba tłumaczyć.
- **K3** ⚠️ wymaga jednej małej zmiany we wtyczce (wybór podtrybów transitu; `job_spec.py`
  już przyjmuje dowolną listę, brakuje tylko kontrolki w UI). To jest zaleta, nie wada:
  dogfooding, który zostawia po sobie funkcję.
- **K4** ✅ jak wyżej.
- **K5** ✅ GISBoost nie publikował nic o podziale modalnym.

**Bonus — temat jest na czasie.** Łódź modernizuje **całą** sieć tramwajową: ze 124 km
torowisk zostało 20 km do remontu, program biegnie do 2029, a w samym 2026 startuje pięć
placów budowy (Broniewskiego, Franciszkańska, Rzgowska, Nowe Centrum Łodzi,
al. Rydza-Śmigłego)
([TransInfo](https://transinfo.pl/infotram/lodz-modernizuje-cala-siec-tramwajowa-do-2029-roku-wyremontowany-zostanie-kazdy-metr-torow/)).
Pytanie „co się dzieje z dostępnością, kiedy korytarz tramwajowy znika na rok" jest w Łodzi
pytaniem operacyjnym, nie akademickim. Analiza jest też **przedsionkiem scenariuszy**
(T2-E w [`roadmap-candidates.md`](roadmap-candidates.md)) — kontrfaktyk przez `transitModes`
to najtańsza możliwa wersja tego, co docelowo zrobi `RunScenarioAnalysis`.

**Ryzyka i jak je nazywamy.** Wyłączenie tramwaju w R5 to **miara zależności**, nie prognoza
polityki transportowej: model nie uruchamia komunikacji zastępczej ani nie przenosi
pasażerów. To musi być napisane wprost w podpisie mapy i w tekście — inaczej pierwszy
komentarz pod postem będzie brzmiał „przecież puszczają autobusy zastępcze".

### B. Loteria odjazdu — rozrzut percentylowy w oknie — **ODŁOŻONY**

Jeden przebieg, percentyle P10/P25/P50/P75/P90 czasu przejazdu w oknie 07:00–09:00, mapa
„nie liczy się tylko **gdzie** mieszkasz, ale **kiedy** wyjdziesz z domu". Najczystszy możliwy
pokaz przewagi R5 nad OTP (K1 maksymalne — OTP potrzebuje 120 przebiegów na to samo).

Odłożony, bo: (a) częściowo zrobiony w pilotażu łódzkim jako Metoda A
([`../../tools/accessibility_lodz/STUDENTS_ANALYSIS.md`](../../tools/accessibility_lodz/STUDENTS_ANALYSIS.md) §2),
(b) metryka rozrzutu względnego okazała się tam niestabilna przy małych licznikach
(średni `rel_spread` = 3,01 zdominowany przez heksagony z medianą 1–2), (c) mapa dwóch liczb
naraz jest trudniejsza do czytania niż mapa jednej różnicy.

**Kiedy wrócić:** naturalnie łączy się z T1-A („minuty obsługi", histogramy per minuta
odjazdu) z [`roadmap-candidates.md`](roadmap-candidates.md). Kiedy T1-A powstanie, ta analiza
jest jego gotową demonstracją — i wtedy metryka „dla ilu ze 120 minut odjazdu docierasz w
30 min" zastąpi kruchy rozrzut percentylowy.

### C. Zły dzień: rozkład vs zrealizowany P85 — **ODŁOŻONY, ale jako warstwa opcjonalna F6**

Ile dostępności znika w złym dniu. Najmocniejszy dla marki (to jedyna analiza, w której
easy-OTP i Easy-R5 są jednym łańcuchem: `easy-GTFS-RT` → realized feed → R5), ale to
rozszerzenie Metody C z pilotażu, nie nowa metoda.

**Mamy już dowód, że w Łodzi jest tu sygnał** — pomiar wykonany 2026-09-05 bezpośrednio na
plikach z repo (`lodz_static_gtfs_2026-08-21.zip` vs `..._p50.zip` / `..._p85.zip`,
porównanie `departure_time` per `(trip_id, stop_sequence)`, 1 939 985 wierszy):

| wariant | tryb | wierszy zmienionych | mediana przesunięcia | p90 | mediana 06:00–09:00 |
|---|---|---:|---:|---:|---:|
| P50 | TRAM | 168 356 (28,5%) | +23 s | +140 s | +17 s |
| P50 | BUS | 314 717 (23,3%) | +15 s | +200 s | +4 s |
| **P85** | **TRAM** | 169 277 (28,6%) | **+337 s** | +728 s | **+318 s** |
| **P85** | **BUS** | 315 418 (23,4%) | **+238 s** | +717 s | **+200 s** |

Czyli: w typowym dniu obie sieci trzymają rozkład, a **w złym dniu tramwaj rozjeżdża się
mocniej niż autobus** — mediana +5,6 min vs +4,0 min, w szczycie porannym +5,3 vs +3,3 min.
To jest kontrintuicyjne (szyny „powinny" być odporniejsze) i samo w sobie jest nagłówkiem.
Zastrzeżenie: rekonstrukcja obejmuje 31,1% kursów tramwajowych i 25,8% autobusowych
(tylko te faktycznie zaobserwowane), więc to opis zaobserwowanej próby, nie całej sieci.

**Dlaczego to jest idealna warstwa F6 do analizy A, a nie osobna analiza:** dokładnie te same
cztery przebiegi, tylko na sieci zbudowanej ze zrealizowanego feedu P85, dają drugie zdanie
tej samej historii — *„a w zły dzień premia tramwajowa topnieje bardziej niż autobusowa"*.
Koszt: jeden dodatkowy build sieci i cztery przebiegi. Patrz PRD §8, kamień F6.

### D. Sześć miast tramwajowych — ranking — **ODRZUCONY jako flagowy**

Łódź, Warszawa, Kraków, Gdańsk, Poznań, Szczecin — wszystkie mają siatki 500 m, granice,
PBF-y i GTFS w `tools/accessibility_cities/`, więc technicznie to „tylko" pomnożenie
pipeline'u ×6. Efektowny plakat, ale to osobny projekt badawczy (i osobny artykuł), nie
hero image README. **Kiedy wrócić:** po tym, jak metoda z A obroni się na jednym mieście —
wtedy ×6 to jedna noc obliczeń i gotowy materiał na publikację.

### E. Miasto bez tramwaju jako kontrola — **ODRZUCONY jako flagowy, wart jako przypis**

Kielce (`tools/accessibility_cities/kielce/`, dane już są) nie mają tramwaju. Porównanie
„jak wygląda sub-addytywność w mieście jednomodalnym" jest ładnym kontrapunktem, ale
w hero image nie zmieści się drugie miasto bez rozbicia kompozycji.

### F. Studenci / uczelnie — **ODRZUCONY**

Zrobione i opublikowane
([„61% obszaru zamieszkanego przez studentów…"](https://gisboost.github.io/analizy/dostepnosc-uczelnie/)).
Powtórka jako flagowa byłaby cofnięciem się. Grupa 20–29 lat może wrócić jako **przekrój**
wewnątrz analizy A (czy młodzi mieszkają bardziej „tramwajowo"?) — patrz PRD §6, produkt P4.

### G. 2SFCA / dostępność konkurencyjna — **ODRZUCONY jako flagowy**

Mocniejszy wskaźnik naukowo (T2-G w [`roadmap-candidates.md`](roadmap-candidates.md)), ale
nie da się go wytłumaczyć w podpisie mapy, a hero image ma być zrozumiały bez czytania
metodologii.

## 3. Decyzja (2026-09-05, Michał)

| Wymiar | Wybór |
|---|---|
| Kierunek | **A — komplementarność modalna tramwaj/autobus** |
| Opportunities | **populacja osiągalna** (headline) **+ usługi publiczne** (kontrola odporności wniosku) |
| Zakres | **tylko Łódź** |
| Filtr trybów | **nowy parametr podtrybów w wtyczce** (nie filtrowanie GTFS, nie trzy sieci) |
| B, C, D, E, F | zapisane wyżej; C wraca jako opcjonalny kamień F6 |

## 4. Źródła

**Lokalne**
- `tools/accessibility_lodz/` — `RESEARCH_LOG.md`, `STUDENTS_ANALYSIS.md`, `COLUMNS.md`,
  `lodz_hex500.gpkg`, `lodz_services.csv`, GTFS static + P50 + P85 na 2026-08-21.
- `tools/accessibility_cities/MULTI_CITY_ANALYSIS.md` — pipeline 6 miast, audyt daty, ważenie populacją.
- `tools/ses_income_lodz/lodz.gpkg` — `obwody_spisowe` (3854 obiekty, pole `population`, suma 669 995).
- `docs/notes/r5-vs-otp.md`, `product-scope.md`, `roadmap-candidates.md`, `r5-engine-primer.md`.

**Zewnętrzne**
- Rayaprolu & Levinson 2024, *Transit modal complementarity*, Transportation — <https://doi.org/10.1007/s11116-024-10555-9>
- r5r, `travel_time_matrix()` — słownik trybów (`TRAM, SUBWAY, RAIL, BUS, FERRY, CABLE_CAR, GONDOLA, FUNICULAR`) — <https://ipeagit.github.io/r5r/reference/travel_time_matrix.html>
- r5py, hero image „slow walkers" — <https://r5py.readthedocs.io/stable/>
- Modernizacja sieci tramwajowej Łodzi do 2029 — <https://transinfo.pl/infotram/lodz-modernizuje-cala-siec-tramwajowa-do-2029-roku-wyremontowany-zostanie-kazdy-metr-torow/>

---

## 5. Rozszerzenie v2 (2026-09-05): kolej aglomeracyjna ŁKA — **PARKED (sesja 2, 2026-09-05)**

**Status:** zdjęte z aktywnego planu. Feed ŁKA pod kluczem `lka` okazał się złą (autobusową)
siecią; prawdziwa kolej ma tylko RT jako TripUpdates, którego `easy-OTP` nie umie jeszcze
skonsumować (nowy kod, poza zakresem tej sesji — decyzja Michała: nie teraz). Szczegóły:
[`../notes/lka-gtfs-audit.md`](lka-gtfs-audit.md), decyzja aktualna:
[`flagship-analysis-decision.md`](flagship-analysis-decision.md) (v3). Sekcja niżej opisuje
projekt v2 tak, jak został zaplanowany — pozostaje jako gotowy punkt powrotu, nie jako aktywna
praca.

Spec: [`../prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`](../prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md).

### 5.1 Dlaczego trzeci tryb zmienia jakość, a nie tylko ilość

**Domyka replikację.** Rayaprolu & Levinson (2024) liczą **11 przypadków modalnych** dla trzech
trybów. Z dwoma trybami mieliśmy zawężoną wersję ich projektu. Z trzema mamy pełny, jeden do
jednego — osiem przebiegów (`W, T, B, R, TB, TR, BR, TBR`) daje wszystkie 11 przypadków, bo
cztery warianty „bez przesiadki międzymodalnej" liczy się jako `max()`, nie jako przebiegi.

**Otwiera warstwę odporności.** Przy trzech trybach da się zapytać: *ile zasięgu przetrwa
wyłączenie tego trybu, który dla danego miejsca jest najważniejszy* (`resilience_i`), i gdzie
są heksagony **monomodalne** — takie, które po utracie jednego trybu tracą praktycznie wszystko.
Przy dwóch trybach ta metryka jest degeneratem.

**Podpina analizę pod opublikowany artykuł.** Kaczorowski & Wróblewski (2026), *European Spatial
Research and Policy* 33(2) — patrz §5.2.

### 5.2 Most do artykułu ESRP 2026

Artykuł mierzy **czas obsługi** (ile z 960 minut okna 06:00–22:00 kampus jest osiągalny w 30 min)
dla sześciu polskich miast i formułuje cztery ustalenia o transporcie szynowym:

| # | Ustalenie artykułu | Charakter |
|---|---|---|
| R1 | heksagony ≤500 m od przystanku tramwajowego **lub kolei miejskiej**: ≈9,3 h czasu obsługi vs ≈5,1 h poza — ≈**1,8×** | opisowy, autorzy sami piszą, że to nie jest test statystyczny |
| R2 | wokół stacji powstają **„accessibility islands"**, które „can mask weaker accessibility in intermediate areas" | jakościowy |
| R3 | szyny są niezależne od kongestii → „corridors with the highest level of temporal reliability"; obszary tylko autobusowe → „zones of increased risk of transport exclusion" | mechanizm |
| R4 | „tram communication and metropolitan rail constitute the absolute foundation of transport service continuity"; autobus jako „merely complementary link … feeding passengers to the main rail axes" | wniosek |

Analiza flagowa robi z tym trzy rzeczy, każdą do wypisania w tekście wyników:

1. **Korelacja → kontrfaktyk.** Bufor 500 m mierzy współwystępowanie. Wyłączenie trybu w R5
   mierzy wkład. To inne pytanie i inna liczba — dlatego F3 liczy **także** wersję buforową na
   naszej metryce, żeby obie liczby stały obok siebie uczciwie (PRD v2 §2.2).
2. **Tramwaj oddzielony od kolei.** Artykuł łączy je w jednej kategorii „rail". W Łodzi to dwie
   zupełnie różne oferty — 25 linii tramwajowych i 22 206 kursów na dzień roboczy wobec kolei
   aglomeracyjnej o takcie rzędu godziny. Rozdzielenie jest **testem** R4, nie potwierdzeniem.
3. **Rozkład → zrealizowany.** Artykuł wprost wymienia jako ograniczenie, że feedy to rozkład
   planowany. Kamień F6 to zamyka — i to **symetrycznie dla wszystkich trzech trybów**.

Artykuł sam wskazuje silnik R5 jako naturalny następny krok („transitioning to newer solutions
such as the R5 engine"). Ta analiza jest tym krokiem, wykonanym w QGIS-ie.

### 5.3 Co odblokowało kamień F6

Wcześniejsze zastrzeżenie do warstwy „zły dzień" brzmiało: nagrania GTFS-RT obejmują tylko ZDiT,
więc kolei nie ma czym zdegradować, a porównanie byłoby przechylone na jej korzyść.

**Zweryfikowane 2026-09-05 i nieaktualne.** W `GISBoost/easy-GTFS-RT`, `config/cities.json`,
istnieje klucz **`lka`** („Łódzka Kolej Aglomeracyjna", feed statyczny
`https://cdn.zbiorkom.live/gtfs/lodz-lka.zip`), a `manifest.json` dashboardu ma dla niego
**33 dni nagrań** (2026-08-02 → 2026-09-04). Z `lodz` daje to **31 wspólnych dni**, w tym
**15 dni roboczych ze statusem `ok` po obu stronach i kompletem P50/P85/static**:
`2026-08-03, 04, 05, 07, 12, 13, 14, 17, 18, 20, 21, 25, 26, 28, 31`.

Stąd zmiana daty analizy z **2026-08-24** na **2026-08-21 (piątek)** — jest na tej liście, a
Łódź ma dla tego dnia wszystkie trzy warianty już pobrane w repo. F6 awansuje z opcjonalnego
na pełnoprawny kamień.

### 5.4 Czego świadomie nie robimy (decyzje Michała, 2026-09-05)

| Wymiar | Wybór | Konsekwencja do wypisania w ograniczeniach |
|---|---|---|
| Zasięg | **tylko miasto** | mierzymy wyłącznie wkład ŁKA w dojazdy **wewnątrz** Łodzi, co zaniża jej rolę, bo sens kolei aglomeracyjnej jest regionalny. Wersja aglomeracyjna = future work |
| Zakres kolei | **tylko ŁKA** | PolRegio wozi ludzi w tych samych korytarzach i nie wchodzi do modelu; oferta kolejowa jest więc zaniżona |
| Kartografia | **hero image zostaje przy `tram_share`** | patrz PRD v2 §12 |

### 5.5 Uczciwe oczekiwanie

Prawdopodobny wynik: `rail_share` bliski zeru dla większości heksagonów, z wąskimi wyspami przy
stacjach. Trzy znane z góry powody: mało stacji w granicach miasta, takt rzędu godziny, i
**Łódź Fabryczna jako stacja czołowa** — tunel średnicowy (Kaliska/Żabieniec ↔ Fabryczna, >7,5 km,
przystanki Koziny / Polesie / Śródmieście) wstrzymano we wrześniu 2024 po zawaleniu ściany przy
al. 1 Maja, wznowienie prac ogłoszono w styczniu 2026 bez terminu oddania.

To jest wynik, nie porażka: kwantyfikuje R2, zawęża R4 z „szyn" do „tramwaju", i **daje tunelowi
liczbę** — czyli gotowe uzasadnienie dla `RunScenarioAnalysis` (T2-E w
[`roadmap-candidates.md`](roadmap-candidates.md)).
