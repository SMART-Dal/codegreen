# Changelog

## v0.1.0 (Current)

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
