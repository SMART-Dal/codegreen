# Changelog

## v0.1.0 (Current)

### Features

- Multi-language energy measurement: Python, C, C++, Java
- Tree-sitter based code instrumentation with config-driven language support
- NEMB C++ backend with Intel RAPL, NVIDIA NVML, AMD ROCm drivers
- Granularity control: coarse (main only) and fine (all functions) modes
- Interactive energy timeline visualization via `--export-plot` (Plotly HTML)
- Static plot export (PNG/PDF via matplotlib)
- Hotspot detection (>90th percentile functions)
- Benchmark suite comparing CodeGreen vs perf RAPL
- 11 CLI commands: measure, analyze, init, info, doctor, validate, config, init-sensors, measure-workload, benchmark, validate-accuracy
- Fork safety for multiprocessing programs (pthread_atfork)
- Dynamic buffer sizing for large checkpoint counts

### Architecture

- Signal-generator model: ~100-200ns checkpoint overhead (25-100x lower than synchronous reads)
- Background polling at 1ms with binary search + linear interpolation correlation
- Config-driven language extension via JSON (no core code changes needed)
