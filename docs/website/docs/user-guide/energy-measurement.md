# Energy Measurement Guide

Complete guide to measuring energy consumption with CodeGreen.

## Overview

CodeGreen measures energy consumption at the function level using hardware sensors (Intel RAPL, NVIDIA NVML, AMD ROCm). The measurement system uses a signal-generator architecture that achieves sub-millisecond accuracy with minimal overhead.

## Supported Sensors

### Intel/AMD CPUs (RAPL)

**Running Average Power Limit** provides energy counters for:
- **Package**: Total CPU package energy (cores + uncore + integrated GPU)
- **PP0 (Power Plane 0)**: CPU cores only
- **PP1 (Power Plane 1)**: Integrated GPU (if present)
- **DRAM**: Memory subsystem
- **PSYS**: Platform energy (Skylake and newer)

**Requirements:**
- Intel CPU (Sandy Bridge or newer) or AMD CPU (Ryzen or newer)
- Linux kernel with powercap interface
- Read access to `/sys/class/powercap/intel-rapl:*/energy_uj`

**Accuracy:** ±2% for package measurements

### NVIDIA GPUs (NVML)

**NVIDIA Management Library** provides GPU energy consumption.

**Requirements:**
- NVIDIA GPU (Kepler or newer recommended)
- NVIDIA drivers 450.80.02+
- Optional: CUDA Toolkit 11.0+ for advanced features

**Accuracy:** ±5% based on power sensors

### AMD GPUs (ROCm SMI)

**ROCm System Management Interface** for AMD GPU monitoring.

**Requirements:**
- AMD GPU (Vega or newer)
- ROCm drivers installed
- Access to `/sys/class/drm/*/device/power*`

**Accuracy:** ±5% for supported GPUs

## How It Works

### Signal-Generator Architecture

CodeGreen uses a decoupled measurement model:

1. **Checkpoint Marking (Application Thread)**
   - When your code calls a function, CodeGreen injects a lightweight checkpoint
   - The checkpoint records a high-precision timestamp (~100-200ns overhead)
   - No blocking I/O or hardware reads during code execution

2. **Background Polling (Measurement Thread)**
   - Independent C++ thread polls hardware sensors at configurable intervals (1-100ms)
   - Builds a time-series of cumulative energy readings
   - Runs independently without blocking application code

3. **Correlation (Post-Execution)**
   - After execution, CodeGreen correlates checkpoint timestamps with energy time-series
   - Uses binary search + linear interpolation for sub-millisecond accuracy
   - Calculates energy consumed between function entry and exit

### Mathematical Model

Energy at checkpoint time `tm` is interpolated from sensor readings:

```
E(tm) = E(ti) + (E(ti+1) - E(ti)) × ((tm - ti) / (ti+1 - ti))
```

Where:
- `(ti, E(ti))` and `(ti+1, E(ti+1))` are consecutive sensor readings
- `ti < tm < ti+1` (checkpoint falls between readings)

This achieves accurate energy attribution even for functions shorter than the polling interval.

## Precision Levels

Configure measurement precision vs overhead tradeoff:

| Level | Polling Interval | Overhead | Accuracy | Use Case |
|-------|-----------------|----------|----------|----------|
| **low** | 100ms | ~0.01% | ±10% | Production monitoring, long-running services |
| **medium** | 10ms | ~0.1% | ±5% | Development, general profiling (default) |
| **high** | 1ms | ~1% | ±2% | Detailed profiling, optimization work |

**Set precision:**
```bash
codegreen measure python script.py --precision high
```

## Measurement Modes

### 1. Function-Level Measurement (Default)

Automatically instruments all functions:

```bash
codegreen measure python myapp.py --precision high --output results.json
```

**Output:**
```json
{
  "total_energy_joules": 15.43,
  "execution_time_ms": 1250.5,
  "average_power_watts": 12.34,
  "functions": {
    "process_data": {
      "energy_joules": 12.15,
      "invocations": 1,
      "average_power_watts": 12.50
    },
    "parse_input": {
      "energy_joules": 0.28,
      "invocations": 5,
      "average_power_watts": 9.20
    }
  }
}
```

### 2. Multi-Sensor Measurement

Measure CPU and GPU simultaneously:

```bash
codegreen measure python ml_train.py --sensors rapl nvidia --precision high
```

**Output includes per-sensor breakdown:**
```json
{
  "sensors": {
    "rapl": {
      "package": 145.32,
      "pp0": 120.45,
      "dram": 24.87
    },
    "nvidia_gpu_0": {
      "gpu": 234.56
    }
  },
  "total_energy_joules": 379.88
}
```

### 3. Validation Mode

Compare against native tools (requires root):

```bash
sudo codegreen validate --duration 30 --tolerance 5
```

Runs built-in benchmarks and compares CodeGreen measurements against Linux `perf` for validation.

## Best Practices

### 1. Sensor Initialization

Always initialize sensors before first measurement:

```bash
sudo codegreen init-sensors
```

This sets up permissions and caches sensor configuration. Only needs to be run once per system.

### 2. Baseline Measurements

Establish energy baselines for comparison:

```bash
# Measure baseline
codegreen measure python app.py --output baseline.json

# After optimization
codegreen measure python app.py --output optimized.json

# Compare
python -c "
import json
with open('baseline.json') as f: baseline = json.load(f)
with open('optimized.json') as f: optimized = json.load(f)
improvement = (baseline['total_energy_joules'] - optimized['total_energy_joules']) / baseline['total_energy_joules'] * 100
print(f'Energy improvement: {improvement:.1f}%')
"
```

### 3. Multiple Runs for Stability

Average across multiple runs:

```bash
for i in {1..5}; do
    codegreen measure python app.py --output run$i.json
done
```

Compute statistics across runs to account for system noise.

### 4. Minimize Background Load

For accurate measurements:
- Close unnecessary applications
- Disable CPU frequency scaling: `sudo cpupower frequency-set --governor performance`
- Run on consistent hardware (avoid thermal throttling)

### 5. Warm-up Iterations

For JIT-compiled languages (Java, Python JIT):

```bash
# Warm-up run (discarded)
python app.py

# Actual measurement
codegreen measure python app.py --precision high
```

This ensures JIT optimizations are applied before measurement.

## Common Measurement Scenarios

### Scenario 1: Algorithm Comparison

```python
# algorithms.py
def algorithm_a(data):
    # Implementation A
    return sorted(data)

def algorithm_b(data):
    # Implementation B
    data_copy = data.copy()
    data_copy.sort()
    return data_copy

def main():
    data = [random.randint(1, 1000) for _ in range(100000)]
    result_a = algorithm_a(data)
    result_b = algorithm_b(data)
```

**Measure:**
```bash
codegreen measure python algorithms.py --precision high --output algo_energy.json
```

**Analyze per-function energy** to determine which algorithm is more energy-efficient.

### Scenario 2: Optimization Verification

Before optimization:
```bash
codegreen measure python app_v1.py --output v1_energy.json
```

After optimization:
```bash
codegreen measure python app_v2.py --output v2_energy.json
```

Compare total energy and per-function breakdown.

### Scenario 3: GPU vs CPU Execution

```bash
# CPU version
codegreen measure python ml_cpu.py --sensors rapl --output cpu_energy.json

# GPU version
codegreen measure python ml_gpu.py --sensors rapl nvidia --output gpu_energy.json
```

Compare total energy consumption including data transfer overhead.

## Measurement Accuracy

### Validation Results

CodeGreen measurements validated against Linux `perf`:

| Workload | CodeGreen | Linux perf | Delta |
|----------|-----------|------------|-------|
| Long-running (800J+) | 801.96 J | 834.30 J | -3.88% |
| Short-running (<5J) | 0.23 J | 2.40 J | -90%* |

*Short-running delta is intentional - CodeGreen excludes runtime overhead (interpreter startup), isolating algorithm energy.

### Accuracy Factors

**Hardware Resolution:**
- RAPL: ~61 μJ (microjoule) resolution
- NVML: GPU-dependent, typically ~1 mW resolution
- Update rate: 1-1000 Hz depending on hardware

**Measurement Uncertainty:**
- Systematic error: <1% (calibrated against external meters)
- Random error: <1% (for workloads >1 second)
- Total uncertainty: ±2% at 95% confidence (high precision mode)

### Known Limitations

1. **Short-Duration Functions** (<1ms): May have higher relative uncertainty
2. **Thermal Throttling**: Can affect repeatability if system overheats
3. **Idle Power**: Baseline platform power (15-30W) included in measurements
4. **Multi-Socket Systems**: RAPL per-socket, requires aggregation

## Troubleshooting

### "Permission denied" accessing RAPL

**Solution:**
```bash
sudo codegreen init-sensors
```

Or manually:
```bash
sudo chmod 644 /sys/class/powercap/intel-rapl:*/energy_uj
```

### Inconsistent measurements between runs

**Causes:**
- Background processes consuming CPU
- CPU frequency scaling
- Thermal throttling

**Solutions:**
```bash
# Set performance governor
sudo cpupower frequency-set --governor performance

# Check for throttling
watch -n 1 "grep MHz /proc/cpuinfo"
```

### NVIDIA GPU not detected

**Check drivers:**
```bash
nvidia-smi
codegreen info --verbose
```

**Verify permissions:**
```bash
ls -l /dev/nvidia*
```

### Energy values seem too high/low

**Validate measurement system:**
```bash
sudo codegreen validate --quick
```

Runs known benchmarks with expected energy values.

## Advanced Configuration

### Custom Sensor Selection

```bash
# CPU only
codegreen measure python app.py --sensors rapl

# GPU only
codegreen measure python app.py --sensors nvidia

# Both
codegreen measure python app.py --sensors rapl nvidia
```

### Precision Tuning

Edit `~/.config/codegreen/codegreen.json`:

```json
{
  "measurement": {
    "nemb": {
      "coordinator": {
        "measurement_interval_ms": 1,
        "measurement_buffer_size": 100000
      },
      "timing": {
        "precision": "high",
        "clock_source": "auto"
      }
    }
  }
}
```

### Output Formats

**JSON (machine-readable):**
```bash
codegreen measure python app.py --output results.json --json
```

**Human-readable summary:**
```bash
codegreen measure python app.py
```

## See Also

- [CLI Reference](cli-reference.md) - Complete command options
- [Configuration Reference](configuration-reference.md) - Advanced configuration
- [Examples](../examples/python.md) - Practical examples
- [CI/CD Integration](cicd-integration.md) - Automated measurement
