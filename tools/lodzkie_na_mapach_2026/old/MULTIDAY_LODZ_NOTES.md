# Łódź — analiza wielodniowa (robustness check jednorodnej ujemnej delty)

Notatnik z przebiegu tego pod-zadania, prowadzony na bieżąco. Kontekst decyzji: Michał
zauważył, że delta (realized P50 − static) jest ujemna we WSZYSTKICH 10 (teraz 21)
kategoriach jednocześnie, dla jednego dnia (2026-09-10). Pytanie: czy to realne zjawisko
tego konkretnego czwartku, czy szum jednego dnia. Ustalone podejście: policzyć 3 niezależne
dni (wt/śr/czw tego samego tygodnia), każdy jako osobna para static-tego-dnia vs
realized-tego-dnia, potem uśrednić — NIE poolować surowych obserwacji RT (Michał: ZDiT ma
ograniczoną stabilność trip_id na dłuższe okresy, więc pooling jak przy ŁKA by się nie
udał; ale trzy NIEZALEŻNE pary dzień-po-dniu to inna operacja niż pooling i działa).

Przy okazji: Michał zdecydował rozszerzyć kategorie POI dla Łodzi do WSZYSTKICH 21
kandydatów (nie tylko 10, które przeszły próg ≥5-w-≥18/24-powiatów wojewódzki) — bo miasto
trywialnie ma dość obiektów każdej kategorii. To metodologiczne odejście od reszty pipeline'u
i wymaga osobnego opisu w dokumentacji końcowej: **Łódź jest badana innym zestawem kategorii
POI niż województwo** (21 vs 10), decyzja podjęta post-hoc, po zobaczeniu że próg wojewódzki
był kalibrowany pod rzadkość obiektów na wsi, nie pod miasto.

## Ustalenia wstępne (sprawdzone przed odpaleniem czegokolwiek)

1. **Dane dostępne**: gtfs-dashboard manifest, miasto `lodz`, dni 2026-09-05..09-12 status
   "ok", komplet assetów (static_gtfs/p50/p85) każdego dnia. Wybrane: **2026-09-08 (wt),
   2026-09-09 (śr), 2026-09-10 (czw)** — ten sam tydzień co oryginalna analiza.
2. **Statyczny rozkład ZDiT jest bajt-w-bajt identyczny dla wszystkich 3 dni** (sha256
   `7dbae3c0...`) — potwierdzone. `calendar_dates.txt`: wszystkie 3 dni aktywują dokładnie
   ten sam jeden `service_id` (`11500_11`), zero wyjątków usuwających kursy. Wniosek:
   **strona statyczna liczona RAZ, ważna dla wszystkich 3 dni** — nie ma potrzeby budować
   3 sieci statycznych ani liczyć 3 przebiegów statycznych.
3. `validate_gtfs.py` (funkcje `validate_one_feed`/`compare_static_vs_realized`) na
   wszystkich 3 parach static/realized: PASS, zero błędów, zdrowe rozkłady przesunięć
   (mediana 0s, p05 -75..-84s, grossly_early 0,01-0,10%).
4. Sprawdzone Łódź-specyficzne liczby kategorii POI (11 wcześniej odrzuconych, próg
   prosty ≥5 obiektów w samej Łodzi, bez wymogu pokrycia powiatów): uczelnia 88,
   szpital 25, biblioteka 84, dom_kultury 23, kino 12, teatr 25, muzeum 32,
   silownia 44, basen 51, centrum_handlowe 39, targowisko 27 — wszystkie przechodzą.
   **Łódź dostaje wszystkie 21 kategorii.**

## Plan wykonania

1. Przebudować `poi_targets_lodz` z 21 kategoriami (z cache `poi_all_raw`, bez ponownego
   skanu PBF).
2. Złożyć 2 NOWE foldery sieci: `net_lodz_p50_2026-09-08`, `net_lodz_p50_2026-09-09`
   (wzorem `net_lodz_p50`: `lodz.zip` = dzienny realized, `lka_train.zip` bez zmian).
   `net_lodz_static` i istniejący `net_lodz_p50` (09-10) NIE wymagają przebudowy sieci —
   tylko nowego przebiegu dostępności z nowymi destynacjami.
3. `validate_gtfs.py` na obu nowych folderach przed buildem.
4. `easyr5:buildnetwork` × 2.
5. `easyr5:runaccessibility`: 1× statyczny (nowe 21 kategorii, data 2026-09-10 — ważny dla
   wszystkich 3 dni per ustalenie #2), 3× zrealizowany (08/09/10, nowe kategorie).
6. Delta per dzień (ta sama reguła NULL-przy-zero-static), potem uśrednienie po 3 dniach
   per heksagon per kategoria + rozrzut dzień-do-dnia.
7. Maska RT — bez zmian, nie zależy od destynacji.
8. Update HANDOFF.md + ten plik z wynikami końcowymi.

## Log przebiegu

- 2026-09-13: plan zatwierdzony przez Michała, start realizacji.
- `poi_targets_lodz` przebudowana: **21 kategorii, 4161 punktów** (z cache `poi_all_raw`,
  bez ponownego skanu PBF) — `prepare_poi.build_lodz_all_categories()`.
- `assemble_networks.py`: dodane 2 nowe wpisy (`net_lodz_p50_2026-09-08`,
  `net_lodz_p50_2026-09-09`), złożone. `net_lodz_static`/`net_lodz_p50` (09-10) NIE
  przebudowane (sieć niezależna od destynacji, GTFS bez zmian).
- Walidacja (ad hoc, nie przez `validate_gtfs.py`'s CLI, bo ten zakłada jeden globalny
  `ANALYSIS_DATE` dla obu stron pary — patrz komentarz w pliku): wszystkie 3 pary
  static/realized (08/09/10) PASS, zero błędów. Dodatkowo sprawdzone: pliki zrealizowane
  09-08/09-09 dają IDENTYCZNĄ liczbę aktywnych kursów (10272) niezależnie czy odpytane
  własną datą czy 2026-09-10 -- bezpiecznie zostawić `run_accessibility.py`'s
  `DATE=C.ANALYSIS_DATE` (2026-09-10) sztywne dla wszystkich 4 przebiegów.
- 2 nowe sieci R5 zbudowane (`net_lodz_p50_2026-09-08` hash `1636d49a3f7063e7`,
  `net_lodz_p50_2026-09-09` hash `9f9bd81dce2aa5f3`), ten sam informacyjny komunikat o
  90-dniowym oknie `service_days` co zawsze (nie błąd, znany bug wtyczki #3).
- `run_accessibility.py`: dodane `A3b_lodz_p50_2026-09-08`, `A3b_lodz_p50_2026-09-09` do
  `RUNS`. Odpalone 4 przebiegi razem: `A3a_lodz_static` (nowe 21 kategorii, jeden przebieg
  ważny dla wszystkich 3 dni), `A3b_lodz_p50` (09-10), `A3b_lodz_p50_2026-09-08`,
  `A3b_lodz_p50_2026-09-09`. W trakcie liczenia w tle.
- `compute_metrics.py`: dodana `compute_multiday_lodz_delta()` -- delta per dzień
  (ta sama reguła NULL-przy-zero), `avg_delta_<kat>_c30` (średnia z 3 dni) +
  `spread_<kat>_c30` (max-min, sygnał niespójności dzień-do-dnia) do warstwy
  `hex_lodz_delta_multiday` (tylko 30 min w tabeli atrybutów, pełne dane 30+45 min per
  dzień + średnia 3-dniowa w `out/lodz_delta_summary_multiday.csv`).
  **Bug w kodzie tej funkcji naprawiony po drodze**: kategoria "total" nie ma własnego
  pola `srv_total` w wyniku R5 (to suma po kategoriach, liczona przez nas) -- pierwsza
  wersja próbowała odpytać nieistniejący klucz, dając `hexagons_zero_baseline=4260`
  wszędzie. Naprawione (funkcja `value()` sumuje po `survivors` dla "total").

## KRYTYCZNE ZNALEZISKO 2026-09-13: bug w `easyr5:runaccessibility` unieważnia 11 z 21 kategorii

Po przeliczeniu z 21 kategoriami (rozszerzenie z pkt. 2 planu) wszystkie 11 NOWYCH
kategorii (uczelnia, szpital, biblioteka, dom_kultury, kino, teatr, muzeum, silownia,
basen, centrum_handlowe, targowisko) wyszły z dostępnością **zero wszędzie**, oba cutoffy,
wszystkie heksagony. To NIE jest realny wynik -- sprawdzone bisekcją:

| Warstwa destynacji | N obiektów | Wynik dla uczelnia |
|---|---:|---|
| tylko uczelnia | 88 | działa (251/426 niezerowych) |
| uczelnia + szkola | 320 | działa |
| uczelnia + boisko_sport | 975 | działa |
| pełna warstwa (21 kategorii) | 4161 | **zero wszędzie** |
| surowa macierz (`runtraveltimematrix`, nie accessibility) na 88 pkt | 88 | działa -- 1034 par <30min, 4825 par <45min |

Wykluczone: eksport CSV (sprawdzony bezpośrednio, poprawny), geometria (współrzędne
sensowne), `MAX_WALK_TIME` (wymuszone 90 -- bez zmiany), mieszanie kategorii per se
(320 i 975 działa). Bug siedzi gdzieś między ~975 a 4161 obiektami destynacji, w
`easyr5:runaccessibility` (nie w samym routingu R5 -- surowa macierz jest poprawna).
Zgłoszone jako [GitHub issue #5](https://github.com/GISBoost/easy-R5/issues/5),
`KNOWN_ISSUES.md` #4. Root cause NIE znaleziony.

**Konsekwencje dla tej analizy:**
- Oryginalnych 10 kategorii (przedszkole...urzad_gminy, warstwa 3535 obiektów w
  oryginalnym zestawie) -- **NIE dotknięte**, wszystkie wyniki (w tym cała robustness-check
  3-dniowa powyżej) są ważne i poprawne.
- Rozszerzenie do 21 kategorii dla Łodzi (decyzja Michała, pkt. 2 planu) -- **wymaga
  workaroundu**: podzielić 21 kategorii na 2 mniejsze warstwy destynacji (np. stare 10 +
  nowe 11, każda osobno pod progiem ~975), policzyć osobno, złączyć wyniki. To podwaja
  koszt R5 (trzeba przeliczyć jeszcze raz A3a + 3x A3b dla drugiej warstwy).
- **Wszystkie liczby z 21-kategoriowego przebiegu policzone dziś (jednodniowe i
  3-dniowe) są NIEWAŻNE dla tych 11 kategorii** -- do przeliczenia po zastosowaniu
  workaroundu, decyzja czekająca na Michała.

## WZNOWIONE I ZAKOŃCZONE 2026-09-13 -- oba bugi naprawione, analiza dokończona

Michał zlecił naprawę obu ticketów (nie tylko opis) w osobnej sesji: znaleziono
prawdziwą przyczynę obu i naprawiono w `easy-R5` (commity `25d9825`, `e09189d`,
oba GitHub issue zamknięte z opisem przyczyny). Podsumowanie napraw:

- **Issue #5 (blokujący) -- przyczyna wcale NIE była limitem liczby destynacji.**
  W projekcie QGIS była otwarta warstwa `POI_Lodz` z zapamiętanym (nieaktualnym)
  schematem sprzed rozszerzenia `poi_targets_lodz` do 21 kategorii -- 12 pól/3535
  obiektów zamiast aktualnych 23 pól/4161. `lookupField()` na tym nieaktualnym
  schemacie albo nie znajdował nowych kolumn (-1 -> cicho 0), albo trafiał w
  NIEWŁAŚCIWĄ kolumnę względem aktualnego układu wierszy -- stąd 10 "starych"
  kategorii wyglądało sensownie (bo cicho czytały się nawzajem), a 11 "nowych"
  wychodziło jako czyste zero. Naprawa: `write_points_csv()` teraz sprawdza z
  góry, czy każde żądane pole istnieje na warstwie, i rzuca czytelny błąd
  zamiast cicho wstawiać 0.
- **Issue #4 (enhancement) -- pętla originów w `EasyR5Runner.java` teraz
  równoległa** (pula wątków = liczba rdzeni), zwalidowana jako bajt-w-bajt
  identyczna ze starą wersją sekwencyjną. Efekt praktyczny w tej analizie:
  4 przebiegi po 4260 originów × 21 kategorii, które przed naprawą trwałyby
  ~15-20 min każdy, zajęły **~140 sekund każdy**.

**Ważne znalezisko przy wznowieniu: `merge_split_lodz_categories.py` (workaround
z poprzedniej sesji) miał WŁASNY bug**, niezależny od buga wtyczki. Warstwa
`poi_targets_lodz_new11` zachowywała wszystkie 21 kolumn `srv_*` (tylko 450
punktów, żaden nie należący do "starych" 10 kategorii) -- więc przebieg na niej
też policzył (poprawnie, trywialnie zerowe) wartości dla starych 10 kategorii.
`merge_one()` doklejał WSZYSTKIE wiersze z pliku `_new11`, nie tylko te 11
nowych -- nadpisując (przez `load_wide()`'s "ostatni wpis wygrywa") poprawne
wartości starych 10 kategorii tymi trywialnymi zerami. Wykryte przez sanity
check: `srv_biblioteka` i `srv_boisko_sport` (zupełnie różne kategorie, 84 vs
887 obiektów) miały **identyczną wartość dla każdego z 4260 originów** w
scalonym pliku -- niemożliwe bez buga. **Wniosek: wszystkie liczby ze
scalonych (`_merged21.csv`) plików z wcześniejszej części tej sesji są
NIEWAŻNE i zostały odrzucone**, razem z workaroundem jako takim (nie jest już
potrzebny, skoro bug wtyczki jest naprawiony -- `run_accessibility.py`'s
`*_new11` wpisy usunięte, `compute_metrics.py` wskazuje z powrotem na
bezpośrednie `acc_A3a_lodz_static.csv`/`acc_A3b_lodz_p50*.csv`).

**Przeliczenie od zera, bezpośrednio na pełnej warstwie `poi_targets_lodz`
(4161 punktów, 21 kategorii), po naprawie obu bugów:**
4 przebiegi (`A3a_lodz_static`, `A3b_lodz_p50`, `A3b_lodz_p50_2026-09-08`,
`A3b_lodz_p50_2026-09-09`) -- każdy ~140s, zero podziału na warstwy.
Sanity check po fakcie: `srv_biblioteka` vs `srv_boisko_sport` -- 632/4260
identycznych wartości (zwykły przypadek nakładania się kategorii, nie 4260/4260
jak przy buggy merge) -- **potwierdzone poprawne**.

### Wyniki końcowe -- Łódź, 21 kategorii, static vs P50, 30 min, ważone populacją

**Jednodniowa (2026-09-10):**

| Kategoria | Δ @30min |
|---|---:|
| przedszkole | -0,741 |
| szkoła | -0,694 |
| uczelnia | -0,520 |
| przychodnia | -1,109 |
| szpital | -0,137 |
| apteka | -0,821 |
| biblioteka | -0,441 |
| dom kultury | -0,156 |
| kino | -0,296 |
| teatr | -0,364 |
| muzeum | -0,331 |
| park | -1,090 |
| plac zabaw | -2,084 |
| siłownia | -0,254 |
| basen | -0,025 |
| boisko/sport | -1,613 |
| supermarket | -0,456 |
| centrum handlowe | -0,319 |
| targowisko | -0,172 |
| poczta | -0,339 |
| urząd gminy | -1,417 |
| **total** | **-12,149** |

Pełne dane: `out/lodz_delta_summary.csv`. Wszystkie 21 kategorii ujemne --
jednorodny znak potwierdza się także po rozszerzeniu do pełnego zestawu
kategorii, nie tylko dla oryginalnych 10.

**3-dniowa robustness (08/09/10.09, `total` @30min):**

| Dzień | Δ total |
|---|---:|
| 2026-09-08 (wt) | -11,820 |
| 2026-09-09 (śr) | -13,138 |
| 2026-09-10 (czw) | -12,149 |
| **średnia 3 dni** | **-12,369** |

Znak ujemny i rząd wielkości stabilne w 3 niezależnych dniach -- **potwierdza
wniosek z oryginalnej (10-kategoriowej) analizy robustness**: to nie jest szum
jednego dnia. Pełne dane per kategoria/dzień: `out/lodz_delta_summary_multiday.csv`.
Warstwy `hex_lodz_delta` (77 pól, 4260 heksagonów) i `hex_lodz_delta_multiday`
w `lodzkie_base.gpkg` przeliczone i zapisane; projekt (`Delta_Lodz`,
`Poziom_Lodz`) odświeżony (`reloadData()`+`updateFields()`), wizualnie
sprawdzone -- realny przestrzenny wzorzec (czerwono-niebieska mozaika wokół
centrum, nie jeden jednolity kolor), zgodne z wcześniejszą obserwacją Michała
że rozkład przestrzenny delty jest ważniejszy niż sam znak.

### Sprzątanie po zakończeniu

- `run_accessibility.py`: `*_new11` wpisy w `RUNS` usunięte (workaround już
  niepotrzebny).
- `compute_metrics.py`: `MULTIDAY_CSVS`, `static = load_wide(...)` i `main()`'s
  `lodz_delta = compute_delta_layer(...)` wskazują z powrotem na bezpośrednie
  pliki (`acc_A3a_lodz_static.csv` itd.), nie `_merged21.csv`.
- `merge_split_lodz_categories.py` i `poi_targets_lodz_new11` -- pozostawione
  jako historyczny zapis (dokumentują znaleziony i naprawiony bug), ale poza
  aktywnym pipeline'em.
- `config.py`'s `CUTOFFS="30"` (bez 45 min) -- w mocy dla wszystkich powyższych
  przebiegów; tabela atrybutów `hex_lodz_delta`/`_multiday` ma teraz tylko
  pola `_c30` (żadnych `_c45` do usuwania -- `drop_fields()` w `compute_metrics.py`
  jest teraz bezpiecznym no-opem, zostawiony bez zmian).

**Nadal otwarte (nie w zakresie tego wznowienia):** E9 layouty drukowe, E10
pakiet zgłoszeniowy, przebiegi wojewódzkie A1/A2 (stare, jednopunktowe parki --
patrz HANDOFF.md #4), zrealizowana ŁKA (odłożona, patrz HANDOFF.md #5).
Restylowanie `hex_lodz_delta` w `style_layers.py` dla "total" @30min-only
(schemat pól się nie zmienił nazewniczo, ale liczba kategorii/zakres wartości
"total" tak -- sprawdzić klasy RdBu przed finalnym wydrukiem).

## 2026-09-14: wakacje vs rok szkolny -- czy jednorodna ujemna delta to Łódź czy wrzesień

Michał, po zobaczeniu jednorodnie ujemnej delty (sekcja wyżej): policzyć to samo w sierpniu
(wakacje) tą samą metodą, sprawdzić czy efekt wraca do zera. Wykonane, wynik jednoznaczny.

**Dni:** 08-13, 08-14, 08-17, 08-18 (wszystkie robocze, status `ok`, JEDNA edycja
statycznego rozkładu -- sha256 `e2269d6b...`, `feed_version=11484_11486_11488_11489`,
`feed_start_date=2026-08-10`, ODRÓŻNIA SIĘ od wrześniowej edycji `11499_11500`
/`feed_start_date=2026-09-01` -- to jest realna, osobna edycja "rok szkolny", nie ten sam
rozkład). 08-12 sprawdzony i ODRZUCONY -- wcześniejsza, inna edycja (`11484_11486`),
mieszanie jej z 08-13..18 zafałszowałoby porównanie o niezwiązaną zmianę śródwakacyjną.

**Dwie bazy statyczne, nie jedna** -- w przeciwieństwie do września: `validate_gtfs.
active_service_ids()` pokazał, że 08-13/14 (śr/czw) mają `service_id=11484_11` (9366
aktywnych kursów), a 08-17/18 (pon/wt) mają `11489_11` (9892) -- RÓŻNE kalendarze w tej
samej edycji. Zbudowane: `net_lodz_static_2026-08` (jedna sieć, dwa przebiegi z różnym
DATE) + 4 sieci `net_lodz_p50_2026-08-{13,14,17,18}`. `run_accessibility.py` rozszerzony
o opcjonalny klucz `"date"` w spec (był sztywno `C.ANALYSIS_DATE`). `validate_gtfs.py`
-- wszystkie 4 pary PASS, zero błędów, rozkłady przesunięć zdrowe (mediana 0s,
p05 -96..-101s, grossly_early <0,13%) -- ten sam poziom rygoru co zawsze.

**Incydent po drodze:** QGIS padł (proces `qgis-bin.exe` całkowicie zniknął) w trakcie
5. z 6 przebiegów, zostawiając osierocony `java.exe` (~4,1 GB) -- posprzątany
(`taskkill`). Po restarcie QGIS przez Michała okazało się, że WSZYSTKIE 6 przebiegów
faktycznie dokończyło pracę i zapisało poprawne pliki (`.params.json` obecne, liczba
wierszy zgodna) -- awaria nastąpiła po zapisie wyników, nie w trakcie liczenia. Nic nie
trzeba było powtarzać. Przyczyna awarii QGIS nieznana (brak dostępu do jego logu z tego
poziomu) -- może to być zwykłe wyczerpanie zasobów po 5 ciężkich przebiegach R5 z rzędu.

**Nowa funkcja `compute_metrics.compute_vacation_vs_term_delta()`** -- jak
`compute_multiday_lodz_delta`, ale z osobną bazą statyczną per dzień (`VACATION_DAY_STATIC`
mapuje 08-13/14 -> plik bazy 08-13, 08-17/18 -> plik bazy 08-17). Wypisuje
`out/lodz_delta_summary_vacation.csv`, ten sam kształt co wrześniowy wielodniowy plik.

**Wynik -- delta total @30min, ważona populacją:**

| Dzień | Δ total |
|---|---:|
| 2026-08-13 (śr) | +1,398 |
| 2026-08-14 (czw) | -2,318 |
| 2026-08-17 (pon) | -2,748 |
| 2026-08-18 (wt) | -2,192 |
| **średnia 4 dni** | **-1,465** |
| (dla porównania) średnia 3 dni wrzesień | **-12,369** |

Sierpień: ~8,4x mniejszy efekt niż wrzesień, i dużo mniej jednorodny -- 61/84 komórek
kategoria×dzień ujemnych (73%) wobec 62/63 we wrześniu (98%); jeden dzień (08-13) wyszedł
NETTO DODATNI. Po uśrednieniu 4 dni: 17/21 kategorii nadal ujemnych, ale 4
(`dom_kultury`, `basen`, `boisko_sport`, `supermarket`) w plusie.

**Niezależne potwierdzenie spoza tego pipeline'u** -- surowe `lodz_diff_<data>_p50_summary.csv`
z `easy-GTFS-RT` (agregacja per-linia, całkowicie inny kod niż R5/routing):

| Dzień | mean_delay_sec | % kursów zmienionych |
|---|---:|---:|
| 08-13 | 6,48 s | 18,4% |
| 08-14 | 6,00 s | 18,1% |
| 08-17 | 7,93 s | 18,5% |
| 08-18 | 10,44 s | 18,5% |
| **09-10** | **27,19 s** | **38,5%** |

Dwa niezależne pomiary (mój routing R5 i surowe opóźnienia z dashboardu) zgadzają się co
do kierunku i rzędu wielkości: wrzesień ma realnie ~3-4x wyższe opóźnienia i >2x wyższy
odsetek zmienionych kursów niż sierpień, nie tylko inną deltę dostępności.

**Zastrzeżenie do zapisania uczciwie:** `n_rows` w surowym podsumowaniu opóźnień jest we
wrześniu ~2x mniejsze niż w sierpniu przy niemal identycznej liczbie aktywnych kursów --
sugeruje to zmianę gęstości próbkowania GTFS-RT między oknami, nie tylko realną zmianę na
drodze. Nie unieważnia wniosku (dwa niezależne pomiary zgadzają się), ale to jest różnica
w zbieraniu danych między dwoma oknami czasowymi, do wpisania w ograniczenia metodyki.

**Wniosek:** jednorodna ujemna delta NIE jest czystą cechą Łodzi (systematycznie
optymistyczny rozkład vs rzeczywistość) -- gdyby tak było, sierpień wyglądałby tak samo
jednorodnie ujemnie jak wrzesień. Najbardziej prawdopodobne wyjaśnienie: powrót do
szkoły/pracy po wakacjach pogarsza realną punktualność (potwierdzone niezależnie w
surowych danych opóźnień), co przekłada się na spadek dostępności liczonej z rozkładu
zrealizowanego. Nie jest to dowód eksperymentalny (brak drugiego roku/innego okresu do
porównania), ale kierunek i rząd wielkości są spójne w dwóch niezależnych pomiarach.

Pliki: `out/lodz_delta_summary_vacation.csv` (pełne dane per kategoria/dzień),
`work/gtfs_raw/diff_summary_2026-08-{13,14,17,18}.csv` + `diff_summary_2026-09-10.csv`
(surowe dane porównawcze, do wglądu).

## PRZERWANE 2026-09-13 -- Michał: napraw krytyczne bugi najpierw, nie kontynuuj sam

*(sekcja historyczna, opisuje stan w momencie przerwania -- zobacz sekcję
powyżej dla stanu po wznowieniu i zakończeniu)*

Michał zdecydował: workaround (podział na 2 warstwy) -- **zaakceptowany i wdrożony**
(`poi_targets_lodz_new11`, 450 obiektów, `run_accessibility.py` ma 4 nowe wpisy
`*_new11`, `merge_split_lodz_categories.py` napisany i gotowy do odpalenia). Przebiegi
zostały wystrzelone i liczyły się w tle w momencie przerwania -- **nie wiadomo, czy się
skończyły** (monitor zatrzymany, sam proces QGIS/Java NIE zabity, może dokończyć się
samoistnie w tle; sprawdzić `out/acc_*_new11.csv.params.json` przy powrocie do tematu,
zanim cokolwiek się odpali ponownie).

**Polecenie Michała: nie naprawiać błędów samodzielnie, nie prowadzić dalszego śledztwa.**
Oba zgłoszone bugi mają już pełny opis w swoich ticketach (repro, co wykluczone, co
podejrzewane) -- to ma wystarczyć do dalszej naprawy przez kogoś innego / w osobnej
sesji, bez ponownego zaczynania śledztwa od zera:

- **[easy-R5 issue #4](https://github.com/GISBoost/easy-R5/issues/4)** (enhancement,
  nie blokujący) -- pętla originów w `EasyR5Runner.java` jest sekwencyjna (jeden
  `TravelTimeComputer` na raz), ~8,5% z 12 rdzeni wykorzystane. Jak wywołać: dowolny
  `easyr5:runaccessibility`/`runtraveltimematrix` na >1 originie, obserwować
  Task Manager / `Get-Process java` podczas liczenia. Co naprawić: rozważyć pulę wątków
  na pętli originów (`EasyR5Runner.java:267`) -- ale najpierw ustalić, czy
  `TravelTimeComputer`/`TransportNetwork` są bezpieczne wątkowo przy współdzieleniu
  jednej sieci (nierozstrzygnięte, patrz ticket).
- **[easy-R5 issue #5](https://github.com/GISBoost/easy-R5/issues/5)** (bug, blokujący,
  `KNOWN_ISSUES.md` #4) -- `easyr5:runaccessibility` cicho zwraca 0 dla niektórych pól
  opportunity, gdy warstwa destynacji jest duża (potwierdzone: 975 działa, 4161 nie).
  Jak wywołać: dokładna receptura w tickecie (siatka `hex_lodz_centroids`, sieć
  `net_lodz_static`, warstwa `poi_targets_lodz` z 21 kategoriami, dowolne pole z listy
  11 "nowych" kategorii jako `OPPORTUNITY_FIELDS`, porównać z tym samym polem na
  warstwie zawierającej TYLKO tę kategorię). Co sprawdzić dalej (nierozstrzygnięte, nie
  dochodzone głębiej na polecenie Michała): dokładny próg między 975 a 4161; czy
  `easyr5:runtraveltimematrix` (nie tylko `runaccessibility`) ma ten sam problem przy
  pełnej warstwie 4161 punktów wprost; czy przyczyna leży w `_matrix_base.py`'s eksporcie
  destynacji, czy po stronie R5/Java (`FreeFormPointSet`/linkage).

## Stan na przerwanie -- co jest zapisane i bezpieczne

- `config.py`: `CUTOFFS` zmienione z `"30,45"` na `"30"` (Michał, 2026-09-13) --
  obowiązuje dla wszystkich PRZYSZŁYCH przebiegów. Istniejące `out/*.csv` z dziś
  nadal mają wiersze dla 45 min, nieużywane po tej zmianie.
- Poprawka dużych parków (skalowane punkty na obwodzie) -- **gotowa, zapisana w
  `prepare_poi.py`**, zastosowana do `poi_all_raw`/`poi_targets_woj`/`poi_targets_lodz`.
- Rozszerzenie Łodzi do 21 kategorii -- **kod gotowy** (`prepare_poi.build_lodz_all_categories()`,
  `run_accessibility.py`'s `*_new11` wpisy, `merge_split_lodz_categories.py`), ale
  **przebiegi być może niedokończone** -- sprawdzić przed kontynuacją.
- 3-dniowa analiza robustness (10 oryginalnych kategorii) -- **kompletna i poprawna**,
  wynik: znak ujemny potwierdzony, stabilny (total @30min: -4,77/-4,99/-4,75, średnia -4,84).
- Nowe sieci R5 (`net_lodz_p50_2026-09-08`, `net_lodz_p50_2026-09-09`) -- zbudowane,
  gotowe do ponownego użycia bez rebuildu.
- HANDOFF.md zaktualizowany równolegle (E9/E10 nadal nie zaczęte, teraz też: multi-day
  Łódź i 21-kategoriowe rozszerzenie w stanie "przerwane, czeka na naprawę bugów").

**Następny krok po naprawie bugów (nie teraz):** sprawdzić czy 4 przebiegi `*_new11`
się dokończyły (`out/acc_*_new11.csv.params.json`), jeśli tak -- odpalić
`merge_split_lodz_categories.py`, potem `compute_metrics.main()` dla Łodzi (jednodniowe
i wielodniowe), zaktualizować warstwy i podsumowania z CUTOFFS="30" (usunąć logikę 45 min
z `compute_multiday_lodz_delta`/`compute_delta_layer` gdzie jest teraz zbędna).
