# CodeGreen PyPI Publishing Guide

This guide explains how to build, test, and publish CodeGreen to PyPI.

## Prerequisites

### System Requirements
- Python 3.8+ with pip, setuptools, wheel, build
- CMake 3.16+
- C++ compiler (GCC, Clang, or MSVC)
- Git

### Platform-Specific Dependencies

**Ubuntu/Debian:**
```bash
sudo apt install cmake g++ libjsoncpp-dev libsqlite3-dev libcurl4-openssl-dev
pip install build wheel twine
```

**macOS:**
```bash
brew install cmake jsoncpp sqlite curl
pip install build wheel twine
```

**Windows:**
```bash
# Install Visual Studio Build Tools or Visual Studio
choco install cmake
pip install build wheel twine
```

## Local Testing

### 1. Test the Complete Pipeline
```bash
# Run the comprehensive test suite
python test_installation.py
```

This will:
- Build the C++ binary
- Create a Python wheel
- Test installation in a virtual environment
- Validate CLI functionality
- Test energy measurement

### 2. Manual Testing
```bash
# Build wheel manually
python build_wheels.py

# Test in virtual environment
python -m venv test_env
source test_env/bin/activate  # or test_env\Scripts\activate on Windows
pip install dist/*.whl

# Test CLI
codegreen --help
codegreen info
codegreen doctor
codegreen python examples/simple_test.py
```

## Cross-Platform Building

### Current Platform
```bash
python build_wheels.py
```

### All Platforms (requires CI/CD)
The GitHub Actions workflow builds for:
- Linux (ubuntu-latest)
- macOS (macos-latest) 
- Windows (windows-latest)

## Publishing to PyPI

### 1. Test PyPI (Recommended First)
```bash
# Upload to test.pypi.org
twine upload --repository testpypi dist/*

# Test installation from test PyPI
pip install -i https://test.pypi.org/simple/ codegreen
```

### 2. Production PyPI
```bash
# Create a release tag
git tag v0.1.0
git push origin v0.1.0

# This triggers GitHub Actions to build and publish automatically
# Or manually upload:
twine upload dist/*
```

### 3. Verify Publication
```bash
# Install from PyPI
pip install codegreen

# Test functionality
codegreen --help
codegreen info
```

## GitHub Actions Automation

The repository includes a complete CI/CD pipeline (`.github/workflows/build-and-publish.yml`) that:

1. **Builds wheels** for Linux, macOS, and Windows
2. **Tests installation** and basic functionality
3. **Publishes to Test PyPI** on version tags
4. **Publishes to PyPI** after test validation

### Required Secrets

Set these in your GitHub repository settings:

- `TEST_PYPI_API_TOKEN`: Token for test.pypi.org
- `PYPI_API_TOKEN`: Token for pypi.org

### Triggering a Release

```bash
# Create and push a version tag
git tag v0.1.0
git push origin v0.1.0
```

This automatically triggers the build and publish workflow.

## Version Management

Update version in these files before release:
- `pyproject.toml` (version field)
- `setup.py` (get_version function)
- `codegreen/__init__.py` (__version__)
- `CHANGELOG.md` (add new version entry)

## Troubleshooting

### Build Issues
```bash
# Clean build artifacts
rm -rf build dist *.egg-info codegreen/bin

# Rebuild from scratch
python build_wheels.py
```

### Binary Not Found
Ensure the C++ binary is built and copied to the correct location:
```bash
ls -la build/bin/codegreen
ls -la codegreen/bin/*/codegreen
```

### Wheel Issues
```bash
# Check wheel contents
python -m zipfile -l dist/*.whl

# Test wheel installation
pip install dist/*.whl --force-reinstall
```

### PyPI Upload Issues
```bash
# Check package metadata
twine check dist/*

# Upload with verbose output
twine upload --verbose dist/*
```

## Release Checklist

- [ ] Update version numbers in all files
- [ ] Update CHANGELOG.md
- [ ] Test locally with `python test_installation.py`
- [ ] Test on all target platforms
- [ ] Create and push version tag
- [ ] Verify GitHub Actions build succeeds
- [ ] Test installation from Test PyPI
- [ ] Verify final PyPI publication
- [ ] Test `pip install codegreen` works correctly
- [ ] Update documentation if needed

## Package Structure

The published package includes:
```
codegreen/
├── __init__.py              # Package metadata
├── cli.py                   # Main CLI interface
├── core/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   └── engine.py           # Measurement engine interface
├── utils/
│   ├── __init__.py
│   ├── binary.py           # Binary location utilities
│   └── platform.py        # Platform detection
└── bin/
    ├── linux-x86_64/       # Platform-specific binaries
    │   └── codegreen
    ├── macos-x86_64/
    │   └── codegreen
    ├── windows-x86_64/
    │   └── codegreen.exe
    ├── config/
    │   └── codegreen.json   # Default configuration
    └── runtime/
        └── codegreen_runtime.py  # Python runtime support
```

## Support

For issues with publishing or packaging:
1. Check the GitHub Actions logs
2. Verify all dependencies are installed
3. Test locally before publishing
4. Open an issue with detailed error information