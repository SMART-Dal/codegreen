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

    Hardware-level energy monitoring via RAPL (Linux), IOReport (macOS), EMI (Windows), NVML, and ROCm with sub-millisecond resolution.

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

    CLI tool with JSON/CSV/Markdown output, CI/CD energy gating via `--budget`, and granularity control.

    [:octicons-arrow-right-24: Installation](getting-started/installation.md)

</div>

## Setup & Installation

<video width="100%" controls autoplay loop muted>
  <source src="assets/demo.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>
*Quick start guide: installing and configuring CodeGreen.*

## What is CodeGreen?

CodeGreen is an energy measurement tool that helps developers understand the energy consumption of their software at the function level. It uses Tree-sitter AST parsing for automatic code instrumentation and a C++ backend (NEMB) for hardware-level energy readings with minimal overhead.

### Key Features

- **Energy Measurement**: Per-function energy attribution via RAPL (Linux), IOReport + kpc (macOS), EMI (Windows), NVML, ROCm
- **Quick Measurement**: `codegreen run` measures energy of any shell command with hardware-level precision
- **Continuous Monitoring**: `codegreen monitor` samples already-running services; per-PID via cgroup_v2; per-request via UDS annotations
- **Project Profiling**: `codegreen project` plugs into your build (Maven, Gradle, Make, plain python) for per-function attribution across multi-file projects
- **Code Analysis**: Tree-sitter based static analysis across Python, C, C++, Java
- **Visualization**: Interactive energy timeline with `--export-plot` (Plotly HTML with zoom/pan)
- **Granularity Control**: Coarse mode (main only) or fine mode (all functions)
- **CI/CD Energy Gating**: `--budget` flag to enforce energy budgets in pipelines
- **Benchmarking**: Built-in benchmark suite -- 0.03% error vs perf RAPL on representative workloads

## Quick Start

Get started with CodeGreen in just a few steps:

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
    codegreen measure python my_script.py
    ```

=== "Quick Run"

    ```bash
    codegreen run python my_script.py --repeat 10
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

## Find what you need in two clicks

| I want to ... | Start here | Then |
|---|---|---|
| Measure a one-off Python or shell script | [Quickstart](getting-started/quickstart.md) | [01 Quickstart measure](examples/01_quickstart_measure.md) |
| Get a stable mean across N runs | [Examples](examples/index.md) | [02 Run with repeats](examples/02_run_repeat.md) |
| Bracket regions inside a long script | [Python API](api/python.md) | [03 Session API](examples/03_session_api.md) |
| Find per-method hotspots in a Java/Python/C++ project | [Project Profiling](user-guide/project-profiling.md) | [04 Java](examples/04_project_hotspots_java.md) / [09 Python](examples/09_project_hotspots_python.md) |
| Watch a running daemon or webapp | [Continuous Monitoring](user-guide/continuous-monitoring.md) | [06 host](examples/06_monitor_host.md) / [07 PID](examples/07_monitor_pid.md) / [08 annotations](examples/08_monitor_socket.md) |
| Integrate into CI | [CI/CD integration](user-guide/cicd-integration.md) | `codegreen run --budget 10.0 ...` |
| Cross-validate against `perf` | [Energy Measurement](user-guide/energy-measurement.md) | [10 CodeGreen vs perf](examples/10_codegreen_vs_perf.md) |
| Add a language or contribute | [Architecture](development/architecture.md) | [Contributing](development/contributing.md) |

## What's new in 0.4.9

- `codegreen monitor` / `codegreen.Monitor` -- continuous sampler with cgroup_v2 per-PID attribution. See [Continuous Monitoring](user-guide/continuous-monitoring.md).
- `codegreen.annotate_request` over a UDS socket -- per-request energy in Flask/gunicorn webapps. See [08 Monitor socket](examples/08_monitor_socket.md).
- `codegreen run --stdin <file>` -- pipe a fixed payload into the subprocess across all repeats. See [CLI: run](user-guide/cli-reference.md#run).
- 10 worked end-to-end examples under [`examples/`](examples/index.md), each verified by `pytest tests/test_examples.py`.
- Earlier 0.4.7 / 0.4.8 changes (schema overhaul, local-timezone display fields) are in the [Changelog](about/changelog.md).

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

Pre-built wheels for Linux x86_64 and macOS ARM64. Windows and other platforms: install from source.

## Citing CodeGreen

If you use CodeGreen in your research, please cite:

> Rajput, S., & Sharma, T. (2026). CodeGreen: Towards Improving Precision and Portability in Software Energy Measurement. *arXiv preprint arXiv:2603.17924*.

[:octicons-arrow-right-24: Full citation & BibTeX](about/citing.md)

## Community

- [:material-github: GitHub](https://github.com/SMART-Dal/codegreen) - Source code and issues
- [:material-chat: Discussions](https://github.com/SMART-Dal/codegreen/discussions) - Community discussions

## License

CodeGreen is released under the MPL 2.0 License. See the [License](about/LICENSE) page for details.
