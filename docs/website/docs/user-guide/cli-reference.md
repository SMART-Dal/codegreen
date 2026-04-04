# CLI Reference

Complete reference for CodeGreen command-line interface.

## Global Options

```bash
codegreen [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug output |
| `--config PATH` | Path to configuration file |
| `--version, -v` | Show version and exit |
| `--log-level [DEBUG\|INFO\|WARNING\|ERROR]` | Set logging level (default: INFO) |
| `--help, -h` | Show help message |

## Commands

### `measure`

Instruments code, executes it, and measures energy consumption using hardware sensors.

```bash
codegreen measure [OPTIONS] LANGUAGE:{python|cpp|java|c} SCRIPT [-- ARGS...]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Save results to file (JSON format) |
| `-s, --sensors [rapl\|nvidia\|amd_gpu\|amd_cpu]` | Sensors to use |
| `-p, --precision [low\|medium\|high]` | Measurement precision (default: high) |
| `-g, --granularity [coarse\|fine]` | Instrumentation level (default: coarse) |
| `--export-plot PATH` | Export energy timeline (HTML via Plotly, or PNG/PDF via matplotlib) |
| `-t, --timeout SECONDS` | Execution timeout |
| `--verbose` | Show detailed output |
| `--json` | Output results in JSON format |
| `--no-cleanup` | Keep temporary instrumented files |
| `--instrumented` | Script is already instrumented (skip instrumentation) |

**Granularity:**

- **coarse** (default): Instruments only main entry/exit. Minimal overhead, gives total program energy.
- **fine**: Instruments all functions per language config. Per-function energy breakdown.

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
codegreen measure cpp main.cpp -- 5000

# Save results
codegreen measure python main.py -o results.json
```

### `run`

Measure energy consumption of any shell command with hardware-level precision via RAPL, NVML, or IOReport. No code instrumentation required.

```bash
codegreen run [OPTIONS] COMMAND [ARGS...]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-n, --repeat INTEGER` | Number of repetitions (default: 10) |
| `-w, --warmup INTEGER` | Warmup runs before measurement (default: 1) |
| `--json` | Output results as JSON |
| `--budget FLOAT` | Energy budget in Joules; exits with error if mean exceeds budget |

**Output includes:**

- Mean energy (Joules) with standard deviation
- 95% confidence interval
- Min/max range
- Mean wall time with standard deviation
- Outlier detection and removal

**Examples:**
```bash
# Measure a Python script with 10 runs
codegreen run python script.py

# Custom repetitions and warmup
codegreen run --repeat 20 --warmup 3 python train.py

# Compiled binary with arguments
codegreen run ./my_binary arg1 arg2

# JSON output for scripting
codegreen run --json python script.py

# CI/CD energy budget gating (fails if mean > 10J)
codegreen run --budget 10.0 python train.py
```

### `analyze`

Static analysis via Tree-sitter AST parsing. Identifies instrumentation points without executing code.

```bash
codegreen analyze [OPTIONS] LANGUAGE:{python|cpp|java|c} SCRIPT
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Save analysis to file |
| `--verbose` | Show detailed instrumentation points |
| `--json` | Output in JSON format |
| `--suggestions` | Show optimization suggestions (default: true) |
| `--save-instrumented` | Save instrumented code to current directory |
| `--output-dir PATH` | Directory for instrumented code |
| `--no-cleanup` | Keep temporary files |

**Examples:**
```bash
codegreen analyze python script.py --verbose
codegreen analyze cpp main.cpp --json
codegreen analyze python app.py --save-instrumented --output-dir ./instrumented
```

### `init`

Comprehensive system initialization: detects hardware, configures sensors, sets permissions.

```bash
codegreen init [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--interactive` | Interactive setup with prompts |
| `--auto-detect-only` | Auto-detect only, no prompts |
| `--sensors SENSOR` | Specify sensors to initialize |
| `--force` | Overwrite existing configuration |

### `init-sensors`

Initialize and cache sensor configuration for NEMB measurement system. **Requires root.**

```bash
sudo codegreen init-sensors
```

Performs:

- Discovers available energy measurement hardware (RAPL, NVML, ROCm)
- Validates sensor accessibility and permissions
- Sets up `/sys/class/powercap` read permissions
- Caches sensor configuration for fast startup

**This must be run before any energy measurements.**

### `info`

Display CodeGreen installation, hardware sensors, and system information.

```bash
codegreen info [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed information |
| `--json` | Output in JSON format |

### `doctor`

Diagnose CodeGreen installation and configuration issues.

```bash
codegreen doctor [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed diagnostic output |
| `--fix` | Attempt to fix issues automatically |

### `benchmark`

Run benchmarks from the benchmarksgame suite comparing CodeGreen energy measurement vs perf RAPL.

```bash
codegreen benchmark [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-p, --problem TEXT` | Problems to run (e.g., nbody, binarytrees) |
| `-l, --lang TEXT` | Languages to test |
| `-s, --size TEXT` | Problem sizes |
| `--profiler TEXT` | Profilers: codegreen, perf |
| `-r, --reps INTEGER` | Repetitions per test (default: 5) |
| `-o, --output-dir PATH` | Output directory (default: benchmark/results) |

**Examples:**
```bash
# Run all benchmarks
codegreen benchmark

# Specific problem and language
codegreen benchmark -p nbody -l python -s 5000

# Compare profilers
codegreen benchmark -p nbody --profiler codegreen --profiler perf
```

### `measure-workload`

Measure energy consumption of synthetic workloads for sensor calibration and testing.

```bash
codegreen measure-workload [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--duration INTEGER` | Duration in seconds (default: 3) |
| `--workload TEXT` | Workload type: cpu_stress, memory_stress, mixed |

**Examples:**
```bash
codegreen measure-workload --duration 10 --workload cpu_stress
codegreen measure-workload --workload memory_stress
```

### `validate`

Validate measurement accuracy against native hardware tools. **Requires root.**

```bash
sudo codegreen validate [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--quick` | Quick validation (30 seconds) |
| `--full` | Full validation suite |
| `--tolerance PERCENT` | Acceptable error tolerance |

### `validate-accuracy`

Run validation experiments for paper submission.

```bash
codegreen validate-accuracy [OPTIONS] [EXPERIMENT]
```

**Experiments:** overhead, accuracy, scalability, crosslang, linearity, all

| Option | Description |
|--------|-------------|
| `-o, --output-dir PATH` | Output directory (default: validation_results) |
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
