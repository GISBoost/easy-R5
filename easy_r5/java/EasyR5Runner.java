import com.conveyal.gtfs.GTFSFeed;
import com.conveyal.osmlib.OSM;
import com.conveyal.r5.OneOriginResult;
import com.conveyal.r5.SoftwareVersion;
import com.conveyal.r5.analyst.FreeFormPointSet;
import com.conveyal.r5.analyst.PointSet;
import com.conveyal.r5.analyst.TravelTimeComputer;
import com.conveyal.r5.analyst.cluster.RegionalTask;
import com.conveyal.r5.analyst.scenario.Scenario;
import com.conveyal.r5.api.util.LegMode;
import com.conveyal.r5.api.util.TransitModes;
import com.conveyal.r5.kryo.KryoNetworkSerializer;
import com.conveyal.r5.profile.StreetMode;
import com.conveyal.r5.transit.DuplicateFeedException;
import com.conveyal.r5.transit.TransportNetwork;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.locationtech.jts.geom.Envelope;

import java.io.BufferedWriter;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

/**
 * Easy-R5 engine runner. One file, one compilation unit (Java 21 single-file
 * source launcher — see ADR-0001). Started from docs/reference/probe/Probe.java.
 *
 *   java -Xmx<heap> -cp <r5-all.jar>            EasyR5Runner.java <job.json>   # source launcher
 *   java -Xmx<heap> -cp <r5-all.jar>;<classDir> EasyR5Runner       <job.json>  # compiled
 *
 * stdout protocol (PRD 3.2), one line per message, UTF-8, '\n':
 *   INFO      <text>
 *   PROGRESS  <done> <total>
 *   WARN      <code> <text>
 *   ERROR     <code> <text>      -> exit 1
 *   RESULT    <key>=<value>
 *   DONE      <path> <rowcount>  -> exit 0
 *
 * M1 implements only command "info". Later milestones add commands; the
 * protocol never changes.
 */
public class EasyR5Runner {

    static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) {
        // Force UTF-8 stdout so a Windows console code page cannot mangle
        // "Europe/Warsaw" or feed identifiers.
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8));
        try {
            if (args.length < 1) {
                Emit.error("BAD_JOB_SPEC", "No job file argument.");
                return;
            }
            String raw;
            try {
                raw = Files.readString(Path.of(args[0]));
            } catch (Exception e) {
                Emit.error("IO_ERROR", "Cannot read job file '" + args[0] + "': " + e);
                return;
            }
            JsonNode job;
            try {
                job = MAPPER.readTree(raw);
            } catch (Exception e) {
                Emit.error("BAD_JOB_SPEC", "Job file is not valid JSON: " + e);
                return;
            }
            String command = job.path("command").asText("");
            switch (command) {
                case "info":
                    doInfo(job);
                    break;
                case "build":
                    doBuild(job);
                    break;
                case "matrix":
                    doMatrix(job);
                    break;
                default:
                    Emit.error("BAD_JOB_SPEC", "Unknown command '" + command + "'.");
            }
        } catch (Throwable t) {
            Emit.error(classify(t), String.valueOf(t));
        }
    }

    // --- command: info -------------------------------------------------------

    private static void doInfo(JsonNode job) {
        String networkPath = job.path("network").asText("").trim();
        if (networkPath.isEmpty()) {
            Emit.error("BAD_JOB_SPEC", "'info' needs a 'network' path.");
            return;
        }
        TransportNetwork network = loadNetwork(networkPath);

        Emit.result("r5_version", r5Version());
        Emit.result("network_format_version", KryoNetworkSerializer.NETWORK_FORMAT_VERSION);
        Emit.result("timezone", String.valueOf(network.getTimeZone()));
        Emit.result("feeds", String.join(",", network.transitLayer.feedChecksums.keySet()));
        Emit.result("stops", Integer.toString(network.transitLayer.getStopCount()));
        Emit.result("trip_patterns", Integer.toString(network.transitLayer.tripPatterns.size()));
        Emit.result("routes", Integer.toString(network.transitLayer.routes.size()));
        Emit.result("street_vertices", Integer.toString(network.streetLayer.getVertexCount()));
        Emit.result("bounds", bounds(network));

        Emit.done(networkPath, 0);
    }

    /**
     * Read a serialised network, mapping the Kryo failure modes to stable error
     * codes. On failure this emits ERROR and exits (never returns null in
     * practice — the return type only satisfies the compiler).
     */
    private static TransportNetwork loadNetwork(String networkPath) {
        File networkFile = new File(networkPath);
        if (!networkFile.isFile()) {
            Emit.error("IO_ERROR", "Network file not found: " + networkPath);
        }
        Emit.info("Loading network: " + networkPath);
        try {
            return KryoNetworkSerializer.read(networkFile);
        } catch (Throwable t) {
            String m = String.valueOf(t.getMessage());
            String lower = m.toLowerCase(Locale.ROOT);
            if (lower.contains("file format version") || lower.contains("this r5 requires")
                    || lower.contains("network_format_version")) {
                Emit.error("NETWORK_VERSION_MISMATCH",
                        "This network.dat was built with a different R5 version and cannot be read "
                        + "by R5 " + r5Version() + " (format " + KryoNetworkSerializer.NETWORK_FORMAT_VERSION
                        + "). Rebuild it with BuildNetwork. Engine detail: " + m);
            } else if (t instanceof OutOfMemoryError) {
                Emit.error("OUT_OF_MEMORY", "Ran out of memory reading the network. Engine detail: " + m);
            } else {
                Emit.error("NETWORK_READ_FAILED",
                        "R5 could not read the network file. It may be corrupt or truncated. "
                        + "Engine detail: " + m);
            }
            return null;  // unreachable: Emit.error exited
        }
    }

    // --- command: matrix -------------------------------------------------

    /**
     * One-to-many travel times for a slice of origins against every
     * destination, streamed as a long-format CSV
     * (<code>from_id,to_id,travel_time_p&lt;pct&gt;,...</code>).
     *
     * <p>The recipe (RegionalTask fields, FreeFormPointSet binary layout) is
     * ported from docs/reference/probe/Probe.java, verified against a real
     * network 2026-09-02. Load-bearing details:
     * <ul>
     *   <li>the destination point set is built <b>once</b> and reused for every
     *       origin — first origin ~900 ms (linking + EgressCostTable), the rest
     *       ~20-40 ms;</li>
     *   <li><code>r.maxWalkTime</code> is always set (Python guarantees a
     *       numeric <code>max_walk_time_minutes</code>) — unbounded, R5 searches
     *       an unlimited walk radius per access/egress/transfer;</li>
     *   <li>unreachable cells (Integer.MAX_VALUE, or over the trip budget) are
     *       written as an empty field, never 0 and never 2147483647;</li>
     *   <li>for a transit run, a walk-only companion computation per origin
     *       feeds <code>RESULT transit_used_pairs</code> — the independent
     *       walk-only detector (PRD 5.8).</li>
     * </ul>
     */
    private static void doMatrix(JsonNode job) throws Exception {
        String networkPath = job.path("network").asText("").trim();
        String originsPath = job.path("origins").asText("").trim();
        String destsPath = job.path("destinations").asText("").trim();
        String outCsv = job.path("out_csv").asText("").trim();
        if (networkPath.isEmpty() || originsPath.isEmpty() || destsPath.isEmpty() || outCsv.isEmpty()) {
            Emit.error("BAD_JOB_SPEC", "'matrix' needs network, origins, destinations, out_csv.");
            return;
        }
        for (String p : new String[]{originsPath, destsPath}) {
            if (!new File(p).isFile()) {
                Emit.error("IO_ERROR", "Point file not found: " + p);
                return;
            }
        }

        int[] percentiles = intArray(job.path("percentiles"));
        if (percentiles.length == 0) {
            Emit.error("BAD_JOB_SPEC", "'matrix' needs at least one percentile.");
            return;
        }
        int medianIdx = medianIndex(percentiles);
        int maxTripMinutes = job.path("max_trip_duration_minutes").asInt(90);
        boolean writeUnreachable = job.path("write_unreachable").asBoolean(false);

        TransportNetwork network = loadNetwork(networkPath);

        List<Pt> origins = readPoints(Path.of(originsPath));
        List<Pt> dests = readPoints(Path.of(destsPath));
        if (origins.isEmpty() || dests.isEmpty()) {
            Emit.error("BAD_JOB_SPEC", "origins/destinations CSV has no usable rows.");
            return;
        }
        Emit.info("origins=" + origins.size() + " destinations=" + dests.size()
                + " percentiles=" + percentiles.length);

        warnUnlinked(network, origins, "origins");
        int linkedDests = warnUnlinked(network, dests, "destinations");
        if (linkedDests == 0) {
            Emit.error("NO_POINTS_LINKED",
                    "Not one destination point could be linked to the street network. "
                    + "Check that the points fall inside the OSM extent the network was built from.");
            return;
        }

        // Build the destination point set once — this is the 900 ms cost that
        // must not be paid per origin.
        PointSet pointSet = buildPointSet(dests);

        int start = 0;
        int end = origins.size();
        JsonNode range = job.path("origin_range");
        if (range.isArray() && range.size() == 2) {
            start = Math.max(0, range.get(0).asInt());
            end = Math.min(origins.size(), range.get(1).asInt());
        }
        List<Pt> slice = origins.subList(start, Math.max(start, end));

        EnumSet<TransitModes> transitModes = parseTransitModes(job.path("transit_modes"));
        boolean transitRun = !transitModes.isEmpty();

        long rowsWritten = 0;
        long transitUsedPairs = 0;
        int total = slice.size();
        int done = 0;
        long lastProgress = 0;

        try (BufferedWriter w = Files.newBufferedWriter(Path.of(outCsv), StandardCharsets.UTF_8)) {
            StringBuilder header = new StringBuilder("from_id,to_id");
            for (int p : percentiles) {
                header.append(",travel_time_p").append(p);
            }
            w.write(header.toString());
            w.write('\n');

            for (Pt origin : slice) {
                RegionalTask task = baseTask(network, origin, job, percentiles, transitModes);
                task.destinationPointSets = new PointSet[]{pointSet};
                int[][] transit = new TravelTimeComputer(task, network).computeTravelTimes().travelTimes.getValues();

                int[] walkMedian = null;
                if (transitRun) {
                    RegionalTask walkTask = baseTask(network, origin, job, percentiles,
                            EnumSet.noneOf(TransitModes.class));
                    walkTask.destinationPointSets = new PointSet[]{pointSet};
                    int[][] walk = new TravelTimeComputer(walkTask, network)
                            .computeTravelTimes().travelTimes.getValues();
                    walkMedian = walk[medianIdx];
                }

                for (int d = 0; d < dests.size(); d++) {
                    boolean anyReached = false;
                    StringBuilder cells = new StringBuilder();
                    for (int p = 0; p < percentiles.length; p++) {
                        int tt = transit[p][d];
                        cells.append(',');
                        if (tt < Integer.MAX_VALUE && tt <= maxTripMinutes) {
                            cells.append(tt);
                            anyReached = true;
                        }
                    }
                    if (anyReached || writeUnreachable) {
                        w.write(origin.id);
                        w.write(',');
                        w.write(dests.get(d).id);
                        w.write(cells.toString());
                        w.write('\n');
                        rowsWritten++;
                    }
                    if (transitRun && walkMedian != null) {
                        int t = transit[medianIdx][d];
                        int wk = walkMedian[d];
                        if (t < Integer.MAX_VALUE && (wk >= Integer.MAX_VALUE || t < wk)) {
                            transitUsedPairs++;
                        }
                    }
                }

                done++;
                long now = System.currentTimeMillis();
                if (now - lastProgress >= 1000 || done == total) {
                    Emit.progress(done, total);
                    lastProgress = now;
                }
            }
        }

        Emit.result("transit_used_pairs", Long.toString(transitUsedPairs));
        Emit.result("origins_done", Integer.toString(total));
        Emit.done(outCsv, rowsWritten);
    }

    /** RegionalTask per Probe.java baseTask(), parametrised from the job. */
    private static RegionalTask baseTask(TransportNetwork network, Pt origin, JsonNode job,
                                         int[] percentiles, EnumSet<TransitModes> transitModes) {
        RegionalTask r = new RegionalTask();
        r.scenario = new Scenario();
        r.scenario.id = "id";
        r.scenarioId = r.scenario.id;
        r.zoneId = network.getTimeZone();
        r.fromLat = origin.lat;
        r.fromLon = origin.lon;
        r.walkSpeed = (float) (job.path("walk_speed_kmh").asDouble(3.6) / 3.6);
        r.bikeSpeed = (float) (job.path("bike_speed_kmh").asDouble(12.0) / 3.6);
        int maxTrip = job.path("max_trip_duration_minutes").asInt(90);
        int maxWalk = job.path("max_walk_time_minutes").asInt(maxTrip);
        r.streetTime = maxTrip;
        r.maxTripDurationMinutes = maxTrip;
        r.maxWalkTime = maxWalk;
        r.maxBikeTime = maxTrip;
        r.maxCarTime = maxTrip;
        r.maxRides = job.path("max_rides").asInt(3);
        r.bikeTrafficStress = 3;
        r.directModes = parseLegModes(job.path("direct_modes"), LegMode.WALK);
        r.accessModes = parseLegModes(job.path("access_modes"), LegMode.WALK);
        r.egressModes = parseLegModes(job.path("egress_modes"), LegMode.WALK);
        r.transitModes = transitModes;
        r.date = LocalDate.parse(job.path("date").asText());
        int fromTime = secondsOfDay(job.path("departure_time").asText("07:00"));
        r.fromTime = fromTime;
        r.toTime = fromTime + job.path("time_window_minutes").asInt(120) * 60;
        r.monteCarloDraws = job.path("monte_carlo_draws").asInt(5);
        r.makeTauiSite = false;
        r.recordTimes = true;
        r.recordAccessibility = false;
        r.percentiles = percentiles;
        return r;
    }

    /** FreeFormPointSet binary format, per Probe.java / r5r's buildDestinationPointSet. */
    private static PointSet buildPointSet(List<Pt> pts) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bos);
        out.writeInt(pts.size());
        for (Pt p : pts) {
            out.writeUTF(p.id);
        }
        for (Pt p : pts) {
            out.writeDouble(p.lat);
        }
        for (Pt p : pts) {
            out.writeDouble(p.lon);
        }
        for (Pt p : pts) {
            out.writeDouble(1.0);
        }
        return new FreeFormPointSet(new ByteArrayInputStream(bos.toByteArray()));
    }

    /**
     * Count how many points link to the street network; WARN if any fail.
     * Not fatal for origins (PRD 5.6 = warn, not block); the caller aborts only
     * when zero destinations link.
     */
    private static int warnUnlinked(TransportNetwork network, List<Pt> pts, String label) {
        double radius = com.conveyal.r5.streets.StreetLayer.LINK_RADIUS_METERS;
        int linked = 0;
        for (Pt p : pts) {
            if (network.streetLayer.findSplit(p.lat, p.lon, radius, StreetMode.WALK) != null) {
                linked++;
            }
        }
        if (linked < pts.size()) {
            Emit.warn("UNLINKED_POINTS", (pts.size() - linked) + " of " + pts.size() + " "
                    + label + " are not near any street and will be unreachable - check the "
                    + "OSM extent and that the points are not offshore.");
        }
        return linked;
    }

    private static List<Pt> readPoints(Path path) throws Exception {
        List<String> lines = Files.readAllLines(path);
        if (lines.isEmpty()) {
            return new ArrayList<>();
        }
        String[] header = lines.get(0).split(",");
        int iId = colIndex(header, "id");
        int iLon = colIndex(header, "lon");
        int iLat = colIndex(header, "lat");
        List<Pt> out = new ArrayList<>();
        for (int i = 1; i < lines.size(); i++) {
            if (lines.get(i).isBlank()) {
                continue;
            }
            String[] c = lines.get(i).split(",");
            out.add(new Pt(c[iId].trim(),
                    Double.parseDouble(c[iLon].trim()),
                    Double.parseDouble(c[iLat].trim())));
        }
        return out;
    }

    private static int colIndex(String[] header, String name) {
        for (int i = 0; i < header.length; i++) {
            if (header[i].trim().equalsIgnoreCase(name)) {
                return i;
            }
        }
        throw new IllegalArgumentException("point CSV has no '" + name + "' column");
    }

    private static int[] intArray(JsonNode node) {
        if (!node.isArray()) {
            return new int[0];
        }
        int[] out = new int[node.size()];
        for (int i = 0; i < node.size(); i++) {
            out[i] = node.get(i).asInt();
        }
        return out;
    }

    /** Index of the value closest to 50 — the percentile used for the walk-only compare. */
    private static int medianIndex(int[] percentiles) {
        int best = 0;
        for (int i = 1; i < percentiles.length; i++) {
            if (Math.abs(percentiles[i] - 50) < Math.abs(percentiles[best] - 50)) {
                best = i;
            }
        }
        return best;
    }

    private static int secondsOfDay(String hhmm) {
        String[] parts = hhmm.trim().split(":");
        return Integer.parseInt(parts[0]) * 3600 + Integer.parseInt(parts[1]) * 60;
    }

    private static EnumSet<LegMode> parseLegModes(JsonNode arr, LegMode fallback) {
        EnumSet<LegMode> set = EnumSet.noneOf(LegMode.class);
        if (arr.isArray()) {
            for (JsonNode n : arr) {
                String s = n.asText("").trim().toUpperCase(Locale.ROOT);
                if (!s.isEmpty()) {
                    set.add(LegMode.valueOf(s));
                }
            }
        }
        if (set.isEmpty()) {
            set.add(fallback);
        }
        return set;
    }

    private static EnumSet<TransitModes> parseTransitModes(JsonNode arr) {
        EnumSet<TransitModes> set = EnumSet.noneOf(TransitModes.class);
        if (arr.isArray()) {
            for (JsonNode n : arr) {
                String s = n.asText("").trim().toUpperCase(Locale.ROOT);
                if (!s.isEmpty()) {
                    set.add(TransitModes.valueOf(s));
                }
            }
        }
        return set;
    }

    /** One origin/destination row from an id,lon,lat CSV. */
    record Pt(String id, double lon, double lat) {
    }

    // --- command: build ---------------------------------------------------

    private static void doBuild(JsonNode job) throws Exception {
        String osmPath = job.path("osm").asText("").trim();
        List<String> gtfs = new ArrayList<>();
        for (JsonNode g : job.path("gtfs")) {
            String s = g.asText("").trim();
            if (!s.isEmpty()) {
                gtfs.add(s);
            }
        }
        String outNet = job.path("out_network").asText("").trim();
        String outSum = job.path("out_summary").asText("").trim();
        if (osmPath.isEmpty() || gtfs.isEmpty() || outNet.isEmpty() || outSum.isEmpty()) {
            Emit.error("BAD_JOB_SPEC", "'build' needs osm, gtfs[], out_network, out_summary.");
            return;
        }
        if (!new File(osmPath).isFile()) {
            Emit.error("IO_ERROR", "OSM file not found: " + osmPath);
            return;
        }
        for (String g : gtfs) {
            if (!new File(g).isFile()) {
                Emit.error("IO_ERROR", "GTFS file not found: " + g);
                return;
            }
        }

        Emit.info("Building network: " + osmPath + " + " + gtfs.size() + " GTFS feed(s)");
        Emit.progress(0, 4);

        File cacheDir = new File(outNet).getAbsoluteFile().getParentFile();
        if (cacheDir != null) {
            cacheDir.mkdirs();
        }

        // Keep the MapDB sidecar in our cache dir, not next to the source OSM —
        // the tools/ folders already carry r5r's .osm.pbf.mapdb from an older
        // osmlib and OSM.openOrCreateFile would reuse a stale one.
        OSM osm = OSM.openOrCreateFile(new File(cacheDir, "osm.mapdb"), osmPath);
        Emit.info("OSM loaded: " + osm.ways.size() + " ways, " + osm.nodes.size() + " nodes");
        Emit.progress(1, 4);

        Stream<GTFSFeed> feeds = gtfs.stream().map(GTFSFeed::readOnlyTempFileFromGtfs);

        TransportNetwork network;
        try {
            network = TransportNetwork.build(null, osm, feeds, true);
        } catch (DuplicateFeedException e) {
            Emit.error("IO_ERROR",
                    "Two GTFS feeds share the same feed_id — put each network variant in its "
                    + "own folder. Detail: " + e.getMessage());
            return;
        }
        Emit.info("Network built: " + network.transitLayer.getStopCount() + " stops, "
                + network.transitLayer.tripPatterns.size() + " trip patterns");
        Emit.progress(2, 4);

        KryoNetworkSerializer.write(network, new File(outNet));
        Emit.progress(3, 4);

        ObjectNode j = MAPPER.createObjectNode();
        j.put("r5_version", r5Version());
        j.put("network_format_version", KryoNetworkSerializer.NETWORK_FORMAT_VERSION);
        j.put("built_at", LocalDateTime.now().withNano(0).toString());
        j.put("timezone", String.valueOf(network.getTimeZone()));
        ArrayNode feedsArr = j.putArray("feeds");
        for (String f : network.transitLayer.feedChecksums.keySet()) {
            feedsArr.add(f);
        }
        j.put("stops", network.transitLayer.getStopCount());
        j.put("trip_patterns", network.transitLayer.tripPatterns.size());
        j.put("routes", network.transitLayer.routes.size());
        j.put("street_vertices", network.streetLayer.getVertexCount());
        Envelope e = network.getEnvelope();
        ObjectNode b = j.putObject("bounds");
        if (e != null && !e.isNull()) {
            b.put("min_lon", e.getMinX());
            b.put("min_lat", e.getMinY());
            b.put("max_lon", e.getMaxX());
            b.put("max_lat", e.getMaxY());
        }
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(new File(outSum), j);
        Emit.progress(4, 4);

        Emit.done(outNet, network.transitLayer.tripPatterns.size());
    }

    // --- helpers -----------------------------------------------------------

    private static String r5Version() {
        String v = "7.6";
        try {
            SoftwareVersion sv = SoftwareVersion.instance;
            if (sv != null && sv.version != null && !sv.version.isBlank()) {
                v = sv.version;
            }
        } catch (Throwable ignored) {
            // fall through to the pinned value
        }
        return v.startsWith("v") ? v.substring(1) : v;  // "v7.6" -> "7.6", matches pins.R5_VERSION
    }

    /** min_lon,min_lat,max_lon,max_lat with 6 decimals, or "" if unavailable. */
    private static String bounds(TransportNetwork network) {
        Envelope e = null;
        try {
            e = network.getEnvelope();
        } catch (Throwable ignored) {
            // try the street layer directly
        }
        if (e == null || e.isNull()) {
            try {
                e = network.streetLayer.getEnvelope();
            } catch (Throwable ignored) {
                // give up
            }
        }
        if (e == null || e.isNull()) {
            Emit.warn("IO_ERROR", "Could not derive network bounds.");
            return "";
        }
        return String.format(Locale.ROOT, "%.6f,%.6f,%.6f,%.6f",
                e.getMinX(), e.getMinY(), e.getMaxX(), e.getMaxY());
    }

    private static String classify(Throwable t) {
        if (t instanceof OutOfMemoryError) {
            return "OUT_OF_MEMORY";
        }
        if (t instanceof java.io.IOException) {
            return "IO_ERROR";
        }
        return "IO_ERROR";
    }

    /** stdout protocol writer. Every method flushes. */
    static final class Emit {
        private Emit() {
        }

        static void info(String text) {
            line("INFO " + text);
        }

        static void progress(int done, int total) {
            line("PROGRESS " + done + " " + total);
        }

        static void warn(String code, String text) {
            line("WARN " + code + " " + text);
        }

        static void result(String key, String value) {
            line("RESULT " + key + "=" + value);
        }

        static void error(String code, String text) {
            line("ERROR " + code + " " + oneLine(text));
            System.exit(1);
        }

        static void done(String path, long rowcount) {
            line("DONE " + path + " " + rowcount);
            System.exit(0);
        }

        private static void line(String s) {
            System.out.println(s);
            System.out.flush();
        }

        private static String oneLine(String s) {
            return s == null ? "" : s.replace('\r', ' ').replace('\n', ' ');
        }
    }
}
