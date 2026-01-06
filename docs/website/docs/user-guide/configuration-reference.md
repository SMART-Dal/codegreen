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

1. **Local Project Override**: `./config/codegreen.json`
2. **Current Directory**: `./codegreen.json`
3. **User Configuration**: `~/.codegreen/codegreen.json`
4. **System-wide**: `/etc/codegreen/codegreen.json`

The first file found is used. All others are ignored.

### Recommended Setup

**Development:**
```bash
# Project-specific config
cp config/codegreen.json ./codegreen.json
# Edit for your project needs
```

**Personal Use:**
```bash
# User-level config
mkdir -p ~/.codegreen
cp config/codegreen.json ~/.codegreen/codegreen.json
```

**System-wide (requires sudo):**
```bash
# All users on system
sudo mkdir -p /etc/codegreen
sudo cp config/codegreen.json /etc/codegreen/
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
        "intel_rapl": {
          "enabled": true,
          "domains": ["package", "pp0", "dram"],
          "validation_enabled": true
        },
        "nvidia_nvml": {
          "enabled": true,
          "device_indices": [0],
          "validation_enabled": true
        },
        "amd_rocm": {
          "enabled": false
        }
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

**Intel RAPL:**
```json
"intel_rapl": {
  "enabled": true,
  "domains": ["package", "pp0", "dram"],
  "validation_enabled": true
}
```

**Available domains:**
- `package`: Total CPU package energy
- `pp0`: Core energy (all cores)
- `pp1`: Uncore/GPU energy (integrated GPU)
- `dram`: Memory subsystem energy
- `psys`: Platform energy (Skylake+)

**NVIDIA NVML:**
```json
"nvidia_nvml": {
  "enabled": true,
  "device_indices": [0],
  "validation_enabled": true
}
```

**AMD ROCm:**
```json
"amd_rocm": {
  "enabled": false
}
```

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

**Important:** Use `-O0` (no optimization) for accurate measurements. Optimizations can eliminate code, making measurements unreliable.

---

## Validation and Testing

### Validate Configuration

```bash
# Check syntax and values
codegreen config --validate --verbose

# Show current active configuration
codegreen config --show

# Test with minimal workload
codegreen benchmark cpu_stress --duration 5
```

### Common Validation Errors

**Error: Invalid precision value**
```json
// ❌ Wrong
"precision": "maximum"

// ✅ Correct
"precision": "high"
```

**Error: Provider name mismatch**
```json
// ❌ Wrong
"nvidia_gpu": { "enabled": true }

// ✅ Correct
"nvidia_nvml": { "enabled": true }
```

**Error: Missing required fields**
```json
// ❌ Incomplete
"nemb": {
  "enabled": true
}

// ✅ Complete
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
        "nvidia_nvml": { "enabled": true }
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
codegreen info --verbose

# Output will show:
# Configuration loaded from: /path/to/codegreen.json
```

### Syntax Errors

```bash
# Validate JSON syntax
codegreen config --validate

# Use a JSON validator
python3 -m json.tool config/codegreen.json
```

### Permission Issues

```bash
# RAPL access requires permissions
sudo codegreen init-sensors

# Or manual setup
sudo chmod 644 /sys/class/powercap/intel-rapl:*/energy_uj
```

### Performance Issues

```bash
# Check measurement overhead
codegreen doctor --verbose

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

---

## Best Practices

1. **Start with Defaults**: Use the provided `config/codegreen.json` template
2. **Validate Early**: Run `codegreen config --validate` after changes
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

# Validate configuration
codegreen config --validate

# Reset to defaults
codegreen config --reset

# Show config search path
codegreen info --verbose
```

---

## See Also

- [CLI Reference](cli-reference.md) - Command-line options
- [Installation](../getting-started/installation.md) - Setup and installation guide
- [Quick Start](../getting-started/quickstart.md) - Getting started with CodeGreen
