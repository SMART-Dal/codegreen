# Python Examples

Practical examples of using CodeGreen with Python programs.

## Basic Energy Measurement

```python
# hello_energy.py
def greet(name):
    message = f"Hello, {name}!"
    return message

def calculate_sum(n):
    total = sum(range(n))
    return total

def main():
    result = greet("CodeGreen")
    print(result)

    total = calculate_sum(1000000)
    print(f"Sum: {total}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python hello_energy.py --precision high --output results.json
```

**Output:**
```json
{
  "total_energy_joules": 0.145,
  "execution_time_ms": 12.3,
  "functions": {
    "greet": {
      "energy_joules": 0.001,
      "invocations": 1
    },
    "calculate_sum": {
      "energy_joules": 0.142,
      "invocations": 1
    }
  }
}
```

## Algorithm Comparison

Compare energy consumption of different implementations:

```python
# sorting_comparison.py
import random

def generate_data(size):
    random.seed(42)
    return [random.randint(1, 10000) for _ in range(size)]

def bubble_sort(arr):
    n = len(arr)
    arr = arr.copy()
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result

def main():
    data = generate_data(5000)

    bubble_result = bubble_sort(data)
    print(f"Bubble sort first element: {bubble_result[0]}")

    quick_result = quick_sort(data)
    print(f"Quick sort first element: {quick_result[0]}")

    merge_result = merge_sort(data)
    print(f"Merge sort first element: {merge_result[0]}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python sorting_comparison.py --precision high --output sorting.json
```

**Expected results:**
- Bubble sort: ~12 J (O(n²))
- Quick sort: ~0.8 J (O(n log n))
- Merge sort: ~1.2 J (O(n log n))

## Data Processing

Real-world data processing example:

```python
# data_processing.py
import json

def load_data(size):
    return [{"id": i, "value": i * 1.5} for i in range(size)]

def filter_data(data, threshold):
    return [item for item in data if item["value"] > threshold]

def aggregate_data(data):
    total = sum(item["value"] for item in data)
    count = len(data)
    return {"total": total, "average": total / count if count > 0 else 0}

def process_pipeline(size):
    data = load_data(size)
    filtered = filter_data(data, 500)
    result = aggregate_data(filtered)
    return result

def main():
    result = process_pipeline(100000)
    print(f"Total: {result['total']:.2f}")
    print(f"Average: {result['average']:.2f}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python data_processing.py --precision high --json
```

## Machine Learning Example

Energy profiling of ML training:

```python
# ml_training.py
import math

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

def initialize_weights(input_size, output_size):
    return [[0.1] * output_size for _ in range(input_size)]

def forward_pass(inputs, weights):
    return [sum(inputs[i] * weights[i][j] for i in range(len(inputs)))
            for j in range(len(weights[0]))]

def train_epoch(data, weights, learning_rate):
    for inputs, target in data:
        predictions = forward_pass(inputs, weights)
        # Simplified gradient update
        for i in range(len(weights)):
            for j in range(len(weights[0])):
                weights[i][j] += learning_rate * 0.01
    return weights

def train_model(epochs, data_size):
    # Generate synthetic data
    data = [([float(i % 10) / 10 for i in range(5)], 1.0)
            for _ in range(data_size)]

    weights = initialize_weights(5, 3)

    for epoch in range(epochs):
        weights = train_epoch(data, weights, 0.01)

    return weights

def main():
    final_weights = train_model(epochs=100, data_size=1000)
    print(f"Training complete. First weight: {final_weights[0][0]:.4f}")

if __name__ == "__main__":
    main()
```

**Measure training energy:**
```bash
codegreen measure python ml_training.py --precision high --output ml_energy.json
```

## Optimization Example

Before and after optimization:

**Before (inefficient):**
```python
# string_concat_slow.py
def concatenate_slow(n):
    result = ""
    for i in range(n):
        result += f"item{i},"
    return result

def main():
    result = concatenate_slow(50000)
    print(f"Length: {len(result)}")

if __name__ == "__main__":
    main()
```

**After (optimized):**
```python
# string_concat_fast.py
def concatenate_fast(n):
    result = []
    for i in range(n):
        result.append(f"item{i},")
    return "".join(result)

def main():
    result = concatenate_fast(50000)
    print(f"Length: {len(result)}")

if __name__ == "__main__":
    main()
```

**Compare both:**
```bash
codegreen measure python string_concat_slow.py --output slow.json
codegreen measure python string_concat_fast.py --output fast.json
```

**Energy savings:** Optimized version typically uses 70-85% less energy.

## Matrix Operations

CPU-intensive computation:

```python
# matrix_multiply.py
def create_matrix(rows, cols, value):
    return [[value] * cols for _ in range(rows)]

def matrix_multiply(a, b):
    rows_a, cols_a = len(a), len(a[0])
    rows_b, cols_b = len(b), len(b[0])

    if cols_a != rows_b:
        raise ValueError("Matrix dimensions incompatible")

    result = [[0] * cols_b for _ in range(rows_a)]

    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]

    return result

def main():
    size = 200
    a = create_matrix(size, size, 1.5)
    b = create_matrix(size, size, 2.0)

    result = matrix_multiply(a, b)
    print(f"Result[0][0]: {result[0][0]}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python matrix_multiply.py --precision high
```

## Recursive vs Iterative

Energy comparison of implementation styles:

```python
# recursion_vs_iteration.py
def fibonacci_recursive(n):
    if n <= 1:
        return n
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)

def fibonacci_iterative(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def fibonacci_memoized(n, memo=None):
    if memo is None:
        memo = {}
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fibonacci_memoized(n - 1, memo) + fibonacci_memoized(n - 2, memo)
    return memo[n]

def main():
    n = 30

    result_rec = fibonacci_recursive(n)
    print(f"Recursive result: {result_rec}")

    result_iter = fibonacci_iterative(n)
    print(f"Iterative result: {result_iter}")

    result_memo = fibonacci_memoized(n)
    print(f"Memoized result: {result_memo}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python recursion_vs_iteration.py --precision high --output fib_energy.json
```

**Expected:** Recursive: ~8 J, Iterative: ~0.001 J, Memoized: ~0.002 J

## List Comprehension vs Loops

Compare different Python idioms:

```python
# comprehension_vs_loops.py
def process_with_loop(data):
    result = []
    for item in data:
        if item % 2 == 0:
            result.append(item * 2)
    return result

def process_with_comprehension(data):
    return [item * 2 for item in data if item % 2 == 0]

def process_with_map_filter(data):
    return list(map(lambda x: x * 2, filter(lambda x: x % 2 == 0, data)))

def main():
    data = list(range(1000000))

    result1 = process_with_loop(data)
    print(f"Loop result length: {len(result1)}")

    result2 = process_with_comprehension(data)
    print(f"Comprehension result length: {len(result2)}")

    result3 = process_with_map_filter(data)
    print(f"Map/filter result length: {len(result3)}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python comprehension_vs_loops.py --precision high
```

## NumPy vs Pure Python

Energy comparison with NumPy:

```python
# numpy_comparison.py
import numpy as np

def sum_pure_python(size):
    data = list(range(size))
    result = sum(data)
    return result

def sum_numpy(size):
    data = np.arange(size)
    result = np.sum(data)
    return result

def main():
    size = 10000000

    python_result = sum_pure_python(size)
    print(f"Pure Python result: {python_result}")

    numpy_result = sum_numpy(size)
    print(f"NumPy result: {numpy_result}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
codegreen measure python numpy_comparison.py --precision high
```

**Expected:** NumPy typically uses 60-80% less energy for numerical operations.

## Best Practices

1. **Use CLI Measurement**: CodeGreen instruments code automatically via CLI
2. **Avoid I/O During Profiling**: File I/O adds measurement noise
3. **Return Results**: Always use function return values (prevents optimization elimination)
4. **Consistent Data**: Use same seed for random data when comparing
5. **Multiple Runs**: Average 3-5 runs for stable results

## Common Patterns

### Basic Measurement
```bash
codegreen measure python script.py --precision high
```

### Save Results to JSON
```bash
codegreen measure python script.py --output results.json --json
```

### Multiple Sensors
```bash
codegreen measure python script.py --sensors rapl nvidia
```

### Low Overhead Monitoring
```bash
codegreen measure python script.py --precision low
```

### Keep Instrumented File for Inspection
```bash
codegreen measure python script.py --no-cleanup
```

## Analyzing Results

After measurement, analyze the JSON output:

```python
# analyze_results.py
import json
import sys

def analyze_energy_report(filename):
    with open(filename) as f:
        data = json.load(f)

    print(f"Total Energy: {data['total_energy_joules']:.6f} J")
    print(f"Execution Time: {data['execution_time_ms']:.2f} ms")
    print(f"Average Power: {data['average_power_watts']:.3f} W")

    print("\nFunction Breakdown:")
    functions = data.get('functions', {})
    sorted_funcs = sorted(functions.items(),
                         key=lambda x: x[1].get('energy_joules', 0),
                         reverse=True)

    for func_name, metrics in sorted_funcs:
        energy = metrics.get('energy_joules', 0)
        invocations = metrics.get('invocations', 0)
        print(f"  {func_name}: {energy:.6f} J ({invocations} calls)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_results.py <results.json>")
        sys.exit(1)

    analyze_energy_report(sys.argv[1])
```

**Run:**
```bash
python analyze_results.py results.json
```

## See Also

- [CLI Reference](../user-guide/cli-reference.md) - Complete command options
- [Configuration](../getting-started/configuration.md) - Python-specific settings
- [C/C++ Examples](cpp.md) - C/C++ energy profiling
- [Java Examples](java.md) - Java energy profiling
