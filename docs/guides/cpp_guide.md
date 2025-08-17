# C++ Development Guide for CodeGreen

This guide will help you understand C++ development in the CodeGreen project, from basic concepts to advanced usage.

## Table of Contents
1. [C++ Basics](#c-basics)
2. [Project Structure](#project-structure)
3. [Building and Running](#building-and-running)
4. [Testing](#testing)
5. [Common Patterns](#common-patterns)
6. [Best Practices](#best-practices)

## C++ Basics

### Key Concepts

1. **Memory Management**
   ```cpp
   // Smart pointers for automatic memory management
   #include <memory>
   
   // Unique pointer - exclusive ownership
   auto ptr = std::make_unique<Measurement>();
   
   // Shared pointer - shared ownership
   auto shared_ptr = std::make_shared<Measurement>();
   
   // Weak pointer - non-owning reference
   std::weak_ptr<Measurement> weak_ref = shared_ptr;
   ```

2. **Error Handling**
   ```cpp
   // Exception-based error handling
   class MeasurementError : public std::exception {
   public:
       const char* what() const noexcept override {
           return "Measurement error occurred";
       }
   };
   
   // Return error codes
   enum class ErrorCode {
       Success,
       HardwareError,
       InvalidMeasurement
   };
   ```

3. **Templates and Generic Programming**
   ```cpp
   // Template class
   template<typename T>
   class EnergyAnalyzer {
   public:
       T analyze(const std::string& code);
   };
   
   // Template function
   template<typename T>
   T measure_energy(const T& target) {
       // Implementation
   }
   ```

## Project Structure

### CMake Organization
```
codegreen/
├── CMakeLists.txt                  # Main CMake configuration
├── src/                            # Main application source
│   └── main.cpp                   # Entry point
├── core/                           # Core library
│   ├── CMakeLists.txt             # Core library build config
│   ├── include/                    # Public headers
│   └── src/                        # Implementation files
├── packages/                        # Feature packages
│   ├── ide/                        # IDE integration
│   ├── optimizer/                  # Code optimization
│   ├── visualization/              # Data visualization
│   ├── instrumentation/            # Code instrumentation
│   ├── hardware-plugins/           # Hardware monitoring plugins
│   └── language-adapters/          # Language-specific adapters
```

### Key Files
- `CMakeLists.txt`: Build configuration
- `include/`: Header files
- `src/`: Source files
- `tests/`: Test files
- `examples/`: Example code

## Building and Running

### Basic Commands

1. **Build the project**
   ```bash
   # Create build directory
   mkdir build && cd build
   
   # Configure with CMake
   cmake .. -DCMAKE_BUILD_TYPE=Release
   
   # Build
   make -j$(nproc)
   ```

2. **Install the project**
   ```bash
   # Install to system
   sudo make install
   
   # Install to user directory
   cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local
   make install
   ```

3. **Clean build**
   ```bash
   # Remove build artifacts
   rm -rf build/
   
   # Or clean specific targets
   make clean
   ```

### Development Workflow

1. **Debug build**
   ```bash
   cmake .. -DCMAKE_BUILD_TYPE=Debug
   make
   ```

2. **Format code**
   ```bash
   # Using clang-format
   clang-format -i src/*.cpp include/*.hpp
   
   # Using astyle
   astyle --style=google src/*.cpp include/*.hpp
   ```

3. **Static analysis**
   ```bash
   # Using clang-tidy
   clang-tidy src/*.cpp -checks=*
   ```

## Testing

### Types of Tests

1. **Unit Tests**
   ```cpp
   #include <gtest/gtest.h>
   
   TEST(MeasurementTest, BasicFunctionality) {
       Measurement m;
       EXPECT_EQ(m.get_energy(), 0.0);
   }
   ```

2. **Integration Tests**
   ```cpp
   TEST(MeasurementEngineTest, CompleteFlow) {
       MeasurementEngine engine;
       auto session = engine.start_measurement();
       EXPECT_TRUE(session != nullptr);
   }
   ```

3. **Benchmark Tests**
   ```cpp
   #include <benchmark/benchmark.h>
   
   static void BM_EnergyMeasurement(benchmark::State& state) {
       for (auto _ : state) {
           measure_energy();
       }
   }
   BENCHMARK(BM_EnergyMeasurement);
   ```

### Running Tests
```bash
# Run all tests
make test

# Run specific test
./test/unit_tests --gtest_filter=MeasurementTest.*

# Run with verbose output
./test/unit_tests --gtest_verbose
```

## Common Patterns

### RAII (Resource Acquisition Is Initialization)
```cpp
class MeasurementSession {
public:
    MeasurementSession() {
        // Acquire resources
        start_monitoring();
    }
    
    ~MeasurementSession() {
        // Automatically release resources
        stop_monitoring();
    }
};
```

### PIMPL (Pointer to Implementation)
```cpp
// Header file
class MeasurementEngine {
public:
    MeasurementEngine();
    ~MeasurementEngine();
    void measure();
private:
    class Impl;
    std::unique_ptr<Impl> pImpl;
};

// Implementation file
class MeasurementEngine::Impl {
public:
    void measure() { /* implementation */ }
};

MeasurementEngine::MeasurementEngine() : pImpl(std::make_unique<Impl>()) {}
MeasurementEngine::~MeasurementEngine() = default;
void MeasurementEngine::measure() { pImpl->measure(); }
```

### Plugin System
```cpp
class HardwarePlugin {
public:
    virtual ~HardwarePlugin() = default;
    virtual std::string name() const = 0;
    virtual bool init() = 0;
    virtual Measurement get_measurement() = 0;
};

class PluginRegistry {
public:
    void register_plugin(std::unique_ptr<HardwarePlugin> plugin);
    std::vector<const HardwarePlugin*> get_plugins() const;
private:
    std::vector<std::unique_ptr<HardwarePlugin>> plugins_;
};
```

## Best Practices

### Code Organization

1. **Header Organization**
   - Use include guards or `#pragma once`
   - Forward declare when possible
   - Keep headers minimal

2. **Error Handling**
   - Use exceptions for exceptional cases
   - Return error codes for expected failures
   - Provide meaningful error messages

3. **Documentation**
   ```cpp
   /**
    * @brief Measures energy consumption of the target
    * @param target The target to measure
    * @return Energy measurement in joules
    * @throws MeasurementError if measurement fails
    */
   double measure_energy(const Target& target);
   ```

### Performance

1. **Memory Management**
   - Use smart pointers by default
   - Avoid raw pointers when possible
   - Use move semantics for efficiency

2. **Concurrency**
   - Use `std::thread` for CPU-bound tasks
   - Use `std::async` for simple async operations
   - Use `std::mutex` and `std::lock_guard` for synchronization

3. **Optimization**
   - Profile before optimizing
   - Use `const` and `constexpr` where appropriate
   - Consider cache locality

### Modern C++ Features

1. **C++17 Features**
   ```cpp
   // Structured bindings
   auto [energy, power] = get_measurements();
   
   // If constexpr
   if constexpr (std::is_same_v<T, double>) {
       // Compile-time conditional
   }
   
   // std::optional
   std::optional<Measurement> get_measurement();
   ```

2. **C++20 Features (if available)**
   ```cpp
   // Concepts
   template<typename T>
   concept Measurable = requires(T t) {
       { t.measure() } -> std::convertible_to<double>;
   };
   
   // Ranges
   auto measurements = data | std::views::filter([](auto m) { return m.valid(); });
   ```

## Additional Resources

1. **Official Documentation**
   - [C++ Reference](https://en.cppreference.com/)
   - [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/)
   - [C++ Standard](https://isocpp.org/std/the-standard)

2. **Tools**
   - [clang-format](https://clang.llvm.org/docs/ClangFormat.html) - Code formatting
   - [clang-tidy](https://clang.llvm.org/extra/clang-tidy/) - Static analysis
   - [Valgrind](https://valgrind.org/) - Memory debugging

3. **Community**
   - [Stack Overflow](https://stackoverflow.com/questions/tagged/c%2b%2b)
   - [Reddit r/cpp](https://www.reddit.com/r/cpp/)
   - [C++ Discord](https://discord.gg/ZPErMGW)
