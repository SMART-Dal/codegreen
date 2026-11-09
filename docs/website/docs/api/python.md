# Python API

`import codegreen` exposes `Session`, `TaskResult`, `task`, `Monitor`,
`annotate_request` and `__version__`.

| API | Use |
|---|---|
| [`codegreen.Session`](#manual-api-codegreensession) and [`@codegreen.task`](#manual-api-codegreensession) | Measure named regions of a Python program, in-process |
| [`codegreen.Monitor`](#codegreenmonitor) | Sample a running service or the whole host continuously |
| [`codegreen.annotate_request`](#annotate_request) | Attribute energy to individual requests through a `Monitor` |
| [Runtime module](#runtime-module-auto-instrumenter) | What `codegreen measure` and `project` inject into instrumented code |

All of them use the native backend `libcodegreen-nemb` and sum the providers
selected by `measurement.default_sensors` (there is no per-call sensor
argument; set it in the [config](../user-guide/configuration-reference.md#sensor-selection)
or with `CODEGREEN_CONFIG`). For worked examples see
[Python examples](../examples/python.md) and
[Example 03](../examples/03_session_api.md).

## Manual API: `codegreen.Session`

```python
import codegreen

with codegreen.Session("training-run") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        train_model()
```

A task can also be opened with `s.start_task(name)` / `s.stop_task(name)`,
or by decorating a function with `@codegreen.task()` (named after the
function's qualified name unless a name is given; calling it outside an
active session raises `RuntimeError`). Tasks nest; each thread keeps its own
task stack. When the session stops, the report is written to
`codegreen_<pid>.json` in the working directory if at least one task ran;
`stop()` also returns it as a dict, and `s.tasks` holds the `TaskResult`
objects.

### Constructor parameters

| Param | Default | Notes |
|---|---|---|
| `name` | `"default"` | Session name, written to `meta.session_name` |
| `output_file` | `codegreen_<pid>.json` | Output path; a path ending in `.csv` selects CSV (one row per task, appended) |
| `output_format` | `"auto"` | `"auto"` (from the extension, else JSON), `"json"`, `"csv"` or `"none"` (no file) |
| `save_to_file` | `True` | `False` writes no file |
| `warn_on_concurrent` | `True` | Warn when another CodeGreen process is active on the host (the counters are system-wide) |
| `record_time_series` | `False` | Record the sampler's readings for every task |
| `buffer_samples` | `None` | Override the native ring-buffer size (`measurement_buffer_size`, 100000 readings) |
| `sample_interval_ms` | `None` | Override the sampler period for this process (`measurement_interval_ms`, 10 ms) |
| `sampling_mode` | `"fixed"` | Only `"fixed"` is implemented |

### Report

Top-level keys: `meta`, `tasks`, `totals`, `sampler`, `validity`. A real
report (one task, `default_sensors: ["rapl"]`, AMD EPYC 9554P), with `cwd`,
`argv`, `codegreen_env` and most of `sampler` removed:

```json
{
  "meta": {
    "schema_version": "1",
    "codegreen_version": "0.5.0",
    "run_id": "ae19c0a5b27c",
    "started_at": "2026-11-06T23:12:28.379344+00:00",
    "ended_at": "2026-11-06T23:12:28.744816+00:00",
    "duration_total_s": 0.365506,
    "hostname": "asgard",
    "pid": 2886208,
    "platform": "linux",
    "python_version": "3.13.12",
    "cpu_model": "AMD EPYC 9554P 64-Core Processor",
    "kernel": "Linux-5.15.0-139-generic-x86_64-with-glibc2.31",
    "measurement_quality": "ok",
    "domain_support": "full",
    "outlier_method": "none",
    "iso_timestamp_format": "rfc3339_utc",
    "started_at_local": "2026-11-06T19:12:28.379356-04:00",
    "ended_at_local": "2026-11-06T19:12:28.744831-04:00",
    "host_timezone": "AST",
    "nemb_abi_version": 4,
    "domain_topology": {
      "package-0": {"top_level": true, "kind": "cpu_package", "includes": ["core"]},
      "core": {"top_level": false, "kind": "nested", "includes": []}
    },
    "timeseries": {"enabled": false},
    "session_name": "demo"
  },
  "tasks": [
    {
      "name": "compute",
      "energy_j": 28.218922999999997,
      "avg_power_w": 77.26881657510587,
      "duration_s": 0.365204545,
      "started_at": 1794006748.3795133,
      "ended_at": 1794006748.7447863,
      "depth": 0,
      "parent": null,
      "domains": {"core": 0.007522, "package-0": 28.218923},
      "domains_power_w": {"core": 0.020596676856800892, "package-0": 77.26881657510587},
      "started_at_mono_ns": 37131825150185017,
      "ended_at_mono_ns": 37131825515459042,
      "timeseries": null,
      "noise": null,
      "valid": true,
      "invalid_reason": null,
      "shared_boundary": false
    }
  ],
  "totals": {
    "energy_j": 28.218922999999997,
    "duration_s": 0.365204545,
    "wall_duration_s": 0.365505576133728,
    "task_duration_s": 0.365204545,
    "gap_duration_s": 0.00023155113372802516,
    "concurrent_overlap_s": 0.0,
    "n_tasks": 1,
    "n_top_level_tasks": 1,
    "invalid_tasks": 0,
    "domains": {"core": 0.007522, "package-0": 28.218923},
    "domains_power_w": {"core": 0.020596676856800892, "package-0": 77.26881657510587},
    "sample_interval_ms": null,
    "worst_within_task_power_cv_percent": null,
    "noise_warnings": []
  },
  "sampler": {"interval_ms": 10, "buffer_capacity": 100000, "readings": 42, "marker_reads": "interpolated", "providers": ["..."]},
  "validity": {"status": "valid", "reasons": [], "detail": {}, "warnings": {}}
}
```

#### `meta`

`codegreen run --json` and the result block of instrumented runs carry the
same `meta` block.

| Field | Meaning |
|---|---|
| `schema_version` | Output schema version; changes on a breaking rename or removal |
| `codegreen_version` | Installed CodeGreen version |
| `run_id` | 12 hex characters, unique per process, for log correlation |
| `session_name` | The `Session` name; `null` for `codegreen run`, `auto_instrumentation` for instrumented runs |
| `started_at` / `ended_at` | RFC 3339 UTC timestamps with microseconds; use these for joins and sorting |
| `started_at_local` / `ended_at_local`, `host_timezone` | The same instants in the host's local time zone, for display |
| `duration_total_s` | Monotonic time from session start to report |
| `hostname`, `pid`, `platform`, `python_version`, `cpu_model`, `kernel`, `cwd`, `argv` | Host and process identity |
| `codegreen_env` | Every `CODEGREEN_*` environment variable |
| `measurement_quality` | `ok`, `no_tasks`, `no_backend`, `provider_read_failed`, `negative_energy`, `energy_zero`, `checkpoints_only` (instrumented runs), `no_energy` or `failed` (`codegreen run`) |
| `domain_support` | `full` (per-domain breakdown), `scalar_only` (total only) or `none` (no backend) |
| `outlier_method` | `measurement.report.outlier_method` (`none` or `iqr_<k>`), used by `codegreen run` |
| `iso_timestamp_format` | Format of `started_at` / `ended_at` |
| `nemb_abi_version` | ABI of the loaded native library (4 in 0.5.0) |
| `domain_topology` | Which domains are top-level and which lie inside another |
| `timeseries` | Whether time series were recorded, and their sample schema and clock |

#### `tasks[]` and `TaskResult` { #taskresult-fields }

| Field | Meaning |
|---|---|
| `name`, `depth`, `parent` | Task name, nesting depth (0 = top level) and the enclosing task's name |
| `energy_j` | Energy between the task's start and stop reads, summed over the selected providers |
| `avg_power_w` | `energy_j / duration_s` |
| `duration_s` | Monotonic duration |
| `started_at`, `ended_at` | Wall-clock POSIX seconds (display only) |
| `started_at_mono_ns`, `ended_at_mono_ns` | Monotonic timestamps, on the clock of `timeseries[].t_ns` |
| `domains`, `domains_power_w` | Energy (J) and average power (W) per domain |
| `timeseries` | The samples inside the task window (`record_time_series=True`; `null` otherwise, `[]` for a task shorter than one sample). A parent's samples include its children's |
| `noise` | Power variability of the task, from its time series |
| `valid`, `invalid_reason` | `valid` is `false` when the task's energy is not a measurement: `provider_read_failed` (a boundary read failed) or `negative_energy`. Such tasks are excluded from `totals` and counted in `totals.invalid_tasks`; their energy is not reported as 0 J |
| `shared_boundary` | A start or stop read happened while another task was open. A provider with a boundary energy counter (NVIDIA) then answers from its last counter read plus its power integral, because a counter read would discard the open task's energy; that task's energy from it is integrated power |

Domain energies are not disjoint: `package-0` includes `core`, while DRAM and
GPU domains are separate counters. `energy_j` sums only the top-level
domains, so `sum(domains.values())` is larger than `energy_j` whenever a
nested domain is present; `meta.domain_topology` says which is which.

#### `totals`

`energy_j` and `task_duration_s` (also `duration_s`) sum the valid top-level
tasks. `wall_duration_s` runs from `start()` to `stop()`; `gap_duration_s` is
the wall time outside every top-level task; `concurrent_overlap_s` is positive
when top-level tasks overlapped in different threads. `domains_power_w[d]` is
the domain's energy over the duration of the tasks that reported it.

#### `sampler` and `validity`

`sampler` is the native sampler's statistics, as in the CLI output.
`validity` is `{status, reasons, detail, warnings}`: `PROVIDER_READ_FAILED`
and `NEGATIVE_ENERGY` name excluded tasks; the provider checks of `run` apply
(`GPU_IN_TOTAL`, `GPU_READ_HELD`, `BOUNDARY_READ_HELD`,
`COUNTER_INTEGRAL_DIVERGED`, `PROVIDER_STALLED`); `TASK_POWER_INTEGRATED`
names tasks whose energy integrates sampled power and `TASK_BELOW_RESOLUTION`
tasks shorter than `min_run_updates` provider resolutions. `stop()` also
issues each reason and warning as a `RuntimeWarning` (`codegreen: CODE:
text`). The API never changes the exit code; check `validity` yourself. See
[Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity).

### Time series

With `record_time_series=True` each task carries the sampler's readings
inside its window. `meta.timeseries` describes them (`t_ns_clock` is
`clock_monotonic` on Linux). A real sample:

```json
{"t_ns": 37132889715889060, "energy_j": 4.018652, "power_w": 78.0526951593942,
 "domain_j": {"core": 0.001221, "package-0": 4.018652},
 "domain_w": {"core": 0.0209661320057171, "package-0": 78.0526951593942}}
```

| Key | Unit | Meaning |
|---|---|---|
| `t_ns` | ns | Monotonic timestamp of the reading (the clock of `started_at_mono_ns`) |
| `energy_j` | J | Cumulative energy of the selected providers since the backend started |
| `power_w` | W | Power at this reading |
| `domain_j` | J | Cumulative energy per domain |
| `domain_w` | W | Power per domain; providers without per-domain power leave the domain out rather than report 0 |

`meta.timeseries.sample_keys` lists `domains` where the samples carry
`domain_j` and `domain_w`.

The native ring buffer holds `measurement_buffer_size` readings (100000, or
1000 s at 10 ms). A drain thread copies new readings out every 0.5 s, faster
(down to 50 ms) when a drain finds the buffer more than half full and slower
(up to 2 s) after three nearly empty drains, and warns above 90 % with a
larger `buffer_samples` to use.

#### Noise and quality { #noise--quality-reporting }

With time series, every task carries a `noise` summary and `totals` a
roll-up:

```json
"noise": {"samples_captured": 33, "samples_expected": 34, "samples_expected_method": "observed_median",
          "drop_ratio": 0.0294, "power_mean_w": 77.5687, "power_std_w": 2.0381,
          "power_cv_percent": 2.627, "sample_interval_ms": 10, "quality": "good"}
```

`samples_expected_method` is `observed_median` (interval inferred from the
samples, with at least three) or `configured`. `quality` is `excellent`
(CV below 2 %), `good` (below 5 %), `moderate` (below 10 %) or `high-noise`.
A task with a CV of at least 10 % or a `drop_ratio` of at least 20 % is
appended to `totals.noise_warnings` and raises a `RuntimeWarning`. The
thresholds are in `measurement.report.noise_warning`. The drain thread runs
inside the measured process, so leave time series off for the most stable
totals.

### Power-vs-time plotting

`s.export_plot(path)` draws each task's power over time from its time series
(`record_time_series=True`). The format follows the extension: `.html`
(plotly) or `.png`, `.svg`, `.pdf` (matplotlib); without the library nothing
is written, and no warning is issued.

```python
with codegreen.Session("training", record_time_series=True) as s:
    with s.task("epoch1"): train_one_epoch()
    with s.task("epoch2"): train_one_epoch()
    s.export_plot("training.html")
```

The area under a task's curve approximates its `energy_j`; the exact value
is `energy_j`, which comes from the boundary reads.

### Behavior rules

- One active `Session` per process: constructing a second raises
  `RuntimeError` until the first is stopped.
- Stopping a task that is not the innermost open task of the thread raises
  `RuntimeError` naming the innermost one.
- A session that is never stopped is finalized at exit (and on SIGTERM or
  SIGINT): open tasks are closed innermost first and the report is written.
- Forked child processes do not measure; only the parent reports.
- Without the native library the session warns and records no energy; the
  program still runs.
- The counters are system-wide. Two CodeGreen processes measuring at the same
  time both include each other's energy; the constructor warns when it finds
  another live CodeGreen process (`$XDG_RUNTIME_DIR/codegreen-<uid>.pids`).

## `codegreen.Monitor`

Continuous sampler for an already-running service or the whole host;
`codegreen monitor` is a thin wrapper around it.

```python
import codegreen

m = codegreen.Monitor(interval_ms=200, output_file="energy.jsonl").start()
run_load_test()
summary = m.stop()
print(summary["total_joules"], summary["avg_watts"], summary["validity"]["status"])
```

The constructor parameters (`interval_ms`, `duration_s`, `pid`,
`include_children`, `output_file`, `max_samples_in_memory`, `rotate_mb`,
`listen_socket_path`, `attribution_mode`, `max_labels`, `exporters`,
`exporter_overrides`) default to the `monitor.*` keys of the config; they are
listed in [Continuous Monitoring: Python API](../user-guide/continuous-monitoring.md#python-api),
and the summary and JSON-lines records under
[Output](../user-guide/continuous-monitoring.md#output).

A failed first read raises `RuntimeError`. A failed sample read is recorded
as `{"type": "sample", "t": ..., "valid": false}` and reported as the warning
`SAMPLES_INVALID`; a failed final read is the reason `PROVIDER_READ_FAILED`.
Calling `start()` twice on one instance raises `RuntimeError`; monitors on
the same host each count the full system energy.

## `codegreen.annotate_request` { #annotate_request }

Context manager that opens a labelled span on a `Monitor` listening on a
Unix socket; each finished span is added to the monitor's `per_label[name]`.

```python
import codegreen

with codegreen.annotate_request("GET /search"):
    handle_search()
```

| Param | Default | Notes |
|---|---|---|
| `name` | required | Label to aggregate under |
| `labels` | `None` | Extra key-value labels (at most `monitor.annotation.max_label_count`) |
| `socket_path` | per-user default | `$XDG_RUNTIME_DIR/codegreen.sock`, else `/tmp/codegreen-<uid>/codegreen.sock`; matches `--listen-on-socket default` |
| `timeout_s` | `0.25` | Socket timeout for connect, send and receive |

Entering raises (for example `FileNotFoundError`) when no monitor listens on
the socket; wrap it if requests must not fail when the monitor is down. A
web-framework recipe is in [Example 08](../examples/08_monitor_socket.md).

## Runtime module (auto-instrumenter)

`codegreen/instrumentation/language_runtimes/python/codegreen_runtime.py` is
copied next to the instrumented code by `measure` and `project` and imported
as `codegreen_runtime`. Instrumented functions call:

```python
def checkpoint(checkpoint_id: str, name: str, checkpoint_type: str): ...
```

```python
def square_sum(n):
    _codegreen_rt.checkpoint('function_enter_square_sum_2_1', 'square_sum', 'enter')
    try:
        return sum(i * i for i in range(n))
    finally:
        _codegreen_rt.checkpoint('function_exit_square_sum_frame_2', 'square_sum', 'exit')
```

`checkpoint()` passes `"<type>:<name>:<id>"` to `nemb_mark_checkpoint`,
which appends `#inv_<N>_t<thread>` and records the timestamp; no counter is
read. `measure_checkpoint(checkpoint_id, checkpoint_type, name, line_number,
context)` is the lower-level call it delegates to.
`CODEGREEN_CHECKPOINT_THROTTLE_MS` drops repeated checkpoints (see
[Checkpoint throttling](../user-guide/energy-measurement.md#checkpoint-throttling)).

## Auto-instrumenter output format

At exit (or on SIGTERM / SIGINT) the runtime writes one result block to a copy
of stdout taken at import, so a workload that closes stdout does not lose
it. The block carries `meta`, `measurements`, `sampler` and `validity` (and
the session's report when a `Session` is active). Its markers and sampler are
those of `libcodegreen-nemb` ABI 4, the same object `nemb_get_checkpoints_json`
returns. Trimmed from a real `measure -g fine` run:

```
--- CODEGREEN_RESULT_START ---
{"meta": {...},
 "measurements": [
  {"checkpoint_id": "enter:main:function_enter_main_8_1#inv_1_t15540708132652139232",
   "timestamp": 37132208765435856, "joules": 2.526685902262177, "watts": 0.12192525190311514,
   "ri": 2, "clamp": "none", "provider_j": {"intel_rapl": 2.526685902262177}},
  {"checkpoint_id": "exit:main:function_exit_main_frame_10#inv_1_t15540708132652139232",
   "timestamp": 37132209525420989, "joules": 61.216009158970536, "watts": 74.33832834205687,
   "ri": 77, "clamp": "none", "provider_j": {"intel_rapl": 61.216009158970536}}],
 "sampler": {"interval_ms": 10, "interval_ms_min": 10, "interval_ms_max": 10, "buffer_capacity": 100000,
             "readings": 78, "wrapped": false, "rejected_readings": 0, "failed_reads": 0,
             "provider_restarts": 0, "dropped_checkpoints": 0, "first_ns": ..., "last_ns": ...,
             "median_gap_ns": 10073552, "max_gap_ns": 10077223, "affinity_cpus": 128,
             "sampler_affinity_cpus": 128, "marker_reads": "interpolated",
             "providers": [{"name": "intel_rapl", "hardware_type": "cpu", "energy_source": "counter",
                            "boundary_source": "counter", "update_interval_ms": 1, "counter_group": "cpu_package",
                            "rejected": 0, "held": 0, "boundary_held": 0, "boundary_held_max_ns": 0,
                            "readings": 78, "last_ns": ..., "max_stall_ns": 319411, "counter_check": {}}],
             "config_path": ".../codegreen/config.json"},
 "validity": {"status": "valid", "reasons": [], "detail": {}, "warnings": {}}}
--- CODEGREEN_RESULT_END ---
```

| Field | Meaning |
|---|---|
| `checkpoint_id` | `<type>:<name>:<id>#inv_<N>_t<thread>`: checkpoint type, function name, checkpoint id, invocation counter and thread |
| `timestamp` | Monotonic nanoseconds |
| `joules` | Cumulative energy interpolated at `timestamp`, the sum of `provider_j`; the difference between two markers is the energy of that window |
| `watts` | Power interpolated from the bracketing readings (the first reading has none, so the earliest markers read low) |
| `ri` | Index of the first sampler reading at or after the marker; the difference between two markers' `ri` is the number of readings inside that window |
| `clamp` | `none`, or `before_first` / `after_last` when the marker lies outside the sampled range (the run is then invalid) |
| `provider_j` | Interpolated cumulative energy per provider |
| `sampler` | Sampler statistics; fields listed under [Exit codes and measurement validity](../user-guide/cli-reference.md#exit-codes-and-measurement-validity) |

The Python runtime computes `validity` from in-process facts and the CLI adds
process-level reasons (exit code, timeout). NEMB's own block, written by C,
C++ and Java programs, has no `validity`; the CLI computes it with the same
`codegreen_runtime.measurement_validity`. A block without `sampler` comes
from a library older than ABI 4 and is reported as `STALE_LIBRARY`.

## Package layout

```
codegreen/
  cli/cli.py                         # Typer CLI
  config.json                        # bundled configuration
  instrumentation/
    language_engine.py               # Tree-sitter parsing and query matching
    ast_processor.py                 # checkpoint insertion
    configs/*.json                   # per-language instrumentation configs
    language_runtimes/
      python/codegreen_runtime.py    # ctypes bridge to NEMB, Session, Monitor, validity rules
      c/codegreen_runtime.h          # C checkpoint macro
      cpp/codegreen/runtime.hpp      # C++ checkpoint function
      java/codegreen/runtime/        # CodeGreenRuntime (JNI) and CodeGreenStandaloneRuntime
  analyzer/plot.py                   # --export-plot rendering
  analysis/                          # profiling metrics (counters, samplers, GPU)
  measurement/                       # NEMB C++ sources (libcodegreen-nemb)
```
