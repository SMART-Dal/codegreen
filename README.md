# CodeGreen - Energy Monitoring and Code Optimization Tool

CodeGreen is a comprehensive tool for fine-grained energy profiling and optimization of code. It provides real-time energy measurement during code execution, identifies energy hotspots, and offers optimization suggestions to reduce energy consumption.

## 🚀 Quick Start

### Installation

#### Easy Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/codegreen-dev/codegreen.git
cd codegreen

# Install dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install cmake build-essential pkg-config libjsoncpp-dev libcurl4-openssl-dev libsqlite3-dev python3-dev

# One-command installation and testing
./install.sh

# The install script will:
# - Build the C++ binary
# - Install the Python CLI package
# - Run comprehensive validation tests
# - Set up energy sensor permissions (if needed)
```

#### Manual Installation

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Build the project
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Install Python CLI package
cd ..
pip3 install -e .

# Add CLI to PATH (if needed)
export PATH="$HOME/.local/bin:$PATH"
```

### Verify Installation

```bash
# Check CLI is available
codegreen --help

# Run system initialization and sensor detection
codegreen init --interactive

# Test with a quick benchmark
codegreen benchmark cpu_stress --duration 5
```

### Basic Usage

```bash
# Measure energy consumption of a Python script
codegreen measure python examples/simple_test.py

# Analyze code structure without running
codegreen analyze python examples/complex_python_test.py

# Get detailed analysis with optimization suggestions
codegreen analyze python script.py --verbose --suggestions

# Run comprehensive system information
codegreen info --detailed
```

## 📊 Features

### Energy Monitoring
- **Hardware-Level Measurement**: Uses Intel RAPL, NVIDIA NVML, and AMD ROCm for accurate energy readings
- **Fine-Grained Profiling**: Function-level and line-level energy consumption analysis
- **Real-Time Monitoring**: Live energy measurement during code execution
- **Multi-Platform Support**: Linux (primary), with Windows/macOS support planned

### Code Analysis
- **Language-Agnostic AST Analysis**: Currently supports Python with C/C++/Java coming soon
- **Automated Instrumentation**: Intelligently inserts energy measurement checkpoints
- **Syntax-Aware Processing**: Uses tree-sitter for robust code parsing
- **95+ Instrumentation Points**: Handles complex codebases with classes, functions, generators, async code

### Professional CLI Interface
- **Typer-based CLI**: Rich, user-friendly command-line interface with auto-completion
- **Comprehensive Commands**: Measure, analyze, benchmark, configure, and diagnose
- **Rich Output**: Beautiful terminal output with tables, progress bars, and colored text
- **Smart Error Handling**: Helpful error messages and suggestions

## 🛠️ CLI Commands

### Core Commands

```bash
# Energy measurement with detailed analysis
codegreen measure python script.py                    # Basic measurement
codegreen measure python script.py --sensors rapl     # Specific sensors
codegreen measure python script.py --precision high   # High precision mode
codegreen measure python script.py --verbose          # Detailed output

# Code analysis (no execution)
codegreen analyze python script.py                    # Quick analysis
codegreen analyze python script.py --verbose          # Show instrumentation points
codegreen analyze python script.py --output report.json  # Save results
```

### System Management

```bash
# System initialization and setup
codegreen init                          # Interactive setup with sensor detection
codegreen init --auto-detect-only       # Quick auto-detection
codegreen init --setup-permissions      # Auto-fix energy sensor permissions

# System information and diagnostics
codegreen info                          # Basic system information
codegreen info --detailed              # Comprehensive system details
codegreen doctor                        # Diagnose installation issues
codegreen doctor --test-sensors        # Test sensor functionality
```

### Benchmarking and Validation

```bash
# Built-in benchmarks for testing energy measurement
codegreen benchmark cpu_stress --duration 10          # CPU stress test
codegreen benchmark memory_stress --duration 5        # Memory stress test
codegreen benchmark mixed --output results.json       # Mixed workload

# Accuracy validation (requires root for hardware access)
sudo codegreen validate                                # Compare with native tools
sudo codegreen validate --reference rapl --tolerance 3.0
```

### Configuration Management

```bash
# Configuration management
codegreen config --show                # Show current configuration
codegreen config --edit                # Edit configuration file
codegreen config --reset               # Reset to defaults
```

## 📈 Sample Output

### Measurement Example
```
🌱 Running CodeGreen on fibonacci.py
Language: python

✓ Analysis completed!
Analysis method: tree_sitter_ast
Instrumentation points found: 12
Analysis time: 45.32ms

🔧 Instrumenting code for energy measurement...
✓ Instrumented code saved to: fibonacci_instrumented.py

🏃 Running energy measurement...
✓ Energy measurement completed!

📊 Recent benchmark: 125.7J consumed, 42.3W average power

💡 Optimization Suggestions:
  1. Consider using iterative approach instead of recursion
  2. Profile memory usage in recursive functions
  3. Use memoization for repeated calculations
```

### System Information Example
```
🌱 CodeGreen Installation Information

Installation Status
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component    │ Status      │ Details                            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Binary       │ ✓ Found     │ /home/user/codegreen/bin/codegreen │
│ Config       │ ✓ Found     │ /home/user/codegreen/config/...    │
│ Runtime      │ ✓ Available │ Python runtime modules found       │
│ Platform     │ ✓           │ Linux x86_64                       │
│ Python       │ ✓           │ 3.10.12                           │
└──────────────┴─────────────┴────────────────────────────────────┘
```

## 🏗️ Architecture

CodeGreen uses a hybrid C++/Python architecture for optimal performance and flexibility:

- **C++ Core**: High-performance energy measurement using NEMB (Native Energy Measurement Backend)
- **Python AST Engine**: Language-agnostic code analysis and instrumentation using tree-sitter
- **Typer CLI**: Professional command-line interface with rich formatting and auto-completion
- **SQLite Database**: Persistent storage of fine-grained energy measurements
- **Bridge System**: Seamless integration between C++ binary and Python analysis

### Project Structure

```
codegreen/
├── src/
│   ├── cli/                       # Typer-based CLI interface
│   │   └── cli.py                # Main CLI commands and interface
│   ├── instrumentation/           # Python AST analysis system
│   │   ├── language_engine.py    # Language analysis engine (Python)
│   │   ├── ast_processor.py      # AST processing and instrumentation
│   │   ├── language_configs.py   # Language definitions and patterns
│   │   ├── codegreen_runtime.py  # Runtime library for instrumented code
│   │   ├── bridge_analyze.py     # C++ bridge for analysis
│   │   └── bridge_instrument.py  # C++ bridge for instrumentation
│   ├── collector/                # C++ energy measurement core
│   │   └── main.cpp              # CLI entry point and measurement logic
│   └── database/                 # Database management
├── bin/                          # Built executable (development)
│   └── codegreen                # Main binary
├── build/                        # CMake build output
│   └── bin/codegreen            # Compiled binary
├── config/
│   └── codegreen.json           # Configuration file
├── examples/                     # Sample code for testing
├── third_party/                  # Dependencies (tree-sitter parsers)
└── install.sh                   # One-command installation script
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

# Python packages (auto-installed by install.sh)
typer[all] (≥0.17.0)     # CLI framework
rich (≥12.0.0)           # Terminal formatting
tree-sitter-languages    # Code parsing
psutil (≥5.9.0)         # System information
pydantic (≥1.10.0)      # Data validation
```

## 🚀 Hardware Support

### Energy Sensors
- ✅ **Intel RAPL** - CPU package and core energy
- ✅ **AMD RAPL** - AMD CPU energy (via Intel interface)
- ✅ **NVIDIA NVML** - GPU energy measurement
- 🔄 **AMD ROCm** - AMD GPU support (in development)
- 🔄 **ARM PMU** - ARM processor support (planned)

### Sensor Detection
```bash
# Comprehensive sensor detection and setup
codegreen init --interactive

# Example output:
# Environment Information
# ┌─────────────────────┬─────────────────────────┐
# │ Environment Type    │ personal                │
# │ Platform            │ linux                   │
# │ Deployment Mode     │ development             │
# └─────────────────────┴─────────────────────────┘
#
# Hardware Sensors
# ┌─────────────┬─────────────┬───────────────────────────────┐
# │ Sensor      │ Status      │ Details                       │
# ├─────────────┼─────────────┼───────────────────────────────┤
# │ intel_rapl  │ ✅ Available │ Intel RAPL accessible         │
# │ nvidia_gpu  │ ❌ Unavailable │ No NVIDIA GPUs detected      │
# │ amd_gpu     │ ❌ Unavailable │ Not detected                  │
# └─────────────┴─────────────┴───────────────────────────────┘
```

## 📊 Database Schema

Energy data is stored in SQLite with the following structure:

```sql
-- Fine-grained measurements
CREATE TABLE measurement_sessions (
    session_id TEXT PRIMARY KEY,
    file_path TEXT,
    language TEXT,
    total_joules REAL,
    duration_seconds REAL,
    timestamp DATETIME
);

CREATE TABLE measurements (
    checkpoint_id TEXT,
    session_id TEXT,
    joules REAL,
    watts REAL,
    timestamp DATETIME,
    function_name TEXT,
    line_number INTEGER
);

CREATE TABLE function_energy_stats (
    function_name TEXT,
    total_joules REAL,
    avg_joules REAL,
    call_count INTEGER,
    file_path TEXT
);
```

Database location: `./measurements.db` (created in project directory)

## 🧪 Development & Testing

### Testing Installation
```bash
# The install.sh script runs comprehensive tests:
./install.sh

# Tests include:
# 1️⃣ CLI help functionality
# 2️⃣ C++ binary accessibility  
# 3️⃣ Typer CLI initialization
# 4️⃣ CPU stress benchmark with energy measurement
# 5️⃣ Energy measurement permissions
# 6️⃣ Tree-sitter language support
# 7️⃣ Code instrumentation via Typer CLI
```

### Manual Testing
```bash
# Test individual components
python3 -c "from src.cli.cli import main_cli; print('✅ CLI imports successfully')"

# Test with sample files
codegreen analyze python examples/simple_test.py
codegreen measure python examples/complex_python_test.py

# Run diagnostics
codegreen doctor --test-sensors
```

### Adding New Commands
```bash
# The CLI is built with Typer - add new commands in src/cli/cli.py
@app.command()
def your_command():
    """Your command description."""
    # Implementation here
```

## 📦 Distribution

### For End Users
```bash
# Simple installation
git clone <repository>
cd codegreen
./install.sh

# CLI will be available as 'codegreen' command
# Add to PATH if needed: export PATH="$HOME/.local/bin:$PATH"
```

### For Developers
```bash
# Development installation
pip3 install -e .  # Editable installation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test with `./install.sh`
5. Submit a pull request

### Adding Language Support
1. Add language configuration in `src/instrumentation/language_configs.py`
2. Create tree-sitter grammar integration in `third_party/`
3. Add language enum to `src/cli/cli.py`
4. Test with sample code using `codegreen analyze <language> <file>`

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **GitHub**: https://github.com/codegreen-dev/codegreen
- **Documentation**: https://codegreen.readthedocs.io/ (coming soon)
- **PyPI Package**: https://pypi.org/project/codegreen/ (coming soon)
- **Issues**: https://github.com/codegreen-dev/codegreen/issues

---

**CodeGreen** - Making software development more energy-efficient, one line of code at a time. 🌱⚡