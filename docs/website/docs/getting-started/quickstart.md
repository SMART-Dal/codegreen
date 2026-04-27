# Quick start

Get a real energy measurement in three steps. For end-to-end examples (training loops, GPT-2 inference, mode comparison), continue to [Python examples](../examples/python.md). For every parameter and field, see the [Python API](../api/python.md).

## 1. Install

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh
```

## 2. Initialize sensors

```bash
sudo codegreen init-sensors
```

## 3. Verify setup

```bash
codegreen measure-workload --duration 5 --workload cpu_stress
```

If you see energy values (Joules/Watts), sensors are working.

## 4. Measure your code

Three idioms, pick one:

### From Python (recommended for libraries / scripts)

Bracket the regions you care about with `codegreen.Session`. Hardware counters are read in-process; no CLI wrapper, no AST instrumentation:

```python
import codegreen

with codegreen.Session("training") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        train()
# writes codegreen_<pid>.json with per-task energy + per-domain breakdown
```

For all three forms (context manager, explicit `start_task`/`stop_task`, decorator) and power-vs-time plots, see [Python examples](../examples/python.md). For every parameter and field, see the [Python API](../api/python.md).

### Whole-script measurement (any command)

Wrap an unmodified command. No source changes:

```bash
codegreen run python my_script.py --repeat 10 --warmup 1
codegreen run --budget 10.0 --json python train.py     # CI energy budget
```

### Per-function auto-instrumentation

Inject checkpoints at function boundaries via tree-sitter:

```bash
codegreen measure python my_script.py                              # coarse: main only
codegreen measure python my_script.py -g fine                      # all functions
codegreen measure python my_script.py -g fine --export-plot energy.html
```

The HTML plot has a per-function bar chart with hotspot highlighting and a zoomable timeline.

### C/C++ programs

```bash
codegreen measure cpp main.cpp -- 5000
codegreen measure c algorithm.c
```

### Java programs

```bash
codegreen measure java Main.java
```

## How `codegreen measure` works

1. Tree-sitter parses the source and locates function boundaries.
2. Lightweight checkpoint calls are injected at enter/exit.
3. A background C++ thread samples hardware sensors at the configured interval (default 1 ms; see `coordinator.measurement_interval_ms` in `config.json`, or pass `sample_interval_ms=N` to `Session`).
4. At process exit, checkpoints are correlated with sample timestamps via binary search + linear interpolation.
5. Energy between enter/exit = function energy.

Checkpoints are timestamp markers (~100 ns), not synchronous hardware reads (~5-20 us), giving 25-100x lower overhead than traditional profiling.

`codegreen.Session` skips steps 1-2 entirely: you mark the regions yourself, the same backend reads counters directly.

## 5. Analyze results

Output includes total energy (J), average power (W), per-function breakdown with invocation counts (fine mode), and hotspot highlighting (>90th percentile).

## Next steps

- [Python examples](../examples/python.md) - end-to-end workloads, GPT-2 inference, CLI vs Session comparison
- [Python API](../api/python.md) - every `Session` parameter, every `TaskResult` field
- [CLI reference](../user-guide/cli-reference.md) - all commands and options
- [Configuration](configuration.md) - sampling rate, output paths
- [CI/CD integration](../user-guide/cicd-integration.md) - continuous energy monitoring
