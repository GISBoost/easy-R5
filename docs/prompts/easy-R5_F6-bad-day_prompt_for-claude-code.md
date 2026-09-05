# Claude Code prompt — Easy-R5 **F6**: warstwa „zły dzień" (zrealizowany P85)

> **PARKED (2026-09-05, sesja 2)** w tej wersji — pisany dla trzech trybów (§0 poniżej zakłada
> kolej). Aktywny plan to v1 (dwa tryby). Jeśli F6 ma wejść dla samego tramwaju/autobusu przed
> powrotem kolei, napisać nową, dwutrybową wersję zamiast odpalać tę. Patrz
> `docs/notes/flagship-analysis-decision.md` v3.

> Wklej poniżej linii do Claude Code, w repo `easy-R5`, czysty tree. Kod po angielsku,
> rozmowa po polsku. **F3 musi być zrobione, z zielonymi niezmiennikami.** F4 i F5 mogą, ale nie
> muszą być gotowe. Nowego brancha nie twórz.

---

## Kontekst do wczytania

- `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md` — **§0** (dlaczego ten kamień awansował),
  **§3.4** (dwie sieci), **§8** (miejsce F6).
- `docs/prd/PR_easy-R5_flagship-lodz-modal.md` §4.2, §4.5 — parametry i progi, bez zmian.
- `docs/notes/flagship-analysis-candidates.md` §2C — **pomiar, który uzasadnia ten kamień**:
  w wariancie P85 tramwaje rozjeżdżają się mocniej niż autobusy (mediana +337 s vs +238 s,
  szczyt poranny +318 s vs +200 s), na 1 939 985 wierszy `stop_times`.
- `CONTEXT.md`, hasło **Realized GTFS (P50 / P85)** — czym ten feed jest i czym nie jest.

## Po co ten kamień istnieje

Pierwsza warstwa analizy mówi, **co sieć daje według rozkładu**. Ta mówi, **co z tego zostaje
w złym dniu**. Do niedawna była opcjonalna, bo nagrania GTFS-RT obejmowały tylko ZDiT — a
porównanie, w którym kolej jedzie punktualnie z definicji, a tramwaj i autobus są zdegradowane,
byłoby przechylone na korzyść kolei i nie dałoby się go obronić.

**To już nie jest problem:** ŁKA jest w `easy-GTFS-RT` pod kluczem `lka` i ma własne nagrania
(33 dni, 2026-08-02 → 2026-09-04). Wszystkie trzy tryby degradują się **symetrycznie, z
własnych obserwacji**.

Ten kamień domyka też ograniczenie wymienione wprost w artykule Kaczorowski & Wróblewski (2026):
feedy GTFS „represent planned rather than realised timetables, so they do not capture delays,
cancellations or congestion".

## Co zrobić

### 1. Powtórzyć osiem przebiegów na `network_p85/`

Dokładnie te same przypadki modalne co w F3 (`W, T, B, R, TB, TR, BR, TBR`), dokładnie te same
parametry, ta sama warstwa celów, ta sama data. **Jedyna zmienna to sieć.** Jeżeli zmieni się
cokolwiek innego, porównanie przestaje mierzyć niezawodność.

Skrypt: rozszerzyć `run_modal_cases.py` z F3 o parametr wariantu sieci, nie pisać drugiego.
Wyjścia do `out/p85/acc_<id>.csv`, metadane do `out/p85/run_meta.json`.

### 2. Powtórzyć niezmienniki

`I3`, `I4`, `I5` muszą przejść **także** na sieci P85. `I4` jest tu szczególnie ważny: feed
zrealizowany ŁKA to inny plik niż statyczny i jego `route_type` trzeba sprawdzić osobno.

### 3. Policzyć metryki różnicowe

Dla każdego heksagona, progu, percentyla i kolumny opportunities:

```
impact_i         = (A^m,P85_i - A^m,STATIC_i) / A^m,STATIC_i     dla każdego m
resilience_delta = resilience_i(P85) - resilience_i(STATIC)
```

Plus wersje modalne — **to jest sedno tego kamienia**:

```
tram_share_p85_i - tram_share_static_i
bus_share_p85_i  - bus_share_static_i
rail_share_p85_i - rail_share_static_i
```

Pytanie, na które te trzy liczby odpowiadają: **czy w złym dniu rola tramwaju rośnie, czy
maleje?** Pomiar z `flagship-analysis-candidates.md` §2C sugeruje, że **maleje** — tramwaj
w P85 rozjeżdża się mocniej niż autobus. Jeżeli wyjdzie odwrotnie, to jest sprzeczność
z pomiarem na surowych `stop_times` i **trzeba ją wyjaśnić, a nie wybrać wygodniejszą liczbę.**

### 4. Reguły twarde, przeniesione z F3

- `−100%` to **twarda podłoga**, nie katastrofa. Osiąga ją każdy heksagon, w którym `A^m,P85 = 0`,
  a przy małym mianowniku znaczy „stracił dwa cele", nie „zapaść". **Zawsze czytać razem
  z wartością bezwzględną** — dokładnie ta pomyłka wystąpiła w pilotażu studenckim
  (`tools/accessibility_lodz/STUDENTS_ANALYSIS.md` §3, 43 z 285 heksagonów z −100%).
- `A^m,STATIC = 0` → `impact` jest `NULL`, nie 0 i nie −100%.
- Próg wiarygodności `K` jak w PRD v1 §4.5.

### 5. Produkty

| id | produkt |
|---|---|
| P11 | mapa `impact` dla `A^TBR` (30 min, p50, populacja) — „ile zasięgu znika w złym dniu" |
| P12 | wykres: `tram_share` / `bus_share` / `rail_share` — rozkład vs zrealizowany P85, obok siebie |
| P13 | akapit do `flagship-lodz-modal-results.md` z liczbami |

Kompozycja map jak w PRD v1 §7. **Paleta rozbieżna** (diverging), bo `impact` ma znak — i
uwaga: dodatnie wartości są możliwe (zrealizowany rozkład bywa lokalnie *szybszy* od
planowanego), więc paleta musi być wyśrodkowana na zerze, a nie na medianie.

## Czego NIE ruszać

- `easy_r5/` — zero zmian.
- Wyników z F3 — ten kamień dokłada katalog `out/p85/`, nie nadpisuje `out/`.
- Hero image. P1 zostaje przy rozkładzie.

## Kryteria akceptacji

- [ ] Osiem przebiegów na `network_p85/`, te same parametry co F3 (udowodnij diffem `run_meta.json`
      — jedyna różnica ma być w ścieżce sieci).
- [ ] `I3`, `I4`, `I5` zielone na P85.
- [ ] `impact` ma `NULL` tam, gdzie `A^STATIC = 0`.
- [ ] Kierunek zmiany `tram_share` zgodny z pomiarem na `stop_times` — albo wyjaśniony.
- [ ] Każda liczba w P13 wskazywalna w `out/p85/`.

## Co musi sprawdzić Michał

1. Czy mapa `impact` ma sens przestrzenny — peryferie tracą więcej niż centrum, jak w Metodzie C
   pilotażu (`STUDENTS_ANALYSIS.md` §3, r = −0,28)?
2. Czy różnica `tram_share` między rozkładem a P85 jest w rzędzie wielkości, którego się
   spodziewasz po pomiarze na `stop_times`?
3. Czy gdzieś wyszedł dodatni `impact` na dużej bazie — i czy to jest wiarygodne, czy to artefakt
   rekonstrukcji feedu?
