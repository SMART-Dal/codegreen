# CodeGreen - Energy Monitoring and Code Optimization Tool

CodeGreen is a comprehensive tool for fine-grained energy profiling and optimization of code. It provides real-time energy measurement during code execution, identifies energy hotspots, and offers optimization suggestions to reduce energy consumption.

## 🚀 Quick Start

### Installation

#### Option 1: Development Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/codegreen-dev/codegreen.git
cd codegreen

# Install dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install cmake build-essential pkg-config libjsoncpp-dev libcurl4-openssl-dev libsqlite3-dev python3-dev

# Build the project
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build

# The binary is automatically copied to bin/ for CLI integration
```

#### Option 2: Python Package Installation

```bash
# Install from PyPI (coming soon)
pip install codegreen

# Or install development version
pip install -e .
```

### Basic Usage

```bash
# Initialize hardware sensors (first time setup)
python codegreen_cli.py --init-sensors

# Analyze energy consumption of a Python script
python codegreen_cli.py python examples/simple_test.py

# Analyze complex applications with detailed profiling
python codegreen_cli.py python examples/complex_python_test.py
```

## 📊 Features

### Energy Monitoring
- **Hardware-Level Measurement**: Uses Intel RAPL, NVIDIA NVML, and AMD ROCm for accurate energy readings
- **Fine-Grained Profiling**: Function-level and line-level energy consumption analysis
- **Real-Time Monitoring**: Live energy measurement during code execution
- **Multi-Platform Support**: Linux, Windows, and macOS (hardware dependent)

### Code Analysis
- **Language-Agnostic AST Analysis**: Currently supports Python with C/C++/Java coming soon
- **Automated Instrumentation**: Intelligently inserts energy measurement checkpoints
- **Syntax-Aware Processing**: Uses tree-sitter for robust code parsing
- **95+ Instrumentation Points**: Handles complex codebases with classes, functions, generators, async code

### Energy Optimization
- **Optimization Suggestions**: AI-powered recommendations for energy efficiency
- **Performance Profiling**: Identifies energy hotspots and bottlenecks
- **Database Storage**: SQLite-based storage for historical analysis and trends
- **Visualization Ready**: Structured data for charts and reports

## 🛠️ Commands

### Energy Profiling Commands

```bash
# Basic energy profiling
python codegreen_cli.py python <script.py>

# Profile script with command-line arguments  
python codegreen_cli.py python <script.py> arg1 arg2

# Currently supported languages:
python codegreen_cli.py python <file.py>    # Python 3.x ✅
# Coming soon:
# python codegreen_cli.py c <file.c>        # C language (in development)
# python codegreen_cli.py cpp <file.cpp>    # C++ language (in development)  
# python codegreen_cli.py java <file.java>  # Java language (in development)
```

### System Commands

```bash
# Initialize and test hardware sensors
python codegreen_cli.py --init-sensors

# Show help and available commands
python codegreen_cli.py --help

# Measure system workload (advanced)
python codegreen_cli.py --measure-workload --duration=10 --workload=cpu
```

## 📈 Sample Output

```
Configuration loaded from: "config/codegreen.json"
CodeGreen - Energy Monitoring Tool
Analyzing and instrumenting: examples/complex_python_test.py
Generating energy measurement checkpoints...
Phase 1: Code analysis and instrumentation...
✅ Found 95 instrumentation points
Phase 2: Clean execution with energy measurement...
🧪 Starting Complex Python CodeGreen Test
✅ Complex Python test completed!

=== Instrumentation Results ===
Checkpoints generated: 95
Energy measurement data collected.

=== Energy Optimization Suggestions ===
  • Consider using list comprehensions for better performance
  • Profile memory usage in loops  
  • Use context managers for resource management
```

## 🏗️ Architecture

CodeGreen uses a hybrid C++/Python architecture for optimal performance and flexibility:

- **C++ Core**: High-performance energy measurement using NEMB (Native Energy Measurement Backend)
- **Python AST Engine**: Language-agnostic code analysis and instrumentation  
- **Tree-sitter Integration**: Professional-grade code parsing for multiple languages
- **SQLite Database**: Persistent storage of fine-grained energy measurements
- **Bridge System**: Seamless integration between C++ binary and Python analysis

### Project Structure

```
codegreen/
├── bin/                        # Built executable
│   └── codegreen              # Main binary
├── src/
│   ├── measurement/           # C++ energy measurement core
│   │   ├── main.cpp          # CLI entry point
│   │   ├── src/              # Core implementation
│   │   └── include/          # Headers
│   ├── instrumentation/       # Python AST system  
│   │   ├── language_engine.py    # Multi-language analysis
│   │   ├── ast_processor.py      # AST processing
│   │   ├── language_configs.py   # Language definitions
│   │   ├── codegreen_runtime.py  # Runtime library
│   │   ├── bridge_analyze.py     # C++ bridge (analysis)
│   │   └── bridge_instrument.py  # C++ bridge (instrumentation)
├── config/
│   └── codegreen.json        # Configuration
├── examples/                  # Sample code for testing
├── tests/                    # Test suites
└── third_party/              # Dependencies (tree-sitter, etc.)
```

## 🔧 Requirements

### System Requirements
- **OS**: Linux (Ubuntu 20.04+, Debian 10+) - Primary platform
- **Hardware**: Intel/AMD CPU with RAPL support, optional NVIDIA GPU
- **Memory**: 512MB RAM minimum, 2GB recommended
- **Storage**: 100MB for installation, database grows with usage

### Software Dependencies
```bash
# Build tools
cmake (≥3.16)
gcc/g++ (≥7.0)
python3 (≥3.8)

# System libraries  
libjsoncpp-dev
libcurl4-openssl-dev
libsqlite3-dev
python3-dev

# Python packages (auto-installed)
tree-sitter-languages
sqlite3
```

## 🚀 Hardware Support

### Energy Sensors
- ✅ **Intel RAPL** - CPU package and core energy
- ✅ **AMD RAPL** - AMD CPU energy (via Intel interface)  
- ✅ **NVIDIA NVML** - GPU energy measurement
- 🔄 **AMD ROCm** - AMD GPU support (in development)
- 🔄 **ARM PMU** - ARM processor support (planned)

### Initialization Test
```bash
python codegreen_cli.py --init-sensors
# Output shows which sensors are available:
# ✅ Intel RAPL (active) 
# ❌ NVIDIA GPU provider failed to initialize
# ✓ System self-test passed
```

## 📊 Database Schema

Energy data is stored in SQLite with the following structure:

```sql
-- Fine-grained measurements
measurement_sessions (session_id, file_path, language, total_joules, ...)
measurements (checkpoint_id, joules, watts, timestamp, function_name, ...)
function_energy_stats (function_name, total_joules, avg_joules, call_count, ...)
energy_timeline (timestamp_bucket, avg_watts, max_watts, ...)
```

Database location: `~/.codegreen/energy_data.db`

## 🧪 Development & Testing

```bash
# Run instrumentation tests
python tests/instrumentation/test_instrumentation.py
python tests/instrumentation/test_ast_instrumentation.py

# Build development version
cmake --build build
./bin/codegreen --help

# Test with sample files
python codegreen_cli.py python examples/simple_test.py
python codegreen_cli.py python examples/complex_python_test.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Adding Language Support
1. Extend Python bridge adapter for new language
2. Add language configuration in `language_configs.py`
3. Create tree-sitter grammar integration
4. Test with sample code

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **GitHub**: https://github.com/codegreen-dev/codegreen
- **Documentation**: https://codegreen.readthedocs.io/ (coming soon)
- **PyPI Package**: https://pypi.org/project/codegreen/ (coming soon)
- **Issues**: https://github.com/codegreen-dev/codegreen/issues

---

**CodeGreen** - Making software development more energy-efficient, one line of code at a time. 🌱⚡