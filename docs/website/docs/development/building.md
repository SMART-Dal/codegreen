# Building from Source

Complete guide to building CodeGreen from source for development and contribution.

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+, Fedora 33+, Arch Linux)
- **CPU**: x86_64 architecture (Intel/AMD)
- **Memory**: 2 GB RAM minimum, 4 GB recommended
- **Disk**: 1 GB free space

### Required Tools

**Build Tools:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    git

# Fedora
sudo dnf install -y \
    gcc gcc-c++ \
    cmake \
    pkg-config \
    git

# Arch Linux
sudo pacman -S --noconfirm \
    base-devel \
    cmake \
    pkg-config \
    git
```

**C++ Compiler:**
- GCC 7+ or Clang 10+ with C++17 support
- CMake 3.16+

**Python:**
```bash
# Ubuntu/Debian
sudo apt-get install -y python3 python3-pip python3-dev

# Fedora
sudo dnf install -y python3 python3-pip python3-devel

# Arch Linux
sudo pacman -S --noconfirm python python-pip
```

### Required Libraries

**C++ Dependencies:**
```bash
# Ubuntu/Debian
sudo apt-get install -y \
    libjsoncpp-dev \
    libcurl4-openssl-dev \
    libsqlite3-dev

# Fedora
sudo dnf install -y \
    jsoncpp-devel \
    libcurl-devel \
    sqlite-devel

# Arch Linux
sudo pacman -S --noconfirm \
    jsoncpp \
    curl \
    sqlite
```

**Python Dependencies:**
```bash
pip3 install -r requirements.txt
```

## Quick Build

### Automated Installation

Fastest way to build and install:

```bash
git clone https://github.com/codegreen/codegreen.git
cd codegreen
./install.sh
```

This script:
1. Installs system dependencies (requires sudo)
2. Builds NEMB (C++ measurement backend)
3. Installs Python CLI
4. Sets up binary in `/usr/local/bin`

### Manual Build

For development or custom installation:

```bash
git clone https://github.com/codegreen/codegreen.git
cd codegreen

# Initialize submodules
git submodule update --init --recursive

# Build C++ NEMB library
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Install library
sudo make install
sudo ldconfig

# Install Python CLI
cd ..
pip3 install -e .
```

## Build Configurations

### Debug Build

For development with debug symbols:

```bash
mkdir build-debug && cd build-debug
cmake .. -DCMAKE_BUILD_TYPE=Debug
make -j$(nproc)
```

**Features:**
- Debug symbols included
- Assertions enabled
- No optimization (-O0)
- Larger binary size

### Release Build

For production with optimizations:

```bash
mkdir build-release && cd build-release
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

**Features:**
- Full optimizations (-O3)
- Debug symbols stripped
- Smaller binary size
- Maximum performance

### RelWithDebInfo Build

For profiling with debug info:

```bash
mkdir build-profile && cd build-profile
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
make -j$(nproc)
```

**Features:**
- Optimizations enabled (-O2)
- Debug symbols retained
- Good for profiling

## Build Options

### CMake Configuration Options

```bash
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DBUILD_TESTS=ON \
    -DBUILD_EXAMPLES=ON \
    -DENABLE_CUDA=OFF
```

**Available Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `CMAKE_BUILD_TYPE` | Release | Build type (Debug/Release/RelWithDebInfo) |
| `CMAKE_INSTALL_PREFIX` | /usr/local | Installation directory |
| `BUILD_TESTS` | ON | Build unit tests |
| `BUILD_EXAMPLES` | OFF | Build example programs |
| `ENABLE_CUDA` | OFF | Enable CUDA support (requires CUDA Toolkit) |
| `ENABLE_ROCM` | OFF | Enable AMD ROCm support |

### Compiler Selection

Use specific compiler:

```bash
# GCC
cmake .. -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++

# Clang
cmake .. -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
```

## Development Build

### Editable Install

For active development:

```bash
# Install Python package in editable mode
pip3 install -e .

# Changes to Python code take effect immediately
# No need to reinstall after editing
```

### Build NEMB Library Only

When working on C++ components:

```bash
cd build
make -j$(nproc)
sudo make install
sudo ldconfig
```

### Running Tests

After building with `BUILD_TESTS=ON`:

```bash
# C++ tests
cd build
ctest --output-on-failure

# Python tests
pytest tests/
```

## Troubleshooting

### CMake Configuration Fails

**Problem:** `Could not find required library: jsoncpp`

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install libjsoncpp-dev

# Fedora
sudo dnf install jsoncpp-devel

# Arch Linux
sudo pacman -S jsoncpp
```

### Compilation Errors

**Problem:** `error: 'std::filesystem' has not been declared`

**Solution:** Update to GCC 8+ or Clang 10+:
```bash
# Ubuntu 20.04
sudo apt-get install gcc-10 g++-10
cmake .. -DCMAKE_C_COMPILER=gcc-10 -DCMAKE_CXX_COMPILER=g++-10
```

### Linker Errors

**Problem:** `undefined reference to 'Json::Value::Value()'`

**Solution:** Ensure libjsoncpp is installed and ldconfig is run:
```bash
sudo ldconfig
```

### Permission Errors During Install

**Problem:** `Permission denied` when running `make install`

**Solution:** Use sudo for system installation:
```bash
sudo make install
sudo ldconfig
```

Or install to user directory:
```bash
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local
make install
export PATH="$HOME/.local/bin:$PATH"
```

### Import Errors in Python

**Problem:** `ModuleNotFoundError: No module named 'codegreen'`

**Solution:**
```bash
# Reinstall Python package
pip3 install -e .

# Or add to PYTHONPATH
export PYTHONPATH="$PWD:$PYTHONPATH"
```

## Cross-Compilation

### ARM64 (aarch64)

```bash
# Install cross-compiler
sudo apt-get install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu

# Configure for ARM64
cmake .. \
    -DCMAKE_SYSTEM_NAME=Linux \
    -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
    -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc \
    -DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++

make -j$(nproc)
```

## Packaging

### Debian/Ubuntu Package

```bash
# Install packaging tools
sudo apt-get install debhelper dh-make

# Create package
cd codegreen
dpkg-buildpackage -us -uc

# Install
sudo dpkg -i ../codegreen_0.1.0_amd64.deb
```

### RPM Package (Fedora/RHEL)

```bash
# Install packaging tools
sudo dnf install rpm-build rpmdevtools

# Create package
cd codegreen
rpmbuild -ba codegreen.spec

# Install
sudo rpm -i ~/rpmbuild/RPMS/x86_64/codegreen-0.1.0-1.x86_64.rpm
```

## Verification

After building, verify installation:

```bash
# Check binary
which codegreen
codegreen --version

# Check library
ldconfig -p | grep codegreen

# Run doctor
codegreen doctor --verbose

# Run validation test
sudo codegreen validate --quick
```

## Clean Build

Remove build artifacts:

```bash
# Clean CMake build
rm -rf build/

# Clean Python build
rm -rf build/ dist/ *.egg-info
pip3 uninstall codegreen

# Full clean (including submodules)
git clean -fdx
git submodule foreach --recursive git clean -fdx
```

## See Also

- [Contributing Guide](contributing.md) - Development workflow
- [Architecture](architecture.md) - System design
- [Installation](../getting-started/installation.md) - User installation
