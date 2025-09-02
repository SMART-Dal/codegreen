# CodeGreen Usage Guide

A comprehensive guide to building, installing, configuring, and using CodeGreen for energy-aware software development.

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Installation Methods](#installation-methods)
4. [Configuration](#configuration)
5. [Quick Start](#quick-start)
6. [Usage Examples](#usage-examples)
7. [Hardware Sensor Support](#hardware-sensor-support)
8. [Data Visualization](#data-visualization)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Features](#advanced-features)
11. [Quick Reference](#quick-reference)

## 🎯 Overview

CodeGreen is an energy-aware software development tool that monitors and analyzes energy consumption during code execution. It integrates with the Power Measurement Toolkit (PMT) to provide real-time energy measurements and optimization suggestions.

### Key Features

- **Real-time Energy Monitoring**: Track CPU, GPU, and system power consumption
- **Automatic Hardware Detection**: Automatically detects available power sensors
- **Code Optimization Suggestions**: Identifies energy-intensive code patterns
- **Multiple Output Formats**: SQLite, CSV, Grafana dashboards
- **Cross-platform Support**: Linux, macOS, Windows (with limitations)

## 💻 System Requirements

### Minimum Requirements

- **OS**: Linux (recommended), macOS, Windows 10/11
- **CPU**: x86_64 or ARM64 processor
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Python**: 3.7+ (for examples and configuration)

### Recommended Requirements

- **OS**: Ubuntu 20.04+, CentOS 8+, or similar modern Linux distribution
- **CPU**: Multi-core processor with RAPL support (Intel/AMD)
- **GPU**: NVIDIA GPU with CUDA support, or AMD GPU with ROCm
- **RAM**: 16GB+
- **Storage**: SSD with 10GB+ free space

### Hardware Sensor Support

| Sensor | Requirements | Linux | macOS | Windows |
|--------|--------------|-------|-------|---------|
| **RAPL** | Intel/AMD CPU | ✅ | ✅ | ✅ |
| **NVML** | NVIDIA GPU + CUDA | ✅ | ✅ | ❌ |
| **AMD SMI** | AMD GPU + AMD SMI lib | ✅ | ❌ | ❌ |
| **PowerSensor** | USB device | ✅ | ✅ | ✅ |
| **LIKWID** | LIKWID library | ✅ | ❌ | ❌ |
| **ROCm** | AMD GPU + ROCm | ✅ | ❌ | ❌ |

## 🚀 Installation Methods

### Prerequisites

#### System Requirements
- **OS**: Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+), macOS, Windows 10/11
- **Architecture**: x86_64 or ARM64
- **RAM**: 2GB minimum, 8GB recommended
- **Storage**: 1GB minimum, 10GB+ recommended
- **Python**: 3.7+ (for examples and configuration)

#### Required Software
- **CMake**: 3.16 or higher
- **Compiler**: GCC 7.0+ or compatible C++17 compiler
- **Build Tools**: Make, pkg-config, Git
- **Python**: 3.7+ with pip

#### Required Libraries
- **Development**: libjsoncpp-dev, libcurl4-openssl-dev
- **System**: libsqlite3-dev, libboost-all-dev
- **Optional**: NVIDIA CUDA toolkit, AMD ROCm, LIKWID

### Method 1: Quick Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/codegreen.git
cd codegreen

# Run the automated installer
chmod +x install.sh
./install.sh
```

The automated installer will:
- Check all dependencies
- Install missing system packages
- Configure the project with CMake
- Build all components
- Install the binary to `/usr/local/bin/codegreen`

### Method 2: Python Package Install

```bash
# Install via pip (if available)
pip install codegreen

# Or install from source
git clone https://github.com/yourusername/codegreen.git
cd codegreen
pip install -e .
```

### Method 3: Manual Build

#### Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libjsoncpp-dev \
    libcurl4-openssl-dev \
    libsqlite3-dev \
    libboost-all-dev \
    git \
    python3 \
    python3-pip
```

**CentOS/RHEL:**
```bash
sudo yum groupinstall -y "Development Tools"
sudo yum install -y \
    cmake3 \
    pkgconfig \
    jsoncpp-devel \
    libcurl-devel \
    sqlite-devel \
    boost-devel \
    git \
    python3 \
    python3-pip
```

**Arch Linux:**
```bash
sudo pacman -S \
    base-devel \
    cmake \
    pkg-config \
    jsoncpp \
    curl \
    sqlite \
    boost \
    git \
    python \
    python-pip
```

**macOS:**
```bash
brew install cmake git python3 boost sqlite3 pkg-config
```

#### Build Steps

```bash
# 1. Clone and initialize
git clone https://github.com/yourusername/codegreen.git
cd codegreen
git submodule update --init --recursive

# 2. Create build directory
mkdir build && cd build

# 3. Configure with CMake
cmake .. -DCMAKE_BUILD_TYPE=Release

# 4. Build
make -j$(nproc)  # Linux/macOS
# or
make -j$(sysctl -n hw.ncpu)  # macOS

# 5. Install (optional)
sudo make install
```

#### Build Options

```bash
# Custom build configuration
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCODEGREEN_ENABLE_TESTS=ON \
  -DCODEGREEN_ENABLE_DOCS=ON \
  -DCMAKE_INSTALL_PREFIX=/usr/local

# Debug build
cmake .. -DCMAKE_BUILD_TYPE=Debug

# User installation (no sudo required)
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local

# Clean build
make clean
rm -rf build && mkdir build
```

### Method 4: Development Installation

For development work, install in development mode:

```bash
# Clone and setup
git clone https://github.com/yourusername/codegreen.git
cd codegreen
git submodule update --init --recursive

# Create development build
mkdir build-debug
cd build-debug
cmake .. -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$HOME/.local
make -j$(nproc)
make install

# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Post-Installation Setup

#### 1. Add to PATH (if not already added)
The binary is installed to `/usr/local/bin/` which should already be in your PATH. If not, add it:

```bash
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### 2. Create Configuration Directory
```bash
mkdir -p ~/.config/codegreen
```

#### 3. Set Up Hardware Monitoring (Optional)
Some hardware monitoring features may require additional setup:

```bash
# For Intel RAPL (if supported)
sudo modprobe msr

# For GPU monitoring (NVIDIA)
sudo nvidia-smi

# For ARM energy counters
# May require kernel configuration
```

#### 4. Verify Installation
```bash
# Check if codegreen is available
which codegreen

# Check version
codegreen --version

# Test basic functionality
codegreen --help
```

### Installation Troubleshooting

#### Common Issues

**CMake Not Found:**
```bash
# Ubuntu/Debian
sudo apt-get install cmake

# CentOS/RHEL
sudo yum install cmake3

# macOS
brew install cmake
```

**Compiler Not Found:**
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"

# macOS
xcode-select --install
```

**Missing Libraries:**
```bash
# Check what's missing
pkg-config --exists jsoncpp || echo "jsoncpp missing"
pkg-config --exists libcurl || echo "libcurl missing"

# Install missing libraries
sudo apt-get install libjsoncpp-dev libcurl4-openssl-dev
```

**Permission Denied During Install:**
```bash
# Make sure you have sudo privileges
sudo -v

# Or install to user directory
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local
make install
```

#### Build Errors

**C++17 Not Supported:**
Update your compiler:
```bash
# Ubuntu/Debian
sudo apt-get install g++-8

# Use specific compiler
cmake .. -DCMAKE_CXX_COMPILER=g++-8
```

**Memory Issues During Build:**
Reduce parallel jobs:
```bash
make -j2  # Use 2 jobs instead of all cores
```

**Missing Dependencies:**
```bash
# Install missing packages
sudo apt install libboost-all-dev libsqlite3-dev

# Clean rebuild
make clean && cmake .. && make -j$(nproc)
```

### Uninstallation

To remove CodeGreen:

```bash
# Remove binary
sudo rm -f /usr/local/bin/codegreen

# Remove libraries
sudo rm -rf /usr/local/lib/libcodegreen*

# Remove headers
sudo rm -rf /usr/local/include/codegreen

# Remove configuration (optional)
rm -rf ~/.config/codegreen
```

## ⚙️ Configuration

### Configuration File

CodeGreen uses a JSON-based configuration file (`config/codegreen.json`) for comprehensive system settings. The configuration supports environment variable substitution for flexible deployment:

```json
{
  "version": "0.1.0",
  "measurement": {
    "pmt": {
      "preferred_sensors": ["rapl", "nvml", "dummy"],
      "fallback_enabled": true,
      "validation_enabled": true,
      "measurement_interval_ms": 1
    }
  },
  "paths": {
    "database": {
      "default_path": "${USER_HOME}/.codegreen/energy_data.db"
    },
    "temp_directory": {
      "base": "${SYSTEM_TEMP}",
      "prefix": "codegreen_",
      "cleanup_on_exit": true
    }
  },
  "security": {
    "sql_injection_protection": true,
    "path_validation": true
  }
}
```

### Environment Variables

CodeGreen supports several environment variables for runtime configuration:

```bash
# Set configuration file location
export CODEGREEN_CONFIG=/path/to/codegreen.json

# Enable debug mode
export CODEGREEN_DEBUG=1

# Set output directory
export CODEGREEN_OUTPUT_DIR=/path/to/output

# Environment variables used in config substitution:
export EXECUTABLE_DIR=/usr/local/bin/codegreen
export USER_HOME=/home/username
export SYSTEM_TEMP=/tmp
```

## 🚀 Quick Start

### Get Up and Running in 5 Minutes

**Prerequisites Check**:
```bash
# Verify system requirements
which cmake gcc python3
pkg-config --exists jsoncpp sqlite3 libcurl
```

```bash
# 1. Clone and build
git clone https://github.com/yourusername/codegreen.git
cd codegreen
git submodule update --init --recursive
mkdir build && cd build
cmake .. && make -j$(nproc)

# 2. Run sample program
cd ..
python3 examples/sample_python.py

# 3. Check available sensors
./build/src/codegreen sensors --list

# 4. Run sample measurement
./build/bin/codegreen python examples/simple_test.py

# 5. Check measurement results
ls ~/.codegreen/
sqlite3 ~/.codegreen/energy_data.db "SELECT * FROM measurement_sessions LIMIT 5;"
```

### First-Time Setup Checklist

- [ ] Clone repository and initialize submodules
- [ ] Install system dependencies (build tools, libraries)
- [ ] Build CodeGreen from source
- [ ] Verify hardware detection works
- [ ] Test with sample program
- [ ] Configure output directory and settings

## 📖 Usage Examples

### Basic Usage

```bash
# Run the main CodeGreen application
./build/src/codegreen

# Run with specific configuration
./build/src/codegreen --config config/codegreen.conf

# Run in verbose mode
./build/src/codegreen --verbose
```

### Python Examples

```bash
# Run the sample Python program
cd examples
python3 sample_python.py

# Run with energy monitoring
python3 -m codegreen.monitor sample_python.py
```

### C++ Examples

```bash
# Build and run C++ examples
cd build/examples
make
./cpp_example
```

### Command Line Interface

```bash
# Monitor a specific process
codegreen monitor --pid 1234

# Monitor a command
codegreen monitor --command "python3 script.py"

# Export data
codegreen export --format csv --output energy_report.csv

# Generate dashboard
codegreen dashboard --generate
```

## 🔌 Hardware Sensor Support

### Automatic Detection

CodeGreen automatically detects available hardware:

```bash
# Check detected sensors
codegreen sensors --list

# Test specific sensor
codegreen sensors --test rapl
codegreen sensors --test nvml

# Force enable/disable
codegreen sensors --enable rapl,nvml
codegreen sensors --disable powersensor2,powersensor3
```

### Manual Configuration

```bash
# Force enable specific sensors
codegreen sensors --enable rapl,nvml

# Disable problematic sensors
codegreen sensors --disable powersensor2,powersensor3
```

### Sensor-Specific Setup

#### RAPL (Intel/AMD Power Monitoring)

```bash
# Usually works out of the box on Linux
# Check if available
ls /sys/class/powercap/

# Enable if needed
sudo modprobe intel_rapl

# Check permissions
sudo chmod 666 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
```

#### NVML (NVIDIA GPU)

```bash
# Install NVIDIA drivers
sudo apt install nvidia-driver-xxx

# Install CUDA toolkit (optional, for advanced features)
sudo apt install nvidia-cuda-toolkit

# Test GPU detection
nvidia-smi
```

#### AMD SMI

```bash
# Install AMD SMI library
sudo apt install rocm-smi

# Or build from source
git clone https://github.com/ROCm-Developer-Tools/rocm_smi_lib
cd rocm_smi_lib
mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install
```

#### PowerSensor (External USB)

```bash
# Check USB devices
lsusb | grep -i powersensor

# Set permissions
sudo chmod 666 /dev/ttyUSB0

# Test connection
codegreen sensors --test powersensor3
```

#### LIKWID (Performance Monitoring)

```bash
# Check if available
likwid-topology

# Install if needed
sudo apt install likwid
# or build from source
git clone https://github.com/RRZE-HPC/likwid
cd likwid
make -j$(nproc)
sudo make install
```

## 📊 Data Visualization

### Automatic Plot Generation

```bash
# Enable automatic plots in config
auto_generate_plots = true

# Plots are saved to energy_plots/ directory
ls energy_plots/
```

### Grafana Dashboard

```bash
# Start Grafana (if available)
docker run -d -p 3000:3000 grafana/grafana

# Import dashboard
codegreen dashboard --grafana --url http://localhost:3000
```

### Custom Analysis

```python
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

# Load energy data
conn = sqlite3.connect('energy_data.db')
df = pd.read_sql_query("SELECT * FROM measurements", conn)

# Create custom plots
plt.figure(figsize=(12, 8))
plt.plot(df['timestamp'], df['power_watts'])
plt.title('Power Consumption Over Time')
plt.xlabel('Time')
plt.ylabel('Power (Watts)')
plt.savefig('custom_plot.png')
```

## 🛠️ Troubleshooting

### Common Issues

#### Build Failures

```bash
# Missing dependencies
sudo apt install build-essential cmake libboost-all-dev libsqlite3-dev

# Clean rebuild
make clean && cmake .. && make -j$(nproc)

# Check dependencies
cmake .. --debug-output
```

#### Sensor Detection Issues

```bash
# Check hardware detection
codegreen sensors --verbose

# Test individual sensors
codegreen sensors --test rapl
codegreen sensors --test nvml

# Check system permissions
sudo chmod 666 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
```

#### Runtime Errors

```bash
# Enable debug mode
export CODEGREEN_DEBUG=1

# Check logs
tail -f /var/log/codegreen.log

# Verify configuration
codegreen --validate-config
```

### Debug Mode

```bash
# Enable debug output
export CODEGREEN_DEBUG=1
export CODEGREEN_LOG_LEVEL=DEBUG

# Run with debug flags
codegreen --debug --verbose

# Verbose sensor detection
codegreen sensors --verbose

# Debug build
cmake .. --debug-output
```

### Performance Issues

```bash
# Reduce measurement frequency
# In codegreen.conf:
measurement_interval = 5000  # 5 seconds instead of 1 second

# Limit data retention
max_sessions = 100  # Keep only last 100 sessions
```

## 🚀 Advanced Features

### Custom Sensors

```cpp
// Create custom PMT sensor
#include <pmt/Sensor.h>

class CustomSensor : public pmt::Sensor {
public:
    CustomSensor() : pmt::Sensor("custom") {}
    
    pmt::State Read() override {
        // Custom measurement logic
        return pmt::State();
    }
};
```

### Integration with CI/CD

```yaml
# GitHub Actions example
name: Energy Testing
on: [push, pull_request]

jobs:
  energy-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build CodeGreen
        run: |
          mkdir build && cd build
          cmake .. && make -j$(nproc)
      - name: Run Energy Tests
        run: |
          ./build/src/codegreen --test
```

### API Usage

```python
from codegreen import CodeGreen

# Initialize CodeGreen
cg = CodeGreen()

# Start monitoring
cg.start_monitoring()

# Run your code
result = your_function()

# Stop monitoring
cg.stop_monitoring()

# Get energy report
report = cg.get_report()
print(f"Total energy: {report.total_energy} J")
print(f"Peak power: {report.peak_power} W")
```

### Custom Metrics

```python
# Define custom energy metrics
class CustomMetrics:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.energy_consumed = 0
    
    def start(self):
        self.start_time = time.time()
    
    def stop(self):
        self.end_time = time.time()
        # Calculate energy based on your logic
        self.energy_consumed = self.calculate_energy()
    
    def calculate_energy(self):
        # Custom energy calculation
        return 42.0  # Joules
```

## 📋 Quick Reference

### Essential Commands

```bash
# Building
make clean                    # Clean build directory
cmake ..                     # Configure with CMake
make -j$(nproc)             # Build with all cores

# Basic Usage
codegreen python script.py               # Measure Python script
codegreen --config custom.json python script.py  # Custom config
codegreen --sensors rapl,nvml python script.py   # Specific sensors

# Advanced Options
codegreen --debug --verbose python script.py     # Debug mode
codegreen --output results.json python script.py # Custom output

# Hardware Detection (via PMT integration)
# Available sensors shown in measurement output
# Manual sensor testing done through C++ PMT API
```

### Configuration Quick Settings

```json
# Key settings in config/codegreen.json
{
  "measurement": {
    "pmt": {
      "preferred_sensors": ["rapl", "nvml", "dummy"],
      "fallback_enabled": true,
      "validation_enabled": true
    },
    "timing": {
      "precision": "high",
      "sync_method": "perf_counter"
    }
  },
  "paths": {
    "database": {
      "default_path": "${USER_HOME}/.codegreen/energy_data.db"
    }
  },
  "developer": {
    "debug_mode": false,
    "verbose_logging": false
  }
}
```

### Environment Variables

```bash
export CODEGREEN_CONFIG=/path/to/config.json
export CODEGREEN_DEBUG=1
export CODEGREEN_OUTPUT_DIR=/path/to/output

# Configuration substitution variables
export EXECUTABLE_DIR=/usr/local/bin
export USER_HOME=/home/username
export SYSTEM_TEMP=/tmp
```

### Hardware Support Status

| Sensor | Status | Command to Test |
|--------|--------|-----------------|
| **RAPL** | ✅ Usually works | `ls /sys/class/powercap/` |
| **NVML** | ✅ If NVIDIA GPU | `nvidia-smi` |
| **AMD SMI** | ⚠️ If AMD GPU + lib | `rocm-smi` |
| **PowerSensor** | ❌ USB device needed | `lsusb \| grep powersensor` |
| **LIKWID** | ❌ Library needed | `likwid-topology` |

### Output Files Structure

```
codegreen/
├── energy_data.db          # SQLite database
├── energy_plots/           # Generated plots
│   ├── power_over_time.png
│   └── energy_summary.png
├── config/
│   └── codegreen.conf      # Configuration
└── logs/                   # Log files
```

### Integration Examples

#### Python Integration
```python
from codegreen import CodeGreen

cg = CodeGreen()
cg.start_monitoring()

# Your code here
result = your_function()

cg.stop_monitoring()
report = cg.get_report()
print(f"Energy: {report.total_energy} J")
```

#### C++ Integration
```cpp
#include <codegreen/codegreen.hpp>

int main() {
    CodeGreen cg;
    cg.start_monitoring();
    
    // Your code here
    
    cg.stop_monitoring();
    auto report = cg.get_report();
    std::cout << "Energy: " << report.total_energy << " J\n";
    return 0;
}
```

#### Command Line Integration
```bash
# Monitor Python script
codegreen monitor --command "python3 my_script.py" --output my_report.json

# Monitor specific time
codegreen monitor --duration 60 --interval 1000

# Export specific data
codegreen export --sensor rapl --format csv --output rapl_data.csv
```

### Debug Commands

```bash
# Verbose sensor detection
codegreen sensors --verbose

# Debug build
cmake .. --debug-output

# Check configuration
codegreen --validate-config

# Monitor with debug
codegreen monitor --debug --verbose
```

## 📚 Additional Resources

### Documentation

- [API Reference](docs/API.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

### Examples

- [Basic Examples](examples/)
- [Advanced Examples](examples/advanced/)
- [Integration Examples](examples/integration/)

### Support

- [GitHub Issues](https://github.com/yourusername/codegreen/issues)
- [Discussions](https://github.com/yourusername/codegreen/discussions)
- [Wiki](https://github.com/yourusername/codegreen/wiki)

## 🔄 Version History

- **v1.0.0**: Initial release with basic energy monitoring
- **v1.1.0**: Added automatic hardware detection
- **v1.2.0**: Enhanced visualization and dashboard support
- **v1.3.0**: Improved sensor support and performance

---

**Note**: This guide is for CodeGreen version 1.3.0+. For older versions, please refer to the appropriate documentation or upgrade to the latest version.

**Need Help?** Check the troubleshooting section above or open an issue on GitHub.
