#!/bin/bash

# CodeGreen Documentation Development Server
# This script starts a local MkDocs development server

echo "🚀 Starting CodeGreen Documentation Server..."
echo "📍 Server will be available at: http://127.0.0.1:8000"
echo "🔄 Auto-reload enabled - changes will be reflected automatically"
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

cd "$(dirname "$0")"

# Check if mkdocs is installed
if ! command -v mkdocs &> /dev/null; then
    echo "❌ MkDocs not found. Installing..."
    pip install mkdocs mkdocs-material mkdocstrings[python]
fi

# Start the development server
mkdocs serve --dev-addr 127.0.0.1:8000
