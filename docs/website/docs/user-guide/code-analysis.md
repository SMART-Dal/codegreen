# Code Analysis

`codegreen analyze` shows where CodeGreen would place checkpoints, without
running the code. Use it to check what `measure -g fine` and `project`
will instrument, or to inspect the instrumented source.

```console
$ codegreen analyze python sums.py --verbose
...
Instrumentation points: 6
Analysis time: 2.06ms
Source lines: 14

Instrumentation Points:
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Type           ┃ Subtype ┃ Name       ┃ Line ┃ Context                          ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ function_enter │ enter   │ square_sum │ 2    │ Enter function_enter: square_sum │
│ function_exit  │ frame   │ square_sum │ 2    │ Function frame exit: square_sum  │
│ function_enter │ enter   │ main       │ 8    │ Enter function_enter: main       │
│ function_exit  │ frame   │ main       │ 10   │ Function frame exit: main        │
│ function_enter │ enter   │ cube_sum   │ 5    │ Enter function_enter: cube_sum   │
│ function_exit  │ frame   │ cube_sum   │ 5    │ Function frame exit: cube_sum    │
└────────────────┴─────────┴────────────┴──────┴──────────────────────────────────┘
```

`analyze` always lists every point the language config finds; `measure`
keeps only the entry function's pair at the default coarse granularity.

## How it works

Each language has a JSON config in `codegreen/instrumentation/configs/`
(`python.json`, `c.json`, `cpp.json`, `java.json`; `SCHEMA.md` documents the
format). It names the Tree-sitter node types and queries that identify
functions, the checkpoint call to insert, and the insertion rules. Adding a
language means adding a grammar and a config, not changing the engine.
`javascript` is accepted by `analyze`, but instrumented measurement has no
JavaScript runtime yet.

For each function CodeGreen inserts one entry checkpoint and closes the frame
on every exit path: a `try`/`finally` in Python and Java, an RAII guard in
C++, and a rewrite of every `return` in C. The work inside `return <expr>` is
therefore attributed to the function. For `sums.py`, the saved instrumented
code of `square_sum` is:

```python
def square_sum(n):
    _codegreen_rt.checkpoint('function_enter_square_sum_2_1', 'square_sum', 'enter')
    try:
        return sum(i * i for i in range(n))
    finally:
        _codegreen_rt.checkpoint('function_exit_square_sum_frame_2', 'square_sum', 'exit')
```

## Output

| Option | Effect |
|---|---|
| `--verbose` | Table of every instrumentation point |
| `--json` | `timestamp`, `script`, `language`, `success`, `analysis_metadata` (`method`, `parser_available`, `time_ms`, `source_lines`), `instrumentation_points_count`, `instrumentation_points` (`id`, `type`, `subtype`, `name`, `line`, `column`, `context`, `metadata`) and `optimization_suggestions` |
| `-o FILE` | Write the JSON to a file |
| `--save-instrumented` | Write `<name>_instrumented.<ext>` (every function instrumented) to the current directory, or to `--output-dir` |

`optimization_suggestions` are simple pattern checks from the language
config (wildcard imports, nested loops, raw `new` in C++); they are often
empty and are not based on measured energy.

```bash
codegreen analyze python sums.py --save-instrumented --output-dir ./instrumented
codegreen analyze cpp main.cpp --json
```
