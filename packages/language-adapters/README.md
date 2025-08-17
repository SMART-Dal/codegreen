# Energy Language Adapters

The **Energy Language Adapters** module contains language-specific extensions for CodeGreen. It includes language-specific parsing and instrumentation rules tailored for different programming languages.

**Responsibilities:**
- Provide language-specific parsing for detecting method/function definitions.
- Customize instrumentation rules for languages such as Java, Python, and C/C++.
- Act as an extension point to support additional languages in the future.

**Design Patterns:**
- **Plugin Architecture:** Allowing seamless addition of new language support.
- **Separation of Language-Specific Logic:** Ensuring core instrumentation remains language agnostic.

## Building

```bash
# From the project root
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make codegreen-language-adapters
```

## Testing

```bash
# Run language adapter tests
ctest -R language_adapters
```

## Usage

```cpp
#include "language_adapter.hpp"

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

## Adding New Language Support

1. Create a new adapter class inheriting from `LanguageAdapter`
2. Implement the required virtual methods
3. Add language-specific parsing logic
4. Register the adapter with the measurement engine

## Usage and Extension:**
- Add new language support by creating new adapter classes with the necessary parsing logic and rules.
- Maintain consistency with existing structures for ease of integration.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your language adapter
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
