import com.conveyal.r5.OneOriginResult;
import com.conveyal.r5.analyst.FreeFormPointSet;
import com.conveyal.r5.analyst.PointSet;
import com.conveyal.r5.analyst.TravelTimeComputer;
import com.conveyal.r5.analyst.cluster.AnalysisWorkerTask;
import com.conveyal.r5.analyst.cluster.RegionalTask;
import com.conveyal.r5.analyst.scenario.Scenario;
import com.conveyal.r5.api.util.LegMode;
import com.conveyal.r5.api.util.TransitModes;
import com.conveyal.r5.kryo.KryoNetworkSerializer;
import com.conveyal.r5.transit.TransportNetwork;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;

/**
 * Easy-R5 feasibility probe. Answers open questions 5-9 empirically against a real
 * r5r-built network. Run:
 *   java -Xmx8g -cp <r5-all.jar> Probe.java <network.dat> <origins.csv> <destinations.csv> <yyyy-mm-dd>
 */
public class Probe {

    public static void main(String[] args) throws Exception {
        long t0 = System.currentTimeMillis();
        say("java.version=" + System.getProperty("java.version"));

        File networkFile = new File(args[0]);
        List<Pt> origins = readCsv(Path.of(args[1]));
        List<Pt> dests = readCsv(Path.of(args[2]));
        LocalDate date = LocalDate.parse(args[3]);
        say("origins=" + origins.size() + " destinations=" + dests.size() + " date=" + date);

        // --- Q: constants and fields we plan to rely on -----------------------------
        say("MAX_PERCENTILES=" + AnalysisWorkerTask.MAX_PERCENTILES);
        for (String f : new String[]{"recordTravelTimeHistograms", "recordTimes", "recordAccessibility", "percentiles"}) {
            say("field " + f + " -> " + fieldType(AnalysisWorkerTask.class, f));
        }

        // --- Q: does a 106 MB r5r-built network load in vanilla R5 on this JDK? ------
        long t1 = System.currentTimeMillis();
        TransportNetwork network = KryoNetworkSerializer.read(networkFile);
        say("network loaded in " + (System.currentTimeMillis() - t1) + " ms");
        say("stops=" + network.transitLayer.getStopCount()
                + " tripPatterns=" + network.transitLayer.tripPatterns.size()
                + " streetVertices=" + network.streetLayer.getVertexCount());
        say("feedChecksums=" + network.transitLayer.feedChecksums.keySet());
        say("timeZone=" + network.getTimeZone());

        // --- Q: does percentile validation actually reject more than 5? --------------
        RegionalTask six = baseTask(network, origins.get(0), date, new int[]{10, 25, 50, 75, 85, 95});
        try {
            six.validatePercentiles();
            say("validatePercentiles(6) -> ACCEPTED (no exception)");
        } catch (Throwable e) {
            say("validatePercentiles(6) -> REJECTED: " + e.getClass().getSimpleName() + ": " + e.getMessage());
        }

        // --- Q: one-to-many travel times, vanilla TravelTimeComputer, 5 percentiles --
        PointSet ps = pointSet(dests);
        int[] percentiles = {25, 50, 75, 85, 95};
        RegionalTask task = baseTask(network, origins.get(0), date, percentiles);
        task.destinationPointSets = new PointSet[]{ps};

        long t2 = System.currentTimeMillis();
        OneOriginResult result = new TravelTimeComputer(task, network).computeTravelTimes();
        long oneOrigin = System.currentTimeMillis() - t2;
        say("computeTravelTimes(1 origin -> " + dests.size() + " dests) in " + oneOrigin + " ms");

        int[][] v = result.travelTimes.getValues();
        say("result shape: percentiles=" + v.length + " points=" + v[0].length);
        int reachable = 0, sum = 0;
        for (int d = 0; d < v[1].length; d++) {
            if (v[1][d] < 120) { reachable++; sum += v[1][d]; }
        }
        say("P50 reachable<120min=" + reachable + "/" + v[1].length
                + " meanMinutes=" + (reachable > 0 ? (sum / reachable) : -1));
        StringBuilder sb = new StringBuilder("first 5 dests, per percentile 25/50/75/85/95: ");
        for (int d = 0; d < Math.min(5, v[0].length); d++) {
            sb.append("[");
            for (int p = 0; p < v.length; p++) sb.append(v[p][d]).append(p < v.length - 1 ? "," : "");
            sb.append("] ");
        }
        say(sb.toString());

        // --- Q: what does OneOriginResult expose (for the histogram question)? -------
        StringBuilder f = new StringBuilder("OneOriginResult fields: ");
        for (Field fl : OneOriginResult.class.getFields()) f.append(fl.getName()).append("(").append(fl.getType().getSimpleName()).append(") ");
        say(f.toString());

        // --- Q: cost of a second origin (is network load the dominant cost?) ---------
        long t3 = System.currentTimeMillis();
        RegionalTask task2 = baseTask(network, origins.get(1), date, percentiles);
        task2.destinationPointSets = new PointSet[]{ps};
        new TravelTimeComputer(task2, network).computeTravelTimes();
        say("second origin in " + (System.currentTimeMillis() - t3) + " ms");

        say("TOTAL wall clock " + (System.currentTimeMillis() - t0) + " ms");
    }

    private static RegionalTask baseTask(TransportNetwork network, Pt origin, LocalDate date, int[] percentiles) {
        RegionalTask r = new RegionalTask();
        r.scenario = new Scenario();
        r.scenario.id = "id";
        r.scenarioId = r.scenario.id;
        r.zoneId = network.getTimeZone();
        r.fromLat = origin.lat;
        r.fromLon = origin.lon;
        r.walkSpeed = 1.0f;                 // m/s, r5r default 3.6 km/h
        r.bikeSpeed = 3.3f;
        r.streetTime = 90;
        r.maxWalkTime = 30;
        r.maxBikeTime = 30;
        r.maxCarTime = 30;
        r.maxTripDurationMinutes = 90;
        r.maxRides = 3;
        r.bikeTrafficStress = 3;
        r.directModes = EnumSet.of(LegMode.WALK);
        r.accessModes = EnumSet.of(LegMode.WALK);
        r.egressModes = EnumSet.of(LegMode.WALK);
        r.transitModes = EnumSet.allOf(TransitModes.class);
        r.date = date;
        r.fromTime = 7 * 3600;              // 07:00
        r.toTime = 7 * 3600 + 120 * 60;     // + 120 min window, as in run_accessibility.R
        r.monteCarloDraws = 5;
        r.makeTauiSite = false;
        r.recordTimes = true;
        r.recordAccessibility = false;
        r.percentiles = percentiles;
        return r;
    }

    /** FreeFormPointSet's binary format, per r5r's R5Process.buildDestinationPointSet(). */
    private static PointSet pointSet(List<Pt> pts) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bos);
        out.writeInt(pts.size());
        for (Pt p : pts) out.writeUTF(p.id);
        for (Pt p : pts) out.writeDouble(p.lat);
        for (Pt p : pts) out.writeDouble(p.lon);
        for (Pt p : pts) out.writeDouble(1.0);
        return new FreeFormPointSet(new ByteArrayInputStream(bos.toByteArray()));
    }

    private static List<Pt> readCsv(Path path) throws Exception {
        List<String> lines = Files.readAllLines(path);
        String[] header = lines.get(0).split(",");
        int iId = idx(header, "id"), iLon = idx(header, "lon"), iLat = idx(header, "lat");
        List<Pt> out = new ArrayList<>();
        for (int i = 1; i < lines.size(); i++) {
            if (lines.get(i).isBlank()) continue;
            String[] c = lines.get(i).split(",");
            out.add(new Pt(c[iId], Double.parseDouble(c[iLon]), Double.parseDouble(c[iLat])));
        }
        return out;
    }

    private static int idx(String[] header, String name) {
        for (int i = 0; i < header.length; i++) if (header[i].trim().equalsIgnoreCase(name)) return i;
        throw new IllegalArgumentException("no column " + name);
    }

    private static String fieldType(Class<?> c, String name) {
        try {
            return c.getField(name).getType().getSimpleName();
        } catch (NoSuchFieldException e) {
            return "ABSENT";
        }
    }

    private static void say(String s) {
        System.out.println("PROBE: " + s);
    }

    record Pt(String id, double lon, double lat) {
    }
}
