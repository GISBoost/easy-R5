# Open questions

Things that must be answered before or during the first milestones. Ordered by how much they
change the plan. Answer them by *running something*, not by reasoning — everything here has been
reasoned about as far as it usefully can be.

## Answered (2026-09-02)

1. ~~Is owning a Java source file acceptable?~~ **Yes** — ADR-0001 Accepted: one
   `EasyR5Runner.java`, compiled with the downloaded JDK, run as a subprocess. JPype stays as a
   documented reversal path only.
2. ~~Does `tools/ses_income_lodz/` move?~~ **Yes** — ADR-0003 Accepted: all four folders plus
   `isochrones-cities.yml`. **Executed 2026-09-02**, including ~6 GB of untracked study data and
   the link updates in `mapy-analizy` and the blog.
3. ~~Hex grid / population algorithms — copy or cross-link?~~ **No hex-grid algorithm** (it wraps
   `native:creategrid`; document the recipe instead), but **`PreparePopulationLayer`** (renamed
   from easy-OTP's `PrepareStudentLayer`) **and `PopulationOverlay` are copied here** — they are
   genuinely unique. **Copied, not moved** — easy-OTP keeps its own; nothing is taken out of
   easy-OTP. PRD §4.7–4.9. One follow-up: the `openpyxl` exception needs Michał's sign-off in
   `CLAUDE.md` before the M5 agent implements it.

## Blocking — for Michał, not for an agent

4. **Repository name and QGIS plugin name.** `easy-R5` / `Easy-R5` is assumed throughout, and
   the GitHub repository now exists under that name. The official QGIS plugin repository will
   also want a unique plugin name and folder.

## Answered by the spike (2026-09-02) — see [`spike-r5-probe-2026-09-02.md`](spike-r5-probe-2026-09-02.md)

5. ~~Can the per-departure-minute distribution be recovered?~~ **Yes.**
   `recordTravelTimeHistograms = true` → `TravelTimeResult.getHistogram(target)` returns
   `int[120]`, one bin per travel-time minute, counting departure minutes. The service-minutes
   metric is computable; scheduled for v0.2 under its own name.
6. ~~Does `validatePercentiles()` really reject more than 5?~~ **Yes**, `IllegalArgumentException`
   on six. Python validates before spawning Java. (Whether `TravelTimeComputer` calls it on the
   direct path is now moot.)
8. ~~Does the single-file source launcher work with a 62 MB classpath jar, and at what cost?~~
   **Works; ~0.8 s compile overhead**, removed entirely by pre-compiling at setup.
9. ~~JDK vs JRE?~~ **JDK**, so the runner can be compiled on the user's machine — no build
   pipeline, no shipped binary. Accepted in ADR-0001.

Bonus finding, not previously asked: **R5's native accessibility is unusable standalone**
(`task.destinationPointSetKeys is null`). Accessibility is computed in Python from the matrix.

## Technical — still open

7. **Is vanilla Conveyal R5 enough, or is r5py's fork needed?** Only two functional patches exist:
   `input.close()` on Kryo load-error paths (a Windows file-locking fix — likely to matter for us)
   and `saveShapes = true` (obtainable via a build-config JSON, [verify]). The spike ran against
   the r5r-shipped 7.5.1 jar; re-run it against vanilla 7.6 in M1.
Items 10–12 now have a specified answer in [`../prd/PR_easy-R5_v01.md`](../prd/PR_easy-R5_v01.md)
(§3.4); they stay listed because the specification is untested until M3.

10. **Heap sizing heuristic.** The r5r pipeline OOM'd at 12 GB on Warszawa at 500 m origins. What
    does Easy-R5 default to, how does it detect available RAM from PyQGIS, and what does it say to
    the user when R5 dies? An OOM must never surface as a Java stack trace.
11. **Batch size / progress granularity.** One `TravelTimeComputer` call = one origin. Progress and
    cancellation hook in there; batching is also the OOM mitigation. What is the unit of work the
    Python side schedules, and does the runner do the batching or does Python re-invoke it?
12. **Network cache invalidation.** Key on hash(inputs) + R5 version. Confirm the Kryo version
    check's error message is intelligible enough to catch and rewrite.

## Product

13. ~~Which existing result is the acceptance test?~~ **Decided: Gdańsk**, not Łódź — its folder
    already holds `network.dat`, origins, destinations *and* r5r's
    `gdansk_service_accessibility.csv`, and the spike ran against exactly that network. PRD M4.
    One unknown remains: **the departure date r5r used for that CSV is not recorded anywhere** in
    the repo and has to be reconstructed (the run log only shows the build timestamp and a
    spurious "<20% of services" warning).
14. **Does Easy-R5 need its own `DownloadTransitData`, or does it call easy-OTP's?** Duplication
    versus a hard dependency between plugins. Recommendation: duplicate — it is small, and a
    cross-plugin dependency in the QGIS repository is worse.
15. **Experimental flag and release cadence.** easy-OTP shipped `experimental=True` until v0.3.5.
    Same here.
