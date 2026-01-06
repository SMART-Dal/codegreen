# Configuration

CodeGreen uses a JSON configuration file to customize behavior and sensor settings.

## Configuration File Location

- **Default**: `~/.config/codegreen/codegreen.json`
- **Custom**: Use `--config` flag: `codegreen --config /path/to/codegreen.json`

## Basic Configuration

```json
{
  "measurement": {
    "nemb": {
      "enabled": true,
      "coordinator": {
        "measurement_interval_ms": 1,
        "measurement_buffer_size": 100000,
        "auto_restart_failed_providers": true
      },
      "timing": {
        "precision": "high",
        "clock_source": "auto"
      },
      "providers": {
        "intel_rapl": {
          "enabled": true,
          "domains": ["package", "pp0", "dram"]
        },
        "nvidia_nvml": {
          "enabled": true
        },
        "amd_rocm": {
          "enabled": false
        }
      }
    }
  },
  "instrumentation": {
    "checkpoint_strategy": "functions",
    "language_specific": {
      "python": {
        "instrument_loops": false,
        "max_depth": 10
      }
    }
  },
  "output": {
    "format": "json",
    "verbose": false
  }
}
```

## Sensor Configuration

### Available Sensors (NEMB Providers)

- **intel_rapl**: Intel/AMD CPU energy monitoring via RAPL interface
  - Domains: package, pp0 (cores), pp1 (GPU), dram, psys (platform)
  - Interface: `/sys/class/powercap/intel-rapl:*`
  - Platforms: Linux (Intel/AMD x86_64)

- **nvidia_nvml**: NVIDIA GPU monitoring via NVML
  - Requires: NVIDIA drivers and CUDA toolkit
  - Platforms: Linux, Windows (limited)

- **amd_rocm**: AMD GPU via ROCm
  - Requires: ROCm drivers and libraries
  - Platforms: Linux only

### Sensor Settings

```json
{
  "measurement": {
    "nemb": {
      "providers": {
        "intel_rapl": {
          "enabled": true,
          "domains": ["package", "pp0", "pp1", "dram", "psys"]
        },
        "nvidia_nvml": {
          "enabled": true,
          "device_indices": [0]
        },
        "amd_rocm": {
          "enabled": false
        }
      }
    }
  }
}
```

**Sensor Details:**
- **intel_rapl**: Reads `/sys/class/powercap/intel-rapl:*` (requires permissions)
- **nvidia_nvml**: Uses NVIDIA Management Library (requires CUDA drivers)
- **amd_rocm**: AMD GPU via ROCm (Linux only)

## Measurement Settings

```json
{
  "measurement": {
    "nemb": {
      "coordinator": {
        "measurement_interval_ms": 1,
        "measurement_buffer_size": 100000,
        "auto_restart_failed_providers": true,
        "provider_restart_interval": 5000
      },
      "timing": {
        "precision": "high",
        "clock_source": "auto"
      }
    }
  }
}
```

**Precision Levels:**
- `low`: 100ms sampling, ~0.01% overhead, ±10% accuracy
- `medium`: 10ms sampling, ~0.1% overhead, ±5% accuracy
- `high`: 1ms sampling, ~1% overhead, ±2% accuracy

**Clock Sources:**
- `auto`: Automatically select best available (TSC → MONOTONIC_RAW → MONOTONIC)
- `tsc`: Time Stamp Counter (x86/x64 only, highest precision)
- `monotonic`: CLOCK_MONOTONIC (all platforms)

## Output Settings

```json
{
  "output": {
    "format": "json",       // json, table, csv
    "verbose": false,       // detailed output
    "save_to_file": true,   // save results to file
    "output_dir": "~/.config/codegreen/results"
  }
}
```

## Environment Variables

- `CODEGREEN_CONFIG`: Path to configuration file
- `CODEGREEN_DEBUG`: Enable debug output
- `CODEGREEN_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Configuration Commands

```bash
# Show current configuration
codegreen config --show

# Edit configuration in default editor
codegreen config --edit

# Validate configuration syntax
codegreen config --validate

# Reset to default configuration
codegreen config --reset
```

## Configuration File Locations (Priority Order)

1. `./codegreen.json` (Local override in current directory)
2. `~/.codegreen/codegreen.json` (User configuration)
3. `/etc/codegreen/codegreen.json` (System-wide configuration)
