# Prompt startowy dla Claude Code — wybór lokalizacji mieszkania w Łodzi

Wklej w całości jako pierwszą wiadomość w sesji Claude Code uruchomionej w repo `easy-R5`.

---

## Cel

Zbuduj publiczną, statyczną aplikację w przeglądarce, która pomaga wybrać miejsce zakupu mieszkania w Łodzi. Użytkownik ustawia wymagania (do 5 celów dojazdu, odległości do przystanków, zieleń, hałas, cena), a mapa heksagonów pokazuje tylko miejsca spełniające wymagania, kolorowane wynikiem. Wyróżnik: czasy dojazdu transportem publicznym liczone z rozkładu oraz ze zrekonstruowanego GTFS-RT (warianty P50 i P85), czyli obraz zbliżony do rzeczywistego, także w gorszy dzień.

Pełna specyfikacja: `docs/prd/PR_easy-R5_apartment-finder.md`. **Przeczytaj ją najpierw w całości.** To jest źródło prawdy dla zakresu, decyzji (§4), modelu punktacji (§5), pipeline'u (§7), walidacji (§9) i otwartych kwestii (§11). Ten prompt mówi, jak pracować, nie powtarza PRD.

## Zakres zadania

W MVP: siatka heksagonalna ok. 250 m dla miasta Łódź, cele dowolne klikane na mapie, scenariusze (pora dnia × rozkładowy/P50/P85 × limit przesiadek × ŁKA wł./wył.), tryby pieszo/rower/auto/TP, kryteria z PRD §5.4, punktacja trzywarstwowa, interfejs PL/EN jako podstrona w repo `mapy-analizy`.

Poza MVP (nie rób, nie zaczynaj, nie zostawiaj martwego kodu): usługi codzienne, MPZP, jakość powietrza, gminy ościenne, filtr cenowy, tryb pary, rower + TP, inne miasta. Lista jest w PRD §12; jeśli widzisz, że coś z niej da się przy okazji tanio przygotować (np. config parametryzowany miastem), zaproponuj to w raporcie zamiast robić.

## Zanim cokolwiek zbudujesz (kamień M0)

1. Przeczytaj PRD.
2. Przeczytaj repo `mapy-analizy` (lokalnie; ścieżkę poda Michał, jeśli nie znajdziesz jej w sąsiednich folderach): stack, schemat strony, mapa, i18n, build, deploy, sposób hostowania danych. Nowa podstrona ma pasować do tego schematu.
3. Przeczytaj dokumenty easy-R5: `docs/notes/flagship-analysis-candidates.md`, `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`, prompty `docs/prompts/easy-R5_F2b_*` i `F3`. Znajdziesz tam rozpoznanie feedu ŁKA, ryzyko rozszerzonych `route_type` (100–117) i niezmienniki. Znajdź też istniejący schemat liczenia częstotliwości kursowania.
4. Użyj instrukcji do wtyczki easy-R5 i MCP QGIS, które Michał już skonfigurował. Sprawdź, czy wtyczka ma tryb bez GUI wystarczający do skryptu (O16).
5. Rozpoznaj dane: endpoint ArcGIS REST mapy akustycznej Łodzi (Intersit UMŁ), dostępność i licencję rejestru cen, dni z kompletem danych dla Łodzi i ŁKA (static, P50, P85).
6. Zmierz: liczbę heksów, rozmiar jednej macierzy, czas jednego przebiegu R5, szacunek całości (ok. 205 przebiegów) i rozmiar danych po kwantyzacji względem limitu hostingu.
7. Zaproponuj odpowiedzi na otwarte kwestie O3–O16 z PRD §11, a pytania do Michała (O1, O2, O5, O6, O10, O11) zbierz w jedną listę.

**Zatrzymaj się po M0.** Wynik to krótki raport (liczby, wybory, ryzyka, pytania) i plan M1–M7. Nie zaczynaj ciężkiego liczenia ani frontendu, dopóki Michał nie zatwierdzi.

## Dalszy przebieg

Kamienie M1–M7 z PRD §13. Po każdym: krótki raport (co zrobione, jakie liczby, co zawiodło, co dalej) i zatrzymanie na zatwierdzenie. Pracuj na jednym dniu i podzbiorze scenariuszy, zanim puścisz pełne liczenie.

## Zasady pracy

- **Bez zmyślonych danych.** Każda liczba na stronie pochodzi z pipeline'u. Przykłady i atrapy oznaczaj `placeholder: true` i nie wypuszczaj ich do wersji produkcyjnej.
- **Parametry w `config/*.yaml`**: progi hałasu, krzywe kryteriów, okna czasowe, lista dni, promienie wygładzania. Bez magicznych liczb w kodzie.
- **Pipeline wznawialny i idempotentny**, cache per dzień × scenariusz, wersja metody w metadanych wyników.
- **Niezmienniki I1–I5 (PRD §9)** to testy: ich złamanie zatrzymuje pracę i trafia do raportu. Zwróć szczególną uwagę na sondę routingu ŁKA (kolej mogła zostać po cichu odrzucona).
- **Nazewnictwo:** czasy z GTFS-RT w interfejsie to „zmierzony (rekonstrukcja GTFS-RT)", nie „rzeczywisty". Auto: „przybliżenie korków, nie pomiar".
- **Dane z ceną:** nie umieszczaj w repo ani na stronie pojedynczych transakcji, tylko agregaty do heksów z liczbą transakcji. Jeśli dane nie są dostępne lub licencja nie pozwala, zostaw pusty slot z opisem powodu; to nie blokuje MVP.
- **Licencje źródeł** (mapa akustyczna, rejestr cen, OSM, BDOT10k, kafle podkładowe) odnotuj w raporcie i w README. Nie hotlinkuj kafli OSM.
- **Daty i dni:** wybierz 5 ostatnich dni roboczych bez świąt i dni anomalnych z kompletem danych, ale listę pokaż Michałowi przed liczeniem. Statyka z tego samego dnia co dane zmierzone.
- **Bez nieodwracalnych działań** (usuwanie danych, publikacja, wdrożenie, push) bez zgody Michała w czacie.
- **Pytania zadawaj zbiorczo**, nie pojedynczo, i tylko takie, których nie da się rozstrzygnąć z repo lub PRD. Jeśli PRD jest z czymś sprzeczne albo coś jest błędne, napisz to wprost zamiast cicho obchodzić.

## Warunki zatrzymania i eskalacji

Zatrzymaj się i zapytaj, gdy: rozmiar danych po kwantyzacji przekracza limit hostingu; feed ŁKA nie przechodzi sondy routingu; endpoint hałasu jest niedostępny; wtyczka nie wystarcza do pipeline'u headless; czas całego liczenia przekracza rozsądny budżet; niezmiennik I1 lub I3 jest złamany.

## Wynik końcowy

Działająca podstrona w `mapy-analizy` (lokalnie), dane i pipeline w `easy-R5`, README z opisem powtórzenia pipeline'u i wersją metody, aktualizacja PRD o podjęte decyzje. Wdrożenie dopiero po zgodzie Michała.
