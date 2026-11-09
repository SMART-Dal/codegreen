# Building from Source

`./install.sh` does all of this in one step; see
[Installation](../getting-started/installation.md#from-source). The manual
steps:

## Prerequisites

- Python 3.9 or later
- CMake 3.16 or later, `make` and a C++17 compiler (GCC or Clang)
- Optional: a JDK (`JNI`) for the Java runtime bridge, the NVIDIA driver for
  NVML

## Build

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
git submodule update --init --recursive    # Tree-sitter grammars

mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release        # Debug or RelWithDebInfo also work
make -j"$(nproc)"
cd ..

pip install -e .                           # the codegreen CLI
sudo codegreen init-sensors                # Linux: RAPL read access
```

| Artifact | Path |
|---|---|
| NEMB shared library | `build/lib/libcodegreen-nemb.so`, copied to `lib/libcodegreen-nemb.so` |
| CLI | `codegreen` on the environment's `PATH` (from `pip install -e .`) |

## Verify

```bash
codegreen --version
codegreen doctor --test-sensors
codegreen measure-workload --duration 3
```

## Tests

```bash
pip install -e ".[dev,all]"
pytest tests --ignore=tests/test_examples.py   # as in CI; energy tests skip without RAPL or NVML
pytest tests/test_examples.py                  # runs the examples/ scripts
cd build && make nemb-validation-test && ./bin/nemb-validation-test   # native validation tests
```
