# CLI Reference

Complete reference for CodeGreen command-line interface.

## Global Options

```bash
codegreen [OPTIONS] COMMAND [ARGS]...
```

### Options

- `--debug`: Enable debug output
- `--config PATH`: Path to configuration file
- `--version, -v`: Show version and exit
- `--log-level [DEBUG|INFO|WARNING|ERROR]`: Set logging level
- `--help, -h`: Show help message

## Commands

### `measure`

Instruments code, executes it, and measures energy consumption using hardware sensors.

```bash
codegreen measure [OPTIONS] LANGUAGE SCRIPT [ARGS]...
```

**Options:**
- `-o, --output PATH`: Save results to file (JSON format)
- `-s, --sensors SENSOR`: Sensors to use (rapl, nvidia, amd_gpu, amd_cpu)
- `-p, --precision [low|medium|high]`: Measurement precision
- `-t, --timeout SECONDS`: Execution timeout
- `--verbose`: Show detailed output
- `--json`: Output results in JSON format
- `--no-cleanup`: Keep temporary instrumented files
- `--instrumented`: Script is already instrumented (skip instrumentation)

**Precision Levels:**

| Level | Interval | Overhead | Accuracy | Use Case |
|-------|----------|----------|----------|----------|
| `low` | 100ms | ~0.01% | ±10% | Production monitoring |
| `medium` | 10ms | ~0.1% | ±5% | Development (default) |
| `high` | 1ms | ~1% | ±2% | Detailed profiling |

**Technical Details:**
- Background thread polls hardware sensors at specified interval
- Higher precision = more frequent polling = better correlation accuracy
- Checkpoint overhead is constant (~100-200ns), independent of precision
- Precision affects time-series granularity, not checkpoint cost

**Examples:**
```bash
# Basic measurement (medium precision by default)
codegreen measure python script.py

# High precision with multiple sensors
codegreen measure python ml_train.py --precision high --sensors rapl nvidia

# Low overhead for production
codegreen measure python server.py --precision low

# C++ program measurement
codegreen measure cpp main.cpp
```

### `analyze`

Performs static analysis using Tree-sitter AST parsing to identify instrumentation points.

```bash
codegreen analyze [OPTIONS] LANGUAGE SCRIPT
```

**Options:**
- `-o, --output PATH`: Save analysis to file
- `--verbose`: Show detailed instrumentation points
- `--suggestions`: Show optimization suggestions (default: true)
- `--save-instrumented`: Save instrumented code to current directory
- `--output-dir PATH`: Directory for instrumented code

### `init`

Comprehensive system initialization: detects hardware, configures sensors, sets permissions.

```bash
codegreen init [OPTIONS]
```

**Options:**
- `--interactive`: Interactive setup with prompts
- `--auto-detect-only`: Auto-detect only, no prompts
- `--sensors SENSOR`: Specify sensors to initialize
- `--force`: Overwrite existing configuration

### `init-sensors`

Initialize and cache sensor configuration for NEMB measurement system. **Requires root for permission setup.**

```bash
sudo codegreen init-sensors
```

Performs comprehensive initialization including:
- Discovers available energy measurement hardware (RAPL, NVML, ROCm)
- Validates sensor accessibility and permissions
- Sets up `/sys/class/powercap` read permissions
- Caches sensor configuration for fast startup

**Note:** This command must be run before any energy measurements can be performed. Run with `sudo` to ensure proper sensor permissions are configured.

### `info`

Display CodeGreen installation, hardware sensors, and system information.

```bash
codegreen info [OPTIONS]
```

**Options:**
- `--verbose`: Show detailed information
- `--json`: Output in JSON format

### `doctor`

Diagnose CodeGreen installation and configuration issues.

```bash
codegreen doctor [OPTIONS]
```

**Options:**
- `--verbose`: Show detailed diagnostic output
- `--fix`: Attempt to fix issues automatically

### `benchmark`

Measure energy consumption using built-in synthetic workloads.

```bash
codegreen benchmark [OPTIONS] WORKLOAD
```

**Workloads:** cpu_stress, memory_stress, mixed, gpu_compute

**Options:**
- `--duration SECONDS`: Duration of benchmark (default: 10)
- `--intensity [low|medium|high]`: Workload intensity
- `--output PATH`: Save results to file

**Note:** May require `sudo` if sensor permissions haven't been configured via `sudo codegreen init-sensors`.

### `validate`

Validate measurement accuracy against native tools. **Requires root.**

```bash
codegreen validate [OPTIONS]
```

**Options:**
- `--quick`: Quick validation (30 seconds)
- `--full`: Full validation suite
- `--tolerance PERCENT`: Acceptable error tolerance

### `config`

Manage CodeGreen configuration.

```bash
codegreen config [OPTIONS]
```

**Options:**
- `--show`: Display current configuration
- `--edit`: Open configuration in editor
- `--reset`: Reset to default configuration
- `--validate`: Validate configuration syntax