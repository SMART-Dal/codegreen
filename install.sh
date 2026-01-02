#!/bin/bash
# CodeGreen Installation Script
# Builds C++ binary, installs Python CLI, and validates installation

set -e

PROJECT_ROOT="$(pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
BINARY_PATH="$BUILD_DIR/bin/codegreen"

echo "CodeGreen Installation"
echo "====================="
echo "Project root: $PROJECT_ROOT"

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 8 ]; then
    echo "Error: Python 3.8+ required, found $PYTHON_VERSION"
    exit 1
fi
echo "Python $PYTHON_VERSION found"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Sync instrumentation files
echo "Syncing instrumentation files..."
mkdir -p bin/src/instrumentation bin/runtime bin/src/instrumentation/configs

# Copy instrumentation files to development directories
cp -u src/instrumentation/language_runtimes/python/codegreen_runtime.py bin/runtime/
cp -u src/instrumentation/bridge_analyze.py bin/src/instrumentation/
cp -u src/instrumentation/bridge_instrument.py bin/src/instrumentation/
cp -u src/instrumentation/language_engine.py bin/src/instrumentation/
cp -u src/instrumentation/ast_processor.py bin/src/instrumentation/
cp -u src/instrumentation/language_configs.py bin/src/instrumentation/
cp -u src/instrumentation/configs/*.json bin/src/instrumentation/configs/

# Clean Python cache
find bin/src/instrumentation -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find src/instrumentation -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "Instrumentation files synchronized"

# Build C++ components
echo "Building C++ components..."

# Clean and rebuild
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Configuring with CMake..."
if ! cmake .. -DCMAKE_BUILD_TYPE=Release; then
    echo "Error: CMake configuration failed"
    exit 1
fi

echo "Building project..."
if ! make -j$(nproc) > /dev/null 2>&1; then
    echo "Error: Build failed. Showing detailed output:"
    make -j$(nproc)
    exit 1
fi

# Verify binary was created
if [ ! -f "$BINARY_PATH" ]; then
    echo "Error: Binary not found at $BINARY_PATH"
    exit 1
fi

echo "C++ binary built successfully"

# Copy binary to development location
cd ..
cp "$BINARY_PATH" bin/
echo "Binary deployed to bin/"

# Install Python CLI package
echo "Installing Python CLI package..."
pip3 uninstall -y codegreen 2>/dev/null || true
pip3 install -e .

# Verify CLI installation
if ! python3 -c "from src.cli.cli import main_cli" 2>/dev/null; then
    echo "Error: Python CLI installation failed"
    exit 1
fi

# Setup PATH for this session
export PATH="$HOME/.local/bin:$PATH"

# Verify CLI command is available
if command -v codegreen >/dev/null 2>&1; then
    CLI_PATH=$(which codegreen)
    echo "CLI command found: $CLI_PATH"
else
    echo "Warning: CLI command not found in PATH"
    echo "Add $HOME/.local/bin to your PATH for permanent access"
fi

# Basic functionality tests
echo "Running basic tests..."

# Test CLI help
if timeout 10s codegreen --help >/dev/null 2>&1; then
    echo "CLI help test passed"
else
    echo "Warning: CLI help test failed"
fi

# Test binary execution
if [ -x "$BINARY_PATH" ]; then
    echo "Binary is executable"
else
    echo "Error: Binary is not executable"
    exit 1
fi

# Test a quick benchmark
echo "Testing CPU benchmark..."
BENCHMARK_OUTPUT=$(timeout 15s "$BINARY_PATH" benchmark cpu_stress --duration=2 2>&1 || echo "TIMEOUT_OR_ERROR")

if echo "$BENCHMARK_OUTPUT" | grep -q "Energy consumed:.*J" && echo "$BENCHMARK_OUTPUT" | grep -q "Average power:.*W"; then
    ENERGY=$(echo "$BENCHMARK_OUTPUT" | grep "Energy consumed:" | sed 's/.*Energy consumed: \([0-9.]*\).*/\1/')
    POWER=$(echo "$BENCHMARK_OUTPUT" | grep "Average power:" | sed 's/.*Average power: \([0-9.]*\).*/\1/')
    echo "Benchmark test passed: ${ENERGY}J consumed, ${POWER}W average power"
else
    echo "Warning: Benchmark test failed or timed out"
fi

# Check RAPL permissions
if [ -r "/sys/class/powercap/intel-rapl:0/energy_uj" ]; then
    echo "RAPL energy measurement available"
else
    echo "Warning: RAPL energy files not accessible (may need sudo for hardware access)"
fi

# Final summary
echo ""
echo "INSTALLATION COMPLETE"
echo "===================="
echo "Binary: $BINARY_PATH"
echo "CLI: $(which codegreen 2>/dev/null || echo $HOME/.local/bin/codegreen)"
echo ""
echo "Ready to use:"
echo "  codegreen --help"
echo "  codegreen info"
echo "  codegreen measure python script.py"
echo "  codegreen analyze python script.py"
echo ""
echo "If 'codegreen' command is not found, add to your shell:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""