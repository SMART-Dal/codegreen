# Energy Hardware Plugins

This package provides hardware-specific energy measurement plugins for CodeGreen. It implements a plugin architecture that allows for easy addition of new hardware measurement capabilities.

## Architecture

The package follows a plugin-based architecture where each hardware-specific implementation:
1. Inherits from the `HardwarePlugin` base class
2. Provides hardware-specific measurement logic
3. Exposes a consistent interface for energy measurement

## Available Plugins

### Intel RAPL Plugin
- Measures CPU package and DRAM energy consumption
- Uses Model Specific Registers (MSR) for measurements
- Requires root access to `/dev/cpu/*/msr`
- Supports power and energy measurements

## Adding New Plugins

To add a new hardware plugin:

1. Create a new header file in `include/`
2. Create a new implementation file in `src/`
3. Inherit from the `HardwarePlugin` base class
4. Implement the required virtual methods
5. Register the plugin in the `PluginRegistry`

Example:
```cpp
#include "hardware_plugin.hpp"

class MyHardwarePlugin : public HardwarePlugin {
public:
    std::string name() const override {
        return "my_hardware";
    }
    
    std::unique_ptr<Measurement> get_measurement() override {
        // Implementation
        return std::make_unique<Measurement>();
    }
    
    bool init() override {
        // Initialize hardware
        return true;
    }
    
    void cleanup() override {
        // Cleanup hardware
    }
    
    bool is_available() const override {
        // Check if hardware is available
        return true;
    }
};
```

## Usage

```cpp
#include "plugin_registry.hpp"
#include "intel_rapl_plugin.hpp"

auto registry = std::make_unique<PluginRegistry>();
registry->register_plugin(std::make_unique<IntelRAPLPlugin>());

// Get available plugins
auto available_plugins = registry->get_available_plugins();

// Use a specific plugin
if (auto plugin = registry->get_plugin("intel_rapl")) {
    plugin->init();
    auto measurement = plugin->get_measurement();
    plugin->cleanup();
}
```

## Requirements

- Linux operating system
- Root access for hardware sensors
- Appropriate hardware support (e.g., Intel CPU for RAPL)
- C++17 compatible compiler

## Testing

Run the tests with:
```bash
# From the project root
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Debug
make
make test

# Or run specific tests
ctest -R hardware_plugins
```

Note: Some tests require hardware support and may be skipped if the required hardware is not available.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your plugin
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
