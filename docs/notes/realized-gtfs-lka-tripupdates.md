# Realized GTFS dla ŁKA — przez TripUpdates, nie VehiclePositions (2026-09-09)

Wykonane w tej sesji, poza `easy_r5/`. Odblokowuje częściowo `docs/notes/lka-gtfs-audit.md`
i wątek „kolej" z `docs/notes/flagship-analysis-decision.md`: warstwa zrealizowana dla ŁKA
**da się teraz zbudować** — jest konwerter i wystartowało zbieranie danych.

## Wynik w jednym zdaniu

ŁKA nie ma feedu VehiclePositions, więc pipeline `family_a` jej nie odbuduje — ale krajowy
agregat **TripUpdates** `mkuran.pl/gtfs/polish_trains/updates.pb` (PKP PLK *Otwarte Dane*)
wystarcza w zupełności, a dla dni już przejechanych jest **bliżej empirii** niż typowy feed
TripUpdates, bo PKP oznacza ~99 % przejść jako `confirmed` (rzeczywiste minięcie punktu, nie
prognoza).

## Co zmierzono (snapshot z 2026-09-09 15:25, doba serwisowa 2026-09-08 — kompletna)

| | wartość |
|---|---|
| kursy ŁKA w feedzie (agency `LKA`) | 586 na snapshot (329 za wczoraj kompletnie + 257 za dziś częściowo) |
| dopasowanie do statycznego `polish_trains.zip` po `(trip_id, start_date)` | **329 / 329** (100 %, bez fallbacku) |
| klucz zapasowy | `updates.numbers[0]` == statyczny `plk_train_number` == `trip_short_name` — pewny |
| potwierdzone przejścia przez stację (ŁKA, ta doba) | ~9 370; 51 wierszy bez potwierdzenia (końce tras) |
| opóźnienie vs rozkład (6178 przejść) | mediana **0 s**, średnia **+158 s**, p90 **+7 min**, p99 **+29 min**; pociągi nie jeżdżą przed czasem |
| retencja feedu | **~2 dni** (wczoraj + dziś). Starszego nic nie odzyska — brak archiwum u źródła. |
| stacje „Łódź *" w `polish_trains.zip` | 24 (Fabryczna, Kaliska, Widzew, Chojny, Żabieniec, …) |

Przebieg konwertera na tej dobie: 645 segmentów / 5695 obserwacji, feed P50 — 94,9 %
instancji segmentów skorygowanych, **0 naruszeń monotoniczności**. Rozkład długości kursu
vs rozkład: P50 mediana **−57 s** (rozkład ma zapas), P85 mediana **+274 s** (bufor
niezawodności). Spójne z feedami zrealizowanymi ZDiT.

## Dlaczego to jest inne niż każde inne miasto

Każde inne miasto: VehiclePositions → nagrywanie na telefonie co minutę →
`family_a_reconstruction` (map-matching + interpolacja z pozycji). ŁKA: brak
VehiclePositions w ogóle.

| | reszta miast | ŁKA |
|---|---|---|
| typ feedu RT | VehiclePositions | **TripUpdates** (krajowy agregat kolejowy) |
| skąd czas przystankowy | wywnioskowany z pozycji pojazdu | **raportowany** przez PKP PLK (`confirmed`) |
| nagrywanie | runit, co 60 s, okno 6–22 | **cron raz na dobę** (feed sam niesie całą wczorajszą dobę) |
| silnik | `family_a` (Family A, Wessel 2017) | `gtfsrt_realizer.py` (RT-3 / Family B, Braga 2023) |
| kod | `easy-OTP/tools/family_a_reconstruction/` | `easy-OTP/tools/family_b_realized/` |
| co jest w `.pb` | lat/lon, `current_stop_sequence` | `trip_id` + absolutne `arrival.time`/`departure.time`; `route_id`/`stop_id` **puste** → tryb dopasowania tylko `TRIP_ID` |

Zastrzeżenie do formy `.pb`: nie niesie flagi `confirmed` z `updates.json`. Konwerter
kompensuje to biorąc **tylko doby już przejechane** (dzisiejsze prognozy z tego samego
snapshotu są odrzucane po `start_date`) — dla takiej doby i tak ~99 % przejść jest
`confirmed`.

## Jak to działa end-to-end

```
mkuran.pl/gtfs/polish_trains/updates.pb  (PKP PLK Otwarte Dane, retencja ~2 dni)
        │
        ├─ prymarnie: telefon, cron 03:30 CET
        │     easy-OTP/scripts/termux/fetch_polish_trains_rt.sh   (TX-10)
        └─ backup: GitHub Actions, cron 03:30 UTC
              easy-GTFS-RT/.github/workflows/polish-trains-tripupdates-fetch.yml
        │
        ▼  ta sama nazwa pliku, ten sam release — kto pierwszy, ten wygrywa
   GISBoost/easy-GTFS-RT  release  polish-trains-tripupdates-raw-<YYYY-MM>
        assety:  polish_trains_updates_<doba>.pb.gz   (~1,7 MB/dobę)
        │
        ▼  po uzbieraniu ~15–20 dni roboczych
   easy-OTP/tools/family_b_realized/build_realized.py
        --snapshots <katalog>  --static polish_trains.zip  --agency-id LKA
        --out-prefix lka_realized_<data>
        │
        ▼
   lka_realized_<data>_p50.zip  /  _p85.zip   (kształt jak istniejące feedy zrealizowane)
        │
        ▼
   BuildNetwork w easy-R5  →  analiza modalna F6 / „zły dzień na kolei"
```

## Co to odblokowuje

- **F1–F5** (statyczna analiza modalna z koleją) — już odblokowane przez sam
  `polish_trains.zip` (patrz `lka-gtfs-audit.md`).
- **F6** („zły dzień", trzy tryby z koleją symetrycznie) — **przestaje być zablokowane
  kodem**. Zostaje tylko czas zbierania: ~15–20 dni roboczych od startu crona
  (2026-09-09). Do tego czasu F6 można zrobić tramwaj+autobus jak w v1.
- PRD v2-rail (`docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`) zostaje **Parked**
  jako *analiza* — ale nie z powodu braku warstwy RT.

## Do zrobienia ręcznie (Michał)

1. Wgrać `fetch_polish_trains_rt.sh` na telefon + wpis w cron (patrz
   `easy-OTP/scripts/termux/README.md`, „TX-10").
2. Odpalić raz backup GitHub Actions (`workflow_dispatch`) i sprawdzić, że tworzy
   asset / poprawnie nie-robi-nic gdy telefon już wgrał.
3. Zdecydować, co z runit-serwisem `family-a-record-lka` (dalej nagrywa złą, autobusową
   sieć).
4. Po ~15–20 dniach: `build_realized.py --all` na uzbieranych snapshotach i probka R5
   (`buildnetwork` + `RunTravelTimeMatrix` kolej vs pieszo między stacjami w Łodzi —
   uwaga na `A^rail == A^walk` wszędzie, co znaczyłoby że R5 pominął kolej; `route_type`
   w `polish_trains.zip` to `2`, więc ryzyko conveyal/r5#1001 nie występuje).
