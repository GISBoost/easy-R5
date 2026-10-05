# Easy-R5 — wybór lokalizacji mieszkania w Łodzi: PRD v1.1 (2026-10-05)

Status: szkic do zatwierdzenia przez Michała przed startem Claude Code.
Robocza nazwa: „Gdzie mieszkać w Łodzi" (decyzja D1).
Miejsce w repo: `docs/prd/PR_easy-R5_apartment-finder.md`. Prompt startowy: `docs/prompts/easy-R5_apartment-finder_prompt.md`.

---

## 1. Cel

Publiczna, statyczna strona w przeglądarce, na której osoba kupująca mieszkanie w Łodzi ustawia swoje wymagania, a mapa heksagonów pokazuje tylko miejsca, które je spełniają, i koloruje je wynikiem.

Wyróżnik: czasy dojazdu transportem publicznym liczone nie tylko z rozkładu, ale też ze zrekonstruowanego GTFS-RT (warianty P50 i P85). Użytkownik widzi, jak dojazd wygląda w praktyce, także w gorszy dzień. Żadna aplikacja do szukania mieszkań tego nie ma.

Narzędzie pokazuje model, nie wyrocznię. Nie jest poradą inwestycyjną ani wyceną nieruchomości.

## 2. Użytkownicy

- Główny: osoba (lub para) wybierająca dzielnicę pod zakup mieszkania w Łodzi, bez umiejętności GIS.
- Pierwszy użytkownik: Michał.
- Narzędzie publiczne (decyzja Michała): PL/EN, jasne zastrzeżenia, licencje danych, brak danych osobowych.

## 3. Zakres

### W MVP

- Siatka heksagonalna o rozstawie środków ok. 250 m dla całego miasta Łódź (bez gmin ościennych).
- Do 5 celów dojazdu, dowolnych, wskazywanych kliknięciem na mapie (cel przypina się do heksa). Każdy cel ma własny zestaw trybów, maksymalny czas i wagę.
- Przełącznik kierunku: „do celu" i „od celu", z domyślnym ustawieniem zależnym od pory dnia.
- Scenariusze (globalne): pora dnia × typ czasu (rozkładowy / P50 / P85) × limit przesiadek × ŁKA włączona lub nie.
- Tryby: pieszo, rower, auto (przybliżenie korków), transport publiczny.
- Kryteria miękkie: dojazdy do celów, odległość do przystanku tramwajowego (przedział idealny), odległość do przystanku autobusowego, częstotliwość kursowania, odległość do zieleni po sieci, hałas (drogowy, szynowy, przemysłowy), cena.
- Trzy warstwy punktacji: wymagania twarde, kryteria miękkie z wagami 0–5, suwak minimalnego wyniku.
- PL/EN, podstrona w repo `mapy-analizy`, schemat strony taki jak w tym repo.

### Poza MVP (roadmapa w §12)

Usługi codzienne pieszo, MPZP i ryzyka planistyczne, jakość powietrza, gminy ościenne, filtr cenowy, para z osobnymi celami, rower + TP, porównanie wybranych miejsc, inne miasta.

## 4. Decyzje podjęte

| # | Decyzja | Źródło |
|---|---|---|
| 1 | Publiczne narzędzie, PL/EN | Michał |
| 2 | Statyczna strona, architektura jak `mapy-analizy`, podstrona w tym repo | Michał |
| 3 | Rozstaw heksów 250 m, własna siatka heksagonalna, nie H3 (O1 rozstrzygnięte 2026-10-05); test 150 m jako pilotaż | Michał |
| 4 | Macierze R5 liczone wcześniej, strona tylko je wyświetla | Michał |
| 5 | 5 dni roboczych, wynik = mediana po dniach (osobno dla P50 i P85) | Michał |
| 6 | ŁKA jako przełącznik (kolej wł./wył.) | Michał |
| 7 | Auto: prędkości z danych autobusów przypisane odcinkom OSM, wygładzone w promieniu, podpis „przybliżenie korków" | Michał |
| 8 | Hałas z mapy akustycznej (ArcGIS REST, Intersit Łodzi): drogowy, szynowy, przemysłowy; Lden główny, Ln jako przełącznik „sypialnia" | Michał |
| 9 | Przystanek tramwajowy mierzony jako dojście do przystanku (nie do torów) | Michał |
| 10 | Cena z rejestru cen, agregacja do heksów, warstwa bez przełącznika; brak danych = pusty slot, nie blokuje MVP | Michał |
| 11 | Zieleń: odległość po sieci do najbliższej | Michał |
| 12 | Częstotliwość kursowania: schemat liczenia już istnieje w repo | Michał |
| 13 | Bez MPZP i bez jakości powietrza w MVP | Michał |
| 14 | Pipeline jako skrypt wołający wtyczkę easy-R5 (instrukcje i MCP QGIS są po stronie Michała) | Michał |
| 15 | Punktacja trzywarstwowa (twarde / miękkie z wagami / minimalny wynik) | Michał |
| 17 | Cztery pory dnia, w tym popołudniowy szczyt 15–18 | Michał, 2026-10-05 |
| 18 | Rano domyślnie „do celu" (analiza §5.2a) | Michał, 2026-10-05 |
| 16 | Dni: 5 ostatnich roboczych z kompletem danych Łódź + ŁKA (static, P50, P85); lista do zatwierdzenia przez Michała | Michał |

## 5. Funkcje

### 5.1 Siatka

- Rozstaw środków ok. 250 m. Dla Łodzi (ok. 293 km²) daje to rząd 5,4 tys. heksów, czyli ok. 29 mln par O–D na jeden scenariusz. To jest szacunek do zmierzenia w M0.
- H3 nie ma rozdzielczości 250 m (res. 9 ma środki co ok. 0,3 km). **Decyzja: własna siatka heksagonalna 250 m** (`native:creategrid`, bez generatora we wtyczce, zgodnie z CLAUDE.md), wersjonowana, stabilny `hex_id`.
- Cel kliknięty na mapie przypina się do heksa, więc błąd położenia to maks. ok. 145 m.
- Test 150 m (ok. 15 tys. heksów, ok. 225 mln par): wyłącznie pilotaż na wybranym fragmencie miasta, żeby sprawdzić, czy gęstsza siatka zmienia ranking miejsc. Nie wchodzi do produkcji.

### 5.2 Cele i kierunek

- Do 5 celów, klik na mapie. Każdy cel: nazwa, tryby (wielokrotny wybór; czas = minimum po wybranych trybach), maks. czas, waga, rodzaj (twardy / miękki).
- „Do celu": dla każdego heksa czas dojazdu do celu. „Od celu": czas z celu do heksa.
- Obie wartości pochodzą z tej samej macierzy O–D (odjazd w oknie czasowym): „do celu" to kolumna celu, „od celu" to jego wiersz. Układ plików musi pozwalać na tani odczyt obu (O4).
- Domyślnie: rano „do celu" (dom → praca), w popołudniowym szczycie „od celu" (powrót). Dla południa i całego dnia domyślnie „do celu" (O5 do potwierdzenia). Analiza porannego domyślnego: §5.2a.

### 5.2a Analiza: domyślny kierunek rano

Pytanie: czy rano domyślnie „do celu" (odjazd z heksa w oknie 07–09, cel = praca)?

- **Semantyka.** Kupujący pyta „ile będę jechał do pracy z tego miejsca". Rano to droga dom → cel: heks jest początkiem podróży, odjazd mieści się w oknie 07–09. „Od celu" rano odpowiada pytaniu „dokąd dojadę, jeśli wyjadę z celu o 7–9", czyli drodze pod prąd typowego ruchu; jako domyślna byłaby myląca.
- **Jedna macierz, dwa kierunki.** M[o,d] = podróż z o do d z odjazdem z o w oknie pory dnia. „Do celu" to kolumna celu (z każdego heksa do T, odjazd z heksa), „od celu" to wiersz celu (z T do każdego heksa, odjazd z T). Oba odczyty pochodzą z tej samej macierzy tego samego scenariusza, więc liczba przebiegów się nie zmienia. (Pierwsza wersja tego akapitu błędnie zakładała dwie osobne macierze; poprawione 2026-10-05 przy projektowaniu runnera.)
- **Asymetria sieci.** Czas TP „do celu" o 8:00 i „od celu" o 8:00 to różne wartości (inne częstotliwości, przesiadki, kierunek pików), więc nie wolno zastępować jednego drugim przez transpozycję macierzy. Mierzymy skalę asymetrii w M4 na próbce celów.
- **Układ plików.** Wiersz jest tani przy zapisie wierszowym, kolumna przy zapisie transponowanym; do odczytu obu kierunków trzeba przechowywać oba układy (podwaja rozmiar) albo zaakceptować wolniejszy odczyt kolumny (O4, rozstrzyga rozmiar z M4).
- **Auto.** Prędkości z autobusów są per pora dnia bez kierunku (§7.3), więc rano oba kierunki różnią się tylko geometrią sieci (jednokierunkowe ulice). Podpis „przybliżenie".
- **Wniosek:** rano domyślnie „do celu", z przełącznikiem; oba kierunki z jednej macierzy.

### 5.3 Scenariusze

Globalne przełączniki:

- **Pora dnia (4):** rano / południe / popołudnie / cały dzień. Propozycja okien: poranny szczyt 07:00–09:00, południe 11:00–14:00, **popołudniowy szczyt 15:00–18:00 (decyzja Michała, dodany)**, cały dzień 06:00–22:00 (okno z artykułu Kaczorowski & Wróblewski). Popołudniowy szczyt ma największe odchylenia od rozkładu, więc jest kluczowy dla wyróżnika P50/P85. Okna w `config/`, do zatwierdzenia po M0.
- **Typ czasu:** rozkładowy (statyczny GTFS tego samego dnia) / zmierzony P50 / zmierzony P85. Nazewnictwo w interfejsie: „zmierzony (rekonstrukcja GTFS-RT)", bo nie ma prawdy referencyjnej, rekonstrukcja to też model.
- **Przesiadki:** bez limitu / maks. 1.
- **ŁKA:** wł. / wył.

Tryby wybiera się per cel. Pieszo i rower nie zależą od GTFS, auto zależy tylko od pory dnia.

Liczba przebiegów na dzień (do potwierdzenia): TP 4 pory × 3 typy czasu × 2 przesiadki × 2 ŁKA = 48, plus pieszo 1, rower 1, auto 4 = 54 przy jednej macierzy na scenariusz, ok. 270 przebiegów na 5 dni. Liczba przebiegów nie zależy od kierunku (§5.2a). Wariant rozkładowy nie zależy od ŁKA-realized, więc część da się zdeduplikować (do zmierzenia w M0). Claude Code mierzy czas jednego przebiegu i szacuje całość przed pełnym startem.

### 5.4 Kryteria

| Kryterium | Definicja | Krzywa |
|---|---|---|
| Dojazd do celu k | czas (min) z macierzy, minimum po wybranych trybach | malejąca, 1 przy ≤ idealnym, 0 przy maks. czasie |
| Przystanek tramwajowy | odległość pieszo po sieci do najbliższego przystanku | **przedział idealny** (za blisko = hałas, za daleko = niewygoda) |
| Przystanek autobusowy | j.w. | malejąca |
| Częstotliwość | odjazdy/godz. na przystankach w zasięgu pieszym, per pora dnia | rosnąca z nasyceniem |
| Zieleń | odległość po sieci do najbliższego terenu zieleni od ok. 1 ha (O12) | malejąca |
| Hałas drogowy, szynowy, przemysłowy | udział powierzchni heksa powyżej progu dB (Lden; Ln przy trybie „sypialnia") | malejąca |
| Cena | zł/m² zagregowane do heksa, z liczbą transakcji | do ustalenia (O10) |

Parametry krzywych (progi, przedziały idealne) trafiają do `config/`, nie do kodu. Wartości domyślne proponuje Claude Code, Michał zatwierdza.

### 5.5 Punktacja

1. **Wymagania twarde.** Heks, który ich nie spełnia, znika (opcja „pokaż odrzucone" jako blady kolor). Przykłady: dojazd do celu > limit, udział powierzchni z hałasem drogowym > próg.
2. **Kryteria miękkie.** Każde daje wynik s ∈ [0, 1] z krzywej i ma wagę w ∈ {0…5}. Waga 0 wyłącza kryterium.
3. **Wynik** S = 100 × Σ(wᵢ·sᵢ) / Σwᵢ po aktywnych kryteriach. Suwak „minimalny wynik": heks poniżej progu znika.

Pytania otwarte: brak danych w heksie (np. cena z za małą liczbą transakcji) traktować jako neutralny, pominąć kryterium, czy wykluczyć heks (O9). Cel osiągalny tylko jednym trybem w danym scenariuszu: jak liczyć (O7).

### 5.6 Interfejs

- Mapa z heksami: kolor = wynik, odrzucone znikają (lub blado).
- Panel: scenariusze, lista celów, suwaki wag, progi twarde, suwak minimalnego wyniku, licznik pozostałych heksów.
- Klik w heks: karta „dlaczego ten wynik" (wkład każdego kryterium, czasy do celów, wartości surowe).
- Stan filtrów w adresie URL (udostępnianie).
- Podpisy: auto = „przybliżenie korków, nie pomiar"; typy czasu z krótkim objaśnieniem P50/P85; zastrzeżenie, że to model.
- PL/EN. Schemat budowy strony, biblioteki mapowe, i18n i deploy: zgodnie z `mapy-analizy` (Claude Code czyta to repo przed startem).

## 6. Dane

| Warstwa | Źródło | Status |
|---|---|---|
| Sieć drogowa | OSM (kopia z modyfikacją `maxspeed` dla auta) | do zrobienia |
| GTFS statyczny, P50, P85 (Łódź) | release'y `GISBoost/easy-GTFS-RT` (tidy + static, tag `lodz-realized-<data>-phone`) | wg stanu repo, do weryfikacji dla wybranych dni |
| GTFS ŁKA | `easy-GTFS-RT`, klucz `lka`, feed statyczny `https://cdn.zbiorkom.live/gtfs/lodz-lka.zip` | **niezweryfikowany**; ryzyko rozszerzonych `route_type` 100–117 (R5 może je po cichu porzucić), obowiązuje sonda routingu i niezmienniki z analizy flagowej |
| Prędkości dla auta | tidy GTFS-RT (odcinki autobusowe, per pora dnia) | metoda w §7.3 |
| Hałas | mapa akustyczna Łodzi, ArcGIS REST (Intersit UMŁ); Claude Code szuka endpointu, w razie porażki Michał podaje link | do rozpoznania, sprawdzić licencję |
| Cena | rejestr cen i wartości nieruchomości | do rozpoznania: dostępność, forma, licencja, dane osobowe |
| Zieleń | OSM lub BDOT10k | wybór w O12 |
| Przystanki, częstotliwość | GTFS (schemat liczenia już w repo) | do zlokalizowania w repo |

Zasada dla ceny: w repo i na stronie nie ma pojedynczych transakcji, tylko agregaty do heksów z liczbą transakcji.

## 7. Pipeline (skrypt wołający wtyczkę easy-R5)

Pipeline jest wznawialny i idempotentny; wyniki per dzień × scenariusz są cache'owane. Wszystkie parametry w `config/*.yaml`.

### 7.1 Wybór dni

Skrypt wybiera 5 ostatnich dni roboczych (bez świąt, ferii, dni anomalnych), dla których Łódź i ŁKA mają komplet: static, P50, P85. Lista trafia do Michała do zatwierdzenia przed liczeniem. Statyka bierze się z tego samego dnia co dane zmierzone.

### 7.2 Macierze O–D

Dla każdego dnia i scenariusza: macierz czasów (heks × heks), w oknie odjazdów wybranej pory dnia. Którego percentyla czasu w oknie używać (O3). Wynik końcowy per scenariusz: mediana po 5 dniach, osobno dla P50 i P85. Przesiadki: maks. 1 przez limit przejazdów TP. ŁKA wył.: filtr trybów (parametr `TRANSIT_SUBMODES` we wtyczce lub osobny feed, do sprawdzenia).

### 7.3 Auto

1. Z danych zrekonstruowanych policzyć prędkość autobusów na odcinkach między przystankami, per pora dnia.
2. Dopasować odcinki do krawędzi OSM.
3. Wygładzić: krawędzie bez danych dostają prędkość podobnych dróg (ta sama klasa) w promieniu, żeby nie powstawały sztuczne objazdy.
4. Zapisać jako `maxspeed` w kopii OSM przed zbudowaniem sieci R5, osobno per pora dnia.

Zastrzeżenia: prędkość autobusu zawiera postoje (zaniża prędkość auta), a tramwaje i buspasy nie reprezentują ruchu ogólnego. Potrzebna korekta lub zakresy graniczne i kontrola na kilku trasach (O8).

### 7.4 Warstwy statyczne

Per heks: odległości pieszo po sieci (przystanki tramwajowe, autobusowe, zieleń), częstotliwość per pora dnia, udziały powierzchni w klasach hałasu (Lden, Ln × drogowy/szynowy/przemysłowy), cena z liczbą transakcji.

## 8. Format danych i budżet rozmiaru

Przybliżony rachunek (do zmierzenia w M0/M4): 29 mln par × 1 bajt (czas w minutach, obcięty do limitu) ≈ 29 MB na scenariusz i kierunek. Przy ok. 54 scenariuszach to ok. 1,6 GB surowo na jeden układ, a potrzebny jest też układ transponowany (kolumny celu). Limit GitHub Pages to 1 GB na stronę.

Do rozważenia przez Claude Code:

- kwantyzacja (np. 2-minutowe przedziały, obcięcie do 90 min),
- kodowanie różnicowe (P85 − rozkładowy mały i dobrze się kompresuje),
- jeden duży plik z odczytem po zakresach bajtów (jak PMTiles) zamiast tysięcy małych,
- hosting dużych plików poza Pages (release'y, Cloudflare R2), jeśli pomiar wyjdzie ponad limit.

Wymagania klienta: wybór celu ładuje jedną kolumnę (ok. 5,4 KB przed kompresją) na aktywny scenariusz; przeliczenie punktacji dla wszystkich heksów w przeglądarce jest natychmiastowe.

## 9. Walidacja i kryteria akceptacji

Niezmienniki pipeline'u (łamanie = błąd, nie ostrzeżenie):

- I1: dodanie ŁKA nie może wydłużyć żadnego czasu; limit „maks. 1 przesiadka" nie może skrócić czasu względem „bez limitu".
- I2: czas zmierzony P85 ≥ P50 ≥ rozkładowy dla zdecydowanej większości par; odsetek naruszeń raportowany.
- I3: sonda routingu na ŁKA potwierdza, że kolej realnie jest w sieci (ochrona przed cichym porzuceniem `route_type` 100–117).
- I4: czasy pieszo w przybliżeniu symetryczne.
- I5: rozrzut czasu między 5 dniami raportowany; dzień odstający oznaczony.

Kontrola ręczna: ok. 10 par O–D porównanych z niezależnym planerem trasy (rząd wielkości, nie dokładność) przez Michała.

Akceptacja MVP:

- wszystkie warstwy poza ceną działają, cena działa lub jest pustym slotem z opisem powodu,
- punktacja i „dlaczego ten wynik" odtwarzalne dla wybranego heksa ręcznym rachunkiem,
- strona PL/EN, stan w URL, podpisy i zastrzeżenia na miejscu,
- rozmiar wdrożenia mieści się w limicie wybranego hostingu,
- README opisuje powtórzenie pipeline'u i wersję metody.

## 10. Ryzyka

| Ryzyko | Skutek | Reakcja |
|---|---|---|
| Rozmiar macierzy ponad limit hostingu | strona się nie wdroży | pomiar w M0, kwantyzacja, hosting poza Pages |
| Feed ŁKA z rozszerzonymi `route_type` | kolej znika po cichu, wynik „ŁKA nic nie daje" | sonda routingu, niezmiennik I3 |
| Czas liczenia (ok. 205 przebiegów) | blokada harmonogramu | pomiar jednego przebiegu, wznawialność, cache |
| Prędkości auta z autobusów | błędne czasy auta | korekta, granice, podpis „przybliżenie", kontrola na trasach |
| Brak lub licencja danych cenowych | brak warstwy ceny | pusty slot, nie blokuje |
| Hałas: brak dostępu do serwisu lub licencja | brak warstwy | link od Michała; zapytanie do UMŁ |
| Dni z feedem niepełnym lub anomalnym | zły dzień zafałszuje wynik | mediana z 5 dni, I5, zatwierdzenie listy dni |
| Odczytanie narzędzia jako rekomendacji zakupu | ryzyko wizerunkowe/prawne | zastrzeżenie na stronie, brak wyceny, brak pojedynczych transakcji |
| Zmiana siatki między wersjami | niezgodność danych | wersjonowanie metody i siatki |

## 11. Otwarte kwestie

Dla Michała:

- **O1** Nazwa i adres podstrony. Siatka rozstrzygnięta: własna heksagonalna 250 m.
- **O2** Licencja kodu i danych wynikowych; zastrzeżenia prawne na stronie.
- **O5** Domyślny kierunek („do celu" / „od celu") dla południa i całego dnia.
- **O6** Rozstrzygnięte: popołudniowy szczyt jako czwarta pora. Do zatwierdzenia same okna po M0.
- **O10** Zachowanie ceny w punktacji: kryterium z wagą (im taniej tym lepiej), czy sama warstwa informacyjna na MVP?
- **O11** Ścieżka lokalna repo `mapy-analizy` (potrzebny dostęp do folderu).

Dla Claude Code (do rozstrzygnięcia w M0 i zaproponowania):

- **O3** Który percentyl czasu podróży w oknie odjazdów zapisywać (mediana? P85 jako osobny wymiar?), by nie mieszać go z wariantami P50/P85 danych zmierzonych.
- **O4** Układ plików: czy wystarczy układ kolumnowy z transpozycją, jaki rozmiar, jaki hosting.
- **O7** Cel nieosiągalny trybem w scenariuszu: wykluczenie heksa czy wynik 0.
- **O8** Korekta prędkości auta na postoje; walidacja na kilku trasach.
- **O9** Brak danych w heksie: neutralnie, pominięcie, wykluczenie.
- **O12** Definicja zieleni (OSM vs BDOT10k, minimalna powierzchnia ok. 1 ha, punkty dostępu do parku zamiast środka).
- **O13** Wartości progów hałasu i klas z mapy akustycznej (zgodne z klasami samej mapy i rozporządzeniem; zweryfikować, nie zakładać).
- **O14** Definicja „częstotliwości": odjazdy/godz. według rozkładu, czy według wariantu zmierzonego; jak łączyć kilka przystanków w zasięgu.
- **O15** Czy ŁKA wył. realizować filtrem trybów, czy osobnym feedem.
- **O16** Czy wtyczka easy-R5 ma tryb bez GUI wystarczający do skryptu; jeśli nie, wariant przez PyQGIS lub r5py.

## 12. Roadmapa (po MVP)

Kolejność orientacyjna, do przeglądu po wdrożeniu MVP.

1. **Usługi codzienne pieszo:** sklep, apteka, przychodnia, szkoła, przedszkole (czas pieszo po sieci, osobne kryteria).
2. ~~Popołudniowy szczyt~~ — wszedł do MVP.
3. **Filtr cenowy** (max zł/m²), rozróżnienie rynku pierwotnego i wtórnego, wyższa jakość agregacji ceny.
4. **Para / rodzina:** osobne cele dla dwóch osób, agregacja „maksimum z czasów" lub suma.
5. **Ryzyka planistyczne:** MPZP, planowane inwestycje (ulice, wieżowce, zakłady).
6. **Jakość powietrza:** GIOŚ ma w Łodzi mało czujników, więc potrzebny dodatkowy model lub źródło; do tego wyspa ciepła i tereny zalewowe.
7. **Gminy ościenne** jako cele i jako obszar kandydatów (Zgierz, Pabianice i in.).
8. **Rower + TP** jako tryb łączony.
9. **Porównanie 2–3 wybranych miejsc**, eksport (PDF/CSV).
10. **Wielkość zieleni** (nie tylko odległość), nasłonecznienie, zabudowa.
11. **Gotowe profile wag** („cisza", „dojazdy", „rodzina z dziećmi").
12. **Inne miasta** (pipeline parametryzowany miastem; krajowe archiwum GTFS-RT obejmuje ok. 26 miast).
13. **Więcej dni obserwacji** i pełne okno sezonowe zamiast 5 dni.
14. **Walidacja gęstszej siatki** (150 m) na całym mieście, jeśli pilotaż pokaże zysk.

## 13. Kamienie milowe

Po każdym kamieniu Claude Code zatrzymuje się, raportuje i czeka na zatwierdzenie Michała.

| M | Zakres | Wyjście |
|---|---|---|
| M0 | Rozpoznanie: przeczytać `mapy-analizy`, dokumenty easy-R5 (analiza flagowa, F2b), instrukcje wtyczki; sprawdzić endpoint hałasu, rejestr cen, feed ŁKA, schemat częstotliwości; zmierzyć rozmiary i czas przebiegu; zaproponować odpowiedzi na O3–O16 | raport + plan, bez ciężkiego liczenia |
| M1 | Siatka i warstwy statyczne: przystanki, częstotliwość, zieleń po sieci | pliki per heks + test na kilku heksach |
| M2 | Hałas: pobranie, agregacja do udziałów powierzchni | warstwa per heks + licencja |
| M3 | Auto: prędkości z autobusów, kopia OSM z `maxspeed` | warstwa prędkości + kontrola na trasach |
| M4 | Pilotaż macierzy: 1 dzień, podzbiór scenariuszy; niezmienniki I1–I5; pomiar rozmiaru i czasu; pilotaż 150 m na fragmencie | raport z liczbami, decyzja o układzie plików |
| M5 | Pełne liczenie: 5 dni × scenariusze, mediana, pakowanie do wybranego układu | dane gotowe do strony |
| M6 | Frontend w `mapy-analizy`: mapa, cele, scenariusze, punktacja, karta heksa, URL, PL/EN | działająca podstrona lokalnie |
| M7 | Cena (lub pusty slot), QA, README, zastrzeżenia, wdrożenie | MVP na żywo po zgodzie Michała |
