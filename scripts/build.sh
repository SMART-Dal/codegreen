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
check_dependency cmake
check_dependency make
check_dependency g++
check_dependency pkg-config
check_dependency docker
check_dependency docker-compose

# Check for required libraries
check_library() {
    if ! pkg-config --exists $1; then
        print_error "$1 development library is required but not installed"
        print_error "Install with: sudo apt-get install lib$1-dev"
        exit 1
    fi
}

print_status "Checking required libraries..."
check_library jsoncpp
check_library libcurl

# Create build directory
print_status "Creating build directory..."
mkdir -p build
cd build

# Configure with CMake
print_status "Configuring project with CMake..."
cmake .. -DCMAKE_BUILD_TYPE=Release

# Build the project
print_status "Building project..."
make -j$(nproc)

# Install
print_status "Installing..."
sudo make install

# Create symlinks
print_status "Creating symlinks..."
sudo ln -sf /usr/local/bin/codegreen /usr/local/bin/codegreen

print_status "Build completed successfully!"
print_status "You can now use the 'codegreen' command"
print_status "Binary location: /usr/local/bin/codegreen" 