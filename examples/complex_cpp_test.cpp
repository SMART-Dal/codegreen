/*
 * Complex C++ Test for CodeGreen Instrumentation
 * Tests challenging constructs: templates, classes, inheritance, lambdas,
 * smart pointers, STL containers, exception handling, RAII
 */

#include <iostream>
#include <vector>
#include <map>
#include <unordered_map>
#include <memory>
#include <algorithm>
#include <functional>
#include <thread>
#include <mutex>
#include <future>
#include <chrono>
#include <random>
#include <exception>
#include <typeinfo>
#include <sstream>
#include <fstream>
#include <queue>
#include <stack>

// Forward declarations for complex template usage
template<typename T> class SmartContainer;
template<typename T, typename Predicate> class FilteredContainer;

// Complex template with multiple parameters and specializations
template<typename T, int N = 10, typename Allocator = std::allocator<T>>
class AdvancedMatrix {
private:
    std::vector<std::vector<T, Allocator>> data_;
    size_t rows_, cols_;
    mutable std::mutex mutex_;
    
public:
    // Constructor with complex initialization
    AdvancedMatrix(size_t rows, size_t cols) : rows_(rows), cols_(cols) {
        data_.resize(rows_);
        for (size_t i = 0; i < rows_; ++i) {
            data_[i].resize(cols_);
            // Complex initialization with nested loops
            for (size_t j = 0; j < cols_; ++j) {
                if constexpr (std::is_arithmetic_v<T>) {
                    data_[i][j] = static_cast<T>(i * cols_ + j);
                } else {
                    data_[i][j] = T{};
                }
            }
        }
    }
    
    // Copy constructor with complex logic
    AdvancedMatrix(const AdvancedMatrix& other) : rows_(other.rows_), cols_(other.cols_) {
        std::lock_guard<std::mutex> lock(other.mutex_);
        data_ = other.data_;
        
        // Complex post-copy processing
        for (auto& row : data_) {
            for (auto& element : row) {
                if constexpr (std::is_arithmetic_v<T>) {
                    element = static_cast<T>(element * 1.1);  // Slightly modify copied data
                }
            }
        }
    }
    
    // Move constructor
    AdvancedMatrix(AdvancedMatrix&& other) noexcept 
        : data_(std::move(other.data_)), rows_(other.rows_), cols_(other.cols_) {
        other.rows_ = other.cols_ = 0;
    }
    
    // Complex operator overloading
    AdvancedMatrix& operator=(const AdvancedMatrix& other) {
        if (this != &other) {
            std::lock(mutex_, other.mutex_);
            std::lock_guard<std::mutex> lock1(mutex_, std::adopt_lock);
            std::lock_guard<std::mutex> lock2(other.mutex_, std::adopt_lock);
            
            rows_ = other.rows_;
            cols_ = other.cols_;
            data_ = other.data_;
        }
        return *this;
    }
    
    // Template method with complex SFINAE
    template<typename U>
    typename std::enable_if_t<std::is_convertible_v<U, T>, AdvancedMatrix&>
    multiply_scalar(const U& scalar) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        // Parallel processing with complex lambda
        std::for_each(std::execution::par_unseq, data_.begin(), data_.end(),
            [scalar](auto& row) {
                std::for_each(row.begin(), row.end(),
                    [scalar](auto& element) {
                        element = static_cast<T>(element * scalar);
                    });
            });
        
        return *this;
    }
    
    // Complex nested iteration with various loop types
    void complex_processing() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        // Range-based for with structured bindings
        for (auto&& [row_idx, row] : enumerate(data_)) {
            // Traditional for loop
            for (size_t col_idx = 0; col_idx < row.size(); ++col_idx) {
                // While loop with complex condition
                T& element = row[col_idx];
                size_t iterations = 0;
                
                while (iterations < 5 && element != T{}) {
                    if constexpr (std::is_arithmetic_v<T>) {
                        // Do-while loop inside while
                        T temp = element;
                        do {
                            temp = static_cast<T>(temp * 0.9);
                            ++iterations;
                        } while (temp > static_cast<T>(0.1) && iterations < 10);
                        
                        element = temp;
                    }
                    ++iterations;
                }
                
                // For loop with complex increment
                for (T factor = static_cast<T>(1.1); 
                     factor < static_cast<T>(2.0); 
                     factor = static_cast<T>(factor * 1.1)) {
                    
                    if constexpr (std::is_arithmetic_v<T>) {
                        element = static_cast<T>(element * factor);
                        
                        // Break conditions in nested loop
                        if (element > static_cast<T>(1000)) {
                            break;
                        }
                    }
                }
            }
        }
    }
    
private:
    // Helper function for enumeration (C++17 style)
    template<typename Container>
    auto enumerate(Container&& container) {
        struct Iterator {
            size_t index;
            typename std::remove_reference_t<Container>::iterator iter;
            
            auto operator*() { return std::forward_as_tuple(index, *iter); }
            Iterator& operator++() { ++index; ++iter; return *this; }
            bool operator!=(const Iterator& other) const { return iter != other.iter; }
        };
        
        struct Enumerable {
            Container& container;
            auto begin() { return Iterator{0, container.begin()}; }
            auto end() { return Iterator{0, container.end()}; }
        };
        
        return Enumerable{container};
    }
};

// Template specialization for complex types
template<int N, typename Allocator>
class AdvancedMatrix<std::string, N, Allocator> {
private:
    std::vector<std::vector<std::string, Allocator>> data_;
    
public:
    AdvancedMatrix(size_t rows, size_t cols) {
        data_.resize(rows);
        for (size_t i = 0; i < rows; ++i) {
            data_[i].resize(cols);
            for (size_t j = 0; j < cols; ++j) {
                std::ostringstream oss;
                oss << "Cell(" << i << "," << j << ")";
                data_[i][j] = oss.str();
            }
        }
    }
    
    void string_specific_processing() {
        for (auto& row : data_) {
            for (auto& str : row) {
                // Complex string manipulation
                std::transform(str.begin(), str.end(), str.begin(), ::toupper);
                
                // Nested loop for character processing
                for (size_t i = 0; i < str.length(); ++i) {
                    if (str[i] == '(' || str[i] == ')') {
                        for (size_t j = i + 1; j < str.length(); ++j) {
                            if (std::isdigit(str[j])) {
                                str[j] = static_cast<char>(str[j] + 1);
                                break;
                            }
                        }
                    }
                }
            }
        }
    }
};

// Complex inheritance hierarchy
class BaseProcessor {
protected:
    std::unique_ptr<std::vector<double>> data_;
    mutable std::shared_mutex shared_mutex_;
    
public:
    BaseProcessor() : data_(std::make_unique<std::vector<double>>()) {}
    
    virtual ~BaseProcessor() = default;
    
    virtual void process() = 0;
    virtual std::unique_ptr<BaseProcessor> clone() const = 0;
    
    // Virtual function with complex implementation
    virtual double calculate_metric() const {
        std::shared_lock<std::shared_mutex> lock(shared_mutex_);
        
        if (data_->empty()) return 0.0;
        
        double sum = 0.0;
        double sum_squares = 0.0;
        
        // Complex calculation with nested conditions
        for (const auto& value : *data_) {
            sum += value;
            sum_squares += value * value;
            
            // Nested processing based on value
            if (value > 0) {
                for (int i = 1; i <= 3; ++i) {
                    double temp = std::pow(value, 1.0 / i);
                    if (temp > 1.0) {
                        sum += temp * 0.1;
                    }
                }
            } else if (value < 0) {
                double abs_val = std::abs(value);
                while (abs_val > 1.0) {
                    abs_val = std::sqrt(abs_val);
                    sum += abs_val * 0.05;
                }
            }
        }
        
        double mean = sum / data_->size();
        double variance = (sum_squares / data_->size()) - (mean * mean);
        
        return std::sqrt(variance);  // Return standard deviation
    }
};

class AdvancedProcessor : public BaseProcessor {
private:
    std::map<std::string, std::function<double(double)>> operations_;
    std::queue<std::pair<std::string, double>> operation_queue_;
    std::mutex queue_mutex_;
    
public:
    AdvancedProcessor() {
        // Initialize operations map with lambdas
        operations_["square"] = [](double x) { return x * x; };
        operations_["sqrt"] = [](double x) { return x >= 0 ? std::sqrt(x) : 0.0; };
        operations_["log"] = [](double x) { return x > 0 ? std::log(x) : -1.0; };
        operations_["sin"] = [](double x) { return std::sin(x); };
        operations_["complex"] = [](double x) {
            double result = x;
            for (int i = 1; i <= 5; ++i) {
                result = std::sin(result) + std::cos(result * i);
                if (std::abs(result) > 100) break;
            }
            return result;
        };
    }
    
    void process() override {
        std::unique_lock<std::shared_mutex> lock(shared_mutex_);
        
        // Generate test data with complex patterns
        data_->clear();
        std::random_device rd;
        std::mt19937 gen(rd());
        std::normal_distribution<> dis(0.0, 1.0);
        
        for (int i = 0; i < 100; ++i) {
            double value = dis(gen);
            data_->push_back(value);
            
            // Complex nested processing
            for (const auto& [name, operation] : operations_) {
                try {
                    double result = operation(value);
                    
                    // Queue operations for batch processing
                    {
                        std::lock_guard<std::mutex> queue_lock(queue_mutex_);
                        operation_queue_.emplace(name, result);
                    }
                    
                    // Process queue when it gets large
                    if (operation_queue_.size() > 10) {
                        process_operation_queue();
                    }
                    
                } catch (const std::exception& e) {
                    std::cerr << "Operation " << name << " failed: " << e.what() << std::endl;
                }
            }
        }
        
        // Process remaining operations
        process_operation_queue();
    }
    
    std::unique_ptr<BaseProcessor> clone() const override {
        return std::make_unique<AdvancedProcessor>(*this);
    }
    
private:
    void process_operation_queue() {
        std::lock_guard<std::mutex> queue_lock(queue_mutex_);
        
        std::vector<double> batch_results;
        
        while (!operation_queue_.empty()) {
            auto [operation_name, result] = operation_queue_.front();
            operation_queue_.pop();
            
            // Complex batch processing
            if (operation_name == "complex") {
                // Multi-step processing for complex operations
                double processed = result;
                for (int step = 0; step < 3; ++step) {
                    if (processed > 0) {
                        processed = std::log(processed + 1);
                    } else {
                        processed = -std::log(-processed + 1);
                    }
                    
                    // Nested validation loop
                    int validation_count = 0;
                    while (std::isnan(processed) || std::isinf(processed)) {
                        processed = result * 0.1;
                        if (++validation_count > 5) break;
                    }
                }
                batch_results.push_back(processed);
            } else {
                batch_results.push_back(result);
            }
        }
        
        // Apply batch results back to main data
        if (!batch_results.empty()) {
            std::unique_lock<std::shared_mutex> data_lock(shared_mutex_);
            for (size_t i = 0; i < std::min(batch_results.size(), data_->size()); ++i) {
                (*data_)[i] = ((*data_)[i] + batch_results[i]) * 0.5;
            }
        }
    }
};

// Complex template function with multiple constraints
template<typename Container, typename Predicate, typename Transform>
requires std::ranges::range<Container> && 
         std::predicate<Predicate, std::ranges::range_value_t<Container>> &&
         std::invocable<Transform, std::ranges::range_value_t<Container>>
auto complex_algorithm(Container&& container, Predicate pred, Transform trans) {
    using ValueType = std::ranges::range_value_t<Container>;
    using ResultType = std::invoke_result_t<Transform, ValueType>;
    
    std::vector<ResultType> results;
    std::map<ResultType, size_t> frequency_map;
    
    // Complex multi-pass processing
    for (const auto& item : container) {
        if (pred(item)) {
            ResultType transformed = trans(item);
            results.push_back(transformed);
            
            // Track frequency
            ++frequency_map[transformed];
            
            // Complex nested processing based on frequency
            if (frequency_map[transformed] > 1) {
                // Process duplicates differently
                for (auto& prev_result : results) {
                    if (prev_result == transformed) {
                        if constexpr (std::is_arithmetic_v<ResultType>) {
                            prev_result = static_cast<ResultType>(prev_result * 1.1);
                        }
                    }
                }
            }
        }
    }
    
    // Sort and process results
    std::sort(results.begin(), results.end());
    
    // Complex post-processing with multiple loops
    for (size_t i = 0; i < results.size(); ++i) {
        for (size_t j = i + 1; j < results.size(); ++j) {
            if constexpr (std::is_arithmetic_v<ResultType>) {
                if (results[i] + results[j] > static_cast<ResultType>(0)) {
                    // Nested calculation loop
                    ResultType factor = static_cast<ResultType>(1.01);
                    int iterations = 0;
                    
                    do {
                        results[i] = static_cast<ResultType>(results[i] * factor);
                        results[j] = static_cast<ResultType>(results[j] / factor);
                        factor = static_cast<ResultType>(factor * 1.01);
                        ++iterations;
                    } while (iterations < 3 && factor < static_cast<ResultType>(1.1));
                }
            }
        }
    }
    
    return results;
}

// Complex async processing class
class AsyncProcessor {
private:
    std::vector<std::future<double>> futures_;
    std::vector<std::thread> threads_;
    std::atomic<bool> stop_flag_{false};
    std::condition_variable cv_;
    std::mutex cv_mutex_;
    
public:
    ~AsyncProcessor() {
        stop_all();
    }
    
    void start_processing(const std::vector<double>& data) {
        stop_flag_ = false;
        
        // Create multiple async tasks
        for (size_t i = 0; i < data.size(); i += 10) {
            size_t end_idx = std::min(i + 10, data.size());
            std::vector<double> batch(data.begin() + i, data.begin() + end_idx);
            
            // Launch async task with complex lambda
            auto future = std::async(std::launch::async, [this, batch, i]() mutable {
                double result = 0.0;
                
                // Complex processing loop
                for (size_t j = 0; j < batch.size(); ++j) {
                    if (stop_flag_.load()) return result;
                    
                    double value = batch[j];
                    
                    // Nested computation loops
                    for (int iteration = 0; iteration < 5; ++iteration) {
                        if (stop_flag_.load()) return result;
                        
                        for (int inner = 0; inner < 3; ++inner) {
                            value = std::sin(value) + std::cos(value * (iteration + 1));
                            
                            // Early termination check
                            if (std::abs(value) > 1000) {
                                value = 0.0;
                                break;
                            }
                        }
                        
                        result += value;
                        
                        // Synchronization point
                        {
                            std::unique_lock<std::mutex> lock(cv_mutex_);
                            cv_.wait_for(lock, std::chrono::milliseconds(1));
                        }
                    }
                }
                
                return result;
            });
            
            futures_.push_back(std::move(future));
        }
        
        // Start monitoring thread
        threads_.emplace_back([this]() {
            while (!stop_flag_.load()) {
                {
                    std::lock_guard<std::mutex> lock(cv_mutex_);
                    cv_.notify_all();
                }
                
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                
                // Check futures status
                size_t completed = 0;
                for (const auto& future : futures_) {
                    if (future.wait_for(std::chrono::milliseconds(0)) == std::future_status::ready) {
                        ++completed;
                    }
                }
                
                if (completed == futures_.size()) {
                    break;
                }
            }
        });
    }
    
    std::vector<double> get_results() {
        std::vector<double> results;
        
        for (auto& future : futures_) {
            try {
                if (future.valid()) {
                    double result = future.get();
                    results.push_back(result);
                }
            } catch (const std::exception& e) {
                std::cerr << "Future exception: " << e.what() << std::endl;
                results.push_back(0.0);
            }
        }
        
        return results;
    }
    
    void stop_all() {
        stop_flag_ = true;
        
        {
            std::lock_guard<std::mutex> lock(cv_mutex_);
            cv_.notify_all();
        }
        
        for (auto& thread : threads_) {
            if (thread.joinable()) {
                thread.join();
            }
        }
        
        threads_.clear();
        futures_.clear();
    }
};

// Exception handling with custom exceptions
class ProcessingException : public std::exception {
private:
    std::string message_;
    int error_code_;
    
public:
    ProcessingException(const std::string& message, int code = 0) 
        : message_(message), error_code_(code) {}
    
    const char* what() const noexcept override {
        return message_.c_str();
    }
    
    int error_code() const noexcept { return error_code_; }
};

// Complex function with extensive exception handling
void complex_exception_test() {
    std::vector<std::unique_ptr<BaseProcessor>> processors;
    
    try {
        // Create processors with potential failures
        for (int i = 0; i < 5; ++i) {
            try {
                auto processor = std::make_unique<AdvancedProcessor>();
                
                // Complex validation with nested try-catch
                try {
                    processor->process();
                    double metric = processor->calculate_metric();
                    
                    if (std::isnan(metric) || std::isinf(metric)) {
                        throw ProcessingException("Invalid metric calculated", 1001);
                    }
                    
                    processors.push_back(std::move(processor));
                    
                } catch (const ProcessingException& pe) {
                    std::cerr << "Processing exception: " << pe.what() 
                              << " (code: " << pe.error_code() << ")" << std::endl;
                    
                    // Retry with different parameters
                    if (pe.error_code() == 1001) {
                        auto retry_processor = std::make_unique<AdvancedProcessor>();
                        try {
                            retry_processor->process();
                            processors.push_back(std::move(retry_processor));
                        } catch (...) {
                            // Ignore retry failures
                        }
                    }
                } catch (const std::runtime_error& re) {
                    std::cerr << "Runtime error: " << re.what() << std::endl;
                    continue;
                }
                
            } catch (const std::bad_alloc& ba) {
                std::cerr << "Memory allocation failed: " << ba.what() << std::endl;
                break;  // Stop creating more processors
            } catch (...) {
                std::cerr << "Unknown exception during processor creation" << std::endl;
                continue;
            }
        }
        
        // Process all created processors
        for (auto& processor : processors) {
            if (processor) {
                try {
                    processor->process();
                    
                    // Complex processing loop with exception handling
                    for (int attempt = 0; attempt < 3; ++attempt) {
                        try {
                            double metric = processor->calculate_metric();
                            std::cout << "Processor metric (attempt " << attempt + 1 
                                      << "): " << metric << std::endl;
                            break;  // Success, exit retry loop
                            
                        } catch (const std::exception& e) {
                            if (attempt == 2) {
                                throw;  // Re-throw on final attempt
                            }
                            
                            std::cerr << "Attempt " << attempt + 1 
                                      << " failed: " << e.what() << std::endl;
                            std::this_thread::sleep_for(std::chrono::milliseconds(10));
                        }
                    }
                    
                } catch (const std::exception& e) {
                    std::cerr << "Failed to process: " << e.what() << std::endl;
                }
            }
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Top-level exception: " << e.what() << std::endl;
        throw;  // Re-throw for caller
    } catch (...) {
        std::cerr << "Unknown top-level exception" << std::endl;
        throw;
    }
}

// Main function with comprehensive testing
int main() {
    std::cout << "🧪 Starting Complex C++ CodeGreen Test" << std::endl;
    std::cout << "======================================" << std::endl;
    
    try {
        // Test 1: Template matrix operations
        std::cout << "\n📊 Testing template matrix operations:" << std::endl;
        
        AdvancedMatrix<double> double_matrix(5, 5);
        double_matrix.multiply_scalar(2.5);
        double_matrix.complex_processing();
        
        AdvancedMatrix<std::string> string_matrix(3, 3);
        string_matrix.string_specific_processing();
        
        std::cout << "Matrix operations completed" << std::endl;
        
        // Test 2: Complex algorithm testing
        std::cout << "\n🔄 Testing complex algorithms:" << std::endl;
        
        std::vector<int> test_data(100);
        std::iota(test_data.begin(), test_data.end(), -50);
        
        auto results = complex_algorithm(test_data,
            [](int x) { return x % 3 == 0; },  // Predicate: multiples of 3
            [](int x) { return x * x + 1; }    // Transform: x² + 1
        );
        
        std::cout << "Complex algorithm processed " << results.size() << " elements" << std::endl;
        
        // Test 3: Inheritance and polymorphism
        std::cout << "\n🏗️ Testing inheritance and polymorphism:" << std::endl;
        
        std::vector<std::unique_ptr<BaseProcessor>> processors;
        for (int i = 0; i < 3; ++i) {
            processors.push_back(std::make_unique<AdvancedProcessor>());
        }
        
        for (auto& processor : processors) {
            processor->process();
            double metric = processor->calculate_metric();
            std::cout << "Processor metric: " << metric << std::endl;
        }
        
        // Test 4: Async processing
        std::cout << "\n⚡ Testing async processing:" << std::endl;
        
        std::vector<double> async_data(50);
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_real_distribution<> dis(-10.0, 10.0);
        
        std::generate(async_data.begin(), async_data.end(), [&]() { return dis(gen); });
        
        AsyncProcessor async_proc;
        async_proc.start_processing(async_data);
        
        // Wait a bit then get results
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        auto async_results = async_proc.get_results();
        
        std::cout << "Async processing completed with " << async_results.size() << " results" << std::endl;
        
        // Test 5: Exception handling
        std::cout << "\n🚨 Testing exception handling:" << std::endl;
        
        try {
            complex_exception_test();
            std::cout << "Exception handling test completed successfully" << std::endl;
        } catch (const ProcessingException& pe) {
            std::cout << "Caught ProcessingException: " << pe.what() 
                      << " (code: " << pe.error_code() << ")" << std::endl;
        } catch (const std::exception& e) {
            std::cout << "Caught standard exception: " << e.what() << std::endl;
        }
        
        // Test 6: Complex nested loops with STL algorithms
        std::cout << "\n🔁 Testing complex nested loops:" << std::endl;
        
        std::vector<std::vector<int>> nested_data(10);
        for (size_t i = 0; i < nested_data.size(); ++i) {
            nested_data[i].resize(10);
            std::iota(nested_data[i].begin(), nested_data[i].end(), i * 10);
        }
        
        // Complex nested processing
        int total_processed = 0;
        for (const auto& outer_vec : nested_data) {
            for (const auto& value : outer_vec) {
                // Inner processing loop
                int temp_value = value;
                int inner_iterations = 0;
                
                while (temp_value > 0 && inner_iterations < 5) {
                    temp_value /= 2;
                    ++inner_iterations;
                    
                    // Nested for loop with complex condition
                    for (int factor = 1; factor <= 3; ++factor) {
                        int processed = temp_value * factor;
                        
                        if (processed > 10) {
                            // Do-while loop inside nested structure
                            do {
                                processed -= factor;
                                ++total_processed;
                            } while (processed > factor && total_processed < 1000);
                        }
                        
                        if (total_processed > 500) break;
                    }
                    
                    if (total_processed > 500) break;
                }
                
                if (total_processed > 500) break;
            }
            
            if (total_processed > 500) break;
        }
        
        std::cout << "Complex nested loops processed " << total_processed << " items" << std::endl;
        
        std::cout << "\n✅ All C++ tests completed successfully!" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "\n❌ Test failed with exception: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "\n❌ Test failed with unknown exception" << std::endl;
        return 2;
    }
    
    return 0;
}