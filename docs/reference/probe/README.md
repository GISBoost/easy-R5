# R5 feasibility probes

Working code that calls R5 from a single Java source file, as ADR-0001 specifies.
**`EasyR5Runner.java` starts from here, not from an empty file** — the `RegionalTask` setup and
the `FreeFormPointSet` binary format in `Probe.java` are verified against a real network.

Measurements and interpretation: [`../../notes/spike-r5-probe-2026-09-02.md`](../../notes/spike-r5-probe-2026-09-02.md).

## Run

```
java -Xmx8g -cp <r5-all.jar> Probe.java  <network.dat> <origins.csv> <destinations.csv> <yyyy-mm-dd>
java -Xmx8g -cp <r5-all.jar> Probe3.java <network.dat> <origins.csv> <destinations.csv> <yyyy-mm-dd>
```

`Probe.java` — network load, task setup, one-to-many travel times, percentile limit, timings.
`Probe3.java` — `recordTravelTimeHistograms` and the shape of `TravelTimeResult.getHistogram()`.

CSV inputs need `id,lon,lat` columns (extra columns are ignored).

As used on 2026-09-02:

```
jar:      %LOCALAPPDATA%\R\cache\R\r5r\r5_jar_v7.5.1\r5-v7.5-1-gf3631e9-all.jar
network:  easy-OTP\tools\accessibility_cities\gdansk\network.dat
origins:  gdansk_hex_origins.csv        destinations: gdansk_service_destinations.csv
date:     2026-08-25
```

These probes are reference material, not tests — they are not wired into CI and they will not be
maintained once the runner exists. Re-run them when bumping the pinned R5 version (open question:
does vanilla 7.6 behave like the r5r-shipped 7.5.1?).
