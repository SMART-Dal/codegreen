#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <chrono>
#include <cmath>

/**
 * Comprehensive C++ Sample for CodeGreen Testing
 * Tests various language constructs and checkpoint generation
 */

class DataProcessor {
private:
    std::vector<double> data;
    int processed_count;
    
public:
    DataProcessor(const std::vector<double>& input_data) 
        : data(input_data), processed_count(0) {}
    
    std::vector<double> process_data() {
        std::vector<double> results;
        
        // Test loop checkpoint
        for (size_t i = 0; i < data.size(); ++i) {
            if (data[i] > 0) {
                // Test conditional checkpoint
                double processed = std::sqrt(data[i]) * 2.0;
                results.push_back(processed);
                processed_count++;
            }
        }
        
        return results;
    }
    
    std::pair<double, double> get_statistics() {
        if (data.empty()) {
            return {0.0, 0.0};
        }
        
        double sum = 0.0;
        double max_val = data[0];
        double min_val = data[0];
        
        for (double value : data) {
            sum += value;
            max_val = std::max(max_val, value);
            min_val = std::min(min_val, value);
        }
        
        return {sum / data.size(), max_val - min_val};
    }
    
    int get_processed_count() const {
        return processed_count;
    }
};

class FibonacciCalculator {
public:
    static int recursive(int n) {
        if (n <= 1) return n;
        return recursive(n - 1) + recursive(n - 2);
    }
    
    static int iterative(int n) {
        if (n <= 1) return n;
        
        int a = 0, b = 1;
        for (int i = 2; i <= n; ++i) {
            int temp = a + b;
            a = b;
            b = temp;
        }
        return b;
    }
};

template<typename T>
class VectorOperations {
public:
    static std::vector<T> generate_squares(int count) {
        std::vector<T> squares;
        squares.reserve(count);
        
        for (int i = 0; i < count; ++i) {
            squares.push_back(i * i);
        }
        
        return squares;
    }
    
    static T sum(const std::vector<T>& vec) {
        T total = T{};
        for (const T& value : vec) {
            total += value;
        }
        return total;
    }
};

int main() {
    std::cout << "🚀 CodeGreen C++ Language Test" << std::endl;
    std::cout << "================================" << std::endl;
    
    // Test data processing
    std::vector<double> data = {1.0, 4.0, 9.0, 16.0, 25.0, -1.0, 36.0};
    DataProcessor processor(data);
    
    std::cout << "Input data: ";
    for (double value : data) {
        std::cout << value << " ";
    }
    std::cout << std::endl;
    
    // Process data
    auto start_time = std::chrono::high_resolution_clock::now();
    std::vector<double> results = processor.process_data();
    auto end_time = std::chrono::high_resolution_clock::now();
    
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    
    std::cout << "Processed results: ";
    for (double value : results) {
        std::cout << value << " ";
    }
    std::cout << std::endl;
    std::cout << "Processing time: " << duration.count() << " microseconds" << std::endl;
    
    // Get statistics
    auto stats = processor.get_statistics();
    std::cout << "Statistics - Mean: " << stats.first << ", Range: " << stats.second << std::endl;
    std::cout << "Processed count: " << processor.get_processed_count() << std::endl;
    
    // Test Fibonacci functions
    std::cout << "\n🧮 Testing Fibonacci functions:" << std::endl;
    for (int i = 0; i < 8; ++i) {
        int fib_rec = FibonacciCalculator::recursive(i);
        int fib_iter = FibonacciCalculator::iterative(i);
        std::cout << "F(" << i << ") = " << fib_rec << " (recursive), " << fib_iter << " (iterative)" << std::endl;
    }
    
    // Test template operations
    std::cout << "\n📊 Testing template operations:" << std::endl;
    auto squares = VectorOperations<int>::generate_squares(5);
    std::cout << "Squares: ";
    for (int value : squares) {
        std::cout << value << " ";
    }
    std::cout << std::endl;
    
    int sum_squares = VectorOperations<int>::sum(squares);
    std::cout << "Sum of squares: " << sum_squares << std::endl;
    
    // Test STL algorithms
    std::vector<int> numbers = {3, 1, 4, 1, 5, 9, 2, 6};
    std::sort(numbers.begin(), numbers.end());
    
    std::cout << "Sorted numbers: ";
    for (int value : numbers) {
        std::cout << value << " ";
    }
    std::cout << std::endl;
    
    std::cout << "\n✅ C++ language test completed successfully!" << std::endl;
    
    return 0;
}
