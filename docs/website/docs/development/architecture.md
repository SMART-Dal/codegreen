# Architecture

CodeGreen has three layers: a Python CLI, a Tree-sitter instrumentation
engine, and a C++ measurement backend (NEMB) that reads the hardware.

```
codegreen CLI (Typer)            codegreen.Session / Monitor (Python API)
        |                                   |
Instrumentation (Tree-sitter + language configs)
        |                                   |
Language runtimes (Python ctypes, C/C++ headers, Java)
        |
NEMB: libcodegreen-nemb (C++)
        |
Providers: RAPL (powercap, MSR), NVML, ROCm SMI, IOReport, EMI
```

## CLI

`codegreen/cli/cli.py` implements every command: `measure`, `analyze`,
`run`, `monitor`, `project`, `timeline`, `init`, `config`, `init-sensors`,
`info`, `capabilities`, `doctor`, `benchmark` and the hidden
`measure-workload`, `validate` and `validate-accuracy`. The validity rules
the CLI applies live in the Python runtime (`codegreen_runtime.py`), so the
CLI, `Session`, `Monitor` and instrumented programs share one policy.

## Instrumentation

- `instrumentation/language_engine.py` parses source with Tree-sitter and
  finds instrumentation points with the queries of the language config.
- `instrumentation/ast_processor.py` inserts the checkpoint calls, closing
  each frame on every exit path (`try`/`finally`, an RAII guard in C++,
  rewritten `return` statements in C).
- `instrumentation/configs/<language>.json` holds everything
  language-specific: node types, queries, checkpoint templates, insertion
  rules, entry points for coarse mode, and the `project_config` used by
  `codegreen project` (source patterns, build-system detection, runtime
  injection).

## NEMB backend

`codegreen/measurement/src/nemb/` builds `libcodegreen-nemb`:

| Component | File | Purpose |
|---|---|---|
| C API and `EnergyMeter` | `codegreen_energy.cpp` | Exported functions, markers, sessions, checkpoint correlation, result block |
| Coordinator | `core/measurement_coordinator.cpp` | Sampler thread, ring buffer of synchronized readings, provider restarts |
| Provider registry | `core/energy_provider.cpp` | Provider registration and selection (`CODEGREEN_PROVIDERS`, one provider per counter group) |
| Config loader | `config_loader.cpp` | Reads the active `config.json` |
| Providers | `drivers/intel_rapl_provider.cpp`, `amd_rapl_provider.cpp`, `nvidia_gpu_provider.cpp`, `amd_gpu_provider.cpp`, `darwin_ioreport_provider.cpp`, `darwin_kpc_provider.cpp`, `windows_emi_provider.cpp`, `arm_energy_provider.cpp` | One per energy source; the platform decides which are compiled |
| Counter manager | `hal/counter_manager.cpp` | Counter wrap-around handling |
| Timer | `utils/precision_timer.cpp` | Monotonic timestamps |

### Measurement flow

1. The first `nemb_mark_checkpoint` (or `nemb_initialize`) loads the config,
   initializes the selected providers and starts the sampler thread. The
   buffer is seeded with a synchronous reading.
2. The sampler reads every provider each `measurement_interval_ms` and
   stores the summed, per-provider and per-domain cumulative energy.
3. A checkpoint records a name and a timestamp only.
4. At exit, a final synchronous reading closes the buffer, each marker is
   interpolated between the two readings that bracket it, and the result
   block (markers plus sampler statistics) is written to a copy of stdout.
5. The CLI parses the block, replays the calls into inclusive and exclusive
   energy per function and computes the validity verdict.

`Session` tasks and `codegreen run` read the counters synchronously at each
boundary (`nemb_start_session` / `nemb_stop_session_v2`) instead of
interpolating. `Monitor` calls `nemb_read_current` on its own timer.

A forked child process detaches from NEMB (`pthread_atfork`) and reports
nothing.

## Project profiling

`codegreen project` composes the layers with your build: discover sources
with the language config's patterns, instrument them in place (backing up
the originals), inject the runtime, run `--build-cmd`, run `--run-cmd`
`--repeat` times, then restore the sources. Java uses
`CodeGreenStandaloneRuntime`, which polls the RAPL files from inside the JVM
and reports per-JVM aggregates; Python and C/C++ use NEMB as `measure` does.

## Visualization and analysis

`codegreen/analyzer/plot.py` renders `--export-plot` and
`Session.export_plot` after the measurement. `codegreen/analysis/`
(hardware counters, line and event samplers, GPU metrics) works on separate
profiled runs, never on measured ones. `codegreen timeline` puts a NEMB
time series, JFR events and a torch.profiler trace on one clock.
