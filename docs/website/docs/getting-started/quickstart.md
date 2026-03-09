# Quick Start

Get up and running with CodeGreen in minutes.

## 1. Install

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh
```

## 2. Initialize Sensors

```bash
sudo codegreen init-sensors
```

## 3. Verify Setup

```bash
codegreen measure-workload --duration 5 --workload cpu_stress
```

If you see energy values (Joules/Watts), sensors are working.

## 4. Measure Your Code

### Coarse Mode (default)

Total program energy -- instruments only main entry/exit:

```bash
codegreen measure python my_script.py
```

### Fine Mode

Per-function energy breakdown -- instruments all functions:

```bash
codegreen measure python my_script.py -g fine
```

### With Visualization

Export an interactive energy timeline:

```bash
codegreen measure python my_script.py -g fine --export-plot energy.html
```

Open `energy.html` in a browser to see:

- Per-function energy bar chart with hotspot detection
- Zoomable timeline with hover tooltips
- Summary stats (total energy, wall time, power)

### Quick Energy Measurement (any command)

Measure the energy of any shell command without instrumentation, similar to hyperfine:

```bash
codegreen run python my_script.py --repeat 10 --warmup 1
```

With JSON output and energy budget enforcement:

```bash
codegreen run --budget 10.0 --json python train.py
```

### C/C++ Programs

```bash
codegreen measure cpp main.cpp -- 5000
codegreen measure c algorithm.c
```

### Java Programs

```bash
codegreen measure java Main.java
```

## How It Works

When you run `codegreen measure`:

1. **Tree-sitter AST Parsing**: Identifies function boundaries and instrumentation points
2. **Code Instrumentation**: Injects lightweight checkpoint calls
3. **Background Polling**: C++ thread samples hardware sensors at 1ms intervals
4. **Execution**: Your code runs with ~100-200ns overhead per checkpoint
5. **Time-Series Correlation**: Binary search + linear interpolation matches checkpoints to energy readings
6. **Attribution**: Energy difference between enter/exit checkpoints = function energy

Checkpoints are timestamp markers (~100ns), not synchronous hardware reads (~5-20us). This achieves 25-100x lower overhead than traditional profiling.

## 5. Analyze Results

Output includes:

- **Total Energy**: Consumption in Joules
- **Average Power**: Draw in Watts
- **Function Breakdown**: Per-function energy with invocation counts (fine mode)
- **Hotspot Detection**: Functions consuming >90th percentile energy highlighted

## Next Steps

- [CLI Reference](../user-guide/cli-reference.md) - All commands and options
- [Configuration](configuration.md) - Customize measurement settings
- [Reports & Visualization](../user-guide/reports.md) - Energy timeline plots
- [CI/CD Integration](../user-guide/cicd-integration.md) - Continuous energy monitoring
