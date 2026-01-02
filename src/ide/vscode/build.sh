#!/bin/bash
# VSCode Extension Build Script

set -e

echo "📦 Building CodeGreen VSCode Extension..."

# Navigate to extension directory
cd "$(dirname "$0")"

# Install dependencies
echo "📦 Installing npm dependencies..."
npm install

# Compile TypeScript
echo "🏗️ Compiling TypeScript..."
npm run compile

echo "✅ VSCode Extension built successfully in out/ directory."
echo "You can now run it using F5 in VSCode or package it with vsce."