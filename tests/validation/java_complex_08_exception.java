import java.util.*;

// Complex Java: Exception Handling logic
public class java_complex_08_exception {
    static double riskyOperation(int i) throws Exception {
        if (i % 100 == 0) throw new Exception("Error");
        return 100.0 / (i % 100);
    }

    public static void main(String[] args) {
        int success = 0;
        int failures = 0;
        
        for (int i = 1; i < 10000; i++) {
            try {
                riskyOperation(i);
                success++;
            } catch (Exception e) {
                failures++;
            } finally {
                // Ensure checkpointing handles finally blocks
                if (i % 10000 == 0) System.out.print(".");
            }
        }
        System.out.println("\nSuccess: " + success + ", Failures: " + failures);
    }
}