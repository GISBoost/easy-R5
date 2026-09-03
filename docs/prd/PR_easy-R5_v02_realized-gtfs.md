# PRD — Easy-R5 v0.2 · Pobieranie zrealizowanego GTFS z gtfs-dashboard

**Status:** ✅ zaimplementowane (R0–R4), 2026-09-03. `metadata.txt` `0.2.0`.
Zweryfikowane end-to-end w QGIS 3.40 (`processing.run` + okno) na lokalnym
serwerze z fałszywym manifestem: pobranie do katalogu per-wariant, idempotencja,
błędy „brak daty" / „brak wariantu", kaskada miasto→miesiąc→dzień, znacznik
„⟂ partial", wyszarzanie niedostępnych wariantów, sprzątanie menu w `unload()`.
30 nowych testów pytest (`test_downloads`, `test_gtfs_dashboard`,
`test_realized_gtfs_flow`). **Zostaje:** przebieg na realnym manifeście
gtfs-dashboard i realnym assecie (rozmiar, ew. górny katalog w zipie);
tłumaczenie PL nowych stringów (issue #1).
**Data:** 2026-09-03
**Autor:** Michał Kaczorowski
**Kontekst wymagany do pracy:** ten plik + `PR_easy-R5_v01.md` (v0.1, frozen) +
`CLAUDE.md` + `CONTEXT.md` + `docs/notes/roadmap-candidates.md` §3 (uzasadnienie i dowody).

> Ten PRD opisuje **jeden element v0.2**: sposób, w jaki użytkownik Easy-R5 pobiera
> „zrealizowany" GTFS (P50/P85) albo rozkładowy GTFS z danego dnia z serwisu
> [`gisboost.github.io/gtfs-dashboard`](https://gisboost.github.io/gtfs-dashboard/),
> bez ręcznego grzebania w GitHub Releases. Reszta zakresu v0.2 (metryka minut obsługi,
> `CompareScenarios`, `CheckTransitData`, `DownloadTransitData`) ma osobne PRD.
> **Nie wybiegaj naprzód.**

---

## 0. Po co to jest

**Problem użytkownika.** `easy-GTFS-RT` codziennie publikuje zrekonstruowany („co się
faktycznie wydarzyło") GTFS dla ~25 miast — jeden GitHub Release na miasto na dzień, już
513 wpisów. Lista Releases przestała być przeglądalna; `gtfs-dashboard` rozwiązuje to dla
przeglądarki (drill-down miasto → miesiąc → dzień). Dla Easy-R5 **to jedyna droga, którą
informacja realtime może w ogóle wejść do wtyczki** (R5 nie czyta GTFS-RT —
`CONTEXT.md`, `r5-vs-otp.md`). Dziś użytkownik musiałby: wejść na dashboard, znaleźć dzień,
skopiować URL assetu z Release'a, wkleić do przeglądarki, rozpakować, wskazać `BuildNetwork`.
Chcemy: **wybierz miasto → miesiąc → dzień → wariant → Pobierz**, i plik ląduje w
katalogu gotowym pod `BuildNetwork`.

**Dlaczego to tanie.** ~90% mechaniki (`urllib` z paskiem postępu i anulowaniem, bezpieczne
rozpakowanie zip, QSettings) już istnieje w `algorithms/download_r5.py`. Manifest
`gtfs-dashboard` **już zawiera bezpośrednie URL-e do assetów Release'ów** — nie ma potrzeby
odpytywać GitHub REST API (i jego limitu 60 req/h). Patrz `roadmap-candidates.md` §3 z
cytatami źródeł.

**Zakres.** Trzy nowe moduły + jeden refactor + podpięcie do menu wtyczki:
`core/downloads.py` (refactor), `core/gtfs_dashboard.py`, `algorithms/download_realized_gtfs.py`,
`gui/download_recordings_dialog.py`.

---

## 1. Decyzja architektoniczna: algorytm Processing vs osobne okno

**To jest pytanie, które trzeba rozstrzygnąć przed kodowaniem. Rozstrzygnięcie: HYBRYDA —
osobne okno dialogowe jako główny UX + cienki algorytm Processing pod spodem.**

### Dlaczego nie sam algorytm Processing

Kaskadowy wybór miasto → miesiąc → dzień z **danych na żywo** jest niewyrażalny w modelu
parametrów Processing:

- Parametry algorytmu są definiowane **statycznie** w `initAlgorithm()` i budowane raz,
  zanim okno się pokaże. Nie ma reaktywności „gdy zmieni się parametr A, przelicz opcje
  parametru B" — `QgsProcessingParameterEnum` ma listę opcji zamrożoną na starcie.
- Żeby `Enum` „miasto" był wypełniony realnymi danymi, `initAlgorithm()` musiałby pobrać
  manifest (**906 KB, rośnie**) przy **każdym otwarciu okna algorytmu** — blokujące I/O
  w wątku GUI, i pusta lista przy braku sieci.
- Wariant „jeden płaski `Enum` ze wszystkimi kombinacjami" = **513 dni × 2–3 warianty ≈
  1200–1500 pozycji** w jednym dropdownie. Bezużyteczne.
- Wariant „`CITY` jako `Enum` (25 pozycji, OK) + `DATE` jako wolny `String`" — miasto
  odkrywalne, ale data nie; użytkownik i tak musi zerknąć na dashboard, żeby wiedzieć,
  które dni istnieją. To nie jest „wybór taki sam jak na stronie".

### Dlaczego nie samo okno dialogowe

- Traci skryptowalność (`processing.run`, modele graficzne, batch), historię i logi
  Processing, oraz izolowaną testowalność mechaniki pobierania.
- Easy-R5 **jest** z założenia providerem Processing (`CLAUDE.md` §Architektura); easy-OTP
  nie ma **ani jednego** `QDialog` — cała funkcjonalność to algorytmy. Okno to odstępstwo,
  które trzeba świadomie ograniczyć.

### Hybryda — jak to się składa

```
gui/download_recordings_dialog.py   (GŁÓWNY UX — „głupi" wybierak)
    │  pobiera manifest raz, przy otwarciu (async, ze spinnerem)
    │  3 kaskadowe QComboBox: miasto → miesiąc → dzień  + wariant + folder
    │  „Pobierz"  ─────────────────────────────┐
    │                                          ▼
    │                       processing.run("easyr5:downloadrealizedgtfs", {...})
    │
algorithms/download_realized_gtfs.py   (MECHANIKA — źródło prawdy, testowalne)
    │  parametry: CITY, DATE, VARIANT, TARGET_FOLDER, MANIFEST_URL(adv)
    │  fetch manifest (cache) → resolve URL → download → integrity → unzip
    │  → katalog rozdzielony per wariant → QSettings → zwróć ścieżkę
    │
core/gtfs_dashboard.py    (klient manifestu — czysty Python, unit-test)
core/downloads.py         (współdzielone HTTP + zip, refactor z download_r5)
```

- **Logika pobierania jest w jednym miejscu** (algorytm). Okno to ~180 linii powłoki, która
  woła `processing.run`. Zero duplikacji.
- **Algorytm działa też samodzielnie** w Toolboxie — dla użytkownika, który zna klucz
  miasta i datę, dla modeli Processing i batcha.
- **Manifest pobierany raz na sesję** i cache'owany (`core/gtfs_dashboard`), więc `fetch`
  w algorytmie zaraz po tym, jak okno wypełniło dropdowny, to trafienie w cache.

### Koszt odstępstwa (świadomy, ograniczony)

Pierwszy kod GUI we wtyczce → nowy pakiet `easy_r5/gui/`, podpięcie akcji menu w
`EasyR5Plugin.initGui()`, sprzątanie w `unload()`. Nic poza tym oknem nie dostaje GUI.

---

## 2. Kolejność wdrożenia i mapa zależności

| # | Element | Nakład | Wymaga | Komentarz |
|---|---|---|---|---|
| R0 | refactor: `core/downloads.py` | S | — | Wyciągnij współdzielone helpery z `download_r5.py`; `DownloadR5` woła je zamiast metod prywatnych. |
| R1 | `core/gtfs_dashboard.py` | S | R0 nie wymagane | Klient manifestu: fetch + cache + parse + `resolve_asset`. Czysty Python, unit-test na fixture. |
| R2 | `algorithms/download_realized_gtfs.py` | S–M | R0, R1 | Algorytm Processing, grupa Setup. |
| R3 | `gui/download_recordings_dialog.py` + podpięcie w `easy_r5_plugin.py` | M | R1, R2 | Pierwszy kod GUI. |
| R4 | i18n (`easy_r5_pl.ts`), README, `metadata.txt` 0.2.0, `provider.py` | S | R2, R3 | |

```
R0 (core/downloads) ──► R2 ──► R3
R1 (core/gtfs_dashboard) ──┤ └──► R3
                           └──────┘
```

Wykonaj strikte w tej kolejności — każdy krok konsumuje produkt poprzedniego.

---

## R0 — `core/downloads.py` (współdzielone HTTP + rozpakowanie)

### Cel i wartość

`DownloadR5` ma prywatne metody `_download`, `_safe_zipextract`, `_safe_tarextract`,
`_check_writable`, `_check_disk`. `DownloadRealizedGtfs` potrzebuje trzech z nich. W obrębie
jednej wtyczki współdzielenie idzie przez `core/` (`CLAUDE.md` §Architektura: „Logika w
`core/`"). Wyciągamy je do jednego modułu, `DownloadR5` woła moduł.

### Kontekst i zależności

- Źródło: `easy_r5/algorithms/download_r5.py:359–456` (`_check_writable`, `_check_disk`,
  `_download`, `_rm`, `_safe_zipextract`, `_safe_tarextract`).
- Te metody dziś przyjmują `QgsProcessingMultiStepFeedback` i wołają `self.tr(...)`. Nowa
  wersja bierze **`feedback` (dowolny `QgsFeedback`/`QgsProcessingFeedback`)** i **gotowe
  stringi** (tłumaczenie zostaje po stronie wołającego algorytmu, bo `core/` nie ma
  kontekstu `tr()` — dokładnie jak `core/matrix.py` dziś).
- Bez importu `qgis` na poziomie modułu poza tym, co konieczne — `download` używa tylko
  `urllib`, `pathlib`, `shutil`, `zipfile`, `tarfile`. `QgsProcessingException` podnosi
  wołający, nie `core/`.

### Sygnatury (docelowe)

```python
# core/downloads.py
class DownloadError(RuntimeError): ...          # wołający mapuje na QgsProcessingException
class DownloadCancelled(RuntimeError): ...

def check_writable(path: Path) -> None           # raise DownloadError
def check_free_space(path: Path, need_mb: int) -> None
def download_file(url: str, dest: Path, *, feedback, user_agent: str,
                  timeout: int = 60, expected_bytes: int | None = None,
                  progress_range: tuple[int, int] = (0, 100)) -> None
    # chunked; feedback.isCanceled() -> DownloadCancelled + sprząta .tmp;
    # zapis do dest.with_suffix('.tmp'), potem atomowy rename;
    # jeśli expected_bytes podane i Content-Length inny -> DownloadError
def safe_extract_zip(zip_path: Path, dest_dir: Path) -> list[str]   # zip-slip-safe, zwraca listę wpisów
def safe_extract_tar(tar_path: Path, dest_dir: Path) -> None
```

### Algorytm krok po kroku

1. Przenieś ciało metod 1:1, zamień `multi.pushInfo/pushWarning` na `feedback.pushInfo/…`
   i `self.tr("…")` na argument stringowy (albo goły string — wołający z algorytmu owinie).
2. `_download` dziś liczy postęp w oknie `step_start..step_start+step_count` z 12-krokowego
   `MultiStepFeedback`. Nowa `download_file` bierze `progress_range=(lo, hi)` i mapuje
   `done/total` w ten przedział przez `feedback.setProgress`.
3. W `download_r5.py` zamień wywołania: `self._download(...)` → `downloads.download_file(...)`,
   `self._safe_zipextract` → `downloads.safe_extract_zip`, itd. Usuń martwe metody prywatne.
4. `except downloads.DownloadCancelled` / `DownloadError` w `DownloadR5.processAlgorithm`
   → `QgsProcessingException` (albo ciche `return {}` przy anulowaniu, jak dziś).

### Edge cases

- `download_file` przy 0-bajtowej odpowiedzi lub `Content-Length: 0` → `DownloadError`
  („serwer zwrócił pusty plik").
- Rename `.tmp` → `dest` na Windows, gdy `dest` istnieje: `os.replace` (atomowy, nadpisuje).
- Anulowanie w środku: zamknij uchwyt, skasuj `.tmp`, podnieś `DownloadCancelled`.

### Kryteria akceptacji

- `DownloadR5` po refaktorze przechodzi te same testy co dziś (`test_download_*` jeśli są;
  jeśli nie — ręczny przebieg M1 bez regresji).
- Nowy `test_downloads.py`: `safe_extract_zip` odrzuca wpis `../escape` i ścieżkę absolutną
  (przeniesione z `test_dependencies.py` wzorzec); `download_file` z lokalnym `file://` albo
  z `http.server` w fixture — pobiera, liczy postęp, honoruje `expected_bytes`.
- `flake8` czysto, `bandit` czysto (przenieś `# nosec B310` z komentarzem).

---

## R1 — `core/gtfs_dashboard.py` (klient manifestu)

### Cel i wartość

Jedno miejsce, które wie, jak wygląda `manifest.json` gtfs-dashboard. Oddziela interfejs
wtyczki od wewnętrznej struktury `easy-GTFS-RT` (nazw tagów, konwencji Release'ów) — jeśli
kiedyś zmieni się sposób publikacji, psuje się tylko ten moduł, dopóki manifest ma stabilny
schemat.

### Kontekst i zależności

- Schemat (potwierdzony z `../gtfs-dashboard/manifest.json`, 25 miast / 513 dni):

  ```json
  {
    "generated_at": "2026-08-15T...Z",
    "source_repo": "GISBoost/easy-GTFS-RT",
    "cities": {
      "lodz": {
        "display_name": "Łódź",
        "days": [
          {
            "date": "2026-07-13",
            "status": "ok" | "partial",
            "created_at": "2026-07-13T11:18:32Z",
            "coverage_ranges": ["12:46-17:11", ...],
            "assets": {
              "p50": "https://github.com/GISBoost/easy-GTFS-RT/releases/download/<tag>/lodz_realized_2026-07-13_p50.zip",
              "p85": "https://github.com/.../lodz_realized_2026-07-13_p85.zip",
              "static_gtfs": "https://github.com/.../lodz_static_gtfs_2026-07-13.zip",
              "diff_chart": null, "diff_summary": null, "tidy_table": null
            }
          }
        ]
      }
    },
    "raw_snapshot_archives": [ ... ]   // pomijamy — to surowe pozycje, nie GTFS
  }
  ```

- URL manifestu: stała `MANIFEST_URL = "https://gisboost.github.io/gtfs-dashboard/manifest.json"`.
  Nadpisywalna przez QSettings `easy_r5/manifest_url` (self-hosting / testy).
- Serwowany przez CDN GitHub Pages (Fastly), **nie** przez `api.github.com` — brak limitu
  REST API. Patrz `roadmap-candidates.md` §3.

### Sygnatury (docelowe)

```python
# core/gtfs_dashboard.py
MANIFEST_URL = "https://gisboost.github.io/gtfs-dashboard/manifest.json"
VARIANTS = ("p50", "p85", "static_gtfs")            # kolejność = domyślny priorytet
_GTFS_REQUIRED = ("agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt")

class ManifestError(RuntimeError): ...

def fetch_manifest(*, url: str | None = None, cache_dir: Path | None = None,
                   max_age_s: int = 86400, feedback=None, force: bool = False) -> dict
    # 1. jeśli w pamięci procesu i świeży -> zwróć
    # 2. GET url (urllib, User-Agent, timeout 30) -> parse -> slim -> zapisz do pamięci
    #    i do cache_dir/gtfs_dashboard_manifest.json
    # 3. przy błędzie sieci: jeśli jest cache na dysku -> zwróć z flagą {"_stale": true, "_error": "..."}
    #    inaczej -> ManifestError z radą (link do dashboardu i do Releases)

def slim(manifest: dict) -> dict
    # zostaw tylko cities.<k>.{display_name, days[].{date, status, assets:{p50,p85,static_gtfs}}}
    # + generated_at; wyrzuć coverage_ranges, delay_stats, raw_snapshot_archives, itd.

def cities(manifest: dict) -> list[tuple[str, str]]           # [(key, display_name)] sortowane po display_name
def months(manifest: dict, city_key: str) -> list[str]        # ["2026-08", "2026-07", ...] malejąco
def days(manifest: dict, city_key: str, month: str) -> list[dict]   # [{date, status, assets}] malejąco
def resolve_asset(manifest: dict, city_key: str, date: str, variant: str) -> str
    # zwróć URL albo ManifestError:
    #   - nieznane miasto -> lista dostępnych kluczy
    #   - brak daty -> "miasto <X> ma dni: 2026-08-15, 2026-08-14, ... (najbliższe do <date>)"
    #   - assets[variant] is None -> "dla <miasto> <data> nie ma wariantu <variant>; dostępne: p50, static_gtfs"

def looks_like_gtfs(directory: Path) -> bool
    # wszystkie _GTFS_REQUIRED obecne + (calendar.txt OR calendar_dates.txt)
```

### Edge cases i walidacja

- Manifest z `cities: {}` albo bez klucza `cities` → `ManifestError` („manifest pusty lub
  w nieznanym formacie — zgłoś na easy-GTFS-RT").
- `date` w złym formacie w argumencie `resolve_asset` → `ManifestError` przed lookupem.
- Miasto z `days: []` → w oknie wyszarz, w algorytmie `ManifestError`.
- `generated_at` starszy niż ~48 h → nie błąd, ale `feedback.pushWarning` w algorytmie
  („manifest z <data> — pipeline mógł się zatrzymać").
- `_stale` cache → algorytm robi `pushWarning`, okno pokazuje pasek „offline — dane z <data>".

### Testy (`test_gtfs_dashboard.py`, czysty pytest)

Fixture: skopiuj `../gtfs-dashboard/manifest.sample.json` do `easy_r5/test/fixtures/manifest.json`.

- `slim` wyrzuca `coverage_ranges` / `raw_snapshot_archives`, zostawia `assets`.
- `cities` posortowane po `display_name`, `months` malejąco, `days` malejąco.
- `resolve_asset` happy path zwraca dokładny URL z fixture.
- `resolve_asset` nieznane miasto / brak daty / `variant=None` → `ManifestError` z sensownym
  komunikatem (asercja na fragment tekstu).
- `looks_like_gtfs`: katalog z kompletem plików → `True`; bez `stop_times.txt` → `False`;
  z `calendar_dates.txt` bez `calendar.txt` → `True`.
- `fetch_manifest` z `url="file://.../fixtures/manifest.json"` → parsuje; z URL-em 404 i
  cache na dysku → zwraca `_stale`; bez cache → `ManifestError`.

---

## R2 — `algorithms/download_realized_gtfs.py` (`DownloadRealizedGtfs`)

### Cel i wartość

Mechanika: z (miasto, data, wariant) zrób katalog GTFS gotowy pod `BuildNetwork`. Jedno
źródło prawdy dla okna i dla użytkownika Toolboxa/batcha.

### Kontekst i zależności

- Grupa Processing: **Setup** (`groupId="setup"`), obok `DownloadR5`, `BuildNetwork`.
- `name="downloadrealizedgtfs"`, kontekst `tr()` = `"DownloadRealizedGtfs"`.
- Konsumuje `core.gtfs_dashboard` (R1) i `core.downloads` (R0).
- **Gotcha z `CLAUDE.md`:** zrealizowany (`p50`/`p85`) i statyczny GTFS mają te same
  `trip_id`/`stop_id` — **nie mogą leżeć w jednym katalogu budowy sieci**. Każdy wariant
  do własnego katalogu.
- Brak SHA — manifest nie niesie hashy. Integralność: `Content-Length` + `zipfile.testzip()`
  + `looks_like_gtfs`. Udokumentować jako lukę vs `DownloadR5` (który pinuje SHA-256).

### Parametry algorytmu QGIS

| param | typ | domyślnie | uwagi |
|---|---|---|---|
| `CITY` | `String` | — | klucz miasta z manifestu (np. `krakow`). Nie `Enum` — `Enum` wymagałby fetchu w `initAlgorithm`. `shortHelpString` mówi „użyj okna *Easy-R5 → Pobierz nagrania przejazdów…* dla wyboru z listy". |
| `DATE` | `String` | — | `yyyy-MM-dd`. |
| `VARIANT` | `Enum` | `0` (`p50`) | opcje: `Zrealizowany P50` / `Zrealizowany P85` / `Rozkładowy (statyczny)` → mapa na `p50`/`p85`/`static_gtfs`. |
| `TARGET_FOLDER` | `File` (Folder) | QSettings `easy_r5/transit_data_folder`, fallback `cache_folder`, fallback temp | |
| `MANIFEST_URL` | `String`, **advanced** | `""` → `gtfs_dashboard.MANIFEST_URL` (albo QSettings) | override do testów/self-hostu. |
| `OUTPUT_FOLDER` | wyjście: `String` (folder) | — | ścieżka rozpakowanego GTFS (do łańcuchowania w modelu). |

Bez `QgsProcessingParameterDateTime` tutaj — istnieje od QGIS 3.14 (jest w 3.22), ale
wolne pole daty zapraszałoby 404; w oknie data jest `Enum` z manifestu. (Natywny date-param
warto osobno rozważyć dla `DATE` w `RunTravelTimeMatrix` — poza zakresem tego PRD.)

### Algorytm krok po kroku

`processAlgorithm` → `QgsProcessingMultiStepFeedback(5, feedback)`:

1. **Krok 0 — parametry i manifest.**
   `city = parameterAsString(CITY).strip()`, `date`, `variant = VARIANTS[enum]`,
   `target = Path(parameterAsFile(TARGET_FOLDER))`.
   Walidacja `date` regexem `^\d{4}-\d{2}-\d{2}$` → `QgsProcessingException`.
   `downloads.check_writable(target)`; `target.mkdir(parents=True, exist_ok=True)`.
   `manifest = gtfs_dashboard.fetch_manifest(url=..., cache_dir=Path(cache_folder), feedback=multi)`.
   `except gtfs_dashboard.ManifestError as e: raise QgsProcessingException(str(e))`.
   Jeśli `manifest.get("_stale")` → `multi.pushWarning(...)`.
   Jeśli `generated_at` > 48 h → `multi.pushWarning(...)`.

2. **Krok 1 — rozwiąż URL.**
   `url = gtfs_dashboard.resolve_asset(manifest, city, date, variant)` (łapie i re-raise
   jako `QgsProcessingException` z listą dostępnych dni/wariantów).
   Znajdź wpis dnia; jeśli `status == "partial"` →
   `multi.pushWarning("Nagranie z {date} jest częściowe (luki w pokryciu) — rozkład dla
   części kursów pochodzi z danych statycznych.")`.

3. **Krok 2 — katalog docelowy (rozdzielony per wariant).**
   `variant_dir = target / "transit-recordings" / city / date / {p50,p85,static}[variant]`.
   `short = {"p50":"p50","p85":"p85","static_gtfs":"static"}[variant]`.
   Jeśli `variant_dir` istnieje i `looks_like_gtfs` → `multi.pushInfo("Już pobrane: {dir}")`,
   przeskocz do kroku 4 (idempotencja; `FORCE_REDOWNLOAD` advanced boolean jak
   `FORCE_REBUILD` w `BuildNetwork` — domyślnie `False`).
   `downloads.check_free_space(target, 200)`.

4. **Krok 3 — pobierz.**
   `tmp_zip = variant_dir.parent / f"{short}.zip"`.
   `downloads.download_file(url, tmp_zip, feedback=multi, user_agent=pins.USER_AGENT,
   progress_range=(20, 80))`.
   `except downloads.DownloadCancelled: raise QgsProcessingException(tr("Anulowano."))`.

5. **Krok 4 — integralność + rozpakuj.**
   `zipfile.ZipFile(tmp_zip).testzip()` — jeśli nie `None` → `QgsProcessingException`
   („pobrany plik jest uszkodzony — spróbuj ponownie").
   Wyczyść `variant_dir` (jeśli nadpisujemy), `downloads.safe_extract_zip(tmp_zip, variant_dir)`.
   Jeśli w zipie jest pojedynczy górny katalog (`lodz_realized_.../`) — spłaszcz o jeden
   poziom, żeby `stops.txt` był bezpośrednio w `variant_dir`.
   `if not gtfs_dashboard.looks_like_gtfs(variant_dir): raise QgsProcessingException(
   "Rozpakowany plik nie wygląda jak GTFS (brak: <lista>).")`.
   `tmp_zip.unlink(missing_ok=True)`.

6. **Zakończenie.**
   `settings.set_("last_gtfs_folder", str(variant_dir))` (klucz, który `BuildNetwork`
   czyta jako domyślną wartość `GTFS_FOLDER` — patrz „Otwarte pytania" #4).
   `multi.pushInfo(tr("GTFS gotowy: {dir}\nUżyj go jako 'GTFS folder' w Build R5 network."))`.
   `return {self.OUTPUT_FOLDER: str(variant_dir)}`.

Wszystkie zasoby (`tmp_zip`, uchwyty) sprzątane w `finally`.

### Pliki referencyjne / wzorzec do portu

- `easy_r5/algorithms/download_r5.py` — struktura klasy, `MultiStepFeedback`, `settings`,
  łapanie `Cancelled`, komunikaty OOM/miejsca na dysku.
- `easy_r5/algorithms/build_network.py` — wzorzec `FORCE_*` boolean, walidacja katalogu.
- `../easy-OTP/easy_otp/algorithms/download_transit_data.py` — wzorzec „pobierz dane
  tranzytowe do wskazanego folderu", komunikaty.

### Edge cases i walidacja

- `CITY` z literówką → `ManifestError` z listą kluczy (`resolve_asset`).
- Podana data istnieje dla miasta, ale wybrany wariant to `null` → jasny komunikat +
  lista wariantów, które są.
- Sieć pada w trakcie pobierania → `.tmp` skasowany, `DownloadError`, `variant_dir`
  nietknięty.
- Rozpakowany katalog istnieje, ale niekompletny (poprzednie pobranie przerwane) →
  `looks_like_gtfs` = `False` → normalne ponowne pobranie (nie traktuj jako „już pobrane").
- Zip z path-traversal → `safe_extract_zip` pomija (test w R0).
- `TARGET_FOLDER` = katalog systemowy bez praw zapisu → `check_writable` → rada „wybierz
  folder w profilu użytkownika".

### Tryb błędu i komunikaty

Każdy `QgsProcessingException` niesie konkretną radę, nie surowy wyjątek (`PRD_v01 §5.1`):

| sytuacja | komunikat |
|---|---|
| brak sieci, brak cache | „Nie udało się pobrać listy nagrań z gtfs-dashboard i nie ma kopii lokalnej. Sprawdź połączenie albo pobierz ręcznie: github.com/GISBoost/easy-GTFS-RT/releases" |
| nieznane miasto | „Miasto '<x>' nie ma nagrań. Dostępne: krakow, lodz, poznan, … (użyj klucza, nie nazwy wyświetlanej)." |
| brak daty | „<Miasto> nie ma nagrania z <data>. Najbliższe: <d1>, <d2>, <d3>." |
| brak wariantu | „<Miasto> <data>: nie ma wariantu 'P85'. Dostępne: P50, Rozkładowy." |
| uszkodzony zip | „Pobrany plik jest uszkodzony (błąd CRC). Uruchom ponownie." |
| nie-GTFS | „Rozpakowany plik nie wygląda jak GTFS — brak: stop_times.txt. Zgłoś na easy-GTFS-RT." |

### Kryteria akceptacji

- Algorytm zarejestrowany w `provider.py`, widoczny w grupie Setup.
- `processing.run("easyr5:downloadrealizedgtfs", {"CITY":"lodz","DATE":"<realna data>",
  "VARIANT":0,"TARGET_FOLDER":"<tmp>"})` pobiera i rozpakowuje realny GTFS; `looks_like_gtfs`
  = `True`; `OUTPUT_FOLDER` wskazuje na katalog z `stops.txt`.
- Ta sama komenda drugi raz → „już pobrane", brak ruchu sieciowego (chyba że `FORCE_REDOWNLOAD`).
- Zła data → wyjątek z listą dostępnych dni.
- `p50` i `static` tego samego dnia lądują w **osobnych** katalogach.
- Anulowanie w trakcie pobierania → brak `.tmp`, brak połowicznego `variant_dir`, brak
  osieroconych wątków.
- `flake8` + `bandit` czysto. Unit-testy R1 zielone (algorytm sam w sobie wymaga QGIS —
  weryfikacja ręczna wg listy powyżej).

### Otwarte pytania / spike'y

- Czy zipy z `easy-GTFS-RT` mają górny katalog, czy pliki GTFS w korzeniu? → sprawdzić
  jeden realny asset przy implementacji, ustawić logikę spłaszczania.
- Rozmiar realnego assetu (do `check_free_space` i komunikatu „~X MB")? → zmierzyć.

---

## R3 — `gui/download_recordings_dialog.py` + podpięcie do menu

### Cel i wartość

UX, który użytkownik opisał: „wybór taki sam jak na stronie — miasto, miesiąc, dzień,
klikasz Pobierz". Kaskadowe dropdowny z danych na żywo.

### Kontekst i zależności

- Nowy pakiet `easy_r5/gui/` (`__init__.py` + `download_recordings_dialog.py`).
- Bez `.ui` — layout budowany w kodzie (mały, jeden ekran; brak zależności od
  `uic`/zasobów). Zgodne z „tylko PyQGIS + biblioteki z dystrybucji QGIS".
- `QDialog` z `QgsGui`/`qgis.PyQt.QtWidgets`. Fetch manifestu: `QgsTask` (wątek roboczy
  QGIS) albo `QThread` — **nie** blokować GUI.
- Konsumuje `core.gtfs_dashboard` (R1); pobieranie deleguje do `processing.run` (R2).

### Layout (jeden ekran)

```
┌─ Pobierz nagrania przejazdów (gtfs-dashboard) ──────────────┐
│  [ pasek statusu: „Łączenie z serwerem…” / „dane z 2026-08-15” ] │
│                                                             │
│  Miasto:   [ Łódź                    ▾ ]                     │
│  Miesiąc:  [ 2026-08                 ▾ ]                     │
│  Dzień:    [ 2026-08-14  ⚠ częściowy ▾ ]                     │
│  Wariant:  ( ) Zrealizowany P50                              │
│            ( ) Zrealizowany P85                              │
│            (•) Rozkładowy (statyczny)                        │
│                                                             │
│  Folder docelowy: [ C:\…\transit-data          ] [ … ]      │
│                                                             │
│  [ szczegóły dnia: 159 761 obserwacji, pokrycie 12:46–22:00 ]│
│                                                             │
│            [ Pobierz ]   [ Zamknij ]                         │
└─────────────────────────────────────────────────────────────┘
```

### Zachowanie krok po kroku

1. **`__init__`** — zbuduj layout, wyłącz wszystkie kontrolki poza „Zamknij", ustaw pasek
   statusu „Łączenie z serwerem…". Wystartuj fetch manifestu w tle
   (`QgsApplication.taskManager().addTask(QgsTask.fromFunction(...))` albo lekki `QThread`).
2. **fetch OK** → `self._manifest = slim(...)`; wypełnij `cityCombo`
   (`gtfs_dashboard.cities`, `userData=key`); status: `„dane z {generated_at}”` (+ „(offline)"
   jeśli `_stale`). Włącz kontrolki.
3. **fetch błąd** → status na czerwono + link „Otwórz Releases w przeglądarce"
   (`QDesktopServices.openUrl`); „Pobierz" nieaktywne; przycisk „Spróbuj ponownie".
4. **`cityCombo` zmiana** → `monthCombo` = `gtfs_dashboard.months(manifest, key)`; wyczyść
   `dayCombo`.
5. **`monthCombo` zmiana** → `dayCombo` = `gtfs_dashboard.days(manifest, key, month)`;
   label = `f"{date}  {'⚠ częściowy' if status=='partial' else ''}"`, `userData=day_dict`.
6. **`dayCombo` / wariant zmiana** → pokaż „szczegóły dnia" (obserwacje, pokrycie); wyszarz
   warianty, których `assets[...]` jest `null`; włącz „Pobierz" gdy komplet.
7. **Folder** — `QgsFileWidget(storageMode=GetDirectory)`, prefill z QSettings
   `easy_r5/transit_data_folder`.
8. **„Pobierz"** →
   - zapisz folder do QSettings;
   - `params = {"CITY": key, "DATE": date, "VARIANT": variant_idx, "TARGET_FOLDER": folder}`;
   - uruchom `processing.run("easyr5:downloadrealizedgtfs", params, feedback=fb)` gdzie
     `fb` jest podpięte pod modalny `QgsProcessingFeedback` + `QProgressDialog` (albo,
     lepiej, `QgsProcessingAlgRunnerTask` — patrz spike);
   - sukces → `QMessageBox` „Pobrano do <ścieżka>" z przyciskami „Otwórz folder" i
     „Ustaw jako źródło GTFS w Build network" (zapis QSettings `last_gtfs_folder`);
   - błąd → `QMessageBox.warning` z `str(exc)`.
9. **`unload`** okna nie dotyczy — okno jest modalne/bezstanowe; ale akcja menu i toolbar
   muszą zostać usunięte w `EasyR5Plugin.unload()`.

### Podpięcie w `easy_r5_plugin.py`

```python
def initGui(self):
    ...  # istniejące: bootstrap openpyxl, rejestracja providera
    from .gui.download_recordings_dialog import DownloadRecordingsDialog
    self._dl_action = QAction(
        QIcon(os.path.join(os.path.dirname(__file__), "resources", "icon.svg")),
        self.tr("Download transit recordings…"), self.iface.mainWindow())
    self._dl_action.triggered.connect(self._open_download_recordings)
    self.iface.addPluginToMenu("Easy-R5", self._dl_action)

def _open_download_recordings(self):
    from .gui.download_recordings_dialog import DownloadRecordingsDialog
    DownloadRecordingsDialog(self.iface.mainWindow()).exec()

def unload(self):
    if getattr(self, "_dl_action", None) is not None:
        self.iface.removePluginMenu("Easy-R5", self._dl_action)
        self._dl_action = None
    ...  # istniejące: usunięcie providera, translatora
```

Import `DownloadRecordingsDialog` **leniwy** (w `_open_...`), żeby błąd w GUI nie wywalił
`initGui` — best-effort, jak bootstrap openpyxl.

### Edge cases

- Użytkownik otwiera okno bez sieci → stan „błąd + Releases + Spróbuj ponownie", okno
  nie wisi.
- Miasto bez dni w wybranym miesiącu → `dayCombo` pusty, „Pobierz" nieaktywne.
- Zamknięcie okna w trakcie fetchu → `QgsTask` anulowany w `closeEvent`.
- Podwójne kliknięcie „Pobierz" → przycisk `setEnabled(False)` na czas `processing.run`.

### Kryteria akceptacji (ręczne, w QGIS)

- Menu *Wtyczki → Easy-R5 → Download transit recordings…* otwiera okno; po ~1 s dropdowny
  wypełnione realnymi miastami.
- Kaskada działa: zmiana miasta przeładowuje miesiące, zmiana miesiąca — dni.
- „⚠ częściowy" pokazuje się dla dni ze `status: partial`.
- „Pobierz" ściąga plik, pokazuje postęp, kończy `QMessageBox` ze ścieżką; plik jest na
  dysku w `…/transit-recordings/<miasto>/<data>/<wariant>/` i wygląda jak GTFS.
- „Ustaw jako źródło GTFS" sprawia, że `BuildNetwork` otwiera się z tym folderem
  wypełnionym.
- Wyłączenie sieci → okno pokazuje błąd z linkiem, nie crashuje QGIS.
- `unload` (wyłączenie wtyczki) usuwa pozycję z menu; brak wyjątków w logu.

### Otwarte pytania / spike'y

- **`processing.run` modalnie vs `QgsProcessingAlgRunnerTask`** — najpierw spróbuj prostej
  ścieżki (modalny `QProgressDialog` + `QgsProcessingFeedback`); jeśli UX zamrożenia jest
  zły, przełącz na `AlgRunnerTask`. Rozstrzygnąć na etapie kodu.
- **Fetch manifestu: `QgsTask` vs `QgsNetworkContentFetcher` vs `QThread`** — `QgsTask`
  jest najbardziej QGIS-owy i ma anulowanie; wybrać przy implementacji.
- Czy `display_name` w manifeście jest zawsze obecny i po polsku? (sample: tak). Fallback:
  klucz.

---

## R4 — i18n, dokumentacja, metadane

- **i18n:** wszystkie nowe stringi UI przez `self.tr(...)` (algorytm) i `self.tr(...)`
  (okno, kontekst `"DownloadRecordingsDialog"`). Po kodzie: `pylupdate5` → uzupełnić
  `easy_r5_pl.ts` → `lrelease` (kolejność i narzędzia jak w handoffie M5).
- **README:** nowa sekcja „Getting archival / realized GTFS" — co to jest, że indeksuje
  **nagrania GISBoost dla ~25 miast w konkretne dni**, że to **nie** ogólne źródło GTFS
  (to zadanie `DownloadTransitData`), i uwaga o braku weryfikacji SHA.
- **`metadata.txt`:** `version=0.2.0`, blok changelog `0.2.0` (`feat(setup):
  DownloadRealizedGtfs`, `feat(gui): download-recordings dialog`, `refactor(core):
  downloads`). `experimental` zostaje `True` do przebiegu na czystym profilu.
- **`provider.py`:** `addAlgorithm(DownloadRealizedGtfs())`.
- **`CLAUDE.md`:** dopisać do „Architektura" jedno zdanie, że `gui/` istnieje wyłącznie dla
  okna pobierania nagrań (żeby następny agent nie potraktował tego jako pozwolenia na GUI
  wszędzie).

---

## Testy — zbiorczo

| plik | co | wymaga QGIS |
|---|---|---|
| `test_downloads.py` | `safe_extract_zip` (zip-slip), `download_file` (postęp, `expected_bytes`, anulowanie) na lokalnym serwerze/`file://` | nie |
| `test_gtfs_dashboard.py` | `slim`, `cities`/`months`/`days`, `resolve_asset` (happy + 3 błędy), `looks_like_gtfs`, `fetch_manifest` (cache, `_stale`) | nie |
| — | `DownloadRealizedGtfs` end-to-end, okno dialogowe | **tak — ręcznie**, wg kryteriów akceptacji R2/R3 |

Fixture: `easy_r5/test/fixtures/manifest.json` (kopia `manifest.sample.json`),
`easy_r5/test/fixtures/mini_gtfs/` (5 wymaganych plików GTFS, po 2 wiersze) do
`looks_like_gtfs`.

---

## Poza zakresem tej wersji

| Pomysł | Dlaczego nie teraz |
|---|---|
| `DownloadTransitData` (OSM + rozkładowy GTFS z Geofabrik / Mobility Database) | Osobny element v0.2 z własnym PRD; inny backend, inne API. |
| Slim `index.json` po stronie gtfs-dashboard | Optymalizacja cross-repo; design tutaj nie zależy od niej (bierzemy pełny manifest i ślimaczymy lokalnie). Jeśli powstanie — zmiana jednej stałej URL. |
| Weryfikacja kryptograficzna pobranego GTFS | Manifest nie niesie hashy. Wymagałoby zmiany w `easy-GTFS-RT` (publikacja `.sha256` per asset). Zanotowane jako luka; mitygacja: CRC zip + `looks_like_gtfs`. |
| Pobieranie „surowych" pozycji (`raw_snapshot_archives`) | To nie jest GTFS — R5 tego nie zbuduje. `easy-GTFS-RT` przetwarza je w zrealizowany feed; tylko ten interesuje wtyczkę. |
| `QgsProcessingParameterDateTime` w tym algorytmie | Wolne pole daty → 404. W oknie data jest `Enum` z manifestu. (Natywny date-param dla `RunTravelTimeMatrix.DATE` — osobno.) |
| Automatyczne łańcuchowanie „pobierz → zbuduj sieć → policz" | Model Processing to załatwia; nie budujemy meta-algorytmu. |

---

## Źródła

- `docs/notes/roadmap-candidates.md` §3 — feasibility + cytaty (GitHub Pages vs REST API
  rate limit, schemat manifestu, `QgsProcessingParameterDateTime` od 3.14).
- `../gtfs-dashboard/manifest.json` (25 miast / 513 dni), `manifest.sample.json`,
  `../gtfs-dashboard/README.md` + `PRD.md` — schemat, CI `refresh-manifest.yml`, hosting.
- `../easy-GTFS-RT/README.md` + `HOW-IT-WORKS.md` — czym jest zrealizowany GTFS, P50/P85.
- `easy_r5/algorithms/download_r5.py` — wzorzec pobierania/rozpakowania do refaktoru.
- `../easy-OTP/easy_otp/algorithms/download_transit_data.py` — wzorzec algorytmu „pobierz dane".
- `CLAUDE.md` — gotcha „static i realized w osobnych katalogach", „tylko PyQGIS",
  „stringi UI w `tr()`".
