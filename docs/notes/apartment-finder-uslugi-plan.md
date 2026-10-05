# Plan: usługi codzienne — „co najmniej X placówek w Y minut", jeden tryb na kryterium

Status: **plan po analizie, nic nie zaimplementowano** (decyzja Michała 2026-10-05: tylko planować/analizować).
Dotyczy PRD §12 poz. 1. Kontekst: [`apartment-finder-progress.md`](apartment-finder-progress.md), [PRD](../prd/PR_easy-R5_apartment-finder.md).
Decyzje Michała (2026-10-05): **4–5 kryteriów, nie 21**; RSPO tylko jeśli da się znaleźć dobre dane; **convenience wchodzi**; **jeden tryb na kryterium**.

## Kryterium

Dla każdego kryterium: **tryb** (pieszo / rower / auto / TP), **Y** (minuty), **X** (ile placówek).
Miękko: `s = min(1, liczba / X)`; twardo: `liczba ≥ X` (pole „Wymagaj", jak przy hałasie).
Liczba = ile placówek jest osiągalnych **z środka heksa** w ≤ Y min wybranym trybem (tym samym oknem czasu/rozkładem, co reszta scenariusza).

## Kryteria = 4 metakategorie (korekta 2026-10-05: miało być zbicie kilkunastu kategorii w szersze grupy)

Pierwsza wersja (5 wąskich kryteriów) była nieporozumieniem. Obowiązuje: **21 typów OSM z `lodzkie_na_mapach_2026` zebranych w 4 metakategorie**
(te same cztery grupy co w opisie konkursu). Liczymy osobno każdy typ (można zmienić grupowanie bez nowego liczenia R5), a eksport sumuje typy w metakategorie.

| Metakategoria | Typy (OSM) |
|---|---|
| Edukacja | przedszkola, szkoły, uczelnie |
| Zdrowie | przychodnie i lekarze (`clinic`, `doctors`, `healthcare=*`), szpitale, apteki |
| Handel i usługi | supermarkety, sklepy osiedlowe (`convenience`, `grocery`), centra handlowe, targowiska, poczty, urzędy |
| Kultura i rekreacja | biblioteki, domy kultury, kina, teatry, muzea, place zabaw, siłownie, baseny, boiska i obiekty sportowe |

Parków **nie** liczymy w metakategoriach (duży park byłby liczony raz na każdy punkt obwodu); zieleń ma osobne kryterium. Liczba w metakategorii to
suma placówek wszystkich jej typów w zasięgu (apteka + szpital = 2); opis składu jest widoczny pod każdą grupą w interfejsie.
Konfiguracja: `config/services.yaml` (`types`, `meta`).

## Czy liczymy „od środka heksa" i co to jest przypisanie placówki do heksa

**Tak, start zawsze od środka heksa** (jak wszędzie w apartment-finder). Pytanie dotyczy **końca trasy**. Są dwa sposoby:
- **Dokładny:** R5 liczy czas z środka heksa do **rzeczywistej współrzędnej** każdej placówki (jak w `lodzkie_na_mapach_2026`).
- **Skrót (przypisanie):** placówkę przesuwam do środka heksa, w którym leży, i używam gotowej macierzy heks×heks. Błąd położenia placówki do ok. 145 m (mediana ok. 95 m).

Test (2026-10-05, ta sama sieć i dzień 2026-10-02, 5 kategorii, 5662 heksów): zgodność rang (Spearman) skrótu z dokładnym:

| tryb, Y | ρ (skrót vs dokładny) |
|---|---|
| pieszo 5 min | **0,67–0,78** (za słabo) |
| pieszo 10 min | 0,89–0,93 |
| pieszo 15 / 20 min | 0,94–0,97 |
| rower 5 / 10 / 15 / 20 min | 0,92–0,95 / 0,98 / 0,99 / 0,99 |
| auto 5 / 10 / 15 min | 0,91–0,95 / 0,98–0,99 / 0,99–1,00 |
| TP 15 / 30 / 45 min (rano, rozkład) | 0,94–0,96 / 0,98 / 0,99 |

Wniosek: **skrót psuje tylko małe progi pieszo (≤ 10 min, promień 400–800 m, błąd 145 m jest wtedy duży)**. Średnie liczby różnią się o 0–12%.
(Wcześniejsze „+5–17%" vs `lodzkie_na_mapach_2026` wynikało głównie z innego dnia i próbek, nie z przypisania.)

**Dokładny jest tani**: czas R5 z środka heksa do 4161 punktów (wszystkie kategorie naraz): pieszo 42 s, rower 55 s, auto 63 s, **TP 79 s na scenariusz** (5 losowań).

## Rekomendowana architektura (hybryda)

- **Pieszo, rower, auto (3 okna): dokładny R5** — razem ok. 5 min lokalnie (QGIS headless, ten sam `_qgis_env.py`). Progi Y wybieramy dopiero po obliczeniu (macierz hex→placówka, potem progi w numpy).
- **TP (zmiana 2026-10-05, decyzja Michała: „przelicz dokładną metodą"): dokładny R5, na GitHub Actions** (`apartment-finder-services.yml`, job na dzień × porę, 6 scenariuszy: rozkład/P50/P85 × ŁKA; wersja bez QGIS: `scripts/ci_services.py`). ~~Skrót na macierzach~~ — pominięty (ρ ≥ 0,94, przy Y ≥ 30 min ρ ≥ 0,98) — zero nowego liczenia. Gdyby to nie wystarczyło: dokładny R5 dla 36 wariantów × 5 dni ≈ 15 jobów CI (ok. 80 s × 12 wariantów każdy) — tak jak M5.
- Wynik offline: tablice uint8 (liczba placówek) per scenariusz × próg × kryterium × heks; eksport jednego pliku na scenariusz (ok. 0,2 MB), razem kilka MB w repo danych.
- Kierunek: dla usług zawsze **odjazd z domu** (wiersz macierzy), bez „do celu / od celu".

## Dane (co jest, co zostaje do zrobienia)

- **Punkty:** `tools/lodzkie_na_mapach_2026/lodzkie_base.gpkg` → `poi_targets_lodz` (4161 pkt, 21 kategorii, WGS84). Siatka identyczna z naszą (4260 centroidów ≤ 1 m). `convenience` **nie ma** w tej warstwie (kategorie z `prepare_poi.py` nie obejmują `shop=convenience`) → dodać do ekstrakcji; przychodnie obecnie bez `healthcare=*`.
- **Odświeżenie z jednego PBF**, na którym liczymy resztę (bez Overpass, wzorzec `prepare_poi.py` przez OGR; Overpass dziś nie rozwiązuje obszaru Łodzi i wymaga nagłówka User-Agent).
- **Rozbieżność 350 vs 268 aptek wyjaśniona:** zbiory pokrywają się w 266 z 268; dodatkowe 84 apteki w `realtime_delay_lodz` leżą **poza miastem** (starsze przycięcie prostokątem).
- **Granica miasta:** placówek tuż za granicą (do 1,2 km) jest niewiele: 8 szkół, 12 przedszkoli, 12 aptek, 9 przychodni, 19 supermarketów. Nasze macierze obejmują tylko heksy w mieście, więc te placówki giną w heksach przy granicy. Do rozstrzygnięcia: zignorować i opisać, albo policzyć dokładnym R5 z POI z bufora (dokładny sposób to umożliwia, skrót nie).
- **RSPO:** dane są jawne i wolne do ponownego wykorzystania, ale: nowe API (`api.rspo.gov.pl`, od 15.01.2026) wymaga **wniosku e-mail o dostęp** (rspo@cie.gov.pl), stare wyłączono 2.03.2026, a otwarty zbiór na dane.gov.pl to stan z 30.09.2022 z **samymi adresami, bez współrzędnych** (geokodowanie osobno). **Na teraz nie opłaca się:** OSM ma ok. 230 szkół i 250 przedszkoli. Zostaje jako ewentualna kontrola liczności po uzyskaniu dostępu.
- **Convenience:** OSM Łódź ma ich dużo (ok. 780), więc kryterium „sklepy" będzie miało dużo wyższe liczby niż same supermarkety; domyślne X ustawić po obejrzeniu rozkładu (np. mediana liczby w 10 min pieszo).

## Frontend / punktacja

Sekcja „Usługi w zasięgu": wiersz na kryterium — ważność 0–5, tryb, Y, X, „Wymagaj". Karta „dlaczego ten wynik": „N aptek w ≤ Y min (tryb)".
Zero placówek = ocena 0; brak danych scenariusza = kryterium pominięte. Testy w `score.test.js`, PL/EN, stan w hashu (jak `nc` dla hałasu).

## Etapy

1. **S1 — dane:** rozszerzyć `prepare_poi.py` (convenience, `healthcare=*`), odświeżyć z naszego PBF, dedup, raport liczności + porównanie z `poi_targets_lodz`.
2. **S2 — obliczenie:** R5 dokładny dla pieszo/rower/auto + skrót dla TP; walidacja (bramka ρ ≥ 0,95 wg `poi_control.py`; dla TP przy Y ≥ 15 min).
3. **S3 — eksport + frontend**, test na żywych danych.
4. **S4 — QA i publikacja** po zgodzie.

## Decyzje do podjęcia

- Czy akceptujesz zestaw 5 kryteriów (tabela wyżej) i że reszta kategorii wypada z v1.
- Hybryda (dokładny dla pieszo/rower/auto, skrót dla TP) czy dokładny również dla TP (więcej obliczeń, ok. 15 jobów CI).
- Progi Y per tryb (propozycja: pieszo 5/10/15/20, rower 5/10/15/20, auto 5/10/15, TP 15/30/45) i domyślne X.
- Placówki za granicą miasta: ignorować czy dodać bufor 1,2 km (wymaga dokładnego R5 także dla TP).

## Ryzyka

- **Próg schodkowy i MAUP** (`realtime_delay_lodz`): liczba skacze wokół progu Y; do opisania, ewentualnie wygładzić.
- **Kompletność OSM** (apteki/sklepy w Łodzi dobre; convenience i przychodnie zmienne — dane różnią się między ekstraktami).
- Wynik modelowy, nie pomiar (jak reszta strony).
