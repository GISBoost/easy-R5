# Claude Code prompt — Easy-R5 **M1**: plugin skeleton + engine on disk

> Paste everything below the line into Claude Code, in the `easy-R5` repo, on a clean git tree.
> Code, comments and commit messages in English (`CLAUDE.md`); chat with Michał in Polish.
> Implement **M1 only**. Do not start `BuildNetwork` or any Analysis algorithm — those are M2+.
> Do not create a new branch.

---

## ✅ Implementation status (2026-09-03)

**Implemented and committed on `main`** (`ac24b41`..`4f801c9`). Plugin skeleton,
Processing provider `easyr5`, `DownloadR5`, `TestR5Setup`, `EasyR5Runner.java`
command `info`. Unit tests for the job spec, the stdout-protocol parser and the
Java-env helpers.

**Still needs Michał:** ZIP install on a clean profile; `DownloadR5` real
download (Adoptium + GitHub Releases, no admin rights, SHA-256); `TestR5Setup`
output.

Full picture: [`../handoffs/2026-09-03_M3-M5-implementation.md`](../handoffs/2026-09-03_M3-M5-implementation.md).

## Context to load first

- `CLAUDE.md` — hard constraints. Especially: no `pip install`, no R in the plugin, pinned
  versions, separate QSettings namespace from easy-OTP.
- `docs/prd/PR_easy-R5_v01.md` — **§3.2** (runner contract), **§3.3** (core modules),
  **§4.1–4.2** (`DownloadR5`, `TestR5Setup`), **§6 M1** (acceptance criteria), **§7** (QGIS
  plugin repository checklist).
- `docs/adr/0001-r5-binding.md`, `docs/adr/0002-pinned-versions.md` — both Accepted.
- `docs/notes/spike-r5-probe-2026-09-02.md` — measured facts; the numbers you must not
  contradict.
- `docs/reference/probe/Probe.java` — **working code that already calls R5.** `EasyR5Runner.java`
  starts from this file, not from scratch.
- `../easy-OTP/easy_otp/algorithms/download_jre.py` — the pattern for downloading a JDK from the
  Adoptium API, verifying a checksum, extracting safely and saving paths to QSettings. Read it
  before writing `DownloadR5`; deviate only where R5 differs from OTP.
- `../easy-OTP/easy_otp/provider.py`, `../easy-OTP/easy_otp/easy_otp_plugin.py`,
  `../easy-OTP/easy_otp/metadata.txt` — plugin skeleton to mirror.

## Why this milestone exists

Nothing can be tested until the engine is on disk and provably runnable. M1 is the smallest
end-to-end slice that proves ADR-0001 outside a scratch directory: QGIS downloads a JDK and the
R5 jar, compiles our one Java file, runs it, and reads a line of output back. Every later
milestone is "add a command to a runner that already works".

## Goal

A loadable QGIS plugin with a Processing provider containing exactly two algorithms —
`DownloadR5` and `TestR5Setup` — plus `EasyR5Runner.java` implementing only `command: "info"`.

## What to build

### `easy_r5/` skeleton
`__init__.py` with `classFactory`, `easy_r5_plugin.py` (`__init__`/`initGui`/`unload`,
provider registered and cleanly removed), `provider.py` (`id="easyr5"`, `name="Easy-R5"`),
`metadata.txt` (all fields from PRD §7, `version=0.0.1`, `experimental=True`,
`hasProcessingProvider=yes`), `LICENSE` (copy of the repo's), `resources/icon.svg` placeholder.

### `easy_r5/java/EasyR5Runner.java`
One file, one compilation unit (Java 21 has no multi-file source programs — this is a hard
constraint, see ADR-0001). For M1 implement only `command: "info"`: read the job JSON, load
`network.dat` via `KryoNetworkSerializer.read`, emit `RESULT key=value` lines
(r5_version, network_format_version, timezone, feeds, stops, trip_patterns, street_vertices,
bounds), exit 0. Implement the full stdout protocol from PRD §3.2 now (`INFO`/`PROGRESS`/
`WARN`/`ERROR`/`RESULT`/`DONE`) — later milestones only add commands, never change the protocol.

JSON parsing: hand-rolled minimal reader or `com.fasterxml.jackson` if it is already inside the
R5 shaded jar — check before adding anything; **no new dependencies**.

### `easy_r5/core/`
`java_env.py` (paths from QSettings, JDK version check, jar SHA-256 check, compile runner to a
cache dir, RAM detection and `-Xmx` heuristic per PRD §3.4), `runner.py` (spawn, stdout protocol
parsing, progress, cancel, `finally` cleanup, error-code → message mapping), `job_spec.py`
(build + validate), `settings.py` (**`easy_r5/…` keys only** — never touch easy-OTP's).

### `easy_r5/algorithms/`
`download_r5.py`, `test_r5_setup.py` per PRD §4.1–4.2. `TestR5Setup` reports each step
separately; a failure in step 3 must still show that steps 1–2 passed.

### `easy_r5/test/`
Pure-Python tests runnable outside QGIS: job-spec validation (percentiles ≤5, ascending, 1–99),
stdout protocol parser (including a truncated line and an interleaved Java log line), heap
heuristic, SHA-256 verification. Mirror `../easy-OTP/easy_otp/test/` in style.

## Acceptance criteria

- Plugin loads in QGIS 3.22 and 3.40; provider appears; `unload()` leaves nothing behind.
- `DownloadR5` fetches Temurin 21 JDK + pinned `r5-v7.6-all.jar`, verifies SHA-256, stores paths,
  compiles the runner. No admin rights needed.
- `TestR5Setup` passes on a clean QGIS profile and prints the R5 version.
- Running `info` against `tools/accessibility_cities/gdansk/network.dat` reports
  **1619 stops, 573 trip patterns, `Europe/Warsaw`, feed `gdansk_gtfs`** (that network was built
  by R5 7.5.1 — if 7.6 refuses to load it, that is the expected
  `NETWORK_VERSION_MISMATCH` path: verify the error message is intelligible and say so in the
  report, do not "fix" it).
- Unit tests green.

## What you must NOT do

- No `pip install`, no new Python or Java dependencies.
- No second Java file.
- No sharing of QSettings keys, downloaded JDK, or cache directories with easy-OTP.
- No work on network building, matrices, accessibility or isochrones.

## Report to Michał when done (he tests, you cannot)

1. Install from ZIP on a clean QGIS profile; run `DownloadR5`; confirm the download sizes and that
   no admin prompt appears.
2. Run `TestR5Setup`; paste the output.
3. Point `info` at Gdańsk's `network.dat` and compare the numbers with the acceptance criteria.
4. Confirm QGIS has no orphaned `java.exe` in Task Manager after each run.
