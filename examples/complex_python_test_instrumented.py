#!/usr/bin/env python3
"""
Complex Python Test for CodeGreen Instrumentation
Tests challenging constructs: nested functions, closures, decorators, 
context managers, async/await, generators, comprehensions, exception handling
"""

import codegreen_runtime as _codegreen_rt
import asyncio
import contextlib
import functools
import itertools
import time
from typing import AsyncGenerator, Iterator, List, Dict, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


@dataclass
_codegreen_rt.measure_checkpoint('class_enter_DataPoint_20', 'class_enter', 'DataPoint', 20, 'Class definition: DataPoint')
class DataPoint:
    """Complex data structure for testing"""
    value: float
    timestamp: float
    metadata: Dict[str, any]
    
    def __post_init__(self):
        if self.timestamp <= 0:
            _codegreen_rt.measure_checkpoint('function_enter___post_init___27', 'function_enter', '__post_init__', 27, 'Function entry: __post_init__')
            self.timestamp = time.time()
_codegreen_rt.measure_checkpoint('function_exit___post_init___28', 'function_exit', '__post_init__', 28, 'Function exit: __post_init__')


_codegreen_rt.measure_checkpoint('class_enter_ComplexProcessor_31', 'class_enter', 'ComplexProcessor', 31, 'Class definition: ComplexProcessor')
class ComplexProcessor:
    """Complex class with various method types and nested constructs"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        _codegreen_rt.measure_checkpoint('function_enter___init___35', 'function_enter', '__init__', 35, 'Function entry: __init__')
        self.config = config
        self.results = []
        self._cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
    _codegreen_rt.measure_checkpoint('function_exit___init___39', 'function_exit', '__init__', 39, 'Function exit: __init__')
    
    @property
    def cache_size(self) -> int:
        _codegreen_rt.measure_checkpoint('function_exit_cache_size_43', 'function_exit', 'cache_size', 43, 'Function exit: cache_size')
        return len(self._cache)
    _codegreen_rt.measure_checkpoint('function_enter_cache_size_43', 'function_enter', 'cache_size', 43, 'Function entry: cache_size')
    
    @functools.lru_cache(maxsize=128)
    def fibonacci(self, n: int) -> int:
        """Cached recursive function"""
        _codegreen_rt.measure_checkpoint('function_enter_fibonacci_47', 'function_enter', 'fibonacci', 47, 'Function entry: fibonacci')
        if n <= 1:
            return n
        _codegreen_rt.measure_checkpoint('function_exit_fibonacci_50', 'function_exit', 'fibonacci', 50, 'Function exit: fibonacci')
        return self.fibonacci(n - 1) + self.fibonacci(n - 2)
    
    @staticmethod
    def static_computation(data: List[float]) -> float:
        """Static method with complex nested loops"""
        _codegreen_rt.measure_checkpoint('function_enter_static_computation_54', 'function_enter', 'static_computation', 54, 'Function entry: static_computation')
        total = 0.0
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_56', 'loop_start', 'for_loop', 56, 'For loop')
        for i in range(len(data)):
            for j in range(i + 1, len(data)):
                _codegreen_rt.measure_checkpoint('loop_start_for_loop_58', 'loop_start', 'for_loop', 58, 'For loop')
                for k in range(j + 1, len(data)):
                    # Triple nested loop - challenging for instrumentation
                    if data[i] + data[j] + data[k] > 0:
                        total += data[i] * data[j] * data[k]
                    elif data[i] < 0:
                        # Nested conditional inside triple loop
                        _codegreen_rt.measure_checkpoint('loop_start_while_loop_64', 'loop_start', 'while_loop', 64, 'While loop')
                        while abs(data[i]) > 1:
                            data[i] /= 2
                            if data[i] < 0.1:
                                break
        _codegreen_rt.measure_checkpoint('loop_exit_while_loop_67', 'loop_exit', 'while_loop', 67, 'Loop exit: while_loop')
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_67', 'loop_exit', 'for_loop', 67, 'Loop exit: for_loop')
        _codegreen_rt.measure_checkpoint('function_exit_static_computation_68', 'function_exit', 'static_computation', 68, 'Function exit: static_computation')
        return total
    
    @classmethod
    def create_from_config(cls, config_path: str):
        """Class method with file I/O and exception handling"""
        _codegreen_rt.measure_checkpoint('function_enter_create_from_config_72', 'function_enter', 'create_from_config', 72, 'Function entry: create_from_config')
        config = {}
        try:
            with open(config_path, 'r') as f:
                # Context manager inside try block
                _codegreen_rt.measure_checkpoint('loop_start_for_loop_77', 'loop_start', 'for_loop', 77, 'For loop')
                for line_num, line in enumerate(f):
                    if line.strip():
                        try:
                            key, value = line.split('=')
                            config[key.strip()] = value.strip()
                        except ValueError:
                            print(f"Invalid line {line_num}: {line}")
                            continue
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_84', 'loop_exit', 'for_loop', 84, 'Loop exit: for_loop')
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            config = {"default": "true"}
        except Exception as e:
            print(f"Unexpected error reading config: {e}")
            raise
        finally:
            print("Config loading completed")
        
        _codegreen_rt.measure_checkpoint('function_exit_create_from_config_94', 'function_exit', 'create_from_config', 94, 'Function exit: create_from_config')
        return cls("ConfigBased", config)
    
    def generator_method(self, data: List[int]) -> Iterator[int]:
        """Generator with complex control flow"""
        _codegreen_rt.measure_checkpoint('function_enter_generator_method_97', 'function_enter', 'generator_method', 97, 'Function entry: generator_method')
        seen = set()
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_99', 'loop_start', 'for_loop', 99, 'For loop')
        for item in data:
            if item in seen:
                continue
            
            # Nested generator expression
            _codegreen_rt.measure_checkpoint('comprehension_generator_comp_104', 'comprehension', 'generator_comp', 104, 'Generator comprehension')
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
    _codegreen_rt.measure_checkpoint('loop_exit_for_loop_117', 'loop_exit', 'for_loop', 117, 'Loop exit: for_loop')
    _codegreen_rt.measure_checkpoint('function_exit_generator_method_117', 'function_exit', 'generator_method', 117, 'Function exit: generator_method')
    
    async def async_processor(self, items: List[DataPoint]) -> AsyncGenerator[float, None]:
        """Async generator with concurrent processing"""
        _codegreen_rt.measure_checkpoint('function_enter_async_processor_120', 'function_enter', 'async_processor', 120, 'Function entry: async_processor')
        semaphore = asyncio.Semaphore(3)
        
        async def process_item(item: DataPoint) -> float:
            async with semaphore:
                _codegreen_rt.measure_checkpoint('function_enter_process_item_124', 'function_enter', 'process_item', 124, 'Function entry: process_item')
                # Simulated async work with nested awaits
                await asyncio.sleep(0.01)
                
                result = item.value
                _codegreen_rt.measure_checkpoint('loop_start_for_loop_129', 'loop_start', 'for_loop', 129, 'For loop')
                for _ in range(3):
                    # Nested async loop
                    result = await self._complex_async_calculation(result)
                    if result > 1000:
                        break
                _codegreen_rt.measure_checkpoint('loop_exit_for_loop_133', 'loop_exit', 'for_loop', 133, 'Loop exit: for_loop')
                
                _codegreen_rt.measure_checkpoint('function_exit_process_item_135', 'function_exit', 'process_item', 135, 'Function exit: process_item')
                return result
        
        # Concurrent processing with exception handling
        tasks = []
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_139', 'loop_start', 'for_loop', 139, 'For loop')
        for item in items:
            if item.value > 0:
                task = asyncio.create_task(process_item(item))
                tasks.append(task)
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_142', 'loop_exit', 'for_loop', 142, 'Loop exit: for_loop')
        
        # Process results as they complete
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_145', 'loop_start', 'for_loop', 145, 'For loop')
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                yield result
            except Exception as e:
                print(f"Processing error: {e}")
                yield -1.0
    _codegreen_rt.measure_checkpoint('loop_exit_for_loop_151', 'loop_exit', 'for_loop', 151, 'Loop exit: for_loop')
    _codegreen_rt.measure_checkpoint('function_exit_async_processor_151', 'function_exit', 'async_processor', 151, 'Function exit: async_processor')
    
    async def _complex_async_calculation(self, value: float) -> float:
        """Private async method with complex logic"""
        _codegreen_rt.measure_checkpoint('function_enter__complex_async_calculation_154', 'function_enter', '_complex_async_calculation', 154, 'Function entry: _complex_async_calculation')
        if value < 0:
            raise ValueError("Negative values not supported")
        
        # Async comprehension
        _codegreen_rt.measure_checkpoint('comprehension_list_comp_159', 'comprehension', 'list_comp', 159, 'List comprehension')
        squares = [x**2 async for x in self._async_range(int(value % 10))]
        
        _codegreen_rt.measure_checkpoint('function_exit__complex_async_calculation_161', 'function_exit', '_complex_async_calculation', 161, 'Function exit: _complex_async_calculation')
        return sum(squares) + value * 1.1
    
    async def _async_range(self, n: int) -> AsyncGenerator[int, None]:
        """Helper async generator"""
        _codegreen_rt.measure_checkpoint('function_enter__async_range_164', 'function_enter', '_async_range', 164, 'Function entry: _async_range')
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_165', 'loop_start', 'for_loop', 165, 'For loop')
        for i in range(n):
            await asyncio.sleep(0.001)
            yield i
    _codegreen_rt.measure_checkpoint('loop_exit_for_loop_167', 'loop_exit', 'for_loop', 167, 'Loop exit: for_loop')
    _codegreen_rt.measure_checkpoint('function_exit__async_range_167', 'function_exit', '_async_range', 167, 'Function exit: _async_range')
    
    @contextlib.contextmanager
    def timing_context(self, operation_name: str):
        """Context manager for timing operations"""
        _codegreen_rt.measure_checkpoint('function_enter_timing_context_171', 'function_enter', 'timing_context', 171, 'Function entry: timing_context')
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
    _codegreen_rt.measure_checkpoint('function_exit_timing_context_181', 'function_exit', 'timing_context', 181, 'Function exit: timing_context')
    
    def decorator_test(self):
        """Method that uses decorators heavily"""
        _codegreen_rt.measure_checkpoint('function_enter_decorator_test_184', 'function_enter', 'decorator_test', 184, 'Function entry: decorator_test')
        
        @functools.wraps(self.fibonacci)
        def cached_fib_wrapper(n):
            # Nested function with closure
            cache_key = f"fib_{n}"
            _codegreen_rt.measure_checkpoint('function_enter_cached_fib_wrapper_189', 'function_enter', 'cached_fib_wrapper', 189, 'Function entry: cached_fib_wrapper')
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            result = self.fibonacci(n)
            self._cache[cache_key] = result
            _codegreen_rt.measure_checkpoint('function_exit_cached_fib_wrapper_195', 'function_exit', 'cached_fib_wrapper', 195, 'Function exit: cached_fib_wrapper')
            return result
        
        # Multiple decorators and nested calls
        @functools.lru_cache(maxsize=64)
        def complex_calculation(x, y):
            if x == 0 or y == 0:
                _codegreen_rt.measure_checkpoint('function_enter_complex_calculation_200', 'function_enter', 'complex_calculation', 200, 'Function entry: complex_calculation')
                return 0
            
            # Recursive with multiple branches
            if x > y:
                return complex_calculation(x - 1, y) + complex_calculation(x, y - 1)
            else:
                _codegreen_rt.measure_checkpoint('function_exit_complex_calculation_207', 'function_exit', 'complex_calculation', 207, 'Function exit: complex_calculation')
                return x * y + complex_calculation(x - 1, y - 1)
        
        results = []
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_210', 'loop_start', 'for_loop', 210, 'For loop')
        for i in range(10):
            for j in range(5):
                # Nested loops calling nested functions
                fib_val = cached_fib_wrapper(i + j)
                calc_val = complex_calculation(i, j)
                results.append((fib_val, calc_val))
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_215', 'loop_exit', 'for_loop', 215, 'Loop exit: for_loop')
        
        _codegreen_rt.measure_checkpoint('function_exit_decorator_test_217', 'function_exit', 'decorator_test', 217, 'Function exit: decorator_test')
        return results
    
    def comprehension_heavy_method(self, data: List[int]) -> Dict[str, List]:
        """Method with various comprehension types"""
        _codegreen_rt.measure_checkpoint('function_enter_comprehension_heavy_method_220', 'function_enter', 'comprehension_heavy_method', 220, 'Function entry: comprehension_heavy_method')
        # List comprehension with conditional
        _codegreen_rt.measure_checkpoint('comprehension_list_comp_222', 'comprehension', 'list_comp', 222, 'List comprehension')
        squares = [x**2 for x in data if x > 0]
        
        # Dictionary comprehension with nested logic
        _codegreen_rt.measure_checkpoint('comprehension_dict_comp_225', 'comprehension', 'dict_comp', 225, 'Dict comprehension')
        categorized = {
            _codegreen_rt.measure_checkpoint('comprehension_list_comp_226', 'comprehension', 'list_comp', 226, 'List comprehension')
            f"bucket_{i}": [
                x for x in data 
                if i * 10 <= x < (i + 1) * 10
            ]
            for i in range(10)
            _codegreen_rt.measure_checkpoint('comprehension_generator_comp_231', 'comprehension', 'generator_comp', 231, 'Generator comprehension')
            if any(i * 10 <= x < (i + 1) * 10 for x in data)
        }
        
        # Set comprehension with function calls
        _codegreen_rt.measure_checkpoint('comprehension_set_comp_235', 'comprehension', 'set_comp', 235, 'Set comprehension')
        processed_set = {
            self.fibonacci(x % 10) 
            for x in data 
            if x > 0 and x % 2 == 0
        }
        
        # Generator expression in function call
        _codegreen_rt.measure_checkpoint('comprehension_generator_comp_242', 'comprehension', 'generator_comp', 242, 'Generator comprehension')
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
    _codegreen_rt.measure_checkpoint('function_exit_comprehension_heavy_method_253', 'function_exit', 'comprehension_heavy_method', 253, 'Function exit: comprehension_heavy_method')
    
    def exception_heavy_method(self, risky_data: List[any]) -> List:
        """Method with complex exception handling patterns"""
        _codegreen_rt.measure_checkpoint('function_enter_exception_heavy_method_256', 'function_enter', 'exception_heavy_method', 256, 'Function entry: exception_heavy_method')
        results = []
        
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_259', 'loop_start', 'for_loop', 259, 'For loop')
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
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_296', 'loop_exit', 'for_loop', 296, 'Loop exit: for_loop')
        
        # Filter out None values with exception handling
        try:
            _codegreen_rt.measure_checkpoint('comprehension_list_comp_300', 'comprehension', 'list_comp', 300, 'List comprehension')
            cleaned_results = [x for x in results if x is not None]
        except Exception:
            cleaned_results = []
        
        _codegreen_rt.measure_checkpoint('function_exit_exception_heavy_method_304', 'function_exit', 'exception_heavy_method', 304, 'Function exit: exception_heavy_method')
        return cleaned_results


def complex_standalone_function(data: List[DataPoint], processor: ComplexProcessor) -> Dict:
    """Standalone function with complex nested structures"""
    _codegreen_rt.measure_checkpoint('function_enter_complex_standalone_function_308', 'function_enter', 'complex_standalone_function', 308, 'Function entry: complex_standalone_function')
    
    # Nested function definitions
    def inner_processor(points: List[DataPoint]) -> Iterator[float]:
        def validate_point(point: DataPoint) -> bool:
            _codegreen_rt.measure_checkpoint('function_enter_inner_processor_312', 'function_enter', 'inner_processor', 312, 'Function entry: inner_processor')
            return (
                _codegreen_rt.measure_checkpoint('function_enter_validate_point_313', 'function_enter', 'validate_point', 313, 'Function entry: validate_point')
                point.value is not None and 
                isinstance(point.value, (int, float)) and
                point.timestamp > 0
            )
        _codegreen_rt.measure_checkpoint('function_exit_validate_point_317', 'function_exit', 'validate_point', 317, 'Function exit: validate_point')
        
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_319', 'loop_start', 'for_loop', 319, 'For loop')
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
                    _codegreen_rt.measure_checkpoint('loop_start_while_loop_329', 'loop_start', 'while_loop', 329, 'While loop')
                    while adjusted > 1:
                        adjusted /= 2
                        if adjusted < 0.1:
                            break
                    _codegreen_rt.measure_checkpoint('loop_exit_while_loop_332', 'loop_exit', 'while_loop', 332, 'Loop exit: while_loop')
                    yield adjusted
    _codegreen_rt.measure_checkpoint('loop_exit_for_loop_333', 'loop_exit', 'for_loop', 333, 'Loop exit: for_loop')
    _codegreen_rt.measure_checkpoint('function_exit_inner_processor_333', 'function_exit', 'inner_processor', 333, 'Function exit: inner_processor')
    
    # Multiple nested loops with generators
    results = {
        "processed": list(inner_processor(data)),
        "statistics": {},
        "complex_metrics": {}
    }
    
    # Complex nested loop structure
    _codegreen_rt.measure_checkpoint('loop_start_for_loop_343', 'loop_start', 'for_loop', 343, 'For loop')
    for category in ['low', 'medium', 'high']:
        category_data = []
        threshold = {'low': 10, 'medium': 100, 'high': 1000}[category]
        
        _codegreen_rt.measure_checkpoint('loop_start_for_loop_347', 'loop_start', 'for_loop', 347, 'For loop')
        for point in data:
            if point.value <= threshold:
                _codegreen_rt.measure_checkpoint('loop_start_for_loop_349', 'loop_start', 'for_loop', 349, 'For loop')
                for multiplier in [0.5, 1.0, 1.5, 2.0]:
                    transformed = point.value * multiplier
                    
                    # Nested while loop
                    iterations = 0
                    _codegreen_rt.measure_checkpoint('loop_start_while_loop_354', 'loop_start', 'while_loop', 354, 'While loop')
                    while transformed > 1 and iterations < 10:
                        transformed = transformed ** 0.9
                        iterations += 1
                        
                        # Break conditions inside nested loop
                        if transformed < 0.01:
                            break
                    _codegreen_rt.measure_checkpoint('loop_exit_while_loop_360', 'loop_exit', 'while_loop', 360, 'Loop exit: while_loop')
                    
                    category_data.append(transformed)
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_362', 'loop_exit', 'for_loop', 362, 'Loop exit: for_loop')
        
        results["statistics"][category] = {
            "count": len(category_data),
            "sum": sum(category_data),
            "avg": sum(category_data) / len(category_data) if category_data else 0
        }
    _codegreen_rt.measure_checkpoint('loop_exit_for_loop_368', 'loop_exit', 'for_loop', 368, 'Loop exit: for_loop')
    
    _codegreen_rt.measure_checkpoint('function_exit_complex_standalone_function_370', 'function_exit', 'complex_standalone_function', 370, 'Function exit: complex_standalone_function')
    return results


async def complex_async_main():
    """Complex async main function testing various patterns"""
    _codegreen_rt.measure_checkpoint('function_enter_complex_async_main_374', 'function_enter', 'complex_async_main', 374, 'Function entry: complex_async_main')
    
    # Create test data
    _codegreen_rt.measure_checkpoint('comprehension_list_comp_377', 'comprehension', 'list_comp', 377, 'List comprehension')
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
            _codegreen_rt.measure_checkpoint('loop_start_for_loop_398', 'loop_start', 'for_loop', 398, 'For loop')
            async for result in processor.async_processor(test_data):
                async_results.append(result)
                if len(async_results) >= 10:  # Limit results for testing
                    break
            _codegreen_rt.measure_checkpoint('loop_exit_for_loop_401', 'loop_exit', 'for_loop', 401, 'Loop exit: for_loop')
            
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
            _codegreen_rt.measure_checkpoint('loop_start_for_loop_416', 'loop_start', 'for_loop', 416, 'For loop')
            for batch_start in range(0, len(test_data), batch_size):
                batch = test_data[batch_start:batch_start + batch_size]
                
                # Process batch concurrently
                batch_tasks = []
                _codegreen_rt.measure_checkpoint('loop_start_for_loop_421', 'loop_start', 'for_loop', 421, 'For loop')
                for item in batch:
                    if item.value > 0:
                        # Create coroutine for each positive value
                        task = processor._complex_async_calculation(item.value)
                        batch_tasks.append(task)
                _codegreen_rt.measure_checkpoint('loop_exit_for_loop_425', 'loop_exit', 'for_loop', 425, 'Loop exit: for_loop')
                
                if batch_tasks:
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    _codegreen_rt.measure_checkpoint('comprehension_list_comp_429', 'comprehension', 'list_comp', 429, 'List comprehension')
                    valid_results = [r for r in batch_results if not isinstance(r, Exception)]
                    print(f"Batch {batch_start // batch_size + 1}: {len(valid_results)} valid results")
        _codegreen_rt.measure_checkpoint('loop_exit_for_loop_430', 'loop_exit', 'for_loop', 430, 'Loop exit: for_loop')
        
        except Exception as e:
            print(f"Error in main processing: {e}")
            raise
        
        finally:
            # Cleanup
            processor.executor.shutdown(wait=True)
            print("Cleanup completed")
_codegreen_rt.measure_checkpoint('function_exit_complex_async_main_439', 'function_exit', 'complex_async_main', 439, 'Function exit: complex_async_main')


def fibonacci_itertools_approach(n: int) -> int:
    """Fibonacci using itertools - tests iterator protocols"""
    _codegreen_rt.measure_checkpoint('function_enter_fibonacci_itertools_approach_443', 'function_enter', 'fibonacci_itertools_approach', 443, 'Function entry: fibonacci_itertools_approach')
    def fib_generator():
        a, b = 0, 1
        _codegreen_rt.measure_checkpoint('function_enter_fib_generator_445', 'function_enter', 'fib_generator', 445, 'Function entry: fib_generator')
        _codegreen_rt.measure_checkpoint('loop_start_while_loop_446', 'loop_start', 'while_loop', 446, 'While loop')
        while True:
            yield a
            a, b = b, a + b
    _codegreen_rt.measure_checkpoint('loop_exit_while_loop_448', 'loop_exit', 'while_loop', 448, 'Loop exit: while_loop')
    _codegreen_rt.measure_checkpoint('function_exit_fib_generator_448', 'function_exit', 'fib_generator', 448, 'Function exit: fib_generator')
    
    _codegreen_rt.measure_checkpoint('function_exit_fibonacci_itertools_approach_450', 'function_exit', 'fibonacci_itertools_approach', 450, 'Function exit: fibonacci_itertools_approach')
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
    _codegreen_rt.measure_checkpoint('loop_start_for_loop_472', 'loop_start', 'for_loop', 472, 'For loop')
    for i in range(10):
        fib_val = fibonacci_itertools_approach(i)
        print(f"F({i}) = {fib_val}")
    _codegreen_rt.measure_checkpoint('loop_exit_for_loop_474', 'loop_exit', 'for_loop', 474, 'Loop exit: for_loop')
    
    # Run async tests
    try:
        asyncio.run(complex_async_main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        raise
    
    print("\n✅ Complex Python test completed!")