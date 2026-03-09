# Architecture

CodeGreen is a 3-layer system: Python CLI, Tree-sitter instrumentation, and C++ NEMB backend.

## Overview

```
User CLI (Python/Typer)
    |
    v
Instrumentation Layer (Tree-sitter + language configs)
    |
    v
NEMB Backend (C++ shared library)
    |
    v
Hardware (RAPL, NVML, ROCm)
```

## Layer 1: CLI (`src/cli/`)

The command-line interface is built with Typer and Rich. It provides 12 commands (measure, run, analyze, init, info, doctor, validate, config, init-sensors, measure-workload, benchmark, validate-accuracy).

Key file: `src/cli/cli.py`

## Layer 2: Instrumentation (`src/instrumentation/`)

### Tree-sitter Engine

`language_engine.py` uses Tree-sitter grammars to parse source code into ASTs and identify function boundaries via query patterns.

### Config-Driven Design

Language support is defined by JSON configs in `src/instrumentation/configs/`:

- `python.json`, `c.json`, `cpp.json`, `java.json`

Each config specifies: function patterns, enter/exit templates, checkpoint call format. Adding a new language requires only a new grammar + JSON config.

### AST Processor

`ast_processor.py` traverses the parsed AST, matches instrumentation patterns, and generates instrumented source code with checkpoint calls injected at function boundaries.

## Layer 3: NEMB Backend (`src/measurement/src/nemb/`)

The Native Energy Measurement Backend is a C++ shared library (`libcodegreen-nemb.so`).

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Public API | `codegreen_energy.cpp` | C API: init, mark checkpoint, get results |
| Coordinator | `core/measurement_coordinator.cpp` | Orchestrates providers, circular buffer |
| Intel RAPL | `drivers/intel_rapl_provider.cpp` | Reads `/sys/class/powercap` |
| NVIDIA NVML | `drivers/nvidia_gpu_provider.cpp` | GPU power via NVML |
| AMD ROCm | `drivers/amd_gpu_provider.cpp` | AMD GPU power |
| Timer | `utils/precision_timer.cpp` | High-resolution timestamps |
| Counter Manager | `hal/counter_manager.cpp` | Wrapping counter handling |

### Measurement Flow

1. `nemb_initialize()` -- initializes providers, starts background polling thread
2. `nemb_mark_checkpoint(name)` -- records a timestamp marker (~100ns, auto-initializes on first call)
3. Background thread polls sensors at 1ms intervals into circular buffer
4. `nemb_report_at_exit()` -- prints correlated checkpoint data to stdout (called via `atexit`)
5. Output format: `{"measurements": [{"checkpoint_id": "...", "timestamp": ..., "joules": ..., "watts": ...}]}`

### Runtime Bridge

Language runtimes bridge instrumented code to the C++ backend:

- **Python**: `src/instrumentation/language_runtimes/python/codegreen_runtime.py` (ctypes to libcodegreen-nemb.so)
- **C/C++**: `src/instrumentation/language_runtimes/c/codegreen_runtime.h` (direct C API)
- **Java**: `src/instrumentation/language_runtimes/java/` (JNI bridge)

### Fork Safety

For multiprocessing programs, `pthread_atfork` handlers in `codegreen_energy.cpp` detach child processes from the parent's RAPL file descriptors.

## Layer 4: Visualization (`src/analyzer/`)

Post-measurement only. `plot.py` uses Plotly (HTML) or matplotlib (PNG/PDF) to render energy timelines. Zero overhead during measurement.

## Build System

```bash
cd build && cmake .. -DCMAKE_BUILD_TYPE=Release && make -j$(nproc)
```

Output: `lib/libcodegreen-nemb.so`

Python CLI: `pip install -e .` (entry point: `src.cli.entrypoint:main_cli_wrapper`)
