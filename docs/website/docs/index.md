# CodeGreen

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **Fast Energy Monitoring**

    ---

    Real-time monitoring of CPU, GPU, and system energy consumption with minimal overhead.

    [:octicons-arrow-right-24: Getting Started](getting-started/quickstart.md)

-   :material-code-tags:{ .lg .middle } **Multi-Language Support**

    ---

    Support for Python, C, C++, Java, and more with language-specific optimizations.

    [:octicons-arrow-right-24: Examples](examples/python.md)

-   :material-chart-line:{ .lg .middle } **Advanced Analytics**

    ---

    Detailed energy reports, visualizations, and optimization suggestions.

    [:octicons-arrow-right-24: CLI Reference](user-guide/cli-reference.md)

-   :material-cog:{ .lg .middle } **Easy Integration**

    ---

    CLI tools, Python API, and IDE plugins for seamless development workflow.

    [:octicons-arrow-right-24: Installation](getting-started/installation.md)

</div>

## Demo

<video width="100%" controls autoplay loop muted>
  <source src="assets/demo.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>
*Watch CodeGreen in action: measuring energy consumption of a Python script.*

## What is CodeGreen?

CodeGreen is a comprehensive energy monitoring and optimization tool designed to help developers understand and reduce the energy consumption of their software. By providing real-time energy measurements, detailed analytics, and optimization suggestions, CodeGreen enables energy-aware software development.

### Architecture

CodeGreen uses the **Native Energy Measurement Backend (NEMB)**, a high-performance C++ measurement engine that:

- **Signal-Generator Model**: Lightweight timestamp markers (~100-200ns overhead) instead of synchronous hardware reads (~5-20μs)
- **Background Polling**: Independent C++ thread samples hardware sensors at configurable intervals (1-100ms)
- **Time-Series Correlation**: Binary search + linear interpolation matches checkpoints to energy readings
- **Thread-Safe Invocation Tracking**: Handles recursive functions and multi-threaded code with zero-lock performance

This achieves **25-100x lower overhead** than traditional profiling while maintaining **±2% accuracy**.

### Key Features

- **🔋 Energy Monitoring**: Real-time monitoring of CPU, GPU, and system energy consumption
- **📊 Code Analysis**: Language-agnostic code analysis for energy optimization opportunities  
- **🛠️ IDE Integration**: Support for VSCode, IntelliJ, and other popular IDEs
- **🔌 Hardware Plugins**: Extensible plugin system for different hardware platforms
- **📈 Visualization**: Charts and reports for energy consumption analysis
- **⚡ Code Instrumentation**: Automatic code instrumentation for energy profiling

## Quick Start

Get started with CodeGreen in just a few steps:

=== "Installation"

    ```bash
    git clone https://github.com/SMART-Dal/codegreen.git
    cd codegreen
    ./install.sh
    ```

=== "Initialize"

    ```bash
    sudo codegreen init-sensors
    ```

=== "Measure"

    ```bash
    codegreen measure python my_script.py
    ```

=== "Analyze"

    ```bash
    codegreen info
    ```

## Supported Platforms

<div class="grid cards" markdown>

-   :material-linux:{ .lg .middle } **Linux**

    ---

    Full support for Intel RAPL, NVIDIA NVML, and AMD hardware monitoring.

-   :material-apple:{ .lg .middle } **macOS**

    ---

    Support for Intel and Apple Silicon energy monitoring.

-   :material-microsoft-windows:{ .lg .middle } **Windows**

    ---

    Windows-specific energy monitoring and optimization tools.

</div>

## Community

Join our community to get help, share ideas, and contribute to CodeGreen:

- [:material-github: GitHub](https://github.com/SMART-Dal/codegreen) - Source code and issues
- [:material-chat: Discussions](https://github.com/SMART-Dal/codegreen/discussions) - Community discussions

## License

CodeGreen is released under the MIT License. See the [License](about/license.md) page for details.