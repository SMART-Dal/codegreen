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

# --- RAPL Sensor Permissions ---
echo ""
echo "Setting up energy sensor permissions..."

RAPL_OK=0
if [ -r "/sys/class/powercap/intel-rapl:0/energy_uj" ]; then
    echo "[ok] Intel RAPL sensors already accessible"
    RAPL_OK=1
elif [ "$(id -u)" -eq 0 ]; then
    # Running as root (sudo ./install.sh) - set up RAPL now
    ACTUAL_USER="${SUDO_USER:-$USER}"
    if [ "$ACTUAL_USER" != "root" ]; then
        echo "Setting up RAPL access for $ACTUAL_USER..."
        echo "  (Read-only access to energy counters via group permissions)"
        echo "  (Same approach as CodeCarbon, Scaphandre, and other energy tools)"

        # Create codegreen group
        if ! getent group codegreen > /dev/null 2>&1; then
            groupadd codegreen
            echo "  [ok] Created 'codegreen' group"
        fi

        # Add user to group
        if ! id -nG "$ACTUAL_USER" | grep -qw codegreen; then
            usermod -aG codegreen "$ACTUAL_USER"
            echo "  [ok] Added $ACTUAL_USER to 'codegreen' group"
        fi

        # Set RAPL file permissions
        RAPL_COUNT=0
        for f in /sys/class/powercap/intel-rapl*/energy_uj /sys/class/powercap/intel-rapl*/max_energy_range_uj; do
            [ -f "$f" ] && chgrp codegreen "$f" 2>/dev/null && chmod g+r "$f" 2>/dev/null && RAPL_COUNT=$((RAPL_COUNT+1))
        done

        # Udev rule for persistence across reboots
        UDEV_RULE='/etc/udev/rules.d/99-codegreen-rapl.rules'
        echo 'SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", GROUP="codegreen", MODE="0640"' > "$UDEV_RULE"
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger 2>/dev/null || true

        if [ "$RAPL_COUNT" -gt 0 ]; then
            echo "  [ok] Set read permissions on $RAPL_COUNT RAPL sysfs files"
            echo "  [ok] Udev rule: $UDEV_RULE (persists across reboots)"
            echo "  [ok] Group: 'codegreen' with read-only access to /sys/class/powercap/"
            RAPL_OK=1
            echo ""
            echo "[!!] Log out and log back in for group membership to take effect"
            echo "     Verify with: groups | grep codegreen"
        else
            echo "  [!!] No RAPL files found in /sys/class/powercap/"
            echo "       CPU may not support RAPL energy counters"
        fi
    fi
else
    echo "[!!] RAPL sensors not accessible (permission denied)"
    echo "  RAPL files at /sys/class/powercap/intel-rapl*/energy_uj need read access"
    echo "  Fix: re-run installer with sudo, or run:"
    echo "    sudo codegreen init-sensors"
    echo "    (then log out and back in for group changes)"
fi

echo ""
echo "Installation complete!"
echo ""
echo "What was installed:"
echo "  Library: $PROJECT_ROOT/lib/libcodegreen-nemb.so"
echo "  CLI:     $(which codegreen 2>/dev/null || echo '$INSTALL_BIN/codegreen')"
if [ "$RAPL_OK" -eq 1 ]; then
echo "  Sensors: RAPL access via 'codegreen' group (read-only)"
fi
echo ""
echo "Quick start:"
echo "  codegreen measure python your_script.py"
echo "  codegreen measure python your_script.py -g fine --export-plot energy.html"
echo "  codegreen benchmark python nbody 50000"
echo ""
echo "Docs: https://smart-dal.github.io/codegreen/"
