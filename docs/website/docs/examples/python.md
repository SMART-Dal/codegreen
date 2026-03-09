# Python Examples

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
# Coarse mode: total program energy
codegreen measure python hello_energy.py

# Fine mode: per-function breakdown
codegreen measure python hello_energy.py -g fine

# With visualization
codegreen measure python hello_energy.py -g fine --export-plot energy.html
```

## Algorithm Comparison

Compare energy consumption of different sorting implementations:

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

def main():
    data = generate_data(5000)
    bubble_result = bubble_sort(data)
    print(f"Bubble sort first: {bubble_result[0]}")
    quick_result = quick_sort(data)
    print(f"Quick sort first: {quick_result[0]}")

if __name__ == "__main__":
    main()
```

**Measure with per-function breakdown:**
```bash
codegreen measure python sorting_comparison.py -g fine --export-plot sorting.html
```

The energy timeline will show `bubble_sort` consuming significantly more energy than `quick_sort` due to O(n^2) vs O(n log n) complexity.

## Optimization Before/After

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
    parts = []
    for i in range(n):
        parts.append(f"item{i},")
    return "".join(parts)

def main():
    result = concatenate_fast(50000)
    print(f"Length: {len(result)}")

if __name__ == "__main__":
    main()
```

**Compare:**
```bash
codegreen measure python string_concat_slow.py -o slow.json
codegreen measure python string_concat_fast.py -o fast.json
```

The join-based version typically uses 70-85% less energy.

## Matrix Operations

CPU-intensive computation:

```python
# matrix_multiply.py
def create_matrix(rows, cols, value):
    return [[value] * cols for _ in range(rows)]

def matrix_multiply(a, b):
    rows_a, cols_a = len(a), len(a[0])
    cols_b = len(b[0])
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

```bash
codegreen measure python matrix_multiply.py -g fine --export-plot matrix.html
```

## Recursive vs Iterative

```python
# fibonacci.py
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

def main():
    n = 30
    print(f"Recursive: {fibonacci_recursive(n)}")
    print(f"Iterative: {fibonacci_iterative(n)}")

if __name__ == "__main__":
    main()
```

```bash
codegreen measure python fibonacci.py -g fine --export-plot fib.html
```

The recursive version consumes orders of magnitude more energy due to exponential function calls.

## Common CLI Patterns

```bash
# Quick energy measurement of any command (no instrumentation)
codegreen run python script.py --repeat 10

# Energy budget enforcement (exits non-zero if exceeded)
codegreen run --budget 5.0 python script.py

# Basic measurement (coarse, 2 checkpoints)
codegreen measure python script.py

# Fine granularity (all functions)
codegreen measure python script.py -g fine

# JSON output to stdout
codegreen measure python script.py --json

# Save results to file
codegreen measure python script.py -o results.json

# Interactive HTML plot
codegreen measure python script.py -g fine --export-plot energy.html

# Static PNG plot (requires matplotlib)
codegreen measure python script.py -g fine --export-plot energy.png

# Keep instrumented code for inspection
codegreen measure python script.py --no-cleanup

# Pass arguments to the script
codegreen measure python script.py -- arg1 arg2

# Analyze without running (static analysis only)
codegreen analyze python script.py --verbose
```

## Best Practices

1. **Use fine mode for profiling**: `-g fine` shows per-function energy breakdown
2. **Use coarse mode for totals**: Default mode gives total energy with minimal overhead
3. **Consistent data**: Use same seeds for random data when comparing
4. **Multiple runs**: Average 3-5 runs for stable results
5. **Avoid I/O during profiling**: File I/O adds measurement noise
6. **Return results**: Use function return values to prevent dead code elimination

## See Also

- [CLI Reference](../user-guide/cli-reference.md)
- [Reports & Visualization](../user-guide/reports.md)
- [C/C++ Examples](cpp.md)
- [Java Examples](java.md)
