#!/bin/bash
set -e

echo "CodeGreen Installation"
echo "====================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Parse flags
SKIP_RAPL=0
UPGRADE=0
for arg in "$@"; do
    case "$arg" in
        --skip-rapl) SKIP_RAPL=1 ;;
        --upgrade) UPGRADE=1 ;;
        --help)
            echo "Usage: ./install.sh [--skip-rapl] [--upgrade]"
            echo "  --skip-rapl  Skip RAPL sensor permission setup"
            echo "  --upgrade    Rebuild and reinstall (preserves config)"
            exit 0 ;;
    esac
done

# --- System Requirements ---
echo ""
echo "Checking system requirements..."

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]; }; then
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

if ! command -v perf &> /dev/null; then
    echo "[!!] perf not found (needed for 'codegreen run' and benchmark validation)"
    echo "     Install with: sudo apt install linux-tools-$(uname -r)"
fi

# --- Git Submodules ---
if [ -d .git ]; then
    echo ""
    echo "Initializing submodules..."
    git submodule update --init --recursive 2>/dev/null || true
fi

# --- Python Dependencies ---
echo ""
echo "Installing Python dependencies..."

IS_VENV=$(python3 -c "import sys; print(1 if sys.prefix != sys.base_prefix else 0)")

PIP_FLAGS=""
if [ "$IS_VENV" -eq 1 ]; then
    echo "Virtual environment detected."
else
    PIP_FLAGS="--user"
    export PIP_BREAK_SYSTEM_PACKAGES=1
fi

python3 -m pip install $PIP_FLAGS --upgrade pip setuptools wheel 2>&1 | tail -1
python3 -m pip install $PIP_FLAGS -r requirements.txt 2>&1 | tail -1

# --- Build C++ Backend ---
echo ""
echo "Building NEMB C++ backend..."

BUILD_DIR="$PROJECT_ROOT/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

if [ "$UPGRADE" -eq 1 ]; then
    echo "Clean rebuild..."
    cmake .. -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=$(which python3) 2>&1 | tail -3
else
    cmake .. -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=$(which python3) 2>&1 | tail -3
fi
make -j$(nproc) 2>&1 | tail -5

cd "$PROJECT_ROOT"

if [ ! -f "$PROJECT_ROOT/lib/libcodegreen-nemb.so" ]; then
    echo "Error: Build failed - libcodegreen-nemb.so not produced"
    exit 1
fi
echo "[ok] libcodegreen-nemb.so built"

# --- Install Python Package ---
echo ""
echo "Installing CodeGreen CLI..."

python3 -m pip install $PIP_FLAGS -e . 2>&1 | tail -1
unset PIP_BREAK_SYSTEM_PACKAGES

# --- Install Shared Library ---
echo ""
echo "Installing shared library..."
LIB_DIR="$PROJECT_ROOT/lib"

if [ -w /usr/local/lib ]; then
    cp "$LIB_DIR/libcodegreen-nemb.so" /usr/local/lib/
    ldconfig 2>/dev/null || true
    echo "[ok] Library installed to /usr/local/lib"
else
    # Ensure LD_LIBRARY_PATH includes our lib dir
    echo "[ok] Library at $LIB_DIR"
    if ! echo "$LD_LIBRARY_PATH" | grep -q "$LIB_DIR"; then
        echo "     Add to shell profile: export LD_LIBRARY_PATH=\"$LIB_DIR:\$LD_LIBRARY_PATH\""
    fi
fi

# --- Verify Installation ---
echo ""
echo "Verifying installation..."

if [ "$IS_VENV" -eq 1 ]; then
    INSTALL_BIN="$(python3 -c 'import sys; print(sys.prefix)')/bin"
else
    INSTALL_BIN="$(python3 -m site --user-base 2>/dev/null)/bin"
fi
export PATH="$INSTALL_BIN:$PATH"

if command -v codegreen &>/dev/null; then
    CG_PATH=$(which codegreen)
    echo "[ok] codegreen CLI: $CG_PATH"
    # Quick smoke test
    if codegreen --help &>/dev/null; then
        echo "[ok] CLI responds to --help"
    else
        echo "[!!] CLI installed but --help failed"
    fi
else
    echo "[!!] codegreen not in PATH"
    echo "     Add: export PATH=\"$INSTALL_BIN:\$PATH\""
fi

# --- RAPL Sensor Permissions ---
if [ "$SKIP_RAPL" -eq 0 ]; then
    echo ""
    echo "Setting up energy sensor permissions..."

    RAPL_OK=0
    if [ -r "/sys/class/powercap/intel-rapl:0/energy_uj" ]; then
        echo "[ok] RAPL sensors accessible"
        RAPL_OK=1
    elif [ "$(id -u)" -eq 0 ]; then
        ACTUAL_USER="${SUDO_USER:-$USER}"
        if [ "$ACTUAL_USER" != "root" ]; then
            echo "Setting up RAPL access for $ACTUAL_USER..."

            if ! getent group codegreen > /dev/null 2>&1; then
                groupadd codegreen
                echo "  [ok] Created 'codegreen' group"
            fi

            if ! id -nG "$ACTUAL_USER" | grep -qw codegreen; then
                usermod -aG codegreen "$ACTUAL_USER"
                echo "  [ok] Added $ACTUAL_USER to 'codegreen' group"
            fi

            RAPL_COUNT=0
            for f in /sys/class/powercap/intel-rapl*/energy_uj /sys/class/powercap/intel-rapl*/max_energy_range_uj; do
                [ -f "$f" ] && chgrp codegreen "$f" 2>/dev/null && chmod g+r "$f" 2>/dev/null && RAPL_COUNT=$((RAPL_COUNT+1))
            done

            UDEV_RULE='/etc/udev/rules.d/99-codegreen-rapl.rules'
            echo 'SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", GROUP="codegreen", MODE="0640"' > "$UDEV_RULE"
            udevadm control --reload-rules 2>/dev/null || true
            udevadm trigger 2>/dev/null || true

            if [ "$RAPL_COUNT" -gt 0 ]; then
                echo "  [ok] RAPL permissions set ($RAPL_COUNT files)"
                echo "  [ok] Udev rule: $UDEV_RULE"
                RAPL_OK=1
                echo ""
                echo "  Log out and back in for group membership to take effect"
            else
                echo "  [!!] No RAPL files found (CPU may not support RAPL)"
            fi
        fi
    else
        echo "[!!] RAPL not accessible. Fix with: sudo ./install.sh"
    fi
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Installation complete"
echo "==============================="
echo ""
echo "  Library: $PROJECT_ROOT/lib/libcodegreen-nemb.so"
echo "  CLI:     $(which codegreen 2>/dev/null || echo "$INSTALL_BIN/codegreen")"
echo "  Version: $(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])' 2>/dev/null || echo '0.1.0')"
echo ""
echo "Quick start:"
echo "  codegreen measure python script.py"
echo "  codegreen measure python script.py -g fine --json"
echo "  codegreen run -- python script.py"
echo "  codegreen run --budget 10.0 --json -- python train.py"
echo ""
echo "Upgrade: ./install.sh --upgrade"
echo "Docs:    https://smart-dal.github.io/codegreen/"
