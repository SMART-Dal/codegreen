# CodeGreen Configuration Guide

Complete guide to configuring CodeGreen for optimal performance and accuracy.

## Table of Contents

1. [Configuration File Locations](#configuration-file-locations)
2. [Configuration Structure](#configuration-structure)
3. [NEMB Measurement Settings](#nemb-measurement-settings)
4. [Instrumentation Options](#instrumentation-options)
5. [Language-Specific Settings](#language-specific-settings)
6. [Validation and Testing](#validation-and-testing)
7. [Migration from Old Configs](#migration-from-old-configs)
8. [Troubleshooting](#troubleshooting)

---

## Configuration File Locations

CodeGreen searches for configuration files in this priority order:

1. `<install_dir>/config/codegreen.json` (project root)
2. `<install_dir>/build/bin/config/codegreen.json`
3. `~/.codegreen/codegreen.json` (user home)

The first file found is used. The default config ships at `config/codegreen.json` in the project root.

### Custom Config

```bash
# User-level override
mkdir -p ~/.codegreen
cp config/codegreen.json ~/.codegreen/codegreen.json
# Edit as needed
```

---

## Configuration Structure

### Minimal Working Configuration

```json
{
  "version": "0.1.0",
  "measurement": {
    "nemb": {
      "enabled": true,
      "coordinator": {
        "measurement_interval_ms": 1
      },
      "timing": {
        "precision": "high"
      },
      "providers": {
        "intel_rapl": { "enabled": true }
      }
    }
  }
}
```

### Complete Configuration Reference

```json
{
  "version": "0.1.0",

  "measurement": {
    "nemb": {
      "enabled": true,

      "coordinator": {
        "measurement_interval_ms": 1,
        "measurement_buffer_size": 100000,
        "auto_restart_failed_providers": true,
        "provider_restart_interval": 5000,
        "cross_validation": true,
        "cross_validation_threshold": 0.05
      },

      "timing": {
        "precision": "high",
        "clock_source": "auto"
      },

      "providers": {
        "intel_rapl": {"enabled": true},
        "amd_rapl": {"enabled": true},
        "nvidia_gpu": {"enabled": true},
        "amd_gpu": {"enabled": true}
      },

      "accuracy": {
        "target_uncertainty_percent": 1.0,
        "measurement_validation": true,
        "outlier_detection": true,
        "noise_filtering": "adaptive",
        "statistical_validation": true,
        "confidence_threshold": 0.95
      }
    }
  },

  "instrumentation": {
    "checkpoint_strategy": "functions",
    "track_invocations": true,
    "track_threads": true,
    "language_specific": {
      "python": {
        "instrument_loops": false,
        "max_recursion_depth": 100
      },
      "cpp": {
        "instrument_loops": false,
        "track_templates": true
      },
      "java": {
        "instrument_loops": false,
        "track_lambdas": true
      }
    }
  },

  "paths": {
    "temp_directory": {
      "base": "${SYSTEM_TEMP}",
      "prefix": "codegreen_",
      "cleanup_on_exit": true
    },
    "database": {
      "default_path": "${USER_HOME}/.codegreen/energy_data.db"
    },
    "logs": {
      "directory": "${USER_HOME}/.codegreen/logs",
      "level": "INFO",
      "max_files": 10,
      "max_size_mb": 50
    }
  },

  "languages": {
    "python": {
      "executable": "python3",
      "runtime_module": "codegreen_runtime.py",
      "extensions": [".py", ".pyw", ".pyi"]
    },
    "c": {
      "executable": "gcc",
      "compiler_flags": ["-O0", "-g"],
      "extensions": [".c", ".h"]
    },
    "cpp": {
      "executable": "g++",
      "compiler_flags": ["-O0", "-g", "-std=c++17"],
      "extensions": [".cpp", ".cxx", ".cc", ".hpp", ".h"]
    },
    "java": {
      "executable": "java",
      "compiler": "javac",
      "extensions": [".java"]
    }
  },

  "output": {
    "format": "json",
    "verbose": false
  },

  "developer": {
    "debug_mode": false,
    "preserve_temp_files": false
  }
}
```

---

## NEMB Measurement Settings

### Coordinator Settings

| Setting | Default | Options | Description |
|---------|---------|---------|-------------|
| `measurement_interval_ms` | 1 | 1-100 | Background polling interval (lower = more accurate) |
| `measurement_buffer_size` | 100000 | 1000-1000000 | Circular buffer size for energy readings |
| `auto_restart_failed_providers` | true | true/false | Automatically restart crashed providers |
| `provider_restart_interval` | 5000 | 1000-60000 | Wait time (ms) before restart |

**Performance vs Accuracy:**

```json
// High Accuracy (recommended for profiling)
"coordinator": {
  "measurement_interval_ms": 1,
  "measurement_buffer_size": 100000
}

// Balanced (default)
"coordinator": {
  "measurement_interval_ms": 10,
  "measurement_buffer_size": 10000
}

// Low Overhead (production monitoring)
"coordinator": {
  "measurement_interval_ms": 100,
  "measurement_buffer_size": 1000
}
```

### Timing Settings

| Setting | Default | Options | Description |
|---------|---------|---------|-------------|
| `precision` | high | low/medium/high | Measurement precision level |
| `clock_source` | auto | auto/tsc/monotonic | High-resolution timer source |

**Precision Levels:**
- `high`: 1ms sampling, ~1% overhead, ±2% accuracy
- `medium`: 10ms sampling, ~0.1% overhead, ±5% accuracy
- `low`: 100ms sampling, ~0.01% overhead, ±10% accuracy

**Clock Sources:**
- `auto`: Automatically select best (TSC → MONOTONIC_RAW → MONOTONIC)
- `tsc`: Time Stamp Counter (x86/x64 only, nanosecond precision)
- `monotonic`: CLOCK_MONOTONIC (all platforms, nanosecond precision)

### Provider Settings

`measurement.nemb.providers` is keyed by NEMB registry name (`intel_rapl`,
`amd_rapl`, `nvidia_gpu`, `amd_gpu`):

```json
"providers": {
  "intel_rapl": {"enabled": true},
  "amd_rapl": {"enabled": true},
  "nvidia_gpu": {"enabled": true},
  "amd_gpu": {"enabled": true}
}
```

`enabled: false` removes a provider from every sensor selection. Selection
itself is `measurement.default_sensors` (or `--sensors`): `"all"` (default)
sums every provider that initializes, a list of sensor names (keys of
`measurement.sensor_providers`) selects them strictly. The CLI and the Python
runtime turn a selection into `CODEGREEN_PROVIDERS`, one group per sensor with
its enabled providers as alternatives (`intel_rapl|amd_rapl`). Disabling a
provider while `default_sensors` is `"all"` is rejected (a strict list is
needed to exclude it). `codegreen init` enables the detected providers and
lists their sensors in `default_sensors`. RAPL domains (`package`, `pp0`,
`pp1`, `dram`, `psys`) are reported per task and per run.

### Config file resolution

The CLI, the Python runtime and the native library read one file:
`CODEGREEN_CONFIG` if set, else `~/.codegreen/config.json`, else the bundled
`codegreen/config.json`. The CLI and the runtime export the resolved path as
`CODEGREEN_CONFIG` to measured processes and to the library. Python merges
the bundled defaults with the active file key by key, so an older user config
cannot drop a key. A file that does not parse raises an error naming it.

### Measurement Validity

Keys under `measurement` in `codegreen/config.json`, read by
`codegreen_runtime.measurement_validity` and `run_validity` in the CLI and in
the measured Python process alike.

`measurement.report.validity` (thresholds of the
[validity gate](cli-reference.md#exit-codes-and-measurement-validity)):

| Key | Default | Description |
|---|---|---|
| `min_window_samples` | 2 | Fewest sampler readings a root window must span |
| `median_gap_factor` | 1.5 | Median reading gap, in sampler intervals, that counts as a gap |
| `gap_policy.<marker_reads>.max_gap_factor` | 3.0 | Max reading gap, in sampler intervals, that counts as a gap |
| `gap_policy.<marker_reads>.severity` | `interpolated`: `fatal`; `last_poll`: `warning` | `fatal` reports `SAMPLER_STARVED`, `warning` reports `SAMPLER_GAP` and widens the per-function resolution to the gap |
| `gap_policy.<marker_reads>.failed_read_severity` | `interpolated`: `warning`; `last_poll`: `fatal` | Severity of `PROVIDER_READ_FAILED` for `sampler.failed_reads` (interpolated markers skip a failed reading; last-poll markers read a stale counter) |
| `min_affinity_cpus` | 2 | Fewest CPUs the measured process may run on before the `AFFINITY_SINGLE_CPU` warning |
| `min_run_updates` | 10 | `run`: fewest resolutions per run before `RUN_BELOW_RESOLUTION` |
| `measured_min_factor` | 10 | Mean time per call, in resolutions, and sampler readings in every call, for per-function `measured` |
| `aggregate_min_factor` | 10 | Summed time, in resolutions, for per-function `aggregate_only` |
| `fail_on_invalid` | true | Exit 3 on an invalid `measure`, `run` or `project` result; `false` only reports |

`gap_policy` is keyed by `sampler.marker_reads`; a sampler whose read mode has
no policy raises. Resolutions come from provider facts
(`sampler.providers[].update_interval_ms`, 0 = unknown, then the sampler
interval) and the sampler interval; there is no RAPL constant.

Other keys:

| Key | Default | Description |
|---|---|---|
| `measurement.report.max_checkpoints` | 2000000 | Markers NEMB stores per process; later ones are dropped and counted (`CHECKPOINT_CAP`) |
| `measurement.report.outlier_method` | `none` | `run`: `iqr_<k>` adds a `filtered` block over the runs inside Tukey fences at k IQRs of energy (time, power and domains use the same runs); the primary statistics stay unfiltered |
| `measurement.default_sensors` | `"all"` | Sensors measured without `--sensors`: `"all"` or a list of `sensor_providers` keys |
| `measurement.sensor_providers` | `rapl`: `[intel_rapl, amd_rapl]`, `amd_cpu`: `[amd_rapl]`, `nvidia`: `[nvidia_gpu]`, `amd_gpu`: `[amd_gpu]` | Sensor name (the `--sensors` choices) to NEMB provider alternatives |
| `measurement.run_path.sampler_interval_ms` | 1000 | Background sampler period during `codegreen run` sessions (kept at the coordinator interval when a selected provider integrates power) |
| `measurement.toolchain.c` / `.cpp` | `gcc` / `g++` | Compilers for instrumented C/C++ in `measure`; `CC`/`CXX` override |
| `measurement.toolchain.prefer_dirs` | `["/usr/bin"]` | Directories searched for the compiler before `PATH`; the compile runs with the compiler's directory first on `PATH` |

Size `measurement.nemb.coordinator.measurement_buffer_size` for the longest
run: the buffer holds `measurement_buffer_size` x `measurement_interval_ms`
of readings (100000 x 10 ms = 1000 s by default). A longer run is
`BUFFER_WRAPPED`.

---

## Instrumentation Options

### Checkpoint Strategy

```json
"instrumentation": {
  "checkpoint_strategy": "functions",
  "track_invocations": true,
  "track_threads": true
}
```

**Strategies:**
- `minimal`: Only entry/exit of main function
- `functions`: All function boundaries (default, recommended)
- `blocks`: Function boundaries + loop blocks
- `all`: Maximum instrumentation (high overhead)

**Invocation Tracking:**
- `track_invocations: true`: Adds `#inv_N` to checkpoint names for recursive functions
- `track_threads: true`: Adds `_tTHREADID` for multi-threaded programs

### Language-Specific Settings

**Python:**
```json
"python": {
  "instrument_loops": false,
  "max_recursion_depth": 100
}
```

**C/C++:**
```json
"cpp": {
  "instrument_loops": false,
  "track_templates": true
}
```

**Java:**
```json
"java": {
  "instrument_loops": false,
  "track_lambdas": true
}
```

---

## Language-Specific Settings

### Compiler Configuration

**C Programs:**
```json
"c": {
  "executable": "gcc",
  "compiler_flags": ["-O0", "-g"],
  "extensions": [".c", ".h"]
}
```

**C++ Programs:**
```json
"cpp": {
  "executable": "g++",
  "compiler_flags": ["-O0", "-g", "-std=c++17"],
  "extensions": [".cpp", ".cxx", ".cc", ".hpp", ".h"]
}
```

**Note:** CodeGreen defaults to `-O2` for realistic energy measurement. Use `-O0` only if you need to measure unoptimized code.

---

## Validation and Testing

### Validate Configuration

```bash
# Check JSON syntax
python3 -m json.tool config/codegreen.json

# Show current active configuration
codegreen config --show

# Test with minimal workload
codegreen measure-workload --duration 3
```

### Common Validation Errors

**Error: Invalid precision value**
```json
// WRONG
"precision": "maximum"

// CORRECT
"precision": "high"
```

**Error: Provider name mismatch**
```json
// WRONG (pre-0.5 names, ignored)
"nvidia_gpu": { "enabled": true }

// CORRECT (NEMB registry names)
"nvidia_gpu": { "enabled": true }
```

**Error: Missing required fields**
```json
// INCOMPLETE
"nemb": {
  "enabled": true
}

// COMPLETE
"nemb": {
  "enabled": true,
  "coordinator": {
    "measurement_interval_ms": 1
  }
}
```

---

## Migration from Old Configs

### From PMT-based Config (v0.0.x)

**Old Structure:**
```json
{
  "pmt": {
    "preferred_sensors": ["rapl", "nvml"],
    "measurement_interval_ms": 1
  }
}
```

**New Structure:**
```json
{
  "measurement": {
    "nemb": {
      "coordinator": {
        "measurement_interval_ms": 1
      },
      "providers": {
        "intel_rapl": { "enabled": true },
        "nvidia_gpu": { "enabled": true }
      }
    }
  }
}
```

### Migration Script

```bash
# Backup old config
cp config/codegreen.json config/codegreen.json.backup

# Copy new template
cp config/codegreen.json.template config/codegreen.json

# Edit with your settings
codegreen config --edit
```

---

## Troubleshooting

### Config Not Loading

```bash
# Check which config file is being used
codegreen info --detailed

# Output will show:
# Configuration loaded from: /path/to/codegreen.json
```

### Syntax Errors

```bash
# Validate JSON syntax
python3 -m json.tool config/codegreen.json

# Use a JSON validator
python3 -m json.tool config/codegreen.json
```

### Permission Issues

```bash
# Set up RAPL access (creates codegreen group + udev rule)
sudo codegreen init-sensors
# Then log out/in for group changes
```

### Performance Issues

```bash
# Check measurement overhead
codegreen doctor --test-sensors

# Reduce precision if needed
{
  "timing": { "precision": "low" },
  "coordinator": { "measurement_interval_ms": 100 }
}
```

---

## Environment Variable Substitution

CodeGreen supports environment variables in config values:

```json
{
  "paths": {
    "temp_directory": {
      "base": "${SYSTEM_TEMP}"
    },
    "database": {
      "default_path": "${USER_HOME}/.codegreen/energy_data.db"
    }
  }
}
```

**Available Variables:**
- `${USER_HOME}`: User's home directory
- `${SYSTEM_TEMP}`: System temp directory (/tmp)
- `${EXECUTABLE_DIR}`: CodeGreen installation directory
- Any custom environment variable: `${MY_VAR}`

### Runtime Environment Variables

| Variable | Description |
|----------|-------------|
| `CODEGREEN_CONFIG` | Path to configuration file |
| `CODEGREEN_DEBUG` | Enable debug output |
| `CODEGREEN_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `CODEGREEN_CHECKPOINT_THROTTLE_MS` | Minimum interval (ms) between checkpoint recordings; reduces overhead for high-frequency checkpoints |
| `CODEGREEN_PROVIDERS` | Comma-separated NEMB provider names (`intel_rapl`, `amd_rapl`, `nvidia_gpu`, `amd_gpu`, ...). Only these are initialized; an unknown or failing one is an error. Set by `measure --sensors` |
| `CC` / `CXX` | Compiler for instrumented C / C++ in `measure` (overrides `measurement.toolchain`) |

---

## Best Practices

1. **Start with Defaults**: Use the provided `config/codegreen.json` template
2. **Validate Early**: Run `python3 -m json.tool config/codegreen.json` after changes
3. **Test Incrementally**: Change one setting at a time
4. **Monitor Overhead**: Use `codegreen doctor` to check measurement impact
5. **Version Control**: Commit project-specific configs to git
6. **Document Changes**: Add comments (strip before using JSON parsers)

---

## Command Reference

```bash
# Show current configuration
codegreen config --show

# Edit configuration
codegreen config --edit

# Reset to defaults
codegreen config --reset

# Validate JSON syntax
python3 -m json.tool config/codegreen.json
```

---

## See Also

- [CLI Reference](cli-reference.md) - Command-line options
- [Installation](../getting-started/installation.md) - Setup and installation guide
- [Quick Start](../getting-started/quickstart.md) - Getting started with CodeGreen
