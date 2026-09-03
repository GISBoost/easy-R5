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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="78"/>
        <source>OSM extract (.osm.pbf)</source>
        <translation>Wycinek OSM (.osm.pbf)</translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="86"/>
        <source>Folder of GTFS feeds (every .zip inside is used)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="93"/>
        <source>Network cache folder (blank = plugin default)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="101"/>
        <source>Force rebuild (ignore the cache)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="108"/>
        <source>network.dat path</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="109"/>
        <source>network.json path</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="118"/>
        <source>OSM file not found: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="121"/>
        <source>No .zip GTFS feeds in folder: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="135"/>
        <source>Cache hit: {} — inputs and R5 version unchanged, skipping build.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="160"/>
        <source>Building the network — this can take a few minutes…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="167"/>
        <source>Network build cancelled by user.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="176"/>
        <source>Computing service_days from the GTFS calendar…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="201"/>
        <source>Network summary:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="217"/>
        <source>  served dates: {} .. {} — {} of {} days in the window have trips.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/build_network.py" line="221"/>
        <source>  This feed has NO active service anywhere in the {}-day window — every date would produce walk-only results. Check the GTFS release.</source>
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="90"/>
        <source>Destination folder for the JDK and R5 jar</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="98"/>
        <source>Download the Temurin 21 JDK</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="103"/>
        <source>Download r5-v7.6-all.jar</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="108"/>
        <source>Platform override</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="117"/>
        <source>JDK java binary path</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="118"/>
        <source>JDK version</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="119"/>
        <source>R5 jar path</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="120"/>
        <source>Runner mode</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="139"/>
        <source>Target platform: {} x64</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="149"/>
        <source>&apos;Download the Temurin 21 JDK&apos; is off and no JDK path is saved. Enable it, or run this once with it enabled.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="155"/>
        <source>Using saved JDK: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="158"/>
        <source>Cancelled after the JDK phase. The JDK path is saved — run the algorithm again to fetch the R5 jar.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="171"/>
        <source>&apos;Download r5-v7.6-all.jar&apos; is off and no jar path is saved.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="175"/>
        <source>Using saved R5 jar: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="182"/>
        <source>Compiling the Java runner…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="191"/>
        <source>Runner compiled to {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="193"/>
        <source>Pre-compilation unavailable; the runner will be compiled on each run (~1 s overhead). Reason: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="215"/>
        <source>Existing Java 21+ found at {}, skipping download.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="219"/>
        <source>Found a Java at {} that is not 21+ — leaving it; downloading a Temurin 21 JDK alongside it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="226"/>
        <source>Querying the Adoptium API for the latest Temurin 21 JDK…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="309"/>
        <source>Downloading {}…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="237"/>
        <source>Verifying SHA-256…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="241"/>
        <source>JDK archive checksum does not match the Adoptium API. Expected {}, got {}. Retry.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="246"/>
        <source>Extracting…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="255"/>
        <source>Cannot find bin/java inside the unpacked JDK at {}. Please open an issue at {}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="264"/>
        <source>Unpacked JDK reports &apos;{}&apos;: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="267"/>
        <source>Java {} OK ({})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="281"/>
        <source>Cannot reach the Adoptium API (https://api.adoptium.net). Check your connection. ({})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="286"/>
        <source>Adoptium has no Temurin 21 JDK x64 build for &apos;{}&apos;. See https://adoptium.net/temurin/releases/?version=21</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="301"/>
        <source>Existing R5 jar found at {}, skipping download.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="321"/>
        <source>R5 jar SHA-256 does not match the pinned value.
  expected {}
  got      {}
The download may be corrupt — retry.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="327"/>
        <source>Downloaded R5 jar failed its structure check. Retry.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="330"/>
        <source>R5 jar OK ({}), SHA-256 verified.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="341"/>
        <source>Automatic download supports x64 only (detected {}). Install Temurin 21 manually from https://adoptium.net/temurin/releases/?version=21 and point TestR5Setup at it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="353"/>
        <source>Unsupported platform &apos;{}&apos;. Use the &apos;Platform override&apos; parameter.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="362"/>
        <source>Folder &apos;{}&apos; does not exist and neither does its parent.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="370"/>
        <source>Cannot write to &apos;{}&apos;: administrator rights required. Choose a folder in your user profile.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="375"/>
        <source>Cannot write to &apos;{}&apos;: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="382"/>
        <source>Not enough disk space in &apos;{}&apos;. Need ~{} MB, have {:.0f} MB.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/download_r5.py" line="411"/>
        <source>Download failed ({}): {}</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>GenerateIsochrones</name>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="55"/>
        <source>Generate isochrones</source>
        <translation>Wygeneruj izochrony</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="58"/>
        <source>Analysis</source>
        <translation>Analiza</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="67"/>
        <source>Travel-time isochrone polygons from one or more origin points. Builds a regular destination grid (GRID_SPACING, metres), runs a one-origin matrix against it, then rasterises and contours each cutoff.

R5 does not contour — that is done here in GDAL. If one cutoff fails to contour it is reported and skipped; the rest still come out.

Grid cost is quadratic in 1/GRID_SPACING — the run is blocked above a few hundred thousand grid points. MAX_WALK_TIME defaults to max(CUTOFFS), which is lossless and the biggest speed lever.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="80"/>
        <source>Percentiles (1-99, ascending, up to 5)</source>
        <translation>Percentyle (1–99, rosnąco, maks. 5)</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="83"/>
        <source>Cutoffs (minutes, comma-separated)</source>
        <translation>Progi czasowe (minuty, po przecinku)</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="89"/>
        <source>Grid spacing (metres)</source>
        <translation>Rozstaw siatki (metry)</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="95"/>
        <source>Output isochrones</source>
        <translation>Wynikowe izochrony</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="111"/>
        <source>Cutoffs must be whole numbers of minutes.</source>
        <translation>Progi czasowe muszą być całkowitą liczbą minut.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="113"/>
        <source>Give at least one positive cutoff.</source>
        <translation>Podaj co najmniej jeden dodatni próg czasowy.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="117"/>
        <source>Origin points are required.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="137"/>
        <source>Could not create the output layer.</source>
        <translation>Nie udało się utworzyć warstwy wynikowej.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="149"/>
        <source>Origin {} reached no grid cell — no isochrone.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="155"/>
        <source>{} isochrone polygons written.</source>
        <translation>Zapisano {} wielokątów izochron.</translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="185"/>
        <source>Grid would be ~{n:,.0f} points ({w:.0f} x {h:.0f} m at {s} m). Increase GRID_SPACING or use fewer / closer origins.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="189"/>
        <source>Destination grid: ~{:,.0f} points at {} m.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/generate_isochrones.py" line="254"/>
        <source>Origin {}: cutoff {} min failed ({}) — skipped.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>MatrixBase</name>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="79"/>
        <source>R5 network (network.dat)</source>
        <translation>Sieć R5 (network.dat)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="85"/>
        <source>Origin points</source>
        <translation>Punkty źródłowe</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="88"/>
        <source>Origin id field (blank = feature id)</source>
        <translation>Pole identyfikatora źródła (puste = id obiektu)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="95"/>
        <source>Destination points</source>
        <translation>Punkty docelowe</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="99"/>
        <source>Destination id field (blank = feature id)</source>
        <translation>Pole identyfikatora celu (puste = id obiektu)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="106"/>
        <source>Date (yyyy-MM-dd; required for transit)</source>
        <translation>Data (rrrr-MM-dd; wymagana dla transportu)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="111"/>
        <source>Departure time (HH:mm)</source>
        <translation>Godzina odjazdu (GG:mm)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="116"/>
        <source>Departure window (minutes)</source>
        <translation>Okno odjazdów (minuty)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="125"/>
        <source>Max trip duration (minutes)</source>
        <translation>Maksymalny czas podróży (minuty)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="131"/>
        <source>Walk speed (km/h)</source>
        <translation>Prędkość pieszo (km/h)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="137"/>
        <source>Max transit rides (transfers + 1)</source>
        <translation>Maksymalna liczba przejazdów (przesiadki + 1)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="143"/>
        <source>Travel mode</source>
        <translation>Środek transportu</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="148"/>
        <source>Max walk time (minutes; blank = lossless default)</source>
        <translation>Maksymalny czas pieszo (minuty; puste = bezstratna wartość domyślna)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="154"/>
        <source>Monte Carlo draws per minute</source>
        <translation>Losowania Monte Carlo na minutę</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="160"/>
        <source>Origins per batch process</source>
        <translation>Źródeł na proces wsadowy</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="167"/>
        <source>Time a sample of origins first</source>
        <translation>Najpierw zmierz próbkę źródeł</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="172"/>
        <source>Run even if the date has no transit service (diagnostic)</source>
        <translation>Uruchom nawet gdy w danym dniu nie ma kursów (diagnostyka)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="179"/>
        <source>Java heap (GB; blank = auto)</source>
        <translation>Sterta Javy (GB; puste = automatycznie)</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="200"/>
        <source>Network file not found: {}</source>
        <translation>Nie znaleziono pliku sieci: {}</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="209"/>
        <source>Origin and destination layers are required.</source>
        <translation>Warstwy źródeł i celów są wymagane.</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="237"/>
        <source>A date is required for a transit run.</source>
        <translation>Dla przebiegu transportowego wymagana jest data.</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="243"/>
        <source>The GTFS feed has no active trips on {date}. R5 would silently return walk-only results. Nearest served days: {days}. (Advanced: ALLOW_NO_SERVICE overrides this for diagnostics.)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="243"/>
        <source>none in the feed span</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="250"/>
        <source>ALLOW_NO_SERVICE: {date} has no transit service — expect a walk-only failure after the run.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="259"/>
        <source>MAX_WALK_TIME ({w} min) is below the lossless default ({d} min): faster, but trips with a long walk leg will be missed.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="290"/>
        <source>No usable points after dropping empty geometries ({} origins, {} destinations skipped).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="294"/>
        <source>{o} origins x {d} destinations = {n} pairs.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="347"/>
        <source>Cancelled by user.</source>
        <translation>Anulowano przez użytkownika.</translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="337"/>
        <source>Batch {b}/{n}: origins {s}-{e}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="350"/>
        <source>R5 ran out of memory (heap {gb} GB, batch size {bs}). Lower the batch size, thin the origin grid, or raise the Java heap in the plugin settings.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="360"/>
        <source>Matrix: {n} reachable pairs.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="363"/>
        <source>Not one OD pair is faster by transit than on foot — R5 returned walk-only results. Most likely the date has no service or the GTFS does not match the network.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="410"/>
        <source>Timing {n} sample origins…</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="416"/>
        <source>Estimate run failed ({}). Continuing.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="420"/>
        <source>~{s:.2f} s/origin on this network -&gt; ~{m:.1f} min for {n} origins.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/_matrix_base.py" line="426"/>
        <source>Estimated {m:.0f} min — consider fewer origins or a coarser grid.</source>
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="65"/>
        <source>Hex grid</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="72"/>
        <source>Population layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="79"/>
        <source>Population field</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="88"/>
        <source>Output (hex grid with population count)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="112"/>
        <source>Hex grid must be in a projected CRS with metric units (e.g. EPSG:2180, EPSG:3857). Got: {}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="118"/>
        <source>Population layer must be polygonal, got &apos;{}&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="126"/>
        <source>Population layer has no field &apos;{}&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="134"/>
        <source>Field &apos;{}&apos; must be numeric (Int or Float), got &apos;{}&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="141"/>
        <source>Output field &apos;population&apos; already exists in HEX_GRID. Remove it or rename it before running PopulationOverlay.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="150"/>
        <source>Reprojecting population layer from {} to {}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/population_overlay.py" line="312"/>
        <source>{} hexagon(s) have population = 0 (not covered by the population layer).</source>
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="85"/>
        <source>GUS NSP 2021 Excel file</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="85"/>
        <source>Excel files (*.xlsx)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="93"/>
        <source>Sheet name (empty = first sheet)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="101"/>
        <source>Population column name in Excel header</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="108"/>
        <source>Census tract geometry layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="115"/>
        <source>Join key field in geometry layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="123"/>
        <source>Output field name</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="130"/>
        <source>Output layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="151"/>
        <source>openpyxl is not available. If the automatic install at QGIS startup failed, install manually from the OSGeo4W Shell: python -m pip install openpyxl — then restart QGIS.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="170"/>
        <source>Loading Excel file: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="184"/>
        <source>Excel reader subprocess failed (exit {}):
{}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="197"/>
        <source>Multi-sheet workbook; using first sheet &apos;{}&apos;. All sheets: {}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="231"/>
        <source>Could not detect header row. Searched rows 0-29 for columns &apos;Symbol&apos; and &apos;Struktura&apos;. Check that the sheet &apos;{}&apos; is correct.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="242"/>
        <source>Column &apos;{}&apos; not found in header. Available columns near row {}: {}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="251"/>
        <source>Header: Symbol/Struktura at row {} (0-based), &apos;{}&apos; at row {}. Columns: Symbol={}, Struktura={}, {}={}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="306"/>
        <source>Row {}: census tract &apos;{}&apos; encountered without a preceding &apos;rejon statystyczny&apos; row. Cannot build join key.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="330"/>
        <source>Row {}: cannot interpret &apos;{}&apos; as a number in column &apos;{}&apos;. Expected a number, an empty cell, or &apos;-&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="352"/>
        <source>{} OBWOD symbol(s) appeared more than once; population values summed (GUS records split census tracts under the same symbol at administrative boundaries): {}{}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="362"/>
        <source>Excel extraction: {} tract rows, {} unique keys, {} &apos;-&apos; values converted to 0.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="374"/>
        <source>Geometry layer has no field &apos;{}&apos;. Available fields: {}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="418"/>
        <source>Key field &apos;{}&apos; is numeric; leading zeros may be lost when converting to string. Consider storing &apos;{}&apos; as a text field to preserve keys like &apos;0123456&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/prepare_population_layer.py" line="449"/>
        <source>None of the {} Excel rows match the geometry layer. Check that you provided the correct file for this region.</source>
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/run_accessibility.py" line="152"/>
        <source>Wrote {n} rows to {p}</source>
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="84"/>
        <source>Output OD lines (optional)</source>
        <translation>Wynikowe linie OD (opcjonalne)</translation>
    </message>
    <message>
        <location filename="../algorithms/run_travel_time_matrix.py" line="106"/>
        <source>Wrote {p}</source>
        <translation type="unfinished"></translation>
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
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="65"/>
        <source>Use the JDK path saved by &apos;Download R5 engine and Java 21&apos;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="72"/>
        <source>Java 21 binary (only if not using the saved path)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="84"/>
        <source>network.dat to probe with command=info (optional)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="95"/>
        <source>R5 version</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="114"/>
        <source>All checks passed.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="116"/>
        <source>One or more checks failed — see the steps above.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="124"/>
        <source>Step 1: Java 21 JDK</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="128"/>
        <source>  No JDK path saved. Run &apos;Download R5 engine and Java 21&apos;, or untick &apos;Use the saved JDK path&apos; and supply one.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="139"/>
        <source>  No JDK path given. Tick &apos;Use the saved JDK path&apos; or set one.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="146"/>
        <source>  OK: Java {} at {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="152"/>
        <source>Step 2: R5 jar</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="155"/>
        <source>  No R5 jar path saved. Run &apos;Download R5 engine and Java 21&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="161"/>
        <source>  R5 jar not found: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="164"/>
        <source>  Not a .jar file: {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="167"/>
        <source>  {} does not look like the R5 fat jar (size or contents wrong).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="175"/>
        <source>  SHA-256 mismatch for {}.
  expected {}
  got      {}
  Re-run &apos;Download R5 engine and Java 21&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="182"/>
        <source>  OK: {} (SHA-256 verified)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="186"/>
        <source>Step 3: Java runner</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="188"/>
        <source>  Skipped: fix steps 1 and 2 first.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="194"/>
        <source>  OK: compiled runner in {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="196"/>
        <source>  Compiled runner missing from {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="203"/>
        <source>  OK: source launcher will compile the runner per run ({})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="207"/>
        <source>  Runner source missing from {}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="209"/>
        <source>  Runner not set up. Run &apos;Download R5 engine and Java 21&apos;.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="215"/>
        <source>Step 4: command=info</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="217"/>
        <source>  Skipped (no network.dat supplied).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="220"/>
        <source>  Skipped: the runner is not ready.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="251"/>
        <source>  This is expected when the network was built with a different R5 version. It confirms the runner loads and the version guard works.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../algorithms/test_r5_setup.py" line="265"/>
        <source>  R5 version: {}</source>
        <translation type="unfinished"></translation>
    </message>
</context>
</TS>
