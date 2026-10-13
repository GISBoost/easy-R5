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


# Easy-R5 — analiza flagowa: decyzja i plan (v3, 2026-09-05)
 
Pełne dokumenty leżą w repo `easy-R5`, nie tutaj. Ten plik jest wskaźnikiem dla przyszłych sesji.
 
## Decyzja aktualna (v3): **kolej wyrzucona na razie — wracamy do v1, dwa tryby**
 
**Kierunek:** komplementarność modalna w Łodzi — kontrfaktyczne wyłączanie trybów w R5
(`transitModes`), metodyka wg Rayaprolu & Levinson 2024, *Transit modal complementarity*,
Transportation, doi:10.1007/s11116-024-10555-9 (open access). **Aktywny zakres: `docs/prd/PR_easy-R5_flagship-lodz-modal.md` (v1) — tramwaj i autobus, bez kolei.**

**Dlaczego v2 (kolej ŁKA) jest zdjęta z aktywnego planu, nie skasowana.** Sesja 2026-09-05
sprawdziła feed ŁKA (`docs/notes/lka-gtfs-audit.md`) i znalazła dwa problemy różne od tych,
które przewidywał PRD v2:

1. Klucz `lka` w `easy-GTFS-RT`/`gtfs-dashboard` nagrywał **złą sieć** (autobusy z
   `zbiorkom.live`, nie kolej). Statyczna część jest **naprawialna** — prawdziwa kolej jest
   w `mkuran.pl/gtfs/polish_trains.zip` (24 stacje w Łodzi, 274 kursy kolejowe/dzień na
   2026-08-21). `easy-GTFS-RT/config/cities.json` już poprawione na tę sesję.
2. **Zrealizowana warstwa P50/P85 dla kolei nie da się zbudować bez nowego kodu.** Jedyne
   źródło RT dla ŁKA to `mkuran.pl/gtfs/polish_trains/updates.json` — feed **TripUpdates**
   (bezpośrednie potwierdzone czasy), nie VehiclePositions. `easy-OTP/tools/family_a_reconstruction`
   obsługuje wyłącznie VehiclePositions (poll → map-match → interpolacja) — nie ma ścieżki dla
   TripUpdates. To jest nowy kod w innym repo, poza zakresem, który `easy-GTFS-RT/CLAUDE.md`
   pozwala dotykać bez osobnej, wyraźnej zgody Michała.

**Decyzja Michała 2026-09-05 (sesja 2): nie wchodzimy w TripUpdates teraz.** Kolej wraca jako
osobny temat, kiedy będzie na to czas — PRD v2-rail zostaje w repo jako **Parked**, nie
usunięty (patrz `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`, nagłówek). Kamienie F2b i
F6 (`docs/prompts/`) są nieaktywne razem z nim.

## Co jest aktywne teraz

Dwa tryby (tramwaj, autobus), metodyka i pytanie badawcze **z PRD v1 bez zmian** — patrz
`docs/prd/PR_easy-R5_flagship-lodz-modal.md` §1. To jest zawężona wersja repliki Rayaprolu &
Levinson (2 z 3 trybów artykułu), nie pełna — pełna wraca z kolejowym rozszerzeniem.

**Hero image:** mapa `tram_share` (ile 30-minutowego zasięgu znika bez tramwaju) — definicja
v1 (`(A^TB − A^B)/A^TB`, świat dwutrybowy), **nie** definicja v2 z pełną siecią. Nie mieszać.
 
**Parametry decyzji Michała:** opportunities = populacja + usługi jako kontrola; zasięg = tylko
miasto Łódź; filtr trybów = parametr `TRANSIT_SUBMODES` we wtyczce (kamień F1).
 
## Most do opublikowanego artykułu
 
Kaczorowski, M. & Wróblewski, W. (2026), *Spatio-temporal and demographic distribution of public
transport accessibility: a GIS-based method using OpenTripPlanner*, **European Spatial Research
and Policy** 33(2). Artykuł mierzy czas obsługi (960 minut okna 06:00–22:00) dla 6 miast i mówi
o szynach cztery rzeczy: bufor 500 m od przystanku tramwajowego/kolejowego → 9,3 h vs 5,1 h
(≈1,8×, opisowo); „accessibility islands" wokół stacji; szyny = korytarze najwyższej
niezawodności czasowej; wniosek, że tramwaj i kolej to fundament ciągłości obsługi, a autobus
jest komplementarny.
 
Analiza flagowa robi to artykułowi w wersji v1 (aktywnej): (1) zamienia korelację buforową na
kontrfaktyk, (2) zamienia rozkład planowany na zrealizowany (P85, kamień F6 — tylko tramwaj i
autobus). Punkt (3) z poprzedniej wersji tego pliku — „rozdziela tramwaj od kolei" — **wraca
razem z kolejowym rozszerzeniem**, nie jest częścią v1: bez trzeciego trybu nie ma czego
rozdzielać, artykułowa kategoria „rail" pozostaje niedotknięta. Artykuł sam wskazuje silnik R5
jako następny krok.
 
## Gdzie co leży w repo
 
| Plik | Co |
|---|---|
| `docs/notes/flagship-analysis-candidates.md` | przegląd kandydatów + §5 rozszerzenie v2 (**parked**) i most do artykułu |
| `docs/prd/PR_easy-R5_flagship-lodz-modal.md` | **PRD v1 (dwa tryby) — aktywny** |
| `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md` | PRD v2 — **Parked**, patrz nagłówek pliku |
| `docs/prompts/easy-R5_F1-transit-submodes_*.md`, `F2-data-prep_*.md`, `F3-runs-and-metrics_*.md`, `F4-cartography_*.md`, `F5-writeup_*.md` | prompty aktywne, kolejność jak nazwane |
| `docs/prompts/easy-R5_F2b-rail-feed_*.md`, `F6-bad-day_*.md` | **nieaktywne razem z v2** — F2b to feed ŁKA, F6 to warstwa „zły dzień" na trzech trybach |
| `docs/notes/lka-gtfs-audit.md` | audyt feedu ŁKA — dlaczego v2 jest parked, co odblokowuje powrót |
| `docs/notes/logo-brief.md` | brief logo |
 
## Twarde fakty zweryfikowane w sesji
 
- **Data analizy: 2026-08-24 (poniedziałek) — z powrotem do wyboru z PRD v1 §3.1.** v2
  przestawiła datę na 2026-08-21, żeby złapać dzień nagrany przez oba operatory (ZDiT + ŁKA);
  bez kolei ten powód znika, a 2026-08-24 ma przewagę, którą v2 świadomie poświęciła:
  **porównywalność z badaniem 6 miast** (`tools/accessibility_cities/`, audyt z 2026-08-23).
  Jeśli kolej wróci, data znowu stanie się przedmiotem decyzji.
- **ŁKA jest w `easy-GTFS-RT`** pod kluczem `lka` — feed statyczny poprawiony w tej sesji na
  `https://mkuran.pl/gtfs/polish_trains.zip` (poprzednio wskazywał na złą, autobusową sieć —
  patrz `lka-gtfs-audit.md`). Nieistotne dla v1, zapisane dla przyszłego powrotu do kolei.
- Pomiar na `stop_times` (1 939 985 wierszy, static vs P50/P85 dla Łodzi, **tramwaj/autobus,
  nadal aktualne dla v1/F6**): w wariancie P85 tramwaje rozjeżdżają się mocniej niż autobusy —
  mediana +337 s vs +238 s, szczyt poranny +318 s vs +200 s.
- Rozszerzony `route_type` (conveyal/r5#1001), tunel średnicowy i inne fakty specyficzne dla
  kolei przeniesione do `lka-gtfs-audit.md` — nie dotyczą aktywnego zakresu v1.


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
