#!/bin/bash
cd "$(dirname "$0")"

echo "Starting CodeGreen docs server at http://127.0.0.1:8000/"
echo "Press Ctrl+C to stop"
echo ""

if ! command -v mkdocs &> /dev/null; then
    pip install mkdocs mkdocs-material mkdocstrings[python] mkdocs-glightbox
fi

# Local dev: temp config without site_url prefix and social plugin
sed 's|site_url:.*|site_url: ""|; /- social/d' mkdocs.yml > .mkdocs-dev.yml
trap 'rm -f .mkdocs-dev.yml' EXIT
mkdocs serve --dev-addr 127.0.0.1:8000 -f .mkdocs-dev.yml
