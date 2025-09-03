# Quick Start

Get up and running with CodeGreen in minutes!

## 1. Installation

```bash
pip install codegreen
```

## 2. Initialize

Set up sensor configuration:

```bash
codegreen init
```

## 3. Basic Usage

### Measure Energy Consumption

```bash
# Measure a Python script
codegreen measure python my_script.py

# Measure with specific options
codegreen measure --precision high --timeout 30 python my_script.py
```

### Get System Information

```bash
codegreen info
```

### Diagnose Issues

```bash
codegreen doctor
```

## 4. Python API

```python
import codegreen
from codegreen.core import engine, config

# Create measurement engine
engine = engine.MeasurementEngine()

# Measure a function
@engine.measure
def my_function():
    # Your code here
    pass

# Get results
result = engine.get_last_measurement()
print(f"Energy consumed: {result.total_joules} J")
```

## Next Steps

- [Configuration](configuration.md) - Customize CodeGreen settings
- [CLI Reference](user-guide/cli-reference.md) - Complete command reference
- [Examples](examples/python.md) - Real-world usage examples
