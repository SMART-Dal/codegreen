# Codegreen

Codegreen is a Python package and CLI tool for energy profiling of Python code. It allows measuring the energy consumption of Deep learning framework APIs like TensorFlow.

## Prerequisites

Codegreen requires the following hardware:

- Intel processor
- NVIDIA GPU 

The Intel processor is needed for accessing the RAPL power sensors. An NVIDIA GPU is required for profiling GPU usage via `nvidia-smi`.

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
Run `codegreen --help` to see the CLI options:

```
Usage: codegreen [OPTIONS] COMMAND [ARGS]...                              
                                                                          
🍃 CodeGreen: Your Passport to a Greener Code! 🍃                         
                                                                          
╭─ Options ──────────────────────────────────────────────────────────────╮
│ --install-completion        [bash|zsh|fish|power    Install completion   │
│                              shell|pwsh]            for the specified    │  
│                                                      shell.             │
│ --show-completion           [bash|zsh|fish|power    Show completion for  │
│                              shell|pwsh]            the specified shell, │
│                                                      to copy it or       │
│                                                      customize the       │
│                                                      installation.       │
│ --help                                              Show this message and│
│                                                      exit.               │  
╰────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────╮
│ project-patcher            Patch scripts for measurement │
│ run-energy-profiler        Start measurement server │   
│ start-energy-measurement   Run patched scripts and collect data │
╰────────────────────────────────────────────────────────────────────────╯
```

Basic usage:

```bash
codegreen project-patcher --project myscripts/
```

Patch all Python scripts in `myscripts/` for instrumentation. Patched projects are saved with a `_patched` suffix.

```bash  
codegreen run-energy-profiler
```

This will start the energy measurement server.

```bash
codegreen start-energy-measurement --project repo_dir --scripts script_to_run --iterations "5"
``` 

This will run the patched scripts for project `repo_dir`, scripts `script_to_run` and number of run iterations `n` and collect power usage data. Save the energy profiles and execution logs under `experiments/`.

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
  - `utils/`: utility functions
<!-- - `dist/`: Built distributions
- `tests/`: Unit tests
- `examples/`: Usage examples -->

<!-- 
## Contributing

Contributions to codegreen are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

Please file bug reports and feature requests on the GitHub issues page.
-->

## License

codegreen is licensed under the Apache 2.0. See [LICENSE](https://www.apache.org/licenses/LICENSE-2.0) for more details.
