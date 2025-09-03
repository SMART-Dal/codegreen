# Python Examples

Practical examples of using CodeGreen with Python.

## Basic Energy Measurement

```python
import codegreen
from codegreen.core import engine

# Create measurement engine
engine = engine.MeasurementEngine()

# Measure a simple function
@engine.measure
def simple_calculation():
    result = sum(i**2 for i in range(1000))
    return result

# Run and get results
result = simple_calculation()
measurement = engine.get_last_measurement()

print(f"Result: {result}")
print(f"Energy: {measurement.total_joules:.6f} J")
print(f"Power: {measurement.average_watts:.3f} W")
```

## Comparing Algorithms

```python
import codegreen
from codegreen.core import engine

engine = engine.MeasurementEngine()

# Compare sorting algorithms
@engine.measure
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

@engine.measure  
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

# Test with same data
import random
data = [random.randint(1, 1000) for _ in range(1000)]

# Measure bubble sort
bubble_result = bubble_sort(data.copy())
bubble_energy = engine.get_last_measurement()

# Measure quick sort  
quick_result = quick_sort(data.copy())
quick_energy = engine.get_last_measurement()

print(f"Bubble sort energy: {bubble_energy.total_joules:.6f} J")
print(f"Quick sort energy: {quick_energy.total_joules:.6f} J")
print(f"Energy difference: {bubble_energy.total_joules - quick_energy.total_joules:.6f} J")
```

## Batch Processing

```python
import codegreen
from codegreen.core import engine

engine = engine.MeasurementEngine()

# Process multiple files
files = ["file1.txt", "file2.txt", "file3.txt"]
results = []

for filename in files:
    @engine.measure
    def process_file(fname):
        # Simulate file processing
        with open(fname, 'r') as f:
            content = f.read()
        return len(content.split())
    
    word_count = process_file(filename)
    measurement = engine.get_last_measurement()
    
    results.append({
        'file': filename,
        'words': word_count,
        'energy': measurement.total_joules
    })

# Analyze results
total_energy = sum(r['energy'] for r in results)
print(f"Total energy for batch: {total_energy:.6f} J")

for result in results:
    print(f"{result['file']}: {result['words']} words, {result['energy']:.6f} J")
```
