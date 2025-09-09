#!/bin/bash

# CodeGreen VSCode Extension Build Script
# This script builds and packages the VSCode extension

set -e

EXTENSION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🔧 Building CodeGreen VSCode Extension"
echo "📁 Extension directory: $EXTENSION_DIR"

cd "$EXTENSION_DIR"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

echo "📦 Installing dependencies..."
npm install

echo "✅ JavaScript extension ready (no compilation needed)"

echo "🧪 Running tests..."
npm test

echo "✅ Extension built successfully!"
echo ""
echo "🚀 To test the extension:"
echo "   1. Press F5 in VSCode to launch extension development host"
echo "   2. Open a Python/JavaScript/TypeScript/Java/C++/C file"
echo "   3. Run 'CodeGreen: Analyze Energy Consumption' command"
echo ""
echo "📦 To package the extension:"
echo "   npm install -g vsce"
echo "   vsce package"
echo ""
echo "🎉 Extension is ready to use!"
