# Contributing

## Setup

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
./install.sh --skip-rapl          # builds NEMB and installs the package in editable mode
pip install -e ".[dev,all]"
```

See [Building from Source](building.md) for the manual build and the tests.

## Conventions

- Python: snake_case functions and variables, PascalCase classes,
  UPPER_CASE constants.
- Configuration over constants: thresholds and paths belong in
  `codegreen/config.json` or the language configs, not in code.
- Measurement failures are reported, never hidden: a failed or doubtful
  reading becomes a `validity` reason or warning, not a silent 0.

## Adding a language

Instrumentation is driven by per-language configs, so the engine does not
change:

1. Add the Tree-sitter grammar (the `tree-sitter-language-pack` dependency
   covers most languages; otherwise a submodule under `third_party/`).
2. Write `codegreen/instrumentation/configs/<language>.json`, starting from
   `TEMPLATE.json`; `SCHEMA.md` in the same directory documents the format.
3. Add a runtime bridge under
   `codegreen/instrumentation/language_runtimes/<language>/` that calls
   `nemb_mark_checkpoint` (see [Core API](../api/core.md#language-runtimes)).
4. Add the language to the `Language` enum in `codegreen/cli/cli.py` and, for
   `measure`, its run command in `_run_energy_measurement`.

## Pull requests

1. Fork the repository and create a feature branch.
2. Run the tests (`pytest tests --ignore=tests/test_examples.py`).
3. Open a pull request that explains the change and how it was verified.
