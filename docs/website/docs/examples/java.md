# Java Examples

Practical examples of using CodeGreen with Java programs.

## Basic Energy Measurement

```java
// Fibonacci.java
public class Fibonacci {

    public static long fibonacci(int n) {
        if (n <= 1) return n;

        long a = 0, b = 1;
        for (int i = 2; i <= n; i++) {
            long temp = a + b;
            a = b;
            b = temp;
        }
        return b;
    }

    public static void main(String[] args) {
        long result = fibonacci(1000000);
        System.out.println("Fibonacci result: " + result);
    }
}
```

**Measure:**
```bash
codegreen measure java Fibonacci.java --precision high --output results.json
```

## Algorithm Comparison

Compare energy consumption of different sorting implementations:

```java
// SortingComparison.java
import java.util.Arrays;
import java.util.Random;

public class SortingComparison {

    private static int[] generateData(int size) {
        Random rand = new Random(42);
        int[] data = new int[size];
        for (int i = 0; i < size; i++) {
            data[i] = rand.nextInt(10000);
        }
        return data;
    }

    public static int bubbleSort(int[] arr) {
        int n = arr.length;
        for (int i = 0; i < n - 1; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (arr[j] > arr[j + 1]) {
                    int temp = arr[j];
                    arr[j] = arr[j + 1];
                    arr[j + 1] = temp;
                }
            }
        }
        return arr[0];
    }

    public static int quickSort(int[] arr, int low, int high) {
        if (low < high) {
            int pi = partition(arr, low, high);
            quickSort(arr, low, pi - 1);
            quickSort(arr, pi + 1, high);
        }
        return arr.length > 0 ? arr[0] : 0;
    }

    private static int partition(int[] arr, int low, int high) {
        int pivot = arr[high];
        int i = low - 1;

        for (int j = low; j < high; j++) {
            if (arr[j] < pivot) {
                i++;
                int temp = arr[i];
                arr[i] = arr[j];
                arr[j] = temp;
            }
        }

        int temp = arr[i + 1];
        arr[i + 1] = arr[high];
        arr[high] = temp;

        return i + 1;
    }

    public static void main(String[] args) {
        int[] data1 = generateData(5000);
        int[] data2 = Arrays.copyOf(data1, data1.length);

        System.out.println("Bubble sort result: " + bubbleSort(data1));
        System.out.println("Quick sort result: " + quickSort(data2, 0, data2.length - 1));
    }
}
```

**Measure:**
```bash
codegreen measure java SortingComparison.java --precision high --output sorting_energy.json
```

## Data Processing Example

Real-world data processing scenario:

```java
// DataProcessor.java
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class DataProcessor {

    static class Record {
        String id;
        double value;

        Record(String id, double value) {
            this.id = id;
            this.value = value;
        }
    }

    public static List<Record> generateRecords(int count) {
        List<Record> records = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            records.add(new Record("ID" + i, Math.random() * 1000));
        }
        return records;
    }

    public static double processImperative(List<Record> records) {
        double sum = 0.0;
        int count = 0;

        for (Record r : records) {
            if (r.value > 500) {
                sum += r.value;
                count++;
            }
        }

        return count > 0 ? sum / count : 0.0;
    }

    public static double processFunctional(List<Record> records) {
        return records.stream()
            .filter(r -> r.value > 500)
            .mapToDouble(r -> r.value)
            .average()
            .orElse(0.0);
    }

    public static void main(String[] args) {
        List<Record> data = generateRecords(1000000);

        double resultImperative = processImperative(data);
        double resultFunctional = processFunctional(data);

        System.out.println("Imperative result: " + resultImperative);
        System.out.println("Functional result: " + resultFunctional);
    }
}
```

**Compare imperative vs functional style:**
```bash
codegreen measure java DataProcessor.java --precision high --output processing.json
```

## Matrix Operations

CPU-intensive computation example:

```java
// MatrixMultiply.java
public class MatrixMultiply {

    public static double[][] createMatrix(int size, double value) {
        double[][] matrix = new double[size][size];
        for (int i = 0; i < size; i++) {
            for (int j = 0; j < size; j++) {
                matrix[i][j] = value;
            }
        }
        return matrix;
    }

    public static double multiply(double[][] a, double[][] b) {
        int n = a.length;
        double[][] c = new double[n][n];

        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    c[i][j] += a[i][k] * b[k][j];
                }
            }
        }

        return c[0][0];
    }

    public static void main(String[] args) {
        int size = 500;
        double[][] a = createMatrix(size, 1.0);
        double[][] b = createMatrix(size, 2.0);

        double result = multiply(a, b);
        System.out.println("Matrix multiply result: " + result);
    }
}
```

**Measure:**
```bash
codegreen measure java MatrixMultiply.java --precision high
```

## Parallel Processing Comparison

Compare sequential vs parallel stream processing:

```java
// ParallelProcessing.java
import java.util.stream.IntStream;

public class ParallelProcessing {

    public static double computeSequential(int size) {
        return IntStream.range(0, size)
            .mapToDouble(i -> Math.sin(i) * Math.cos(i))
            .sum();
    }

    public static double computeParallel(int size) {
        return IntStream.range(0, size)
            .parallel()
            .mapToDouble(i -> Math.sin(i) * Math.cos(i))
            .sum();
    }

    public static void main(String[] args) {
        int size = 10000000;

        double seqResult = computeSequential(size);
        System.out.println("Sequential result: " + seqResult);

        double parResult = computeParallel(size);
        System.out.println("Parallel result: " + parResult);
    }
}
```

**Measure both approaches:**
```bash
codegreen measure java ParallelProcessing.java --precision high --output parallel_energy.json
```

**Analysis:** Parallel processing may use more total energy but complete faster, resulting in better energy efficiency for large workloads.

## String Processing

Common string operation energy costs:

```java
// StringProcessing.java
public class StringProcessing {

    public static String concatenateWithPlus(int count) {
        String result = "";
        for (int i = 0; i < count; i++) {
            result += "item" + i;
        }
        return result;
    }

    public static String concatenateWithBuilder(int count) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < count; i++) {
            builder.append("item").append(i);
        }
        return builder.toString();
    }

    public static void main(String[] args) {
        int count = 50000;

        String result1 = concatenateWithPlus(count);
        System.out.println("Plus concatenation length: " + result1.length());

        String result2 = concatenateWithBuilder(count);
        System.out.println("StringBuilder length: " + result2.length());
    }
}
```

**Measure:**
```bash
codegreen measure java StringProcessing.java --precision high --output string_energy.json
```

**Expected:** StringBuilder typically uses 70-90% less energy than string concatenation with `+`.

## Recursion vs Iteration

Energy comparison of different implementation styles:

```java
// RecursionVsIteration.java
public class RecursionVsIteration {

    public static long factorialRecursive(int n) {
        if (n <= 1) return 1;
        return n * factorialRecursive(n - 1);
    }

    public static long factorialIterative(int n) {
        long result = 1;
        for (int i = 2; i <= n; i++) {
            result *= i;
        }
        return result;
    }

    public static void main(String[] args) {
        int n = 20;

        long recResult = factorialRecursive(n);
        System.out.println("Recursive factorial: " + recResult);

        long iterResult = factorialIterative(n);
        System.out.println("Iterative factorial: " + iterResult);
    }
}
```

**Measure:**
```bash
codegreen measure java RecursionVsIteration.java --precision high
```

## Best Practices

1. **Use Real Computation**: Avoid `Thread.sleep()` - it measures idle power, not code energy
2. **Warm-up JVM**: Run once before measuring to let JIT compiler optimize
3. **Disable JIT for Profiling**: Use `-Xint` flag for consistent measurements
4. **Return Results**: Prevent dead code elimination by using computation results
5. **Multiple Runs**: Average across 3-5 runs due to JVM non-determinism

## JVM Options for Measurement

### Standard Measurement
```bash
codegreen measure java Program.java --precision high
```

### Disable JIT Compiler (Interpretation Only)
```bash
java -Xint Program.java
codegreen measure --instrumented java -Xint Program.class
```

### Control Heap Size
```bash
java -Xms512m -Xmx512m Program.java
codegreen measure --instrumented java -Xms512m -Xmx512m Program.class
```

## Common Patterns

### Warm-up Before Measurement
```bash
# Run once to warm up JVM
java Program.java

# Now measure with optimized code
codegreen measure java Program.java --precision high
```

### Batch Processing
```bash
# Measure multiple programs
for file in *.java; do
    codegreen measure java "$file" --output "${file%.java}_energy.json"
done
```

## See Also

- [CLI Reference](../user-guide/cli-reference.md) - Complete command options
- [Configuration](../getting-started/configuration.md) - JVM-specific settings
- [Python Examples](python.md) - Python energy profiling
- [C/C++ Examples](cpp.md) - C/C++ energy profiling
