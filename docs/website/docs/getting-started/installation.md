# Installation

CodeGreen can be installed via the automated script, built manually from source, or installed for development.

## Quick Install (Recommended)

The easiest way to install CodeGreen on Linux/macOS is using the automated script. This handles system dependencies, C++ compilation (NEMB), and Python bindings.

```bash
# 1. Clone the repository
git clone https://github.com/codegreen/codegreen.git
cd codegreen

# 2. Run the automated installer
./install.sh
```

**What this does:**
*   Installs required system packages (requires `sudo`).
*   Builds the Native Energy Measurement Backend (NEMB) using CMake.
*   Installs the `codegreen` CLI tool to your system.

### Post-Install Setup

After installation, it is **critical** to initialize the hardware sensors. This step detects your CPU/GPU capabilities and sets up the necessary permissions (e.g., for reading RAPL energy counters).

```bash
# Initialize sensors (may require sudo for first-time permission setup)
sudo codegreen init-sensors
```

## Manual Build

If you prefer to build manually or have specific requirements:

### Prerequisites

- **Python**: 3.8+
- **CMake**: 3.16+
- **C++ Compiler**: GCC 7+ or Clang (C++17 support)
- **Libraries**: `libjsoncpp-dev`, `libcurl4-openssl-dev`, `libsqlite3-dev`

### Build Steps

1. **Clone and Initialize:**
   ```bash
   git clone https://github.com/codegreen/codegreen.git
   cd codegreen
   git submodule update --init --recursive
   ```

2. **Build C++ Core:**
   ```bash
   mkdir build && cd build
   cmake .. -DCMAKE_BUILD_TYPE=Release
   make -j$(nproc)
   ```

3. **Install Python Package:**
   ```bash
   cd ..
   pip install -e .
   ```

## Development Installation

For contributors or those who want to modify the CodeGreen source code:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/codegreen/codegreen.git
    cd codegreen
    ```

2.  **Install development dependencies:**
    ```bash
    pip install -e ".[dev]"
    ```

3.  **Install pre-commit hooks:**
    ```bash
    pre-commit install
    ```

## Hardware Requirements

CodeGreen's **NEMB** (Native Energy Measurement Backend) supports a variety of hardware sensors.

| Sensor | Requirements | Linux | macOS | Windows |
|--------|--------------|-------|-------|---------|
| **RAPL** | Intel/AMD CPU | ✅ | ✅ | ✅ |
| **NVML** | NVIDIA GPU | ✅ | ✅ | ❌ |
| **ROCm** | AMD GPU | ✅ | ❌ | ❌ |

### Hardware-Specific Notes

*   **NVIDIA GPUs**: Requires NVIDIA drivers 450.80.02 or later. Optional CUDA Toolkit 11.0+ for advanced features.
*   **Intel/AMD CPUs**: Requires access to `/sys/class/powercap` on Linux (handled by `codegreen init`).

## Docker Installation

For containerized environments, use the official image. Note that you must run with `--privileged` to allow access to hardware energy counters.

```bash
docker pull codegreen/codegreen:latest
docker run --privileged -it --rm codegreen/codegreen:latest
```

## Troubleshooting

### Common Issues

**Command not found**
Ensure your installation directory is in your `PATH`. If you installed via `pip --user`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Permission denied (RAPL)**
If you see errors accessing `/sys/class/powercap`, run the initialization command:
```bash
sudo codegreen init-sensors
```

**Missing dependencies**
Use the built-in diagnostic tool to identify missing libraries or configuration issues:
```bash
codegreen doctor
```

### Getting Help

If you encounter persistent issues:

1.  Check the [CLI Reference](../user-guide/cli-reference.md) for correct usage.
2.  Run `codegreen doctor --verbose` for detailed diagnostics.
3.  Open an issue on [GitHub](https://github.com/codegreen/codegreen/issues).
