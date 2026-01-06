# Configuration API Reference

Programmatic configuration and settings management.

## Overview

CodeGreen configuration can be managed through:
- JSON configuration files
- Environment variables
- Command-line arguments
- Programmatic API (advanced)

## Configuration File Format

### Complete Schema

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
        "provider_restart_interval": 5000
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
        "outlier_detection": true
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

  "output": {
    "format": "json",
    "verbose": false
  }
}
```

## Field Reference

### Measurement Configuration

#### `measurement.nemb.enabled`
- **Type**: boolean
- **Default**: `true`
- **Description**: Enable NEMB measurement backend

#### `measurement.nemb.coordinator.measurement_interval_ms`
- **Type**: integer
- **Range**: 1-100
- **Default**: `1` (high precision)
- **Description**: Background polling interval in milliseconds
- **Impact**: Lower = more accurate, higher overhead

#### `measurement.nemb.coordinator.measurement_buffer_size`
- **Type**: integer
- **Range**: 1000-1000000
- **Default**: `100000`
- **Description**: Circular buffer size for energy readings
- **Memory**: ~80 bytes per entry

#### `measurement.nemb.timing.precision`
- **Type**: enum
- **Values**: `"low"`, `"medium"`, `"high"`
- **Default**: `"high"`
- **Description**: Measurement precision level
- **Presets**:
  - `low`: 100ms interval, ~0.01% overhead, ±10% accuracy
  - `medium`: 10ms interval, ~0.1% overhead, ±5% accuracy
  - `high`: 1ms interval, ~1% overhead, ±2% accuracy

#### `measurement.nemb.timing.clock_source`
- **Type**: enum
- **Values**: `"auto"`, `"tsc"`, `"monotonic"`
- **Default**: `"auto"`
- **Description**: High-resolution timer source
- **Notes**:
  - `tsc`: Time Stamp Counter (x86/x64 only, nanosecond precision)
  - `monotonic`: CLOCK_MONOTONIC (all platforms)
  - `auto`: Automatically selects best available

### Provider Configuration

#### `measurement.nemb.providers.intel_rapl.enabled`
- **Type**: boolean
- **Default**: `true`
- **Description**: Enable Intel RAPL sensor

#### `measurement.nemb.providers.intel_rapl.domains`
- **Type**: array of strings
- **Default**: `["package", "pp0", "dram"]`
- **Values**: `"package"`, `"pp0"`, `"pp1"`, `"dram"`, `"psys"`
- **Description**: RAPL domains to measure

#### `measurement.nemb.providers.nvidia_nvml.enabled`
- **Type**: boolean
- **Default**: `true`
- **Description**: Enable NVIDIA GPU measurement

#### `measurement.nemb.providers.nvidia_nvml.device_indices`
- **Type**: array of integers
- **Default**: `[0]`
- **Description**: GPU device indices to monitor

### Instrumentation Configuration

#### `instrumentation.checkpoint_strategy`
- **Type**: enum
- **Values**: `"minimal"`, `"functions"`, `"blocks"`, `"all"`
- **Default**: `"functions"`
- **Description**: Checkpoint placement strategy

#### `instrumentation.track_invocations`
- **Type**: boolean
- **Default**: `true`
- **Description**: Track invocation count for recursive functions

#### `instrumentation.track_threads`
- **Type**: boolean
- **Default**: `true`
- **Description**: Include thread ID in checkpoint names

## Environment Variables

Override configuration via environment variables:

| Variable | Config Path | Example |
|----------|-------------|---------|
| `CODEGREEN_PRECISION` | `measurement.nemb.timing.precision` | `high` |
| `CODEGREEN_INTERVAL_MS` | `measurement.nemb.coordinator.measurement_interval_ms` | `1` |
| `CODEGREEN_CONFIG` | N/A (config file path) | `/path/to/config.json` |
| `CODEGREEN_LOG_LEVEL` | `paths.logs.level` | `DEBUG` |
| `CODEGREEN_TEMP_DIR` | `paths.temp_directory.base` | `/tmp/codegreen` |

**Usage:**
```bash
export CODEGREEN_PRECISION=high
export CODEGREEN_LOG_LEVEL=DEBUG
codegreen measure python app.py
```

## Command-Line Overrides

Override configuration via CLI arguments:

```bash
codegreen measure python app.py \
    --precision high \
    --sensors rapl nvidia \
    --output results.json \
    --config /path/to/custom_config.json
```

**Priority:** CLI args > Environment vars > Config file > Defaults

## Programmatic Configuration (C++)

### Load Configuration

```cpp
#include <codegreen/config_loader.hpp>

codegreen::ConfigLoader config("config.json");

// Access values
int interval = config.get_int("measurement.nemb.coordinator.measurement_interval_ms");
std::string precision = config.get_string("measurement.nemb.timing.precision");
bool rapl_enabled = config.get_bool("measurement.nemb.providers.intel_rapl.enabled");
```

### Modify Configuration

```cpp
codegreen::ConfigLoader config;

config.set("measurement.nemb.timing.precision", "high");
config.set("measurement.nemb.coordinator.measurement_interval_ms", 1);

config.save("updated_config.json");
```

## Programmatic Configuration (Python)

### Load Configuration

```python
import json

with open('config.json') as f:
    config = json.load(f)

precision = config['measurement']['nemb']['timing']['precision']
interval = config['measurement']['nemb']['coordinator']['measurement_interval_ms']
```

### Modify Configuration

```python
import json

with open('config.json') as f:
    config = json.load(f)

config['measurement']['nemb']['timing']['precision'] = 'high'
config['measurement']['nemb']['coordinator']['measurement_interval_ms'] = 1

with open('config.json', 'w') as f:
    json.dump(config, f, indent=2)
```

## Configuration Management Commands

### View Current Configuration

```bash
codegreen config --show
```

### Validate Configuration

```bash
codegreen config --validate
```

### Edit Configuration

```bash
codegreen config --edit
```

Opens configuration in default editor (respects `$EDITOR`).

### Reset to Defaults

```bash
codegreen config --reset
```

## Configuration File Locations

CodeGreen searches for configuration in this order (first found is used):

1. **Specified via CLI**: `--config /path/to/config.json`
2. **Environment variable**: `$CODEGREEN_CONFIG`
3. **Current directory**: `./codegreen.json`
4. **User configuration**: `~/.config/codegreen/codegreen.json`
5. **System-wide**: `/etc/codegreen/codegreen.json`

### Check Active Configuration

```bash
codegreen info --verbose
```

Shows which configuration file is being used.

## Best Practices

### 1. Project-Specific Configuration

Commit project config to version control:

```bash
# Create project config
cp ~/.config/codegreen/codegreen.json ./codegreen.json

# Customize for project
vim codegreen.json

# Commit
git add codegreen.json
git commit -m "Add CodeGreen configuration"
```

### 2. User-Wide Defaults

Set personal defaults:

```bash
mkdir -p ~/.config/codegreen
cp /usr/share/codegreen/codegreen.json ~/.config/codegreen/
vim ~/.config/codegreen/codegreen.json
```

### 3. CI/CD Configuration

Use environment variables in CI:

```yaml
# .github/workflows/energy.yml
env:
  CODEGREEN_PRECISION: high
  CODEGREEN_INTERVAL_MS: 1

steps:
  - run: codegreen measure python app.py
```

### 4. Validation in Tests

Validate configuration in test suite:

```python
# test_config.py
import json
import pytest

def test_config_valid():
    with open('codegreen.json') as f:
        config = json.load(f)

    assert config['version'] == '0.1.0'
    assert config['measurement']['nemb']['enabled'] is True
    assert 1 <= config['measurement']['nemb']['coordinator']['measurement_interval_ms'] <= 100
```

## Troubleshooting

### Configuration Not Loading

**Check search path:**
```bash
codegreen info --verbose
# Shows: "Configuration loaded from: /path/to/config.json"
```

### Syntax Errors

**Validate JSON:**
```bash
python3 -m json.tool codegreen.json
# OR
codegreen config --validate
```

### Permission Issues

**RAPL access:**
```bash
sudo codegreen init-sensors
```

## See Also

- [Configuration Guide](../user-guide/configuration-reference.md) - Complete configuration reference
- [CLI Reference](../user-guide/cli-reference.md) - Command-line options
- [Installation](../getting-started/installation.md) - Setup guide
