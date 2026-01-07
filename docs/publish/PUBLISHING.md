# CodeGreen Publishing Guide

## Distribution Methods

### 1. Source Installation (Current)
**Users:**
```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh
```

**Requirements:**
- Python 3.8+
- CMake 3.15+
- C++ compiler (gcc/clang)
- Build tools (make)

---

### 2. PyPI Distribution (Recommended)

**For Users:**
```bash
pip install codegreen
sudo codegreen init-sensors
```

**Publishing Steps:**

#### A. Build Source Distribution
```bash
python3 -m pip install build twine
python3 -m build --sdist
```

Creates: `dist/codegreen-0.1.0.tar.gz`

#### B. Build Binary Wheels (Platform-Specific)
```bash
python3 -m build --wheel
```

Creates: `dist/codegreen-0.1.0-cp311-cp311-linux_x86_64.whl`

**Note:** Binary wheels must be built on each target platform:
- Linux: `manylinux` Docker containers
- macOS: Native build on macOS
- Windows: Native build on Windows

#### C. Upload to PyPI
```bash
# Test PyPI first
python3 -m twine upload --repository testpypi dist/*

# Production PyPI
python3 -m twine upload dist/*
```

**Setup PyPI Account:**
1. Create account: https://pypi.org/account/register/
2. Create API token: https://pypi.org/manage/account/token/
3. Configure: `~/.pypirc`

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TESTPYPI-TOKEN-HERE
```

---

### 3. GitHub Releases (Recommended for Pre-releases)

**Create Release:**
```bash
# Tag version
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0

# Build artifacts
./build_release.sh

# Upload to GitHub Releases
gh release create v0.1.0 \
  --title "CodeGreen v0.1.0" \
  --notes "See CHANGELOG.md" \
  dist/codegreen-0.1.0.tar.gz \
  dist/*.whl
```

**Users Install:**
```bash
pip install https://github.com/SMART-Dal/codegreen/releases/download/v0.1.0/codegreen-0.1.0-cp311-cp311-linux_x86_64.whl
```

---

### 4. Conda/Conda-Forge (Future)

**For Complex Dependencies:**

Create `conda-recipe/meta.yaml`:
```yaml
package:
  name: codegreen
  version: 0.1.0

build:
  number: 0
  script: python -m pip install . -vv

requirements:
  host:
    - python
    - pip
    - cmake
    - make
  run:
    - python
    - typer
    - rich

test:
  commands:
    - codegreen --version
```

**Users:**
```bash
conda install -c conda-forge codegreen
```

---

### 5. System Packages (Future)

#### Homebrew (macOS/Linux)
```bash
brew install codegreen
```

#### APT (Debian/Ubuntu)
```bash
sudo apt install codegreen
```

---

## Recommended Release Strategy

### Phase 1: Development (Now)
- Git clone + ./install.sh
- GitHub issues for bug reports
- Documentation on GitHub Pages

### Phase 2: Beta Testing (1-2 months)
- PyPI TestPyPI releases
- Limited binary wheels (Linux x86_64)
- GitHub Releases for pre-releases

### Phase 3: Production (3-6 months)
- PyPI official releases
- Multi-platform wheels (Linux, macOS, Windows)
- Automated builds with GitHub Actions

### Phase 4: Ecosystem (6+ months)
- Conda-forge package
- Homebrew formula
- System packages (apt/yum)

---

## Automated Publishing with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  build-and-publish:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11']

    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install build twine

    - name: Build wheel
      run: python -m build --wheel

    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: python -m twine upload dist/*
```

---

## Checklist Before Publishing

- [ ] Update version in `pyproject.toml`
- [ ] Update CHANGELOG.md
- [ ] Test on clean system
- [ ] Build all wheels
- [ ] Test installation from wheel
- [ ] Update documentation
- [ ] Create git tag
- [ ] Upload to TestPyPI
- [ ] Test TestPyPI install
- [ ] Upload to PyPI
- [ ] Create GitHub Release
- [ ] Announce release
