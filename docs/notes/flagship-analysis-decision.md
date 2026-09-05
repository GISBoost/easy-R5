# Easy-R5 — analiza flagowa: decyzja i plan (v3, 2026-09-05)
 
Pełne dokumenty leżą w repo `easy-R5`, nie tutaj. Ten plik jest wskaźnikiem dla przyszłych sesji.
 
## Decyzja aktualna (v3): **kolej wyrzucona na razie — wracamy do v1, dwa tryby**
 
**Kierunek:** komplementarność modalna w Łodzi — kontrfaktyczne wyłączanie trybów w R5
(`transitModes`), metodyka wg Rayaprolu & Levinson 2024, *Transit modal complementarity*,
Transportation, doi:10.1007/s11116-024-10555-9 (open access). **Aktywny zakres: `docs/prd/PR_easy-R5_flagship-lodz-modal.md` (v1) — tramwaj i autobus, bez kolei.**

**Dlaczego v2 (kolej ŁKA) jest zdjęta z aktywnego planu, nie skasowana.** Sesja 2026-09-05
sprawdziła feed ŁKA (`docs/notes/lka-gtfs-audit.md`) i znalazła dwa problemy różne od tych,
które przewidywał PRD v2:

1. Klucz `lka` w `easy-GTFS-RT`/`gtfs-dashboard` nagrywał **złą sieć** (autobusy z
   `zbiorkom.live`, nie kolej). Statyczna część jest **naprawialna** — prawdziwa kolej jest
   w `mkuran.pl/gtfs/polish_trains.zip` (24 stacje w Łodzi, 274 kursy kolejowe/dzień na
   2026-08-21). `easy-GTFS-RT/config/cities.json` już poprawione na tę sesję.
2. **Zrealizowana warstwa P50/P85 dla kolei nie da się zbudować bez nowego kodu.** Jedyne
   źródło RT dla ŁKA to `mkuran.pl/gtfs/polish_trains/updates.json` — feed **TripUpdates**
   (bezpośrednie potwierdzone czasy), nie VehiclePositions. `easy-OTP/tools/family_a_reconstruction`
   obsługuje wyłącznie VehiclePositions (poll → map-match → interpolacja) — nie ma ścieżki dla
   TripUpdates. To jest nowy kod w innym repo, poza zakresem, który `easy-GTFS-RT/CLAUDE.md`
   pozwala dotykać bez osobnej, wyraźnej zgody Michała.

**Decyzja Michała 2026-09-05 (sesja 2): nie wchodzimy w TripUpdates teraz.** Kolej wraca jako
osobny temat, kiedy będzie na to czas — PRD v2-rail zostaje w repo jako **Parked**, nie
usunięty (patrz `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md`, nagłówek). Kamienie F2b i
F6 (`docs/prompts/`) są nieaktywne razem z nim.

## Co jest aktywne teraz

Dwa tryby (tramwaj, autobus), metodyka i pytanie badawcze **z PRD v1 bez zmian** — patrz
`docs/prd/PR_easy-R5_flagship-lodz-modal.md` §1. To jest zawężona wersja repliki Rayaprolu &
Levinson (2 z 3 trybów artykułu), nie pełna — pełna wraca z kolejowym rozszerzeniem.

**Hero image:** mapa `tram_share` (ile 30-minutowego zasięgu znika bez tramwaju) — definicja
v1 (`(A^TB − A^B)/A^TB`, świat dwutrybowy), **nie** definicja v2 z pełną siecią. Nie mieszać.
 
**Parametry decyzji Michała:** opportunities = populacja + usługi jako kontrola; zasięg = tylko
miasto Łódź; filtr trybów = parametr `TRANSIT_SUBMODES` we wtyczce (kamień F1).
 
## Most do opublikowanego artykułu
 
Kaczorowski, M. & Wróblewski, W. (2026), *Spatio-temporal and demographic distribution of public
transport accessibility: a GIS-based method using OpenTripPlanner*, **European Spatial Research
and Policy** 33(2). Artykuł mierzy czas obsługi (960 minut okna 06:00–22:00) dla 6 miast i mówi
o szynach cztery rzeczy: bufor 500 m od przystanku tramwajowego/kolejowego → 9,3 h vs 5,1 h
(≈1,8×, opisowo); „accessibility islands" wokół stacji; szyny = korytarze najwyższej
niezawodności czasowej; wniosek, że tramwaj i kolej to fundament ciągłości obsługi, a autobus
jest komplementarny.
 
Analiza flagowa robi to artykułowi w wersji v1 (aktywnej): (1) zamienia korelację buforową na
kontrfaktyk, (2) zamienia rozkład planowany na zrealizowany (P85, kamień F6 — tylko tramwaj i
autobus). Punkt (3) z poprzedniej wersji tego pliku — „rozdziela tramwaj od kolei" — **wraca
razem z kolejowym rozszerzeniem**, nie jest częścią v1: bez trzeciego trybu nie ma czego
rozdzielać, artykułowa kategoria „rail" pozostaje niedotknięta. Artykuł sam wskazuje silnik R5
jako następny krok.
 
## Gdzie co leży w repo
 
| Plik | Co |
|---|---|
| `docs/notes/flagship-analysis-candidates.md` | przegląd kandydatów + §5 rozszerzenie v2 (**parked**) i most do artykułu |
| `docs/prd/PR_easy-R5_flagship-lodz-modal.md` | **PRD v1 (dwa tryby) — aktywny** |
| `docs/prd/PR_easy-R5_flagship-lodz-modal_v2-rail.md` | PRD v2 — **Parked**, patrz nagłówek pliku |
| `docs/prompts/easy-R5_F1-transit-submodes_*.md`, `F2-data-prep_*.md`, `F3-runs-and-metrics_*.md`, `F4-cartography_*.md`, `F5-writeup_*.md` | prompty aktywne, kolejność jak nazwane |
| `docs/prompts/easy-R5_F2b-rail-feed_*.md`, `F6-bad-day_*.md` | **nieaktywne razem z v2** — F2b to feed ŁKA, F6 to warstwa „zły dzień" na trzech trybach |
| `docs/notes/lka-gtfs-audit.md` | audyt feedu ŁKA — dlaczego v2 jest parked, co odblokowuje powrót |
| `docs/notes/logo-brief.md` | brief logo |
 
## Twarde fakty zweryfikowane w sesji
 
- **Data analizy: 2026-08-24 (poniedziałek) — z powrotem do wyboru z PRD v1 §3.1.** v2
  przestawiła datę na 2026-08-21, żeby złapać dzień nagrany przez oba operatory (ZDiT + ŁKA);
  bez kolei ten powód znika, a 2026-08-24 ma przewagę, którą v2 świadomie poświęciła:
  **porównywalność z badaniem 6 miast** (`tools/accessibility_cities/`, audyt z 2026-08-23).
  Jeśli kolej wróci, data znowu stanie się przedmiotem decyzji.
- **ŁKA jest w `easy-GTFS-RT`** pod kluczem `lka` — feed statyczny poprawiony w tej sesji na
  `https://mkuran.pl/gtfs/polish_trains.zip` (poprzednio wskazywał na złą, autobusową sieć —
  patrz `lka-gtfs-audit.md`). Nieistotne dla v1, zapisane dla przyszłego powrotu do kolei.
- Pomiar na `stop_times` (1 939 985 wierszy, static vs P50/P85 dla Łodzi, **tramwaj/autobus,
  nadal aktualne dla v1/F6**): w wariancie P85 tramwaje rozjeżdżają się mocniej niż autobusy —
  mediana +337 s vs +238 s, szczyt poranny +318 s vs +200 s.
- Rozszerzony `route_type` (conveyal/r5#1001), tunel średnicowy i inne fakty specyficzne dla
  kolei przeniesione do `lka-gtfs-audit.md` — nie dotyczą aktywnego zakresu v1.