# Configuration

CodeGreen uses a JSON configuration file to customize behavior and sensor settings.

## Configuration File Location

- **Default**: `~/.config/codegreen/codegreen.json`
- **Custom**: Use `--config` flag: `codegreen --config /path/to/config.json`

## Basic Configuration

```json
{
  "pmt": {
    "auto_detect": true,
    "cache_sensor_config": true,
    "sensor_config_cache_path": "~/.config/codegreen/sensor_cache.json",
    "sensor_config": {
      "rapl": "auto",
      "nvml": "auto", 
      "dummy": "on"
    }
  },
  "measurement": {
    "precision": "medium",
    "timeout": 30,
    "sample_rate": 1000
  },
  "output": {
    "format": "json",
    "verbose": false
  }
}
```

## Sensor Configuration

### Available Sensors

- **RAPL**: Intel/AMD CPU energy monitoring
- **NVML**: NVIDIA GPU monitoring  
- **AMD_SMI**: AMD GPU monitoring
- **ROCm**: AMD GPU via ROCm
- **PowerSensor**: USB power measurement devices
- **LIKWID**: Performance monitoring
- **Dummy**: Fallback sensor for testing

### Sensor Settings

```json
{
  "pmt": {
    "sensor_config": {
      "rapl": "auto",      // auto, on, off
      "nvml": "auto",      // auto, on, off
      "amd_smi": "off",    // auto, on, off
      "rocm": "off",       // auto, on, off
      "powersensor": "off", // auto, on, off
      "likwid": "off",     // auto, on, off
      "dummy": "on"        // always on for fallback
    }
  }
}
```

## Measurement Settings

```json
{
  "measurement": {
    "precision": "medium",  // low, medium, high
    "timeout": 30,          // seconds
    "sample_rate": 1000,    // Hz
    "baseline_duration": 1.0, // seconds
    "cooldown_duration": 0.5  // seconds
  }
}
```

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
codegreen config show

# Validate configuration
codegreen config validate

# Reset to defaults
codegreen config reset
```
