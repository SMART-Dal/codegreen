# Changelog

For the latest release notes, see [GitHub Releases](https://github.com/SMART-Dal/codegreen/releases).

## v0.3.16 (Current)

### NVML Runtime Loading
- NVML loaded via dlopen/LoadLibrary instead of link-time dependency (fixes `libnvidia-ml.so.1: cannot open shared object file`)
- Works on all platforms without NVIDIA drivers installed (no hard .so dependency)
- `CODEGREEN_NVML_PATH` env var for non-standard NVML locations
- Detailed error messages listing all searched paths when NVML not found
- Eliminates `HAVE_NVML` compile flag entirely -- provider always compiles, decides at runtime

## v0.3.15

### Crash Fixes
- Fix core dump when RAPL permission denied (C++ exception no longer crosses ctypes boundary)
- Fix `os.geteuid()` crash on Windows (AttributeError)
- Fix NEMB session leak on subprocess timeout (always calls `nemb_stop_session`)
- Fix random crash from unhandled `TimeoutExpired` in all measurement backends

### NVML / GPU
- Fix NVML never working: `HAVE_NVML` compile definition now passed to `codegreen-nemb` target
- Add Windows NVML search paths (`C:/Windows/System32`, CUDA toolkit)
- NVIDIA GPU detected and reported in `codegreen doctor`

### Measurement Accuracy
- Consistent `capture_output=True` across JSON and human modes (was 22% energy difference)
- RAPL provider skips inaccessible domains instead of failing entirely (partial access works)
- JSON output budget exit code fixed (was exit 0 even when exceeded)

### CLI Improvements
- `codegreen doctor` now checks NEMB library, energy backend, RAPL permissions, GPU
- `--include-warmup` flag: measure energy during warmup and include in results
- `--repeat` validation (must be >= 1)
- Permission check before measurement runs (fail fast with fix instructions)
- No silent fallbacks: refuses to run without real energy backend
- JSON output includes `backend`, `domains`, `cv_percent`, `power_watts`, `outliers_removed`
- JSON `command` field is now a list (preserves argument boundaries)
- Command grouping: Measurement / Setup / Diagnostics / Validation panels
- Shutdown message suppressed in non-debug mode

### Build & Packaging
- cmake errors now visible under pip install (stderr with captured build output)
- Python 3.14 classifier added
- Version single source of truth via `importlib.metadata`
- Config path alignment between Python CLI and NEMB C++ backend
- Production defaults: `debug_mode: false`, `verbose_logging: false`

### Documentation
- 57 documentation issues fixed across README, INSTALL, CITATION, config, help text
- License classifier corrected (MIT -> MPL-2.0)
- All broken `benchmark cpu_stress` references replaced with working commands
- JavaScript added to Language enum (analysis works; instrumented measurement WIP)

## v0.3.14

### Build
- Remove dead tree-sitter from CMake (fixes sdist build on Python 3.14+)
- Better build error messages in setup.py

## v0.3.13

### Diagnostics
- `--verbose` shows full NEMB init log, provider detection, load errors, alternate paths

## v0.3.12

### Fixes
- Verbose shows exact NEMB load error and searches alternate paths

## v0.3.11

### Diagnostics
- `--verbose`/`--debug` flag shows CPU model, cores, RAM, dependency versions, NEMB status, backend detection

## v0.3.10

### Energy Domain Accuracy
- Correct PSYS-aware domain summation: uses PSYS alone when present (was 82-91% overcount on Skylake+ laptops)
- Multi-socket support: all package-* and dram-* domains summed (was missing socket 1 on dual-socket)
- macOS power calculation uses only top-level domain deltas (was 67% overcount)
- Per-domain breakdown in `codegreen run` output: energy (J) + power (W) per hardware domain
- Structural hierarchy detection: sysfs path depth determines top-level vs sub-domain
- Dynamic channel normalization on macOS (no hardcoded if-else chain)
- Unknown future domains default to top-level (safe overcount, never silent drop)
- Negative energy delta clamping (handles counter reset/sleep)

### Output Quality
- CV (coefficient of variation) and quality rating (excellent/good/moderate/high noise)
- Per-domain energy and power breakdown with relative bar chart
- Noise warning with recommendation to increase repeats
- Domain values averaged across all runs (consistent with total energy)

### Windows 11 Support
- WindowsEMIProvider: RAPL energy via inbox `intelpep.sys` driver (PKG, PP0/cores, PP1/iGPU, DRAM)
- Zero driver install, HVCI-compatible, pre-built Windows x64 wheels on PyPI
- Verified on i7-1165G7 and i7-12700H

### Build & CI
- Pre-built wheels: Linux x64, Linux ARM64, macOS ARM64, Windows x64
- Legacy codegreen-core removed (2,565 lines, jsoncpp/curl/sqlite deps gone)
- Auto GitHub Release on tag push
- Python 3.9+ compatibility
- CodeCarbon and JoularJX profiler wrappers
- DaCapo and Renaissance benchmark suites

## v0.3.1

### Windows 11 Energy Measurement
- WindowsEMIProvider: RAPL energy via inbox `intelpep.sys` driver (PKG, PP0/cores, PP1/iGPU, DRAM)
- Zero driver install, HVCI-compatible, cumulative picowatt-hours via PDH Performance Counters
- Verified on i7-1165G7: idle 47W, load 80W, 4 RAPL domains
- PrecisionTimer: QueryPerformanceCounter path for Windows timestamps

### Fixes
- Python 3.9 compatibility: `from __future__ import annotations` in setup.py
- Removed legacy codegreen-core C++ code (2,565 lines deleted, moved to archive/)
- Removed jsoncpp, curl, sqlite build dependencies (only NEMB remains)
- CMakeLists.txt simplified: single `codegreen-nemb` target
- Version display reads from `__version__` (was hardcoded 0.1.0 in CLI)

## v0.3.0

### Cross-Platform Energy Measurement
- **macOS**: DarwinIOReportProvider via `libIOReport.dylib` (CPU, GPU, ANE, DRAM), DarwinKPCProvider via `kperf.framework` (~200ns exact hardware counters), per-channel unit handling (mJ/nJ via `IOReportChannelGetUnitLabel`), `mach_continuous_time` precision timer (~42ns)
- **Windows 11**: WindowsEMIProvider via PDH Energy Meter counters (RAPL via inbox `intelpep.sys`)
- **Linux**: IntelRAPLProvider, AMDRAPLProvider, NvidiaGPUProvider, AMDGPUProvider
- Pre-built macOS ARM64 wheels on PyPI

### Platform-Aware Energy Backends
- NEMB-first backend selection: NEMB (in-process, zero file I/O) > perf (Linux) > powermetrics (macOS) > time-only
- Extensible backend registry via `_EnergyBackend` subclassing
- `codegreen run` and `codegreen project` auto-detect best backend per platform

## v0.1.0

### Features

- Multi-language energy measurement: Python, C, C++, Java, JavaScript
- Tree-sitter based code instrumentation with config-driven language support
- NEMB C++ backend with Intel RAPL, NVIDIA NVML, AMD ROCm drivers
- `codegreen run` command: measure energy of any shell command with `--repeat`, `--warmup`, `--json`, and `--budget` flags
- CI/CD energy budget gating via `codegreen run --budget`
- Granularity control: coarse (main only) and fine (all functions) modes
- Multiple output formats: JSON, CSV, Markdown, text
- Interactive energy timeline visualization via `--export-plot` (Plotly HTML)
- Hotspot detection (>90th percentile functions)
- Benchmark suite: 0.03% error vs perf RAPL (binarytrees/18)
- 13 CLI commands
- Fork safety for multiprocessing programs (pthread_atfork)

### Architecture

- Signal-generator model: ~100-200ns checkpoint overhead (25-100x lower than synchronous reads)
- Background polling at 1ms with binary search + linear interpolation correlation
- Config-driven language extension via JSON (no core code changes needed)
