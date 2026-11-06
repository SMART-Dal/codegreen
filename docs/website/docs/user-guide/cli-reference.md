# CLI Reference

Complete reference for the `codegreen` command-line interface.

The CLI is grouped into four panels: **Measurement** (`measure`, `analyze`,
`run`, `monitor`, `project`, `timeline`), **Setup** (`init`, `config`,
`init-sensors`), **Diagnostics** (`info`, `doctor`), and **Validation**
(`benchmark`; `validate`/`validate-accuracy`/`measure-workload` are hidden
but still functional).

## Global Options

```bash
codegreen [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--debug, --verbose` | Enable verbose diagnostic output |
| `--config PATH` | Path to configuration file |
| `-v, --version` | Show version and exit |
| `--log-level [DEBUG\|INFO\|WARNING\|ERROR]` | Set logging level (default: INFO) |
| `--install-completion` | Install shell completion |
| `--show-completion` | Print shell completion script |
| `-h, --help` | Show help message |

## Commands

### `measure`

Instruments code, executes it, and measures energy consumption using hardware sensors.

```bash
codegreen measure [OPTIONS] LANGUAGE:{python|cpp|java|c|javascript} SCRIPT [ARGS]...
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file for results |
| `-s, --sensors [rapl\|nvidia\|amd_gpu\|amd_cpu]` | Sensors to measure (repeatable; the keys of `measurement.sensor_providers`). Default: `measurement.default_sensors` |
| `-p, --precision [low\|medium\|high]` | Measurement precision (default: high) |
| `-g, --granularity [coarse\|fine]` | Instrumentation level (default: coarse) |
| `--export-plot PATH` | Export energy timeline (HTML default, or PNG/PDF) |
| `-t, --timeout INTEGER` | Timeout in seconds |
| `--verbose` | Verbose output |
| `--json` | Output results in JSON format |
| `--no-cleanup` | Keep temporary files |
| `--instrumented` | Script is already instrumented |

**Granularity:**

- **coarse** (default): Instruments only the entry function's frame (`instrumentation_config.entry_points` in the language config, else the first frame-opening and last frame-closing point). Minimal overhead, gives total program energy.
- **fine**: Instruments all functions per language config. Per-function energy breakdown.

With `--json`, the output carries an `instrumentation_audit` block
(`prospects_detected`, `fine_runtime_checkpoints`, `fallback_to_coarse`,
optional `warning`). If a fine run captures fewer than two checkpoints (work
at module level or in child processes) and did not crash, it is re-measured at
coarse granularity so the report keeps whole-program energy; `granularity` in
the output then reads `coarse`. A failed or checkpoint-less run sets `error`.
Pass script arguments after the script (`codegreen measure cpp main.cpp 5000`).

**Sensors.** `--sensors` (or, without it, `measurement.default_sensors`) maps
each sensor to NEMB registry names through `measurement.sensor_providers` and
passes them to the measured process as `CODEGREEN_PROVIDERS`, one group per
sensor written as alternatives (`rapl` -> `intel_rapl|amd_rapl`: the first that
initializes). Only those providers are summed. A requested sensor whose
providers all fail to initialize makes the run invalid (`NEMB_INIT_FAILED`).
With the default `"all"`, every provider that initializes is summed; a total
that mixes GPU and CPU providers carries the warning `GPU_IN_TOTAL`. Use
`--sensors rapl` for CPU-only energy. The same option exists on `run`, and
`project` uses `measurement.default_sensors`.

**JSON output.** Besides `instrumentation_audit` and `error`:

- `summary`: `total_energy_j`, `wall_time_s`, `avg_power_w`,
  `checkpoint_count`, `energy_by_provider`, `providers`, `sensors_requested`,
  `exclusive_sum_j`, `exclusive_sum_ratio`, `overlapping_threads`.
- `per_function_energy`: per function `inclusive_j`, `exclusive_j`,
  `energy_j` (= inclusive), `wall_time_s`, `avg_power_w`, `calls`, `quality`.
  Every call on every thread is replayed. `quality` is the per-function
  verdict shared with `project` (see [Per-function quality](#per-function-quality)).
- `checkpoints`: the NEMB result block (`checkpoint_id`, `timestamp`,
  `joules`, `watts`, `ri`, `clamp`, `provider_j`).
- `sampler` and `validity`: see
  [Exit codes and measurement validity](#exit-codes-and-measurement-validity).
  `validity` is `null` when no energy backend is available.

An invalid measurement exits 3 with `success: false` and
`error: "invalid_measurement: CODE[,CODE]"`.

**Examples:**
```bash
# Basic measurement (coarse granularity)
codegreen measure python script.py

# Fine-grained with per-function breakdown
codegreen measure python script.py -g fine

# Export interactive HTML energy timeline
codegreen measure python script.py -g fine --export-plot energy.html

# Export static PNG plot (requires matplotlib)
codegreen measure python script.py -g fine --export-plot energy.png

# Multiple sensors with JSON output
codegreen measure python ml_train.py --sensors rapl nvidia --json

# C++ program with arguments
codegreen measure cpp main.cpp 5000

# Save results
codegreen measure python main.py -o results.json
```

### `run`

Measure energy consumption of any shell command with hardware-level precision via RAPL, NVML, or IOReport. No code instrumentation required.

```bash
codegreen run [OPTIONS] COMMAND...
```

Use `--` before commands that have their own flags; otherwise flags such as
`-c` or `-jar` are parsed as codegreen options and fail.

**Options:**

| Option | Description |
|--------|-------------|
| `-n, --repeat INTEGER` | Number of repetitions (default: 10) |
| `-w, --warmup INTEGER` | Warmup runs (default: 1) |
| `--include-warmup` | Measure energy during warmup and include in results |
| `--stdin TEXT` | Bind this file as the subprocess's stdin on every repeat (cat/hash/ETL workloads) |
| `--json` | Output results as JSON |
| `--budget FLOAT` | Energy budget in Joules; exits with error if mean exceeds budget |
| `--validate / --no-validate` | Execute the command once, unmeasured, before measuring (default: validate). A failing command is also caught by the first measured run |
| `--validate-timeout INTEGER` | Seconds allowed for the validation run (default: 300) |
| `--timeout INTEGER` | Per-run limit in seconds (default: none) |
| `-s, --sensors [rapl\|nvidia\|amd_gpu\|amd_cpu]` | Sensors summed into the energy (default: `measurement.default_sensors`) |

**Output includes:**

- Mean energy (Joules) with standard deviation
- 95% confidence interval
- Min/max range
- Mean wall time with standard deviation
- `energy_j`, `duration_s`, `power_w` (mean of per-run energy/time),
  `domains` (mean joules) and `domains_power_w` (mean of per-run domain
  joules/time) cover every `ok` run, unfiltered. With
  `measurement.report.outlier_method` `iqr_<k>` (default `none`), `filtered`
  adds `method`, `runs` and the same five summaries over the runs whose energy
  lies inside the Tukey fences; `runs.iqr_outliers_removed` counts the rest.
  `runs.energies_j` lists every run's signed reading (`null` where the read
  failed) and `runs.status` its status (`ok`, `zero_energy`,
  `negative_energy`, `read_failed`). Only `ok` runs enter the statistics.
- A `validity` block (`--json`) with `checks.affinity_cpus` and
  `checks.resolution_ms`. Fatal reasons: `RUN_BELOW_RESOLUTION` (mean run
  shorter than `min_run_updates` resolutions; the resolution is the slowest
  selected provider's update interval, plus the sampler interval when a
  provider integrates power), `ZERO_ENERGY_RUNS`, `NEGATIVE_ENERGY_RUNS` and
  `PROVIDER_READ_FAILED`. A backend without provider facts (perf,
  powermetrics) gets the warning `RESOLUTION_UNKNOWN`. An invalid result exits
  3 with `success: false` and `error: "invalid_measurement: ..."`, before the
  `--budget` check. `sampler` carries the provider facts.

Energy is read synchronously at each run boundary. During the runs the NEMB
background sampler is slowed to `measurement.run_path.sampler_interval_ms`
(reported as `meta.run_sampler_interval_ms`; `null` when unchanged, which
happens when a selected provider has `boundary_source: integrated_power`, since
its run energy is integrated from the samples). For short commands use `--repeat`
and `--warmup` rather than one long-tailed run.

**Examples:**
```bash
# Measure a Python script with 10 runs
codegreen run python script.py

# Command with its own flags
codegreen run -- python3 -c "sum(range(10**7))"

# Custom repetitions and warmup
codegreen run --repeat 20 --warmup 3 -- python train.py

# Compiled binary with arguments
codegreen run -- ./my_binary -v arg1

# JSON output for scripting
codegreen run --json -- python script.py

# CI/CD energy budget gating (fails if mean > 10J)
codegreen run --budget 10.0 -- python train.py

# Stdin-driven workload (hash a fixed payload each run)
codegreen run --repeat 5 --stdin payload.bin sha256sum

# Skip the unmeasured validation run; cap each run at 10 minutes
codegreen run --no-validate --timeout 600 -- ./long_job
```

### `monitor`

Continuously sample system energy without launching a workload. Use for
already-running services where `Session` cannot be embedded. See the
[Continuous Monitoring guide](continuous-monitoring.md) for the full
walkthrough.

```bash
codegreen monitor [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-d, --duration FLOAT` | Stop after N seconds (default: run until Ctrl-C) |
| `-i, --interval INTEGER` | Sample period in ms (config floor of 50 ms enforced) |
| `-p, --pid INTEGER` | Attribute energy to this process via CPU% share |
| `-o, --output PATH` | Stream samples as JSON-lines to this file |
| `--rotate-mb INTEGER` | Rotate JSONL when it exceeds N MB (0 = disabled) |
| `--max-in-memory INTEGER` | Bound in-memory sample deque (0 = drop when `-o` set) |
| `--max-labels INTEGER` | Cap distinct annotation labels; overflow collapses into `__other__` (0 = unlimited) |
| `--listen-on-socket TEXT` | Bind a UDS for request-annotation events |
| `--attribution-mode TEXT` | PID share backend: `auto` (default), `cgroup_v2`, `cgroup_v1`, `cpu_percent` |
| `--exporter TEXT` | Enable a telemetry exporter sink (repeatable). Known: `otlp`, `prometheus`. Needs `pip install codegreen[otlp]` or `codegreen[prometheus]` |
| `--otlp-endpoint TEXT` | OTLP/gRPC collector endpoint (overrides `monitor.exporters.otlp.endpoint`) |
| `--prometheus-port INTEGER` | Prometheus `/metrics` port (overrides `monitor.exporters.prometheus.port`; 0 = ephemeral) |
| `--prometheus-listen-addr TEXT` | Prometheus bind address (default `127.0.0.1`; non-loopback emits a runtime warning) |
| `--json` | Print final summary as JSON |
| `-q, --quiet` | Suppress live sample output |

**Examples:**
```bash
# 30-second host sample
codegreen monitor -d 30

# 1Hz for an hour, JSONL output
codegreen monitor -i 1000 -d 3600 -o energy.jsonl

# Per-PID attribution
codegreen monitor --pid 1234 -o pid.jsonl

# Per-request UDS attribution (see Flask recipe in the guide)
codegreen monitor --listen-on-socket /tmp/cg.sock -o requests.jsonl

# Cap distinct labels at 1000
codegreen monitor --max-labels 1000

# Export over OTLP and expose a Prometheus endpoint
codegreen monitor --exporter otlp --otlp-endpoint http://localhost:4317
codegreen monitor --exporter prometheus --prometheus-port 9464
```

SIGINT and SIGTERM stop cleanly and flush the summary. SIGHUP re-reads
`monitor.*` from `config.json` and hot-applies `--interval`, `--rotate-mb`,
`--max-in-memory` and `--max-labels` without dropping in-flight annotations.

### `project`

Profile a project's energy consumption with per-function attribution.
Three-phase workflow: DISCOVER -> INSTRUMENT+BUILD -> MEASURE. See the
[Project Profiling guide](project-profiling.md) for the full walkthrough.

```bash
codegreen project [OPTIONS] LANGUAGE:{python|cpp|java|c|javascript} PROJECT_DIR
```

| Option | Description |
|--------|-------------|
| `-b, --build-cmd TEXT` | Build command (e.g. `mvn package -DskipTests`) |
| `-r, --run-cmd TEXT` | Run command (e.g. `java -jar target/benchmarks.jar`); required |
| `-s, --source-glob TEXT` | Source file glob pattern, project-relative (repeatable) |
| `-g, --granularity [coarse\|fine]` | Instrumentation level (default: fine) |
| `--cores TEXT` | CPU cores for taskset (e.g. `0-7`) |
| `-n, --repeat INTEGER` | Measurement repetitions (default: 1) |
| `--json` | Output as JSON |
| `--no-cleanup` | Keep instrumented files |
| `-o, --output PATH` | Output directory for results |
| `--sync-device TEXT` | Accelerator to synchronise at every probe (Python: `cuda`). Runs `torch.cuda.synchronize()` before each enter/exit timestamp so a frame owns the device work it launched. Costs one device drain per probe (no CPU/GPU overlap). Fails if no synchronisation ran. Off by default |
| `--min-attribution-pct FLOAT` | Floor for `attribution_pct` (exclusive function energy / total run energy; default: 25.0). Below it the result carries an `attribution_warning` |

`--source-glob` is repeatable. If an explicit glob matches no files, or no
checkpoint records are captured, the command exits 1. JSON output includes
`attribution_pct`, `attribution_warning`, `sync_device` and
`skipped_functions` (async functions, generators, coroutines, C++
`constexpr`/`consteval` and some C functions are not instrumented).

Each entry of `runs` carries `sampler`, `validity`, `resolution_ns` and
`overlapping_threads`. The top-level `validity` merges every run (each text is
prefixed `run N:`), and an invalid result exits 3 with `success: false` like
`measure`. Java standalone runs build `sampler` from each JVM's
`CG_CP_META|<json>` record (`marker_reads: "last_poll"`); the poller settings
come from `project_config.runtime_injection.env` in `java.json`, and the
caller's environment overrides them. Each function has `quality`.

#### Per-function quality

`measure` and `project` share one verdict per function:

- `measured`: the mean time per call spans at least `measured_min_factor`
  resolutions (`resolution_ns`: the slowest selected provider's
  `update_interval_ms` or the sampler interval, widened to the largest gap on
  `SAMPLER_GAP`) and, when the markers carry reading indices, every call spans
  at least `measured_min_factor` sampler readings.
- `aggregate_only`: the function's summed time spans at least
  `aggregate_min_factor` resolutions. Use the total, not per-call figures.
- `below_resolution`: below both.

`project` is the command for exclusive per-function attribution. Pass
`--cores` with at least two CPUs; a one-CPU set carries the warning
`AFFINITY_SINGLE_CPU`.

**Examples:**
```bash
# Java + Gradle + JMH
codegreen project java . \
  -b "./gradlew build -x test" \
  -r "java -jar jmh/build/libs/benchmarks.jar '.*MyBench.*' -wi 10 -i 50 -f 1"

# Java + Maven
codegreen project java ./my-project \
  -b "mvn package -DskipTests" \
  -r "java -jar target/benchmarks.jar" --cores 0-7

# Python project, two source globs
codegreen project python ./src -r "python main.py" -s "pkg_a/**/*.py" -s "pkg_b/**/*.py"

# GPU workload: attribute CUDA work to the launching function
codegreen project python ./src -r "python train.py" --sync-device cuda
```

### `timeline`

Put power, CPU stacks, GC, allocation and GPU kernels on one monotonic-clock
axis. Writes a Perfetto/Chrome trace for ui.perfetto.dev and prints a phase
and bottleneck summary. At least one of `--nemb`, `--jfr`, `--torch` is required.

```bash
codegreen timeline [OPTIONS] --out PATH
```

| Option | Description |
|--------|-------------|
| `--out PATH` | Perfetto/Chrome trace JSON to write (required) |
| `--nemb PATH` | NEMB time series JSON (power + cumulative energy) |
| `--jfr PATH` | `jfr print --json` output (stacks, GC, allocation) |
| `--jfr-offset-ns INTEGER` | Monotonic minus realtime ns taken during the run (default: 0) |
| `--torch PATH` | `torch.profiler` Chrome trace JSON |
| `--torch-offset-ns INTEGER` | ns added to Kineto `ts` to reach the monotonic clock (default: 0) |
| `--rel-change FLOAT` | Power change (fraction) that starts a phase (default: 0.2) |
| `--confirm INTEGER` | Consecutive samples confirming a phase change (default: 3) |
| `--gap-min-us FLOAT` | GPU idle gap counted above this length (default: 10.0) |
| `--launch-bound-frac FLOAT` | Gap share covered by CUDA launches to call it launch-bound (default: 0.8) |

**Examples:**
```bash
codegreen timeline --nemb nemb.json --out trace.json
codegreen timeline --nemb nemb.json --jfr run.json --jfr-offset-ns 123456789 --out trace.json
codegreen timeline --nemb nemb.json --torch kineto.json --torch-offset-ns 42000 --out trace.json
```

### `analyze`

Static analysis via Tree-sitter AST parsing. Identifies instrumentation points without executing code.

```bash
codegreen analyze [OPTIONS] LANGUAGE:{python|cpp|java|c|javascript} SCRIPT
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file for analysis results |
| `--verbose` | Verbose output with detailed instrumentation points |
| `--json` | Output in JSON format |
| `--suggestions` | Show optimization suggestions (default: true) |
| `--save-instrumented` | Save instrumented code to current directory |
| `--output-dir PATH` | Directory to save instrumented code |
| `--no-cleanup` | Keep temporary files (default: auto-cleanup) |

**Examples:**
```bash
codegreen analyze python script.py --verbose
codegreen analyze cpp main.cpp --json
codegreen analyze python app.py --save-instrumented --output-dir ./instrumented
```

### `init`

Comprehensive system initialization: detects the environment and hardware, validates permissions, and merges the detected providers (`measurement.nemb.providers.<name>.enabled`) and their sensors (`measurement.default_sensors`) into `--config`, else `CODEGREEN_CONFIG`, else `~/.codegreen/config.json`; the bundled config is never written.

```bash
codegreen init [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-f, --force` | Force re-initialization even if config exists |
| `-i, --interactive` | Interactive mode with user confirmation (default: on) |
| `--config PATH` | Custom config file path |
| `--auto-detect-only` | Only auto-detect, no user interaction |
| `--setup-permissions` | Automatically run permission setup if needed |

### `init-sensors`

Create a `codegreen` group, add the current user, and set read permissions on the RAPL sysfs files. A udev rule keeps the permissions across reboots. **Run once with sudo.**

```bash
sudo codegreen init-sensors
```

Performs:

- Creates the `codegreen` group and adds the current user
- Sets `/sys/class/powercap` read permissions on RAPL files
- Installs a udev rule so the permissions persist across reboots

**This must be run before any energy measurements.**

### `info`

Display CodeGreen installation, hardware sensors, and system information.

```bash
codegreen info [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-d, --detailed` | Show detailed information |

### `doctor`

Diagnose CodeGreen installation and configuration issues.

```bash
codegreen doctor [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--test-sensors` | Run a live energy measurement test |

### `benchmark`

Run benchmarks comparing CodeGreen against perf RAPL. Suites: `benchmarksgame` (default) and `perfopt` (Java JMH benchmarks).

```bash
codegreen benchmark [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--suite TEXT` | Benchmark suite: `benchmarksgame` (default), `perfopt` |
| `-p, --problem TEXT` | Problems/tasks to run (repeatable) |
| `-l, --lang TEXT` | Languages to test (repeatable) |
| `-s, --size TEXT` | Problem sizes (repeatable) |
| `--profiler TEXT` | Profilers: `codegreen`, `perf` (repeatable) |
| `-r, --reps INTEGER` | Repetitions per test (default: 5) |
| `-o, --output-dir PATH` | Output directory (default: `benchmark/results`) |
| `--compare` | Show variant comparison (original vs patched) |
| `--dataset-dir PATH` | Dataset directory (perfopt) |
| `--jars-dir PATH` | Pre-built JARs directory (perfopt) |

**Examples:**
```bash
# Run all benchmarks
codegreen benchmark

# Specific problem and language
codegreen benchmark -p nbody -l python -s 5000

# Compare profilers
codegreen benchmark -p nbody --profiler codegreen --profiler perf

# PerfOpt Java suite
codegreen benchmark --suite perfopt --dataset-dir ~/data/PerfOpt --jars-dir ~/data/jars -p 9bb2f78
```

### `measure-workload` (hidden)

Synthetic workload for sensor calibration. Hidden from `--help`; useful
when bringing up a new host.

```bash
codegreen measure-workload [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--duration INTEGER` | Duration in seconds (default: 3) |
| `--workload TEXT` | `cpu_stress` (default), `memory_stress` |

### `validate` (hidden)

Cross-validates CodeGreen's NEMB against native tools (`perf`, `rapl`,
`nvidia-smi`). Hidden from `--help` because it is research-grade and
requires root.

```bash
sudo codegreen validate [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--reference TEXT` | Reference tool: `rapl`, `perf`, `both` (default `both`) |
| `-d, --duration INTEGER` | Duration in seconds (default 5) |
| `-t, --tolerance FLOAT` | Acceptable error percentage (default 5.0) |

For day-to-day cross-validation, prefer
[example 10](../examples/10_codegreen_vs_perf.md), which uses only the
public `codegreen run` + `perf stat` and needs no root.

### `validate-accuracy` (hidden)

Reproduces the validation experiments from the CodeGreen paper. Hidden
from `--help`.

```bash
codegreen validate-accuracy [OPTIONS] [EXPERIMENT]
```

`EXPERIMENT` is one of `overhead`, `accuracy`, `scalability`, `crosslang`,
`linearity`, `all` (default).

| Option | Description |
|--------|-------------|
| `-o, --output-dir PATH` | Output directory (default: `validation_results`) |
| `--latex` | Generate LaTeX tables |
| `--plots` | Generate plots |
| `-r, --reps INTEGER` | Repetitions per test (default: 30) |

### `config`

Manage CodeGreen configuration.

```bash
codegreen config [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--show` | Display current configuration |
| `--edit` | Open configuration in editor |
| `--reset` | Reset to default configuration |

## Exit codes and measurement validity

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error: bad arguments, build or run failure, `--budget` exceeded |
| 3 | `measure`, `run` or `project`: invalid measurement (`measurement.report.validity.fail_on_invalid`, default `true`) |

The `validity` block is `{"status": "valid"|"invalid", "reasons": [...],
"detail": {code: text}, "warnings": {code: text}}`. Every reason is fatal;
warnings are not.

| Code | Command | Meaning |
|---|---|---|
| `STALE_LIBRARY` | measure, project | Result block without sampler statistics (`libcodegreen-nemb` older than ABI 4); rebuild it |
| `NEMB_INIT_FAILED` | measure | NEMB could not start, e.g. a `--sensors` provider is unavailable |
| `INCOMPLETE_TIMEOUT` | measure | Killed at `--timeout` |
| `INCOMPLETE_CRASH` | measure, project | Non-zero exit or launch failure |
| `INCOMPLETE_NO_CHECKPOINTS` | measure, project | Fewer than two markers in the result block |
| `COMPILE_FAILED` | measure | C, C++ or Java compile error (compiler output in `detail`) |
| `SAMPLER_STARVED` | measure, project | Max reading gap above `gap_policy.<marker_reads>.max_gap_factor` x interval, or median gap above `median_gap_factor` x interval, where that policy's `severity` is `fatal` (NEMB `interpolated` markers) |
| `PROVIDER_READ_FAILED` | all | A provider read failed where the result depends on it: `last_poll` markers (`failed_reads`), a provider restart (counter discontinuity), a failed `run` session read, a failed `Session` task or a failed final `Monitor` read |
| `CHECKPOINT_CAP` | measure, project | Markers dropped at `measurement.report.max_checkpoints` |
| `BUFFER_WRAPPED` | measure, project | Ring buffer overwrote the start of the run |
| `MARKER_CLAMPED` | measure, project | A marker lies outside the sampled range |
| `TOTAL_BELOW_RESOLUTION` | measure, project | Root window (or the whole run, for aggregating runtimes) spans fewer than `min_window_samples` readings |
| `ZERO_ENERGY` | measure, project | Root window measured 0 J |
| `NEGATIVE_ENERGY` | measure, project, Session | Cumulative energy decreases between markers, or a task's energy is negative |
| `RUN_BELOW_RESOLUTION` | run | Mean run shorter than `min_run_updates` resolutions |
| `ZERO_ENERGY_RUNS` | run | At least one run read 0 J |
| `NEGATIVE_ENERGY_RUNS` | run | At least one run read negative energy |
| `AFFINITY_SINGLE_CPU` (warning) | measure, project | Measured process allowed on fewer than `min_affinity_cpus` CPUs; `SAMPLER_STARVED` is the fatal symptom |
| `SAMPLER_GAP` (warning) | measure, project | A reading gap where the policy's `severity` is `warning` (`last_poll` markers); per-function resolution widened to the gap |
| `PROVIDER_READ_FAILED` (warning) | measure, project | `failed_reads` where `failed_read_severity` is `warning` (`interpolated` markers skip the failed reading) |
| `READINGS_REJECTED` (warning) | measure, project | Readings rejected by the sampler; markers interpolate across them |
| `GPU_IN_TOTAL` (warning) | measure, run, project | The total sums GPU and non-GPU providers (scope label; choose with `--sensors` or `default_sensors`) |
| `GPU_READ_HELD` (warning) | measure, run, project | A read was answered with a held value (`providers[].held`): a failed power read kept the last good value, or an energy counter read within one update period of the previous read (which would discard energy) returned that read |
| `RUN_POWER_INTEGRATED` (warning) | run | A provider's run energy is integrated from sampled power (`boundary_source: integrated_power`), so it depends on the sampler interval |
| `OVERLAPPING_THREADS` (warning) | measure, project | Several threads inside instrumented frames at once; each is charged the whole package energy |
| `RESOLUTION_UNKNOWN` (warning) | run | The backend reports no provider facts, so `RUN_BELOW_RESOLUTION` is not checked |
| `SAMPLES_INVALID` (warning) | Monitor | Sample reads failed; the next valid sample's delta spans each gap |

The Python runtime embeds `validity` in its result block from in-process facts;
the CLI adds only process-level reasons (`INCOMPLETE_*`, `NEMB_INIT_FAILED`,
`COMPILE_FAILED`). For C, C++ and Java the CLI computes it from the block with
the same functions (`codegreen_runtime.measurement_validity`).

`sampler` (`measure`, `run`, and each `project` run) describes the sampler for
that run: `interval_ms` (configured), `interval_ms_min`, `interval_ms_max`,
`buffer_capacity`, `readings`, `wrapped`, `rejected_readings`, `failed_reads`,
`dropped_checkpoints`, `first_ns`, `last_ns`, `median_gap_ns`, `max_gap_ns`,
`affinity_cpus` (CPUs the measured process may run on),
`sampler_affinity_cpus`, `marker_reads` (`interpolated` for NEMB, `last_poll`
for the Java standalone poller), `config_path` and `providers`: one object per
provider with `name`, `hardware_type`, `energy_source` (`counter` or
`integrated_power`: how sampled and marker readings get energy),
`boundary_source` (the same for `run` and `Session` boundary reads; NVIDIA GPUs
with a total-energy counter read it there), `update_interval_ms`,
`counter_group`, `rejected` and `held`. Runs of several processes (JVM forks) merge their records (counts add,
gaps take the worst, `processes` counts them; `gap_statistic: "mean"` marks a
poller that keeps only the mean gap).

Guidance for valid results:

- Do not pin the measured process (or `codegreen` around it) to one CPU.
  The sampler thread runs inside the measured process
  (`AFFINITY_SINGLE_CPU`, and usually `SAMPLER_STARVED`).
- Keep measured windows several sampling intervals long. Below
  `min_window_samples` readings the result is `TOTAL_BELOW_RESOLUTION`; for
  short commands use `run --repeat N --warmup M`.
- Choose providers with `--sensors` or `measurement.default_sensors` when a
  GPU is present.
- Use `project` for exclusive per-function attribution across a code base,
  and read each function's `quality`.

Thresholds live in `measurement.report.validity`; see the
[Configuration Reference](configuration-reference.md#measurement-validity).
