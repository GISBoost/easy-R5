# Apartment finder — M0 report (2026-10-05)

Status: M0 zamknięte. Bieżący postęp: [`apartment-finder-progress.md`](apartment-finder-progress.md); PRD: `../prd/PR_easy-R5_apartment-finder.md`. Przechodzę do M1 (zgoda Michała w czacie 2026-10-05: oba repo, bez zatrzymań między kamieniami).

## Liczby (zmierzone)
- **Siatka:** własna hex 250 m, środek w granicach miasta: **5662 heksów**, 32,1 mln par O–D. Odstęp środków 250,0 m. (`tools/apartment_finder/scripts/make_grid.py`, `config/grid.yaml`, `hex250-v1`.)
- **Czas R5:** 600 origins → 5662 destynacji, 2 percentyle (P50, P85), okno 120 min, TP+pieszo, `MAX_WALK_TIME=20`: **15,5 s (0,03 s/origin)**. Pełna macierz ≈ **3 min**; 270 przebiegów ≈ 14 h, 480 ≈ 24 h (jeden proces, bez równoległości).
- **Rozmiar:** jeden scenariusz × kierunek, uint8 (minuty, 255 = poza zasięgiem), 32 MB surowo; po zlib ≈ 12,7 MB (próbka: 48% par osiągalnych), po kwantyzacji 2 min ≈ 10 MB. 54 scenariuszy × 1 kierunek ≈ 540–690 MB samym zlib, przed kodowaniem różnicowym. Nie mieści się komfortowo w 1 GB Pages przy dwóch kierunkach; rozstrzyga M4 (różnice, jeden plik z range requests, hosting poza Pages).
- **Dni:** 28.09, 29.09, 30.09, 01.10, 02.10 (Łódź: static+P50+P85 z release'ów `lodz-realized-<d>-phone`; ŁKA: `lka-realized-<d>-tripupdates`, provisional).
- **Sieć testowa:** Łódź static 2026-10-02 + OSM z 2026-08-23: 2410 przystanków, 136 tras, 10 471 kursów w dniu (bramka dnia przeszła). OSM do odświeżenia w M3/M4.

## Rozstrzygnięte w M0
- **O16 (headless):** TAK. `qgis_process` nie ładuje wtyczki (`initGui` wymaga `iface`), ale skrypt na interpreterze QGIS-a (`python-qgis-ltr.bat`) z ręcznie dodanym `EasyR5Provider` woła `processing.run("easyr5:...")` bez GUI. Dwie pułapki, obie w `scripts/_qgis_env.py`: provider musi być trzymany w referencji (inaczej GC i „Error creating algorithm from createInstance()"), oraz trzeba ustawić org/app name QSettings na QGIS/QGIS3, żeby zobaczyć zapisaną Javę.
- **O1:** własna siatka (zrobione). **O6:** popołudniowy szczyt (zrobione).
- **Hałas:** endpoint działa (warstwy imisji LDWN/LN 15–22: droga, tramwaj, kolej, przemysł; `LMIN/LMAX`; geoJSON; 1000 rekordów/zapytanie). Licencja: nieznana — w README i zapytanie do UMŁ (Wydział Ochrony Środowiska).
- **Cena:** brak otwartego API (RCN przez starostwo); pusty slot, Michał poszuka danych.

## Propozycje odpowiedzi (do wglądu, nie blokują)
- **O3:** zapisywać **P50 czasu w oknie** (mediana po minutach odjazdu) jako wartość główną; P85 okna jako osobny, drugi wymiar tylko dla „typ czasu = zmierzony P85 danych", nie mieszać. R5 liczy do 5 percentyli w jednym przebiegu, więc koszt jest zerowy; zapisujemy P50 i P85 okna i decydujemy w M4 po rozmiarze.
- **O4/O5:** jedna macierz na scenariusz; kierunki = kolumna/wiersz celu (PRD §5.2a, poprawiony). Układ plików: oba układy (wierszowy + transponowany) vs. jeden, rozstrzyga rozmiar w M4. Południe i cały dzień: „do celu".
- **O7:** cel nieosiągalny trybem → ten tryb wypada z minimum; jeśli żaden tryb nie dojeżdża, wynik kryterium 0 i oznaczenie „poza zasięgiem" w karcie heksa (heks nie znika, chyba że cel jest twardy).
- **O8:** auto = prędkości z autobusów podniesione o korektę na postoje (odjąć czas postoju z tidy GTFS-RT; granice dolna/górna jako kontrola), walidacja na ~5 trasach vs. niezależny planer.
- **O9:** brak danych: kryterium pomijane dla tego heksa (renormalizacja wag), licznik „n kryteriów bez danych" w karcie.
- **O12:** zieleń z OSM (`leisure=park|garden`, `landuse=forest|recreation_ground`, `natural=wood`), ≥ 1 ha, **punkty wejścia** = przecięcie obrysu z siecią pieszą, nie środek.
- **O13:** klasy z samej mapy akustycznej (przedziały `LMIN/LMAX`) + progi z rozporządzenia (Lden drogowy 68 dB, Ln 59 dB; szynowy 65/56; przemysłowy 55/45 — do weryfikacji w M2, nie zakładać).
- **O14:** częstotliwość = odjazdy/godz. z **rozkładu** (statyczny GTFS dnia) w zasięgu pieszym (np. 400 m po sieci), per pora; dla tramwaju/autobusu osobno, pociąg ŁKA osobno; wariant zmierzony (regularność) poza MVP. Istniejący schemat (`easy-OTP/tools/transit_charts`, headway z tidy GTFS-RT) liczy medianę odstępu per przystanek — używamy tego samego pojęcia, ale z GTFS dnia, bo to nie zależy od nagrań.
- **O15:** ŁKA wył. przez `TRANSIT_SUBMODES` (RAIL) — filtr trybów we wtyczce istnieje; sprawdzić w M4 niezmiennik I1 (ŁKA wł. nigdy nie wydłuża).
- **O10:** pusty slot.

## Ryzyka i uwagi
- ŁKA realized P50/P85 to **1 dzień na dzień** (cienka próbka, pre-release); I3 (sonda routingu) obowiązkowa w M4. ŁKA nie była jeszcze budowana w tej sieci.
- `mapy-analizy` ładuje kafle OSM wprost z `tile.openstreetmap.org` (`opoznienia-dostepnosc/app.js:57`); prompt zabrania hotlinkowania. Dla nowej podstrony użyję kafli z zasadami użycia (np. CARTO/…/własne, licencja do odnotowania) — do decyzji w M6, nie ruszam starych stron.
- 32 mln par jako CSV z R5: ~250 MB/przebieg; pipeline musi od razu pakować do uint8 i kasować CSV.
