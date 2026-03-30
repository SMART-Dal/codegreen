package codegreen.runtime;

/**
 * CodeGreen Runtime for Java
 *
 * Provides lightweight energy measurement with automatic invocation tracking.
 * The NEMB C++ backend handles all invocation counting, keeping this runtime simple.
 */
public class CodeGreenRuntime {
    private static boolean initialized = false;

    static {
        String libPath = System.getProperty("codegreen.lib.path");
        if (libPath != null) {
            System.load(libPath);
        } else {
            System.loadLibrary("codegreen-nemb");
        }
    }

    // Native methods from C++ API
    private static native void nemb_mark_checkpoint(String name);
    private static native void nemb_report_at_exit();

    private static synchronized void initialize() {
        if (!initialized) {
            try {
                Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                    try {
                        nemb_report_at_exit();
                    } catch (UnsatisfiedLinkError e) {}
                }));
                initialized = true;
            } catch (Exception e) {}
        }
    }

    /**
     * Mark a checkpoint.
     *
     * Invocation tracking is handled automatically by the NEMB C++ backend.
     * Each call to the same checkpoint gets a unique invocation counter (#inv_N).
     *
     * @param id Unique checkpoint ID
     * @param name Function/block name
     * @param type Checkpoint type (enter, exit, etc.)
     */
    public static void checkpoint(String id, String name, String type) {
        if (!initialized) initialize();

        // Simple pass-through - invocation counter added by backend
        nemb_mark_checkpoint(type + ":" + name + ":" + id);
    }
}
