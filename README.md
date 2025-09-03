# CodeGreen - Energy Monitoring and Code Optimization Tool

CodeGreen is a comprehensive tool for monitoring energy consumption during code execution and providing optimization suggestions to reduce energy usage.

## Quick Start

### Installation

```bash
# Install from PyPI
pip install codegreen

# Or install from source
git clone https://github.com/codegreen/codegreen.git
cd codegreen
pip install -e .
```

### Basic Usage

```bash
# Initialize sensor configuration
codegreen init

# Measure energy consumption of a script
codegreen measure python my_script.py

# Get system information
codegreen info

# Diagnose installation issues
codegreen doctor
```

## Features

- **Energy Monitoring**: Real-time monitoring of CPU, GPU, and system energy consumption
- **Code Analysis**: Language-agnostic code analysis for energy optimization opportunities
- **IDE Integration**: Support for VSCode, IntelliJ, and other popular IDEs
- **Hardware Plugins**: Extensible plugin system for different hardware platforms
- **Visualization**: Charts and reports for energy consumption analysis
- **Code Instrumentation**: Automatic code instrumentation for energy profiling

## Project Structure

```
codegreen/
├── CMakeLists.txt              # Main CMake configuration
├── src/                        # Main application source
│   └── main.cpp               # Entry point
├── core/                       # Core library
│   ├── CMakeLists.txt         # Core library build config
│   ├── include/                # Public headers
│   │   ├── measurement_engine.hpp
│   │   ├── energy_monitor.hpp
│   │   ├── measurement_session.hpp
│   │   ├── measurement.hpp
│   │   ├── plugin/
│   │   │   ├── hardware_plugin.hpp
│   │   │   └── plugin_registry.hpp
│   │   └── adapters/
│   │       └── language_adapter.hpp
│   └── src/                    # Implementation files
│       ├── measurement_engine.cpp
│       ├── energy_monitor.cpp
│       ├── measurement_session.cpp
│       └── plugin/
│           └── plugin_registry.cpp
├── packages/                    # Feature packages
│   ├── ide/                    # IDE integration
│   ├── optimizer/              # Code optimization
│   ├── visualization/          # Data visualization
│   ├── instrumentation/        # Code instrumentation
│   ├── hardware-plugins/       # Hardware monitoring plugins
│   └── language-adapters/      # Language-specific adapters
└── scripts/                     # Build and utility scripts
    └── build.sh                # Build script
```

## Building

### Prerequisites

- CMake 3.16 or higher
- GCC 7.0 or higher (or compatible C++17 compiler)
- pkg-config
- libjsoncpp-dev
- libcurl4-openssl-dev

### Install Dependencies (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install cmake build-essential pkg-config libjsoncpp-dev libcurl4-openssl-dev
```

### Build

```bash
# Clone the repository
git clone <repository-url>
cd codegreen

# Build the project
./scripts/build.sh
```

The build script will:
1. Check for required dependencies
2. Configure the project with CMake
3. Build all components
4. Install the binary to `/usr/local/bin/codegreen`

### Manual Build

```bash
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
sudo make install
```

## Usage

After installation, you can use the `codegreen` command:

```bash
# Basic usage
codegreen

# Get help
codegreen --help
```

## Development

### Adding New Hardware Plugins

1. Create a new class inheriting from `HardwarePlugin`
2. Implement the required virtual methods
3. Register the plugin in the plugin registry

### Adding New Language Adapters

1. Create a new class inheriting from `LanguageAdapter`
2. Implement language-specific parsing and analysis
3. Register the adapter in the measurement engine

### Building Individual Components

```bash
# Build only the core library
cd core
mkdir build && cd build
cmake ..
make

# Build only a specific package
cd packages/ide
mkdir build && cd build
cmake ..
make
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Architecture

CodeGreen follows a modular architecture with clear separation of concerns:

- **Core Library**: Provides the foundation for energy measurement and plugin management
- **Hardware Plugins**: Abstract hardware-specific energy monitoring
- **Language Adapters**: Handle different programming languages for code analysis
- **IDE Integration**: Provides seamless integration with development environments
- **Optimization Engine**: Analyzes code and suggests energy-efficient alternatives
- **Visualization**: Presents energy data in meaningful charts and reports

The system is designed to be extensible, allowing new hardware platforms and programming languages to be easily added through the plugin system.
