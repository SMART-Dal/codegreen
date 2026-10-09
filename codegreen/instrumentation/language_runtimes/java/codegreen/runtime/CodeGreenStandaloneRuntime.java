package codegreen.runtime;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentLinkedQueue;

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
 * Wire format (one line per (thread, method) on shutdown):
 *   CG_CP_SUM|tid|name|calls|inclusive_uj|exclusive_uj|time_ns
 */
public class CodeGreenStandaloneRuntime {

    // Sums every top-level package domain (intel-rapl:N whose name starts with
    // "package") under this root; sub-domains (core, dram) are already included
    // in the package counter, and non-package domains (psys) are skipped.
    private static final String RAPL_ROOT =
        System.getProperty("codegreen.rapl.root", "/sys/class/powercap/intel-rapl");
    private static final boolean LEGACY_EMIT =
        Boolean.parseBoolean(System.getProperty("codegreen.standalone.legacy", "false"));

    // The package energy counter advances only once per RAPL update period
    // (~1 ms), so a per-call sysfs read returns no more information than the
    // latest periodic reading while costing a syscall pair on every enter and
    // exit. That cost made instrumented runs of call-heavy code 30x+ slower
    // (RoaringBitmap's JMH setup exceeded an hour). One poller thread reads
    // the counters at the update period (property codegreen.rapl.poll_us,
    // default 1000) and publishes the cumulative energy since startup;
    // checkpoints read the published value.
    private static final long POLL_NS = Long.getLong("codegreen.rapl.poll_us", 1000L) * 1000L;
    private static volatile long raplUj = 0L;

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

    private static Domain[] openPackageDomains() {
        File[] dirs = new File(RAPL_ROOT).listFiles((d, n) -> n.matches("intel-rapl:\\d+"));
        List<Domain> out = new ArrayList<>();
        if (dirs != null) {
            Arrays.sort(dirs);
            for (File dir : dirs) {
                try {
                    if (!new String(Files.readAllBytes(new File(dir, "name").toPath()),
                            StandardCharsets.US_ASCII).trim().startsWith("package")) continue;
                    out.add(new Domain(dir));
                } catch (IOException | NumberFormatException e) {
                    throw new IllegalStateException("CodeGreen: cannot read RAPL domain " + dir
                        + " (" + e + "); per-function energy would be wrong. Grant read access to energy_uj.", e);
                }
            }
        }
        if (out.isEmpty()) {
            throw new IllegalStateException("CodeGreen: no RAPL package domain under " + RAPL_ROOT
                + "; per-function energy is unavailable on this host.");
        }
        return out.toArray(new Domain[0]);
    }

    static {
        final Domain[] domains = openPackageDomains();
        Runtime.getRuntime().addShutdownHook(new Thread(
            CodeGreenStandaloneRuntime::flushOnExit, "cg-flush"));
        Thread poller = new Thread(() -> {
            long total = 0L;
            while (true) {
                try {
                    for (Domain d : domains) total += d.delta();
                } catch (IOException | NumberFormatException e) {
                    System.err.println("CodeGreen: RAPL read failed (" + e + "); energy counter frozen from here on.");
                    return;
                }
                raplUj = total;
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
