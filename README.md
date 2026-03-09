<p align="center">
  <img src="docs/website/docs/assets/codegreen_logo.svg#gh-light-mode-only" width="200" alt="CodeGreen Logo">
  <img src="docs/website/docs/assets/codegreen_logo_white.svg#gh-dark-mode-only" width="200" alt="CodeGreen Logo">
</p>

[![DOI](https://zenodo.org/badge/942273936.svg)](https://doi.org/10.5281/zenodo.18371771)

# CodeGreen - Garage for Energy Measurement and Optimization

CodeGreen is a comprehensive tool for fine-grained energy profiling and optimization of code. It provides real-time energy measurement during code execution, identifies energy hotspots, and offers optimization suggestions to reduce energy consumption.

## Installation

### From PyPI (recommended for users)

```bash
pip install codegreen
```

Requires Linux with RAPL support. The wheel includes the pre-built C++ measurement backend.

### From source (recommended for development)

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh

# For RAPL sensor access (one-time, requires sudo):
sudo ./install.sh   # or: sudo codegreen init-sensors
# Then log out and back in for group permissions
```

### Requirements

- Linux (kernel 5.0+, Ubuntu 20.04+, Debian 11+, Fedora 35+, MacOS)
- Python 3.9+
- CMake 3.16+, g++ 9+ (for source builds only)
- Intel or AMD CPU with RAPL support
- `perf` (for `codegreen run` and benchmark validation)

## Usage

### Measure energy of any command (like hyperfine, but for energy)

```bash
codegreen run -- python script.py
codegreen run --repeat 20 --warmup 3 -- ./my_binary arg1 arg2
codegreen run --budget 10.0 --json -- python train.py   # CI/CD gate
```

### Per-function energy profiling

```bash
# Coarse mode: total program energy
codegreen measure python script.py

# Fine mode: per-function energy breakdown
codegreen measure python script.py -g fine --json

# With energy timeline plot
codegreen measure python script.py -g fine --export-plot energy.html
```

### Static analysis (no execution)

```bash
codegreen analyze python script.py --save-instrumented
```

### Benchmark validation (against perf RAPL ground truth)

```bash
codegreen benchmark -p nbody spectralnorm -l python -r 5 --profilers codegreen perf
```

## Output formats

JSON (default for `--json`), CSV, Markdown table, and text summary. The JSON output is a comprehensive single source of truth containing system state, per-function energy, instrumentation points with AST-stable identifiers, and statistical analysis.

## Language support

Adding a new language requires only a JSON config file in `src/instrumentation/configs/` plus the tree-sitter grammar. No Python code changes needed.

Currently supported: Python, C, C++, JavaScript, Java.

## Architecture

- **C++ NEMB backend**: RAPL energy reading with sub-microsecond timestamping
- **Python instrumentation**: tree-sitter AST analysis, config-driven checkpoint insertion
- **Benchmark harness**: statistical analysis with t-distribution CI, IQR outlier detection, perf RAPL ground truth validation

## CI/CD integration

```bash
# Fail pipeline if energy exceeds budget
codegreen run --budget 10.0 --json -- python tests/benchmark.py
# Exit code 1 if mean energy > 10 Joules
```

## Upgrading

```bash
pip install --upgrade codegreen   # PyPI
# or
cd codegreen && git pull && ./install.sh --upgrade   # source
```

## Citation

```bibtex
@software{Rajput_CodeGreen_2026,
  author = {Rajput, Saurabhsingh},
  doi = {10.5281/zenodo.18371772},
  title = {{CodeGreen: Per-Function Energy Measurement for Multi-Language Software}},
  url = {https://smart-dal.github.io/codegreen/},
  version = {v0.2.0},
  year = {2026}
}
```

## License

MPL-2.0 License - see [LICENSE](LICENSE) file.

**Docs**: [smart-dal.github.io/codegreen](https://smart-dal.github.io/codegreen/)
