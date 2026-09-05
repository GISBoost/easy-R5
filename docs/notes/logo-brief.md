# Logo Easy-R5 — brief projektowy

**Status:** notatka, 2026-09-05. Sprawa drugorzędna wobec analizy flagowej
(`flagship-analysis-candidates.md`), ale logo i hero image mają wyglądać jak jeden zestaw,
więc paleta z §3 jest wejściem dla kartografii (PRD analizy flagowej §7).

---

## 1. Co robią sąsiedzi

Obejrzane bezpośrednio (2026-09-05):

**r5r** — sześciokątny hex sticker w stylu ekosystemu R. Petrolowy błękit, biały wordmark
`R⁵R` (bold, italic, superscript „5"), pod nim schemat sieci transportowej: biały węzeł-hub
w środku, ortogonalne linie rozchodzące się na wszystkie strony, każda zakończona małym
kółkiem-przystankiem, wszystko na tle bladej siatki kwadratów. Mikroskopijny adres repo
wzdłuż dolnej krawędzi. Cienki jasny obrys + zewnętrzny szary kontur heksagonu.

**r5py** — **ta sama grafika**, tylko okrąg zamiast heksagonu i wordmark `R⁵py`. Ten sam
błękit, ten sam schemat sieci, ta sama siatka, ten sam adres repo wzdłuż krawędzi.

**Wniosek, który powinien zaważyć na decyzji.** r5py świadomie zrobił wariant logo r5r, żeby
było widać, że to rodzeństwo w jednym ekosystemie. **Easy-R5 nie jest ich rodzeństwem** —
jest rodzeństwem **easy-OTP**, a wobec r5r/r5py jest niezależnym, innym narzędziem dla innego
użytkownika (`docs/notes/product-scope.md`: „explicitly not the target: someone comfortable
writing r5r or r5py in a notebook").

Zrobienie trzeciej wariacji tej samej naklejki:

- powiedziałoby „to jest binding do R5, jak tamte dwa" — a to nieprawda i README wprost tak
  nie mówi,
- w praktyce sugerowałoby powiązanie z Conveyal / IPEA / r5py, którego nie ma (README ma
  osobne zdanie: *„This plugin is not affiliated with Conveyal"*),
- byłoby najsłabszym z trzech, bo trzecia kopia zawsze jest.

**Rekomendacja: NIE kopiować kompozycji r5r/r5py.** Zapożyczyć można dwie rzeczy i tylko
dwie: **czytelny wordmark z „5"** i **motyw schematu sieci zamiast ikonki pojazdu**. Reszta —
własna. Najważniejsze wejście do projektu to nie r5py, tylko **istniejąca identyfikacja
easy-OTP i GISBoost**: Easy-R5 ma wyglądać jak jej młodszy brat, nie jak cudzy kuzyn.

> **Do rozstrzygnięcia przez Michała przed projektowaniem:** jak wygląda logo easy-OTP i czy
> istnieje jakikolwiek zapisany system marki GISBoost (kolory, krój, kształt kafla na
> miniatury YouTube). Jeżeli tak — to jest nadrzędne wobec wszystkiego poniżej i §3 trzeba
> wyprowadzić z tamtej palety, a nie wymyślać od zera.

## 2. Do czego to logo faktycznie służy

Kolejność ważności, bo ona dyktuje formę:

| # | Zastosowanie | Rozmiar | Konsekwencja |
|---|---|---|---|
| 1 | Ikona wtyczki w QGIS-ie (`easy_r5/resources/`) | **24×24 i 48×48 px** | musi być czytelna jako 24 px sylwetka. To jest twarde ograniczenie i wygrywa ze wszystkim |
| 2 | Miniatura w repozytorium wtyczek QGIS | ~96 px | j.w. |
| 3 | Nagłówek README / strona GitHub | 200–400 px | tu mieści się wordmark |
| 4 | Róg hero image i grafik do posta | 24–48 px wysokości | musi działać obok logo GISBoost |
| 5 | Slajd / miniatura YouTube | duże | wersja pozioma z wordmarkiem |

Z tego wynika **system, nie jeden plik**:

- **mark** — sam znak, kwadratowy, czytelny w 24 px, bez tekstu,
- **lockup poziomy** — znak + „Easy-R5" obok, do README i nagłówków,
- **lockup pionowy** — znak nad tekstem, do naklejek i slajdów,
- **wersja mono** — jednokolorowa czarna i biała, do druku i tła w dowolnym kolorze.

## 3. Kolor

Trzy twarde wymagania:

1. **Nie petrolowy błękit r5r/r5py** (~`#1B87A8`). Nawet dobre logo w tym kolorze zostanie
   odczytane jako wariant tamtych.
2. Musi działać jako **jeden płaski kolor** — QGIS renderuje ikony na jasnym i ciemnym motywie.
3. Musi **współgrać z rampą hero image**, a nie z nią konkurować. Skoro mapa jest sekwencyjna
   i jednobarwna, logo powinno być albo w **tej samej rodzinie** (spójność), albo w kolorze
   **komplementarnym o niskim nasyceniu** (znak nie kradnie uwagi mapie).

Kierunki warte sprawdzenia — wszystkie do przetestowania na kontrast 4,5:1 wobec bieli i wobec
ciemnego motywu QGIS-a, oraz w symulacji deuteranopii i protanopii:

| kierunek | uzasadnienie | ryzyko |
|---|---|---|
| **grafit + jeden akcent** (np. `#1F2429` + ciepły akcent) | najlepiej znosi 24 px, najlepiej wygląda obok mapy w dowolnej rampie, nie starzeje się | mniej „rozpoznawalny z daleka" |
| **głęboka zieleń butelkowa** | daleko od r5py, dobrze kontrastuje z sekwencyjnymi rampami niebieskimi/fioletowymi | zieleń bywa czytana jako „eko", nie „transport" |
| **ciemny fiolet / śliwka** | rzadki w narzędziach GIS, więc zapamiętywalny; dobrze wygląda z żółtym akcentem | trudniejszy w druku mono |

**Czego unikać:** czerwieni (zajęta przez hero image r5py i przez „błąd" w UI), gradientów
(giną w 24 px i psują się w mono), więcej niż dwóch kolorów w marku.

## 4. Motyw — trzy koncepcje

Wspólne założenie: znak ma mówić **„okno czasu na sieci"**, bo to jest to, co odróżnia
Easy-R5 od wszystkiego innego w QGIS-ie (`docs/notes/r5-vs-otp.md`: *„how a network performs
across a time window, at scale"*). Nie „mapa", nie „autobus", nie „pinezka".

**A. Wachlarz percentyli.** Jeden punkt origin, z niego kilka łuków/promieni o rosnącej
długości — wizualizacja tego, że z jednego miejsca o różnych minutach odjazdu dojeżdżasz
różnie daleko. Najbliższe temu, czym wtyczka **jest**. Ryzyko: w 24 px może wyglądać jak
Wi-Fi albo jak wykres kołowy — koniecznie test w małym rozmiarze.

**B. Heksagon z gradientem dostępności.** Siatka kilku heksagonów (3–7), wypełnionych w
odcieniach jednej barwy od ciemnego w środku do jasnego na brzegu. Czyta się natychmiast jako
„dostępność na siatce", świetnie skaluje w dół, i **rymuje się z hero image** (ta sama siatka,
ta sama rampa). Ryzyko: heksagon to najbardziej wyeksploatowany kształt w GIS i w R-owym
ekosystemie — trzeba zrobić coś więcej niż sam heks.

**C. Zegar-sieć.** Okrągła tarcza, w której podziałki godzinowe są jednocześnie liniami
sieci wychodzącymi z centrum. Najmocniejsza metafora („okno odjazdu"), najtrudniejsza
wykonawczo i najbardziej ryzykowna w 24 px.

**Rekomendacja: B jako mark, z elementem A wpisanym w środek**, jeżeli da się to zrobić bez
utraty czytelności w 24 px. B jest bezpieczne i spójne z mapą; A dodaje to, czego nikt inny
nie ma. Zrób oba osobno, zmniejsz do 24 px, wydrukuj — decyzja zapadnie sama.

## 5. Wordmark

- Nazwa pisana **`Easy-R5`** — dokładnie tak, jak w `README.md`, `metadata.txt` i całej
  dokumentacji. Nie `easy-R5`, nie `EasyR5`, nie `easy R5`.
  (`docs/notes/open-questions.md` #4 wciąż formalnie otwarte — jeżeli nazwa się zmieni przed
  wysłaniem do repozytorium wtyczek QGIS, logo idzie do przerobienia, więc **najpierw zamknij
  tę pozycję**.)
- Krój: bezszeryfowy, geometryczny lub neo-grotesk, **nie italic** (r5r/r5py są italic —
  to jest ich znak rozpoznawczy). Kandydaci wolnodostępni: Inter, Source Sans 3, IBM Plex
  Sans, Manrope.
- Bez efektów: bez cienia, bez obrysu, bez gradientu.
- „5" **nie** jako superscript. To u tamtych jest cytatem z „R⁵" (Rapid Realistic Routing on
  Real-world and Reimagined networks) i przepisywanie tego bez powodu jest zapożyczeniem
  cudzej narracji.

## 6. Pliki do wyprodukowania

```
easy_r5/resources/
  icon.svg                 mark, źródło
  icon.png                 24×24 (QGIS Processing)
  icon@2x.png              48×48
docs/img/
  logo-lockup-horizontal.svg + .png (400 px szer.)
  logo-lockup-vertical.svg   + .png
  logo-mono-black.svg
  logo-mono-white.svg
docs/notes/
  logo-brief.md            ten plik
  brand.md                 finalne hexy, kroje, marginesy ochronne, zakazy
```

SVG jako źródło (skalowalne, wersjonowalne, diffowalne). Marginesy ochronne: wolna przestrzeń
wokół marku równa 25% jego wysokości.

## 7. Lista kontrolna przed zatwierdzeniem

- [ ] Zmniejszone do **24×24 px** — nadal rozpoznawalne?
- [ ] W **mono czarnym** i **mono białym** — nadal działa?
- [ ] Na jasnym **i** ciemnym motywie QGIS-a?
- [ ] Obok logo GISBoost — jeden zestaw czy dwie marki?
- [ ] Obok hero image — kolory się wspierają czy biją?
- [ ] W symulacji deuteranopii i protanopii?
- [ ] Wydrukowane w skali szarości na zwykłej drukarce?
- [ ] Czy da się je pomylić z r5r albo r5py? (jeżeli tak — wróć do §1)
- [ ] Nazwa `Easy-R5` zapisana dokładnie jak w `metadata.txt`?
- [ ] Licencja: logo powstaje razem z projektem na GPLv3+; jeżeli użyto jakiegokolwiek kroju
      lub elementu z zewnątrz — licencja odnotowana w `docs/notes/brand.md`.

## 8. Czego nie robić

- Nie używać logotypu, wordmarku ani palety **Conveyal, r5r, r5py, IPEA, ZDiT ani MPK Łódź** —
  ani w logo, ani w hero image. To cudze znaki i README wprost mówi o braku afiliacji.
- Nie wpisywać w logo ikonki tramwaju ani autobusu. Wtyczka nie jest o pojazdach.
- Nie robić logo z mapą Łodzi. Analiza flagowa jest o Łodzi; **wtyczka nie jest**.
