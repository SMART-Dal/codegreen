# CodeGreen Installation Guide

This guide will help you install CodeGreen on your system.

## Prerequisites

### System Requirements
- Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+)
- x86_64 or ARM64 architecture
- At least 2GB RAM
- 1GB free disk space

### Required Software
- CMake 3.16 or higher
- GCC 7.0 or higher (or compatible C++17 compiler)
- Make
- pkg-config
- Git

### Required Libraries
- libjsoncpp-dev
- libcurl4-openssl-dev

## Installation Steps

### 1. Install System Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libjsoncpp-dev \
    libcurl4-openssl-dev \
    git
```

#### CentOS/RHEL
```bash
sudo yum groupinstall -y "Development Tools"
sudo yum install -y \
    cmake3 \
    pkgconfig \
    jsoncpp-devel \
    libcurl-devel \
    git
```

#### Arch Linux
```bash
sudo pacman -S \
    base-devel \
    cmake \
    pkg-config \
    jsoncpp \
    curl \
    git
```

### 2. Clone the Repository
```bash
git clone https://github.com/your-org/codegreen.git
cd codegreen
```

### 3. Build and Install

#### Option A: Using the Build Script (Recommended)
```bash
# Make the build script executable
chmod +x scripts/build.sh

# Run the build script
./scripts/build.sh
```

The build script will:
- Check all dependencies
- Configure the project with CMake
- Build all components
- Install the binary to `/usr/local/bin/codegreen`

#### Option B: Manual Build
```bash
# Create build directory
mkdir build
cd build

# Configure with CMake
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
make -j$(nproc)

# Install
sudo make install
```

### 4. Verify Installation
```bash
# Check if codegreen is available
which codegreen

# Check version
codegreen --version

# Test basic functionality
codegreen --help
```

## Post-Installation

### 1. Add to PATH (if not already added)
The binary is installed to `/usr/local/bin/` which should already be in your PATH. If not, add it:

```bash
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 2. Create Configuration Directory
```bash
mkdir -p ~/.config/codegreen
```

### 3. Set Up Hardware Monitoring (Optional)
Some hardware monitoring features may require additional setup:

```bash
# For Intel RAPL (if supported)
sudo modprobe msr

# For GPU monitoring (NVIDIA)
sudo nvidia-smi

# For ARM energy counters
# May require kernel configuration
```

## Troubleshooting

### Common Issues

#### CMake Not Found
```bash
# Ubuntu/Debian
sudo apt-get install cmake

# CentOS/RHEL
sudo yum install cmake3
```

#### Compiler Not Found
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
```

#### Missing Libraries
```bash
# Check what's missing
pkg-config --exists jsoncpp || echo "jsoncpp missing"
pkg-config --exists libcurl || echo "libcurl missing"

# Install missing libraries
sudo apt-get install libjsoncpp-dev libcurl4-openssl-dev
```

#### Permission Denied During Install
```bash
# Make sure you have sudo privileges
sudo -v

# Or install to user directory
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local
make install
```

### Build Errors

#### C++17 Not Supported
Update your compiler:
```bash
# Ubuntu/Debian
sudo apt-get install g++-8

# Use specific compiler
cmake .. -DCMAKE_CXX_COMPILER=g++-8
```

#### Memory Issues During Build
Reduce parallel jobs:
```bash
make -j2  # Use 2 jobs instead of all cores
```

## Development Installation

For development work, you may want to install in development mode:

```bash
# Clone and setup
git clone https://github.com/your-org/codegreen.git
cd codegreen

# Create development build
mkdir build-debug
cd build-debug
cmake .. -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=$HOME/.local
make -j$(nproc)
make install

# Add to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Uninstallation

To remove CodeGreen:

```bash
# Remove binary
sudo rm -f /usr/local/bin/codegreen

# Remove libraries
sudo rm -rf /usr/local/lib/libcodegreen*

# Remove headers
sudo rm -rf /usr/local/include/codegreen

# Remove configuration (optional)
rm -rf ~/.config/codegreen
```

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Search existing issues on GitHub
3. Create a new issue with:
   - Your system information (`uname -a`)
   - Error messages
   - Steps to reproduce
   - CMake and compiler versions

## Next Steps

After installation, see the main README.md for:
- Usage examples
- Configuration options
- API documentation
- Contributing guidelines 