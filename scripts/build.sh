#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print status
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_warning "Please do not run this script as root"
    exit 1
fi

# Check for required tools
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is required but not installed"
        exit 1
    fi
}

print_status "Checking dependencies..."
check_dependency rustc
check_dependency cargo
check_dependency docker
check_dependency docker-compose
check_dependency python3
check_dependency pip3

# Create build directory
print_status "Creating build directory..."
mkdir -p build

# Build all packages
print_status "Building packages..."

# Build energy-core
print_status "Building energy-core..."
cd packages/energy-core
cargo build --release
cd ../..

# Build energy-instrumentation
print_status "Building energy-instrumentation..."
cd packages/energy-instrumentation
cargo build --release
cd ../..

# Build energy-language-adapters
print_status "Building energy-language-adapters..."
cd packages/energy-language-adapters
cargo build --release
cd ../..

# Build energy-hardware-plugins
print_status "Building energy-hardware-plugins..."
cd packages/energy-hardware-plugins
cargo build --release
cd ../..

# Build energy-visualization
print_status "Building energy-visualization..."
cd packages/energy-visualization
cargo build --release
cd ../..

# Build energy-optimizer
print_status "Building energy-optimizer..."
cd packages/energy-optimizer
cargo build --release
cd ../..

# Build Python bindings
print_status "Building Python bindings..."
cd packages/energy-instrumentation
maturin build
cd ../..

# Copy binaries to build directory
print_status "Copying binaries to build directory..."
mkdir -p build/bin
cp packages/*/target/release/* build/bin/ 2>/dev/null || true

# Create symlinks
print_status "Creating symlinks..."
ln -sf "$(pwd)/build/bin/energy-instrumentation" /usr/local/bin/codegreen

print_status "Build completed successfully!"
print_status "You can now use the 'codegreen' command" 