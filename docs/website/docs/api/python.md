# Python API

CodeGreen is primarily used via CLI. The Python runtime module handles checkpoint communication with the NEMB C++ backend.

## Runtime Module

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
