# CodeGreen Core

The **CodeGreen Core** is the central orchestration layer of the CodeGreen system. It provides the foundation for energy measurement and analysis across multiple programming languages and hardware architectures.

## Architecture

The core module:
- Orchestrates hardware plugins and language adapters
- Manages measurement sessions and data collection
- Provides a unified interface for energy analysis
- Handles error management and system state

## Components

### Measurement Engine
- Coordinates energy measurements across hardware
- Manages measurement sessions
- Handles data aggregation and validation

### Plugin System
- Integrates with hardware-specific plugins
- Provides plugin lifecycle management
- Ensures consistent measurement interfaces

### Language Adapters
- Integrates with language-specific analyzers
- Provides code analysis capabilities
- Enables energy-aware code optimization

## Building

```bash
# From the project root
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make codegreen-core
```

## Testing

```bash
# Run core tests
ctest -R core
```

## Usage

```cpp
#include "core/measurement_engine.hpp"
#include "core/energy_monitor.hpp"

auto engine = std::make_unique<codegreen::MeasurementEngine>();
auto monitor = std::make_unique<codegreen::EnergyMonitor>();

// Start measurements
auto session = monitor->start_measurement();

// Analyze code
engine->analyze_code(source_code, "cpp");

// Stop measurements
auto final_session = monitor->stop_measurement(std::move(session));
```

## Integration

The core module integrates with:
- Hardware plugins for energy measurement
- Language adapters for code analysis
- Storage systems for data persistence
- Visualization tools for data presentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your core features
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details
