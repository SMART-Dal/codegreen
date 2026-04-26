# Python API

CodeGreen exposes two Python entry points:

1. **`codegreen.Session`** — manual span-based measurement, imported and used directly in your code.
2. **CLI auto-instrumenter** — runs `codegreen measure ...` over a script, injects checkpoints automatically.

Both share the same NEMB C++ backend, the same JSON output envelope, and the same `libcodegreen-nemb.so` ABI (v2+). They can coexist in one process.

## Manual API: `codegreen.Session`

```python
import codegreen

with codegreen.Session("training-run") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        train_model()
```

By default, results are written to `codegreen_<pid>.json` in the working directory. CSV is opt-in (pass `output_file="x.csv"` or `output_format="csv"`). Pass `save_to_file=False` to suppress file output.

### Form 1 — context manager (recommended)

```python
with codegreen.Session("my-run") as s:
    with s.task("phase1"):
        ...
```

### Form 2 — explicit start/stop

```python
s = codegreen.Session("my-run").start()
s.start_task("phase1"); do_phase1(); s.stop_task("phase1")
report = s.stop()    # returns dict; writes file
```

### Form 3 — decorator

```python
@codegreen.task("inference")
def infer(x): ...

with codegreen.Session():
    infer(data)         # measured automatically
```

### Constructor parameters

| Param | Default | Notes |
|---|---|---|
| `name` | `"default"` | Session name written to output |
| `output_file` | `codegreen_<pid>.json` | Output path; CSV chosen automatically when path ends in `.csv` |
| `output_format` | `"auto"` | `"auto"` \| `"json"` \| `"csv"` \| `"none"`; `"auto"` sniffs from extension, defaults to JSON |
| `save_to_file` | `True` | Set `False` to suppress file writes entirely |
| `warn_on_concurrent` | `True` | Warn at construction if another codegreen process is active on the same host (RAPL is system-wide) |
| `record_time_series` | `False` | Capture sampled (timestamp, power, energy, per-domain) tuples for each task |
| `buffer_samples` | `None` | Power-user override of the C++ ring-buffer size; usually unnecessary because Python drain is adaptive |
| `sample_interval_ms` | `None` (uses `config.json`) | Per-session override of the sampler's measurement interval; routes to the existing `coordinator.measurement_interval_ms` field via `nemb_set_measurement_interval_ms` — no parallel state |
| `sampling_mode` | `"fixed"` | `"adaptive"` is reserved for a future runtime-rate-control mode; today only `"fixed"` is implemented |

### Output schema

```json
{
  "session_name": "training-run",
  "tasks": [
    {"name": "data_load", "depth": 0, "parent": null,
     "energy_j": 12.4, "avg_power_w": 4.0, "duration_s": 3.1,
     "started_at": 1714155600.123, "ended_at": 1714155603.234,
     "domains": {"package-0": 10.2, "core": 0.8, "gpu0": 1.4},
     "timeseries": [
       {"t": 20364878312447553, "j": 7.94, "w": 37.4,
        "d": {"core": 0.0018, "package-0": 7.92, "gpu0": 0.022}}
     ]}
  ],
  "totals": {"energy_j": 857.4, "duration_s": 123.1, "n_tasks": 2},
  "abi_version": 3
}
```

- `domains` — per-domain RAPL/NVML energy for the task, computed atomically with the session stop (ABI v2 — race-free under concurrent threads).
- `timeseries` — per-sample (`t`=CLOCK_MONOTONIC ns, `j`=cumulative joules, `w`=instantaneous watts, `d`={domain: joules per-interval}). Present only when `record_time_series=True` (ABI v3+).

### Power-vs-time plotting

`record_time_series=True` collects samples at the coordinator's configured rate (`config.json`'s `coordinator.measurement_interval_ms`, default 1 ms on this build). The `Session.export_plot(path)` helper renders a power-vs-time chart per task; area under the curve equals the task's energy.

```python
with codegreen.Session("training", record_time_series=True) as s:
    with s.task("epoch1"): train_one_epoch()
    with s.task("epoch2"): train_one_epoch()
    s.export_plot("training.html")    # Plotly (interactive)
    s.export_plot("training.png")     # Matplotlib (static image)
```

Numerically, integrating `w(t)` over a task's window with the trapezoidal rule recovers the NEMB-reported `energy_j` to within ~0.2% (verified on a 5 s task with ~4,800 samples).

### Time-series correctness for long tasks

The C++ sampling ring buffer is fixed-size (default 1000 samples ≈ 1 s window at 1 ms intervals). To prevent silent loss on long tasks, the Session runs a Python drain thread that pulls samples out faster than the buffer rotates. Drain is **adaptive**:

- starts at 0.5 s,
- halves to a 50 ms floor when buffer >50% saturated on a single drain pass,
- doubles to a 2 s ceiling when <10% for three consecutive drains,
- emits a warning at >90% saturation suggesting `buffer_samples` override.

Verified on a 30-second task with defaults only: 28,460 samples, full span, zero gaps >50 ms.

### Sampling rate

Pre-existing: `config.json`'s `coordinator.measurement_interval_ms` is the startup default (loaded by `nemb::ConfigLoader::load_config()`).

Per-session override: pass `sample_interval_ms=N` to `Session(...)` — it calls `nemb_set_measurement_interval_ms` which writes the **same** `config_.measurement_interval` field the sample loop reads. No parallel sampling-rate state, no duplicate config parsing.

### Behaviour rules

- **Single session per process.** Constructing a second `Session` while one is active raises `RuntimeError`.
- **Mismatched stops** raise `RuntimeError` with the actual innermost task name.
- **Forgotten `.stop()`** is recovered by an `atexit` hook — the file is still written, the JSON envelope still emitted.
- **Concurrent threads** can each maintain their own task stack (per-thread). `nemb_stop_session_v2` makes domain breakdown race-free.
- **Forked children** become no-ops automatically; only the parent process reports.
- **No NEMB lib loaded** (CodeGreen built without C++ backend) → Session degrades to a warning + zero-energy results, your program still runs.

### Multi-process / RAPL caveat

RAPL counters are **system-wide, not per-process**. If two CodeGreen sessions overlap in wall time on the same socket, both readings include the other's energy (double-counting). The Session constructor warns when it detects another live CodeGreen pid via `$XDG_RUNTIME_DIR/codegreen-<uid>.pids`. For benchmarks, run sequentially or accept "system energy during this window" semantics.

## Runtime Module (auto-instrumenter)

`src/instrumentation/language_runtimes/python/codegreen_runtime.py`

This module is injected into instrumented code automatically. It uses ctypes to call `libcodegreen-nemb.so`.

### checkpoint()

```python
def checkpoint(checkpoint_id: str, name: str, checkpoint_type: str):
    """Mark a checkpoint in the energy measurement stream."""
```

Called by instrumented code at function boundaries:

```python
from codegreen_runtime import checkpoint

checkpoint(checkpoint_id="1", name="my_function", checkpoint_type="enter")
# ... function body ...
checkpoint(checkpoint_id="2", name="my_function", checkpoint_type="exit")
```

Each call records a ~100ns timestamp signal. The NEMB backend tracks invocations automatically (`#inv_N` suffix).

### measure_checkpoint()

```python
def measure_checkpoint(checkpoint_id: str, checkpoint_type: str,
                       name: str, line_number: int, context: str):
    """Record a checkpoint marker with full metadata."""
```

Lower-level function with additional context. `checkpoint()` delegates to this.

## Output Format

At process exit (`atexit`), the runtime prints checkpoint data to stdout:

```
--- CODEGREEN_RESULT_START ---
{"measurements": [
  {"checkpoint_id": "enter:main:1#inv_1_t...", "timestamp": 13973..., "joules": 6.80, "watts": 0.76},
  {"checkpoint_id": "exit:main:2#inv_1_t...", "timestamp": 13973..., "joules": 8.91, "watts": 71.94}
]}
--- CODEGREEN_RESULT_END ---
```

The CLI parses this output to extract measurement results.

## CLI Usage

CodeGreen does not expose a Python decorator or programmatic API. All measurement is done via the CLI:

```bash
# Basic measurement
codegreen measure python script.py

# Fine granularity with visualization
codegreen measure python script.py -g fine --export-plot energy.html

# JSON output
codegreen measure python script.py --json

# Save instrumented code for inspection
codegreen analyze python script.py --save-instrumented --output-dir ./out
```

## Package Structure

```
src/
  cli/cli.py                    # Typer CLI (11 commands)
  instrumentation/
    engine.py                   # MeasurementEngine (orchestrates instrumentation)
    language_engine.py          # Tree-sitter parsing + query matching
    ast_processor.py            # Checkpoint injection into AST
    configs/*.json              # Language-specific instrumentation configs
    language_runtimes/
      python/codegreen_runtime.py   # Python ctypes bridge to NEMB
      java/CodeGreenRuntime.java    # Java JNI bridge to NEMB
  analyzer/
    plot.py                     # Plotly/matplotlib visualization
  measurement/src/nemb/
    codegreen_energy.cpp        # C API + EnergyMeter implementation
```
