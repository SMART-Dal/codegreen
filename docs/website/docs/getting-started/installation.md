# Installation

CodeGreen can be installed via PyPI or built from source. The PyPI package provides a Python-only version with CLI tools, while building from source includes the full C++ components.

## PyPI Installation (Recommended)

The easiest way to install CodeGreen is through PyPI:

```bash
pip install codegreen
```

### Requirements

- Python 3.8 or higher
- Linux, macOS, or Windows
- For GPU monitoring: NVIDIA drivers (Linux/Windows) or Apple Silicon (macOS)

### Verify Installation

After installation, verify that CodeGreen is working correctly:

```bash
codegreen --version
codegreen info
```

## Building from Source

For the full experience with C++ components and hardware monitoring:

### Prerequisites

- Python 3.8+
- CMake 3.17+
- C++17 compatible compiler (GCC, Clang, or MSVC)
- Git

### Build Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/codegreen/codegreen.git
   cd codegreen
   git submodule update --init --recursive
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Build the project:**
   ```bash
   python setup.py build_ext --inplace
   ```

4. **Install:**
   ```bash
   pip install -e .
   ```

### Hardware-Specific Requirements

#### NVIDIA GPU Support
- NVIDIA drivers 450.80.02 or later
- CUDA Toolkit 11.0 or later (optional, for advanced features)

#### Intel/AMD CPU Support
- Linux: RAPL interface (usually available by default)
- Windows: Intel Power Gadget (optional)

#### AMD GPU Support
- ROCm 4.0+ (Linux)
- AMD SMI tools

## Docker Installation

For a containerized environment:

```bash
docker pull codegreen/codegreen:latest
docker run -it --rm codegreen/codegreen:latest
```

## Development Installation

For contributing to CodeGreen:

```bash
git clone https://github.com/codegreen/codegreen.git
cd codegreen
pip install -e ".[dev]"
pre-commit install
```

## Troubleshooting

### Common Issues

**Command not found after installation:**
```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export PATH="$HOME/.local/bin:$PATH"
```

**Permission denied errors:**
```bash
# Use --user flag for user installation
pip install --user codegreen
```

**GPU monitoring not working:**
```bash
# Check NVIDIA drivers
nvidia-smi

# Check CUDA installation
nvcc --version
```

### Getting Help

If you encounter issues:

1. Check the [troubleshooting guide](user-guide/troubleshooting.md)
2. Run `codegreen doctor` for system diagnostics
3. Open an issue on [GitHub](https://github.com/codegreen/codegreen/issues)
