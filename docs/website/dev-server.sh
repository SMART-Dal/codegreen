#!/bin/bash
cd "$(dirname "$0")"

echo "Starting CodeGreen docs server at http://127.0.0.1:8000/"
echo "Press Ctrl+C to stop"
echo ""

if ! command -v mkdocs &> /dev/null; then
    pip install mkdocs mkdocs-material mkdocstrings[python] mkdocs-glightbox
fi

export SITE_URL="http://127.0.0.1:8000/"
mkdocs serve --dev-addr 127.0.0.1:8000
