#!/bin/bash

# CodeGreen Local Build Script
# Builds CodeGreen and creates symlink for easy CLI access

set -e

PROJECT_ROOT="/home/srajput/codegreen"
BUILD_DIR="$PROJECT_ROOT/build"
BINARY_PATH="$BUILD_DIR/bin/codegreen"
SYMLINK_PATH="$HOME/.local/bin/codegreen"

echo "🔨 Building CodeGreen..."
echo "========================"

# Navigate to project root
cd "$PROJECT_ROOT"

# Create and enter build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Configure with CMake
echo "📋 Configuring with CMake..."
if ! cmake .. > /dev/null 2>&1; then
    echo "❌ CMake configuration failed!"
    cmake ..
    exit 1
fi

# Build with make
echo "🛠️  Compiling CodeGreen..."
if ! make -j4 > /dev/null 2>&1; then
    echo "❌ Build failed!"
    make -j4
    exit 1
fi

# Verify binary was created
if [ ! -f "$BINARY_PATH" ]; then
    echo "❌ Binary not found at $BINARY_PATH"
    exit 1
fi

# Create symlink for CLI access
echo "🔗 Creating CLI symlink..."
mkdir -p "$(dirname "$SYMLINK_PATH")"
ln -sf "$BINARY_PATH" "$SYMLINK_PATH"

# Verify symlink works
if [ ! -x "$SYMLINK_PATH" ]; then
    echo "❌ Symlink creation failed"
    exit 1
fi

# Add ~/.local/bin to PATH if not already present
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "📝 Adding ~/.local/bin to PATH..."
    if ! grep -q 'export PATH=$HOME/.local/bin:$PATH' ~/.bashrc; then
        echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
        echo "   Added to ~/.bashrc"
    fi
    # Update PATH for current session
    export PATH="$HOME/.local/bin:$PATH"
    echo "   Updated PATH for current session"
fi

echo ""
echo "✅ Build completed successfully!"
echo "📊 CodeGreen CLI ready:"
echo "   • Binary: $BINARY_PATH"
echo "   • Symlink: $SYMLINK_PATH" 
echo "   • Usage: codegreen python3 script.py"
echo "   • Fallback: $BINARY_PATH python3 script.py"
echo ""
echo "🧪 Test it:"
echo "   codegreen python3 examples/python_sample.py"
echo "   # Or if symlink doesn't work:"
echo "   $BINARY_PATH python3 examples/python_sample.py"