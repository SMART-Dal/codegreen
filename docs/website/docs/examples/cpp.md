# C/C++ Examples

Practical examples of using CodeGreen with C and C++ programs.

## Basic C++ Energy Measurement

```cpp
// matrix_multiply.cpp
#include <iostream>
#include <vector>
#include <chrono>

double matrix_multiply(int size) {
    std::vector<std::vector<double>> a(size, std::vector<double>(size, 1.0));
    std::vector<std::vector<double>> b(size, std::vector<double>(size, 2.0));
    std::vector<std::vector<double>> c(size, std::vector<double>(size, 0.0));

    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            for (int k = 0; k < size; k++) {
                c[i][j] += a[i][k] * b[k][j];
            }
        }
    }

    // Return result to prevent dead code elimination
    return c[0][0];
}

int main() {
    std::cout << "Result: " << matrix_multiply(500) << std::endl;
    return 0;
}
```

**Measure:**
```bash
codegreen measure cpp matrix_multiply.cpp --precision high --output results.json
```

## C Example with Multiple Functions

```c
// compute.c
#include <stdio.h>
#include <math.h>

double compute_pi(int iterations) {
    double pi = 0.0;
    for (int i = 0; i < iterations; i++) {
        pi += (i % 2 == 0 ? 1.0 : -1.0) / (2.0 * i + 1.0);
    }
    return pi * 4.0;
}

double factorial(int n) {
    double result = 1.0;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int main() {
    double pi = compute_pi(10000000);
    double fact = factorial(100);

    printf("Pi approximation: %.10f\n", pi);
    printf("Factorial result: %.2e\n", fact);

    return 0;
}
```

**Measure:**
```bash
codegreen measure c compute.c --precision high --json
```

## Algorithm Comparison

Compare energy consumption of different sorting algorithms:

```cpp
// sorting_comparison.cpp
#include <iostream>
#include <vector>
#include <algorithm>
#include <random>

std::vector<int> generate_data(int size) {
    std::vector<int> data(size);
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(1, 10000);

    for (int i = 0; i < size; i++) {
        data[i] = dis(gen);
    }
    return data;
}

int bubble_sort(std::vector<int> arr) {
    int n = arr.size();
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                std::swap(arr[j], arr[j + 1]);
            }
        }
    }
    return arr[0];  // Return to prevent DCE
}

int merge_sort_impl(std::vector<int>& arr, int left, int right) {
    if (left >= right) return 0;

    int mid = left + (right - left) / 2;
    merge_sort_impl(arr, left, mid);
    merge_sort_impl(arr, mid + 1, right);

    std::vector<int> temp(right - left + 1);
    int i = left, j = mid + 1, k = 0;

    while (i <= mid && j <= right) {
        temp[k++] = (arr[i] <= arr[j]) ? arr[i++] : arr[j++];
    }
    while (i <= mid) temp[k++] = arr[i++];
    while (j <= right) temp[k++] = arr[j++];

    for (int i = 0; i < k; i++) {
        arr[left + i] = temp[i];
    }
    return arr[left];
}

int merge_sort(std::vector<int> arr) {
    merge_sort_impl(arr, 0, arr.size() - 1);
    return arr[0];
}

int main() {
    auto data = generate_data(5000);

    std::cout << "Bubble sort result: " << bubble_sort(data) << std::endl;
    std::cout << "Merge sort result: " << merge_sort(data) << std::endl;

    return 0;
}
```

**Measure and compare:**
```bash
codegreen measure cpp sorting_comparison.cpp --precision high --output sorting_energy.json
```

**Expected output:**
```json
{
  "functions": {
    "bubble_sort": {
      "total_energy_joules": 12.45,
      "execution_time_ms": 1250.3,
      "average_power_watts": 9.96
    },
    "merge_sort": {
      "total_energy_joules": 0.85,
      "execution_time_ms": 85.2,
      "average_power_watts": 9.98
    }
  }
}
```

## Optimization Example

Measure before and after optimization:

**Before (cache-unfriendly):**
```cpp
// matrix_transpose_slow.cpp
#include <iostream>
#include <vector>

double transpose_slow(int size) {
    std::vector<std::vector<double>> matrix(size, std::vector<double>(size));
    std::vector<std::vector<double>> result(size, std::vector<double>(size));

    // Initialize
    for (int i = 0; i < size; i++)
        for (int j = 0; j < size; j++)
            matrix[i][j] = i * size + j;

    // Transpose (column-major access - cache unfriendly)
    for (int j = 0; j < size; j++)
        for (int i = 0; i < size; i++)
            result[i][j] = matrix[j][i];

    return result[0][0];
}

int main() {
    std::cout << transpose_slow(2000) << std::endl;
    return 0;
}
```

**After (cache-friendly):**
```cpp
// matrix_transpose_fast.cpp
#include <iostream>
#include <vector>

double transpose_fast(int size) {
    std::vector<std::vector<double>> matrix(size, std::vector<double>(size));
    std::vector<std::vector<double>> result(size, std::vector<double>(size));

    // Initialize
    for (int i = 0; i < size; i++)
        for (int j = 0; j < size; j++)
            matrix[i][j] = i * size + j;

    // Transpose (row-major access - cache friendly)
    for (int i = 0; i < size; i++)
        for (int j = 0; j < size; j++)
            result[j][i] = matrix[i][j];

    return result[0][0];
}

int main() {
    std::cout << transpose_fast(2000) << std::endl;
    return 0;
}
```

**Measure both:**
```bash
codegreen measure cpp matrix_transpose_slow.cpp --output slow.json
codegreen measure cpp matrix_transpose_fast.cpp --output fast.json
```

**Energy savings:** Cache-friendly version typically uses 15-30% less energy.

## Working with NEMB Runtime Directly

For advanced users who want direct checkpoint control:

```cpp
// manual_checkpoints.cpp
#include <iostream>
#include <codegreen_runtime.h>

double heavy_computation() {
    double sum = 0.0;
    for (int i = 0; i < 10000000; i++) {
        sum += sin(i) * cos(i);
    }
    return sum;
}

int main() {
    nemb_initialize();

    nemb_mark_checkpoint("main_start");

    double result = heavy_computation();

    nemb_mark_checkpoint("computation_done");

    std::cout << "Result: " << result << std::endl;

    nemb_mark_checkpoint("main_end");

    return 0;
}
```

**Compile and run:**
```bash
g++ -o manual_checkpoints manual_checkpoints.cpp -lcodegreen-nemb -lm
./manual_checkpoints
```

## Build Options

### Recommended Compiler Flags

For accurate measurements, disable optimizations during profiling:

```bash
# Debug build (no optimizations)
g++ -O0 -g program.cpp -o program

# Measure with CodeGreen
codegreen measure cpp program.cpp
```

### Production Optimization Comparison

Compare energy across optimization levels:

```bash
# Measure O0
g++ -O0 program.cpp -o program_O0
codegreen measure --instrumented ./program_O0 --output O0.json

# Measure O2
g++ -O2 program.cpp -o program_O2
codegreen measure --instrumented ./program_O2 --output O2.json

# Measure O3
g++ -O3 program.cpp -o program_O3
codegreen measure --instrumented ./program_O3 --output O3.json
```

## Best Practices

1. **Prevent Dead Code Elimination**: Always use computation results (return, print, or volatile)
2. **Disable Optimizations**: Use `-O0` during profiling for accurate attribution
3. **Warm-up Iterations**: Run once before measuring to avoid cold-start overhead
4. **Consistent Input**: Use same data for algorithm comparisons
5. **Multiple Runs**: Average results across 3-5 runs for stability

## See Also

- [CLI Reference](../user-guide/cli-reference.md) - Complete command options
- [Configuration](../getting-started/configuration.md) - Compiler flag settings
- [Python Examples](python.md) - Python energy profiling
