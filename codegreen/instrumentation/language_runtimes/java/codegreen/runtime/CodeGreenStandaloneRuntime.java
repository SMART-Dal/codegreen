package codegreen.runtime;

/**
 * CodeGreen Standalone Runtime for Java
 *
 * Pure-Java energy measurement via RAPL sysfs. No JNI dependency.
 * Emits checkpoint data to stderr for external parsing.
 * Used for project-level instrumentation where the NEMB native library
 * may not be on the classpath.
 *
 * RAPL I/O: File descriptor cached (opened once, seek+read per checkpoint).
 * Overhead: ~2 syscalls per checkpoint (lseek + read) vs 3 for Files.readAllBytes.
 *
 * Output format per checkpoint (stderr):
 *   CG_CP|type|name|id|timestamp_ns|energy_uj|thread_id
 */
public class CodeGreenStandaloneRuntime {
    private static final String RAPL_PKG_PATH = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj";
    private static java.io.RandomAccessFile raplFile;
    private static final byte[] raplBuf = new byte[32];

    private static long readRAPL() {
        try {
            if (raplFile == null) {
                raplFile = new java.io.RandomAccessFile(RAPL_PKG_PATH, "r");
            }
            raplFile.seek(0);
            int n = raplFile.read(raplBuf);
            if (n > 0) {
                return Long.parseLong(new String(raplBuf, 0, n).trim());
            }
        } catch (Exception e) {
            // Fall through
        }
        return 0;
    }

    public static void checkpoint(String id, String name, String type) {
        long energy_uj = readRAPL();
        long ts = System.nanoTime();
        long tid = Thread.currentThread().getId();
        System.err.println("CG_CP|" + type + "|" + name + "|" + id + "|" + ts + "|" + energy_uj + "|" + tid);
    }
}
