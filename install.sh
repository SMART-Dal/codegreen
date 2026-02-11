#!/bin/bash
set -e

echo "CodeGreen Installation"
echo "====================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# --- System Requirements ---
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
echo "[ok] Python $PYTHON_VERSION"

for tool in cmake make g++; do
    if ! command -v $tool &> /dev/null; then
        echo "Error: $tool not found. Install with: sudo apt install build-essential cmake"
        exit 1
    fi
done
echo "[ok] CMake $(cmake --version | head -1 | awk '{print $3}')"
echo "[ok] g++ $(g++ --version | head -1 | awk '{print $NF}')"

# --- Git Submodules ---
echo ""
echo "Initializing submodules..."
git submodule update --init --recursive 2>/dev/null || {
    echo "Warning: git submodule update failed (not a git checkout?)"
}

# --- Python Dependencies ---
echo ""
echo "Installing Python dependencies..."

export PIP_BREAK_SYSTEM_PACKAGES=1
IS_VENV=$(python3 -c "import sys; print(1 if sys.prefix != sys.base_prefix else 0)")

PIP_USER_FLAG="--user"
SUDO_CMD=""

if [ "$IS_VENV" -eq 1 ]; then
    echo "Virtual environment detected."
    PIP_USER_FLAG=""
fi

python3 -m pip install $PIP_USER_FLAG --upgrade pip setuptools wheel 2>&1 | tail -1
python3 -m pip install $PIP_USER_FLAG -r requirements.txt 2>&1 | tail -1
python3 -m pip install $PIP_USER_FLAG cmake-build-extension pybind11 2>&1 | tail -1

unset PIP_BREAK_SYSTEM_PACKAGES

# --- Build C++ Backend ---
echo ""
echo "Building NEMB C++ backend..."

BUILD_DIR="$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

cmake .. -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=$(which python3) 2>&1 | tail -3
make -j$(nproc) 2>&1 | tail -3

if [ ! -f "$PROJECT_ROOT/lib/libcodegreen-nemb.so" ]; then
    echo "Error: Build failed - libcodegreen-nemb.so not produced"
    exit 1
fi
echo "[ok] libcodegreen-nemb.so built"

cd "$PROJECT_ROOT"

# --- Install Python Package ---
echo ""
echo "Installing CodeGreen CLI..."

export PIP_BREAK_SYSTEM_PACKAGES=1
python3 -m pip uninstall -y codegreen 2>/dev/null || true
python3 -m pip install $PIP_USER_FLAG -e . 2>&1 | tail -1
unset PIP_BREAK_SYSTEM_PACKAGES

# --- Install Library ---
echo ""
echo "Installing shared library..."
LIB_INSTALL_DIR="$PROJECT_ROOT/lib"

# Also install to /usr/local/lib if writable (for LD path)
if [ -w /usr/local/lib ]; then
    cp "$LIB_INSTALL_DIR/libcodegreen-nemb.so" /usr/local/lib/
    ldconfig 2>/dev/null || true
    echo "[ok] Library installed to /usr/local/lib"
else
    echo "Note: Install library system-wide with:"
    echo "  sudo cp $LIB_INSTALL_DIR/libcodegreen-nemb.so /usr/local/lib/ && sudo ldconfig"
fi

# --- Verify Installation ---
echo ""
echo "Verifying installation..."

INSTALL_BIN="$(python3 -m site --user-base 2>/dev/null)/bin"
if [ "$IS_VENV" -eq 1 ]; then
    INSTALL_BIN="$(python3 -c 'import sys; print(sys.prefix)')/bin"
fi
export PATH="$INSTALL_BIN:$PATH"

if command -v codegreen &>/dev/null; then
    echo "[ok] codegreen CLI installed"
else
    echo "Warning: codegreen not in PATH"
    echo "  Add: export PATH=\"$INSTALL_BIN:\$PATH\""
fi

if [ -r "/sys/class/powercap/intel-rapl:0/energy_uj" ]; then
    echo "[ok] Intel RAPL sensors accessible"
else
    echo "[!!] RAPL sensors need setup: sudo codegreen init-sensors"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Quick start:"
echo "  codegreen measure python your_script.py"
echo "  codegreen measure c your_code.c"
echo "  codegreen benchmark python nbody 50000"
echo ""
echo "If RAPL not accessible, run once:"
echo "  sudo codegreen init-sensors"
echo "  (then log out/in)"
echo ""
echo "Docs: https://smart-dal.github.io/codegreen/"
