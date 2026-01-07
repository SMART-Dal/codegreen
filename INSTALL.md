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

## Alternative Methods

### From PyPI (Future)
```bash
pip install codegreen
sudo codegreen init-sensors
```

### From GitHub Release (Future)
```bash
wget https://github.com/SMART-Dal/codegreen/releases/download/v0.1.0/codegreen-0.1.0-linux-x86_64.whl
pip install codegreen-0.1.0-linux-x86_64.whl
```

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
