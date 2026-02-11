# Configuration API

## Config File

CodeGreen searches for configuration in this order:

1. `<project_root>/config/codegreen.json` (relative to install dir)
2. `<project_root>/build/bin/config/codegreen.json`
3. `~/.codegreen/codegreen.json` (user home)

See [Configuration Reference](../user-guide/configuration-reference.md) for the full schema.

## CLI Commands

```bash
codegreen config --show       # Display current config
codegreen config --edit       # Open in editor
codegreen config --reset      # Reset to defaults
```

## Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `measurement.nemb.coordinator.measurement_interval_ms` | 1 | Polling frequency (ms) |
| `measurement.nemb.coordinator.measurement_buffer_size` | 100000 | Circular buffer size |
| `measurement.nemb.timing.precision` | high | Clock precision (low/medium/high) |
| `measurement.nemb.providers.intel_rapl.enabled` | true | Enable RAPL |
| `measurement.nemb.providers.nvidia_nvml.enabled` | true | Enable NVML |
| `measurement.nemb.accuracy.target_uncertainty_percent` | 1.0 | Target measurement accuracy |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CODEGREEN_CONFIG` | Override config file path |
| `CODEGREEN_DEBUG` | Enable debug mode |
| `CODEGREEN_LOG_LEVEL` | Set log level |
