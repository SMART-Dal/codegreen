# Core API

## NEMB C API

`libcodegreen-nemb` (`.so` on Linux) exports these C functions, defined in
`codegreen/measurement/src/nemb/codegreen_energy.cpp`. The C runtime header
`codegreen/instrumentation/language_runtimes/c/codegreen_runtime.h` declares
`nemb_initialize`, `nemb_probe` and `nemb_mark_checkpoint`; the Python
runtime binds the rest through ctypes. ABI version: 4.

| Function | Description |
|---|---|
| `int nemb_abi_version(void)` | ABI version of the library (4) |
| `int nemb_initialize(void)` | Load the config, initialize the selected providers and start the sampler thread. Returns 1 when energy is available, 0 otherwise (the reason is printed to stderr as `NEMB init failed: ...`) |
| `int nemb_probe(void)` | Initialize and self-test the providers as `nemb_initialize` would, then release them; no sampler, no markers, no exit report. Returns the number of usable providers |
| `int nemb_provider_status_json(char* buf, int size)` | `{"providers": [{"name", "status", "counter_group", "detail"}], "error"}` for the current selection; `status` is `initialized`, `unavailable`, `counter_already_read` or `not_tried` |
| `void nemb_mark_checkpoint(const char* name)` | Record a marker: the name plus `#inv_<N>_t<thread>` and a monotonic timestamp; no counter is read. Initializes the library on first use and registers the exit report |
| `int nemb_get_checkpoints_json(char* buf, int size)` | The markers and sampler statistics as JSON (the same object as the exit report) |
| `void nemb_report_at_exit(void)` | Write the result block (`--- CODEGREEN_RESULT_START ---` ... `--- CODEGREEN_RESULT_END ---`) to the copy of stdout taken at initialization; registered with `atexit` |
| `int nemb_read_current(double* energy_j, double* power_w)` | Synchronous reading: cumulative energy (J) and power (W). Returns 1 on success, 0 when the read failed |
| `uint64_t nemb_start_session(const char* name)` | Read the counters and open a session (a `Session` task); returns its id |
| `int nemb_stop_session_v2(uint64_t id, double* energy_j, double* power_w, double* duration_s, char* json_buf, int json_size)` | Close a session: energy, average power, duration and the per-domain energy as JSON, in one locked operation |
| `int nemb_stop_session(uint64_t id, double* energy_j, double* power_w)` | `nemb_stop_session_v2` without duration and domains |
| `int nemb_get_domain_energy_json(char* buf, int size)` | Per-domain energy of the last stopped session |
| `int nemb_get_time_series_json(char* buf, int size, uint64_t since_ns)` | Sampler readings after `since_ns` as a JSON array of `{t_ns, energy_j, power_w, domain_j, domain_w}` |
| `int nemb_set_measurement_interval_ms(int ms)` | Change the sampler period at run time |
| `int nemb_set_buffer_size(int n)` | Change the ring-buffer capacity; shrinking keeps the newest readings and marks the buffer wrapped |

Functions that fill a buffer return the bytes written, or a negative number
whose magnitude is the size needed when the buffer is too small. Domain
energies are signed; a negative value signals a failed read and must be
treated as invalid, not as 0.

A process created by `fork()` stops measuring: a `pthread_atfork` handler
turns every call in the child into a no-op, so only the parent reports.

The provider selection comes from `CODEGREEN_PROVIDERS` (comma-separated
groups of `|`-separated alternatives, for example `intel_rapl|amd_rapl`) and
the configuration from `CODEGREEN_CONFIG`; see the
[Configuration API](config.md).

## Language runtimes

| Language | Runtime | How it reaches NEMB |
|---|---|---|
| Python | `language_runtimes/python/codegreen_runtime.py` | ctypes; also hosts `Session`, `Monitor` and the validity rules ([Python API](python.md)) |
| C | `language_runtimes/c/codegreen_runtime.h` | `codegreen_checkpoint(id, name, type)` macro calling `nemb_mark_checkpoint` |
| C++ | `language_runtimes/cpp/codegreen/runtime.hpp` | `CodeGreen::checkpoint(id, name, type)` calling `nemb_mark_checkpoint` |
| Java | `language_runtimes/java/codegreen/runtime/` | `CodeGreenRuntime` (JNI, used by `measure`) and `CodeGreenStandaloneRuntime` (no JNI, used by `project`; polls the RAPL files itself) |

The paths are relative to `codegreen/instrumentation/`.

## Result block

The exit report and `nemb_get_checkpoints_json` return one object:

```json
{"measurements": [
  {"checkpoint_id": "enter:main:function_enter_main_8_1#inv_1_t15540708132652139232",
   "timestamp": 37132208765435856, "joules": 2.526685902262177, "watts": 0.12192525190311514,
   "ri": 2, "clamp": "none", "provider_j": {"intel_rapl": 2.526685902262177}}
 ],
 "sampler": {"interval_ms": 10, "buffer_capacity": 100000, "readings": 78, "...": "..."}}
```

Each marker carries `checkpoint_id`, `timestamp` (monotonic ns), `joules`
(cumulative energy interpolated at the timestamp), `watts`, `ri` (reading
index), `clamp` and `provider_j` (per-provider energy). The fields are
described under [Auto-instrumenter output format](python.md#auto-instrumenter-output-format)
and the `sampler` fields under
[Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity).
The Python runtime adds `meta` and `validity` to the block it writes.
