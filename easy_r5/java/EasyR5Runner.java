import com.conveyal.gtfs.GTFSFeed;
import com.conveyal.osmlib.OSM;
import com.conveyal.r5.SoftwareVersion;
import com.conveyal.r5.kryo.KryoNetworkSerializer;
import com.conveyal.r5.transit.DuplicateFeedException;
import com.conveyal.r5.transit.TransportNetwork;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.locationtech.jts.geom.Envelope;

import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
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
        File networkFile = new File(networkPath);
        if (!networkFile.isFile()) {
            Emit.error("IO_ERROR", "Network file not found: " + networkPath);
            return;
        }

        Emit.info("Loading network: " + networkPath);
        TransportNetwork network;
        try {
            network = KryoNetworkSerializer.read(networkFile);
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
            return;
        }

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
