# Python API

CodeGreen provides a comprehensive Python API for energy monitoring and analysis.

## Core Modules

### `codegreen.core.engine`

Main measurement engine for energy monitoring.

```python
from codegreen.core import engine

# Create engine instance
engine = engine.MeasurementEngine()

# Measure a function
@engine.measure
def my_function():
    # Your code here
    pass

# Get measurement results
result = engine.get_last_measurement()
```

### `codegreen.core.config`

Configuration management.

```python
from codegreen.core import config

# Load configuration
config = config.load_config()

# Update settings
config.set_precision("high")
config.set_timeout(60)
```

### `codegreen.utils`

Utility functions for platform detection and binary management.

```python
from codegreen.utils import platform, binary

# Check platform
if platform.is_linux():
    print("Running on Linux")

# Find CodeGreen binary
binary_path = binary.find_codegreen_binary()
```

## Example Usage

```python
import codegreen
from codegreen.core import engine, config

# Initialize
config.load_config()
engine = engine.MeasurementEngine()

# Measure energy consumption
@engine.measure
def compute_fibonacci(n):
    if n <= 1:
        return n
    return compute_fibonacci(n-1) + compute_fibonacci(n-2)

# Run measurement
result = compute_fibonacci(30)

# Get energy data
print(f"Energy consumed: {engine.get_last_measurement().total_joules} J")
print(f"Average power: {engine.get_last_measurement().average_watts} W")
```
