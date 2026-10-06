# Korony drzew — raport M-C0 (rozpoznanie i pilotaż), 2026-10-06

Spec: [`docs/prompts/easy-R5_tree-canopy-module_prompt.md`](../prompts/easy-R5_tree-canopy-module_prompt.md). Skrypty: `tools/apartment_finder/scripts/canopy_pilot.py`, `canopy_buildings.py`. Dane robocze (poza gitem): `tools/apartment_finder/data/canopy/`.

## Film
Opis i rozdziały filmu są niedostępne (YouTube zwraca tylko stopkę), nie obchodziłem blokady. Metoda wzięta z transkrypcji (`D:\Projekty\Youtube\GISBoost\lidar\Untitled_c.txt`): chmura LAZ GUGiK → `Eksportuj do rastera` po atrybucie `Classification`, filtr klas 3,4,5, piksel 1 m → udział = piksele roślinności / (pole kwadratu − pole budynków) w siatce 100 m. Film sam zaznacza, że to głównie zieleń wysoka, nie trawniki.

## Dane GUGiK (zmierzone)
- Skorowidz: WFS `https://mapy.geoportal.gov.pl/wss/service/PZGIK/DanePomiaroweLidarEVRF2007/WFS/Skorowidze`, warstwa `SkorowidzDanychPomiarowychLIDAR2021`, pole `url_do_pobrania`.
- **Łódź + bufor 400 m (347 km²) jest w całości pokryta jednym projektem: 960 kafli, rok 2021, nalot kwiecień 2021, 25 pkt/m², PL-2000 strefa 6 (EPSG:2177), wysokości EVRF2007.** Brak luk i brak mieszania lat. Nalot wczesnowiosenny (drzewa jeszcze bez liści): korona widoczna jako gałęzie, może zaniżać gęstość liści, ale zasięg koron jest dobrze widoczny.
- Chmura LAZ: kafel 800×500 m, średnio 149 MB (85–316 MB) → **ok. 143 GB** na całe miasto (nie 65 GB, jak szacowałem wcześniej). Szybkość pobierania ok. 5,6 MB/s → ok. 7 h. Klasy: 1 niesklasyfikowane, 2 grunt, 3/4/5 roślinność niska/średnia/wysoka, 6 budynki, 7 szum.
- **Lekki wariant istnieje:** NMPT i NMT 2021, ARC/INFO ASCII GRID 0,5 m, ok. 11,2 MB na kafel każdy → ok. 22 GB razem (6,6× mniej), pobranie ok. 1 h. Skorowidze: `NumerycznyModelPokryciaTerenuEVRF2007` (`SkorowidzNMPT2021`) i `NumerycznyModelTerenuEVRF2007` (`SkorowidzNMT2021`).
- Śródmieście na dysku: 56 kafli LAZ (8,1 GB, strefa wielkomiejska, ok. 22 km², ≈6–7% miasta w buforze).
- Licencja: dane otwarte GUGiK (opendata.geoportal.gov.pl); artykuł o skorowidzach nie podaje warunków, **warunki wykorzystania do potwierdzenia przed publikacją** (README/źródło w M-C5).

## Pilotaż (kafel 6.162.33.03.2, osiedla i park przy al. Włókniarzy; kontrola na RGB z samej chmury, porównanie `data/canopy/t/compare*.png`)
| Maska (piksel 1 m) | udział kafla |
|---|---|
| klasy 3+4+5 (film), ≥1 punkt w komórce | 60% (poza budynkami 49%) |
| klasy 4+5 | 53% (45%) |
| klasa 5 | 48% (42%) |
| **nDSM = NMPT−NMT ≥ 2 m, bez budynków (klasa 6)** | **32%** |
| nDSM ≥ 3 m / ≥ 5 m, bez budynków (klasa 6) | 31% / 28% |
| nDSM ≥ 2 m, bez budynków OSM (nie klasa 6) | 37% |
- Metoda z filmu (klasy 3+4+5) na śródmieściu daje **średnio 44% na heks** (percentyle 5/25/50/75/95: 24/34/44/54/70%; bufor 150 m: 26/35/43/50/62%, korelacja heks vs bufor 0,87; 357 pełnych heksów). To jest **pokrycie roślinnością (z krzewami, trawnikiem, szumem przy budynkach), nie koronami**: klasyfikacja wlicza pojedyncze punkty i 36–44% komórek-budynków (z klasy 6) ma też punkty roślinności przy krawędziach.
- Wizualnie nDSM ≥ 2 m daje wyraźne obrysy koron (aleje, podwórka, park), a maska klas 4+5 jest „rozlana" przy budynkach. IoU nDSM≥2 vs klasa 5: 0,77; vs 4+5: 0,72; vs 3+4+5: 0,66.
- Budynki OSM pokrywają 16,7% kafla, klasa 6 w chmurze 25,5% (IoU 0,62): OSM jest niepełne, więc bez lepszej maski budynków ok. 5 p.p. dachów zostaje w „koronach" (zawyżenie ok. 16%). BDOT10k (wymaganie specyfikacji) powinno być pełniejsze, nie mierzone (jeszcze nie pobrane).

## Rekomendacja
**Wariant lekki: nDSM (NMPT−NMT) ≥ 2 m, 0,5 m → agregacja do 1 m/heksa, minus budynki BDOT10k.** Powody: wyraźnie lepsza maska koron niż klasy 3–5, 6,6× mniej danych (22 GB, ok. 1 h), brak potrzeby rasteryzacji 960 chmur (pilotaż: ok. 35 s na kafel × 960 ≈ 9 h). Jako kontrolę policzymy klasy 4+5 na 1–2 kaflach i pokażemy rozbieżność. Budynki: BDOT10k z GUGiK (pobranie do uzgodnienia), a OSM jako zapas.
Odstępstwo od filmu: film = klasy 3+4+5 (zieleń „ogólna"); rekomendowane = nDSM (korony). Jeśli chcesz dokładnie metodę z filmu, to wariant ciężki (143 GB, 7 h pobierania, ok. 9 h rasteryzacji) lub tylko filtr klas 4+5.

## Decyzje do Michała
1. **Metoda:** nDSM≥2 m z NMPT/NMT (rekomendowane, lekka) czy dokładnie klasy 3+4+5 z LAZ (jak film, ciężka)? Próg wysokości 2/3/5 m (C2): proponuję 3 m dla „drzewa" (mniej krzewów), 2 m jako wariant.
2. **Budynki:** pobrać BDOT10k (budynki, powiat Łódź) czy użyć OSM z naszego PBF (niepełne, zawyża o ok. 16%)? Rekomendacja: BDOT10k.
3. **Wskaźnik (C1):** heks + bufor 150 m, korelacja 0,87, więc bufor wygładza, ale niewiele zmienia; do rozstrzygnięcia po pełnym mieście.
4. Wersja twarda „min. pokrycie" (C3), podgląd warstwy (C4), KMKD jako kontrola (C5, licencja niesprawdzona).

## Czego nie zrobiono / zastrzeżenia
Nie pobierano reszty miasta (czeka na zgodę). Brak kontroli na ortofotomapie GUGiK, a RGB z chmury (stan z nalotu 2021). Pilotaż nDSM tylko na jednym kaflu; rozkład dla całego miasta dopiero w M-C1. Liczba punktów w rastrach `count` PDAL wyszła wyższa niż liczba punktów pliku, więc używam wyłącznie obecności (≥1), nie liczności.

## M-C1/M-C2 (2026-10-06): pełne miasto, metoda NMPT−NMT (decyzja Michała)
- Pipeline (system Python, wznawialny, parametry w `config/canopy.yaml`, wersja `canopy-v1`): `canopy_tiles.py` (960 kafli NMPT+NMT 2021 → kody wysokości 0,5 m; 33 min, 87 MB wyników, ASC kasowane po każdym kaflu) → `canopy_mask.py` (próg 3 m, minus BDOT10k: budynki, zbiorniki, wieże, urządzenia techniczne, obiekty sportowe z buforem 1 m, mosty 3 m, maszty 2–3 m; otwarcie 1 m usuwa słupy/latarnie/druty; plamy < 10 m² odpadają; 100 s) → `canopy_hex.py` (QGIS, udział w heksie i w heksie + bufor 150 m).
- BDOT10k: `1061_GPKG.zip` (schemat 2021, powiat Łódź, 37,7 MB) z opendata.geoportal.gov.pl; budynków BUBD_A: 97 517.
- Walidacja na kaflu pilotażowym: pokrycie 30,9%; 99% pikseli korony ma w chmurze punkty klasy 5 (wysoka roślinność), tylko 5,8% leży w komórkach klasy 6 (budynki); IoU z klasą 5: 0,63 (0,70 poza komórkami budynków). Bez BDOT (tylko OSM) wskaźnik wynosił ok. 37%.
- Wynik miasta (5662 heksów, wszystkie pokryte danymi w 100%): średnia 27,8%, mediana 21,5%, percentyle 5/25/75/95 = 1,9/12,5/35,0/86,0%, max 99,7%; bufor 150 m: średnia 27,8%, mediana 22,8%; korelacja heks–bufor 0,93. 552 heksów < 5%, 1149 > 40% (lasy i parki na obrzeżach).
- Mianownik = cała powierzchnia heksa (budynki i drogi w mianowniku, jak „tree canopy cover"), inaczej niż w filmie (tam pole minus budynki).
- Do zrobienia: kontrola wizualna (Michał, QGIS), wpięcie kolumn do `layers.json` i kryterium (M-C3/M-C4), README i PRD (M-C5). Znane ograniczenia: korona nad dachem w buforze 1 m od budynku przepada (lekkie niedoszacowanie), szerokie wiaty spoza BDOT10k mogą zostać w masce, nalot kwiecień 2021 (stan sprzed 5 lat).

## canopy-v2 (2026-10-06, po uwagach Michała z kontroli wiaduktów)
- Wiadukty (BDOT10k ma je tylko jako linie osi) zostawiały pasy krawędzi z barierkami. Dodano filtr gładkości (`smooth` w `config/canopy.yaml`): gładkie (odchylenie NMPT w oknie 2,5 m ≤ 0,12 m), wysokie (≥ 3 m) płaty ≥ 30 m² to konstrukcje (jezdnie wiaduktów, płaskie dachy), wycinane z poszerzeniem 2,5 m (krawędzie). Test na kaflu 6.163.33.17.2: wiadukt B −85% pikseli korony, A −31%, korony obok bez zmian; mapa KMKD (mapadrzew.com) nie pokazuje koron na wiadukcie w punkcie A.
- Bufor 150 m usunięty (korelacja z heksem 0,93, brak wpływu); w pipeline'ie zostaje tylko `canopy_hex`.
- Etap 1 zapisuje teraz 2 pasma (kod wysokości, chropowatość w cm); wynik maski w `data/canopy/final_v2/`.
- Wynik (5662 heksów, pokrycie danymi 100%): średnia 27,5%, mediana 21,3%, percentyle 5/25/75/95: 1,8/12,3/34,8/86,0%; 583 heksy < 5%, 1139 > 40%. Filtr gładkości zdejmuje średnio 1,7% kandydatów na kafel, BDOT10k 17,7%.
