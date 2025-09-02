#!/usr/bin/env python3
"""
Comprehensive Python Sample for CodeGreen Testing
Tests various language constructs and checkpoint generation
"""

import time
import math
from typing import List, Dict, Optional

class DataProcessor:
    """Sample class to test class-based checkpoint generation"""
    
    def __init__(self, data: List[float]):
        self.data = data
        self.processed_count = 0
    
    def process_data(self) -> List[float]:
        """Process data with various operations"""
        results = []
        
        # Test loop checkpoint
        for i, value in enumerate(self.data):
            if value > 0:
                # Test conditional checkpoint
                processed = math.sqrt(value) * 2
                results.append(processed)
                self.processed_count += 1
        
        return results
    
    def get_statistics(self) -> Dict[str, float]:
        """Calculate statistics"""
        if not self.data:
            return {}
        
        return {
            'mean': sum(self.data) / len(self.data),
            'max': max(self.data),
            'min': min(self.data),
            'processed': self.processed_count
        }

def fibonacci_recursive(n: int) -> int:
    """Recursive Fibonacci to test function checkpoints"""
    if n <= 1:
        return n
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)

def fibonacci_iterative(n: int) -> int:
    """Iterative Fibonacci to test loop checkpoints"""
    if n <= 1:
        return n
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def main():
    """Main function to orchestrate the test"""
    print("🚀 CodeGreen Python Language Test")
    print("=" * 40)
    
    # Test data processing
    data = [1.0, 4.0, 9.0, 16.0, 25.0, -1.0, 36.0]
    processor = DataProcessor(data)
    
    print(f"Input data: {data}")
    
    # Process data
    start_time = time.time()
    results = processor.process_data()
    processing_time = time.time() - start_time
    
    print(f"Processed results: {results}")
    print(f"Processing time: {processing_time:.4f} seconds")
    
    # Get statistics
    stats = processor.get_statistics()
    print(f"Statistics: {stats}")
    
    # Test Fibonacci functions
    print("\n🧮 Testing Fibonacci functions:")
    for i in range(8):
        fib_rec = fibonacci_recursive(i)
        fib_iter = fibonacci_iterative(i)
        print(f"F({i}) = {fib_rec} (recursive), {fib_iter} (iterative)")
    
    # Test list comprehension
    squares = [x**2 for x in range(5)]
    print(f"\n📊 Squares: {squares}")
    
    # Test dictionary comprehension
    square_dict = {x: x**2 for x in range(5)}
    print(f"Square dictionary: {square_dict}")
    
    print("\n✅ Python language test completed successfully!")

if __name__ == "__main__":
    main()
