#!/bin/bash

# CodeGreen Installation Script
# This script installs CodeGreen with proper permissions for energy monitoring

set -e

echo "🚀 CodeGreen Installation Script"
echo "================================"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root directly."
   echo "   Please run: sudo $0"
   exit 1
fi

# Check if we have sudo access
if ! sudo -n true 2>/dev/null; then
    echo "❌ This script requires sudo access to set up permissions."
    echo "   Please run: sudo $0"
    exit 1
fi

echo "✅ Running with sudo access"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# Step 1: Set up permissions
echo ""
echo "🔧 Step 1: Setting up energy monitoring permissions..."
"$SCRIPT_DIR/setup_permissions.sh"

# Step 2: Install Python dependencies
echo ""
echo "📦 Step 2: Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Installed dependencies from requirements.txt"
else
    echo "⚠️  No requirements.txt found, installing basic dependencies..."
    pip install typer rich pydantic psutil packaging
fi

# Step 3: Install the package
echo ""
echo "📦 Step 3: Installing CodeGreen package..."
if [ -f "pyproject.toml" ]; then
    pip install -e .
    echo "✅ Installed CodeGreen in development mode"
elif [ -f "setup.py" ]; then
    pip install -e .
    echo "✅ Installed CodeGreen in development mode"
else
    echo "❌ No pyproject.toml or setup.py found"
    exit 1
fi

# Step 4: Verify installation
echo ""
echo "🔍 Step 4: Verifying installation..."
if command -v codegreen >/dev/null 2>&1; then
    echo "✅ CodeGreen CLI is available"
    codegreen --version
else
    echo "⚠️  CodeGreen CLI not found in PATH"
    echo "   You may need to add ~/.local/bin to your PATH"
fi

echo ""
echo "🎉 Installation completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Log out and log back in (or restart) for group changes to take effect"
echo "   2. Test with: codegreen run --repeat 3 -- python3 -c 'sum(range(10**7))'"
echo ""
echo "🔍 To verify setup:"
echo "   - Check groups: groups"
echo "   - Check RAPL files: ls -la /sys/class/powercap/intel-rapl:0/energy_uj"
echo ""
echo "⚠️  Note: You may need to restart for group membership to take effect"
