package codegreen.runtime;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.regex.Pattern;

/**
 * CodeGreen Standalone Runtime for Java (no JNI).
 *
 * Brings the standalone runtime to parity with the C++ {@code nemb}
 * backend's {@code EnergyMeter::Impl::mark_checkpoint}: per-call data
 * is aggregated in thread-local state and flushed ONCE on shutdown,
 * instead of streamed one line per call through {@code System.err}.
 *
 * Why this matters: per-call {@code System.err.println} costs
 * 5-15 microseconds (stderr monitor lock + autoflush syscall + RAPL
 * sysfs read). For workloads with millions of method enters (nbody
 * N=5M, binarytrees N=12) the instrumented run was 100-1000x slower
 * than the un-instrumented run, biased the measured energy upward,
 * and serialised parallelism through the stderr lock. Aggregating
 * in-process drops per-call overhead to ~0.5-1 microsecond
 * (RAPL read + HashMap update + ArrayDeque push/pop).
 *
 * Numerically equivalent to the legacy emit-per-call format. The
 * {@code cli.py} parser previously reconstructed
 * {@code (calls, inclusive_uj, exclusive_uj, time_ns)} per method
 * from the event stream; we now compute the same four numbers
 * in-process using the identical stack-based algorithm and emit one
 * {@code CG_CP_SUM|} record per (thread, method). The legacy
 * {@code CG_CP|} per-event format is retained as a compile-time
 * fallback (system property {@code codegreen.standalone.legacy=true})
 * for replay regressions.
 *
 * Output: appended to the file named by {@code CG_CP_CHECKPOINT_FILE}
 * (set by the CLI per run); {@code System.err} only when it is unset.
 *
 * Poller settings (system property, else environment variable; no defaults, the CLI
 * exports them from runtime_injection.env in configs/java.json):
 *   codegreen.rapl.root    / CODEGREEN_RAPL_ROOT    directory holding the powercap zones
 *   codegreen.rapl.zone    / CODEGREEN_RAPL_ZONE    regex on zone directory names
 *   codegreen.rapl.domain  / CODEGREEN_RAPL_DOMAIN  regex on the zone's name file
 *   codegreen.rapl.poll_us / CODEGREEN_RAPL_POLL_US poll period in microseconds
 *
 * Wire format on shutdown: one poller line per JVM (a single-line JSON object shaped like
 * the NEMB sampler block, ABI 4), then one line per (thread, method):
 *   CG_CP_META|{"marker_reads":"last_poll","interval_ms":D,"readings":N,"failed_reads":N,"first_ns":N,"last_ns":N,"max_gap_ns":N,"affinity_cpus":N,"sampler_affinity_cpus":N,"providers":[{"name":"intel_rapl","hardware_type":"cpu","energy_source":"counter","boundary_source":"counter","update_interval_ms":D,"counter_group":"cpu_package","rejected":0,"held":0}]}
 *   CG_CP_SUM|tid|name|calls|inclusive_uj|exclusive_uj|time_ns
 * max_gap_ns includes the gap from the last poll to shutdown; update_interval_ms is the observed
 * mean period between counter advances (the whole polled span when it advanced fewer than twice).
 */
public class CodeGreenStandaloneRuntime {

    private static final boolean LEGACY_EMIT =
        Boolean.parseBoolean(System.getProperty("codegreen.standalone.legacy", "false"));
    // Sums every zone under RAPL_ROOT whose directory matches RAPL_ZONE and whose name file
    // matches RAPL_DOMAIN. The counter advances once per RAPL update period, so a per-call
    // sysfs read returns no more information than the latest periodic reading while costing
    // a syscall pair on every enter and exit (call-heavy code ran 30x+ slower). One poller
    // thread reads the counters every POLL_NS and publishes the cumulative energy since
    // startup; checkpoints read the published value (marker_reads "last_poll").
    private static final String RAPL_ROOT = setting("codegreen.rapl.root", "CODEGREEN_RAPL_ROOT");
    private static final Pattern RAPL_ZONE = Pattern.compile(setting("codegreen.rapl.zone", "CODEGREEN_RAPL_ZONE"));
    private static final Pattern RAPL_DOMAIN = Pattern.compile(setting("codegreen.rapl.domain", "CODEGREEN_RAPL_DOMAIN"));
    private static final long POLL_NS = Long.parseLong(setting("codegreen.rapl.poll_us", "CODEGREEN_RAPL_POLL_US")) * 1000L;
    private static final int AFFINITY_CPUS = allowedCpus("/proc/self/status");
    private static volatile long raplUj = 0L;
    // Poller coverage, published by the poller as one immutable snapshot per poll so the
    // shutdown hook reads a consistent set: [polls, first_ns, last_ns, max_gap_ns,
    // failed_reads, counter_advances, first_advance_ns, last_advance_ns, sampler_affinity_cpus].
    private static volatile long[] stats = new long[9];

    // Per-method counters PER THREAD. Keeping the map thread-local
    // (no synchronization on the hot path) mirrors the C++ backend
    // (codegreen_energy.cpp:180). The shutdown hook merges across
    // threads.
    //
    // Layout of the long[] value: [calls, inclusive_uj, exclusive_uj, time_ns].
    private static final ThreadLocal<HashMap<String, long[]>> tlAgg =
        ThreadLocal.withInitial(HashMap::new);

    // Frame stack per thread. ArrayDeque is the JDK's recommended
    // non-thread-safe deque; we never share these across threads.
    //
    // Layout of the long[] frame: [enter_ts_ns, enter_energy_uj, callee_energy_uj].
    private static final ThreadLocal<Deque<long[]>> tlStack =
        ThreadLocal.withInitial(ArrayDeque::new);

    // Per-thread name (captured first time we see a thread) so the
    // shutdown hook can emit a stable identifier. Concurrent because
    // many threads register, one thread reads on shutdown.
    private static final java.util.concurrent.ConcurrentHashMap<Long, String> tlNames =
        new java.util.concurrent.ConcurrentHashMap<>();

    // Registry of per-thread aggregator maps so the shutdown hook
    // (which runs on a different thread) can walk every worker's
    // state. We register at first-checkpoint time on each thread.
    private static final ConcurrentLinkedQueue<ThreadState> registry =
        new ConcurrentLinkedQueue<>();

    private static final class ThreadState {
        final long tid;
        final String name;
        final HashMap<String, long[]> agg;
        ThreadState(long tid, String name, HashMap<String, long[]> agg) {
            this.tid = tid; this.name = name; this.agg = agg;
        }
    }

    private static final ThreadLocal<Boolean> tlRegistered =
        ThreadLocal.withInitial(() -> Boolean.FALSE);

    private static final class Domain {
        final String path;
        final RandomAccessFile fd;
        final long range;
        final byte[] buf = new byte[32];
        long last;

        Domain(File dir) throws IOException {
            path = dir.getPath();
            fd = new RandomAccessFile(new File(dir, "energy_uj"), "r");
            range = Long.parseLong(new String(Files.readAllBytes(new File(dir, "max_energy_range_uj").toPath()),
                StandardCharsets.US_ASCII).trim());
            last = read();
        }

        long read() throws IOException {
            fd.seek(0);
            int n = fd.read(buf);
            return Long.parseLong(new String(buf, 0, Math.max(n, 0), StandardCharsets.US_ASCII).trim());
        }

        long delta() throws IOException {
            long cur = read();
            long d = cur >= last ? cur - last : cur + range - last;
            last = cur;
            return d;
        }
    }

    private static String setting(String prop, String env) {
        String v = System.getProperty(prop, System.getenv(env));
        if (v == null || v.isEmpty()) {
            throw new IllegalStateException("CodeGreen: " + env + " (or -D" + prop + ") is unset; `codegreen project`"
                + " exports it from runtime_injection.env in configs/java.json.");
        }
        return v;
    }

    // CPUs in the Cpus_allowed_list of a /proc status file (process or calling thread).
    private static int allowedCpus(String status) {
        try {
            for (String line : Files.readAllLines(Paths.get(status), StandardCharsets.US_ASCII)) {
                if (!line.startsWith("Cpus_allowed_list:")) continue;
                int n = 0;
                for (String part : line.substring(18).trim().split(",")) {
                    String[] r = part.split("-");
                    n += r.length == 1 ? 1 : Integer.parseInt(r[1]) - Integer.parseInt(r[0]) + 1;
                }
                return n;
            }
        } catch (IOException | NumberFormatException e) {
            throw new IllegalStateException("CodeGreen: cannot read the CPU affinity from " + status + " (" + e + ")", e);
        }
        throw new IllegalStateException("CodeGreen: no Cpus_allowed_list in " + status);
    }

    private static Domain[] openDomains() {
        File[] dirs = new File(RAPL_ROOT).listFiles((d, n) -> RAPL_ZONE.matcher(n).matches());
        List<Domain> out = new ArrayList<>();
        if (dirs != null) {
            Arrays.sort(dirs);
            for (File dir : dirs) {
                try {
                    if (!RAPL_DOMAIN.matcher(new String(Files.readAllBytes(new File(dir, "name").toPath()),
                            StandardCharsets.US_ASCII).trim()).matches()) continue;
                    out.add(new Domain(dir));
                } catch (IOException | NumberFormatException e) {
                    throw new IllegalStateException("CodeGreen: cannot read RAPL domain " + dir
                        + " (" + e + "); per-function energy would be wrong. Grant read access to energy_uj.", e);
                }
            }
        }
        if (out.isEmpty()) {
            throw new IllegalStateException("CodeGreen: no zone matching " + RAPL_ZONE + " with a name matching "
                + RAPL_DOMAIN + " under " + RAPL_ROOT + "; per-function energy is unavailable on this host.");
        }
        return out.toArray(new Domain[0]);
    }

    static {
        final Domain[] domains = openDomains();
        Runtime.getRuntime().addShutdownHook(new Thread(
            CodeGreenStandaloneRuntime::flushOnExit, "cg-flush"));
        Thread poller = new Thread(() -> {
            long total = 0L, polls = 0L, firstNs = 0L, lastNs = 0L, maxGapNs = 0L, failed = 0L;
            long advances = 0L, firstAdv = 0L, lastAdv = 0L;
            final long samplerCpus = allowedCpus("/proc/thread-self/status");
            while (true) {
                long before = total;
                // A failed read leaves that domain's last value in place, so the next good read
                // carries its energy; every failure is counted and reported (failed_reads).
                for (Domain d : domains) {
                    try {
                        total += d.delta();
                    } catch (IOException | NumberFormatException e) {
                        failed++;
                    }
                }
                raplUj = total;
                long now = System.nanoTime();
                if (polls == 0L) firstNs = now; else maxGapNs = Math.max(maxGapNs, now - lastNs);
                lastNs = now;
                polls++;
                if (total != before) {
                    if (advances == 0L) firstAdv = now;
                    lastAdv = now;
                    advances++;
                }
                stats = new long[] { polls, firstNs, lastNs, maxGapNs, failed, advances, firstAdv, lastAdv, samplerCpus };
                java.util.concurrent.locks.LockSupport.parkNanos(POLL_NS);
            }
        }, "cg-rapl");
        poller.setDaemon(true);
        poller.start();
    }

    private static void registerThreadIfNeeded() {
        if (tlRegistered.get()) return;
        Thread t = Thread.currentThread();
        long tid = t.getId();
        String name = t.getName();
        tlNames.put(tid, name);
        registry.add(new ThreadState(tid, name, tlAgg.get()));
        tlRegistered.set(Boolean.TRUE);
    }

    /**
     * Public checkpoint API. Same signature as the legacy emit-only
     * runtime so source-rewriting in
     * {@code _rewrite_instrumented_for_standalone} stays unchanged.
     *
     * @param id   per-call site identifier (line + offset, generated
     *             by the instrumentation engine; we ignore it in the
     *             aggregation path but emit it in the legacy path so
     *             {@code codegreen.standalone.legacy=true} reproduces
     *             the old wire format byte-for-byte).
     * @param name fully-qualified method name (Class.method form).
     * @param type {@code "enter"} or {@code "exit"}.
     */
    public static void checkpoint(String id, String name, String type) {
        if (LEGACY_EMIT) {
            long energy_uj = raplUj;
            long ts = System.nanoTime();
            long tid = Thread.currentThread().getId();
            System.err.println("CG_CP|" + type + "|" + name + "|" + id
                + "|" + ts + "|" + energy_uj + "|" + tid);
            return;
        }
        registerThreadIfNeeded();
        long energy_uj = raplUj;
        long ts = System.nanoTime();
        Deque<long[]> stack = tlStack.get();
        if ("enter".equals(type)) {
            // Frame: [enter_ts_ns, enter_energy_uj, callee_energy_uj]
            stack.push(new long[] { ts, energy_uj, 0L });
            return;
        }
        // "exit": pop and accumulate. Defensive against malformed
        // pairs (unmatched exit) — drop the event silently if the
        // stack is empty, the parser path used to ignore this too.
        long[] frame = stack.pollFirst();
        if (frame == null) return;
        long inclusive_uj = Math.max(0L, energy_uj - frame[1]);
        long inclusive_ns = Math.max(0L, ts - frame[0]);
        long exclusive_uj = Math.max(0L, inclusive_uj - frame[2]);
        // Credit the parent (if any) so its `callee_energy_uj` grows
        // — exact same algorithm as the C++ backend stack accounting
        // and the legacy Python parser at cli.py:3620-3650.
        long[] parent = stack.peekFirst();
        if (parent != null) {
            parent[2] += inclusive_uj;
        }
        HashMap<String, long[]> agg = tlAgg.get();
        long[] row = agg.get(name);
        if (row == null) {
            row = new long[] { 0L, 0L, 0L, 0L };
            agg.put(name, row);
        }
        row[0] += 1L;
        row[1] += inclusive_uj;
        row[2] += exclusive_uj;
        row[3] += inclusive_ns;
    }

    private static void flushOnExit() {
        // One CG_CP_SUM line per (thread, method), appended in a single write
        // to the file named by CG_CP_CHECKPOINT_FILE (set by the CLI per run).
        // stderr is not reliable here: a JMH-forked JVM's System.err is JMH's
        // forwarding link, which may already be closed when shutdown hooks
        // run, and that silently dropped the hot methods of whole forks.
        // O_APPEND keeps blocks from concurrent forks intact.
        StringBuilder sb = new StringBuilder(8 * 1024);
        // The gap from the last poll to shutdown counts too: a poller that died
        // or never ran shows as one large gap.
        long[] s = stats;
        double updateMs = (s[5] > 1L ? (double) (s[7] - s[6]) / (s[5] - 1L) : (double) (s[2] - s[1])) / 1e6;
        sb.append("CG_CP_META|{\"marker_reads\":\"last_poll\",\"interval_ms\":").append(POLL_NS / 1e6)
          .append(",\"readings\":").append(s[0]).append(",\"failed_reads\":").append(s[4])
          .append(",\"first_ns\":").append(s[1]).append(",\"last_ns\":").append(s[2])
          .append(",\"max_gap_ns\":").append(Math.max(s[3], System.nanoTime() - s[2]))
          .append(",\"affinity_cpus\":").append(AFFINITY_CPUS).append(",\"sampler_affinity_cpus\":").append(s[8])
          .append(",\"providers\":[{\"name\":\"intel_rapl\",\"hardware_type\":\"cpu\",\"energy_source\":\"counter\"")
          .append(",\"boundary_source\":\"counter\"")
          .append(",\"update_interval_ms\":").append(updateMs)
          .append(",\"counter_group\":\"cpu_package\",\"rejected\":0,\"held\":0}]}\n");
        for (ThreadState ts : registry) {
            for (Map.Entry<String, long[]> e : ts.agg.entrySet()) {
                long[] r = e.getValue();
                sb.append("CG_CP_SUM|").append(ts.tid).append('|')
                  .append(e.getKey()).append('|')
                  .append(r[0]).append('|').append(r[1]).append('|')
                  .append(r[2]).append('|').append(r[3]).append('\n');
            }
        }
        String path = System.getenv("CG_CP_CHECKPOINT_FILE");
        try {
            if (path != null && !path.isEmpty()) {
                try (java.io.FileOutputStream out = new java.io.FileOutputStream(path, true)) {
                    out.write(sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
            } else {
                System.err.print(sb);
                System.err.flush();
            }
        } catch (Exception ex) {
            // Shutdown-hook errors must not crash the JVM; the CLI rejects a
            // run whose instrumented points produced no records.
        }
    }
}
