# lodz_timetable_change — S3: jak zmienił się czas dojazdu po zmianie tras z 2026-10-05 (Łódź)

Prompt: [`../../docs/prompts/easy-R5_S3_lodz-timetable-change.md`](../../docs/prompts/easy-R5_S3_lodz-timetable-change.md).
Ramowanie: **eksperyment objazdowy**, nie „nowa siatka”. Wynik komunikacyjny, bez przypinania metody do doktoratu.

## Co liczymy (wersja z 2026-10-06, zastępuje analizę hex→hex na statykach)
Różnicę **czasu dojazdu transportem** z każdego hexa 250 m do **3 najbliższych** obiektów każdej kategorii
(apteki, szkoły, przychodnie, supermarkety), między dwoma poniedziałkami:

* **model dnia** = zrealizowany GTFS P50 z release'u `easy-GTFS-RT` (`lodz_realized_<data>_p50.zip`), czyli rozkład
  poprawiony pomiarem GTFS-RT; osobny model na każdy poniedziałek,
* **„najbliższe”** = najmniejsza odległość w linii prostej, wybrana **raz** (`prepare_poi.py` → `inputs/nearest.csv`),
  te same punkty w każdym modelu; zmienia się tylko czas dojazdu do nich,
* czas = mediana R5 (p50) po odjazdach w oknie pasma, od drzwi do drzwi; pary porównujemy tylko tam, gdzie
  transport jest szybszy niż pójście pieszo **w obu dniach** (bez tras pieszych); drugi wariant („od drzwi do drzwi”)
  jest liczony obok,
* Δ = później − wcześniej, minuty; ujemne = późniejszy poniedziałek jest szybszy.

Przypadki (`config.yaml`): `ctrl` 21.09, `before` 28.09, `after` 5.10. Pary: `main` = 5.10 vs 28.09, `placebo` =
28.09 vs 21.09 (oba przed zmianą: pokazuje, ile różnicy robi sam dzień).

## Kolejność
1. `py -I 00_fetch_freeze.py` — pobranie tidy i statyków z release'ów (surowe dane, poza gitem).
2. `py -I prepare_poi.py` — jednorazowo, lokalnie (potrzebuje `../lodzkie_na_mapach_2026/lodzkie_base.gpkg`);
   wynik w `inputs/` jest w repo.
3. GitHub Actions: `lodz-timetable-change.yml` (workflow_dispatch, `cases=ctrl,before,after`) → `poi_tt.py`.
   `gh run download <id>` do `<data_dir>/poi_tt/` (po jednym katalogu na przypadek + `walk.npz`).
4. `py -I poi_delta.py` → `out/poi_delta/<para>/` (`sentences.txt`, `summary_pairs.csv`, `summary_hex.csv`, `hex.csv`).
5. W QGIS: `exec(open("poi_qgis.py").read())` → mapy hex 250 m (niebieski = krócej, czerwony = dłużej).

## Zastrzeżenia
* Czas to p50 z 5 losowań w oknie odjazdów, w pełnych minutach; „to samo” = ta sama minuta.
* Model = rozkład + pomiar z jednego dnia; różnice między poniedziałkami obejmują też zwykłą zmienność dnia
  (stąd para placebo) i zmiany z końca września/1.10, nie tylko zmianę z 5.10.
* Kategorie POI to wybór roboczy (zmiana w `config.yaml` → `poi.categories`, potem `prepare_poi.py`).
* Release `lodz-realized-2026-10-05-phone` wymaga udanego buildu w `easy-GTFS-RT` (run z 5.10 został anulowany).

## Drugi przebieg: hex 250 m → hex 250 m (2026-10-06)
Pełna macierz 5665 × 5665 na tych samych modelach i parach (`pairs` w `config.yaml`; `alt` = 5.10 vs 21.09 jako drugi
punkt odniesienia obok placebo). Pary hex-hex ważone ludnością początku × ludnością celu, bez pary hex-ten sam hex,
tylko tam, gdzie transport bije pieszo w obu dniach (osobno wariant „od drzwi do drzwi”). Podział po odległości w linii
prostej (`hexmatrix.distance_classes_km`; ostatnia klasa ≥ 10 km = przejazd przez miasto).

1. Workflow `lodz-timetable-change.yml` z `dest=hex` (jeden job na przypadek i pasmo) → `poi_tt.py --dest hex`.
   `gh run download <id>` do `<data_dir>/hex_tt/<przypadek>/<pasmo>.npz` + `walk.npz`.
2. `py -I hex_delta.py` → `out/hex_delta/<para>/` (`sentences.txt`, `summary.csv`, `hex.csv`).
3. W QGIS: `exec(open("hex_qgis.py").read(), {"BAND": "pm_peak"})` — mapa średniej zmiany z danego hexa
   (wszystkie cele / cele ≥ 10 km).
