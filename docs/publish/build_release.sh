#!/bin/bash
set -e

echo "Building CodeGreen Release Artifacts"
echo "====================================="

VERSION=$(grep 'version = ' pyproject.toml | cut -d'"' -f2)
echo "Version: $VERSION"

echo ""
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info

echo ""
echo "Installing build dependencies..."
python3 -m pip install --upgrade build twine wheel setuptools

echo ""
echo "Building source distribution..."
python3 -m build --sdist

echo ""
echo "Building binary wheel..."
python3 -m build --wheel

echo ""
echo "Checking distributions..."
python3 -m twine check dist/*

echo ""
echo "Build complete!"
echo ""
ls -lh dist/
echo ""
echo "Next steps:"
echo "  Test: python3 -m twine upload --repository testpypi dist/*"
echo "  Publish: python3 -m twine upload dist/*"
