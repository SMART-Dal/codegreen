# CodeGreen

[![PyPI](https://img.shields.io/pypi/v/codegreen)](https://pypi.org/project/codegreen/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/codegreen?period=total&units=NONE&left_color=GREY&right_color=GREEN&left_text=downloads)](about/stats.md)
[![GitHub stars](https://img.shields.io/github/stars/SMART-Dal/codegreen)](https://github.com/SMART-Dal/codegreen/stargazers)
[![License](https://img.shields.io/badge/license-MPL%202.0-blue)](https://github.com/SMART-Dal/codegreen/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20windows-lightgrey)](https://pypi.org/project/codegreen/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18371771.svg)](https://doi.org/10.5281/zenodo.18371771)

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **Precise Energy Measurement**

    ---

    Hardware energy counters via RAPL (Linux), IOReport (macOS), EMI (Windows), NVML and ROCm, with a validity verdict on every result.

    [:octicons-arrow-right-24: Getting Started](getting-started/quickstart.md)

-   :material-code-tags:{ .lg .middle } **Multi-Language Support**

    ---

    Python, C, C++, and Java instrumentation via Tree-sitter with config-driven extensibility.

    [:octicons-arrow-right-24: Examples](examples/index.md)

-   :material-radar:{ .lg .middle } **Continuous Monitoring**

    ---

    `codegreen monitor` samples an already-running service, with cgroup_v2 per-PID attribution and a UDS annotation channel for per-request energy.

    [:octicons-arrow-right-24: Continuous Monitoring](user-guide/continuous-monitoring.md)

-   :material-chart-line:{ .lg .middle } **Interactive Visualization**

    ---

    Energy timeline plots with per-function breakdown, hotspot detection, and zoom/pan via Plotly.

    [:octicons-arrow-right-24: Reports & Visualization](user-guide/reports.md)

-   :material-cog:{ .lg .middle } **Easy Integration**

    ---

    JSON output for every command, CI energy gating with `--budget`, and exit code 3 for invalid measurements.

    [:octicons-arrow-right-24: Installation](getting-started/installation.md)

</div>

## What is CodeGreen?

CodeGreen measures the energy consumption of software from hardware energy counters, down to individual functions. It instruments source code with Tree-sitter and reads the counters through a native C++ backend (NEMB, the Native Energy Measurement Backend).

### Key Features

- **Per-function energy**: `codegreen measure` instruments a file; `codegreen project` instruments a multi-file project and runs your own build and run commands (Maven, Gradle, Make, plain Python).
- **Whole-command energy**: `codegreen run` measures any command over repeated runs, with confidence intervals and `--budget` gating.
- **In-process API**: `codegreen.Session` brackets regions of a Python program.
- **Continuous monitoring**: `codegreen monitor` samples running services, with per-PID attribution (cgroup v2) and per-request annotations over a Unix socket.
- **Validity**: every result carries a verdict with reason codes; `measure`, `run` and `project` exit 3 on an invalid measurement.
- **Visualization**: `--export-plot` writes an interactive Plotly timeline or a static image.

## Quick Start

=== "Install (pip)"

    ```bash
    pip install codegreen
    ```

=== "Install (source)"

    ```bash
    git clone https://github.com/SMART-Dal/codegreen.git
    cd codegreen
    ./install.sh
    ```

=== "Initialize (Linux)"

    ```bash
    sudo codegreen init-sensors
    ```

=== "Measure"

    ```bash
    codegreen measure python my_script.py --sensors rapl
    ```

=== "Quick Run"

    ```bash
    codegreen run --repeat 10 --sensors rapl -- python3 my_script.py
    ```

=== "Visualize"

    ```bash
    codegreen measure python my_script.py -g fine --export-plot energy.html
    ```

=== "Monitor"

    ```bash
    codegreen monitor --pid $(pgrep -f gunicorn | head -1) -d 60 -o energy.jsonl
    ```

=== "Project"

    ```bash
    codegreen project python ./src -r "python main.py" -g fine
    ```

## Where to start

| I want to ... | Start here | Then |
|---|---|---|
| Measure a one-off Python or shell script | [Quickstart](getting-started/quickstart.md) | [01 Quickstart measure](examples/01_quickstart_measure.md) |
| Get a stable mean across N runs | [Examples](examples/index.md) | [02 Run with repeats](examples/02_run_repeat.md) |
| Bracket regions inside a long script | [Python API](api/python.md) | [03 Session API](examples/03_session_api.md) |
| Find per-method hotspots in a Java/Python/C++ project | [Project Profiling](user-guide/project-profiling.md) | [04 Java](examples/04_project_hotspots_java.md) / [09 Python](examples/09_project_hotspots_python.md) |
| Watch a running daemon or webapp | [Continuous Monitoring](user-guide/continuous-monitoring.md) | [06 host](examples/06_monitor_host.md) / [07 PID](examples/07_monitor_pid.md) / [08 annotations](examples/08_monitor_socket.md) |
| Gate energy in CI | [CI/CD integration](user-guide/cicd-integration.md) | `codegreen run --budget 10.0 ...` |
| Cross-validate against `perf` | [Energy Measurement](user-guide/energy-measurement.md) | [10 CodeGreen vs perf](examples/10_codegreen_vs_perf.md) |
| Add a language or contribute | [Architecture](development/architecture.md) | [Contributing](development/contributing.md) |

## What's new in 0.5.0

- Every `measure`, `run` and `project` result carries a `validity` verdict with reason codes, and the command exits 3 on an invalid measurement. See [Exit codes and measurement validity](user-guide/cli-reference.md#exit-codes-and-measurement-validity).
- `--sensors` (and `measurement.default_sensors`) selects the providers that are summed; a total that mixes GPU and CPU energy is flagged `GPU_IN_TOTAL`.
- Per-function energy replays every call: `inclusive_j`, `exclusive_j` and a per-function `quality` verdict. `project` percentages are shares of the attributed (exclusive) energy.
- NEMB result block ABI 4: per-marker reading index, clamp flag, per-provider energy and sampler statistics.

Earlier releases are described in the [Changelog](about/changelog.md).

## Supported Platforms

<div class="grid cards" markdown>

-   :material-linux:{ .lg .middle } **Linux**

    ---

    Intel RAPL, NVIDIA NVML, and AMD ROCm/RAPL energy monitoring.

-   :material-apple:{ .lg .middle } **macOS**

    ---

    Apple Silicon energy via IOReport (CPU/GPU/ANE/DRAM) + kpc hardware perf counters. Pre-built ARM64 wheels on PyPI.

-   :material-microsoft-windows:{ .lg .middle } **Windows 11**

    ---

    RAPL energy via EMI (inbox intelpep.sys driver). PKG, cores, iGPU, DRAM domains. Zero driver install.

</div>

PyPI wheels: Linux x86_64 (CPython 3.9-3.13), Linux aarch64, macOS arm64 and Windows x86_64 (CPython 3.10-3.13). Other platforms install from source.

## Citing CodeGreen

If you use CodeGreen in your research, please cite:

> Rajput, S., & Sharma, T. (2026). CodeGreen: Towards Improving Precision and Portability in Software Energy Measurement. *arXiv preprint arXiv:2603.17924*.

[:octicons-arrow-right-24: Full citation & BibTeX](about/citing.md)

## Community

- [:material-github: GitHub](https://github.com/SMART-Dal/codegreen) - Source code and issues
- [:material-chat: Discussions](https://github.com/SMART-Dal/codegreen/discussions) - Community discussions

## License

CodeGreen is released under the MPL 2.0 License. See the [License](about/LICENSE) page for details.
