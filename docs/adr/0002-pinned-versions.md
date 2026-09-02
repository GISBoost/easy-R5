# ADR-0002 — Pinned R5, Java and QGIS versions

- **Status:** Proposed
- **Date:** 2026-09-02

## Context

R5's own README states it exposes no stable API and that third-party wrappers "may need to
continue using an older release of R5". Both existing bindings pin: `r5py` pins a specific jar
URL **and** its SHA-256; `r5r` builds against whatever `download_r5()` fetches for that package
version. A network file written by one R5 version refuses to load in another
(`NETWORK_FORMAT_VERSION` check in `KryoNetworkSerializer`).

easy-OTP's equivalent decision was "OTP exactly 1.5.0, Java exactly 8". Easy-R5 needs the same
kind of hard pin, with different numbers.

## Decision

| Component | Pin | Notes |
|---|---|---|
| R5 | **`r5-v7.6-all.jar`** (Conveyal official release, 62 MB, MIT) | `https://github.com/conveyal/r5/releases/download/v7.6/r5-v7.6-all.jar`. Releases publish `.md5`/`.sha1` but **not** `.sha256` — compute the SHA-256 once, hardcode it, verify on download (do not weaken to MD5). |
| Java | **Temurin 21** (JDK, not JRE — see ADR-0001) | R5 v7.6 `build.gradle` sets `JavaLanguageVersion.of(21)`. Fetch through the Adoptium API exactly as easy-OTP's `DownloadJre` does, with `feature_version=21`, `image_type=jdk`. |
| QGIS | **3.22 LTR minimum**, as easy-OTP | Keeps one compatibility story across both plugins. Revisit only if a needed PyQGIS API is newer. |
| Network cache | keyed by hash of (inputs + R5 version) | A version bump must invalidate every `network.dat`, otherwise users get an opaque Kryo error. |

Upgrading R5 is a deliberate, tested change — never "whatever is latest". The R5 version string
belongs in the plugin's own metadata and in every network cache directory name.

## Consequences

- A user with Java 8 installed for easy-OTP cannot reuse it; both runtimes coexist, each recorded
  under its own QSettings key. Do **not** share easy-OTP's `java_path` setting.
- Networks built by Easy-R5 are not interchangeable with anything r5r/r5py produced unless they
  happen to be on the same R5 version — worth saying out loud in the README, since the `tools/`
  pipeline being migrated does produce `network.dat` files.
- 62 MB jar + ~180 MB JDK is a chunky first-run download. Show sizes in the setup algorithm's
  description, exactly as easy-OTP does.

## Alternative considered

**`r5py`'s fork jar** (`r5py/r5` tag `v7.6-r5py`). Its only functional patches are two
`input.close()` calls on `KryoNetworkSerializer` error paths (a real Windows file-locking fix) and
`TransitLayer.saveShapes = true` (obtainable from a build-config JSON instead). Prefer the
official Conveyal jar; switch to the fork if Windows file locking on failed network loads turns
out to bite in practice.
