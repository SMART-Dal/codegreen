# CodeGreen Installation Guide

## Quick Install (Recommended)

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh
```

The installer handles PEP 668 externally-managed Python environments automatically.

Add to PATH:
```bash
# Linux
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# macOS
echo 'export PATH="$HOME/Library/Python/3.X/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

One-time setup (run once):
```bash
# Make codegreen available to sudo
sudo ln -sf ~/.local/bin/codegreen /usr/local/bin/codegreen

# Setup permanent RAPL permissions
sudo codegreen init-sensors

# Log out and log back in
```

After this, no sudo needed for normal operations!

Test:
```bash
codegreen --version
codegreen info
codegreen doctor
```

---

## System Requirements

**Required:**
- Linux (Ubuntu 20.04+, Debian 11+, Fedora 35+)
- Python 3.8 or higher
- CMake 3.15+
- C++ compiler (gcc 9+ or clang 10+)
- Make

**Optional:**
- Intel CPU with RAPL support (for energy measurement)
- NVIDIA GPU with NVML support (for GPU energy)
- AMD GPU with ROCm support (for AMD GPU energy)

---

## Detailed Installation

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip cmake build-essential git
```

**Fedora/RHEL:**
```bash
sudo dnf install -y python3 python3-pip cmake gcc-c++ make git
```

**macOS:**
```bash
brew install python cmake
```

### 2. Clone Repository

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
```

### 3. Run Installer

```bash
./install.sh
```

The installer will:
- Check Python version (3.8+ required)
- Install Python dependencies
- Build C++ measurement engine
- Install CLI tool to `~/.local/bin/codegreen`
- Run basic tests

### 4. Configure PATH

Add `~/.local/bin` to your PATH:

```bash
# For bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# For zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 5. Initialize Energy Sensors

Enable hardware energy measurement:

```bash
sudo codegreen init-sensors
```

This configures:
- Intel RAPL counters
- NVIDIA GPU sensors (if available)
- AMD GPU sensors (if available)

---

## Verification

Check installation:
```bash
codegreen --version
codegreen info
codegreen doctor
```

Run benchmark:
```bash
codegreen benchmark cpu_stress --duration 5
```

---

## Troubleshooting

### "externally-managed-environment" Error

**Fixed automatically** - The installer uses `PIP_BREAK_SYSTEM_PACKAGES=1` environment variable to safely install packages to your user directory.

If you still see this error in a new terminal:
```bash
# Verify you're in the repo directory
cd ~/codegreen
./install.sh

# Or check your Python version
python3 --version
which python3
```

The error typically occurs with Homebrew Python (macOS) or system Python on Ubuntu 23.04+. The installer handles this automatically.

### Command not found
```bash
# Check if installed
ls -la ~/.local/bin/codegreen

# Add to PATH (Linux)
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Add to PATH (macOS)
export PATH="$HOME/Library/Python/3.X/bin:$PATH"
echo 'export PATH="$HOME/Library/Python/3.X/bin:$PATH"' >> ~/.zshrc
```

### Permission denied
```bash
chmod +x ~/.local/bin/codegreen
```

### "sudo: codegreen: command not found"

If you installed before this fix, add `~/.local/bin` to sudo's secure_path:

```bash
# Check current secure_path
sudo visudo

# Or use full path once
sudo ~/.local/bin/codegreen init-sensors

# Or preserve PATH
sudo env "PATH=$PATH" codegreen init-sensors
```

After reinstalling with fixed entry point, `sudo codegreen` should work directly.

### "Sensor initialization timed out"

This means codegreen cannot access RAPL files (requires root). Use sudo:

```bash
# Correct (with sudo)
sudo codegreen init-sensors

# Wrong (without sudo)
codegreen init-sensors  # ✗ Will timeout
```

### RAPL sensors not accessible

```bash
# Check if RAPL exists
ls /sys/class/powercap/intel-rapl:0/

# Check permissions
sudo ls -la /sys/class/powercap/intel-rapl:0/

# Initialize with sudo
sudo ~/.local/bin/codegreen init-sensors
```

### Build fails
```bash
# Install missing dependencies
sudo apt install cmake build-essential python3-dev git

# Initialize git submodules
git submodule update --init --recursive

# Clean and rebuild
rm -rf build/
./install.sh
```

---

## Uninstallation

```bash
pip uninstall codegreen
rm ~/.local/bin/codegreen
```

---

## Install from PyPI (Recommended for Users)

```bash
pip install codegreen
sudo codegreen init-sensors
```

The PyPI wheel includes the pre-compiled C++ NEMB backend. No cmake, g++, or manual compilation needed. Works on Linux x86_64 with Python 3.9-3.13.

---

## Development Installation

For contributing to CodeGreen:

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
pip install -e ".[dev]"
./install.sh
```

This installs in editable mode with development dependencies.

---

## Build and Release Architecture

This section documents how CodeGreen is built, packaged, and published. Read this before debugging CI/CD failures or modifying the build pipeline.

### What Gets Built

CodeGreen has two parts:

1. **Python package** (~2000 lines): CLI (`src/cli/`), instrumentation engine (`src/instrumentation/`), analysis/EFG (`src/analysis/`), benchmark harness (`benchmark/`). Pure Python, no compilation needed.

2. **C++ NEMB backend** (~5000 lines): Native Energy Measurement Backend. Compiles to two artifacts:
   - `lib/libcodegreen-nemb.so` (~7.5MB) -- shared library that reads RAPL MSRs, polls energy counters at 1ms intervals, manages checkpoint ring buffers, and correlates timestamps with energy.
   - `build/bin/codegreen` (~5MB) -- CLI binary that links against the shared library. Handles sensor initialization, process spawning, and checkpoint I/O.

   The C++ code depends on: `jsoncpp` (JSON config parsing), `libcurl` (for future remote features), `sqlite3` (result storage), `pthreads` (background measurement thread).

### How the Wheel is Built

The CI/CD pipeline at `.github/workflows/build-and-publish.yml` uses `cibuildwheel` to produce platform-specific wheels:

1. **Container**: `cibuildwheel` spins up a `manylinux_2_28` Docker container (AlmaLinux 8 based). This guarantees the compiled binary works on any Linux with glibc >= 2.28 (Ubuntu 20.04+, Debian 11+, Fedora 35+, RHEL 8+).

2. **C++ deps installed inside container** (`CIBW_BEFORE_ALL_LINUX`):
   ```
   yum install cmake gcc-c++ make pkgconfig jsoncpp-devel libcurl-devel sqlite-devel
   ```

3. **NEMB compiled inside container** (`CIBW_BEFORE_BUILD`):
   ```
   cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_RPATH=$ORIGIN/../lib
   cmake --build . --config Release
   ```
   The `-DCMAKE_INSTALL_RPATH=$ORIGIN/../lib` sets the runtime library search path relative to the binary, so `libcodegreen-nemb.so` is found after `pip install` without `LD_LIBRARY_PATH`.

4. **Binary packaged into wheel**: `setup.py`'s `BuildWithCMake` class copies `lib/libcodegreen-nemb.so` and `build/bin/codegreen` into the wheel's `src/lib/` and `src/bin/` directories. The `BinaryDistribution` class marks the wheel as platform-specific (not `none-any`).

5. **Separate wheel per Python version**: `cibuildwheel` builds for cp39, cp310, cp311, cp312, cp313. Each wheel is tagged like `codegreen-0.2.0-cp311-cp311-manylinux_2_28_x86_64.whl`.

6. **Smoke tests** (`CIBW_TEST_COMMAND`): After building each wheel, cibuildwheel installs it in a clean environment and verifies:
   - The `.so` file exists at the expected path
   - The CLI binary exists and is executable
   - `codegreen --help` works
   - Instrumentation finds checkpoints in a test Python file

### How Publishing Works

Publishing only triggers on **tag pushes** (e.g., `git tag v0.2.0 && git push origin --tags`):

1. `build-wheels` job produces 5 platform-specific wheels (one per Python version)
2. `build-sdist` job produces a `.tar.gz` source distribution
3. `test-wheel` job installs each wheel on fresh VMs with Python 3.10/3.11/3.12 and runs 5 verification checks
4. `publish-pypi` job uploads all wheels + sdist to PyPI using the `PYPI_API_TOKEN` GitHub secret

The source distribution (sdist) is a fallback: if a user's platform has no pre-built wheel (e.g., ARM64), pip downloads the sdist and runs `setup.py` which triggers cmake compilation on their machine.

### File Responsibilities

| File | Role |
|------|------|
| `pyproject.toml` | Package metadata, dependencies, Python package list, entry points |
| `setup.py` | `BuildWithCMake` (triggers cmake), `BinaryDistribution` (marks as platform wheel), copies `.so`/binary into wheel |
| `CMakeLists.txt` | C++ build: finds deps, compiles NEMB, links tree-sitter grammars |
| `.github/workflows/build-and-publish.yml` | CI/CD: cibuildwheel config, smoke tests, PyPI publish |
| `install.sh` | Local development install: checks deps, runs cmake, pip install -e . |

### Platform Support

| Platform | Pre-built wheel | From source | Energy measurement |
|----------|----------------|-------------|-------------------|
| Linux x86_64 (Intel/AMD) | Yes (pip install) | Yes | Full (RAPL + NVML + ROCm) |
| Linux ARM64 | No | Yes (needs cmake + deps) | RAPL if available |
| macOS (Intel) | No | Partial (NEMB won't build) | No (different energy API) |
| macOS (Apple Silicon) | No | Partial | No |
| Windows | No | No | No |

### Common CI/CD Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `502 Bad Gateway` from quay.io | manylinux Docker registry outage | Wait and rerun: `gh run rerun <id>` |
| `cmake: command not found` | Missing `CIBW_BEFORE_ALL_LINUX` deps | Check yum install line |
| `.so not found` in smoke test | Binary not copied into wheel | Check `setup.py` `BuildWithCMake.run()` |
| `py2.py3-none-any.whl` (no binary) | `BinaryDistribution` not used | Ensure `setup.py` has `distclass=BinaryDistribution` |
| `No such file or directory` in cmake | YAML multiline broke command | Keep cmake args on one line in `CIBW_BEFORE_BUILD` |
| SSH submodule clone fails | `Programming-Language-Benchmarks` uses SSH URL | Switch to HTTPS or remove from default submodules |

### How to Debug Build Failures

```bash
# Check latest CI runs
cd ~/codegreen && gh run list --limit 5

# Get failure logs
gh run view <run-id> --log-failed

# Reproduce locally (simulates what cibuildwheel does)
python setup.py bdist_wheel
unzip -l dist/*.whl | grep -E "\.so|/bin/codegreen"  # verify binary in wheel

# Test wheel in clean environment (run from /tmp, not project dir)
cd /tmp
python3 -m venv test && source test/bin/activate
pip install ~/codegreen/dist/codegreen-*.whl
codegreen --help
python -c "import importlib, pathlib; pkg=pathlib.Path(importlib.import_module('src').__file__).parent; print(f'so={(pkg/\"lib\"/\"libcodegreen-nemb.so\").exists()}')"
deactivate && rm -rf test
```

### Releasing a New Version

```bash
cd ~/codegreen

# 1. Update version
# Edit pyproject.toml: version = "X.Y.Z"

# 2. Commit
git add -A && git commit -m "vX.Y.Z: description"

# 3. Tag and push (triggers build + publish)
git tag vX.Y.Z
git push origin main --tags

# 4. Monitor
gh run list --limit 3
gh run view <run-id> --log-failed  # if it fails

# 5. Create GitHub Release (optional, for release notes)
gh release create vX.Y.Z --title "vX.Y.Z" --notes "changelog here"
```
