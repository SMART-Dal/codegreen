#!/bin/bash

# CodeGreen Easy Installation Script
# This script automatically detects hardware and installs CodeGreen with optimal sensor support

set -e

echo "🚀 CodeGreen Installation Script"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_error "This script should not be run as root"
    exit 1
fi

# Detect package manager
if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
else
    print_error "Unsupported package manager"
    exit 1
fi

print_status "Detected package manager: $PKG_MANAGER"

# Install system dependencies
print_status "Installing system dependencies..."

case $PKG_MANAGER in
    "apt")
        sudo apt-get update
        sudo apt-get install -y build-essential cmake git sqlite3 libsqlite3-dev
        ;;
    "yum"|"dnf")
        sudo $PKG_MANAGER install -y gcc gcc-c++ make cmake git sqlite sqlite-devel
        ;;
    "pacman")
        sudo pacman -Syu --noconfirm base-devel cmake git sqlite
        ;;
esac

print_success "System dependencies installed"

# Check for optional hardware support
print_status "Detecting hardware capabilities..."

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    print_success "NVIDIA GPU detected"
    if command -v nvcc &> /dev/null; then
        print_success "CUDA toolkit found - NVML sensor will be enabled"
    else
        print_warning "NVIDIA GPU found but CUDA toolkit not installed"
        print_status "To enable NVML sensor: install CUDA toolkit from NVIDIA"
    fi
else
    print_status "No NVIDIA GPU detected"
fi

# Check for AMD GPU
if command -v rocm-smi &> /dev/null; then
    print_success "AMD ROCm found - AMD SMI sensor will be enabled"
elif lsmod | grep -q amdgpu; then
    print_warning "AMD GPU driver found but ROCm not installed"
    print_status "To enable AMD SMI sensor: install ROCm from AMD"
else
    print_status "No AMD GPU detected"
fi

# Check for Intel/AMD CPU power monitoring
if [ -d "/sys/class/powercap/intel-rapl" ]; then
    print_success "RAPL power monitoring interface found"
else
    print_warning "RAPL power monitoring interface not available"
fi

# Check for PowerSensor devices
if lsusb | grep -qi "powersensor\|power.*sensor"; then
    print_success "PowerSensor USB device detected"
else
    print_status "No PowerSensor USB devices found"
fi

echo ""
print_status "Building CodeGreen with automatic hardware detection..."

# Create build directory
mkdir -p build
cd build

# Configure with CMake
print_status "Configuring build system..."
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build
print_status "Building CodeGreen..."
make -j$(nproc)

print_success "CodeGreen built successfully!"

# Test the installation
print_status "Testing installation..."
./bin/codegreen --help

echo ""
print_success "🎉 CodeGreen installation completed!"
echo ""
echo "📋 Next steps:"
echo "  1. Start measuring energy: ./bin/codegreen python3 your_script.py"
echo "  2. View dashboard: python3 ../scripts/energy_dashboard.py"
echo "  3. Customize settings: edit ../config/codegreen.conf"
echo ""
echo "📚 Documentation: https://github.com/your-repo/codegreen"
echo "🐛 Issues: https://github.com/your-repo/codegreen/issues"
echo ""
