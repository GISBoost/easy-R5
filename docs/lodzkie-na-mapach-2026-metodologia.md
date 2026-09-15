# Łódzkie na mapach 2026 — ustalenia robocze (metoda i dane), stan na 2026-09-13

Notatka z sesji rozeznania w Claude — wskaźnik do wklejenia na start sesji Claude Code,
nie finalna dokumentacja repo.

## Kwalifikowalność
Potwierdzona: absolwent rocznika 2026 → kategoria II (studenci/absolwenci) w konkursie.

## Konkurs — kluczowe fakty regulaminu
- **Termin: 2 listopada 2026, 23:59**, zgłoszenie elektroniczne przez lodzkienamapach.lodzkie.pl
  (hasło: `lodzkienamapach`).
- Narzędzie: ArcGIS **lub QGIS** — easy-R5 (wtyczka QGIS) jest wprost dopuszczalny.
- Zasięg (pkt II.6 regulaminu): *„całego województwa łódzkiego lub jego część"* — mapa samej
  Łodzi jest formalnie dopuszczalna.
- Kryteria oceny (pkt V.1): a) atrakcyjność i oryginalność tematu, b) poprawność danych,
  c) estetyka wykonania, d) zawartość/rozbudowanie tabeli atrybutów, e) własne symbole,
  f) przydatność do publikacji w Geoportalu Województwa Łódzkiego, g) **wielkość obszaru
  objętego opracowaniem**.
- Jedna praca na uczestnika. Zgłoszenie: .zip/.rar z plikami przestrzennej bazy danych,
  projektem QGIS (.qgs/.qgz), wydrukami mapy (pdf/png/jpg/tiff) i załącznikami 1–2
  (oświadczenia — dot. mnie: tylko załącznik 1, jako pełnoletni).

## Decyzja o zasięgu i architekturze mapy

Dwupoziomowa struktura, żeby pogodzić kryterium g) (cały obszar) z tym, że dane o
zrealizowanym rozkładzie (RT) mam tylko dla części województwa:

1. **Warstwa bazowa (całe województwo):** dostępność liczona na statycznym GTFS
   (ŁKA + KKA + Łódź + Kutno + ewentualnie inne potwierdzone feedy) + sieć piesza OSM.
   Spełnia kryterium g).
2. **Warstwa nakładkowa (tylko tam, gdzie jest RT):** delta zrealizowany-vs-statyczny
   (P50/P85 z easy-GTFS-RT) — **poprawka po E1 (2026-09-13), patrz HANDOFF.md §1/§9.3:
   RT jest nagrywane wyłącznie dla Łodzi (ZDiT)**; Kutno i ŁKA mają tylko statyczny GTFS.
   Zamiast delty wojewódzkiej (nieistniejącej poza Łodzią) użyto wzrostu dostępności
   30→60 min jako miary wrażliwości na próg czasu (sekcja 6.6b HANDOFF.md).

**Zastrzeżenie metodologiczne (ważne, zgłoszone przeze mnie):** tam gdzie nie ma danych RT,
nie wolno tego zrównać z `net_delta = 0` na mapie — trzeba osobno, wizualnie oznaczyć „brak
danych o realizacji" (np. zakreskowanie/wyszarzenie + osobna pozycja w legendzie), inaczej
brak danych wygląda jak brak problemu. Dotyczy wprost kryterium b) „poprawność przedstawionych
danych".

## Kategorie POI — rozszerzenie z ~4 do ~15–20

Obecnie w analizach na gisboost.github.io: 4 zagregowane grupy (edukacja/zdrowie/kultura/sklepy
albo szkoły/apteki/uczelnie/centra handlowe), złożone z ok. 7 podtypów OSM.

Proponowany rozkład na kategorie „ludzkie" (tagi OSM w nawiasie), do przycięcia wg realnego
pokrycia danych w województwie:

- **Edukacja:** przedszkola (`amenity=kindergarten`) · szkoły podstawowe / ponadpodstawowe
  (`amenity=school`, różnicowane po `isced:level`) · uczelnie (`amenity=university|college`)
- **Zdrowie:** przychodnie (`amenity=clinic|doctors`) · szpitale (`amenity=hospital`) ·
  apteki (`amenity=pharmacy`)
- **Kultura i rekreacja:** biblioteki (`amenity=library`) · domy kultury
  (`amenity=community_centre`) · kina (`amenity=cinema`) · teatry (`amenity=theatre`) ·
  muzea (`tourism=museum`) · parki (`leisure=park`) · place zabaw (`leisure=playground`) ·
  siłownie/fitness (`leisure=fitness_centre`) · baseny (`leisure=swimming_pool`) ·
  boiska/obiekty sportowe (`leisure=pitch|sports_centre`)
- **Handel i usługi:** supermarkety (`shop=supermarket`) · centra handlowe (`shop=mall`) ·
  targowiska (`amenity=marketplace`) · poczty (`amenity=post_office`) · urzędy gmin
  (`office=government|amenity=townhall`)

**Ostrzeżenie:** kompletność OSM dla kina/siłownia/teatr/basen spada drastycznie poza dużymi
miastami — poza Łodzią i miastami powiatowymi mogą to być białe plamy w OSM, nie w realnej
dostępności. Zaznaczyć jawnie jako ograniczenie danych, nie wynik badania.

## Inwentaryzacja źródeł GTFS w województwie łódzkim

**Potwierdzone (statyczny GTFS):**
- MPK Łódź — portal `otwarte.miasto.lodz.pl`, GTFS + GTFS-RT
- MZK Kutno — `api.zbiorkom.live/api6-open/kutno/gtfs/default` (potwierdzone w Mobility
  Database i Transitland)
- ŁKA pociągi — sanitized feed: `gtfs.kasznia.net/static/sanitized/lka_train.zip`
  (też mkuran.pl, własna strona ŁKA)
- ŁKA/KKA autobusy — `gtfs.kasznia.net/static/sanitized/lka_bus.zip` (aktywnie utrzymywany,
  nieoznaczony jako deprecated — w przeciwieństwie do większości innych przewoźników
  kolejowych w tym katalogu)

**RT (zrealizowany rozkład, nagrywany w easy-GTFS-RT):** ~~tylko Łódź, Kutno, ŁKA~~ —
**poprawka po E1 (2026-09-13): tylko Łódź (ZDiT).** Kutno i ŁKA nigdy nie miały wpisu w
`easy-GTFS-RT/config/cities.json` — to było błędne założenie z tej notatki, nie zweryfikowany
fakt.

**Do sprawdzenia w Claude Code** (brak potwierdzonego GTFS w żadnym sprawdzonym katalogu —
girlc.at, kasznia.net, mkuran.pl, Mobility Database):
- Piotrków Trybunalski (ZDiUM, portal `rozklady.zdium-piotrkow.pl` — sprawdzić, czy ma
  eksport GTFS czy tylko wyszukiwarkę HTML)
- Sieradz (MPK Sieradz)
- Tomaszów Mazowiecki (MZK)
- Zgierz / Pabianice / Głowno (częściowo obsługiwane przez linie łódzkiej aglomeracji —
  sprawdzić, czy istnieje osobny feed)

`files.girlc.at/gtfs` — katalog polskich feedów (siostrzany wobec mkuran.pl i kasznia.net),
prawdopodobnie zawiera więcej pozycji, ale strona ładuje listę plików asynchronicznie
(JS/SPA) — nie dało się jej odczytać prostym fetchem. Do zrobienia lokalnie: DevTools →
Network → filtr Fetch/XHR przy odświeżeniu, znaleźć request zwracający listę (JSON),
odpytać bezpośrednio. Sprawdzić też dane.gov.pl per miasto.

## Otwarte pytania na sesję Claude Code
- Czy Piotrków / Sieradz / Tomaszów Maz. mają GTFS w ogóle (statyczny)?
- Realny listing `files.girlc.at/gtfs` (przez devtools albo curl na znaleziony endpoint)
- Ostateczny wybór ~15–20 kategorii POI wg realnego pokrycia OSM w województwie
  (sprawdzić liczebność przez Overpass per kategoria per powiat, zanim wejdą do finalnej listy)
- Symbolizacja warstwy „brak danych RT" (pod kryterium b regulaminu)
- Struktura tabeli atrybutów pod kryterium d) regulaminu

## Linki
- Regulamin: https://mapy.lodzkie.pl/wp-content/uploads/2026/08/Regulamin_konkurs_LNM2026.pdf
- Strona konkursu: https://mapy.lodzkie.pl/konkurs/
- Zgłoszenia: https://lodzkienamapach.lodzkie.pl (hasło: `lodzkienamapach`)
