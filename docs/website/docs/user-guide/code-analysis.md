# Code Analysis

Static code analysis and instrumentation inspection with CodeGreen.

## Overview

CodeGreen's `analyze` command performs static analysis of your code using Tree-sitter AST parsing to identify instrumentation points, estimate measurement overhead, and suggest optimizations.

## Basic Analysis

Analyze a Python script:

```bash
codegreen analyze python myapp.py
```

**Output:**
```
📊 Code Analysis Report

File: myapp.py
Language: Python
Functions detected: 12
Classes detected: 2
Total lines: 245

Instrumentation Points:
  - Functions: 12
  - Methods: 8
  - Loops: 0 (loop instrumentation disabled)

Estimated Overhead:
  - Checkpoint calls: 40 (20 entry + 20 exit)
  - Per-checkpoint: ~150 ns
  - Total overhead: ~6 μs per execution

Complexity Analysis:
  - process_data: High complexity (nested loops)
  - calculate_metrics: Medium complexity
  - parse_input: Low complexity
```

## Detailed Analysis

Show all instrumentation points:

```bash
codegreen analyze python myapp.py --verbose
```

**Output includes:**
```
Instrumentation Points:

Function: process_data (line 45)
  Entry checkpoint: line 46
  Exit checkpoints: lines 58, 62
  Estimated invocations: Unknown
  Complexity: High (3 nested loops)

Function: calculate_metrics (line 65)
  Entry checkpoint: line 66
  Exit checkpoints: line 78
  Estimated invocations: Unknown
  Complexity: Medium (1 loop)
```

## Save Instrumented Code

Generate and save instrumented version for inspection:

```bash
codegreen analyze python myapp.py --save-instrumented --output-dir ./instrumented
```

Creates `./instrumented/myapp_instrumented.py` with visible checkpoint calls:

```python
import codegreen_runtime

def process_data(data):
    codegreen_runtime.checkpoint("process_data#entry")
    try:
        result = []
        for item in data:
            result.append(item * 2)
        codegreen_runtime.checkpoint("process_data#exit")
        return result
    finally:
        pass
```

## Optimization Suggestions

Get energy optimization recommendations:

```bash
codegreen analyze python myapp.py --suggestions
```

**Output:**
```
💡 Optimization Suggestions:

1. Function 'process_large_file' (line 120):
   - Large data processing detected
   - Suggestion: Consider chunked processing to reduce peak memory
   - Potential energy savings: 15-30%

2. Function 'convert_format' (line 85):
   - String concatenation in loop detected
   - Suggestion: Use list + join() instead of += for strings
   - Potential energy savings: 40-70%

3. Function 'recursive_search' (line 200):
   - Deep recursion detected (max depth unknown)
   - Suggestion: Consider iterative approach with explicit stack
   - Potential energy savings: 20-40%
```

## Analysis Output Formats

### JSON Output

Machine-readable analysis:

```bash
codegreen analyze python myapp.py --output analysis.json --verbose
```

**analysis.json:**
```json
{
  "file": "myapp.py",
  "language": "python",
  "statistics": {
    "total_lines": 245,
    "functions": 12,
    "classes": 2,
    "complexity_score": 28.5
  },
  "instrumentation_points": [
    {
      "type": "function",
      "name": "process_data",
      "line": 45,
      "entry_line": 46,
      "exit_lines": [58, 62],
      "complexity": "high",
      "estimated_overhead_ns": 300
    }
  ],
  "suggestions": [
    {
      "function": "convert_format",
      "line": 85,
      "issue": "String concatenation in loop",
      "recommendation": "Use list + join()",
      "potential_savings_percent": "40-70"
    }
  ]
}
```

## Language-Specific Analysis

### Python

```bash
codegreen analyze python app.py --verbose
```

**Detects:**
- Function definitions
- Class methods
- Async functions
- Generators
- List comprehensions (if enabled)
- Lambda functions (if enabled)

### C/C++

```bash
codegreen analyze cpp program.cpp --verbose
```

**Detects:**
- Function definitions
- Class methods
- Template functions
- Inline functions
- Constructors/destructors

### Java

```bash
codegreen analyze java App.java --verbose
```

**Detects:**
- Method definitions
- Static methods
- Constructors
- Lambda expressions (if enabled)
- Anonymous classes

## Instrumentation Strategies

Configure checkpoint placement:

### Functions Only (Default)

```bash
codegreen analyze python app.py
# Instruments function boundaries only
```

### Include Loops

```bash
codegreen analyze python app.py --instrument-loops
# Also instruments loop blocks
```

### Minimal (Entry Points Only)

```bash
codegreen analyze python app.py --minimal
# Only instruments main/entry functions
```

## Complexity Metrics

CodeGreen computes complexity scores based on:

| Metric | Weight | Description |
|--------|--------|-------------|
| Lines of code | 1x | Total function lines |
| Nested loops | 3x | Each level of nesting |
| Conditional branches | 2x | if/else/switch statements |
| Function calls | 1x | External function invocations |
| Recursion | 5x | Recursive calls detected |

**Complexity categories:**
- **Low** (0-10): Simple functions, minimal branching
- **Medium** (11-25): Moderate logic, some loops/conditions
- **High** (26-50): Complex logic, nested structures
- **Very High** (>50): Highly complex, refactoring recommended

## Integration with Measurement

Analysis helps optimize measurement workflow:

```bash
# 1. Analyze code first
codegreen analyze python app.py --suggestions > analysis.txt

# 2. Review suggestions

# 3. Measure baseline
codegreen measure python app.py --output baseline.json

# 4. Apply optimizations

# 5. Measure optimized version
codegreen measure python app_optimized.py --output optimized.json

# 6. Compare results
python compare_energy.py baseline.json optimized.json
```

## Best Practices

1. **Analyze Before Measuring**: Understand overhead and complexity first
2. **Review Instrumented Code**: Use `--save-instrumented` to inspect checkpoint placement
3. **Check Suggestions**: Review optimization recommendations before implementing
4. **Validate Complexity**: High-complexity functions may benefit from refactoring
5. **Language-Specific**: Be aware of language-specific patterns (GIL in Python, JIT in Java)

## See Also

- [CLI Reference](cli-reference.md) - Complete analyze command options
- [Energy Measurement](energy-measurement.md) - Measuring energy consumption
- [Examples](../examples/python.md) - Practical examples
