# Quick Start

Get up and running with CodeGreen in minutes!

## 1. Installation

The fastest way to install CodeGreen and its dependencies is using the installation script:

```bash
# Clone the repository
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen

# Run installer
./install.sh
```

## 2. Initialize System

CodeGreen needs to detect your hardware sensors (CPU/GPU) and set up permissions.

```bash
# Interactive initialization
codegreen init --interactive
```

## 3. Verify Setup

Run a quick benchmark to ensure sensors are reading data correctly:

```bash
codegreen benchmark cpu_stress --duration 5
```

**Note:** If you see "RAPL energy measurement not available" error, run with `sudo` or ensure you completed step 2 (`sudo codegreen init-sensors`) to set up sensor permissions.

If you see energy consumption values (Joules/Watts), you are ready to go!

## 4. Measure Your Code

### Python Scripts

```bash
# Analyze and measure a script
codegreen measure python my_script.py

# With arguments
codegreen measure python train_model.py --epochs 10

# High precision for detailed profiling
codegreen measure python optimize_me.py --precision high
```

### C/C++ Programs

```bash
# Measure a C++ source file (automatically compiled)
codegreen measure cpp main.cpp

# C program
codegreen measure c algorithm.c
```

### What Happens Internally

When you run `codegreen measure`:

1. **Tree-sitter AST Parsing**: Identifies function boundaries and instrumentation points
2. **Code Instrumentation**: Injects lightweight checkpoint calls (`name#inv_N_tTHREADID`)
3. **Background Polling**: C++ thread samples hardware sensors at 1ms intervals
4. **Execution**: Your code runs with ~100-200ns overhead per checkpoint
5. **Time-Series Correlation**: Binary search + linear interpolation matches checkpoints to energy readings
6. **Attribution**: Energy difference between enter/exit checkpoints = function energy

**Key Insight**: Checkpoints are timestamp markers (~100ns), not synchronous hardware reads (~5-20μs). This achieves 25-100x lower overhead than traditional profiling.

## 5. Analyze Results

View the output for:
- **Total Energy**: Consumption in Joules
- **Average Power**: Power draw in Watts
- **Function Breakdown**: Which functions consumed the most energy (with invocation counts)
- **Recursive Calls**: Separate energy attribution for each invocation
- **Multi-Threading**: Per-thread energy tracking
- **Optimization Tips**: Suggestions to improve efficiency

## Next Steps

- [CLI Reference](../user-guide/cli-reference.md) - Complete command reference
- [Configuration](configuration.md) - Customize settings
- [CI/CD Integration](../user-guide/cicd-integration.md) - Continuous integration workflows