# Installation

CodeGreen can be installed via the automated script or built manually from source.

## Quick Install (Recommended)

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
sudo ./install.sh
```

**What this does:**

- Checks system requirements (Python 3.8+, CMake, g++)
- Initializes git submodules (Tree-sitter grammars)
- Installs Python dependencies
- Builds the NEMB C++ backend (`libcodegreen-nemb.so`)
- Installs the `codegreen` CLI via pip
- Sets up RAPL sensor permissions (creates `codegreen` group, udev rule)

Running with `sudo` handles RAPL permissions automatically. After install, log out and back in for group changes to take effect. No `sudo` needed after that.

If installed without sudo, set up sensors separately:
```bash
sudo codegreen init-sensors
# then log out/in
```

## Manual Build

### Prerequisites

- **Python**: 3.8+
- **CMake**: 3.16+
- **C++ Compiler**: GCC 7+ or Clang (C++17 support)
- **Libraries**: `libjsoncpp-dev`, `libcurl4-openssl-dev`, `libsqlite3-dev`

### Build Steps

1. **Clone and Initialize:**
   ```bash
   git clone https://github.com/SMART-Dal/codegreen.git
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

### Optional: Visualization Support

For `--export-plot` HTML export:
```bash
pip install plotly
```

For PNG/PDF static export:
```bash
pip install matplotlib
```

Or install all visualization dependencies:
```bash
pip install -e ".[viz]"
```

## Development Installation

For contributors:

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
pip install -e ".[dev]"
pre-commit install
```

## Hardware Requirements

CodeGreen's NEMB (Native Energy Measurement Backend) supports the following hardware sensors on **Linux**:

| Sensor | Requirements | Description |
|--------|--------------|-------------|
| **Intel RAPL** | Intel/AMD CPU | CPU package, core, DRAM energy via `/sys/class/powercap` |
| **NVIDIA NVML** | NVIDIA GPU + drivers 450.80+ | GPU power via NVML library |
| **AMD ROCm** | AMD GPU + ROCm | GPU power via ROCm SMI |
| **AMD RAPL** | AMD CPU | CPU energy via RAPL interface |

**Note:** CodeGreen supports Linux, macOS, and Windows. Hardware sensor availability varies by platform.

## Troubleshooting

**Command not found:**
Ensure your installation directory is in your `PATH`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Permission denied (RAPL):**
```bash
sudo codegreen init-sensors
# then log out/in for group changes
```

This creates a `codegreen` group with read-only access to `/sys/class/powercap/` energy counters and a udev rule for persistence across reboots. Verify with `groups | grep codegreen` after relogin.

**Missing dependencies:**
```bash
codegreen doctor
```

### Getting Help

1. Check the [CLI Reference](../user-guide/cli-reference.md)
2. Run `codegreen doctor --verbose`
3. Open an issue on [GitHub](https://github.com/SMART-Dal/codegreen/issues)
