# Building from Source

## Prerequisites

- Python 3.8+
- CMake 3.16+
- GCC 7+ or Clang (C++17)
- System libraries: `libjsoncpp-dev`, `libcurl4-openssl-dev`, `libsqlite3-dev`

## Build Steps

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
git submodule update --init --recursive

# Build C++ backend
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
cd ..

# Install Python CLI
pip install -e .

# Initialize sensors
sudo codegreen init-sensors
```

## Build Output

| Artifact | Path |
|----------|------|
| NEMB shared library | `lib/libcodegreen-nemb.so` |
| CLI entry point | `codegreen` (via pip) |

## Build Options

```bash
# Debug build
cmake .. -DCMAKE_BUILD_TYPE=Debug

# Release with debug info
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
```

## Verification

```bash
codegreen --version
codegreen doctor
codegreen measure-workload --duration 3
```
