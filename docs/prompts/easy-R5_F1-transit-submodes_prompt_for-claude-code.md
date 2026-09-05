# Claude Code prompt — Easy-R5 **F1**: parametr `TRANSIT_SUBMODES`

> Wklej wszystko poniżej linii do Claude Code, w repo `easy-R5`, czysty tree.
> Kod, komentarze, docstringi, stringi UI i commity **po angielsku**; rozmowa po polsku.
> Implementuj **wyłącznie F1**. Nie zaczynaj analizy — to F2/F3. Nowego brancha nie twórz.

---

## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` — **§5** (pełna specyfikacja tego parametru),
  §4.1 (po co jest), §4.6 (niezmienniki, które go zweryfikują w F3).
- `easy_r5/algorithms/_matrix_base.py` — `MODE_OPTIONS`, `_TRANSIT_MODES`, `MODE_MAP`,
  `_add_matrix_params()`, budowa `meta` przy końcu `_run_matrix()`.
- `easy_r5/core/job_spec.py` — `build_matrix_job()`. **Ono już przyjmuje `transit_modes`.**
  Nie zmieniaj jego sygnatury.
- `docs/prd/PR_easy-R5_v01.md` §5.2 — zasada „metoda zapisana w wyniku".
- `easy_r5/test/` — konwencja testów.

## Po co ten kamień istnieje

Analiza flagowa (`docs/prd/PR_easy-R5_flagship-lodz-modal.md`) porównuje dostępność
w sieci tramwajowej, autobusowej i pełnej. Silnik to potrafi — `job_spec` przekazuje dowolną
listę `transit_modes` do runnera — ale **wtyczka nie daje tego wybrać**: `MODE` to sztywny
enum czterech opcji, a `MODE_MAP[0]` wpisuje na stałe wszystkie osiem trybów R5.

To jest też najtańsza możliwa zapowiedź `RunScenarioAnalysis` (T2-E,
`docs/notes/roadmap-candidates.md`): pierwszy parametr, którym użytkownik zmienia *sieć*,
a nie *zapytanie*.

## Co zbudować

Dokładnie to, co opisuje **§5 PRD**. Streszczenie, ale PRD wygrywa przy rozbieżności:

1. Nowy parametr `TRANSIT_SUBMODES` w `MatrixBase._add_matrix_params()`:
   `QgsProcessingParameterEnum(options=_TRANSIT_MODES, allowMultiple=True, optional=True,
   defaultValue=[])`, etykieta `Transit sub-modes (blank = all)`, **bez** `FlagAdvanced`,
   umieszczony bezpośrednio po `MODE`.
2. W `_run_matrix()`: odczytaj wybór (`parameterAsEnums`), zmapuj indeksy na nazwy z
   `_TRANSIT_MODES`, **znormalizuj kolejność** do kolejności `_TRANSIT_MODES` (determinizm
   metadanych), i:
   - pusty wybór → wszystkie tryby (dzisiejsze zachowanie, zero regresji),
   - `MODE != 0` → wybór ignorowany, `transit_modes = []`, jedna linia
     `feedback.pushWarning(...)` w logu,
   - `MODE == 0` → `transit_modes` = wybrana lista.
3. `meta`: nowe pole `transit_submodes` — `"ALL"` albo np. `"TRAM,BUS"`.
4. `mode_label`: `"TRANSIT + WALK"` → `"TRANSIT + WALK (TRAM, BUS)"`, gdy wybór niepusty.
   Sprawdź, gdzie `mode_label` trafia do nazw warstw/plików i czy nawiasy/przecinki nie psują
   nazwy pliku — jeśli psują, w nazwie pliku użyj `_` zamiast `, ` (i napisz o tym w PR).
5. Testy w `easy_r5/test/`:
   - pusty wybór → `job["transit_modes"]` ma 8 elementów w kolejności `_TRANSIT_MODES`,
   - `["BUS", "TRAM"]` → zapisane jako `["TRAM", "BUS"]` (normalizacja),
   - `MODE=WALK` + niepusty wybór → `transit_modes == []`,
   - `meta["transit_submodes"]` poprawne w obu wariantach.
6. i18n: nowe stringi przez `_tr()`/`self.tr()`. **Nie** ruszaj `.ts`/`.qm` — polski przekład
   i tak czeka na ludzki przegląd (KNOWN_ISSUES #1). Dopisz nowe stringi do listy w tym issue,
   jeżeli takie zestawienie tam jest.
7. `README.md`: jedno zdanie przy `Run travel time matrix` i `Run accessibility` o tym, że
   można zawęzić tryby transitu, z przykładem `TRAM` / `BUS`.

## Czego NIE ruszać

- `easy_r5/java/EasyR5Runner.java` — zero zmian.
- Sygnatury `build_matrix_job()`.
- Klucza cache'u sieci — podtryby to parametr **zapytania**, nie **budowy**. Sieć się nie
  przebudowuje.
- Żadnych nowych zależności. `metadata.txt` zostaje `0.1.0`/`experimental=True` — to nie jest
  release.

## Kryteria akceptacji

- [ ] Wszystkie dotychczasowe testy przechodzą **bez modyfikacji**.
- [ ] Cztery nowe testy z listy wyżej — zielone.
- [ ] `flake8` czysto.
- [ ] Wywołanie algorytmu bez dotykania nowego parametru daje **identyczny** `job_spec` jak
      przed zmianą (udowodnij testem porównującym słownik).

## Co musi sprawdzić Michał

Agent nie ma pewności co do zachowania okna dialogowego QGIS-a przy `allowMultiple=True`:

1. Otwórz *Run accessibility* w QGIS 3.40 — czy `Transit sub-modes` renderuje się jako lista
   z checkboxami i czy puste pole jest akceptowane?
2. Zaznacz `TRAM`, uruchom cokolwiek małego — czy w logu jest `transit_submodes=TRAM`, a
   nazwa warstwy wyjściowej zawiera `(TRAM)`?
3. Ustaw `MODE = WALK` i zaznacz `TRAM` — czy leci ostrzeżenie, a wynik jest pieszy?

**Prawdziwa weryfikacja, że R5 respektuje filtr, jest w F3** (niezmiennik I3, PRD §4.6) —
tutaj sprawdzamy tylko, że wtyczka wysyła to, co obiecuje.
