# Python examples

End-to-end workloads. New here? Start with the [Quickstart](../getting-started/quickstart.md). Looking up a parameter or field? Jump to the [Python API](../api/python.md).

The first half of this page covers the in-process `codegreen.Session`, which is the v0.4.0 headline feature. The second half covers the `codegreen measure` auto-instrumenter for legacy / no-source-edit scenarios.

## Manual measurement with `codegreen.Session`

`Session` brackets in-process code regions and reads RAPL/NVML hardware counters directly. No CLI wrapper, no AST instrumentation, no extra subprocess.

### Context-manager form (recommended)

```python
import codegreen

with codegreen.Session("training-run") as s:
    with s.task("data_load"):
        load_data()
    with s.task("train"):
        train_model()
    with s.task("eval"):
        evaluate()
# at exit: writes codegreen_<pid>.json with per-task energy + per-domain breakdown
```

### Explicit `start_task` / `stop_task`

For sequential measurement points where a `with` block is awkward:

```python
import codegreen

s = codegreen.Session("pipeline").start()

s.start_task("preprocess")
preprocess_data()
s.stop_task("preprocess")          # name is asserted; mismatch raises RuntimeError

s.start_task("train")
model.fit(...)
s.stop_task("train")

s.start_task("eval")
score = model.evaluate(...)
s.stop_task("eval")

report = s.stop()                  # returns dict; writes codegreen_<pid>.json
```

Identical semantics to the context-manager form — both call the same internal `_begin_task` / `_end_task`. Pass `expected_name` to `stop_task()` to assert you're closing the right task; omit it to just close the innermost.

### Decorator form

```python
import codegreen

@codegreen.task("inference")
def infer(batch): ...

with codegreen.Session("svc"):
    for b in batches:
        infer(b)        # each call is one task
```

### Accessing raw results

`Session.stop()` returns a dict you can inspect directly. The same dict gets written to `codegreen_<pid>.json` (or your `output_file=`).

```python
import json, os
import codegreen

with codegreen.Session("training", record_time_series=True) as s:
    with s.task("epoch1"): train_epoch()
    with s.task("epoch2"): train_epoch()

# Mid-flight access via .tasks (list of TaskResult dataclasses)
for t in s.tasks:
    print(t.name, t.energy_j, t.avg_power_w, t.duration_s)
    print("  per-domain (J):", t.domains)        # {"package-0": ..., "core": ..., "gpu0": ...}
    if t.timeseries:
        for sample in t.timeseries[:3]:
            print("  sample:", sample)
            # {"t": 20364878312447553, "j": 7.94, "w": 37.4,
            #  "d": {"package-0": 7.92, "core": 0.0018, "gpu0": 0.022}}

# Or load from disk afterwards
with open(f"codegreen_{os.getpid()}.json") as f:
    report = json.load(f)
```

For the full `TaskResult` schema, see the [Python API → TaskResult fields](../api/python.md#taskresult-fields).

To get power-vs-time arrays for any plotting library:

```python
import numpy as np

t = s.tasks[0]
times_s = [(p["t"] - t.timeseries[0]["t"]) / 1e9 for p in t.timeseries]
powers  = [p["w"] for p in t.timeseries]
energy  = np.trapz(powers, times_s)   # ~ t.energy_j to within ~0.2%
```

### Plot export — `Session.export_plot(path)`

The format is chosen from the file extension; no extra arguments:

```python
with codegreen.Session("infer", record_time_series=True) as s:
    with s.task("warmup"): warmup()
    with s.task("batch1"): infer(batch1)
    with s.task("batch2"): infer(batch2)

    s.export_plot("infer.html")    # interactive Plotly (zoom/pan/hover)
    s.export_plot("infer.png")     # static matplotlib
    s.export_plot("infer.svg")     # vector
    s.export_plot("infer.pdf")     # publication-ready
```

Each task is a separate trace. Y-axis = power (W), x-axis = wall time relative to first sample. **Area under each task's curve = that task's energy** (verified <=0.2% deviation against the NEMB-reported total via trapezoidal integration on a 5 s task with ~4,800 samples).

`export_plot` requires `record_time_series=True`. Without time series, the call is a no-op.

> **Note.** Enabling `record_time_series=True` runs an in-process drain thread that pulls samples out of the C++ ring buffer. The mean of total energy is unchanged (≤ 0.3 % vs sampling off, well within run-to-run jitter), but the run-to-run **spread is slightly wider** because the drain thread occasionally competes with the workload for CPU. Use it during development for plots and the noise/quality summary; turn it off for production benchmark runs that want the tightest possible CV. See the [API reference](../api/python.md#noise--quality-reporting) for the full breakdown.

### Real-world example: text generation with per-domain attribution

A mixed CPU/GPU workload: tokenization runs on the CPU, the transformer forward pass runs on the GPU when present, and CodeGreen breaks the resulting energy down by hardware domain so you can see where the joules went.

```python
import codegreen, torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer

device = "cuda" if torch.cuda.is_available() else "cpu"
tok    = GPT2Tokenizer.from_pretrained("gpt2")
tok.pad_token = tok.eos_token
model  = GPT2LMHeadModel.from_pretrained("gpt2").to(device).eval()

prompts = [
    "Energy-aware computing is",
    "The cheapest way to train a model is",
    "Hardware energy counters report",
]

with codegreen.Session("gpt2-gen", record_time_series=True) as s:
    with s.task("tokenize"):
        batch = tok(prompts, padding=True, return_tensors="pt").to(device)
    with s.task("generate"):
        with torch.no_grad():
            out = model.generate(**batch, max_new_tokens=64, do_sample=False)
    with s.task("decode"):
        completions = tok.batch_decode(out, skip_special_tokens=True)
    s.export_plot("gpt2-gen.html")

for t in s.tasks:
    print(f"{t.name:<10} {t.energy_j:7.2f} J   {t.avg_power_w:6.1f} W   "
          f"{t.duration_s:5.2f} s   domains={t.domains}")
```

Measured output on an AMD EPYC 9554P + NVIDIA RTX 5000 Ada host (3 prompts, 64 new tokens each):

```
tokenize      0.12 J    84.3 W   0.00 s   domains={'core': 0.0003, 'gpu0': 0.044,  'package-0': 0.080}
generate     84.78 J   123.3 W   0.69 s   domains={'core': 0.174,  'gpu0': 29.85,  'package-0': 54.93}
decode        0.25 J   163.7 W   0.00 s   domains={'core': 0.0004, 'gpu0': 0.088,  'package-0': 0.159}
```

`package-0` and `core` are RAPL CPU-package readings (Intel/AMD); `dram-0` appears on Intel hosts with separate DRAM counters; `gpu0` is NVML for the first NVIDIA GPU. On a CPU-only host the GPU domain simply isn't present — same code, the report just narrows.

#### Sanity-check: same workload, different access modes

The shipped `benchmark/cg_modes_compare.py` runs an identical GPT-2 generation workload three times — once via `codegreen run`, once bracketed under `codegreen.Session` from inside the script, and once with bare `time.perf_counter()` for a wall-clock control:

```bash
python -m benchmark.cg_modes_compare      # 3 repeats per mode
```

Real run, same hardware, 32 prompts x 128 tokens:

| mode                     | energy (J)        | power (W) | wall (s) | runs |
|--------------------------|-------------------|----------:|---------:|------|
| Bare (timing only)       | n/a               | n/a       | 5.64     | 3/3  |
| `codegreen run` (CLI)    | 831.56 +/- 2.36   | 148.6     | 5.59     | 3/3  |
| `codegreen.Session`      | 667.26 +/- 5.11   | 139.6     | 4.78     | 3/3  |

Three observations:

- **Coefficient of variation is 0.3% / 0.8%** across repeats — the readings are tight and reproducible. Instrumentation isn't adding noise.
- **The two modes agree on power** (within ~6%): both are reading the same RAPL/NVML counters. The small spread is the natural difference between busy and idle phases of the process.
- **The 19.8% gap in total joules is not error — it's span.** `codegreen run` brackets the entire Python subprocess (interpreter startup, every `import`, atexit, GC); `Session` brackets only the in-process region you put around the script body. The 0.81 s wall-time difference, multiplied by ~140 W steady-state power, accounts for ~113 J of the ~164 J delta — exactly what you'd expect from measuring different windows.

Pick the mode that matches the question: "what does this script cost end-to-end?" -> `codegreen run`; "what does this code region cost?" -> `Session`.

### Caveats

- **One Session per process.** Constructing a second while one is active raises `RuntimeError`.
- **Mismatched `stop_task("X")`** raises `RuntimeError` naming the actually-innermost task.
- **Forgotten `stop()`** is recovered by an `atexit` hook; file written, drain thread joined.
- **Forked children** become no-ops automatically; only the parent reports.
- **Concurrent CodeGreen processes on the same host** trigger a warning at construction (RAPL is system-wide; readings overlap).
- **No NEMB lib loaded** -> graceful no-op with a one-time warning; your program still runs.

## Auto-instrumentation via `codegreen measure`

For scripts where you don't want to (or can't) edit the source, `codegreen measure` parses the file with tree-sitter and injects checkpoints at function boundaries.

### Basic auto-instrumentation

```python
# hello_energy.py
def greet(name):
    message = f"Hello, {name}!"
    return message

def calculate_sum(n):
    total = sum(range(n))
    return total

def main():
    result = greet("CodeGreen")
    print(result)
    total = calculate_sum(1000000)
    print(f"Sum: {total}")

if __name__ == "__main__":
    main()
```

**Measure:**
```bash
# Coarse mode: total program energy
codegreen measure python hello_energy.py

# Fine mode: per-function breakdown
codegreen measure python hello_energy.py -g fine

# With visualization
codegreen measure python hello_energy.py -g fine --export-plot energy.html
```

## Algorithm comparison

Compare energy consumption of different sorting implementations:

```python
# sorting_comparison.py
import random

def generate_data(size):
    random.seed(42)
    return [random.randint(1, 10000) for _ in range(size)]

def bubble_sort(arr):
    n = len(arr)
    arr = arr.copy()
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

def main():
    data = generate_data(5000)
    bubble_result = bubble_sort(data)
    print(f"Bubble sort first: {bubble_result[0]}")
    quick_result = quick_sort(data)
    print(f"Quick sort first: {quick_result[0]}")

if __name__ == "__main__":
    main()
```

**Measure with per-function breakdown:**
```bash
codegreen measure python sorting_comparison.py -g fine --export-plot sorting.html
```

The energy timeline will show `bubble_sort` consuming significantly more energy than `quick_sort` due to O(n^2) vs O(n log n) complexity.

## Optimization before/after

**Before (inefficient):**
```python
# string_concat_slow.py
def concatenate_slow(n):
    result = ""
    for i in range(n):
        result += f"item{i},"
    return result

def main():
    result = concatenate_slow(50000)
    print(f"Length: {len(result)}")

if __name__ == "__main__":
    main()
```

**After (optimized):**
```python
# string_concat_fast.py
def concatenate_fast(n):
    parts = []
    for i in range(n):
        parts.append(f"item{i},")
    return "".join(parts)

def main():
    result = concatenate_fast(50000)
    print(f"Length: {len(result)}")

if __name__ == "__main__":
    main()
```

**Compare:**
```bash
codegreen measure python string_concat_slow.py -o slow.json
codegreen measure python string_concat_fast.py -o fast.json
```

The join-based version typically uses 70-85% less energy.

## Matrix operations

CPU-intensive computation:

```python
# matrix_multiply.py
def create_matrix(rows, cols, value):
    return [[value] * cols for _ in range(rows)]

def matrix_multiply(a, b):
    rows_a, cols_a = len(a), len(a[0])
    cols_b = len(b[0])
    result = [[0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result

def main():
    size = 200
    a = create_matrix(size, size, 1.5)
    b = create_matrix(size, size, 2.0)
    result = matrix_multiply(a, b)
    print(f"Result[0][0]: {result[0][0]}")

if __name__ == "__main__":
    main()
```

```bash
codegreen measure python matrix_multiply.py -g fine --export-plot matrix.html
```

## Recursive vs iterative

```python
# fibonacci.py
def fibonacci_recursive(n):
    if n <= 1:
        return n
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)

def fibonacci_iterative(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def main():
    n = 30
    print(f"Recursive: {fibonacci_recursive(n)}")
    print(f"Iterative: {fibonacci_iterative(n)}")

if __name__ == "__main__":
    main()
```

```bash
codegreen measure python fibonacci.py -g fine --export-plot fib.html
```

The recursive version consumes orders of magnitude more energy due to exponential function calls.

## Common CLI patterns

```bash
# Quick energy measurement of any command (no instrumentation)
codegreen run python script.py --repeat 10

# Energy budget enforcement (exits non-zero if exceeded)
codegreen run --budget 5.0 python script.py

# Basic measurement (coarse, 2 checkpoints)
codegreen measure python script.py

# Fine granularity (all functions)
codegreen measure python script.py -g fine

# JSON output to stdout
codegreen measure python script.py --json

# Save results to file
codegreen measure python script.py -o results.json

# Interactive HTML plot
codegreen measure python script.py -g fine --export-plot energy.html

# Static PNG plot (requires matplotlib)
codegreen measure python script.py -g fine --export-plot energy.png

# Keep instrumented code for inspection
codegreen measure python script.py --no-cleanup

# Pass arguments to the script
codegreen measure python script.py -- arg1 arg2

# Analyze without running (static analysis only)
codegreen analyze python script.py --verbose
```

## Best practices

1. **Use fine mode for profiling**: `-g fine` shows per-function energy breakdown.
2. **Use coarse mode for totals**: default mode gives total energy with minimal overhead.
3. **Consistent data**: use the same seeds for random inputs when comparing.
4. **Multiple runs**: average 3-5 runs for stable results.
5. **Avoid I/O during profiling**: file I/O adds measurement noise.
6. **Return results**: use function return values to prevent dead-code elimination.

## See also

- [Quickstart](../getting-started/quickstart.md)
- [Python API](../api/python.md)
- [CLI reference](../user-guide/cli-reference.md)
- [Reports and visualization](../user-guide/reports.md)
- [C/C++ examples](cpp.md)
- [Java examples](java.md)
