import com.conveyal.r5.OneOriginResult;
import com.conveyal.r5.analyst.FreeFormPointSet;
import com.conveyal.r5.analyst.PointSet;
import com.conveyal.r5.analyst.TravelTimeComputer;
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
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;

/** Probe 3: exact shape of TravelTimeResult.getHistogram(target). */
public class Probe3 {
    public static void main(String[] args) throws Exception {
        TransportNetwork network = KryoNetworkSerializer.read(new File(args[0]));
        List<Pt> origins = readCsv(Path.of(args[1]));
        List<Pt> dests = readCsv(Path.of(args[2]));
        PointSet ps = pointSet(dests);

        RegionalTask t = new RegionalTask();
        t.scenario = new Scenario(); t.scenario.id = "id"; t.scenarioId = "id";
        t.zoneId = network.getTimeZone();
        t.fromLat = origins.get(0).lat; t.fromLon = origins.get(0).lon;
        t.walkSpeed = 1.0f; t.bikeSpeed = 3.3f;
        t.streetTime = 90; t.maxWalkTime = 30; t.maxBikeTime = 30; t.maxCarTime = 30;
        t.maxTripDurationMinutes = 90; t.maxRides = 3; t.bikeTrafficStress = 3;
        t.directModes = EnumSet.of(LegMode.WALK);
        t.accessModes = EnumSet.of(LegMode.WALK);
        t.egressModes = EnumSet.of(LegMode.WALK);
        t.transitModes = EnumSet.allOf(TransitModes.class);
        t.date = LocalDate.parse(args[3]);
        t.fromTime = 7 * 3600; t.toTime = 7 * 3600 + 120 * 60;
        t.monteCarloDraws = 5;
        t.recordTimes = true; t.recordAccessibility = false; t.makeTauiSite = false;
        t.percentiles = new int[]{50};
        t.recordTravelTimeHistograms = true;
        t.destinationPointSets = new PointSet[]{ps};

        OneOriginResult r = new TravelTimeComputer(t, network).computeTravelTimes();
        say("nSamplesPerPoint=" + r.travelTimes.nSamplesPerPoint + " nPoints=" + r.travelTimes.nPoints);
        Method getHistogram = r.travelTimes.getClass().getMethod("getHistogram", int.class);
        int[][] v = r.travelTimes.getValues();

        int shown = 0;
        for (int d = 0; d < v[0].length && shown < 3; d++) {
            if (v[0][d] > 120) continue;
            Object h = getHistogram.invoke(r.travelTimes, d);
            say("dest#" + d + " p50=" + v[0][d] + " histogram class=" + (h == null ? "null" : h.getClass().getSimpleName())
                    + " value=" + (h instanceof int[] a ? summarise(a) : String.valueOf(h)));
            shown++;
        }
        // how many of the 120 departure minutes are within 30 / 45 / 60 min?
        for (int d = 0; d < v[0].length && d < 400; d++) {
            if (v[0][d] > 120) continue;
            Object h = getHistogram.invoke(r.travelTimes, d);
            if (h instanceof int[] a) {
                say("dest#" + d + " minutesWithin30=" + cum(a, 30) + " within45=" + cum(a, 45)
                        + " within60=" + cum(a, 60) + " totalSamples=" + sum(a));
                break;
            }
        }
    }

    private static int cum(int[] hist, int upto) {
        int s = 0;
        for (int i = 0; i < Math.min(upto, hist.length); i++) s += hist[i];
        return s;
    }

    private static int sum(int[] a) { int s = 0; for (int x : a) s += x; return s; }

    private static String summarise(int[] a) {
        StringBuilder sb = new StringBuilder("len=" + a.length + " nonzero:");
        for (int i = 0; i < a.length; i++) if (a[i] != 0) sb.append(" [").append(i).append("]=").append(a[i]);
        return sb.toString();
    }

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
        String[] h = lines.get(0).split(",");
        int iId = idx(h, "id"), iLon = idx(h, "lon"), iLat = idx(h, "lat");
        List<Pt> out = new ArrayList<>();
        for (int i = 1; i < lines.size(); i++) {
            if (lines.get(i).isBlank()) continue;
            String[] c = lines.get(i).split(",");
            out.add(new Pt(c[iId], Double.parseDouble(c[iLon]), Double.parseDouble(c[iLat])));
        }
        return out;
    }

    private static int idx(String[] h, String n) {
        for (int i = 0; i < h.length; i++) if (h[i].trim().equalsIgnoreCase(n)) return i;
        throw new IllegalArgumentException("no column " + n);
    }

    private static void say(String s) { System.out.println("PROBE3: " + s); }

    record Pt(String id, double lon, double lat) {}
}
