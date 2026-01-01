#!/usr/bin/env python3
"""
Sample test file for CodeGreen VSCode Extension
This file contains various energy-intensive operations to demonstrate
energy hotspot detection and visualization.
"""

import time
import random
import math

def fibonacci(n):
    """Recursive Fibonacci - CPU intensive, high energy consumption"""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def matrix_multiply(a, b):
    """Matrix multiplication - CPU and memory intensive"""
    rows_a = len(a)
    cols_a = len(a[0])
    cols_b = len(b[0])
    
    result = [[0 for _ in range(cols_b)] for _ in range(rows_a)]
    
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    
    return result

def cpu_intensive_loop():
    """CPU-intensive loop with mathematical operations"""
    total = 0
    for i in range(1000000):
        total += math.sqrt(i) * math.sin(i) * math.cos(i)
    return total

def memory_intensive_operation():
    """Memory-intensive operation with large data structures"""
    large_list = []
    for i in range(100000):
        large_list.append([random.random() for _ in range(100)])
    
    # Process the large list
    processed = []
    for sublist in large_list:
        processed.append(sum(sublist))
    
    return processed

def io_simulation():
    """Simulates I/O operations"""
    data = []
    for i in range(1000):
        data.append(f"Line {i}: {random.randint(0, 1000)}")
    return "\n".join(data)

def nested_loops():
    """Nested loops - moderate energy consumption"""
    result = 0
    for i in range(1000):
        for j in range(1000):
            result += i * j
    return result

def main():
    """Main function that orchestrates all operations"""
    print("Starting CodeGreen energy analysis test...")
    
    # Test 1: Fibonacci (high energy)
    print("\n1. Testing Fibonacci (recursive)...")
    fib_result = fibonacci(30)
    print(f"   Fibonacci(30) = {fib_result}")
    
    # Test 2: Matrix multiplication (high energy)
    print("\n2. Testing Matrix Multiplication...")
    matrix_a = [[random.random() for _ in range(50)] for _ in range(50)]
    matrix_b = [[random.random() for _ in range(50)] for _ in range(50)]
    matrix_result = matrix_multiply(matrix_a, matrix_b)
    print(f"   Matrix result shape: {len(matrix_result)}x{len(matrix_result[0])}")
    
    # Test 3: CPU-intensive loop (high energy)
    print("\n3. Testing CPU-intensive loop...")
    cpu_result = cpu_intensive_loop()
    print(f"   CPU loop result: {cpu_result:.2f}")
    
    # Test 4: Memory-intensive operation (medium energy)
    print("\n4. Testing Memory-intensive operation...")
    mem_result = memory_intensive_operation()
    print(f"   Memory operation result count: {len(mem_result)}")
    
    # Test 5: I/O simulation (low energy)
    print("\n5. Testing I/O simulation...")
    io_result = io_simulation()
    print(f"   I/O result length: {len(io_result)} characters")
    
    # Test 6: Nested loops (medium energy)
    print("\n6. Testing Nested loops...")
    nested_result = nested_loops()
    print(f"   Nested loops result: {nested_result}")
    
    print("\n✅ All tests completed!")
    return {
        'fibonacci': fib_result,
        'matrix': matrix_result,
        'cpu': cpu_result,
        'memory': mem_result,
        'io': io_result,
        'nested': nested_result
    }

if __name__ == "__main__":
    results = main()
    print(f"\n📊 Final results summary:")
    print(f"   - Fibonacci: {results['fibonacci']}")
    print(f"   - Matrix: {len(results['matrix'])}x{len(results['matrix'][0])}")
    print(f"   - CPU: {results['cpu']:.2f}")
    print(f"   - Memory: {len(results['memory'])} items")
    print(f"   - I/O: {len(results['io'])} chars")
    print(f"   - Nested: {results['nested']}")
