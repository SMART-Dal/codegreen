# Configuration Reference

Every key a user may want to set, with its default from the bundled
`codegreen/config.json`. Put only the keys you change in
`~/.codegreen/config.json` (or a file named by `--config` /
`CODEGREEN_CONFIG`); the bundled file supplies the rest. How the file is found
and passed to measured processes, and the environment variables, are in the
[Configuration API](../api/config.md). For a first setup see
[Configuration](../getting-started/configuration.md).

Keys are written as dotted paths: `measurement.default_sensors` is
`{"measurement": {"default_sensors": ...}}`.

## Sensor selection

| Key | Default | Description |
|---|---|---|
| `measurement.default_sensors` | `"all"` | Sensors measured when `--sensors` is not given: `"all"`, or a list of `sensor_providers` keys such as `["rapl"]` |
| `measurement.sensor_providers` | `rapl`: `[intel_rapl, amd_rapl]`, `amd_cpu`: `[amd_rapl]`, `nvidia`: `[nvidia_gpu]`, `amd_gpu`: `[amd_gpu]` | Sensor name (the `--sensors` choices) to NEMB provider alternatives |
| `measurement.nemb.providers.<name>.enabled` | `true` | `false` removes provider `intel_rapl`, `amd_rapl`, `nvidia_gpu` or `amd_gpu` from every selection |
| `measurement.nemb.providers.intel_rapl.superset_zone` | `.*(psys|platform).*` | Powercap zone that contains all others; when one matches, the total is that zone alone |
| `measurement.nemb.providers.intel_rapl.disjoint_subzone` | `dram.*` | Sub-zones added to the top-level zones when no superset zone exists |

With `"all"`, every provider that initializes is summed, GPUs included (the
result then carries the warning `GPU_IN_TOTAL`). A list selects sensors
strictly: each sensor is satisfied by the first of its providers that
initializes, and a sensor with no working provider makes the measurement
invalid (`NEMB_INIT_FAILED`). The CLI and the Python runtime pass the
selection to the native library as `CODEGREEN_PROVIDERS`
(`intel_rapl|amd_rapl`, comma-separated per sensor). Disabling a provider
while `default_sensors` is `"all"` is rejected; list the sensors to measure
instead. `codegreen init` enables the providers that initialize on the host
and writes their sensors to `default_sensors`.

The two zone keys are full-name regular expressions, matched
case-insensitively, and apply to NEMB and to the Java poller of
`codegreen project`. Without a superset zone the total is every top-level zone
plus the sub-zones matching `disjoint_subzone`; other sub-zones (`core`,
`uncore`) lie inside their zone and are never summed. Zones that share a name
(the `dram` of each socket) are reported with the zone index appended
(`dram`, `dram-1`).

## Sampler

Keys under `measurement.nemb.coordinator`, read by the native library at
startup.

| Key | Default | Description |
|---|---|---|
| `measurement_interval_ms` | 10 | Background sampler period. Sets the resolution of `measure`, `project` and `Session` time series |
| `measurement_buffer_size` | 100000 | Ring-buffer capacity in readings |
| `auto_restart_failed_providers` | true | Restart a provider that fails repeatedly; a restart breaks the cumulative counter and makes the run invalid (`PROVIDER_READ_FAILED`) |
| `provider_restart_interval` | 5000 | Milliseconds between restart attempts (whole seconds are used) |
| `max_consecutive_failures` | 5 | Failed reads after which a provider is treated as failed (a GPU is then lost and its readings invalid) |
| `real_time_filtering` | false | Add `power_w_filtered` (an exponential moving average of `power_w`) to time-series samples |

The buffer holds `measurement_buffer_size` x `measurement_interval_ms` of
readings, 1000 s at the defaults. A longer measured process overwrites the
start of its run and is invalid (`BUFFER_WRAPPED`); raise the buffer or the
interval for long runs. A shorter interval gives finer per-function
resolution at the cost of more sampler wake-ups in the measured process.
`codegreen run` slows the sampler to `measurement.run_path.sampler_interval_ms`
(below), because it reads the counters directly at each run boundary.

## Measurement validity

Keys under `measurement.report.validity`: the thresholds of the
[validity verdict](cli-reference.md#exit-codes-and-measurement-validity).
A resolution is the slowest selected provider's update interval
(`sampler.providers[].update_interval_ms`, a hardware fact) or the sampler
interval, whichever is larger; there is no built-in RAPL constant.

| Key | Default | Description |
|---|---|---|
| `fail_on_invalid` | true | Exit 3 on an invalid `measure`, `run` or `project` result; `false` only reports |
| `min_window_samples` | 2 | Fewest sampler readings the root window must span (`TOTAL_BELOW_RESOLUTION`) |
| `median_gap_factor` | 1.5 | Median reading gap, in sampler intervals, above which the sampler is starved |
| `gap_policy.<marker_reads>.max_gap_factor` | 3.0 | Largest reading gap, in sampler intervals, above which the sampler is starved |
| `gap_policy.<marker_reads>.severity` | `interpolated`: `fatal`; `last_poll`: `warning` | `fatal` reports `SAMPLER_STARVED`; `warning` reports `SAMPLER_GAP` and widens the per-function resolution to the gap |
| `gap_policy.<marker_reads>.failed_read_severity` | `interpolated`: `warning`; `last_poll`: `fatal` | Severity of `PROVIDER_READ_FAILED` for failed sampler reads |
| `min_affinity_cpus` | 2 | Fewest CPUs the measured process may run on before the warning `AFFINITY_SINGLE_CPU` |
| `min_run_updates` | 10 | `run`: fewest resolutions per run (`RUN_BELOW_RESOLUTION`); `Session`: per task (`TASK_BELOW_RESOLUTION`) |
| `measured_min_factor` | 10 | Per-function `measured`: mean time per call in resolutions, and sampler readings in every call |
| `aggregate_min_factor` | 10 | Per-function `aggregate_only`: summed time in resolutions |
| `counter_check.tolerance` | 0.05 | Allowed disagreement, as a fraction of the power integral, between a provider's energy counter and its power integral (plus one update interval of energy per counter read) |
| `counter_check.severity` | `fatal` | Severity of `COUNTER_INTEGRAL_DIVERGED` |
| `provider_stall_resolutions` | 10 | A provider without new energy for longer than this many of its resolutions is `PROVIDER_STALLED` |

`gap_policy` is keyed by `sampler.marker_reads`: `interpolated` for NEMB
(markers are interpolated between readings, so a starved sampler corrupts
them) and `last_poll` for the Java standalone poller (markers take the last
polled value, so a gap only coarsens them, while a failed read leaves a stale
counter).

## Reports and toolchain

| Key | Default | Description |
|---|---|---|
| `measurement.report.max_checkpoints` | 2000000 | Markers NEMB stores per process; later ones are dropped and counted, and the run is invalid (`CHECKPOINT_CAP`) |
| `measurement.report.outlier_method` | `none` | `run`: `iqr_<k>` adds a `filtered` block computed over the runs inside the Tukey fences at k IQRs of energy; the primary statistics stay unfiltered |
| `measurement.report.noise_warning.within_task_power_cv_pct_threshold` | 10.0 | `Session` with `record_time_series`: power CV (%) within a task that raises a noise warning |
| `measurement.report.noise_warning.sampling_drop_ratio_threshold` | 0.2 | Same: fraction of missing samples that raises a noise warning |
| `measurement.report.noise_warning.quality_{excellent,good,moderate}_below_cv_pct` | 2.0, 5.0, 10.0 | CV bands of the task `quality` label (`high-noise` above) |
| `measurement.report.timeseries_clock_override` | `""` | Clock label written to `meta.timeseries.t_ns_clock` instead of the one detected for the machine |
| `measurement.run_path.sampler_interval_ms` | 1000 | Sampler period during `codegreen run` (kept at the coordinator interval when a selected provider's `boundary_source` is `integrated_power`) |
| `measurement.toolchain.c` / `.cpp` | `gcc` / `g++` | Compilers for instrumented C and C++ in `measure`; `CC` and `CXX` override them |
| `measurement.toolchain.prefer_dirs` | `["/usr/bin"]` | Directories searched for the compiler before `PATH` |

## Hotspot verdicts

`codegreen project` labels every function with the first verdict whose
thresholds it meets, in this order. Percentages are shares of the run's
attributed energy (the sum of exclusive energies), as in the report's
`energy_pct` and `exclusive_pct`; `self_ratio` is exclusive / inclusive
energy; `efficiency_ratio` is the function's energy per call over the median
energy per call of all functions.

| Verdict | Keys (`hotspot_taxonomy.<verdict>.*`) and defaults | Meaning |
|---|---|---|
| `wrapper` | `self_ratio_max` 0.2, `inclusive_pct_min` 5.0 | Large inclusive share, little work of its own |
| `TYPE_2_INEFFICIENT` | `exclusive_pct_min` 5.0, `efficiency_ratio_min` 3.0 | Energy per call far above the median |
| `TYPE_1_DIRECT` | `exclusive_pct_min` 10.0 | Large exclusive share: optimize the body |
| `TYPE_5_FREQUENCY` | `calls_min` 100000, `exclusive_pct_min` 3.0, `efficiency_ratio_max` 1.5 | Many cheap calls: batch or cache |
| `minor` | | None of the above |

## Monitor

Keys under `monitor`, read by `codegreen monitor` and `codegreen.Monitor`.
`SIGHUP` makes a running `codegreen monitor` re-read them and apply the
interval, rotation, in-memory and label limits. See
[Continuous Monitoring](continuous-monitoring.md).

| Key | Default | Description |
|---|---|---|
| `interval_ms_default` | 500 | Sample period when `--interval` / `interval_ms` is not given |
| `interval_ms_min` | 50 | Smallest allowed period (`ValueError` below it) |
| `interval_ms_warn_below` | 100 | Periods below this warn when the monitor runs without a duration |
| `max_samples_in_memory` | 10000 | In-memory sample deque size (`--max-in-memory`) |
| `rotate_mb_default` | 0 | Rotate the JSON-lines file above this many MB (0 = never) |
| `rotate_max_backups` | 5 | Rotated files kept |
| `attribution.mode_default` | `auto` | PID attribution backend: `auto`, `cgroup_v2`, `cgroup_v1`, `cpu_percent` |
| `attribution.cgroup_root` / `.cgroup_unified_root` | `/sys/fs/cgroup` / `/sys/fs/cgroup/unified` | cgroup mount points |
| `attribution.allow_cgroup_v1` | true | Let `auto` fall back to cgroup v1 |
| `annotation.max_labels` | 1000 | Distinct annotation labels before new ones collapse into `overflow_bucket` (0 = unlimited) |
| `annotation.overflow_bucket` | `__other__` | Label of the overflow bucket |
| `annotation.max_label_count` | 64 | Key-value labels allowed on one annotation |
| `annotation.summary_top_labels` | 50 | Labels listed in the summary's `per_label` |
| `annotation.listener_backlog` / `.recv_buf_bytes` | 16 / 65536 | Annotation socket listen backlog and receive buffer |
| `exporters.otlp.*` | `endpoint` `http://localhost:4317`, `protocol` `grpc`, `timeout_s` 10, `queue_size` 10000, `batch_size` 128, `export_interval_ms` 1000, `tls.{ca_file,cert_file,key_file}` empty; `headers` (a dict, not in the bundled file) | OTLP exporter (`--exporter otlp`) |
| `exporters.prometheus.*` | `listen_addr` `127.0.0.1`, `port` 9464, `endpoint_metrics` `/metrics`, `endpoint_health` `/healthz`, `auth_token` empty, `histogram_buckets_request_duration_seconds`, `redact_resource_attrs` `[]` | Prometheus exporter (`--exporter prometheus`) |

An exporter runs only when named with `--exporter` (or `exporters=` in the
Python API); its `enabled` key is not read. `exporters.remote_push` is a
placeholder with no implementation.

## Profiling metrics

Read by `codegreen.analysis` on profiled runs only, never on measured runs;
`codegreen capabilities` reports what each provider can do on the host.

| Key | Default | Description |
|---|---|---|
| `hw_counters.perf` | `perf` | `perf` binary for counter runs and event sampling; event names per architecture live in `codegreen/hw_events/*.json` |
| `hw_counters.attribution.<event>` | `cache_misses`: 10007 | Events sampled with call stacks (one extra unmeasured run each); the value is the events between samples |
| `gpu_metrics.series_interval_ms` | 50 | Device time-series period |
| `gpu_metrics.ncu.launch_count` | 200 | Kernels replayed for counters |
| `gpu_metrics.ncu.metrics` | `dram_pct`, `sm_pct`, `occupancy_pct`, `duration_ns` | Logical name to Nsight Compute metric |
| `gpu_metrics.roofline.latency_pct` | 30.0 | A kernel whose DRAM and SM shares both stay below it is latency or launch bound |
| `gpu_metrics.peaks` | not set | Per-device datasheet values `{device: {dram_gbps, fp32_tflops, source}}`, declared in the user config; roofline metrics raise without them |
| `languages.<lang>.line_sampler.rate_hz` | python 97, java 1003 | Line-sample rate |
| `languages.<lang>.line_sampler.flags` / `.feature_flags` / `.pass_flags` | | Sampler options: always on / switched on by feature name / one extra profiled run each (python: `native`; `idle`, `gil`) |
| `languages.<lang>.line_sampler.frame_re` / `.library_re` / `.irreducible_re` | | One collapsed frame (groups `func`, `file`, `line`), library files, frames a source rewrite cannot remove |
| `languages.python.line_sampler.binary` / `.record` | `py-spy` / `record --format raw --full-filenames` | py-spy binary and its arguments before `--rate` |
| `languages.python.line_sampler.interpreter_re` / `.alloc_*` | | Interpreter word of the workload command, and the tracemalloc allocation run |
| `languages.java.line_sampler.async_profiler` | `""` | async-profiler release directory (empty: `$CODEGREEN_ASYNC_PROFILER`); `flags` are JVM options loaded with the agent, `file_replace` maps class separators |

## Keys not read in 0.5.0

The bundled file also contains these sections, which no 0.5.0 code reads;
changing them has no effect: `paths.*`, `instrumentation.*`,
`languages.<lang>.{executable,compiler,compiler_flags,extensions,runtime_module}`
(compilers come from `measurement.toolchain`, file extensions from the
language configs in `codegreen/instrumentation/configs/`), `developer.*`,
`performance.*`, `security.*`, `measurement.nemb.enabled`,
`measurement.nemb.timing.*`, `measurement.nemb.accuracy.*`,
`measurement.nemb.coordinator.cross_validation`,
`measurement.report.run_id_bytes`, `monitor.annotation.socket_path_default`
and `monitor.annotation.max_label_chars`. `initialization.*` is written by
`codegreen init`. The `${USER_HOME}`, `${SYSTEM_TEMP}` and `${EXECUTABLE_DIR}`
placeholders in the bundled `paths.*` values are not expanded.

## Upgrading a pre-0.5 config

Provider blocks are keyed by NEMB registry name: rename `nvidia_nvml` to
`nvidia_gpu` and `amd_rocm` to `amd_gpu`; stale names are ignored. A user
config copied from an older release keeps working because the bundled
defaults fill in missing keys, but its stale values still apply, so the
simplest upgrade is to keep only the keys you changed:

```bash
mv ~/.codegreen/config.json ~/.codegreen/config.json.old
echo '{"measurement": {"default_sensors": ["rapl"]}}' > ~/.codegreen/config.json
```
