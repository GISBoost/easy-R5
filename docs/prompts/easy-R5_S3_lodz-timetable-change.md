# S3 — Łódź: skutki zmiany rozkładu jazdy z października 2026 (eksperyment przed/po)

Prompt dla Claude Code. Pomysł zgłoszony 2026-10-06. **Wrażliwe na czas:** dane „przed” trzeba zabezpieczyć jako pierwszy krok.

## Cel

Zmierzyć, co zmieniła w Łodzi nowa siatka rozkładu autobusów i tramwajów, wprowadzona wg Michała w poniedziałek 2026-10-05. Trzy warstwy: (1) zmiana oferty na rozkładzie, (2) zmiana zrealizowanej prędkości na odcinkach wspólnych, (3) zmiana luki scheduled↔measured. Dodatkowo odpowiedź na pytanie radnego „gdzie robią się największe zatory”.

## Przeczytaj najpierw

- `claude/transit-speed-index-handoff.md` (odcinki, pasma, W0–W9, zasady twarde), `claude/flagship-analysis-decision.md` (konfiguracja R5 w Łodzi, tryby, dane statyczne i zrealizowane).
- Sprawdź strukturę repo i zaproponuj, gdzie leży kod (propozycja: `analyses/lodz-timetable-change/`). Jeśli nie pasuje, zapytaj.

## Zasady twarde

- Tylko `seg_status == "ok"`, odcinki w poligonie miasta (W0), statyka z tego samego dnia co tidy.
- Nie importuj kodu `easy-OTP` (GPL). Brak magicznych liczb (YAML). Każda liczba z `n` i przedziałem. Wyniki z różnych `method_version` nie są porównywalne.
- Nic nie publikuj, nie wysyłaj radnemu ani do operatora bez zgody Michała. Ranking lub ocena operatorów dopiero po przeglądzie.

## Zakres — część jasna

**Krok 0 (zrób od razu).** Ustal i zabezpiecz dane „przed”: lista dni Łodzi w release'ach `GISBoost/easy-GTFS-RT` (`git ls-remote --tags`), pobranie tidy i statyki dla dni roboczych od połowy września do piątku 2026-10-02 oraz dla dni po zmianie, deduplikacja statyk po SHA-256, zapis sum kontrolnych i listy luk. Sprawdź, czy statyka sprzed zmiany i po zmianie różnią się (hash, `feed_info`, `calendar`, liczba linii/kursów).

**Warstwa 1 — zmiana oferty (rozkład, bez GTFS-RT).** R5 na starym i nowym statycznym GTFS, ta sama data robocza (sprzed i po zmianie), ta sama siatka heksagonów 500 m, te same cele (populacja, usługi). Δ zasięgu 30/45/60 min i Δ service time (minuty obsługi na dobę) per heksagon i per pasmo. Mapa zmian i tabela zbiorcza, z podziałem na zyskujące i tracące obszary.

**Warstwa 2 — zmiana prędkości na odcinkach wspólnych.** Jednostką jest odcinek `from_stop_id>to_stop_id` (albo odcinek fizyczny dopasowany do OSM, jeśli zmieniono przystanki). Porównanie „przed” i „po” tylko na odcinkach obecnych w obu okresach, osobno autobusy i tramwaje, pasma `am_peak`, `midday`, `pm_peak`, `evening`. Dekompozycja shift-share zmiany prędkości sieci (ΣL/ΣT): część „ta sama droga szybciej/wolniej” vs część „zmienił się skład tras”. Przedziały przez bootstrap po dniach. Dni adaptacji (2–3 pierwsze dni po zmianie) raportuj osobno.

**Warstwa 3 — zmierzona dostępność i luka (po ok. 2–3 tygodniach danych „po”).** R5 na zrekonstruowanym GTFS-RT (P50, P85) „przed” i „po”, luka scheduled↔measured per heksagon, czy nowy rozkład ją zmniejszył. Wykonaj dopiero, gdy będzie dość dni; do tego czasu przygotuj skrypty i uruchom na dostępnych danych jako próbę.

**Pytanie radnego.** Przygotuj produkt oparty na danych „po”: mapa najwolniejszych odcinków (W8) i kary szczytu (W3) z liczbą obserwacji i klasą jakości. Opisz w uwadze, że prędkość nie jest czystym wskaźnikiem zatoru (patrz pytanie 3).

## Poza zakresem

Modelowanie przyczyn spowolnienia; ocena zmian w liniach podmiejskich i ŁKA (zasięg: miasto Łódź, autobusy i tramwaje); wycena kosztów operatora.

## Pytania otwarte — zrób research i wróć z odpowiedziami, albo zapytaj Michała o kierunek

1. **Co dokładnie i kiedy się zmieniło.** Zweryfikuj datę wejścia nowego rozkładu i zakres zmian (linie nowe, zlikwidowane, zmienione trasy, zmiany częstotliwości): komunikaty ZDiT/MPK Łódź, porównanie statyk. Czy wszystkie linie dostały nową siatkę, czy część? Potwierdź też, czy nowy rozkład obowiązuje na stałe, czy to wariant przejściowy (np. na czas remontu).
2. **Kontrola sezonowa i zewnętrzna.** Wrzesień vs październik to inny ruch (powrót studentów, pogoda). Które miasta z archiwum nie miały zmiany rozkładu w tym oknie (sprawdź statyki) i nadają się na grupę kontrolną? Zaproponuj różnicę różnic (Łódź minus kontrola) lub wyjaśnij, czemu nie, i oceń, ile dni „przed” i „po” daje sensowne przedziały.
3. **Prędkość a zator.** `seg_time_s` jest przejazd-do-przejazdu (zawiera postój). Nowy rozkład może zmienić punkty regulacyjne i dociskanie do rozkładu, więc spadek prędkości niekoniecznie oznacza gorszy ruch. Zaproponuj, jak oddzielić zator od zmian w obsłudze, i powiedz, na ile dane na to pozwalają. Zapytaj Michała, czy odpowiedź ma w ogóle być sformułowana jako „zatory”.
4. **Stabilność kluczy odcinków.** Przy zmianie siatki klucze `from_stop_id>to_stop_id` mogą się zmienić (identyfikatory przystanków). Sprawdź, jaki odsetek odcinków da się dopasować i czy trzeba dopasować po geometrii.
5. **Wydarzenia zakłócające.** Dni anomalne w oknie (święta, 1 i 2 listopada jeszcze poza oknem, remonty torowisk, wypadki). Wskaż i wyłącz z uzasadnieniem.
6. **Forma wyniku.** Notatka dla radnego, wpis na stronę GISBoost, element A2 doktoratu? Zapytaj Michała po wynikach warstwy 1.
7. **Oczekiwania względem warstwy 3.** Zapytaj Michała, czy ma być częścią doktoratu (luka scheduled↔measured, H1), bo wtedy trzeba przypiąć wersję metody i okno danych.

## Kryteria akceptacji

- Zabezpieczone dane „przed” i „po” z sumami kontrolnymi i listą luk.
- Warstwa 1: mapy Δ zasięgu i Δ service time, tabela zbiorcza, listy największych zysków i strat.
- Warstwa 2: tabela zmiany prędkości na odcinkach wspólnych per tryb i pasmo z przedziałami, dekompozycja shift-share, osobno dni adaptacji.
- Produkt „pytanie radnego” (mapa + tabela) z zastrzeżeniami.
- Nota (≤ 2 strony) z odpowiedziami na pytania otwarte albo jawną listą pytań do Michała. Warstwa 3 jako skrypt gotowy do uruchomienia, gdy będzie dość dni.
