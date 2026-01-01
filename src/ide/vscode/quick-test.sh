#!/bin/bash

# Quick test script for CodeGreen VSCode Extension
# This script helps verify the extension setup and test files

echo "🧪 CodeGreen VSCode Extension - Quick Test"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "extension.js" ]; then
    echo "❌ Error: extension.js not found. Please run this from the extension directory."
    exit 1
fi

echo "✅ Extension files found"
echo ""

# Check CodeGreen CLI
echo "1️⃣ Checking CodeGreen CLI..."
if command -v codegreen &> /dev/null; then
    echo "   ✅ CodeGreen CLI found: $(which codegreen)"
    codegreen --help &> /dev/null && echo "   ✅ CodeGreen CLI is working"
else
    echo "   ⚠️  CodeGreen CLI not found in PATH"
    echo "   💡 Try: export PATH=\"\$HOME/.local/bin:\$PATH\""
    if [ -f "$HOME/.local/bin/codegreen" ]; then
        echo "   ✅ Found at: $HOME/.local/bin/codegreen"
    fi
fi
echo ""

# Check test files
echo "2️⃣ Checking test files..."
if [ -f "test_files/example.py" ]; then
    echo "   ✅ Python test file found: test_files/example.py"
else
    echo "   ❌ Python test file not found"
fi

if [ -f "test_files/example.js" ]; then
    echo "   ✅ JavaScript test file found: test_files/example.js"
else
    echo "   ❌ JavaScript test file not found"
fi
echo ""

# Test CodeGreen with sample file
echo "3️⃣ Testing CodeGreen CLI with sample file..."
if [ -f "test_files/example.py" ]; then
    export PATH="$HOME/.local/bin:$PATH"
    if command -v codegreen &> /dev/null; then
        echo "   Running: codegreen measure python test_files/example.py"
        codegreen measure python test_files/example.py 2>&1 | head -20
        echo ""
        echo "   ✅ CodeGreen CLI test completed"
    else
        echo "   ⚠️  Skipping CLI test (CodeGreen not in PATH)"
    fi
else
    echo "   ⚠️  Skipping CLI test (test file not found)"
fi
echo ""

# Check Node.js
echo "4️⃣ Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "   ✅ Node.js found: $NODE_VERSION"
    
    # Check if extension.js syntax is valid
    if node -c extension.js 2>/dev/null; then
        echo "   ✅ Extension syntax is valid"
    else
        echo "   ❌ Extension syntax error"
    fi
else
    echo "   ❌ Node.js not found"
fi
echo ""

# Summary
echo "📋 Summary"
echo "=========="
echo ""
echo "To run the extension:"
echo "  1. Open this directory in VSCode/Cursor:"
echo "     cd $(pwd)"
echo "     code ."
echo ""
echo "  2. Press F5 to launch Extension Development Host"
echo ""
echo "  3. In the new window, open:"
echo "     test_files/example.py"
echo ""
echo "  4. Run 'CodeGreen: Analyze Energy Consumption' from Command Palette"
echo "     (Ctrl+Shift+P or Cmd+Shift+P)"
echo ""
echo "📖 For detailed instructions, see: HOW_TO_RUN.md"
echo ""
echo "✅ Quick test completed!"
