# CodeGreen

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **Precise Energy Measurement**

    ---

    Hardware-level energy monitoring via RAPL (Linux), IOReport (macOS), EMI (Windows), NVML, and ROCm with sub-millisecond resolution.

    [:octicons-arrow-right-24: Getting Started](getting-started/quickstart.md)

-   :material-code-tags:{ .lg .middle } **Multi-Language Support**

    ---

    Python, C, C++, and Java instrumentation via Tree-sitter with config-driven extensibility.

    [:octicons-arrow-right-24: Examples](examples/python.md)

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
