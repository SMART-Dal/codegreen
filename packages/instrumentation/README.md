# Energy Instrumentation

The **Energy Instrumentation** module provides language-specific parsing and code instrumentation capabilities. It identifies method or function boundaries and injects measurement hooks to capture energy consumption at a fine granularity.

## Features
- High-performance C++ implementation for minimal measurement noise
- Language-specific parsing using appropriate parsing libraries
- Plugin system for language-specific adapters
- Efficient memory management with smart pointers
- Cross-platform compatibility

## Building

```bash
# From the project root
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make codegreen-instrumentation
```

## Testing

```bash
# Run instrumentation tests
ctest -R instrumentation
```

## Usage

```cpp
#include "instrumenter.hpp"

auto instrumenter = std::make_unique<codegreen::Instrumenter>();

// Instrument code
std::string instrumented_code = instrumenter->instrument_code(source_code, "cpp");

// Start monitoring a process
auto session = instrumenter->start_monitoring(process_id);

// Stop monitoring
auto final_session = instrumenter->stop_monitoring(std::move(session));

// Get metrics
auto metrics = instrumenter->get_metrics();
```

## Adding New Language Support

1. Create a new adapter class inheriting from `LanguageAdapter`
2. Implement the required virtual methods
3. Add language-specific parsing logic
4. Register the adapter with the instrumentation engine

Example:
```cpp
class PythonAdapter : public LanguageAdapter {
public:
    std::string get_language_id() const override {
        return "python";
    }
    
    std::unique_ptr<void> parse(const std::string& source_code) override {
        // Implement Python parsing logic
        return nullptr;
    }
    
    bool analyze(const std::string& source_code) override {
        // Implement Python analysis
        return true;
    }
    
    std::vector<std::string> get_suggestions() const override {
        return suggestions_;
    }
};
```

## Performance

- Minimal runtime overhead
- Efficient memory management with RAII
- Native machine code execution
- Optimized parsing algorithms
- Low-latency measurement hooks

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your instrumentation features
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
