# Claude Code prompt — Easy-R5 **F5**: opis wyników, README, teksty

> Wklej poniżej linii do Claude Code, w repo `easy-R5`, czysty tree. **F3 i F4 muszą być
> zrobione.** Kod po angielsku; `README.md` po angielsku; notatka wynikowa i teksty do
> publikacji po polsku. Nowego brancha nie twórz.

---

## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` — **§2** (zastrzeżenie interpretacyjne),
  **§4.5** (progi), **§6** (produkty P5–P7), **§9 F5** (kryteria).
- `tools/modal_complementarity_lodz/out/*.csv`, `run_meta.json`, `invariants.json`,
  `poi_control.json` — **jedyne** dopuszczalne źródło liczb.
- `tools/accessibility_lodz/STUDENTS_ANALYSIS.md` §6 — wzorzec sekcji „jak to czytać".
- `tools/accessibility_cities/MULTI_CITY_ANALYSIS.md` §5 — wzorzec sekcji „Ograniczenia".
- Skill `linkedin-post-style` — przed napisaniem posta.

## Po co ten kamień istnieje

Analiza bez uczciwego opisu ograniczeń jest ładnym obrazkiem, a nie wynikiem. Ten projekt ma
już historię wykrytych i naprawionych błędów interpretacyjnych (data sobotnia w 5 miastach,
nieważona metryka „% bez dostępu", odwrócony znak percentyli) — wszystkie znalazły się w
dokumentacji i to jest jego mocna strona. Ten kamień utrzymuje ten standard.

## Co napisać

### P5 — `docs/notes/flagship-lodz-modal-results.md` (PL)

Struktura:

1. **Pytanie i metoda w pięciu zdaniach** — z linkiem do PRD i do Rayaprolu & Levinson 2024.
2. **Dane i parametry** — tabela; data 2026-08-24, 9 893 kursy, siatka 500 m, okno 07:00–09:00,
   percentyle, progi. Wersja R5 i wersja wtyczki z `run_meta.json`.
3. **Weryfikacja, że filtr trybów działa** — `I1`, `I2`, `I3` z konkretnymi liczbami z
   `invariants.json`. To jest najważniejsza sekcja metodyczna i ma być przed wynikami.
4. **Wyniki — poziom**: `Ā^TB(30)`, rozkład przestrzenny, ilu mieszkańców poniżej progu.
5. **Wyniki — zależność modalna**: mediana i rozkład `tram_share` / `bus_share`, gdzie leżą
   korytarze, ilu mieszkańców traci >50% zasięgu bez tramwaju. **Zawsze liczba bezwzględna
   obok procentu.**
6. **Wyniki — komplementarność**: `transfer_premium`, `subadd` miejskie, porównanie kierunku
   efektu z Sydney (Rayaprolu & Levinson: sub-addytywność, korzyść z przesiadki rosnąca z
   progiem — czy w Łodzi tak samo?).
7. **Kontrola na usługach**: czy wniosek trzyma się na `srv_total`, czy tylko na populacji?
   Wynik korelacji POI (`poi_control.json`).
8. **Przekrój 20–29 lat** — jedno-dwa zdania, nie osobny rozdział.
9. **Ograniczenia** — osobna sekcja, wymienia co najmniej:
   - to jest **miara zależności, nie prognoza** (PRD §2) — model nie uruchamia zastępczych,
   - próg `K` i liczba odfiltrowanych heksagonów,
   - heksagon liczy sam siebie,
   - POI zagregowane do centroidów heksagonów (+ wynik kontroli),
   - 18 obwodów bez populacji (supresja GUS),
   - jeden dzień, jedno okno, jeden szczyt — nic o weekendzie i wieczorze,
   - jakość OSM dla warstwy usług,
   - czym są linie `Z1/Z2/P1/P2/R8/O` (odpowiedź z F2).
10. **Co dalej** — link do kandydatów odłożonych w
    `docs/notes/flagship-analysis-candidates.md` (loteria odjazdu, zły dzień P85, sześć miast).

### P6 — blok do `README.md` (EN)

Na samą górę, **przed** tabelą porównawczą easy-OTP / Easy-R5:

- obraz P1 (wersja EN) jako pierwszy element,
- 3–4 zdania: co pokazuje, jakimi algorytmami policzone (`Build R5 network` →
  `Run accessibility` ×4 z różnymi `Transit sub-modes`), **ile to trwało** (z `run_meta.json`),
- link „reproduce this" → `tools/modal_complementarity_lodz/README.md`,
- link do P5.

Nie rozdmuchuj README. Cztery zdania i obraz.

### P7 — `tools/modal_complementarity_lodz/out/text_pl.md`

Wersja pod blog GISBoost + post na LinkedIn (skill `linkedin-post-style`). Nagłówek ma być
konkretną liczbą z analizy, nie ogólnikiem — tak jak
„61% obszaru zamieszkanego przez studentów…". Zastrzeżenie o „to nie jest prognoza" **musi**
być w treści posta, nie tylko w artykule.

### Aktualizacje

- `docs/prompts/README.md` — dopisz wiersze F1–F5 do tabeli ze statusem.
- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` §0 — dodaj sekcję „Stan realizacji" z datami.
- `tools/README.md` — nowy wiersz o `modal_complementarity_lodz/`.
- Jeżeli w trakcie F1–F4 wyszedł jakikolwiek błąd wtyczki: wpis w `KNOWN_ISSUES.md`
  **z numerem GitHub Issue** — polityka z `CLAUDE.md` obowiązuje.

## Reguła twarda

**Każda liczba w każdym z tych tekstów musi mieć pokrycie w pliku w `out/`.** Żadnej liczby
z pamięci, żadnej „około". Jeżeli liczby brakuje — dolicz ją skryptem w F3 i zacommituj
skrypt, nie wpisuj wyniku ręcznie.

## Kryteria akceptacji

- [ ] Każda liczba wskazywalna w `out/`.
- [ ] Sekcja „Ograniczenia" zawiera wszystkie 8 punktów z listy wyżej.
- [ ] Zastrzeżenie z PRD §2 w P5, P6 i P7.
- [ ] README urósł o mniej niż 15 wierszy tekstu (plus obraz).
- [ ] Wszystkie linki działają (sprawdź względne ścieżki).
- [ ] Post na LinkedIn zgodny ze skillem stylu.

## Co musi sprawdzić Michał

1. Czy nagłówek P7 jest liczbą, którą sam chciałbyś kliknąć?
2. Czy sekcja „Ograniczenia" nie przemilcza czegoś, co wiesz o tych danych?
3. Czy blok w README nie przytłacza reszty pliku?
