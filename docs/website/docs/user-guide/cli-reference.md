# CLI Reference

Complete reference for the `codegreen` command-line interface.

`codegreen --help` groups the commands into four panels: **Measurement**
(`measure`, `analyze`, `run`, `monitor`, `project`, `timeline`), **Setup**
(`init`, `config`, `init-sensors`), **Diagnostics** (`info`, `capabilities`,
`doctor`) and **Validation** (`benchmark`). Three more commands
(`measure-workload`, `validate`, `validate-accuracy`) are hidden from the
help but work. Every command accepts `-h`/`--help`.

## Global Options

```bash
codegreen [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--debug, --verbose` | Verbose diagnostic output (sets `CODEGREEN_DEBUG=1`, which also shows the native library's provider messages) |
| `--config PATH` | Configuration file to use (sets `CODEGREEN_CONFIG`) |
| `-v, --version` | Show version and exit |
| `--log-level [DEBUG|INFO|WARNING|ERROR]` | Accepted; has no effect in 0.5.0 (it sets `CODEGREEN_LOG_LEVEL`, which nothing reads) |
| `--install-completion` | Install shell completion |
| `--show-completion` | Print shell completion script |
| `-h, --help` | Show help message |

## Commands

### `measure`

Instruments a single source file, runs it, and reports its energy, per function with `-g fine`.

```bash
codegreen measure [OPTIONS] LANGUAGE:{python|cpp|java|c|javascript} SCRIPT [ARGS]...
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Also write the `--json` report to this file |
| `-s, --sensors [rapl|nvidia|amd_gpu|amd_cpu]` | Sensors to measure (repeatable; the keys of `measurement.sensor_providers`). Default: `measurement.default_sensors` |
| `-p, --precision [low|medium|high]` | Accepted for compatibility; has no effect in 0.5.0 (the sampler period is `measurement.nemb.coordinator.measurement_interval_ms`) |
| `-g, --granularity [coarse|fine]` | Instrumentation level (default: coarse) |
| `--export-plot PATH` | Export energy timeline (HTML default, or PNG/PDF) |
| `-t, --timeout INTEGER` | Kill the program after this many seconds (default: 300); the result is then invalid (`INCOMPLETE_TIMEOUT`) |
| `--verbose` | Verbose output |
| `--json` | Output results in JSON format |
| `--no-cleanup` | Keep the instrumented copy and other temporary files |
| `--instrumented` | Run the file as given, without instrumenting it (it already contains checkpoint calls) |

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
`--sensors rapl` for CPU-only energy. The same option exists on `run` and
`project`.

**JSON output.** Top-level keys: `success`, `file`, `language`,
`granularity`, `source_fingerprint` (SHA-256 of the source), `system`
(`kernel`, `cpu_model`, `governor`), `instrumentation_points`,
`optimization_suggestions`, `instrumentation_audit`, `error` when the run
failed, and:

- `summary`: `total_energy_j`, `wall_time_s`, `avg_power_w`,
  `checkpoint_count`, `energy_by_provider`, `providers`, `sensors_requested`,
  `exclusive_sum_j`, `exclusive_sum_ratio`, `overlapping_threads`.
- `per_function_energy`: per function `inclusive_j` (energy including
  callees, summed over every call), `exclusive_j` (without callees; the
  exclusive energies partition the run), `energy_j` (= `inclusive_j`),
  `wall_time_s` (summed over calls), `avg_power_w`, `calls` and `quality`.
  Every call on every thread is replayed, so a recursive function's inclusive
  energy counts each nested frame and can exceed the total. `quality` is the
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

Runs a command `--repeat` times and reports the mean energy, time and power with their spread. No instrumentation: energy is read at the start and end of each run.

```bash
codegreen run [OPTIONS] COMMAND...
```

Use `--` before commands that have their own flags; otherwise flags such as
`-c` or `-jar` are parsed as codegreen options and fail.

**Options:**

| Option | Description |
|--------|-------------|
| `-n, --repeat INTEGER` | Number of repetitions (default: 10) |
| `-w, --warmup INTEGER` | Unmeasured warmup runs before the measured ones, each limited to 300 s (default: 1; `runs.warmup_runs`) |
| `--stdin TEXT` | Bind this file as the subprocess's stdin on every repeat (cat/hash/ETL workloads) |
| `--json` | Output results as JSON |
| `--budget FLOAT` | Energy budget in joules; exit 1 when the mean energy exceeds it |
| `--validate / --no-validate` | Execute the command once, unmeasured, before measuring (default: validate). A failing command is also caught by the first measured run |
| `--validate-timeout INTEGER` | Seconds allowed for the validation run (default: 300) |
| `--timeout INTEGER` | Per-run limit in seconds (default: none) |
| `-s, --sensors [rapl|nvidia|amd_gpu|amd_cpu]` | Sensors summed into the energy (default: `measurement.default_sensors`) |

**Output.** Mean energy with standard deviation, min/max range, 95 %
confidence interval and coefficient of variation; mean time and power; the
per-domain breakdown; the validity verdict. With `--json`:

- `meta`, `command`, `backend` (`name`, `driver`, `domains_seen`), `runs`
  (`attempted`, `energy_valid`, `excluded`, `energies_j`, `status`,
  `warmup_runs`, `measurement_runs`, ...), `budget_exceeded`, `budget_j`
  with `--budget`, `sampler` and `validity`.
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
  shorter than `min_run_updates` update intervals of the finest selected
  provider; for a provider that integrates power, the sampler interval when
  that is longer), `ZERO_ENERGY_RUNS`, `NEGATIVE_ENERGY_RUNS` and
  `PROVIDER_READ_FAILED`. Warnings include `COARSE_PROVIDER_RESOLUTION`
  (runs too short for a slower selected provider, typically a GPU) and, for a
  backend without provider facts (perf, powermetrics), `RESOLUTION_UNKNOWN`.
  An invalid result exits 3 with `success: false` and
  `error: "invalid_measurement: ..."`, before the `--budget` check.

Energy is read synchronously at each run boundary. During the runs the NEMB
background sampler is slowed to `measurement.run_path.sampler_interval_ms`
(reported as `meta.run_sampler_interval_ms`; `null` when unchanged, which
happens when a selected provider has `boundary_source: integrated_power`, since
its run energy is integrated from the samples). A command that ends in a few
milliseconds is `RUN_BELOW_RESOLUTION` (10 RAPL updates are 10 ms on a 1 ms
counter); put a loop around the work or measure a longer input.

**Examples:**
```bash
# Measure a Python script with 10 runs, CPU package only
codegreen run --sensors rapl -- python3 script.py

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

Samples system energy continuously without launching a workload, for
services that are already running. Samples sum the providers of
`measurement.default_sensors` (there is no `--sensors` option). The options
(`--duration`, `--interval`, `--pid`, `--output`, `--rotate-mb`,
`--max-in-memory`, `--max-labels`, `--listen-on-socket`,
`--attribution-mode`, `--exporter`, `--otlp-endpoint`, `--prometheus-port`,
`--prometheus-listen-addr`, `--json`, `--quiet`) are described in
[Continuous Monitoring: CLI](continuous-monitoring.md#cli).

```bash
codegreen monitor -d 30                                  # 30 s host sample
codegreen monitor --pid 1234 -o pid.jsonl                # per-PID attribution
codegreen monitor --listen-on-socket default -o req.jsonl   # per-request annotations
codegreen monitor --exporter prometheus --prometheus-port 9464
```

`monitor` exits 0 even when its summary is invalid; read `validity` (with
`--json`, `success` is `false`).

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
| `-r, --run-cmd TEXT` | Run command, executed in `PROJECT_DIR` (e.g. `java -jar target/benchmarks.jar`); required |
| `-s, --source-glob TEXT` | Source file glob pattern, project-relative (repeatable) |
| `-g, --granularity [coarse|fine]` | Instrumentation level (default: fine) |
| `--cores TEXT` | CPU cores for taskset (e.g. `0-7`) |
| `-n, --repeat INTEGER` | Measurement repetitions, 30 s apart (default: 1) |
| `--json` | Output as JSON |
| `--no-cleanup` | Keep instrumented files |
| `-o, --output PATH` | Directory for `project_results.json` |
| `--sync-device TEXT` | Accelerator to synchronise at every probe (Python: `cuda`). Runs `torch.cuda.synchronize()` before each enter/exit timestamp so a frame owns the device work it launched. Costs one device drain per probe (no CPU/GPU overlap). Fails if no synchronisation ran. Off by default |
| `--min-attribution-pct FLOAT` | Floor for `attribution_pct` (exclusive function energy / total run energy; default: 25.0). Below it the result carries an `attribution_warning` |
| `--sensors [rapl|nvidia|amd_gpu|amd_cpu]` | Sensors summed into the energy, as on `measure` (default: `measurement.default_sensors`) |

`--source-glob` is repeatable. If an explicit glob matches no files, or no
checkpoint records are captured, the command exits 1. The output fields are
described in [Project Profiling](project-profiling.md#output);
`skipped_functions` lists functions that are not instrumented (async
functions, generators, coroutines, C++ `constexpr`/`consteval` and some C
functions).

Each entry of `runs` carries `sampler`, `validity`, `resolution_ns` and
`overlapping_threads`, and each function a `quality`. The top-level
`validity` merges every run (each text is prefixed `run N:`), and an invalid
result exits 3 with `success: false` like `measure`.

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

Lists the instrumentation points Tree-sitter finds, without running the code. See [Code Analysis](code-analysis.md).

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

Detects the environment and the energy providers, checks permissions, and
merges the detected providers (`measurement.nemb.providers.<name>.enabled`)
and their sensors (`measurement.default_sensors`) into `--config`, else
`CODEGREEN_CONFIG`, else `~/.codegreen/config.json`; the bundled config is
never written. A provider counts as detected when NEMB initializes it on its
own; the sensor table shows NEMB's reason for every other one (for
`amd_rapl` without MSR access: `/dev/cpu/0/msr: Permission denied`).

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

Linux: creates a `codegreen` group, adds the current user, makes the RAPL
powercap files readable by the group and installs a udev rule that keeps the
permissions across reboots. Run it once with sudo, then log out and back in.

```bash
sudo codegreen init-sensors
```

### `config`

Without options, prints the active config file, the user override and the
sampler settings. See [Configuration](../getting-started/configuration.md).

```bash
codegreen config [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--show` | Print the active config file as JSON |
| `--edit` | Open `~/.codegreen/config.json` in `$EDITOR` (or `$VISUAL`, else `nano`), first copying the active file there if it does not exist |
| `--reset` | Delete `~/.codegreen/config.json` |

### `info`

Display CodeGreen installation, hardware sensors, and system information.

```bash
codegreen info [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-d, --detailed` | Show detailed information |

### `capabilities`

Print, as JSON, what the profiling registries can measure on this host (probes
only, no workload runs).

```bash
codegreen capabilities [KIND...]
```

`KIND` is any of `metric` (CPU hardware counters), `gpu_series` (device time
series, e.g. NVML), `gpu_replay` (per-kernel replay counters, e.g. Nsight
Compute), `gpu_framework` (framework traces mapped to kernels, e.g. torch), `language` (event and line samplers per
language) and `energy` (NEMB providers of `measurement.nemb.providers`, each probed alone; `reason` is the provider's
own message); none prints every registry, an unknown name exits with an error.
Each registry maps to a list of `{provider, available, reason, device,
details}`; `details` lists per-event or per-component availability (for
`hw_counters`: `arch` and each logical event).

### `doctor`

Diagnose CodeGreen installation and configuration issues.

```bash
codegreen doctor [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--test-sensors` | Run a live energy measurement test |

`doctor` also lists what NEMB does with the configured sensor selection, per
provider: `initialized`, did not initialize (with the provider's reason), not
read again because another provider reads the same counter group (`intel_rapl`
and `amd_rapl` both read the AMD package counter), or not tried because an
earlier alternative initialized. A sensor with no working provider is an issue.

### `benchmark`

Run benchmark programs under CodeGreen and `perf` RAPL and compare the readings. Suites: `benchmarksgame` (default) and `perfopt` (Java JMH benchmarks). The `benchmarksgame` suite reads its programs from `benchmark/benchmarksgame/` of a source checkout, which is not in the git repository or the wheel; without them it reports 0 runs.

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

## Exit codes and measurement validity

| Exit code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error: bad arguments, a failed `project` build, a `run` command that exits non-zero, no energy read at all, `--budget` exceeded |
| 3 | `measure`, `run`, `project` (and `measure-workload`): invalid measurement (`measurement.report.validity.fail_on_invalid`, default `true`). For `measure` this includes a program that does not compile (`COMPILE_FAILED`), crashes (`INCOMPLETE_CRASH`) or times out (`INCOMPLETE_TIMEOUT`) |

`monitor` and the Python API do not change the exit code; read their
`validity` block.

The `validity` block is `{"status": "valid"|"invalid", "reasons": [...],
"detail": {code: text}, "warnings": {code: text}}`. Every reason is fatal;
warnings are not. Without `--json`, `measure`, `run` and `project` print the
same verdict after the energy: `Validity: valid`, or
`invalid_measurement: CODE[,CODE]` followed by one `CODE: detail` line per
reason, then one `WARNING CODE: text` line per warning. `measure` prints the
total energy, time and power and, per function, exclusive and inclusive
energy, calls and `quality`.

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
| `PROVIDER_STALLED` | measure, run, project, Session | A provider stopped reporting mid-run: no successful read, or its cumulative energy unchanged or unread (`providers[].max_stall_ns`, `last_ns`) for more than `provider_stall_resolutions` of its resolution. Its share of the total is missing; nothing is filled in |
| `CHECKPOINT_CAP` | measure, project | Markers dropped at `measurement.report.max_checkpoints` |
| `BUFFER_WRAPPED` | measure, project | Ring buffer overwrote the start of the run |
| `MARKER_CLAMPED` | measure, project | A marker lies outside the sampled range |
| `TOTAL_BELOW_RESOLUTION` | measure, project | Root window (or the whole run, for aggregating runtimes) spans fewer than `min_window_samples` readings |
| `ZERO_ENERGY` | measure, project | Root window measured 0 J |
| `NEGATIVE_ENERGY` | measure, project, Session | Cumulative energy decreases between markers, or a task's energy is negative |
| `RUN_BELOW_RESOLUTION` | run | Mean run shorter than `min_run_updates` resolutions of the finest selected provider |
| `COUNTER_INTEGRAL_DIVERGED` | measure, run, project, Session | A provider's boundary energy counter and its power integral (`providers[].counter_check`) differ by more than `counter_check.tolerance` of the integral plus one update interval of energy per counter read and at the end (a counter read discards what accrued since its last update). Another process reading the counter or instant power (`nvidia-smi --query-gpu=power.draw.instant`, DCGM) makes the NVML counter lose energy. Severity `counter_check.severity` (default fatal) |
| `ZERO_ENERGY_RUNS` | run | At least one run read 0 J |
| `NEGATIVE_ENERGY_RUNS` | run | At least one run read negative energy |
| `AFFINITY_SINGLE_CPU` (warning) | measure, project | Measured process allowed on fewer than `min_affinity_cpus` CPUs; `SAMPLER_STARVED` is the fatal symptom |
| `SAMPLER_GAP` (warning) | measure, project | A reading gap where the policy's `severity` is `warning` (`last_poll` markers); per-function resolution widened to the gap |
| `PROVIDER_READ_FAILED` (warning) | measure, project | `failed_reads` where `failed_read_severity` is `warning` (`interpolated` markers skip the failed reading) |
| `READINGS_REJECTED` (warning) | measure, project | Readings rejected by the sampler; markers interpolate across them |
| `GPU_IN_TOTAL` (warning) | measure, run, project, Session | The total sums GPU and non-GPU providers (scope label; choose with `--sensors` or `default_sensors`) |
| `GPU_READ_HELD` (warning) | measure, run, project, Session | A failed power read kept the last good value (`providers[].held`) |
| `BOUNDARY_READ_HELD` (warning) | measure, run, project, Session | A boundary read answered from a previous read (`providers[].boundary_held`) spanned more than the provider's update interval (`boundary_held_max_ns`), so it misses energy beyond the counter's resolution. Holds within one update period (back-to-back `run --repeat` boundaries) are counted, not warned |
| `TASK_POWER_INTEGRATED` (warning) | Session | Tasks whose energy integrates sampled power: a provider whose `boundary_source` is `integrated_power`, or an `integrated_power` provider for a task with `shared_boundary` (read while another task was open, so its energy counter was not read) |
| `TASK_BELOW_RESOLUTION` (warning) | Session | Tasks shorter than `min_run_updates` resolutions of the selected providers |
| `COARSE_PROVIDER_RESOLUTION` (warning) | run | Mean run shorter than `min_run_updates` update intervals of a slower selected provider (such as a GPU): that provider's share is not resolved |
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
`provider_restarts`, `dropped_checkpoints`, `first_ns`, `last_ns`, `median_gap_ns`, `max_gap_ns`
(NEMB: over the readings bracketing the markers, so setup before the root
window does not count; the whole sampler life when there are no markers),
`affinity_cpus` (CPUs the measured process may run on),
`sampler_affinity_cpus`, `marker_reads` (`interpolated` for NEMB, `last_poll`
for the Java standalone poller), `config_path` and `providers`: one object per
provider with `name`, `hardware_type`, `energy_source` (`counter` or
`integrated_power`: how sampled and marker readings get energy),
`boundary_source` (the same for `run` and `Session` boundary reads; NVIDIA GPUs
with a total-energy counter read it there), `update_interval_ms`,
`counter_group`, `rejected`, `held` (failed reads that kept the last good
value), `boundary_held` (boundary reads answered from the previous read, since a
fresh counter read within one update period would discard energy) and
`boundary_held_max_ns` (the longest span such an answer covered) and
`readings`, `last_ns` and `max_stall_ns` (successful sampler and one-shot reads,
the time of the last one, and the longest span over them with unchanged
cumulative energy; `null` from the Java poller, which does not track it),
`counter_check` (per domain, `counter_j` and `integral_j`: the energy of the
boundary counter and of the power integral from the first to the last counter
read, `span_ns` apart, and `reads`, the counter reads in that span; empty for a
provider with one energy source). Runs of several processes (JVM forks) merge their records (counts add,
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
