# Codegreen

Codegreen is a Python package and CLI tool for energy profiling of Python code. It allows measuring the energy consumption of code regions like functions.

## Installation

```
pip install codegreen
```

Or install from source:

```
git clone https://github.com/user/codegreen
cd codegreen
pip install .
```

## Usage

### As a CLI

```
codegreen --help
```

This will display the CLI usage and options.

Basic example:

```
codegreen profile myscript.py
```

This will instrument myscript.py, run it, and output energy measurements.

### As a Python package

```python
import codegreen

codegreen.profile(my_function)
```

See the API documentation for more details.

## Code Structure

- `codegreen/`: Source code
  - `main.py`: Main CLI entry point
  - `fecom/`: Core measurement functionality
    - `patching/`: Code instrumentation
    - `measurement/`: Measurement and output
    - `experiment/`: Experimental configurations
- `dist/`: Built distributions
- `tests/`: Unit tests
- `examples/`: Usage examples
  
## Contributing

Contributions to codegreen are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

Please file bug reports and feature requests on the GitHub issues page.

## License

codegreen is licensed under the MIT license. See [LICENSE](LICENSE) for more details.

Let me know if you would like me to explain or expand any part of this README draft further.
