# Ceny mieszkań (RCN) — raport M-P0…M-P6

Data: 2026-10-08. Wersja metody: `price-v1`. Wejście: `docs/handoffs/lodz-ceny-mieszkan-handoff.md`. Zakres: **tylko ceny transakcyjne z RCN**;
ceny ofertowe deweloperów (dane.gov.pl) to osobna, jeszcze niezrobiona warstwa.

## Źródło i pobranie (M-P0)
- WFS `https://mapy.geoportal.gov.pl/wss/service/rcn`, `ms:lokale`, bbox miasta (oś: północ, wschód), 86 199 rekordów (79 535 z TERYT 1061).
- **Stronicowanie bez sortowania jest niestabilne**: ten sam zakres zwracał różne zestawy rekordów przy różnym rozmiarze strony (część rekordów brakowała,
  inne się powtarzały: 12 789 duplikatów `gid`). Z `sortBy=gid` zestawy są identyczne. `price_fetch.py` zawsze sortuje i przerywa przy duplikacie.
- `DOK_DATA` w GML jest zagnieżdżone (`<gml:timePosition>`); parser to uwzględnia.
- Plik GeoPackage z Geoportalu („Pobierz dane" → „Transakcje", stan 13.08.2026, 77 337 lokali) ma **tę samą dziurę**; nie dał nic ponad WFS (usunięty z katalogu danych).
- **Dziura w rejestrze dla Łodzi** (mieszkania wg roku aktu, WFS): 2010–2018 po 4,6–9 tys.; 2019–2023 łącznie ok. 5; 2024 = 41; 2025 = 2289; 2026 = 6380.
  Dziura jest u źródła (powiatowy rejestr), nie rynkowa. Okno: od 2025-07-01 (decyzja Michała); realnie gęsto dopiero od października 2025.
- Licencja: RCN bezpłatny od 13.02.2026, strony transakcji zanonimizowane; **warunków ponownego wykorzystania nie znalazłem — do potwierdzenia przed publikacją**.

## Czyszczenie (M-P1, `config/price.yaml`)
Z 86 199 → **7 660 transakcji** (2025-07-03 … 2026-09-08). Odrzucone: poza oknem 59 772, funkcja ≠ mieszkalna 11 113, TERYT ≠ 1061 6 664, powierzchnia
poza 25–120 m² 431, typ transakcji ≠ wolny rynek 332, udział ≠ 1/1 115, brak ceny/powierzchni 83, cena/m² poza 2500–25000 29. Cena lokalu z `LOK_CENA_BRUTTO`; gdy pusta,
z ceny aktu tylko jeśli akt ma jeden wiersz (299 przypadków). Mediana zł/m² wszystkich aktów 9 233 (5%: 5 774, 95%: 12 699). Liczba aktów w miesiącu:
VII 2025 = 65, VIII = 33, IX = 131, potem 480–960; wrzesień 2026 = 5 (opóźnienie rejestracji).

## Agregacja do heksów (M-P2)
- Pierwszy pomysł (sam heks lub heks + 6 sąsiadów, n ≥ 5) dawał 6% / 24% heksów z ceną: transakcje skupiają się w nowych inwestycjach (10 heksów ma ≥ 100 aktów, maks. 370).
- **Zasięg adaptywny**: najmniejszy okrąg 250–1000 m (co 50) wokół środka heksa z ≥ 10 aktami z ≥ 5 różnych lokalizacji (współrzędne zaokrąglone do 1 m); wynik to mediana
  ważona odległością (waga od 1 w środku do 0,25 na brzegu). Wymóg 5 lokalizacji kosztuje 0,4 pp pokrycia, a chroni przed tym, że jedna inwestycja wyznacza cenę okolicy.
- **Heks zamieszkały** = ≥ 1000 m² obrysów budynków „budynki mieszkalne" z BDOT10k (2 411 z 5 662 heksów). Cena zostaje tylko tam (1 082 heksów niezamieszkałych
  z wartością zachowano w `price_m2_outside` do kontroli w QGIS).
- Pokrycie: **1 667 heksów z ceną = 69,1% zamieszkałych, 29,4% wszystkich**. Mediana promienia 350 m, 90% heksów ≤ 850 m. Percentyle ceny heksów: 10% 6 865, 25% 7 348, 50% 8 138, 75% 9 678, 90% 10 655 zł/m².

## Aplikacja (M-P3…M-P5)
- Eksport: `price_m2` (zł/m², puste = brak), `price_r`, `price_n` w `layers.json` (+ ok. 80 KB); blok `price` w manifeście (okres, progi, pokrycie); `method_version` zawiera `price price-v1`.
- Krzywa: ocena 1 przy ≤ 6 900, 0 przy ≥ 10 700 zł/m² (ok. 10. i 90. percentyl), liniowo; domyślna waga **0** (stare linki `#s=` bez zmian); wymaganie twarde „najwyżej X zł/m²"
  (domyślnie 10 000 ≈ 80. percentyl); heks bez ceny nie odpada i nie dostaje punktów (kryterium pominięte).
- UI (PL/EN): suwak, budżet, podgląd barwny (rysowany na istniejącym canvasie heksów: drugi pełnowymiarowy canvas zawieszał przeglądarkę), legenda, wiersz na karcie
  („9900 zł/m² (mediana z 11 transakcji w promieniu 300 m)"), podpis z okresem i ostrzeżeniem o dziurze, punkt w „Jak to działa".

## Walidacja
- `node score.test.js`: kierunek oceny, NaN, granica budżetu, brak ceny nie odrzuca, waga 0 i wyłączona krzywa bez wpływu: OK.
- Niezależne przeliczenie 12 losowych heksów (6 z ceną, 4 niezamieszkałe z wartością, 2 puste) osobnym kodem: cena, promień i liczba aktów zgodne w 12/12.
- Eksport: asercje (ceny dodatnie, spójność `price_m2`/`price_r`/`price_n`, ta sama wersja metody w obu metadanych).
- Przeglądarka lokalnie: brak błędów w konsoli; budżet 8 000 odrzucił 905 heksów; karta liczy 0,21 pkt dla 9 900 zł/m²; EN poprawne; widok 390 px bez przepełnienia; klik w heks działa z włączonym podglądem.

## Ograniczenia i do zrobienia
- Okno ok. 15 miesięcy, brak trendu; początek (VII–IX 2025) cienki, koniec niepełny; ceny z aktów to nie ceny ofertowe, nowe budynki widać z opóźnieniem.
- Cena okolicy do 1000 m, nie konkretnego budynku; 31% heksów zamieszkałych bez ceny.
- Do potwierdzenia: warunki ponownego użycia RCN; wizualna kontrola w QGIS; ceny ofertowe deweloperów jako osobna warstwa; publikacja (nic nie wypchnięto).
