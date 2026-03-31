# Installation

## From PyPI (Recommended)

```bash
pip install codegreen
```

Pre-built wheels available for **Linux x86_64** and **macOS ARM64** (Apple Silicon). Includes the native NEMB energy measurement backend -- no cmake or compilation needed.

After install on Linux, set up RAPL sensor permissions:
```bash
sudo codegreen init-sensors
# then log out/in for group changes
```

On macOS, no setup needed -- energy measurement works out of the box.

## From Source (Development)

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

CodeGreen's NEMB (Native Energy Measurement Backend) auto-detects available energy sensors per platform:

### Linux

| Sensor | Requirements | Description |
|--------|--------------|-------------|
| **Intel RAPL** | Intel CPU | CPU package, core, iGPU, DRAM energy via `/sys/class/powercap` |
| **AMD RAPL** | AMD CPU (EPYC, Ryzen 3000+) | CPU package energy via RAPL interface. Verified on EPYC 9554P (Zen 4). No separate DRAM counter on AMD. |
| **NVIDIA NVML** | NVIDIA GPU + drivers 450.80+ | GPU cumulative energy (mJ). Verified on RTX 5000 Ada. |
| **AMD ROCm** | AMD GPU + ROCm SMI | GPU power via ROCm SMI |

### macOS

| Sensor | Requirements | Description |
|--------|--------------|-------------|
| **IOReport** | Apple Silicon or Intel Mac | CPU, GPU, ANE, DRAM energy via `libIOReport.dylib` |
| **kpc/kperf** | Apple Silicon, sudo | Exact hardware perf counters (cycles, IPC, cache misses) at ~200ns |

### Windows

| Sensor | Requirements | Description |
|--------|--------------|-------------|
| **EMI (Energy Metering Interface)** | Windows 11, Intel CPU (11th gen+) | RAPL energy via inbox `intelpep.sys` driver. Zero install, no admin needed. |
| **NVML** | NVIDIA GPU + drivers 450.80+ | GPU energy via `nvml.dll` (cumulative mJ). User-mode, no admin. |

Windows 11's inbox Intel Power Engine Plugin (`intelpep.sys`) exposes RAPL counters through the Energy Metering Interface (EMI). No additional drivers, no admin setup, nothing to install. Same hardware-integrated cumulative energy as Linux RAPL. Verified on i7-1165G7 (Tiger Lake) and i7-12700H (Alder Lake).

**Windows EMI measures 4 RAPL domains:**

| Domain | What it measures | Example |
|--------|-----------------|---------|
| `RAPL_Package0_PKG` | Entire CPU package (all cores + iGPU + L3 + memory controller) | Total CPU energy |
| `RAPL_Package0_PP0` | CPU cores only (P-cores + E-cores on 12th gen+) | Core computation energy |
| `RAPL_Package0_PP1` | Integrated GPU (Intel Iris Xe / UHD) | iGPU energy |
| `RAPL_Package0_DRAM` | DRAM memory controller + memory | Memory energy |

AMD CPU support on Windows via EMI is unconfirmed (`intelpep.sys` is Intel-specific). Windows 10 does not expose RAPL via EMI.

Energy measurement on macOS works without sudo on modern macOS (Ventura+). The auto-detection backend chain is: NEMB (in-process) > perf (Linux) > powermetrics (macOS) > time-only.

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
