#!/usr/bin/env python3
"""
Sample Python program for CodeGreen energy measurement testing.
This program demonstrates various Python constructs that should generate
energy measurement checkpoints.
"""

import time
import math


def calculate_fibonacci(n):
    """Calculate nth Fibonacci number using recursive method."""
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)


def optimized_fibonacci(n):
    """Calculate nth Fibonacci number using iterative method."""
    if n <= 1:
        return n
    
    a, b = 0, 1
    for i in range(2, n + 1):
        a, b = b, a + b
    
    return b


class NumberProcessor:
    """A class for processing numbers with energy-intensive operations."""
    
    def __init__(self, numbers):
        self.numbers = numbers
        self.results = []
    
    def process_numbers(self):
        """Process numbers using various methods."""
        # List comprehension (should trigger optimization suggestion)
        squares = [x * x for x in self.numbers]
        
        # Loop with string concatenation (should trigger optimization suggestion)
        result_str = ""
        for num in squares:
            result_str += str(num) + " "
        
        # Nested loops for matrix operations
        matrix = [[i * j for j in range(10)] for i in range(10)]
        
        return matrix, result_str.strip()


def main():
    """Main function demonstrating various Python patterns."""
    print("CodeGreen Energy Measurement Demo")
    print("=================================")
    
    # Function calls
    print("Calculating Fibonacci numbers...")
    fib_recursive = calculate_fibonacci(10)
    fib_iterative = optimized_fibonacci(10)
    
    print(f"Fibonacci(10) - Recursive: {fib_recursive}")
    print(f"Fibonacci(10) - Iterative: {fib_iterative}")
    
    # Class instantiation and method calls
    numbers = list(range(1, 21))
    processor = NumberProcessor(numbers)
    matrix, result_str = processor.process_numbers()
    
    print(f"Processed {len(numbers)} numbers")
    print(f"Generated matrix: {len(matrix)}x{len(matrix[0])}")
    
    # Loop with range(len()) pattern (should trigger optimization suggestion)
    for i in range(len(numbers)):
        if numbers[i] % 5 == 0:
            print(f"Multiple of 5: {numbers[i]}")
    
    # With statement (context manager)
    with open("/dev/null", "w") as f:
        for num in numbers:
            f.write(str(num))
    
    # Async-like behavior simulation
    def simulate_async_work():
        for i in range(3):
            time.sleep(0.01)  # Small delay to simulate work
            yield i
    
    async_results = list(simulate_async_work())
    print(f"Async work completed: {async_results}")
    
    print("Demo complete!")


if __name__ == "__main__":
    main()