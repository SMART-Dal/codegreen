# Code Analysis

CodeGreen uses Tree-sitter for language-agnostic AST parsing to identify instrumentation points.

## Static Analysis

The `analyze` command parses source code without executing it:

```bash
codegreen analyze python script.py --verbose
```

This identifies:

- Function definitions and their boundaries (enter/exit points)
- Instrumentation points for energy measurement checkpoints
- Code structure metadata (function count, nesting depth)
- Optimization suggestions

## How It Works

### Tree-sitter Integration

CodeGreen uses Tree-sitter grammars for each supported language to parse source code into an AST. Language-specific query patterns (defined in JSON config files) identify function boundaries.

### Language Configs

Each language has a JSON configuration in `src/instrumentation/configs/`:

| Language | Config | Functions detected |
|----------|--------|-------------------|
| Python | `python.json` | `def` functions, methods |
| C | `c.json` | Function definitions |
| C++ | `cpp.json` | Functions, methods (no class bodies) |
| Java | `java.json` | Methods |

The config-driven approach makes adding new languages straightforward -- add a grammar and a JSON config without changing core code.

### Instrumentation Points

For each detected function, CodeGreen generates two checkpoint types:

- **function_enter**: Inserted at the start of the function body
- **function_exit**: Inserted before return statements and at end of function

## Granularity Control

### Coarse Mode (default)

Only instruments the main entry point:

```bash
codegreen analyze python script.py
# Shows: 2 instrumentation points (main enter + exit)
```

### Fine Mode

Instruments all functions detected by the language config:

```bash
codegreen measure python script.py -g fine
# Shows: N instrumentation points (enter + exit for each function)
```

## Output

### Console

```bash
codegreen analyze python script.py --verbose
```

Shows detected functions, instrumentation points, and suggestions.

### JSON

```bash
codegreen analyze python script.py --json
```

### Save Instrumented Code

```bash
codegreen analyze python script.py --save-instrumented --output-dir ./out
```

Writes the instrumented source code to the specified directory for inspection.
