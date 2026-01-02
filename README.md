# CodeGreen - Energy Monitoring and Code Optimization Tool

CodeGreen is a comprehensive tool for fine-grained energy profiling and optimization of code. It provides real-time energy measurement during code execution, identifies energy hotspots, and offers optimization suggestions to reduce energy consumption.

## 🚀 Quick Start

### Prerequisites

- **Linux** (Primary platform, Kernel 5.0+ required for RAPL energy measurement)
- **Python 3.8+**
- **C++ Build Tools**: `gcc`, `g++`, and **CMake** (required for NEMB energy sensors)

### Installation

#### Easy Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/codegreen-dev/codegreen.git
cd codegreen

# Initialize submodules (Required for Tree-sitter grammars)
git submodule update --init --recursive

# Install dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install cmake build-essential pkg-config libjsoncpp-dev libcurl4-openssl-dev libsqlite3-dev python3-dev

# Run the orchestrated installation
./install.sh
```

#### Manual Installation

```bash
# Initialize submodules
git submodule update --init --recursive

# Install Python dependencies
pip3 install -r requirements.txt

# Build C++ components
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Install Python CLI package
cd ..
pip3 install -e .
```

### ⚡ Sensor Permissions (Critical)

To measure CPU energy (via Intel RAPL), the tool needs read access to hardware registers. Run the following command if you encounter permission errors:

```bash
sudo chmod -R a+r /sys/class/powercap/intel-rapl
```

## 📊 Basic Usage

Once installed, use the `codegreen` CLI to measure and analyze your code.

### 1. Verify Environment
Check which hardware sensors (CPU, GPU, NVIDIA) are active on your system:
```bash
codegreen info
```

### 2. Static Analysis (Identify Hotspots)
Analyze a source file to see where energy checkpoints will be added. This uses our language-agnostic Tree-sitter query engine:
```bash
codegreen analyze python tests/complex_python_cases.py --save-instrumented
```
*This produces an `_instrumented.py` file with measurement calls inserted at every function entry and return path.*

### 3. Dynamic Measurement (Real-time Energy)
Execute your code and capture actual Joule (J) and Watt (W) consumption data:
```bash
codegreen measure python my_script.py
```

## 🔌 Pluggable Language Support

CodeGreen is designed to be language-agnostic. To add support for a new language (e.g., **Go** or **Rust**), you do not need to modify the core engine:

1.  **Config**: Drop a `<language>.json` file into `src/instrumentation/configs/`.
2.  **Queries**: Add Tree-sitter `.scm` queries to the `third_party/nvim-treesitter/queries/` directory.
3.  **Run**: Immediately start analyzing with `codegreen analyze <language> <file>`.

## 🏗️ Architecture

CodeGreen uses a hybrid C++/Python architecture for optimal performance:

- **C++ Core (NEMB)**: High-performance energy measurement backend.
- **Python AST Engine**: Multi-language code analysis using Tree-sitter.
- **JSON Rules**: Externalized configuration for language-specific behavior.
- **SQLite Database**: Persistent storage for energy measurement sessions.

## 🤝 Contributing

We welcome contributions! 
1. Fork the repo.
2. Create your feature branch.
3. Ensure tests pass by running `./install.sh`.
4. Submit a Pull Request.

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**CodeGreen** - Making software development more energy-efficient, one line of code at a time. 🌱⚡
