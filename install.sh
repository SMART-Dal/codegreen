#!/bin/bash
set -e

echo "CodeGreen Installation"
echo "====================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "Checking system requirements..."

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 8 ]; then
    echo "Error: Python 3.8+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"

if ! command -v cmake &> /dev/null; then
    echo "Error: cmake not found. Install with: sudo apt install cmake"
    exit 1
fi
echo "✓ CMake $(cmake --version | head -1 | awk '{print $3}')"

if ! command -v make &> /dev/null; then
    echo "Error: make not found. Install with: sudo apt install build-essential"
    exit 1
fi
echo "✓ Make"

echo ""
echo "Installing Python dependencies..."

# Handle PEP 668 externally-managed environments (Homebrew, Ubuntu 23.04+)
export PIP_BREAK_SYSTEM_PACKAGES=1

python3 -m pip install --user --upgrade pip setuptools wheel
python3 -m pip install --user -r requirements.txt
python3 -m pip install --user cmake-build-extension pybind11

unset PIP_BREAK_SYSTEM_PACKAGES

echo ""
echo "Building CodeGreen..."

BUILD_DIR="$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

cmake .. -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=$(which python3)
make -j$(nproc)

if [ ! -f "$BUILD_DIR/bin/codegreen" ]; then
    echo "Error: Build failed"
    exit 1
fi

cd "$PROJECT_ROOT"
mkdir -p bin
cp "$BUILD_DIR/bin/codegreen" bin/

echo ""
echo "Installing CodeGreen..."

export PIP_BREAK_SYSTEM_PACKAGES=1
sudo python3 -m pip uninstall -y codegreen 2>/dev/null || true
sudo python3 -m pip install -e .
unset PIP_BREAK_SYSTEM_PACKAGES

INSTALL_BIN="$(python3 -c 'import sys; print(sys.prefix)')/bin"
export PATH="$INSTALL_BIN:$PATH"

echo ""
echo "Testing installation..."
if ! command -v codegreen &>/dev/null; then
    echo "Warning: codegreen not in PATH"
    echo "Add to PATH: export PATH=\"$INSTALL_BIN:\$PATH\""
else
    echo "✓ codegreen $(codegreen --version 2>&1 | head -1)"
fi

if [ -r "/sys/class/powercap/intel-rapl:0/energy_uj" ]; then
    echo "✓ Intel RAPL sensors accessible"
else
    echo "⚠ RAPL sensors require setup: sudo codegreen init-sensors"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  1. Add to PATH: echo 'export PATH=\"$INSTALL_BIN:\$PATH\"' >> ~/.zshrc"
    echo "     Then: source ~/.zshrc"
else
    echo "  1. Add to PATH: echo 'export PATH=\"$INSTALL_BIN:\$PATH\"' >> ~/.bashrc"
    echo "     Then: source ~/.bashrc"
fi
echo ""
echo "  2. Initialize sensors (one-time):"
echo "     sudo codegreen init-sensors"
echo "     Then log out/in once"
echo ""
echo "  3. After that, no sudo needed: codegreen --help"
echo "  4. Docs: https://smart-dal.github.io/codegreen/"