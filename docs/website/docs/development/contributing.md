# Contributing

## Getting Started

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
pip install -e ".[dev]"
pre-commit install
```

## Code Style

- **Formatting**: ruff (`ruff check --fix .`)
- **Methods**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_CASE

## Adding Language Support

CodeGreen uses a config-driven design. To add a new language:

1. Add a Tree-sitter grammar to `third_party/`
2. Create `src/instrumentation/configs/<language>.json` with function patterns
3. Add a runtime bridge in `src/instrumentation/language_runtimes/<language>/`
4. Register the language in `src/cli/cli.py` Language enum

No changes needed to the core instrumentation engine.

## Project Structure

```
src/
  cli/              # Python CLI (Typer + Rich)
  instrumentation/  # Tree-sitter engine + language configs
  measurement/      # C++ NEMB backend
  analyzer/         # Post-measurement visualization
benchmark/          # Benchmark suite
docs/website/       # MkDocs documentation
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Ensure `ruff check .` passes
4. Open a pull request with a clear description
