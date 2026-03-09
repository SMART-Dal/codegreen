# Energy Measurement

CodeGreen uses the Native Energy Measurement Backend (NEMB) for hardware-level energy monitoring.

## Supported Hardware Sensors

| Sensor | Driver | Implementation | Platform |
|--------|--------|----------------|----------|
| **CPU (Intel/AMD)** | Intel RAPL | `intel_rapl_provider.cpp` | Linux |
| **GPU (NVIDIA)** | NVIDIA NVML | `nvidia_gpu_provider.cpp` | Linux |
| **GPU (AMD)** | AMD ROCm SMI | `amd_gpu_provider.cpp` | Linux |
| **CPU (AMD)** | AMD RAPL | `amd_rapl_provider.cpp` | Linux |

### RAPL Domains

Intel RAPL exposes multiple energy domains. CodeGreen dynamically enumerates available domains at runtime, including multi-socket systems:

| Domain | What it measures |
|--------|-----------------|
| `package` | Entire CPU socket (cores + uncore) |
| `pp0` / `core` | CPU cores only |
| `pp1` | Integrated GPU (where available) |
| `dram` | Memory subsystem |
| `psys` | Entire platform (where available) |

## Measurement Architecture

### Background Polling

NEMB runs a dedicated high-priority C++ thread that samples hardware sensors at 1ms intervals (configurable). Energy readings are stored in a circular buffer for later correlation.

### Signal-Generator Model

Instead of synchronous hardware reads at every checkpoint (~5-20us each), CodeGreen inserts lightweight timestamp signals (~100-200ns) into the instrumented code. This is 25-100x lower overhead.

### Correlation and Interpolation

After the workload completes, NEMB correlates checkpoint timestamps with the time-series energy data using binary search + linear interpolation to attribute energy between function enter/exit points.

## Granularity Modes

| Mode | What gets instrumented | Use case |
|------|----------------------|----------|
| **coarse** (default) | Main entry/exit only | Total program energy, minimal overhead |
| **fine** | All functions per language config | Per-function energy breakdown |

```bash
# Coarse: 2 checkpoints (enter + exit main)
codegreen measure python script.py

# Fine: N checkpoints (enter + exit for each function)
codegreen measure python script.py -g fine
```

## Visualization

Use `--export-plot` to generate an interactive energy timeline:

```bash
codegreen measure python script.py -g fine --export-plot energy.html
```

The HTML output (via Plotly) includes:

- **Function energy bar chart**: Horizontal bars sorted by energy consumption
- **Hotspot detection**: Functions >90th percentile highlighted in red
- **Zoomable timeline**: Scatter plot with zoom, pan, hover tooltips
- **Summary stats**: Total energy, wall time, average/peak power

For static images:
```bash
codegreen measure python script.py -g fine --export-plot energy.png  # requires matplotlib
```

## Benchmarking

CodeGreen includes a built-in benchmark suite using programs from the [Benchmarks Game](https://benchmarksgame-team.pages.debian.net/benchmarksgame/) to validate energy measurement accuracy.

### Running Benchmarks

```bash
# Run all available benchmarks
codegreen benchmark

# Specific problem and language
codegreen benchmark -p nbody -l python -s 5000

# Compare CodeGreen vs perf RAPL
codegreen benchmark -p nbody --profiler codegreen --profiler perf

# Custom output directory
codegreen benchmark -p nbody -l python -o benchmark/results
```

### Available Programs

| Problem | Languages | Description |
|---------|-----------|-------------|
| nbody | Python, C, C++ | N-body gravitational simulation |
| binarytrees | Python, C, C++ | Binary tree allocation/deallocation |
| spectralnorm | Python, C, C++ | Spectral norm computation |
| fannkuchredux | Python, C, C++ | Pancake sorting permutations |
| fasta | Python, C, C++ | FASTA format sequence generation |

### Benchmark Output

Results are saved as JSON in `benchmark/results/` with per-run energy, time, and checkpoint data. CSV summaries are also generated.

### Quick Sensor Test

For a quick test of sensor accuracy:

```bash
codegreen measure-workload --duration 3
```

### Checkpoint Throttling

For workloads with very high checkpoint rates, set the `CODEGREEN_CHECKPOINT_THROTTLE_MS` environment variable to throttle checkpoint recording. This limits how frequently checkpoints are recorded, reducing overhead for tight loops:

```bash
CODEGREEN_CHECKPOINT_THROTTLE_MS=5 codegreen measure python script.py -g fine
```

### Benchmark Accuracy

Validated against `perf stat` RAPL readings on representative workloads:

| Benchmark | Error vs perf RAPL |
|-----------|-------------------|
| binarytrees/18 | 0.03% |
| spectralnorm/1000 | 0.71% |

Short workloads are automatically repeated to accumulate sufficient energy for accurate measurement.

## Quick Energy Measurement

For measuring any shell command without code instrumentation:

```bash
codegreen run python script.py --repeat 10 --warmup 1
codegreen run --budget 5.0 --json ./my_binary arg1 arg2
```

See [CLI Reference](cli-reference.md#run) for full options.

## Performance

| Metric | Value |
|--------|-------|
| Checkpoint overhead | ~100-200ns per checkpoint |
| Polling interval | 1ms (configurable) |
| Background thread overhead | Negligible |
| Visualization overhead | Zero (post-measurement only) |
