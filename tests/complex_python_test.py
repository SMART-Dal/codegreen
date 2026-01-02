#!/usr/bin/env python3
"""
Complex Python Test for CodeGreen Instrumentation
Tests challenging constructs: nested functions, closures, decorators, 
context managers, async/await, generators, comprehensions, exception handling
"""

import asyncio
import contextlib
import functools
import itertools
import time
from typing import AsyncGenerator, Iterator, List, Dict, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


@dataclass
class DataPoint:
    """Complex data structure for testing"""
    value: float
    timestamp: float
    metadata: Dict[str, any]
    
    def __post_init__(self):
        if self.timestamp <= 0:
            self.timestamp = time.time()


class ComplexProcessor:
    """Complex class with various method types and nested constructs"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.results = []
        self._cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    @property
    def cache_size(self) -> int:
        return len(self._cache)
    
    @functools.lru_cache(maxsize=128)
    def fibonacci(self, n: int) -> int:
        """Cached recursive function"""
        if n <= 1:
            return n
        return self.fibonacci(n - 1) + self.fibonacci(n - 2)
    
    @staticmethod
    def static_computation(data: List[float]) -> float:
        """Static method with complex nested loops"""
        total = 0.0
        for i in range(len(data)):
            for j in range(i + 1, len(data)):
                for k in range(j + 1, len(data)):
                    # Triple nested loop - challenging for instrumentation
                    if data[i] + data[j] + data[k] > 0:
                        total += data[i] * data[j] * data[k]
                    elif data[i] < 0:
                        # Nested conditional inside triple loop
                        while abs(data[i]) > 1:
                            data[i] /= 2
                            if data[i] < 0.1:
                                break
        return total
    
    @classmethod
    def create_from_config(cls, config_path: str):
        """Class method with file I/O and exception handling"""
        config = {}
        try:
            with open(config_path, 'r') as f:
                # Context manager inside try block
                for line_num, line in enumerate(f):
                    if line.strip():
                        try:
                            key, value = line.split('=')
                            config[key.strip()] = value.strip()
                        except ValueError:
                            print(f"Invalid line {line_num}: {line}")
                            continue
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            config = {"default": "true"}
        except Exception as e:
            print(f"Unexpected error reading config: {e}")
            raise
        finally:
            print("Config loading completed")
        
        return cls("ConfigBased", config)
    
    def generator_method(self, data: List[int]) -> Iterator[int]:
        """Generator with complex control flow"""
        seen = set()
        for item in data:
            if item in seen:
                continue
            
            # Nested generator expression
            transformed = sum(x * 2 for x in range(item) if x % 2 == 0)
            
            if transformed > 100:
                # Early termination with cleanup
                print("Large value detected, terminating generator")
                return
            
            seen.add(item)
            yield transformed
            
            # Generator with side effects
            if len(seen) > 10:
                seen.clear()
                yield -1  # Sentinel value
    
    async def async_processor(self, items: List[DataPoint]) -> AsyncGenerator[float, None]:
        """Async generator with concurrent processing"""
        semaphore = asyncio.Semaphore(3)
        
        async def process_item(item: DataPoint) -> float:
            async with semaphore:
                # Simulated async work with nested awaits
                await asyncio.sleep(0.01)
                
                result = item.value
                for _ in range(3):
                    # Nested async loop
                    result = await self._complex_async_calculation(result)
                    if result > 1000:
                        break
                
                return result
        
        # Concurrent processing with exception handling
        tasks = []
        for item in items:
            if item.value > 0:
                task = asyncio.create_task(process_item(item))
                tasks.append(task)
        
        # Process results as they complete
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                yield result
            except Exception as e:
                print(f"Processing error: {e}")
                yield -1.0
    
    async def _complex_async_calculation(self, value: float) -> float:
        """Private async method with complex logic"""
        if value < 0:
            raise ValueError("Negative values not supported")
        
        # Async comprehension
        squares = [x**2 async for x in self._async_range(int(value % 10))]
        
        return sum(squares) + value * 1.1
    
    async def _async_range(self, n: int) -> AsyncGenerator[int, None]:
        """Helper async generator"""
        for i in range(n):
            await asyncio.sleep(0.001)
            yield i
    
    @contextlib.contextmanager
    def timing_context(self, operation_name: str):
        """Context manager for timing operations"""
        start_time = time.time()
        try:
            print(f"Starting {operation_name}")
            yield self
        except Exception as e:
            print(f"Error in {operation_name}: {e}")
            raise
        finally:
            duration = time.time() - start_time
            print(f"Completed {operation_name} in {duration:.3f}s")
    
    def decorator_test(self):
        """Method that uses decorators heavily"""
        
        @functools.wraps(self.fibonacci)
        def cached_fib_wrapper(n):
            # Nested function with closure
            cache_key = f"fib_{n}"
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            result = self.fibonacci(n)
            self._cache[cache_key] = result
            return result
        
        # Multiple decorators and nested calls
        @functools.lru_cache(maxsize=64)
        def complex_calculation(x, y):
            if x == 0 or y == 0:
                return 0
            
            # Recursive with multiple branches
            if x > y:
                return complex_calculation(x - 1, y) + complex_calculation(x, y - 1)
            else:
                return x * y + complex_calculation(x - 1, y - 1)
        
        results = []
        for i in range(10):
            for j in range(5):
                # Nested loops calling nested functions
                fib_val = cached_fib_wrapper(i + j)
                calc_val = complex_calculation(i, j)
                results.append((fib_val, calc_val))
        
        return results
    
    def comprehension_heavy_method(self, data: List[int]) -> Dict[str, List]:
        """Method with various comprehension types"""
        # List comprehension with conditional
        squares = [x**2 for x in data if x > 0]
        
        # Dictionary comprehension with nested logic
        categorized = {
            f"bucket_{i}": [
                x for x in data 
                if i * 10 <= x < (i + 1) * 10
            ]
            for i in range(10)
            if any(i * 10 <= x < (i + 1) * 10 for x in data)
        }
        
        # Set comprehension with function calls
        processed_set = {
            self.fibonacci(x % 10) 
            for x in data 
            if x > 0 and x % 2 == 0
        }
        
        # Generator expression in function call
        sum_of_squares = sum(
            x**2 for x in data 
            if x > 0 
            for _ in range(2)  # Nested generator
        )
        
        return {
            "squares": squares,
            "categorized": categorized,
            "processed_set": list(processed_set),
            "sum_of_squares": sum_of_squares
        }
    
    def exception_heavy_method(self, risky_data: List[any]) -> List:
        """Method with complex exception handling patterns"""
        results = []
        
        for i, item in enumerate(risky_data):
            try:
                # Multiple nested try blocks
                try:
                    if isinstance(item, str):
                        converted = float(item)
                    elif isinstance(item, (int, float)):
                        converted = float(item)
                    else:
                        raise TypeError(f"Cannot convert {type(item)} to float")
                    
                    # Division with potential zero division
                    try:
                        normalized = converted / (i + 1)
                        if normalized > 100:
                            raise ValueError("Value too large")
                        results.append(normalized)
                    except ZeroDivisionError:
                        results.append(0.0)
                
                except (ValueError, TypeError) as e:
                    print(f"Conversion error at index {i}: {e}")
                    # Retry with different approach
                    try:
                        fallback = hash(str(item)) % 100
                        results.append(float(fallback))
                    except Exception:
                        results.append(-1.0)
            
            except Exception as e:
                print(f"Unexpected error processing item {i}: {e}")
                results.append(None)
            
            finally:
                # Cleanup operations
                if len(results) > 1000:
                    print("Results list getting large, truncating")
                    results = results[-100:]
        
        # Filter out None values with exception handling
        try:
            cleaned_results = [x for x in results if x is not None]
        except Exception:
            cleaned_results = []
        
        return cleaned_results


def complex_standalone_function(data: List[DataPoint], processor: ComplexProcessor) -> Dict:
    """Standalone function with complex nested structures"""
    
    # Nested function definitions
    def inner_processor(points: List[DataPoint]) -> Iterator[float]:
        def validate_point(point: DataPoint) -> bool:
            return (
                point.value is not None and 
                isinstance(point.value, (int, float)) and
                point.timestamp > 0
            )
        
        for point in points:
            if validate_point(point):
                # Nested conditional with complex logic
                if point.value > 0:
                    yield point.value * 2
                elif point.value == 0:
                    yield 1.0
                else:
                    # Negative values get special processing
                    adjusted = abs(point.value)
                    while adjusted > 1:
                        adjusted /= 2
                        if adjusted < 0.1:
                            break
                    yield adjusted
    
    # Multiple nested loops with generators
    results = {
        "processed": list(inner_processor(data)),
        "statistics": {},
        "complex_metrics": {}
    }
    
    # Complex nested loop structure
    for category in ['low', 'medium', 'high']:
        category_data = []
        threshold = {'low': 10, 'medium': 100, 'high': 1000}[category]
        
        for point in data:
            if point.value <= threshold:
                for multiplier in [0.5, 1.0, 1.5, 2.0]:
                    transformed = point.value * multiplier
                    
                    # Nested while loop
                    iterations = 0
                    while transformed > 1 and iterations < 10:
                        transformed = transformed ** 0.9
                        iterations += 1
                        
                        # Break conditions inside nested loop
                        if transformed < 0.01:
                            break
                    
                    category_data.append(transformed)
        
        results["statistics"][category] = {
            "count": len(category_data),
            "sum": sum(category_data),
            "avg": sum(category_data) / len(category_data) if category_data else 0
        }
    
    return results


async def complex_async_main():
    """Complex async main function testing various patterns"""
    
    # Create test data
    test_data = [
        DataPoint(value=i * 1.5, timestamp=time.time(), metadata={"index": i})
        for i in range(-10, 20)
    ]
    
    processor = ComplexProcessor("AsyncTester", {"mode": "test", "verbose": "true"})
    
    # Test context manager
    with processor.timing_context("Full Processing"):
        try:
            # Test decorator method
            decorator_results = processor.decorator_test()
            print(f"Decorator test completed: {len(decorator_results)} results")
            
            # Test comprehensions
            comprehension_data = list(range(-5, 15))
            comprehension_results = processor.comprehension_heavy_method(comprehension_data)
            print(f"Comprehension test completed")
            
            # Test async processing
            async_results = []
            async for result in processor.async_processor(test_data):
                async_results.append(result)
                if len(async_results) >= 10:  # Limit results for testing
                    break
            
            print(f"Async processing completed: {len(async_results)} results")
            
            # Test exception handling
            risky_data = [1, "2.5", None, "invalid", 0, -5.5, [], {"key": "value"}]
            exception_results = processor.exception_heavy_method(risky_data)
            print(f"Exception handling test completed: {len(exception_results)} results")
            
            # Test standalone complex function
            complex_results = complex_standalone_function(test_data, processor)
            print(f"Complex function test completed")
            
            # Final nested loop with async operations
            batch_size = 3
            for batch_start in range(0, len(test_data), batch_size):
                batch = test_data[batch_start:batch_start + batch_size]
                
                # Process batch concurrently
                batch_tasks = []
                for item in batch:
                    if item.value > 0:
                        # Create coroutine for each positive value
                        task = processor._complex_async_calculation(item.value)
                        batch_tasks.append(task)
                
                if batch_tasks:
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    valid_results = [r for r in batch_results if not isinstance(r, Exception)]
                    print(f"Batch {batch_start // batch_size + 1}: {len(valid_results)} valid results")
        
        except Exception as e:
            print(f"Error in main processing: {e}")
            raise
        
        finally:
            # Cleanup
            processor.executor.shutdown(wait=True)
            print("Cleanup completed")


def fibonacci_itertools_approach(n: int) -> int:
    """Fibonacci using itertools - tests iterator protocols"""
    def fib_generator():
        a, b = 0, 1
        while True:
            yield a
            a, b = b, a + b
    
    return next(itertools.islice(fib_generator(), n, n + 1))


# Module-level complex constructs
if __name__ == "__main__":
    print("🧪 Starting Complex Python CodeGreen Test")
    print("=" * 50)
    
    # Synchronous tests first
    processor = ComplexProcessor("MainTester", {"debug": True})
    
    # Test static method
    static_test_data = [1.0, -2.0, 3.0, -4.0, 5.0]
    static_result = ComplexProcessor.static_computation(static_test_data)
    print(f"Static method result: {static_result}")
    
    # Test generator
    generator_test_data = list(range(1, 15))
    gen_results = list(processor.generator_method(generator_test_data))
    print(f"Generator results: {len(gen_results)} items")
    
    # Test itertools approach
    for i in range(10):
        fib_val = fibonacci_itertools_approach(i)
        print(f"F({i}) = {fib_val}")
    
    # Run async tests
    try:
        asyncio.run(complex_async_main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        raise
    
    print("\n✅ Complex Python test completed!")