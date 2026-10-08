# Heks bez dojazdu autem (punkty dostępu do sieci) — analiza i naprawa

Data: 2026-10-08. Zgłoszenie Michała: po wybraniu dwóch celów w centrum miasta aplikacja pokazywała, że dojazd samochodem jest niemożliwy.

## Odtworzenie
1. Cel w heksie **2237** (51,7758 N, 19,4546 E: Piotrkowska przy Placu Wolności) z trybem „samochód" (pora dowolna): `morning_car`/`midday_car`/`afternoon_car` mają w wierszu i kolumnie tego heksa **5661 z 5662 par bez dojazdu**. Wszystkie inne heksy dojeżdżają do wszystkiego (0,14% par nieosiągalnych w całej macierzy).
2. Identycznie heksy **1084** (51,7400; 19,3978), **1574** (51,7467; 19,4229) i **1509** (51,7456; 19,4198): 5660–5661 par. Razem 4 heksy, te same w trzech porach.
3. Test w R5 (sieć auta `car_morning`, origin = środek heksa 2237 i punkty co 50–400 m w czterech kierunkach): środek, 50 m N, 50 m W i 100 m N nie mają żadnej trasy, punkty 50 m S/E i dalsze dojeżdżają do celów w 10–35 min.

Skrypt diagnostyczny użyty do odtworzenia był jednorazowy; po naprawie to samo pokazuje `scripts/access_points.py`.

## Przyczyna
R5 przypina punkt (środek heksa) do **najbliższej krawędzi dozwolonej dla trybu**. Środek heksa 2237 leży 3 m od podwórkowych dróg dojazdowych (`highway=service`, `service=driveway`), a sąsiednia Piotrkowska to deptak (`access=no`).
Te podwórkowe drogi tworzą **odciętą wyspę** (nie łączą się z siecią dla aut), więc origin i cel przypięte do wyspy nie mają żadnych tras. Podobnie 1084 (podwórka `service` 7 m od środka), 1574 (najbliższe drogi samochodowe to wyspa/ślepy fragment)
i 1509 (jezdnia jednokierunkowa al. Waltera-Janke i łącznik `secondary_link`). To nie jest błąd frontendu ani eksportu: dane po stronie macierzy są puste.
Ten sam mechanizm działa dla pozostałych trybów: 6 heksów pieszo (745, 1152, 2906, 5322, 5375, 5376) i 3 rowerem (2906, 5375, 5376) były wyspami; te same piesze wyspy są też nieosiągalne w komunikacji miejskiej.

## Naprawa
- `scripts/access_points.py` (+ `config/access.yaml`): wykrywa heksy-wyspy w macierzach jednorazowych (osiągają ≤ 1 inny heks jako origin lub cel), testuje w R5 kandydatów na pierścieniach 25–300 m wokół środka (12 kierunków) względem 405 punktów kontrolnych i wybiera najbliższy punkt, który dojeżdża tak jak typowy heks (≥ 50% typowego zasięgu). Wynik: `data/access_points.csv`.
- `scripts/run_matrices.py`: dla walk/bike/car używa punktów dostępu zamiast środka heksa (zarówno dla origins, jak i destinations); liczba użytych punktów trafia do `*.json` scenariusza (`access_points`).
- `scripts/aggregate.py`: nowy test I6 (raport wysp dla walk/bike/car w `i5_report.json`); wyspa w macierzy auta przerywa agregację z instrukcją naprawy; `aggregate.py <scenariusz...>` agreguje wskazane scenariusze.
- `scripts/test_access_points.py`: sprawdzenie wykrywania wysp.
Przesunięcia: auto 25 / 50 / 75 / 100 m (2237 / 1509 / 1084 / 1574), pieszo 745 → 75 m, 1152 → 150 m, 2906 → 50 m, rowerem 2906 → 50 m, 5375 → 150 m, 5376 → 75 m. **Bez dobrego kandydata w 300 m (zostają, pieszo):** 5322, 5375, 5376 (skraj wschodni, 541,5 tys. E).

## Ograniczenia
- Komunikacja miejska ma te same piesze wyspy (745, 1152, 5322, 5375, 5376, 2906). Macierze TP liczone są w GH Actions (15 jobów); naprawa wymaga ich ponownego przebiegu z punktami dostępu dla trybu pieszego. Nie zrobione.
- Dodatkowych 11 heksów nie dociera w TP do więcej niż jednego innego (brak przystanków w limicie marszu 20 min lub brzeg miasta): wymaga osobnej analizy, nie ma dowodu, że to wyspy.
- Punkt dostępu leży do 100 m od środka heksa (auto): czas dojazdu różni się o ok. minutę od liczonego ze środka.
