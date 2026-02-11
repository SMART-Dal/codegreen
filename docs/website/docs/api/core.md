# Core API

## NEMB C API

The Native Energy Measurement Backend exposes a C API via `libcodegreen-nemb.so`:

| Function | Signature | Description |
|----------|-----------|-------------|
| `nemb_initialize()` | `int nemb_initialize()` | Initialize providers and start background polling. Returns 1 if available. |
| `nemb_mark_checkpoint(name)` | `void nemb_mark_checkpoint(const char* n)` | Record a timestamp marker (~100ns). Auto-initializes on first call. |
| `nemb_read_current(&e, &p)` | `int nemb_read_current(double* e, double* p)` | Read current energy (J) and power (W). |
| `nemb_start_session(name)` | `uint64_t nemb_start_session(const char* n)` | Start a named measurement session. Returns session ID. |
| `nemb_stop_session(id, &e, &p)` | `int nemb_stop_session(uint64_t i, double* e, double* p)` | Stop session, get energy delta and avg power. |
| `nemb_get_checkpoints_json(buf, size)` | `int nemb_get_checkpoints_json(char* b, int m)` | Get checkpoint data as JSON into buffer. |
| `nemb_report_at_exit()` | `void nemb_report_at_exit()` | Print all checkpoint data to stdout (called via `atexit`). |

Fork safety is handled via `pthread_atfork` -- forked children skip all NEMB calls.

## Python Runtime

`src/instrumentation/language_runtimes/python/codegreen_runtime.py`

```python
from codegreen_runtime import checkpoint

# Called by instrumented code at function boundaries
checkpoint(checkpoint_id="1", name="my_function", checkpoint_type="enter")
# ... function body ...
checkpoint(checkpoint_id="2", name="my_function", checkpoint_type="exit")
```

The runtime uses ctypes to call into `libcodegreen-nemb.so`. Measurements are automatically reported at process exit via `atexit`.

## Output JSON Format

The `atexit` handler prints to stdout:

```json
{"measurements": [
  {
    "checkpoint_id": "enter:main:1#inv_1_t18236915910307559997",
    "timestamp": 13973110277836545,
    "joules": 6.80131,
    "watts": 0.758563
  }
]}
```

The `nemb_get_checkpoints_json()` buffer API uses the key `"checkpoints"` instead of `"measurements"`.

### Field Reference

- `checkpoint_id`: `{type}:{function_name}:{id}#inv_{N}_t{thread_id}`
- `timestamp`: Nanoseconds (clock source dependent)
- `joules`: Cumulative energy at this checkpoint
- `watts`: Instantaneous power at this checkpoint
