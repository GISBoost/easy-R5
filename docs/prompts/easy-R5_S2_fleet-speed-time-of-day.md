# S2 — Prędkość floty i dostępność: szczyt vs poza szczytem (pora dnia)

Prompt dla Claude Code. Pomysł zgłoszony 2026-10-04. Łączy dane z `easy-GTFS-RT` (prędkość floty) z R5 (dostępność).

## Cel

Zmierzyć, jak bardzo zrealizowana prędkość floty różni się między porami dnia i **co to znaczy dla dostępności**: o ile zmienia się zasięg 30/45/60 min w szczycie względem pory poza szczytem, osobno na rozkładzie i na rekonstrukcji (measured). Pilotaż: Łódź.

## Przeczytaj najpierw

- `claude/transit-speed-index-handoff.md` (pasma, metryki W1–W9, kolumny tidy, zasady twarde), `claude/flagship-analysis-decision.md` (konfiguracja R5 w Łodzi, `RunAccessibility`, wyniki na rozkładzie i na wariantach P50/P85), `claude/side-research-ideas-ars-inputs.md` (pomysł „peak asymmetry”).
- Pamięć projektu: notatki `peak-asymmetry-lodz` i `transit-speed-index` (pomysły pokrewne, patrz pytanie 1).
- Sprawdź strukturę repo i zaproponuj, gdzie leży kod (propozycja: `analyses/fleet-speed-tod/`). Jeśli nie pasuje, zapytaj.

## Zasady twarde

- Tylko `seg_status == "ok"`, odcinki w poligonie miasta (W0), statyka z tego samego dnia co tidy.
- Pasma (czas lokalny): `am_peak` 7–8, `midday` 10–13, `pm_peak` 15–17, `evening` 19–21 (godziny 6, 9, 14, 18 tylko w `all_day`). Nie zmieniaj ich bez zgody.
- Nie importuj kodu `easy-OTP` (GPL). Brak magicznych liczb (YAML). Każda liczba z `n`. Wyniki z różnych `method_version` nie są porównywalne. Nic nie publikuj bez zgody Michała.

## Zakres — część jasna

1. **Profil prędkości floty.** Dla Łodzi, dni robocze bez świąt, osobno autobusy i tramwaje: prędkość komunikacyjna `3,6·ΣL/ΣT` na godzinę doby i na pasmo, z przedziałem (bootstrap po dniach). Dodatkowo kara szczytu (W3) na tych samych odcinkach (ten sam odcinek, szczyt vs pozaszczyt), żeby oddzielić efekt „inne odcinki w szczycie” od „ten sam odcinek wolniej”.
2. **Dostępność per pasmo.** R5 (`RunAccessibility`) na tej samej sieci i tej samej siatce heksagonów 500 m, osobno dla okna odjazdu każdego pasma, dla trzech wariantów feedu: statyczny, P50, P85 (dla dnia, który ma wszystkie trzy w repo, np. 2026-08-21). Progi 30/45/60 min. Cele: populacja (jak w analizie flagowej), usługi jako kontrola.
3. **Dekompozycja zmiany dostępności** szczyt vs poza szczytem: część wynikająca z częstotliwości (zmiana na rozkładzie) i część wynikająca z prędkości (różnica measured vs scheduled). Wynik: mapa Δ zasięgu per pasmo oraz tabela zbiorcza miasta.
4. **Wyniki:** wykres profilu godzinowego, mapy Δ, tabela, nota metodyczna z ograniczeniami.

## Poza zakresem

Inne miasta (po pilotażu); modelowanie przyczyn spowolnienia (zatory, dwell); ocena skutków konkretnej zmiany rozkładu (to S3).

## Pytania otwarte — zrób research i wróć z odpowiedziami, albo zapytaj Michała o kierunek

1. **Czy to osobny pomysł?** Pokrywa się z „asymetrią szczytów AM/PM” (`peak-asymmetry-lodz`) i z kolumną W3 w indeksie prędkości. Przeczytaj oba, zaproponuj, czy robić jedną pracę, dwie, czy S2 jako wspólny fundament. Zapytaj Michała.
2. **Czy luka istnieje?** Zweryfikuj w pełnych tekstach: Transit Costs Project „Mapping the Speed of Surface Transit” (rozkłady, 32 miasta), przegląd rozkładów czasu przejazdu autobusów (Frontiers in Built Environment 2020), algorytm WATT dla dynamicznej dostępności (PLOS ONE 2017), Wessel & Farber 2019, Liu, Porr & Miller 2022, praca o składowych czasu podróży i fizyce szczytu (Transportation Research Part A, 2023). Dodaj polskie prace. Poprzedni research był krótki i oparty na fragmentach.
3. **Czy rozkład w ogóle widzi efekt szczytu?** W Szczecinie, wg jednego fragmentu, czasy międzyprzystankowe w rozkładzie są takie same cały dzień. Sprawdź to na statycznym GTFS Łodzi (czasy między przystankami per pasmo). Jeśli rozkład jest płaski w ciągu dnia, wariant scheduled nie pokaże efektu prędkości, tylko częstotliwość; wtedy opisz to jako wynik, nie błąd.
4. **Definicja „dostępności w szczycie”.** Okno odjazdu równe pasmu czy punktowa godzina, jaki percentyl (mediana, P85)? Zaproponuj z uzasadnieniem, zapytaj, jeśli kilka wariantów jest równie sensownych.
5. **Rozdzielenie prędkości od częstotliwości** w R5 bez dodatkowej mocy obliczeniowej: czy wystarczą trzy warianty feedu, czy potrzebny jest kontrfaktyczny feed „rozkład z prędkościami z pasma X”? Ocenij koszt i zaproponuj.
6. **Ile dni.** Jeden dzień jest pilotażem; ile dni potrzeba, żeby przedziały były wiarygodne? Policz na danych Łodzi.

## Kryteria akceptacji

- Profil prędkości (wykres + tabela, per tryb i pasmo, z `n` i przedziałami).
- Mapy Δ zasięgu per pasmo i tabela zbiorcza dla wariantów static/P50/P85.
- Dekompozycja częstotliwość vs prędkość z komentarzem o ograniczeniach.
- Nota (≤ 2 strony) z odpowiedziami na pytania otwarte albo jawną listą pytań do Michała.
