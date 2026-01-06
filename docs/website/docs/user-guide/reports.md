# Reports and Visualization

Understanding and visualizing energy measurement results.

## Report Formats

CodeGreen generates energy reports in multiple formats for different use cases.

### JSON Format (Machine-Readable)

Complete measurement data for programmatic analysis:

```bash
codegreen measure python app.py --output results.json --json
```

**results.json:**
```json
{
  "metadata": {
    "timestamp": "2026-01-06T03:30:15.123456",
    "command": "codegreen measure python app.py",
    "precision": "high",
    "hostname": "dev-machine",
    "codegreen_version": "0.1.0"
  },
  "system_info": {
    "cpu": "Intel Core i7-9750H",
    "cpu_cores": 6,
    "gpu": "NVIDIA GeForce GTX 1660 Ti",
    "os": "Linux 5.15.0"
  },
  "total_energy_joules": 15.432,
  "execution_time_ms": 1250.5,
  "average_power_watts": 12.34,
  "sensors": {
    "rapl": {
      "package": 12.150,
      "pp0": 10.450,
      "dram": 1.700
    },
    "nvidia_gpu_0": {
      "gpu": 3.282
    }
  },
  "functions": {
    "main": {
      "energy_joules": 15.420,
      "invocations": 1,
      "average_power_watts": 12.33,
      "execution_time_ms": 1250.0
    },
    "process_data": {
      "energy_joules": 12.150,
      "invocations": 1,
      "average_power_watts": 12.50,
      "execution_time_ms": 972.0
    },
    "parse_input": {
      "energy_joules": 0.285,
      "invocations": 5,
      "average_power_watts": 9.20,
      "execution_time_ms": 31.0
    }
  }
}
```

### Text Summary (Human-Readable)

Quick overview of energy consumption:

```bash
codegreen measure python app.py
```

**Output:**
```
🔋 Energy Measurement Results

Execution Time: 1.25 seconds
Total Energy:   15.43 Joules
Average Power:  12.34 Watts

Sensor Breakdown:
  CPU Package:  12.15 J (78.7%)
  CPU Cores:    10.45 J (67.7%)
  DRAM:         1.70 J (11.0%)
  NVIDIA GPU:   3.28 J (21.3%)

Top Energy Consumers:
  1. process_data     12.15 J  (78.7%)  972 ms
  2. parse_input       0.29 J  ( 1.8%)   31 ms  (5 calls)
  3. main             15.42 J  (99.9%) 1250 ms
```

### CSV Format (Spreadsheet-Compatible)

For external analysis tools:

```bash
codegreen measure python app.py --output results.csv --format csv
```

**results.csv:**
```csv
function_name,energy_joules,invocations,execution_time_ms,average_power_watts
main,15.420,1,1250.0,12.33
process_data,12.150,1,972.0,12.50
parse_input,0.285,5,31.0,9.20
```

## Analyzing Reports

### Python Analysis Script

```python
# analyze_energy.py
import json
import sys
from collections import defaultdict

def analyze_report(filename):
    with open(filename) as f:
        data = json.load(f)

    total_energy = data['total_energy_joules']
    functions = data['functions']

    # Sort by energy consumption
    sorted_funcs = sorted(
        functions.items(),
        key=lambda x: x[1]['energy_joules'],
        reverse=True
    )

    print(f"Total Energy: {total_energy:.3f} J\n")
    print("Energy Hotspots:")
    for i, (name, metrics) in enumerate(sorted_funcs[:5], 1):
        energy = metrics['energy_joules']
        percent = (energy / total_energy) * 100
        calls = metrics.get('invocations', 1)
        print(f"  {i}. {name:30s} {energy:8.3f} J ({percent:5.1f}%) - {calls} calls")

    # Identify high-frequency functions
    print("\nHigh-Frequency Functions:")
    high_freq = [(name, m) for name, m in functions.items()
                 if m.get('invocations', 1) > 10]
    for name, metrics in sorted(high_freq, key=lambda x: x[1]['invocations'], reverse=True)[:5]:
        calls = metrics['invocations']
        energy_per_call = metrics['energy_joules'] / calls
        print(f"  - {name:30s} {calls:6d} calls @ {energy_per_call:.6f} J/call")

if __name__ == "__main__":
    analyze_report(sys.argv[1])
```

**Usage:**
```bash
python analyze_energy.py results.json
```

### Comparing Reports

Compare before/after optimization:

```python
# compare_energy.py
import json
import sys

def compare_reports(baseline_file, optimized_file):
    with open(baseline_file) as f:
        baseline = json.load(f)
    with open(optimized_file) as f:
        optimized = json.load(f)

    baseline_energy = baseline['total_energy_joules']
    optimized_energy = optimized['total_energy_joules']

    improvement = ((baseline_energy - optimized_energy) / baseline_energy) * 100

    print(f"Baseline Energy:  {baseline_energy:.3f} J")
    print(f"Optimized Energy: {optimized_energy:.3f} J")
    print(f"Improvement:      {improvement:+.1f}%\n")

    # Function-level comparison
    baseline_funcs = baseline['functions']
    optimized_funcs = optimized['functions']

    print("Function-Level Changes:")
    for func_name in set(baseline_funcs.keys()) | set(optimized_funcs.keys()):
        base_e = baseline_funcs.get(func_name, {}).get('energy_joules', 0)
        opt_e = optimized_funcs.get(func_name, {}).get('energy_joules', 0)

        if base_e > 0:
            change = ((base_e - opt_e) / base_e) * 100
            print(f"  {func_name:30s} {base_e:8.3f} J → {opt_e:8.3f} J ({change:+6.1f}%)")

if __name__ == "__main__":
    compare_reports(sys.argv[1], sys.argv[2])
```

**Usage:**
```bash
python compare_energy.py baseline.json optimized.json
```

## Visualization

### Energy Distribution Pie Chart

```python
# visualize_energy.py
import json
import matplotlib.pyplot as plt

def plot_energy_distribution(filename):
    with open(filename) as f:
        data = json.load(f)

    functions = data['functions']

    # Get top 5 functions + "Others"
    sorted_funcs = sorted(
        functions.items(),
        key=lambda x: x[1]['energy_joules'],
        reverse=True
    )

    labels = []
    sizes = []

    for name, metrics in sorted_funcs[:5]:
        labels.append(name)
        sizes.append(metrics['energy_joules'])

    if len(sorted_funcs) > 5:
        others_energy = sum(m['energy_joules'] for _, m in sorted_funcs[5:])
        labels.append('Others')
        sizes.append(others_energy)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.set_title(f"Energy Distribution - Total: {data['total_energy_joules']:.2f} J")
    plt.savefig('energy_distribution.png', dpi=300, bbox_inches='tight')
    print("Saved: energy_distribution.png")

if __name__ == "__main__":
    import sys
    plot_energy_distribution(sys.argv[1])
```

### Time-Series Power Plot

```python
# plot_power.py
import json
import matplotlib.pyplot as plt

def plot_power_over_time(filename):
    with open(filename) as f:
        data = json.load(f)

    # Extract power timeline (if available in detailed output)
    # Simplified example using average power
    functions = data['functions']

    names = []
    powers = []
    times = []

    for name, metrics in functions.items():
        names.append(name)
        powers.append(metrics.get('average_power_watts', 0))
        times.append(metrics.get('execution_time_ms', 0) / 1000)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(names, powers, color='steelblue')
    ax.set_xlabel('Average Power (Watts)')
    ax.set_title('Function Power Consumption')
    ax.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    plt.savefig('power_consumption.png', dpi=300, bbox_inches='tight')
    print("Saved: power_consumption.png")

if __name__ == "__main__":
    import sys
    plot_power_over_time(sys.argv[1])
```

## Report Interpretation

### Understanding Metrics

**Total Energy (Joules):**
- Complete energy consumed during execution
- Sum of all sensor measurements
- Includes CPU, GPU, DRAM

**Execution Time (ms):**
- Wall-clock time from start to finish
- Includes I/O wait, sleep time

**Average Power (Watts):**
- Power = Energy / Time
- Indicates intensity of computation
- Higher power = more resource-intensive

**Per-Function Metrics:**
- Energy consumed while function executes
- Includes energy from nested function calls
- Recursive/repeated calls tracked separately

### Common Patterns

**High Energy, Short Time:**
```
process_data: 50 J in 500 ms → 100 W average
```
- Compute-intensive operation
- CPU/GPU running at high utilization
- Optimization: Reduce computational complexity

**Low Energy, Long Time:**
```
wait_for_input: 2 J in 5000 ms → 0.4 W average
```
- I/O-bound or idle operation
- CPU mostly sleeping/waiting
- Not a good optimization target

**Many Small Calls:**
```
helper_func: 0.001 J × 10,000 calls = 10 J total
```
- Frequent invocations add up
- Optimization: Reduce call frequency or inline

## CI/CD Integration

### Automated Reporting

```bash
# .github/workflows/energy-report.yml
- name: Generate Energy Report
  run: |
    codegreen measure python app.py --output energy.json --json
    python scripts/generate_html_report.py energy.json > report.html

- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: energy-report
    path: report.html
```

### Energy Regression Detection

```python
# check_regression.py
import json
import sys

def check_regression(current_file, baseline_file, threshold=10):
    with open(current_file) as f:
        current = json.load(f)
    with open(baseline_file) as f:
        baseline = json.load(f)

    current_energy = current['total_energy_joules']
    baseline_energy = baseline['total_energy_joules']

    increase = ((current_energy - baseline_energy) / baseline_energy) * 100

    if increase > threshold:
        print(f"❌ Energy regression: {increase:.1f}% increase (threshold: {threshold}%)")
        sys.exit(1)
    else:
        print(f"✅ Energy within limits: {increase:+.1f}% change")
        sys.exit(0)

if __name__ == "__main__":
    check_regression(sys.argv[1], sys.argv[2], float(sys.argv[3]))
```

## Best Practices

1. **Save All Measurements**: Keep historical data for trend analysis
2. **Use JSON Format**: Machine-readable for automated analysis
3. **Compare Baselines**: Always measure before/after changes
4. **Track Over Time**: Monitor energy trends across commits
5. **Visualize Results**: Charts reveal patterns not obvious in tables
6. **Focus on Hotspots**: Top 20% of functions often account for 80% of energy

## See Also

- [Energy Measurement](energy-measurement.md) - Measurement guide
- [CLI Reference](cli-reference.md) - Output format options
- [CI/CD Integration](cicd-integration.md) - Automated reporting
- [Examples](../examples/python.md) - Practical examples
