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

Pre-built wheels available for Linux x86_64 and macOS ARM64 (Apple Silicon). Includes the native NEMB energy measurement backend.

### From source (recommended for development)

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh

# Linux: RAPL sensor access (one-time, requires sudo):
sudo ./install.sh   # or: sudo codegreen init-sensors

# macOS: no setup needed, energy measurement works out of the box
```

### Platform support

| Platform | pip install | Energy measurement | Backend |
|----------|------------|-------------------|---------|
| Linux x86_64 (Intel) | Pre-built wheel | Full (PKG, core, iGPU, DRAM) | RAPL via NEMB |
| Linux x86_64 (AMD) | Pre-built wheel | Full (PKG, no DRAM counter) | RAPL via NEMB |
| macOS ARM64 (Apple Silicon) | Pre-built wheel | Full (CPU, GPU, ANE, DRAM) | IOReport + kpc via NEMB |
| macOS Intel | From source | Full | IOReport via NEMB |
| Windows 11 (Intel) | From source | Full (PKG, core, iGPU, DRAM) | EMI via intelpep.sys |
| Windows 11 (AMD) | From source | Unverified | EMI may not expose AMD RAPL |
| NVIDIA GPU (any OS) | Automatic | Full (cumulative mJ) | NVML |
| Other | From source | Time-only | Fallback |

### Requirements

- Python 3.9+
- Linux: kernel 5.0+, Intel/AMD CPU with RAPL support
- macOS: Apple Silicon (M1-M5) or Intel, no setup needed
- Windows 11: Intel/AMD CPU (EMI via inbox intelpep.sys driver, zero install)
- Source builds: CMake 3.16+, C++17 compiler

## Usage

### Measure energy of any command

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

### Manual measurement from Python (Session API)

For span-based measurement of arbitrary code regions, import `codegreen.Session` directly — no CLI, no AST instrumentation:

```python
import codegreen

with codegreen.Session("training-run") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        model.fit(...)
    with s.task("eval"):
        score = model.evaluate(...)
# writes codegreen_<pid>.json with per-task energy + per-domain breakdown
```

Time-series sampling for power-vs-time plots (area under curve = energy):

```python
with codegreen.Session("infer", record_time_series=True) as s:
    with s.task("batch1"):
        run_inference()
    s.export_plot("infer.html")   # interactive Plotly chart
```

The Session API uses the same NEMB backend as the CLI (RAPL/NVML/IOReport), supports nested + concurrent tasks, and degrades gracefully if the native library is unavailable. See [API → Python](docs/website/docs/api/python.md) for the full reference.

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

Adding a new language requires only a JSON config file in `codegreen/instrumentation/configs/` plus the tree-sitter grammar. No Python code changes needed.

Currently supported: Python, C, C++, Java. JavaScript config exists but is not yet exposed via CLI.

## Benchmarking

```bash
# Compare CodeGreen accuracy against perf RAPL ground truth
codegreen benchmark --suite benchmarksgame -l python --reps 5

# Run PerfOpt Java benchmark suite (JMH, original vs patched comparison)
codegreen benchmark --suite perfopt --dataset-dir /path/to/PerfOpt --jars-dir /path/to/jars

# Generate comparison artifacts for documentation
bash scripts/generate_comparison_artifacts.sh docs/benchmarks/
```

## Energy Flow Graph (EFG)

CodeGreen includes an Energy Flow Graph module (`codegreen/analysis/cfg/`) that builds energy-annotated control flow graphs from source code:

```python
from codegreen.analysis.cfg.builder import build_per_method_cfgs
from codegreen.analysis.cfg.energy_flow import build_efg, efg_to_dot, efg_to_text

cfgs = build_per_method_cfgs(java_source_code)
efg = build_efg(cfg_nodes, cfg_edges, "ClassName.method", "File.java", codegreen_data)
print(efg_to_text(efg))  # compact format for LLM prompts
```

Features: Ball & Larus branch heuristics, SCC-based hot path computation, three-level accuracy annotations (MEASURED/ESTIMATED/INFERRED), configurable via `EFGConfig`.

## Architecture

- **C++ NEMB backend**: platform-aware energy measurement (RAPL on Linux, IOReport on macOS, EMI on Windows), sub-microsecond timestamping, background polling with lock-free ring buffers
- **Python instrumentation**: tree-sitter AST analysis, config-driven checkpoint insertion
- **Energy Flow Graph**: CFG + energy annotation for path-dependent analysis
- **Benchmark harness**: multi-suite support (benchmarksgame, PerfOpt), statistical analysis with t-distribution CI, IQR outlier detection, profiler comparison

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
@article{rajput2026codegreen,
  title={CodeGreen: Towards Improving Precision and Portability in Software Energy Measurement},
  author={Rajput, Saurabhsingh and Sharma, Tushar},
  journal={arXiv preprint arXiv:2603.17924},
  year={2026}
}
```

## License

MPL-2.0 License - see [LICENSE](LICENSE) file.

**Docs**: [smart-dal.github.io/codegreen](https://smart-dal.github.io/codegreen/)
