# Changelog

## v0.3.0 (Current)

### macOS Apple Silicon Support
- DarwinIOReportProvider: energy measurement via `libIOReport.dylib` (CPU, GPU, ANE, DRAM domains)
- DarwinKPCProvider: exact hardware perf counters via `kperf.framework` (~200ns per read, cycles/instructions/cache misses/branch misses)
- Per-channel IOReport unit handling (mJ for most channels, nJ for GPU Energy) via `IOReportChannelGetUnitLabel`
- PrecisionTimer: `mach_continuous_time` path for ARM generic timer (~42ns resolution, no kernel transition)
- Pre-built macOS ARM64 wheels on PyPI (no cmake/brew required for users)

### Platform-Aware Energy Backends
- NEMB-first backend selection: NEMB (in-process, zero file I/O) > perf (Linux) > powermetrics (macOS) > time-only
- Extensible backend registry: add new hardware support by subclassing `_EnergyBackend`
- `codegreen run` and `codegreen project` auto-detect best backend per platform

### Package and Build
- Graceful cmake failure on unsupported platforms (Python-only install with CLI, instrumentation, analysis)
- `.dylib` support in setup.py and pyproject.toml package_data
- Multi-arch CI/CD: Linux x86_64 + macOS ARM64 wheel builds and tests
- Auto-create GitHub Release on tag push after PyPI publish
- Robust path resolution: all `parents[N]` indexing replaced with consistent `pkg_root` pattern
- Config.json packaged inside wheel (fixes "Default configuration file not found")
- Version display reads from `__init__.__version__` (was hardcoded 0.1.0)

### Bug Fixes
- Fixed `src/` to `codegreen/` path references across all Python, C++, and CI files
- Fixed IOReport API flow: CopyChannelsInGroup -> CreateSubscription -> CreateSamples (3-step, not 2)
- Fixed Obj-C block captures (`__block` qualifier for mutated variables)
- Fixed `CLOCK_MONOTONIC_RAW` guards for macOS (doesn't exist on Darwin)
- Fixed CIBW inline Python indentation error in CI smoke tests
- Skip legacy `codegreen-core` and C++ binary on macOS (only NEMB needed)

## v0.1.0

### Features

- Multi-language energy measurement: Python, C, C++, Java
- Tree-sitter based code instrumentation with config-driven language support
- NEMB C++ backend with Intel RAPL, NVIDIA NVML, AMD ROCm drivers
- `codegreen run` command: measure energy of any shell command (like hyperfine for energy) with `--repeat`, `--warmup`, `--json`, and `--budget` flags
- CI/CD energy budget gating via `codegreen run --budget`
- Granularity control: coarse (main only) and fine (all functions) modes
- Multiple output formats: JSON, CSV, Markdown, text
- Interactive energy timeline visualization via `--export-plot` (Plotly HTML)
- Static plot export (PNG/PDF via matplotlib)
- Hotspot detection (>90th percentile functions)
- Benchmark suite: 0.03% error vs perf RAPL (binarytrees/18), 0.71% (spectralnorm/1000)
- Auto-repeat mode for short workloads in benchmark harness
- Checkpoint throttling via `CODEGREEN_CHECKPOINT_THROTTLE_MS` environment variable
- Dynamic RAPL domain enumeration with multi-socket support
- 12 CLI commands: measure, run, analyze, init, info, doctor, validate, config, init-sensors, measure-workload, benchmark, validate-accuracy
- Fork safety for multiprocessing programs (pthread_atfork)
- Dynamic buffer sizing for large checkpoint counts

### Architecture

- Signal-generator model: ~100-200ns checkpoint overhead (25-100x lower than synchronous reads)
- Background polling at 1ms with binary search + linear interpolation correlation
- Config-driven language extension via JSON (no core code changes needed)
