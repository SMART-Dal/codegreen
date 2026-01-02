import java.util.*;
import java.time.Duration;
import java.time.Instant;
import java.util.stream.IntStream;
import java.util.stream.Collectors;

/**
 * Comprehensive Java Sample for CodeGreen Testing
 * Tests various language constructs and checkpoint generation
 */

public class JavaSample {
    
    // Static variables to test static scope
    private static int staticCounter = 0;
    private static double staticSum = 0.0;
    
    // Instance variables
    private List<Double> data;
    private int processedCount;
    
    // Constructor
    public JavaSample(List<Double> inputData) {
        this.data = new ArrayList<>(inputData);
        this.processedCount = 0;
    }
    
    /**
     * Process data with various operations
     */
    public List<Double> processData() {
        List<Double> results = new ArrayList<>();
        
        // Test loop checkpoint
        for (int i = 0; i < data.size(); i++) {
            Double value = data.get(i);
            if (value > 0) {
                // Test conditional checkpoint
                double processed = Math.sqrt(value) * 2.0;
                results.add(processed);
                processedCount++;
            }
        }
        
        return results;
    }
    
    /**
     * Calculate statistics
     */
    public Map<String, Double> getStatistics() {
        if (data.isEmpty()) {
            return new HashMap<>();
        }
        
        double sum = data.stream().mapToDouble(Double::doubleValue).sum();
        double max = data.stream().mapToDouble(Double::doubleValue).max().orElse(0.0);
        double min = data.stream().mapToDouble(Double::doubleValue).min().orElse(0.0);
        
        Map<String, Double> stats = new HashMap<>();
        stats.put("mean", sum / data.size());
        stats.put("max", max);
        stats.put("min", min);
        stats.put("processed", (double) processedCount);
        
        return stats;
    }
    
    /**
     * Recursive Fibonacci
     */
    public static int fibonacciRecursive(int n) {
        if (n <= 1) return n;
        return fibonacciRecursive(n - 1) + fibonacciRecursive(n - 2);
    }
    
    /**
     * Iterative Fibonacci
     */
    public static int fibonacciIterative(int n) {
        if (n <= 1) return n;
        
        int a = 0, b = 1;
        for (int i = 2; i <= n; i++) {
            int temp = a + b;
            a = b;
            b = temp;
        }
        return b;
    }
    
    /**
     * Generate squares using streams
     */
    public static List<Integer> generateSquares(int count) {
        return IntStream.range(0, count)
                       .map(i -> i * i)
                       .boxed()
                       .collect(Collectors.toList());
    }
    
    /**
     * Test exception handling
     */
    public static void testExceptionHandling() {
        try {
            int[] arr = new int[5];
            System.out.println("Array element: " + arr[10]); // This will cause ArrayIndexOutOfBoundsException
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("Caught exception: " + e.getMessage());
        } catch (Exception e) {
            System.out.println("Caught general exception: " + e.getMessage());
        } finally {
            System.out.println("Finally block executed");
        }
    }
    
    /**
     * Test generics
     */
    public static <T> void printArray(T[] array) {
        System.out.print("Array contents: ");
        for (T element : array) {
            System.out.print(element + " ");
        }
        System.out.println();
    }
    
    /**
     * Main method
     */
    public static void main(String[] args) {
        System.out.println("🚀 CodeGreen Java Language Test");
        System.out.println("=================================");
        
        // Test data processing
        List<Double> data = Arrays.asList(1.0, 4.0, 9.0, 16.0, 25.0, -1.0, 36.0);
        JavaSample processor = new JavaSample(data);
        
        System.out.print("Input data: ");
        data.forEach(value -> System.out.print(value + " "));
        System.out.println();
        
        // Process data
        Instant startTime = Instant.now();
        List<Double> results = processor.processData();
        Instant endTime = Instant.now();
        
        Duration processingTime = Duration.between(startTime, endTime);
        
        System.out.print("Processed results: ");
        results.forEach(value -> System.out.print(value + " "));
        System.out.println();
        System.out.println("Processing time: " + processingTime.toNanos() / 1_000_000.0 + " milliseconds");
        
        // Get statistics
        Map<String, Double> stats = processor.getStatistics();
        System.out.println("Statistics: " + stats);
        
        // Test Fibonacci functions
        System.out.println("\n🧮 Testing Fibonacci functions:");
        for (int i = 0; i < 8; i++) {
            int fibRec = fibonacciRecursive(i);
            int fibIter = fibonacciIterative(i);
            System.out.printf("F(%d) = %d (recursive), %d (iterative)%n", i, fibRec, fibIter);
        }
        
        // Test stream operations
        System.out.println("\n📊 Testing stream operations:");
        List<Integer> squares = generateSquares(5);
        System.out.println("Squares: " + squares);
        
        int sumSquares = squares.stream().mapToInt(Integer::intValue).sum();
        System.out.println("Sum of squares: " + sumSquares);
        
        // Test collections
        System.out.println("\n🔢 Testing collections:");
        List<Integer> numbers = Arrays.asList(3, 1, 4, 1, 5, 9, 2, 6);
        System.out.println("Original list: " + numbers);
        
        List<Integer> sortedNumbers = new ArrayList<>(numbers);
        Collections.sort(sortedNumbers);
        System.out.println("Sorted list: " + sortedNumbers);
        
        // Test generics
        System.out.println("\n🔧 Testing generics:");
        String[] stringArray = {"Hello", "World", "Java"};
        Integer[] intArray = {1, 2, 3, 4, 5};
        
        printArray(stringArray);
        printArray(intArray);
        
        // Test exception handling
        System.out.println("\n⚠️ Testing exception handling:");
        testExceptionHandling();
        
        // Test static variables
        staticCounter++;
        staticSum += 42.0;
        System.out.println("Static counter: " + staticCounter + ", Static sum: " + staticSum);
        
        // Test lambda expressions
        System.out.println("\nλ Testing lambda expressions:");
        List<String> words = Arrays.asList("Hello", "CodeGreen", "Java", "Testing");
        words.stream()
             .filter(word -> word.length() > 4)
             .map(String::toUpperCase)
             .forEach(System.out::println);
        
        System.out.println("\n✅ Java language test completed successfully!");
    }
}
