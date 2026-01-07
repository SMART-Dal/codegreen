<p align="center">
  <img src="docs/website/docs/assets/codegreen_logo.svg#gh-light-mode-only" width="200" alt="CodeGreen Logo">
  <img src="docs/website/docs/assets/codegreen_logo_white.svg#gh-dark-mode-only" width="200" alt="CodeGreen Logo">
</p>

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
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# One-time sensor setup (sets permanent permissions)
sudo codegreen init-sensors

# Log out and log back in once
# After that, no sudo needed!
```

The installer automatically:
- Checks system requirements
- Installs Python dependencies and CLI tool
- Builds C++ measurement engine

#### System Requirements

- Linux (Ubuntu 20.04+, Debian 11+, Fedora 35+) or macOS
- Python 3.8+
- CMake 3.15+
- C++ compiler (gcc 9+ or clang 10+)
- Make
- Intel CPU with RAPL support (for energy measurement)

See [INSTALL.md](INSTALL.md) for detailed installation instructions and troubleshooting.

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
