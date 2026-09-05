# Claude Code prompt — Easy-R5 **F4**: kartografia analizy flagowej

> Wklej poniżej linii do Claude Code, w repo `easy-R5`, czysty tree. Kod po angielsku,
> rozmowa po polsku. **F3 musi być zrobione, z zielonymi niezmiennikami.** Implementuj
> wyłącznie F4 — teksty to F5. Nowego brancha nie twórz.

---

## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` — **§6** (produkty) i **§7** (pełna
  specyfikacja kompozycji). §7 wygrywa przy każdej rozbieżności z tym promptem.
- Wzorzec kompozycji: r5py, *„How well does public transport work for slow walkers?"* —
  <https://r5py.readthedocs.io/stable/> (obrazek na stronie głównej). Zapożyczamy
  **gramatykę** (kolumna tekstu + mapa, legenda wpleciona w zdanie, brak podkładu i ozdobników),
  **nie** paletę — r5py jest czerwony, my nie.
- Skill `dataviz` — **wczytaj przed napisaniem pierwszej linii kodu rysującego cokolwiek.**
- `tools/modal_complementarity_lodz/COLUMNS.md` z F3 — co znaczy które pole.
- `easy_r5/styles/accessibility.qml` — konwencja stylu wtyczki.

## Po co ten kamień istnieje

Ten jeden obraz staje na górze `README.md` i jest pierwszą rzeczą, którą widzi ktoś, kto
trafia na Easy-R5. Ma w trzy sekundy powiedzieć: *ta wtyczka odpowiada na pytanie, które cię
obchodzi, w skali miasta, w QGIS-ie.*

Efekt, na którym stoi cała mapa: heksagony o wysokiej zależności od tramwaju **same
narysują sieć tramwajową**, choć nikt jej na mapie nie rysuje. Dlatego linie tramwajowe idą
**tylko do małego insetu**, jako weryfikacja — nigdy na mapę główną.

## Co zbudować

### P1 — hero image

`docs/img/flagship-lodz-tram-share.png`, 1200×720 px (render 2× → 2400×1440), dwie wersje
językowe: `…-pl.png` i `…-en.png`.

Kompozycja **dokładnie wg PRD §7**. Elementy, których nie wolno pominąć:

- legenda **wpleciona w zdanie**, nie osobny prostokąt w rogu,
- osobna, wyraźnie odróżnialna klasa **„brak dostępu transportem w 30 min"** (szary) —
  nie może wyglądać jak najniższa klasa udziału,
- heksagony z `pop_total = 0` przezroczyste,
- **zastrzeżenie z PRD §2** fizycznie na obrazie („to jest miara zależności, nie prognoza —
  model nie uruchamia komunikacji zastępczej"),
- inset ~200×140 px z siecią tramwajową z `shapes.txt`, podpisany,
- mikro-akapit źródeł z datą GTFS, licencją CC BY 4.0 i adresem repo,
- **próg `K` i liczba odfiltrowanych heksagonów** w podpisie (PRD §4.5) — mapa, która ukrywa,
  ile komórek wycięła, jest mapą nieuczciwą.

Czego **nie** ma być: podkładu, siatki współrzędnych, strzałki północy, podziałki, obrysów
heksagonów, czerwieni.

### P2 — premia za przesiadkę

`docs/img/flagship-lodz-transfer-premium.png`. Ta sama kompozycja, inny odcień, klasy
`0 / 0–5 / 5–10 / 10–20 / >20%`, tytuł: *„Gdzie Łódź działa jako jedna sieć, a nie jako dwie?"*

### P3 — wykres podsumowujący

`docs/img/flagship-lodz-modal-bars.png`. Dostępność ważona populacją `Ā^m` dla pięciu
przypadków (`W`, `T`, `B`, `T albo B bez przesiadki`, `TB`) × cztery progi (15/30/45/60).
Na wykresie ma być widać, o ile `TB` przewyższa `max(T, B)` — to jest wizualizacja
komplementarności. Liczba sub-addytywności jako adnotacja.

### Jak rysować

Dwie dopuszczalne drogi, wybierz jedną i uzasadnij w commicie:

- **QGIS Print Layout** przez PyQGIS (`QgsPrintLayout`, `QgsLayoutItemMap`, `QgsLayoutExporter`)
  — skrypt w `tools/modal_complementarity_lodz/make_figures.py`. Zaleta: styl warstwy
  zostaje jako `.qml` i użytkownik odtworzy to samo.
- **QGIS przez MCP** (`mcp__qgis__*`, dostępne wg `CLAUDE.md`) — do iteracji na żywo i do
  zrzutów kontrolnych.

Tak czy inaczej **zapisz `.qml`** dla `tram_share` i `transfer_premium` w
`tools/modal_complementarity_lodz/styles/` — bez tego figura jest nieodtwarzalna.

### Paleta

Wymagania twarde (PRD §7): sekwencyjna, jednobarwna, bezpieczna dla deuteranopii,
monotoniczna jasność, czytelna po konwersji do skali szarości, spójna z paletą z
`docs/notes/logo-brief.md`, i **nie czerwona**. Wybierz konkretne wartości hex, zapisz je w
`styles/palette.md` z uzasadnieniem i z wynikiem sprawdzenia kontrastu.

## Czego NIE ruszać

- `easy_r5/` — zero zmian we wtyczce.
- Danych i metryk z F3 — jeżeli coś na mapie wygląda źle, to może być błąd F3; **zgłoś**,
  nie poprawiaj liczb w skrypcie rysującym.
- Nie pisz tekstu analizy poza tym, co jest fizycznie na obrazach. To F5.

## Kryteria akceptacji

- [ ] P1 czytelny w 100% i po zmniejszeniu do **600 px** szerokości (miniatura na GitHubie).
- [ ] P1 czytelny po konwersji do skali szarości (dołącz zrzut kontrolny).
- [ ] Klasa „brak dostępu" wizualnie nie myli się z najniższą klasą udziału.
- [ ] Zastrzeżenie z §2 obecne na obrazie.
- [ ] Próg `K` i liczba odfiltrowanych heksagonów w podpisie.
- [ ] `.qml` i `palette.md` zapisane; `make_figures.py` odtwarza wszystkie trzy figury od zera.
- [ ] Rozmiar każdego PNG < 1,5 MB (README ma się ładować).

## Co musi sprawdzić Michał

1. **Test korytarza**: czy ciemne heksagony pokrywają się z siecią tramwajową z insetu?
   Jeżeli nie — mapa jest ładna i nieprawdziwa, wracamy do F3.
2. Czy tytuł i pierwsze zdanie da się zrozumieć **bez** czytania reszty?
3. Czy obraz obok logo Easy-R5 (`docs/notes/logo-brief.md`) wygląda jak jeden zestaw, czy jak
   dwie różne marki?
