# CodeGreen Quick Start Guide

Get started with CodeGreen energy profiling in minutes.

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+), macOS 10.15+
- **Python**: 3.8 or higher
- **C++ Compiler**: GCC 9+ or Clang 10+
- **CMake**: 3.16 or higher

### Hardware Requirements
- **Intel/AMD CPU** with RAPL support (for CPU energy measurement)
- **NVIDIA GPU** with NVML support (optional, for GPU energy measurement)
- **AMD GPU** with ROCm support (optional, for AMD GPU energy measurement)

## Installation

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install build-essential cmake pkg-config python3 python3-pip
```

**macOS:**
```bash
brew install cmake pkg-config python@3.11
```

### 2. Clone and Install CodeGreen

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh
```

The installer will:
- Install Python dependencies
- Build C++ NEMB backend
- Create the `codegreen` CLI command

### 3. Add CodeGreen to PATH

**Linux:**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**macOS:**
```bash
echo 'export PATH="$HOME/Library/Python/3.11/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 4. Initialize Energy Sensors (One-time Setup)

```bash
sudo codegreen init-sensors
```

Then log out and log back in for group permissions to take effect.

### 5. Verify Installation

```bash
codegreen --version
codegreen info
```

You should see CodeGreen version and available energy sensors.

## Basic Usage

### Measure Energy Consumption of a Python Script

```bash
codegreen measure python fibonacci.py
```

### Measure with High Precision

```bash
codegreen measure python app.py --precision high
```

### Save Results to JSON

```bash
codegreen measure python script.py --output results.json
```

### Specify Sensors

```bash
codegreen measure python ml_train.py --sensors rapl nvidia
```

## Quick Example

Create a sample Python script:

```bash
cat > test.py << 'EOF'
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def iterative_fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print(f"Recursive: {fibonacci(30)}")
print(f"Iterative: {iterative_fib(30)}")
EOF
```

Measure its energy consumption:

```bash
codegreen measure python test.py
```

You'll see:
- Function-level energy breakdown
- Total energy consumed
- Average power draw
- Invocation counts

## Language Support

CodeGreen supports multiple languages:

```bash
# Python
codegreen measure python script.py

# C++
codegreen measure cpp program.cpp

# C
codegreen measure c program.c

# Java
codegreen measure java Program.java
```

## Common Commands

### System Information
```bash
codegreen info                    # Show system and sensor info
codegreen doctor                  # Diagnose issues
```

### Benchmarking
```bash
codegreen run --repeat 3 -- python3 -c 'sum(range(10**7))'    # CPU stress test
codegreen benchmark io_intensive  # I/O benchmark
```

### Analysis Only (No Measurement)
```bash
codegreen analyze python script.py
```

## Project Structure

After installation, your CodeGreen directory looks like:

```
codegreen/
├── bin/                          # Built binaries (gitignored)
│   └── codegreen                 # C++ NEMB binary
├── lib/                          # Compiled libraries (gitignored)
│   └── libcodegreen-nemb.so      # NEMB library
├── src/
│   ├── cli/                      # CLI commands
│   ├── instrumentation/          # Tree-sitter based analysis
│   └── measurement/              # C++ NEMB backend
├── config/
│   └── codegreen.json            # Default configuration
├── docs/                         # Documentation
└── install.sh                    # Installation script
```

## Configuration

Default configuration is at `config/codegreen.json`. You can override with:

```bash
codegreen --config custom.json measure python script.py
```

Configuration options:
- Sampling interval (default: 10ms, high-accuracy: 1ms)
- Energy providers to enable/disable
- Output formats
- Timeout settings

## Troubleshooting

### "codegreen: command not found"
Add `~/.local/bin` to your PATH (see step 3 above).

### "ModuleNotFoundError: No module named 'src'"
Reinstall CodeGreen: `./install.sh`

### "Permission denied" when reading sensors
Run `sudo codegreen init-sensors` and log out/in.

### "No energy providers available"
Check hardware support with `codegreen info`. Ensure RAPL is available on Intel/AMD CPUs.

## Next Steps

- Read the [Complete Usage Guide](../USAGE.md)
- Explore the [Architecture Documentation](../design/architecture.md)
- Check [C++ Development Guide](cpp_guide.md) for NEMB backend development
- View examples in `examples/` directory

## Getting Help

```bash
codegreen --help                  # General help
codegreen measure --help          # Command-specific help
```

For issues and questions:
- GitHub Issues: https://github.com/SMART-Dal/codegreen/issues
- Documentation: https://smart-dal.github.io/codegreen/
