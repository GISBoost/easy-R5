# Prompt dla agenta — moduł „pokrycie koronami drzew" w aplikacji wyboru mieszkania w Łodzi

Wklej w całości jako pierwszą wiadomość w sesji Claude Code uruchomionej w repo `easy-R5` (pipeline). Frontend leży w lokalnym repo `mapy-analizy` (podstrona aplikacji).

---

## Kontekst

Aplikacja ma już działające MVP: statyczna strona z heksagonami ok. 250 m dla Łodzi, kryteria miękkie z wagami 0–5, wymagania twarde, suwak minimalnego wyniku, karta „dlaczego ten wynik", PL/EN. Specyfikacja i decyzje: `docs/prd/PR_easy-R5_apartment-finder.md`. **PRD opisuje plan, a kod mógł się od niego różnić, więc stan faktyczny ustalasz z kodu, nie z PRD.**

Istniejące kryterium „zieleń" mierzy odległość po sieci do najbliższego terenu zieleni, czyli dostęp do parku. Nie mówi nic o tym, jak zielone jest samo otoczenie domu (drzewa na ulicy, na podwórku, w osiedlu). Ten moduł uzupełnia to o pokrycie koronami drzew.

## Cel

Dodaj do aplikacji **moduł „korony drzew"**: warstwę per heks z udziałem powierzchni pokrytej koronami drzew, policzoną z danych LiDAR, oraz opartą na niej regulowaną wagę w punktacji (opcjonalnie też wymaganie twarde „min. pokrycie"). Moduł ma wejść do istniejącego MVP z minimalną ingerencją w działający kod.

## Metoda referencyjna: film Michała

Punktem wyjścia jest metoda z filmu na kanale Michała: „Jak pobierać dane LiDAR do QGIS. Analiza pokrycia koron drzew strefy wielkomiejskiej w Łodzi" (https://www.youtube.com/watch?v=XdsF-8j7UnY).

- Film znaleziono wyszukiwarką. Jego opisu ani rozdziałów nie udało się odczytać (serwer odrzucił zapytanie), więc **nie wiadomo jeszcze, jakich dokładnie danych, progów i narzędzi używa**.
- Spróbuj odczytać opis i rozdziały filmu. Jeśli strona jest niedostępna, nie obchodź blokady (żadnych mirrorów, cache, skryptów omijających). Poproś Michała o kroki metody albo link do skryptu/repo i do tego czasu stosuj metodę domyślną z poniższej sekcji, oznaczając każde odstępstwo od filmu w raporcie.

## Zakres

### W module

1. **Dane LiDAR dla Łodzi** z zasobów GUGiK (Geoportal), z buforem ok. 400 m wokół granic miasta, żeby heksy brzegowe i bufor sąsiedztwa nie były zaniżone. Do pobierania można użyć wtyczki QGIS „Pobieracz danych GUGiK" albo skorowidzów z Geoportalu. Dla każdego arkusza zapisz rok i projekt pomiaru.
2. **Maska koron drzew** (metoda domyślna, jeśli film nie przesądza inaczej):
   - model wysokości roślinności: NMPT − NMT (lub klasy roślinności z chmury punktów, jeśli to bliższe filmowi),
   - próg wysokości (domyślnie 2 m, w config),
   - wykluczenie budynków (BDOT10k lub klasa budynków w chmurze) oraz obiektów wysokich niebędących drzewami (mosty, estakady, linie, maszty, dźwigi) filtrem klasy lub kształtu,
   - usunięcie plam mniejszych niż minimalna powierzchnia (config).
3. **Agregacja do heksów:** (a) udział powierzchni heksa pokrytej koronami, w [0, 1]; (b) udział w buforze sąsiedztwa heksa (domyślnie ok. 150 m, w config), bo heks 250 m jest mały względem skali, w której odczuwa się zieleń. W M-C0 zaproponuj, czy w punktacji użyć (a), (b), czy ich kombinacji. Heksy brzegowe liczone na części leżącej w granicach miasta.
4. **Kryterium miękkie „Korony drzew":** krzywa rosnąca z nasyceniem, waga 0–5, parametry w `config/*.yaml`. Opcjonalne wymaganie twarde (min. pokrycie). Wartości domyślne zaproponuj z rozkładu pokrycia w Łodzi (percentyle), Michał zatwierdza.
5. **Interfejs:** suwak wagi w panelu, wpis w karcie „dlaczego ten wynik" (wartość w %), opcjonalny podgląd warstwy (kolor heksów = pokrycie), podpis z metodą i rokiem danych. PL/EN, zgodnie z istniejącym i18n.
6. **Metadane i dokumentacja:** źródło, rok pomiaru, wersja metody, licencja. README z opisem powtórzenia kroków. Aktualizacja PRD: dodaj moduł i zaznacz, że pozycja roadmapy „wielkość zieleni" jest w części pokryta.

### Poza zakresem (nie rób, nie zostawiaj martwego kodu)

Inwentaryzacja pojedynczych drzew, gatunki, wysokość i stan drzew, wyspa ciepła, modelowanie cienia lub nasłonecznienia, zmiany w czasie (kilka lat pomiarów), wpływ zieleni na hałas, klasyfikacja z ortofotomapy lub AI, inne miasta, zmiany w liczeniu macierzy R5, przebudowa istniejącego kodu poza niezbędnym minimum, wdrożenie.

## Zanim cokolwiek zbudujesz (kamień M-C0)

1. Przeczytaj PRD i **aktualny kod**: stack, sposób definiowania kryteriów i krzywych, format plików warstw per heks, config, i18n, testy, build. Opisz, jak dodać nowe kryterium przy najmniejszej zmianie. Jeśli kryteria są zaszyte na sztywno i potrzebny jest refaktor, zaproponuj jego zakres zamiast go robić.
2. Spróbuj odczytać film (patrz wyżej) i zestaw jego metodę z metodą domyślną.
3. Rozpoznaj dane: jakie produkty LiDAR GUGiK pokrywają Łódź (NMPT, NMT, chmura punktów), rozdzielczość, układ współrzędnych, rok pomiaru na arkusz, czy są luki lub różne lata w różnych częściach miasta, termin nalotu (sezon bezlistny może zaniżać pokrycie koron liściastych), licencja.
4. Zmierz: rozmiar pobrania, czas przetwarzania i potrzebne miejsce na dysku. Porównaj wariant lekki (rastery NMPT/NMT) z ciężkim (chmura punktów) i zarekomenduj jeden.
5. Pilotaż na jednym arkuszu lub kilku heksach z kontrolą wizualną na ortofotomapie.
6. Zbierz pytania do Michała w jedną listę (patrz „Decyzje do podjęcia").

**Zatrzymaj się po M-C0** z krótkim raportem i planem. Nie pobieraj całości danych, dopóki Michał nie zatwierdzi.

## Dalszy przebieg

- **M-C1:** pełne pobranie i maska koron dla całego miasta (z cache, wznawialnie), raport rozkładu pokrycia.
- **M-C2:** agregacja do heksów, plik warstwy w formacie zgodnym z MVP, test na kilku heksach.
- **M-C3:** kryterium w punktacji, config, testy jednostkowe krzywej.
- **M-C4:** interfejs PL/EN, karta „dlaczego", podgląd warstwy.
- **M-C5:** walidacja, README, aktualizacja PRD.

Po każdym kamieniu krótki raport (co zrobione, jakie liczby, co zawiodło) i zatrzymanie na zatwierdzenie.

## Walidacja (kryteria akceptacji)

- **Maska:** po filtrze praktycznie żaden piksel maski nie leży w obrysie budynku BDOT10k (podaj odsetek). Kontrola wizualna na ortofotomapie dla co najmniej 10 heksów różnych typów: park, osiedle blokowe, śródmieście, zabudowa jednorodzinna, tereny przemysłowe, aleja, las na obrzeżach.
- **Rachunek:** pokrycie ∈ [0, 1]; suma ważona po heksach zgadza się z powierzchnią maski w granicach tolerancji; heksy brzegowe policzone poprawnie.
- **Rozkład:** raport (średnia, percentyle, mapa). Porównaj rząd wielkości z niezależnym źródłem, np. z Krajową Mapą Koron Drzew lub danymi miejskimi, **tylko jako kontrolę**; nie kopiuj z nich danych, a licencję najpierw sprawdź. Różnice wyraźnie większe niż oczekiwane wyjaśnij.
- **Powtarzalność:** ponowne uruchomienie daje identyczny wynik; parametry tylko w config.
- **Punktacja:** wynik jednego heksa policzony ręcznie zgadza się z kartą „dlaczego ten wynik".
- **Brak regresji:** istniejące testy i niezmienniki z PRD §9 przechodzą. Rozmiar wdrożenia rośnie o niewielką wartość (jedna kolumna per heks); podaj liczbę.

## Pułapki merytoryczne, które trzeba uwzględnić

- **Rok pomiaru:** drzewa mogły zostać wycięte lub posadzone po nalocie. Zapisz rok i pokaż go na stronie jako „stan z roku X".
- **Krzewy kontra drzewa:** zależy od progu wysokości; sprawdź wpływ progu (np. 2, 3, 5 m) na rozkład.
- **Korony nad budynkami i jezdniami** wliczają się do pokrycia, jeśli maska obejmuje je z góry. Udokumentuj decyzję.
- **Układy współrzędnych:** zachowaj CRS pipeline'u i siatki; nie mieszaj EPSG:2180 z 2176/2177 bez jawnej transformacji. Sprawdź zgodność układów wysokościowych NMPT i NMT.
- **Różne lata w różnych arkuszach** mogą dawać skoki na granicach arkuszy; sprawdź, czy je widać w warstwie.

## Decyzje do podjęcia (zbierz z Michałem w M-C0)

- **C1:** pokrycie w heksie, w buforze sąsiedztwa, czy kombinacja.
- **C2:** próg wysokości drzewa i minimalna powierzchnia plamy.
- **C3:** czy kryterium ma też wersję twardą („min. pokrycie").
- **C4:** czy dodać podgląd warstwy jako osobną mapę.
- **C5:** czy użyć Krajowej Mapy Koron Drzew jako kontroli (zależy od licencji).
- **C6:** metoda z filmu, jeśli różni się od domyślnej (Michał podaje kroki lub link do skryptu).

## Zasady pracy

- Bez zmyślonych danych. Każda liczba na stronie pochodzi z pipeline'u; atrapy oznaczaj `placeholder: true` i nie wypuszczaj ich do produkcji.
- Parametry (próg wysokości, minimalna plama, promień bufora, krzywa, waga domyślna) w `config/*.yaml`, bez magicznych liczb w kodzie.
- Pipeline wznawialny i idempotentny, z cache i wersją metody w metadanych.
- Licencje źródeł (GUGiK, BDOT10k, ewentualne dane porównawcze) odnotuj w raporcie i README.
- Bez nieodwracalnych działań (usuwanie danych, publikacja, wdrożenie, push) bez zgody Michała w czacie.
- Pytania zadawaj zbiorczo i tylko takie, których nie da się rozstrzygnąć z kodu, PRD lub danych. Jeśli coś w PRD lub w kodzie jest sprzeczne albo błędne, napisz to wprost.

## Warunki zatrzymania

Zatrzymaj się i zapytaj, gdy: pobranie lub miejsce na dysku przekracza rozsądny budżet (podaj liczby); dane nie pokrywają części miasta lub pochodzą z bardzo różnych lat; licencja jest niejasna; maska zawiera budynki mimo filtra; dodanie kryterium wymaga większej przebudowy MVP; metoda z filmu istotnie różni się od domyślnej, a nie masz jej opisu.

## Wynik końcowy

Działający moduł w istniejącej aplikacji (lokalnie): skrypt pipeline'u, config, plik warstwy per heks, kryterium w punktacji, interfejs PL/EN, README, zaktualizowane PRD i krótki raport z liczbami. Wdrożenie dopiero po zgodzie Michała.
