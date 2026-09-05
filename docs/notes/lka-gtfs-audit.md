# Audyt feedu ŁKA — wynik (2026-09-05)

Wykonane w tej sesji, poza `easy_r5/` (zwykłe `curl`/Python, nie dotyka wtyczki).
Odpowiada na sześć pytań z `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md` §3.3.
Nadpisuje ustalenie „feed niezweryfikowany" w `docs/notes/flagship-analysis-decision.md`.

## Wynik w jednym zdaniu

**Klucz `lka` w `easy-GTFS-RT` / `gtfs-dashboard` (`cdn.zbiorkom.live/gtfs/lodz-lka.zip`) to nie
jest kolej.** To osobna sieć autobusowa (route_type=3 dla 100% z 51 tras), która sięga Łodzi
sześcioma przystankami na obrzeżach i nie ma nic wspólnego z siecią kolejową ŁKA. Prawdziwy
statyczny feed kolejowy istnieje i jest dobry — ale trzeba go wziąć z innego źródła
(`kolej-lka.pl`, oficjalna strona operatora). Warstwa **zrealizowana P50/P85 dla kolei nie
istnieje** — 33 dni nagrań pod kluczem `lka` w `easy-GTFS-RT` nagrywa tę samą złą (autobusową)
sieć.

## Trzy źródła sprawdzone

| Źródło | URL | Co to jest |
|---|---|---|
| `easy-GTFS-RT` klucz `lka` (to, co zakładał PRD v2) | `https://cdn.zbiorkom.live/gtfs/lodz-lka.zip` | **Zła sieć.** 51 tras, route_type=3 (bus) na 100%, nazwy przystanków kończące się na „BUS" (np. `Bedoń BUS`), 446 przystanków — głównie wsie w promieniu ~60 km od Łodzi (Kutno, Skierniewice, Częstochowa, Tomaszów Maz., Opoczno). W bboxie miasta Łodzi: **6 przystanków**, żaden nie odpowiada realnej stacji ŁKA. `feed_publisher`: Marcin Kasznia (`gtfs.kasznia.net`) |
| **`kolej-lka.pl` (oficjalna strona operatora)** | `https://kolej-lka.pl/pliki/pn0e6eg45qcl4hd5/gtfs-2025-2026/zip/` | **Dobra sieć.** 162 trasy: 125 route_type=2 (kolej), 36 route_type=3 (autobusy zastępcze/dowozowe — mieszane w tym samym feedzie, co jest normalne dla operatorów kolejowych). 665 przystanków, 3320 tripów, kalendarz do grudnia 2026. **24 przystanki z prefiksem „Łódź"**, w tym wszystkie znane stacje: Fabryczna, Kaliska, Żabieniec, Chojny, Widzew, Andrzejów, Retkinia, Radogoszcz Wsch./Zach., Olechów (Wiadukt/Wschód/Zachód), Marysin, Arturówek, Stoki, Zarzew, Dąbrowa, Pabianicka, Lublinek, Niciarniana, Warszawska |
| `mkuran.pl/gtfs/polish_trains.zip` (unifikowany feed wszystkich przewoźników PL) | `https://mkuran.pl/gtfs/polish_trains.zip` | Zawiera agencję `LKA` — **potwierdzenie krzyżowe**, że dane z `kolej-lka.pl` to prawdziwa sieć. Zapasowe źródło, gdyby `kolej-lka.pl` przestał działać. `gtfs.kasznia.net` sam ogłasza na stronie głównej, że jego stare feedy kolejowe (w tym „Łódzka Kolej Aglomeracyjna") są **deprecated na rzecz tego unifikowanego feedu** |

## Odpowiedzi na sześć pytań z PRD §3.3 (dla dobrego źródła — `kolej-lka.pl`)

1. **`route_type`** — tylko `2` (kolej) i `3` (bus), zero rozszerzonych kodów 100–117. **Ryzyko
   conveyal/r5#1001 nie występuje w tym feedzie.** (Uwaga: to nie znaczy, że R5 7.6 nie ma tego
   buga ogólnie — po prostu ten konkretny feed go nie uruchamia.)
2. **Stacje w granicach Łodzi** — 24 przystanki z prefiksem „Łódź", pokrywają się z listą znaną
   z PRD §5.5/§10 (w tym Fabryczna jako stacja czołowa, zgodnie z kontekstem tunelu
   średnicowego).
3. **Kalendarz na 2026-08-21** — pokryty. Logika `calendar.txt` + `calendar_dates.txt` (piątek,
   102 aktywne `service_id` po wyjątkach) daje **619 tripów w całej sieci tego dnia: 331 kolej +
   288 bus**. Z tego **274 tripy kolejowe faktycznie dotykają stacji w Łodzi** (i 32 busowe).
   To jest realny wolumen do routingu — nie „garstka rekordów".
4. **Agencje** — jedna: `LKA` (`Łódzka Kolej Aglomeracyjna`). Zero PolRegio/PKP IC w tym
   konkretnym feedzie, więc decyzja „tylko ŁKA" (§5.4 PRD) nie wymaga filtrowania po
   `agency_id` — feed już jest czysty.
5. **Kursy poza obszarem** — tak, większość sieci wykracza daleko poza Łódź (Kutno, Sieradz,
   Radomsko, Tomaszów Maz.). Zgodnie z PRD trzeba przyciąć do bboxa miasto+bufor przy budowie
   sieci (F2b pkt 5) — nieprzycięte, ~3000 tripów dziennie w całej sieci byłoby marnotrawstwem
   budowy.
6. **Liczba kursów na 2026-08-21** — **331 kolejowych** (274 w Łodzi) wobec **9893 ZDiT**. Sama
   ta proporcja (≈1:30) jest wynikiem do zacytowania w tekście — pokazuje skalę oferty
   kolejowej wobec miejskiej *przed* jakimkolwiek routingiem.

## Nowy blocker, którego PRD nie przewidział: warstwa P50/P85 nie istnieje dla kolei

PRD v2 §3.3/§10 zakładał, że jedyne ryzyko to *rozszerzony `route_type` cicho porzucony przez
R5*. Rzeczywisty problem jest inny i głębszy: **`easy-GTFS-RT` nagrywa pod kluczem `lka` złą
sieć** (autobusową z `zbiorkom.live`, nie kolejową z `kolej-lka.pl`). Skutek:

- **Statyczny feed dla F1–F5**: da się zrobić, źródło jest, trzeba tylko zmienić URL względem
  tego, co zakładał PRD (`kolej-lka.pl` zamiast `cdn.zbiorkom.live/gtfs/lodz-lka.zip`).
- **Zrealizowany P50/P85 dla F6**: **niedostępny bez zmiany w `easy-GTFS-RT`**. 33 dni nagrań
  pod kluczem `lka` to nagrania złej sieci — nie da się z nich zrekonstruować „złego dnia" dla
  prawdziwej kolei. Żeby F6 objął kolej symetrycznie (jak zakładał PRD §3.4/§8), ktoś musi
  najpierw dodać do `easy-GTFS-RT/config/cities.json` osobny wpis wskazujący na
  `kolej-lka.pl` i **zacząć nowe nagrywanie od zera** — 15 wspólnych dni roboczych, na które
  liczył PRD, nie istnieje dla prawdziwej kolei i nie da się tego przyspieszyć (dane
  historyczne z przeszłości nie zostały nagrane).

## Rekomendacja (do decyzji Michała)

1. **F1–F5 (statyczna analiza modalna, w tym `TR`, `BR`, `TBR`, `resilience`, `island_index`)
   — odblokowane.** Zmienić w PRD v2 §3.1/§3.4 źródło statycznego feedu ŁKA na `kolej-lka.pl`.
   Żaden z sześciu punktów audytu nie blokuje.
2. **F6 dla kolei — nie odblokowane, i nie da się tego przyspieszyć.** Trzy opcje:
   - (a) zrobić F6 tylko dla tramwaju/autobusu (jak w v1), z jawnym zastrzeżeniem, że kolej
     wchodzi do warstwy „zły dzień" dopiero w przyszłej iteracji, gdy uzbiera się nagrania;
   - (b) dodać `kolej-lka.pl` do `easy-GTFS-RT` teraz i wrócić do F6-dla-kolei za ~3–4 tygodnie
     nagrywania (nowy koszt czasowy, nie techniczny);
   - (c) zrezygnować z symetrii i użyć feedu `zbiorkom.live` P50/P85 jako proxy dla „ile
     zaburzeń doświadcza autobusowa sieć dowozowa do kolei" — inne pytanie niż „zły dzień na
     kolei", do jasnego nazwania, jeśli w ogóle użyte.

Migawki plików (`routes.txt`, `stops.txt`, `agency.txt`, `feed_info.txt`) dla obu feedów
zostały pobrane do scratchpada tej sesji, nie do repo (zgodnie z `.gitignore` — dane, nie kod).
