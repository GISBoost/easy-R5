# lodz_timetable_change — S3: skutki zmiany tras/rozkładu z 2026-10-05 (Łódź)

Prompt: [`../../docs/prompts/easy-R5_S3_lodz-timetable-change.md`](../../docs/prompts/easy-R5_S3_lodz-timetable-change.md).
Ramowanie (decyzja Michała 2026-10-06): **eksperyment objazdowy**, nie „nowa siatka” — 5.10 to zmiana
tras 23 linii (tramwaje wracają na pl. Reymonta, remont przechodzi na pl. Niepodległości) i rozkładów 10 linii.
Wynik komunikacyjny (nota + wpis), bez przypinania metody do doktoratu. Produkt dla radnego: „najwolniejsze
odcinki”, nie „zatory”.

Dane poza gitem: `G:/easy_data/lodz_timetable_change/` (ścieżka w `config.yaml`).

## Kolejność
1. `py -I 00_fetch_freeze.py` — pobranie tidy + statyk z release'ów `easy-GTFS-RT`, SHA-256, manifest, luki.
2. `py -I 01_static_diff.py` — diff statyk (hash, calendar, linie, kursy aktywne w dniu, look-ahead 10 dni).

## Krok 0 — wyniki (2026-10-06, dni do 2026-10-04)
- Łódź: 0 dni bez tagu w 2026-09-01…10-04, 0 brakujących assetów (brak tagu tylko 08-27, poza oknem).
- 13 unikalnych statyków. Warianty ~16 MB (17–20.09 i od 2.10) to feedy z **kilkoma scalonymi wersjami**
  (`feed_info`: 11501_11510_11511; 11519_11521_11522) i ~75 tys. kursów zamiast ~50 tys. — niosą dni z przyszłości.
- **Statyk z 2.10 już zawiera rozkład po 5.10**: od 5.10 linie 17 i 19 dochodzą, Z2 i Z11 znikają (zgodnie
  z komunikatem MPK), dzień roboczy ma 10 207 kursów i 129 linii (vs 10 275 / 128 w 28–30.09 i 10 471 / 129 w 1–2.10).
  Warstwa 1 nie musi czekać na dane „po”.
- Dni robocze „przed”: identyczny zestaw linii i 10 272 kursów w 7–18.09; 21–24.09 128 linii / 10 271 kursów;
  28–30.09 10 275. 25.09 (10 645 kursów) i 1–2.10 (10 471) są wyjątkowe.
