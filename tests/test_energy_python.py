#!/usr/bin/env python3
"""
Test script for CodeGreen energy measurement
This script performs various computational tasks to test fine-grained energy monitoring
"""

import time
import math
import random

def fibonacci(n):
    """Calculate Fibonacci number - CPU intensive"""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def matrix_multiply(A, B):
    """Matrix multiplication - memory and CPU intensive"""
    rows_A = len(A)
    cols_A = len(A[0])
    cols_B = len(B[0])
    
    result = [[0 for _ in range(cols_B)] for _ in range(rows_A)]
    
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                result[i][j] += A[i][k] * B[k][j]
    
    return result

def prime_sieve(n):
    """Sieve of Eratosthenes - CPU intensive"""
    primes = [True] * (n + 1)
    primes[0] = primes[1] = False
    
    for i in range(2, int(math.sqrt(n)) + 1):
        if primes[i]:
            for j in range(i * i, n + 1, i):
                primes[j] = False
    
    return [i for i in range(2, n + 1) if primes[i]]

def memory_intensive_task():
    """Memory allocation and processing"""
    data = []
    for i in range(10000):
        data.append([random.random() for _ in range(100)])
    
    # Process the data
    total = 0
    for row in data:
        for val in row:
            total += val
    
    return total

def main():
    print("🚀 Starting CodeGreen energy measurement test")
    
    # Test 1: Fibonacci calculation
    print("\n📊 Test 1: Fibonacci calculation")
    start_time = time.time()
    fib_result = fibonacci(30)
    end_time = time.time()
    print(f"Fibonacci(30) = {fib_result}")
    print(f"Time taken: {end_time - start_time:.4f} seconds")
    
    # Test 2: Matrix multiplication
    print("\n📊 Test 2: Matrix multiplication")
    A = [[random.random() for _ in range(50)] for _ in range(50)]
    B = [[random.random() for _ in range(50)] for _ in range(50)]
    
    start_time = time.time()
    matrix_result = matrix_multiply(A, B)
    end_time = time.time()
    print(f"Matrix multiplication completed: {len(matrix_result)}x{len(matrix_result[0])}")
    print(f"Time taken: {end_time - start_time:.4f} seconds")
    
    # Test 3: Prime sieve
    print("\n📊 Test 3: Prime sieve")
    start_time = time.time()
    primes = prime_sieve(10000)
    end_time = time.time()
    print(f"Found {len(primes)} primes up to 10000")
    print(f"Time taken: {end_time - start_time:.4f} seconds")
    
    # Test 4: Memory intensive task
    print("\n📊 Test 4: Memory intensive task")
    start_time = time.time()
    memory_result = memory_intensive_task()
    end_time = time.time()
    print(f"Memory task result: {memory_result}")
    print(f"Time taken: {end_time - start_time:.4f} seconds")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main()
