# S1 — Tramwaj: torowisko wydzielone vs w jezdni wspólnej z samochodami

Prompt dla Claude Code. Pomysł zgłoszony 2026-10-04. Dotyczy ogólnie GTFS/GTFS-RT (dane z `easy-GTFS-RT`), nie wymaga R5.

## Cel

Zmierzyć na **zrealizowanych** danych (rekonstrukcja GTFS-RT), czy odcinki tramwajowe prowadzone w jezdni współdzielonej z ruchem samochodowym mają większe opóźnienia i większą zmienność czasu przejazdu niż odcinki z torowiskiem wydzielonym. Pilotaż: Łódź. Wynik: tabela, mapa odcinków i krótka nota z metodą i wnioskami, z przedziałami niepewności.

Hipoteza Michała: w jezdni współdzielonej opóźnienia są większe. Wygląda na oczywistą, ale nie wiadomo, czy ktoś ją skwantyfikował. To jest powód badania, nie jego wynik: wynik ma wyjść z danych.

## Przeczytaj najpierw

- Dokumenty projektu: `claude/transit-speed-index-handoff.md` (definicje W0–W9, pasma, kolumny tidy, zasady twarde), `claude/flagship-analysis-decision.md`.
- Dane: release'y `GISBoost/easy-GTFS-RT`, tag `<miasto>-realized-<data>-phone`, załączniki `<miasto>_tidy_<data>.csv.gz` i `<miasto>_static_gtfs_<data>.zip`. Statykę bierz z tego samego dnia co tidy.
- Zanim cokolwiek zbudujesz, sprawdź strukturę repo i zaproponuj, gdzie leży kod (propozycja: `analyses/tram-row/`) i notatki (`docs/notes/`). Jeśli struktura nie pasuje, zapytaj.

## Zasady twarde

- Tylko `seg_status == "ok"`, tylko odcinki z obydwoma przystankami w poligonie miasta (W0), tylko tramwaje (`route_type` 0 lub 900–999).
- Nie importuj kodu `easy-OTP` (GPL-3.0-or-later); czytaj tylko dane.
- Żadnych zmyślonych danych i magicznych liczb: progi do pliku konfiguracyjnego YAML. Każda liczba z `n` i statusem jakości.
- Nic nie publikuj ani nie wysyłaj bez zgody Michała.

## Zakres — część jasna (rób bez dopytywania)

1. **Warstwa klasyfikacji odcinków.** Dla każdego odcinka tramwajowego `from_stop_id>to_stop_id` wytnij geometrię z polilinii `shape` między dwoma `shape_dist_m` i nadaj klasę torowiska: `wydzielone`, `w_jezdni`, `mieszane` (część i część), `nieznane`. Źródło wejściowe: OSM (sprawdź, jak w Łodzi są faktycznie otagowane torowiska tramwajowe i czy da się odróżnić torowisko wydzielone od zabudowanego w jezdni; nie zakładaj z góry nazw tagów). Zapisz regułę klasyfikacji w konfiguracji.
2. **Walidacja klasyfikacji.** Wylosuj próbkę ok. 30 odcinków (stratyfikowaną po klasie), zweryfikuj ręcznie na ortofotomapie lub zdjęciach ulicy, podaj zgodność (accuracy per klasa). Jeśli klasyfikacja jest słaba, powiedz to wprost i nie idź dalej na słabej warstwie.
3. **Metryki na odcinek** (osobno pasma dnia z projektu indeksu: `am_peak`, `midday`, `pm_peak`, `evening`, i `all_day`): mediana i P85 prędkości, rozrzut czasu przejazdu (np. P85/P50 i współczynnik zmienności), kara szczytu (W3), udział przejazdów wolniejszych niż rozkład (W6).
4. **Porównanie klas.** Różnica między klasami z kontrolą czynników zakłócających: długość odcinka, liczba skrzyżowań z sygnalizacją na odcinku (z OSM), obecność przystanku, pasmo dnia. Preferowane: porównanie stratyfikowane i model z efektami losowymi po odcinku, wynik z przedziałem ufności (bootstrap po dniach).
5. **Wyniki:** tabela zbiorcza, mapa odcinków (kolor = klasa, osobno wartość metryki), nota metodyczna z ograniczeniami.

## Poza zakresem

Opis wpływu tramwaju na ruch samochodowy; modelowanie sygnalizacji i priorytetu TSP; inne miasta (dopiero po pilotażu w Łodzi); autobusy.

## Pytania otwarte — zrób research i wróć z odpowiedziami, albo zapytaj Michała o kierunek

1. **Czy luka naprawdę istnieje?** Zweryfikuj w pełnych tekstach (nie we fragmentach): praca o tramwaju w Zagrzebiu (Applied Sciences 2024, doi:10.3390/app142411599), Currie & Shalaby 2007 (niezawodność tramwajów na torowiskach współdzielonych, Melbourne/Toronto), Aemmer, Ranjbari & MacKenzie (GTFS-RT, opóźnienia systematyczne i losowe, Public Transport), praca z Drezna (arXiv 2607.07152), polskie źródła (Poznań, Gdańsk, Wrocław, Warszawa). Szukaj też prac AVL z Melbourne. Zwróć listę z oceną: co dokładnie kwantyfikują i czy robią to na zrealizowanych danych odcinek po odcinku. Poprzedni research był krótki i oparty na fragmentach.
2. **Definicja „opóźnienia”.** Względem rozkładu, względem czasu swobodnego (jak go wyznaczyć: np. niski kwantyl z godzin pozaszczytowych?) czy absolutna prędkość i zmienność? Uwaga: rozkład w niektórych miastach już uwzględnia wolniejsze czasy w jezdni, więc opóźnienie względem rozkładu może ukryć efekt. Zaproponuj definicję z uzasadnieniem i zapytaj Michała, jeśli kilka jest równie sensownych.
3. **Lepsze źródło niż OSM?** Sprawdź, czy BDOT10k lub dane ZDiT/MPK Łódź mają informację o torowiskach wydzielonych. Oceń dostępność i licencję.
4. **Konfundowanie.** Torowiska w jezdni są częściej w centrum (więcej skrzyżowań, większy ruch). Zaproponuj, jak oddzielić efekt klasy torowiska od efektu lokalizacji, i powiedz, czy dane wystarczą.
5. **Forma wyniku.** Samodzielna nota/artykuł, odcinek serii GISBoost czy część indeksu prędkości? Zapytaj Michała po pierwszych liczbach.

## Kryteria akceptacji

- Warstwa klasyfikacji z raportem walidacji (accuracy per klasa).
- Tabela metryk per klasa i pasmo, z `n` i przedziałami.
- Mapa i krótka nota (≤ 2 strony) z wynikiem, ograniczeniami i odpowiedziami na pytania otwarte (albo jawną listą pytań do Michała).
- Skrypty powtarzalne po `git clone`, bez ręcznych kroków poza walidacją próbki.
