<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1">
<context>
    <name>BuildNetwork</name>
    <message>
        <location filename="../algorithms/build_network.py" line="54"/>
        <source>Build R5 network</source>
        <translation>Zbuduj sieć R5</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="57"/>
        <source>Setup</source>
        <translation>Konfiguracja</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="66"/>
        <source>Builds an R5 network.dat from one OSM .pbf extract and every .zip GTFS feed in a folder, and writes a network.json summary that includes service_days (active trip count per date, 90-day window).

The result is cached under CACHE_FOLDER/&lt;hash&gt;/ keyed by the input file contents and the pinned R5 version; an unchanged re-run returns at once. FORCE_REBUILD ignores the cache.

Building can take minutes on a large PBF. Run &apos;Download R5 engine and Java 21&apos; first.</source>
        <translation>Buduje plik network.dat z jednego wyciągu OSM .pbf oraz każdego strumienia GTFS w folderze i zapisuje podsumowanie network.json, które zawiera service_days (aktywna liczba kursów na datę, okno 90-dniowe).

Wynik jest buforowany w CACHE_FOLDER/&lt;hash&gt;/ z kluczem opartym na zawartości plików wejściowych i przypisanej wersji R5; ponowne uruchomienie bez zmian zwraca wynik natychmiast. FORCE_REBUILD ignoruje pamięć podręczną.

Budowanie może trwać kilka minut dla dużego PBF. Najpierw uruchom 'Pobierz silnik R5 i Java 21'.</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="78"/>
        <source>OSM extract (.osm.pbf)</source>
        <translation>Wycinek OSM (.osm.pbf)</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="86"/>
        <source>Folder of GTFS feeds (every .zip inside is used)</source>
        <translation>Folder z feedami GTFS (każdy plik .zip wewnątrz jest używany)</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="93"/>
        <source>Network cache folder (blank = plugin default)</source>
        <translation>Folder pamięci podręcznej sieci (puste = domyślne dla wtyczki)</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="101"/>
        <source>Force rebuild (ignore the cache)</source>
        <translation>Wymuś przebudowę (ignoruj pamięć podręczną)</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="108"/>
        <source>network.dat path</source>
        <translation>ścieżka network.dat</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="109"/>
        <source>network.json path</source>
        <translation>ścieżka network.json</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="118"/>
        <source>OSM file not found: {}</source>
        <translation>Plik OSM nie znaleziony: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="121"/>
        <source>No .zip GTFS feeds in folder: {}</source>
        <translation>Brak pliku .zip z danymi GTFS w folderze: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="135"/>
        <source>Cache hit: {} — inputs and R5 version unchanged, skipping build.</source>
        <translation>Wpływ do pamięci podręcznej: {} — wejścia i wersja R5 niezmienione, pomijanie budowania.</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="160"/>
        <source>Building the network — this can take a few minutes…</source>
        <translation>Budowanie sieci — może to zająć kilka minut…</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="167"/>
        <source>Network build cancelled by user.</source>
        <translation>Budowanie sieci anulowane przez użytkownika.</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="176"/>
        <source>Computing service_days from the GTFS calendar…</source>
        <translation>Obliczanie service_days z kalendarza GTFS…</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="201"/>
        <source>Network summary:</source>
        <translation>Podsumowanie sieci:</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="217"/>
        <source>  served dates: {} .. {} — {} of {} days in the window have trips.</source>
        <translation>  daty z kursami: {} .. {} — {} z {} dni w oknie ma kursy.</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="221"/>
        <source>  This feed has NO active service anywhere in the {}-day window — every date would produce walk-only results. Check the GTFS release.</source>
        <translation>Ten strumień nie ma żadnej aktywnej usługi w oknie {}-dniowym — każda data wygeneruje wyniki tylko dla pieszych. Sprawdź wydanie GTFS.</translation>
    </message>
</context>
<context>
    <name>DownloadR5</name>
    <message>
        <location filename="../algorithms/download_r5.py" line="61"/>
        <source>Download R5 engine and Java 21</source>
        <translation>Pobierz silnik R5 i Javę 21</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="64"/>
        <source>Setup</source>
        <translation>Konfiguracja</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="73"/>
        <source>Downloads a portable Eclipse Temurin 21 JDK (x64) from the Adoptium API and r5-v7.6-all.jar from the Conveyal GitHub release, verifies both (SHA-256), saves their paths under the easy_r5/ QSettings keys, and compiles the one-file Java runner to &lt;target&gt;/runner_cache/.

First run downloads ~240 MB (JDK ~180 MB + jar ~62 MB). No administrator rights are needed. These are NOT shared with easy-OTP — that plugin uses Java 8.

Supported platforms: Windows / Linux / macOS x64. On Apple Silicon or ARM Linux, install Temurin 21 manually from https://adoptium.net/temurin/releases/?version=21 and point TestR5Setup at it.

Re-running on the same folder detects existing files and exits in seconds.</source>
        <translation>Pobiera przenośny JDK Temurin 21 (x64) z API Adoptium oraz plik r5-v7.6-all.jar z wydania Conveyal na GitHub, weryfikuje oba (SHA-256), zapisuje ich ścieżki pod kluczami QSettings easy_r5 i kompiluje jednolity runner Java do &lt;target&gt;/runner_cache/.

Pierwsze uruchomienie pobiera około 240 MB (JDK ~180 MB + jar ~62 MB). Nie są wymagane uprawnienia administratora. NIE są one współdzielone z easy-OTP — ten wtyczka używa Javy 8.

Obsługiwane platformy: Windows / Linux / macOS x64. Na Apple Silicon lub ARM Linux, zainstaluj Temurin 21 ręcznie ze strony https://adoptium.net/temurin/releases/?version=21 i wskaż do niego TestR5Setup.

Ponowne uruchomienie w tym samym folderze wykrywa istniejące pliki i kończy działanie w kilka sekund.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="90"/>
        <source>Destination folder for the JDK and R5 jar</source>
        <translation>Folder docelowy dla pliku JAR JDK i R5</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="98"/>
        <source>Download the Temurin 21 JDK</source>
        <translation>Pobierz Temurin 21 JDK</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="103"/>
        <source>Download r5-v7.6-all.jar</source>
        <translation>Pobierz r5-v7.6-all.jar</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="108"/>
        <source>Platform override</source>
        <translation>Nadpisanie platformy</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="117"/>
        <source>JDK java binary path</source>
        <translation>Ścieżka binarna JDK Java</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="118"/>
        <source>JDK version</source>
        <translation>Wersja JDK</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="119"/>
        <source>R5 jar path</source>
        <translation>Ścieżka pliku R5</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="120"/>
        <source>Runner mode</source>
        <translation>Tryb uruchamiania</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="139"/>
        <source>Target platform: {} x64</source>
        <translation>Platforma docelowa: {} x64</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="149"/>
        <source>&apos;Download the Temurin 21 JDK&apos; is off and no JDK path is saved. Enable it, or run this once with it enabled.</source>
        <translation>Pobieranie Temurin 21 JDK jest wyłączone i nie zapisano ścieżki do JDK. Włącz je lub uruchom to raz z włączonymi.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="155"/>
        <source>Using saved JDK: {}</source>
        <translation>Użyj zapisanej JDK: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="158"/>
        <source>Cancelled after the JDK phase. The JDK path is saved — run the algorithm again to fetch the R5 jar.</source>
        <translation>Anulowano po fazie JDK. Ścieżka JDK została zapisana — uruchom algorytm ponownie, aby pobrać plik JAR R5.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="171"/>
        <source>&apos;Download r5-v7.6-all.jar&apos; is off and no jar path is saved.</source>
        <translation>Pobieranie r5-v7.6-all.jar jest wyłączone i nie zapisano ścieżki do pliku jar.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="175"/>
        <source>Using saved R5 jar: {}</source>
        <translation>Używając zapisanej biblioteki R5: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="182"/>
        <source>Compiling the Java runner…</source>
        <translation>Kompilowanie uruchamiacza Java…</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="191"/>
        <source>Runner compiled to {}</source>
        <translation>Uruchomiono do {}</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="193"/>
        <source>Pre-compilation unavailable; the runner will be compiled on each run (~1 s overhead). Reason: {}</source>
        <translation>Wstępna kompilacja niedostępna; uruchamiacz zostanie skompilowany przy każdym uruchomieniu (~1 s narzut). Powód: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="215"/>
        <source>Existing Java 21+ found at {}, skipping download.</source>
        <translation>Znaleziono istniejącą Javę 21+ w {} , pomijanie pobierania.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="219"/>
        <source>Found a Java at {} that is not 21+ — leaving it; downloading a Temurin 21 JDK alongside it.</source>
        <translation>Znaleziono Javę w {} która nie jest wersją 21+ — zostawiamy ją; pobieramy obok niej Temurin 21 JDK.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="226"/>
        <source>Querying the Adoptium API for the latest Temurin 21 JDK…</source>
        <translation>Zapytanie do API Adoptium o najnowszy JDK Temurin 21…</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="309"/>
        <source>Downloading {}…</source>
        <translation>Pobieranie {}…</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="237"/>
        <source>Verifying SHA-256…</source>
        <translation>Weryfikacja SHA-256…</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="241"/>
        <source>JDK archive checksum does not match the Adoptium API. Expected {}, got {}. Retry.</source>
        <translation>Sumowanie kontrolne archiwum JDK nie zgadza się z API Adoptium. Oczekiwano {}, otrzymano {}. Ponawiamy próbę.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="246"/>
        <source>Extracting…</source>
        <translation>Ekstrakcja…</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="255"/>
        <source>Cannot find bin/java inside the unpacked JDK at {}. Please open an issue at {}.</source>
        <translation>Nie można znaleźć bin/java w rozpakowanym JDK pod adresem {} . Proszę zgłosić problem na stronie {} .</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="264"/>
        <source>Unpacked JDK reports &apos;{}&apos;: {}</source>
        <translation>Rozpakowany JDK raportuje '{}': {}</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="267"/>
        <source>Java {} OK ({})</source>
        <translation>Java {} OK ({})</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="281"/>
        <source>Cannot reach the Adoptium API (https://api.adoptium.net). Check your connection. ({})</source>
        <translation>Nie można połączyć się z API Adoptium (https://api.adoptium.net). Sprawdź swoje połączenie. ({})</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="286"/>
        <source>Adoptium has no Temurin 21 JDK x64 build for &apos;{}&apos;. See https://adoptium.net/temurin/releases/?version=21</source>
        <translation>Adoptium nie posiada kompilacji Temurin 21 JDK dla {}x64. Sprawdź pod adresem https://adoptium.net/temurin/releases/?version=21</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="301"/>
        <source>Existing R5 jar found at {}, skipping download.</source>
        <translation>Istniejący plik JAR R5 znaleziony w {} , pomijanie pobierania.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="321"/>
        <source>R5 jar SHA-256 does not match the pinned value.
  expected {}
  got      {}
The download may be corrupt — retry.</source>
        <translation>Plik R5 jar SHA-256 nie zgadza się z przypisaną wartością.
Oczekiwano {}
Otrzymano {}
Pobieranie może być uszkodzone — spróbuj ponownie.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="327"/>
        <source>Downloaded R5 jar failed its structure check. Retry.</source>
        <translation>Pobranie pliku JAR R5 nie przeszło kontroli struktury. Ponówienie próby.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="330"/>
        <source>R5 jar OK ({}), SHA-256 verified.</source>
        <translation>R5 plik JAR OK ({}), zweryfikowano SHA-256.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="341"/>
        <source>Automatic download supports x64 only (detected {}). Install Temurin 21 manually from https://adoptium.net/temurin/releases/?version=21 and point TestR5Setup at it.</source>
        <translation>Automatyczne pobieranie obsługuje tylko x64 (wykryto {}). Zainstaluj ręcznie Temurin 21 z https://adoptium.net/temurin/releases/?version=21 i wskaż do niego TestR5Setup.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="353"/>
        <source>Unsupported platform &apos;{}&apos;. Use the &apos;Platform override&apos; parameter.</source>
        <translation>Nieobsługiwana platforma '{}'. Użyj parametru „Nadpisanie platformy”.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="362"/>
        <source>Folder &apos;{}&apos; does not exist and neither does its parent.</source>
        <translation>Folder '{}' nie istnieje i jego rodzic również.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="370"/>
        <source>Cannot write to &apos;{}&apos;: administrator rights required. Choose a folder in your user profile.</source>
        <translation>Nie można zapisać do '{}': wymagane uprawnienia administratora. Wybierz folder w swoim profilu użytkownika.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="375"/>
        <source>Cannot write to &apos;{}&apos;: {}</source>
        <translation>Nie można zapisać do '{}': {}</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="382"/>
        <source>Not enough disk space in &apos;{}&apos;. Need ~{} MB, have {:.0f} MB.</source>
        <translation>Za mało miejsca na dysku w '{}'. Potrzebne jest około {} MB, dostępne jest {:.0f} MB.</translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="411"/>
        <source>Download failed ({}): {}</source>
        <translation>Pobieranie nie powiodło się ({}): {}</translation>
    </message>
</context>
<context>
    <name>GenerateIsochrones</name>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="64"/>
        <source>Generate isochrones</source>
        <translation>Wygeneruj izochrony</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="67"/>
        <source>Analysis</source>
        <translation>Analiza</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="95"/>
        <source>Percentiles (1-99, ascending, up to 5)</source>
        <translation>Percentyle (1–99, rosnąco, maks. 5)</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="98"/>
        <source>Cutoffs (minutes, comma-separated)</source>
        <translation>Progi czasowe (minuty, po przecinku)</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="104"/>
        <source>Grid spacing (metres)</source>
        <translation>Rozstaw siatki (metry)</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="110"/>
        <source>Output isochrones</source>
        <translation>Wynikowe izochrony</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="126"/>
        <source>Cutoffs must be whole numbers of minutes.</source>
        <translation>Progi czasowe muszą być całkowitą liczbą minut.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="128"/>
        <source>Give at least one positive cutoff.</source>
        <translation>Podaj co najmniej jeden dodatni próg czasowy.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="132"/>
        <source>Origin points are required.</source>
        <translation>Wymagane są punkty źródłowe.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="156"/>
        <source>Could not create the output layer.</source>
        <translation>Nie udało się utworzyć warstwy wynikowej.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="168"/>
        <source>Origin {} reached no grid cell — no isochrone.</source>
        <translation>Źródło {} nie osiągnęło żadnej komórki siatki — brak izochrony.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="175"/>
        <source>{} isochrone polygons written.</source>
        <translation>Zapisano {} wielokątów izochron.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="212"/>
        <source>Grid would be ~{n:,.0f} points ({w:.0f} x {h:.0f} m at {s} m). Increase GRID_SPACING or use fewer / closer origins.</source>
        <translation>Siatka będzie miała około {n:,.0f} punktów ({w:.0f} x {h:.0f} m przy rozstawie {s} m). Zwiększ ROZSTAWIENIE SIATKI lub użyj mniej/bliższych źródeł.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="216"/>
        <source>Destination grid: up to ~{:,.0f} points at {} m (clipped to origin reach).</source>
        <translation>Siatka celów: do ~{:,.0f} punktów co {} m (przycięta do zasięgu źródeł).</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="135"/>
        <source>The origin layer has no valid CRS — set it before running.</source>
        <translation>Warstwa źródłowa nie ma poprawnego CRS — ustaw go przed uruchomieniem.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="198"/>
        <source>Could not derive a metric CRS for the origins (EPSG:{}).</source>
        <translation>Nie można wyprowadzić metrycznego układu współrzędnych dla źródeł (EPSG:{}).</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="76"/>
        <source>Travel-time isochrone polygons from one or more origin points, for one or more cutoffs. Builds a regular destination grid (GRID_SPACING, metres), runs a one-origin matrix against it, interpolates the times to a raster (TIN) and marching-squares contours each cutoff — the same approach r5r/r5py/Conveyal use; R5 itself has no isochrone output.

One output feature per (origin, cutoff), tagged origin_id and cutoff_min, in the origin layer's CRS. Polygons are cumulative — the 30-minute area contains the 15-minute one. Interior holes are kept where an area is genuinely unreachable (a lake, a rail yard, a street-network gap); noise smaller than a few grid cells is dropped.

Contouring runs once per cutoff, so a failure on one is reported and skipped without losing the rest. Grid cost is quadratic in 1/GRID_SPACING and blocked above ~400k points. MAX_WALK_TIME defaults to max(CUTOFFS) — lossless and the biggest speed lever.</source>
        <translation>Poligony izochronne czasu podróży z jednego lub więcej punktów początkowych, dla jednego lub więcej progów czasowych. Buduje regularną siatkę docelową (GRID_SPACING, metry), uruchamia macierz jednopunktową względem niej, interpoluje czasy do rastra (TIN) i kontury metodą kwadratów marszowych dla każdego progu — to ten sam sposób stosowany przez r5r/r5py/Conveyal; sam R5 nie ma wyjścia izochronnego.

Jedna cecha wyjściowa na każdą parę (punkt początkowy, próg czasowy), z tagami origin_id i cutoff_min, w układzie współrzędnych CRS warstwy źródłowej. Poligony są kumulatywne — obszar 30-minutowy zawiera ten 15-minutowy. Zachowane są wewnętrzne dziury tam, gdzie obszar jest faktycznie niedostępny (jezioro, składowisko kolejowe, luka w sieci ulicznej); szum mniejszy niż kilka komórek siatki jest usuwany.

Konturowanie odbywa się raz dla każdego progu czasowego, więc awaria jednego jest zgłaszana i pomijana bez utraty pozostałych. Koszt siatki jest kwadratowy względem 1/GRID_SPACING i blokowany powyżej ~400 tys. punktów. MAX_WALK_TIME domyślnie przyjmuje wartość max(CUTOFFS) — bezstratnie i to największy dźwignia prędkości.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="304"/>
        <source>Origin {}: could not build the travel-time raster ({}).</source>
        <translation>Źródło {}: nie udało się zbudować rastra czasu podróży ({}).</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="342"/>
        <source>Origin {}: cutoff {} min failed to contour ({}) — skipped.</source>
        <translation>Źródło {}: próg czasowy {} min nie udało się konturować ({} ) — pominięto.</translation>
    </message>
</context>
<context>
    <name>PopulationOverlay</name>
    <message>
        <location filename="../algorithms/population_overlay.py" line="39"/>
        <source>Population overlay</source>
        <translation>Nałóż ludność na siatkę</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="42"/>
        <source>Analysis</source>
        <translation>Analiza</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="48"/>
        <source>Overlays a demographic polygon layer on a hexagonal grid using areal interpolation weighted by surface area.

Each hexagon receives a &apos;population&apos; field (Float) with the estimated number of persons from the chosen population field. The algorithm splits census polygons by hex edges, computes the area-weighted population of each piece, then sums those pieces per hexagon.

The hex grid must be in a projected CRS with metric units (e.g. EPSG:2180, EPSG:3857). If the population layer has a different CRS it is reprojected automatically before processing.</source>
        <translation>Nakłada warstwę poligonów demograficznych na siatkę heksagonalną przy użyciu interpolacji powierzchniowej ważonej powierzchnią.

Każdy heksagon otrzymuje pole 'population' (Float) z szacowaną liczbą osób z wybranego pola populacji. Algorytm dzieli poligony spisowe po krawędziach heksagonów, oblicza populację ważoną powierzchnią dla każdego fragmentu, a następnie sumuje te fragmenty w każdym heksagonie.

Siatka heksagonalna musi znajdować się w układzie współrzędnych projektowych z jednostkami metrycznymi (np. EPSG:2180, EPSG:3857). Jeśli warstwa populacji ma inny układ CRS, jest automatycznie reprojektowana przed przetwarzaniem.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="65"/>
        <source>Hex grid</source>
        <translation>Siatka heksagonalna</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="72"/>
        <source>Population layer</source>
        <translation>Warstwa populacji</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="79"/>
        <source>Population field</source>
        <translation>Pole populacji</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="88"/>
        <source>Output (hex grid with population count)</source>
        <translation>Siatka heksagonalna z liczbą ludności</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="112"/>
        <source>Hex grid must be in a projected CRS with metric units (e.g. EPSG:2180, EPSG:3857). Got: {}.</source>
        <translation>Siatka heksagonalna musi znajdować się w układzie współrzędnych projektowych z jednostkami metrycznymi (np. EPSG:2180, EPSG:3857). Otrzymano: {}.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="118"/>
        <source>Population layer must be polygonal, got &apos;{}&apos;.</source>
        <translation>Warstwa populacji musi być poligonalna, otrzymano '{}'.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="126"/>
        <source>Population layer has no field &apos;{}&apos;.</source>
        <translation>Warstwa populacji nie posiada pola '{}'.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="134"/>
        <source>Field &apos;{}&apos; must be numeric (Int or Float), got &apos;{}&apos;.</source>
        <translation>Pole '{}' musi być numeryczne (Int lub Float), otrzymano '{}'.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="141"/>
        <source>Output field &apos;population&apos; already exists in HEX_GRID. Remove it or rename it before running PopulationOverlay.</source>
        <translation>Pole wyjściowe 'population' już istnieje w HEX_GRID. Usuń je lub zmień nazwę przed uruchomieniem PopulationOverlay.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="150"/>
        <source>Reprojecting population layer from {} to {}.</source>
        <translation>Reprojektowanie warstwy populacji z {} do {}.</translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="312"/>
        <source>{} hexagon(s) have population = 0 (not covered by the population layer).</source>
        <translation>{}:n:,.0f heksagonów ma populację = 0 (nie pokryte warstwą populacji).</translation>
    </message>
</context>
<context>
    <name>PreparePopulationLayer</name>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="43"/>
        <source>Prepare population layer</source>
        <translation>Przygotuj warstwę ludności</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="46"/>
        <source>Analysis</source>
        <translation>Analiza</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="52"/>
        <source>Reads a GUS NSP 2021 Excel file and joins census-tract population data to a polygon geometry layer.

Handles three observed states of GUS Excel files:
  'raw'   — multi-row header, short symbols; region code forward-filled from preceding 'rejon statystyczny' rows.
  'wrong' — full 7-char keys, but population values are strings with '-' as suppression markers.
  'done'  — clean, numeric values, minimum processing.

Output: a polygon layer with the original geometry attributes plus one added Double field (default 'pop20_29') — ready for use as POPULATION_LAYER in the Population overlay algorithm.

Census tract geometry layer: must be the GUS polygon layer of statistical census tracts (obwody spisowe NSP 2021) for your study area. The layer must contain a string field with the census-tract identifier (default 'OBWOD') matching the keys in the Excel file. Download the geometry from the GUS geoportal (https://geo.stat.gov.pl/) or use the GeoJSON published alongside the NSP 2021 results. A shapefile that imported OBWOD as an integer field will lose leading zeros — convert it to text in the Field Calculator before running this algorithm.

Requires openpyxl. If the automatic install at QGIS startup failed (e.g. SSL unavailable in QGIS 3.22), install manually from the OSGeo4W Shell: python -m pip install openpyxl — then restart QGIS.

Input file: download the 'Ludnosc w rejonach statystycznych i obwodach spisowych' table from the GUS NSP 2021 results page (stat.gov.pl/spisy-powszechne/nsp-2021/).</source>
        <translation>Odczytuje plik Excel z GUS NSP 2021 i łączy dane o populacji dla obwodów spisowych z warstwą geometrii wielokąta.

Obsługuje trzy zaobserwowane stany plików GUS Excel:
  'raw'   — nagłówek wielo-wierszowy, krótkie symbole; kod regionu wypełniany do przodu z poprzednich wierszy 'rejon statystyczny'.
  'wrong' — pełne klucze 7-znakowe, ale wartości populacji są ciągami znaków ze znacznikami '-' jako markerami zastąpienia.
  'done'  — czyste, numeryczne wartości, minimalna obróbka.

Wyjście: warstwa wielokąta z oryginalnymi atrybutami geometrii plus jednym dodanym polem typu Double (domyślnie 'pop20_29') — gotowa do użycia jako POPULATION_LAYER w algorytmie nakładania populacji.

Warstwa geometrii obwodów spisowych: musi być warstwą wielokąta GUS dla statystycznych obwodów spisowych (obwody spisowe NSP 2021) dla Twojego obszaru badawczego. Warstwa musi zawierać pole tekstowe z identyfikatorem obwodu spisowego (domyślnie 'OBWOD'), pasujące do kluczy w pliku Excel. Pobierz geometrię z geoportalu GUS (https://geo.stat.gov.pl/) lub użyj GeoJSON opublikowanego wraz z wynikami NSP 2021. Plik shapefile, który zaimportował OBWOD jako pole całkowite, straci wiodące zera — przekonwertuj go na tekst w Kalkulatorze pól przed uruchomieniem tego algorytmu.

Wymaga openpyxl. Jeśli automatyczna instalacja przy starcie QGIS się nie powiodła (np. brak SSL w QGIS 3.22), zainstaluj ręcznie z Konsoli OSGeo4W: python -m pip install openpyxl — a następnie uruchom ponownie QGIS.

Plik wejściowy: pobierz tabelę 'Ludność w rejonach statystycznych i obwodach spisowych' ze strony wyników GUS NSP 2021 (stat.gov.pl/spisy-powszechne/nsp-2021/).</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="85"/>
        <source>GUS NSP 2021 Excel file</source>
        <translation>Plik XLSX GUS NSP 2021</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="85"/>
        <source>Excel files (*.xlsx)</source>
        <translation>Pliki Excela (*.xlsx)</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="93"/>
        <source>Sheet name (empty = first sheet)</source>
        <translation>Nazwa arkusza (puste = pierwszy arkusz)</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="101"/>
        <source>Population column name in Excel header</source>
        <translation>Nazwa kolumny populacji w nagłówku arkusza kalkulacyjnego</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="108"/>
        <source>Census tract geometry layer</source>
        <translation>Warstwa geometrii okręgów spisowych</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="115"/>
        <source>Join key field in geometry layer</source>
        <translation>Połącz pole klucza w warstwie geometrii</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="123"/>
        <source>Output field name</source>
        <translation>Nazwa pola wyjściowego</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="130"/>
        <source>Output layer</source>
        <translation>Warstwa wyjściowa</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="151"/>
        <source>openpyxl is not available. If the automatic install at QGIS startup failed, install manually from the OSGeo4W Shell: python -m pip install openpyxl — then restart QGIS.</source>
        <translation>openpyxl nie jest dostępne. Jeśli automatyczna instalacja przy starcie QGIS się nie powiodła, zainstaluj ręcznie z Konsoli OSGeo4W: python -m pip install openpyxl — a następnie uruchom ponownie QGIS.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="170"/>
        <source>Loading Excel file: {}</source>
        <translation>Ładowanie pliku Excela: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="184"/>
        <source>Excel reader subprocess failed (exit {}):
{}</source>
        <translation>Podprocesor czytnika Excela zakończył niepowodzeniem (wyjście {}):
{}</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="197"/>
        <source>Multi-sheet workbook; using first sheet &apos;{}&apos;. All sheets: {}.</source>
        <translation>Wielostronicowa książka robocza; używa pierwszego arkusza '{}'. Wszystkie arkusze: {}.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="231"/>
        <source>Could not detect header row. Searched rows 0-29 for columns &apos;Symbol&apos; and &apos;Struktura&apos;. Check that the sheet &apos;{}&apos; is correct.</source>
        <translation>Nie wykryto wiersza nagłówka. Szukano wierszy 0-29 dla kolumn 'Symbol' i 'Struktura'. Sprawdź, czy arkusz '{}' jest poprawny.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="242"/>
        <source>Column &apos;{}&apos; not found in header. Available columns near row {}: {}.</source>
        <translation>Kolumna '{}' nie została znaleziona w nagłówku. Dostępne kolumny w pobliżu wiersza {}: {}.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="251"/>
        <source>Header: Symbol/Struktura at row {} (0-based), &apos;{}&apos; at row {}. Columns: Symbol={}, Struktura={}, {}={}.</source>
        <translation>Nagłówek: Symbol/Struktura w wierszu {} (indeksowanie od 0), '{}' w wierszu {}. Kolumny: Symbol={}, Struktura={}, {}={}.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="306"/>
        <source>Row {}: census tract &apos;{}&apos; encountered without a preceding &apos;rejon statystyczny&apos; row. Cannot build join key.</source>
        <translation>Wiersz {}: napotkano rejon statystyczny '{}' bez poprzedzającego wiersza 'rejon statystyczny'. Nie można zbudować klucza łączenia.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="330"/>
        <source>Row {}: cannot interpret &apos;{}&apos; as a number in column &apos;{}&apos;. Expected a number, an empty cell, or &apos;-&apos;.</source>
        <translation>W wierszu {}: nie można zinterpretować '{}' jako liczby w kolumnie '{}'. Oczekiwano liczby, pustej komórki lub '-'.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="352"/>
        <source>{} OBWOD symbol(s) appeared more than once; population values summed (GUS records split census tracts under the same symbol at administrative boundaries): {}{}.</source>
        <translation>Symbol OBWOD wystąpił więcej niż raz ({}); wartości ludności zsumowano (GUS dzieli obwody spisowe o tym samym symbolu na granicach administracyjnych): {}{}.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="362"/>
        <source>Excel extraction: {} tract rows, {} unique keys, {} &apos;-&apos; values converted to 0.</source>
        <translation>Ekstrakcja z Excela: {} wierszy działek, {} unikalnych kluczy, {} wartości '-' zamienionych na 0.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="374"/>
        <source>Geometry layer has no field &apos;{}&apos;. Available fields: {}.</source>
        <translation>Warstwa geometryczna nie posiada pola '{}'. Dostępne pola: {}.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="418"/>
        <source>Key field &apos;{}&apos; is numeric; leading zeros may be lost when converting to string. Consider storing &apos;{}&apos; as a text field to preserve keys like &apos;0123456&apos;.</source>
        <translation>Kluczowe pole '{}' jest numeryczne; w przypadku konwersji na ciąg znaków mogą zostać utracone zera wiodące. Rozważ przechowywanie '{}' jako pola tekstowego, aby zachować klucze takie jak '0123456'.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="449"/>
        <source>None of the {} Excel rows match the geometry layer. Check that you provided the correct file for this region.</source>
        <translation>Żaden z {} wierszy pliku Excel nie pasuje do warstwy geometrii. Sprawdź, czy podano właściwy plik dla tego regionu.</translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="462"/>
        <source>--- PreparePopulationLayer complete ---
Excel tract rows:              {}
Geometry features:             {}
Matched (both sets):           {}
Excel keys not in geometry:    {}
Geometry features unmatched:   {} ({} = NULL)
&apos;-&apos; values converted to 0:     {}
{} stats:  min={:.1f}  max={:.1f}  sum={:.1f}</source>
        <translation>Przygotowanie warstwy populacji zakończone ---
Wiersze z Excela:              {}
Obiekty geometryczne:             {}
Dopasowane (oba zbiory):           {}
Klucze z Excela nieobecne w geometrii:    {}
Niepasujące obiekty geometryczne:   {} ({} = NULL)
Wartości '-' zamienione na 0:     {}
Statystyki {}:  min={:.1f}  max={:.1f}  suma={:.1f}</translation>
    </message>
</context>
<context>
    <name>RunAccessibility</name>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="57"/>
        <source>Run accessibility</source>
        <translation>Policz dostępność</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="60"/>
        <source>Analysis</source>
        <translation>Analiza</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="69"/>
        <source>For each origin, counts the opportunities (jobs, schools, shops…) at destinations reachable within each cutoff, weighted by a decay function of travel time. Runs the same matrix as RunTravelTimeMatrix then sums in Python.

OPPORTUNITY_FIELDS are numeric columns on the destination layer. STEP decay (count everything at or under the cutoff) is the default and what accessibility studies use; LOGISTIC and EXPONENTIAL taper.

Output: a long CSV (id, opportunity, percentile, cutoff, accessibility) and an ORIGINS copy with acc_&lt;opp&gt;_p&lt;pct&gt;_c&lt;cutoff&gt; fields.</source>
        <translation>Dla każdego źródła liczy możliwości (miejsca pracy, szkoły, sklepy…) w celach osiągalnych w ramach każdego progu czasowego, ważonych funkcją zaniku czasu podróży. Uruchamia tę samą macierz co RunTravelTimeMatrix, a następnie sumuje ją w Pythonie.

OPPORTUNITY_FIELDS to kolumny numeryczne na warstwie docelowej. Domyślne jest wygaszenie STEP (liczy wszystko przy lub poniżej progu czasowego), którego używają badania dostępności; LOGISTYCZNE i EKSPONENCJALNE wygaszanie.

Wyjście: długi plik CSV (id, opportunity, percentile, cutoff, accessibility) oraz kopia ORIGINS z polami acc_&lt;opp&gt;_p&lt;pct&gt;_c&lt;cutoff&gt;.</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="83"/>
        <source>Percentiles (1-99, ascending, up to 5)</source>
        <translation>Percentyle (1–99, rosnąco, maks. 5)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="84"/>
        <source>Opportunity fields on the destination layer</source>
        <translation>Pola możliwości w warstwie docelowej</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="91"/>
        <source>Cutoffs (minutes, comma-separated)</source>
        <translation>Progi czasowe (minuty, po przecinku)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="97"/>
        <source>Decay function</source>
        <translation>Funkcja zaniku</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="103"/>
        <source>Output accessibility CSV (long)</source>
        <translation>Wynikowy plik CSV dostępności (format długi)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="103"/>
        <source>CSV files (*.csv)</source>
        <translation>Pliki CSV (*.csv)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="109"/>
        <source>Output layer (origins + accessibility fields)</source>
        <translation>Warstwa wynikowa (źródła + pola dostępności)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="125"/>
        <source>Cutoffs must be whole numbers of minutes.</source>
        <translation>Progi czasowe muszą być całkowitą liczbą minut.</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="127"/>
        <source>Give at least one positive cutoff.</source>
        <translation>Podaj co najmniej jeden dodatni próg czasowy.</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="129"/>
        <source>Select at least one opportunity field.</source>
        <translation>Wybierz co najmniej jedno pole możliwości.</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="144"/>
        <source>Summing accessibility ({} decay)…</source>
        <translation>Sumowanie dostępności ({})…</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="152"/>
        <source>Wrote {n} rows to {p}</source>
        <translation>Zapisano {n} wierszy do {p}</translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="190"/>
        <source>Could not create the output layer.</source>
        <translation>Nie udało się utworzyć warstwy wynikowej.</translation>
    </message>
</context>
<context>
    <name>RunTravelTimeMatrix</name>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="43"/>
        <source>Run travel time matrix</source>
        <translation>Policz macierz czasów przejazdu</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="46"/>
        <source>Analysis</source>
        <translation>Analiza</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="55"/>
        <source>Computes travel times from every origin point to every destination point over a departure-time window, using a network built by BuildNetwork. Output is a long-format CSV: from_id, to_id, and one travel_time_p&lt;percentile&gt; column per requested percentile (minutes; unreachable pairs are omitted, or left blank with INCLUDE_UNREACHABLE).

The run is blocked if the GTFS feed has no trips on DATE — R5 would otherwise silently return walk-only results. ESTIMATE_FIRST times a spread sample of origins and reports an extrapolation before the full run; cost scales with network complexity, so the estimate is measured, not guessed.

Accessibility and isochrones are separate algorithms.</source>
        <translation>Oblicza czasy podróży z każdego punktu źródłowego do każdego punktu docelowego w oknie odjazdu, korzystając z sieci zbudowanej przez BuildNetwork. Wynikiem jest plik CSV w formacie długim: from_id, to_id oraz jedna kolumna travel_time_p&lt;percentile&gt; dla każdego żądanego percentyla (minuty; pary niedostępne są pomijane lub pozostawione puste przy INCLUDE_UNREACHABLE).

Uruchomienie jest blokowane, jeśli strumień GTFS nie zawiera kursów w dniu — R5 inaczej domyślnie zwróciłby wyniki tylko dla pieszych. ESTIMATE_FIRST szacuje rozproszony próbkę źródeł i raportuje ekstrapolację przed pełnym uruchomieniem; koszt skaluje się wraz ze złożonością sieci, więc szacunek jest mierzony, a nie zgadywany.

Dostępność (Accessibility) i izochrony to oddzielne algorytmy.</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="71"/>
        <source>Percentiles (1-99, ascending, up to 5)</source>
        <translation>Percentyle (1–99, rosnąco, maks. 5)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="72"/>
        <source>Keep unreachable pairs as blank-value rows</source>
        <translation>Zachowaj pary nieosiągalne jako wiersze z pustą wartością</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="78"/>
        <source>Output matrix CSV</source>
        <translation>Wynikowy plik CSV macierzy</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="78"/>
        <source>CSV files (*.csv)</source>
        <translation>Pliki CSV (*.csv)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="84"/>
        <source>Output OD lines (optional)</source>
        <translation>Wynikowe linie OD (opcjonalne)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="106"/>
        <source>Wrote {p}</source>
        <translation>Napisałem {p}</translation>
    </message>
</context>
<context>
    <name>TestR5Setup</name>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="42"/>
        <source>Test R5 setup</source>
        <translation>Sprawdź konfigurację R5</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="45"/>
        <source>Diagnostics</source>
        <translation>Diagnostyka</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="54"/>
        <source>Checks an R5 setup step by step and reports each independently:
  1. the Temurin 21 JDK exists and reports Java 21+
  2. the R5 jar exists and its SHA-256 matches the pinned value
  3. the Java runner is compiled (or the source launcher is usable)
  4. (optional) run command=info on a network.dat and print its metadata

Run &apos;Download R5 engine and Java 21&apos; first. In milestone M1 the runner implements only command=info; a full travel-time query arrives in M3.</source>
        <translation>Sprawdza konfigurację R5 krok po kroku i raportuje każdy z nich niezależnie:
  1. istnieje JDK Temurin 21 i zgłasza Java 21+
  2. plik jar R5 istnieje i jego SHA-256 odpowiada przypisanym wartościom
  3. runner Java został skompilowany (lub launcher źródłowy jest używalny)
  4. (opcjonalnie) wykonaj polecenie=info na network.dat i wydrukuj jego metadane

Najpierw uruchom 'Pobierz silnik R5 i Javę 21'. W kamieniu milowym M1 runner implementuje tylko command=info; pełne zapytanie o czas podróży pojawi się w M3.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="65"/>
        <source>Use the JDK path saved by &apos;Download R5 engine and Java 21&apos;</source>
        <translation>Użyj ścieżki JDK zapisanej przez „Pobierz silnik R5 i Javę 21”</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="72"/>
        <source>Java 21 binary (only if not using the saved path)</source>
        <translation>Binarna wersja Java 21 (tylko jeśli nie używasz zapisanej ścieżki)</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="84"/>
        <source>network.dat to probe with command=info (optional)</source>
        <translation>network.dat do sondowania z poleceniem=info (opcjonalnie)</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="95"/>
        <source>R5 version</source>
        <translation>wersja R5</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="114"/>
        <source>All checks passed.</source>
        <translation>Wszystkie sprawdzenia zakończone pomyślnie.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="116"/>
        <source>One or more checks failed — see the steps above.</source>
        <translation>Jeden lub więcej testów nie powiodło się — zobacz kroki powyżej.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="124"/>
        <source>Step 1: Java 21 JDK</source>
        <translation>Krok 1: Java 21 JDK</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="128"/>
        <source>  No JDK path saved. Run &apos;Download R5 engine and Java 21&apos;, or untick &apos;Use the saved JDK path&apos; and supply one.</source>
        <translation>Nie zapisana ścieżka do JDK. Uruchom 'Pobierz silnik R5 i Javę 21' lub odznacz 'Użyj zapisanej ścieżki do JDK' i podaj własną.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="139"/>
        <source>  No JDK path given. Tick &apos;Use the saved JDK path&apos; or set one.</source>
        <translation>Nie podano ścieżki do JDK. Zaznacz opcję „Użyj zapisanej ścieżki do JDK” lub ustaw ją ręcznie.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="146"/>
        <source>  OK: Java {} at {}</source>
        <translation>Java {} w {}</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="152"/>
        <source>Step 2: R5 jar</source>
        <translation>Krok 2: plik JAR R5</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="155"/>
        <source>  No R5 jar path saved. Run &apos;Download R5 engine and Java 21&apos;.</source>
        <translation>Nie zapisana ścieżka do pliku R5 jar. Uruchom 'Pobierz silnik R5 i Javę 21'.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="161"/>
        <source>  R5 jar not found: {}</source>
        <translation>Plik R5 nie znaleziony: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="164"/>
        <source>  Not a .jar file: {}</source>
        <translation>Nie plik .jar: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="167"/>
        <source>  {} does not look like the R5 fat jar (size or contents wrong).</source>
        <translation>{} nie wygląda jak plik JAR R5 (zły rozmiar lub zawartość).</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="175"/>
        <source>  SHA-256 mismatch for {}.
  expected {}
  got      {}
  Re-run &apos;Download R5 engine and Java 21&apos;.</source>
        <translation>Niezgodność SHA-256 dla {}.
Oczekiwano {}
Otrzymano {}
Ponownie uruchomienie 'Pobierz silnik R5 i Javę 21'.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="182"/>
        <source>  OK: {} (SHA-256 verified)</source>
        <translation>OK: {} (sprawdzono SHA-256)</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="186"/>
        <source>Step 3: Java runner</source>
        <translation>Krok 3: Uruchomienie w Javie</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="188"/>
        <source>  Skipped: fix steps 1 and 2 first.</source>
        <translation>Pominięto: najpierw popraw kroki 1 i 2.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="194"/>
        <source>  OK: compiled runner in {}</source>
        <translation>OK: skompilowany runner w {}</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="196"/>
        <source>  Compiled runner missing from {}</source>
        <translation>Skompilowany runner brakuje z {}</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="203"/>
        <source>  OK: source launcher will compile the runner per run ({})</source>
        <translation>OK: uruchamiacz źródłowy skompiluje wykonawcę dla każdego uruchomienia ({})</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="207"/>
        <source>  Runner source missing from {}</source>
        <translation>Źródło Runnera brakuje z {}</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="209"/>
        <source>  Runner not set up. Run &apos;Download R5 engine and Java 21&apos;.</source>
        <translation>Uruchomienie nie jest skonfigurowane. Uruchom 'Pobierz silnik R5 i Javę 21'.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="215"/>
        <source>Step 4: command=info</source>
        <translation>Krok 4: komenda=info</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="217"/>
        <source>  Skipped (no network.dat supplied).</source>
        <translation>Pominięto (nie podano pliku network.dat).</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="220"/>
        <source>  Skipped: the runner is not ready.</source>
        <translation>Pominięto: uruchamiacz nie jest gotowy.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="251"/>
        <source>  This is expected when the network was built with a different R5 version. It confirms the runner loads and the version guard works.</source>
        <translation>Oczekiwane, gdy sieć została zbudowana przy użyciu innej wersji R5. Potwierdza to, że runner się ładuje i działa mechanizm ochrony wersji.</translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="265"/>
        <source>  R5 version: {}</source>
        <translation>wersja R5: {}</translation>
    </message>
</context>
<context>
    <name>MatrixBase</name>
    <message>
        <source>Origin id field (blank = feature id)</source>
        <translation>Pole identyfikatora źródła (puste = identyfikator cechy)</translation>
    </message>
    <message>
        <source>Date (yyyy-MM-dd; required for transit)</source>
        <translation>Data (rrrr-MM-dd; wymagane dla transportu)</translation>
    </message>
    <message>
        <source>R5 network (network.dat)</source>
        <translation>Sieć R5 (network.dat)</translation>
    </message>
    <message>
        <source>Origin points</source>
        <translation>Punkty źródłowe</translation>
    </message>
    <message>
        <source>Destination id field (blank = feature id)</source>
        <translation>Pole identyfikatora celu (puste = identyfikator cechy)</translation>
    </message>
    <message>
        <source>Departure time (HH:mm)</source>
        <translation>Czas odjazdu (HH:mm)</translation>
    </message>
    <message>
        <source>Departure window (minutes)</source>
        <translation>Okno odjazdu (minuty)</translation>
    </message>
    <message>
        <source>Max trip duration (minutes)</source>
        <translation>Maksymalny czas kursu (minuty)</translation>
    </message>
    <message>
        <source>Walk speed (km/h)</source>
        <translation>Prędkość chodu (km/h)</translation>
    </message>
    <message>
        <source>Max transit rides (transfers + 1)</source>
        <translation>Maksymalna liczba przejazdów (przesiadki + 1)</translation>
    </message>
    <message>
        <source>Travel mode</source>
        <translation>Tryb podróży</translation>
    </message>
    <message>
        <source>Max walk time (minutes; blank = lossless default)</source>
        <translation>Maksymalny czas przejścia (minuty; puste = domyślne bezstratne)</translation>
    </message>
    <message>
        <source>Monte Carlo draws per minute</source>
        <translation>Monte Carlo rysuje na minutę</translation>
    </message>
    <message>
        <source>Origins per batch process</source>
        <translation>Źródła na partię przetwarzania</translation>
    </message>
    <message>
        <source>Time a sample of origins first</source>
        <translation>Czas próbki źródeł najpierw</translation>
    </message>
    <message>
        <source>Run even if the date has no transit service (diagnostic)</source>
        <translation>Uruchom nawet jeśli data nie ma usługi transportowej (diagnoza)</translation>
    </message>
    <message>
        <source>Java heap (GB; blank = auto)</source>
        <translation>Pamięć Java (GB; pusty = automatycznie)</translation>
    </message>
    <message>
        <source>Origin and destination layers are required.</source>
        <translation>Wymagane są warstwy źródła i celu.</translation>
    </message>
    <message>
        <source>A date is required for a transit run.</source>
        <translation>Wymagowana jest data dla kursu tranzytowego.</translation>
    </message>
    <message>
        <source>Cancelled by user.</source>
        <translation>Anulowano przez użytkownika.</translation>
    </message>
    <message>
        <source>Not one OD pair is faster by transit than on foot — R5 returned walk-only results. Most likely the date has no service or the GTFS does not match the network.</source>
        <translation>Żadna para źródło-cel nie jest szybsza komunikacją publiczną niż pieszo — R5 zwróciło wyniki tylko dla chodzenia. Najprawdopodobniej data nie ma obsługi lub GTFS nie pasuje do sieci.</translation>
    </message>
    <message>
        <source>Destination points</source>
        <translation>Punkty docelowe</translation>
    </message>
    <message>
        <source>{o} origins x {d} destinations = {n} pairs.</source>
        <translation>{o} źródeł x {d} celów = {n} par.</translation>
    </message>
    <message>
        <source>Matrix: {n} reachable pairs.</source>
        <translation>Macierz: {n} osiągalnych par.</translation>
    </message>
    <message>
        <source>Timing {n} sample origins…</source>
        <translation>Czasowanie {n} źródeł...</translation>
    </message>
    <message>
        <source>~{s:.2f} s/origin on this network -&gt; ~{m:.1f} min for {n} origins.</source>
        <translation>~{s:.2f} s/źródło na tej sieci -&gt; ~{m:.1f} min dla {n} źródeł.</translation>
    </message>
    <message>
        <source>Network file not found: {}</source>
        <translation>Plik sieciowy nie znaleziony: {}</translation>
    </message>
    <message>
        <source>ALLOW_NO_SERVICE: {date} has no transit service — expect a walk-only failure after the run.</source>
        <translation>BRAK_USŁUGI: {date} nie ma usługi transportowej — spodziewaj się błędu tylko pieszo po uruchomieniu.</translation>
    </message>
    <message>
        <source>No usable points after dropping empty geometries ({} origins, {} destinations skipped).</source>
        <translation>Brak użytecznych punktów po usunięciu geometrii pustych (pominiowano {} źródeł, {} celów).</translation>
    </message>
    <message>
        <source>Estimated {m:.0f} min — consider fewer origins or a coarser grid.</source>
        <translation>Szacowany {m:.0f} min — rozważ mniej źródeł lub grubszy siatkę.</translation>
    </message>
    <message>
        <source>The GTFS feed has no active trips on {date}. R5 would silently return walk-only results. Nearest served days: {days}. (Advanced: ALLOW_NO_SERVICE overrides this for diagnostics.)</source>
        <translation>W strumieniu GTFS nie ma aktywnych kursów na dzień {date}. R5 domyślnie zwróci wyniki tylko dla pieszych. Najbliższe dni obsługiwane: {days}. (Zaawansowane: ALLOW_NO_SERVICE nadpisuje to w celach diagnostycznych.)</translation>
    </message>
    <message>
        <source>MAX_WALK_TIME ({w} min) is below the lossless default ({d} min): faster, but trips with a long walk leg will be missed.</source>
        <translation>Maksymalny czas przejścia ({w} min) jest poniżej domyślnego wartości bezstratnej ({d} min): szybciej, ale zostaną pominięte kursy z długim odcinkiem pieszym.</translation>
    </message>
    <message>
        <source>Batch {b}/{n}: origins {s}-{e}</source>
        <translation>Partia {b}/{n}: źródła {s}-{e}</translation>
    </message>
    <message>
        <source>Estimate run failed ({}). Continuing.</source>
        <translation>Szacowanie wykonania nie powiodło się ({}). Kontynuowanie.</translation>
    </message>
    <message>
        <source>none in the feed span</source>
        <translation>żaden w zakresie strumienia</translation>
    </message>
    <message>
        <source>R5 ran out of memory (heap {gb} GB, batch size {bs}). Lower the batch size, thin the origin grid, or raise the Java heap in the plugin settings.</source>
        <translation>R5 wyczerpał pamięć (pamięć stosu {gb} GB, rozmiar partii {bs}). Zmniejsz rozmiar partii, przerzedź siatkę źródła lub zwiększ pamięć stosu Java w ustawieniach wtyczki.</translation>
    </message>
</context>
</TS>
