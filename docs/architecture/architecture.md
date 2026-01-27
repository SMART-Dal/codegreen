# CodeGreen Architecture Overview

This document provides an overview of the CodeGreen tool's architecture. CodeGreen is designed as a modular, language-agnostic energy measurement system that supports multiple hardware platforms and scenarios. Its design follows best practices to ensure extensibility, maintainability, and reusability.

## 1. High-Level Architecture Overview

#### A. Core Layers

1. **Measurement Engine (NEMB - Native Energy Measurement Backend)**
   - **Purpose:**
     High-performance C++ measurement backend using signal-generator architecture for ultra-low overhead (<0.1% CPU utilization) with industry-grade accuracy (<2% error).
   - **Responsibilities:**
     - Checkpoint management with thread-local invocation tracking
     - Background polling of hardware sensors at configurable intervals (1-100ms)
     - Time-series energy data buffering with atomic circular buffer
     - Correlation of checkpoints to energy readings via binary search + linear interpolation
     - Multi-provider coordination (Intel RAPL, NVIDIA NVML, AMD ROCm)
   - **Key Patterns:**
     - **Signal-Generator Model:** Lightweight timestamp markers instead of synchronous reads
     - **Producer-Consumer:** Background thread polls hardware, application thread generates checkpoints
     - **Time-Series Correlation:** Post-execution energy attribution via interpolation
   - **Key Components:**
     - `MeasurementCoordinator`: Orchestrates multiple energy providers, background polling loop
     - `EnergyMeter`: Public API for checkpoint marking and correlation
     - `EnergyProvider`: Abstract interface for hardware sensors (RAPL, NVML, ROCm)
     - `PrecisionTimer`: High-resolution timestamping (TSC, CLOCK_MONOTONIC)
   - **Implementation:**
     - `src/measurement/include/nemb/` - Public API headers
     - `src/measurement/src/nemb/` - Core implementation
     - `src/measurement/src/nemb/drivers/` - Hardware-specific providers

2. **Instrumentation and Parsing Engine**
   - **Purpose:**  
     Uses language-specific parsers to analyze source code, detect method/function boundaries, and inject instrumentation hooks.
   - **Responsibilities:**  
     - Integrate with language-specific parsing libraries for accurate code analysis.
     - Provide a unified API to "instrument" code blocks (e.g., wrap methods with measurement calls).
     - Expose a plugin system for language-specific query definitions.
   - **Key Patterns:**  
     - **Plugin Architecture:** So that each language can have its own parsing rules and instrumentation logic.
     - **Separation of Concerns:** Ensuring parsing logic remains independent of measurement logic.

3. **Command Line Interface (CLI)**
   - **Purpose:**
     Provides the primary user interface via a Typer-based CLI for triggering instrumentation, execution, and viewing energy reports.
   - **Responsibilities:**
     - Handle command-line arguments and subcommands (measure, analyze, benchmark, etc.)
     - Interface with the Instrumentation Engine to parse and instrument code
     - Execute instrumented code and collect measurements
     - Display results in terminal with Rich formatting or export to JSON/CSV
   - **Key Patterns:**
     - **Command Pattern:** Each CLI subcommand encapsulates a specific operation
     - **Facade:** Simplifies interactions between user and underlying engines
   - **Implementation:**
     - `src/cli/cli.py`: Main CLI commands using Typer framework
     - `src/cli/entrypoint.py`: Entry point with path independence for system-wide execution

4. **Reporting and Aggregation**
   - **Purpose:**  
     Aggregates raw measurement data to produce per-method energy consumption metrics and offers output in standard formats.
   - **Responsibilities:**  
     - Process raw measurement data.
     - Generate outputs such as CSV, JSON, or interactive dashboards.
   - **Key Patterns:**  
     - **Separation of Concerns:** Decouple reporting from measurement, enabling independent improvements.

## 5. Analysis and Reporting (Current Implementation)

- **Purpose:**
  Process raw measurement data and generate structured reports with energy consumption metrics and insights.
- **Responsibilities:**
  - Aggregate checkpoint-level energy data into function/method summaries
  - Calculate derived metrics (average power, energy per invocation, etc.)
  - Generate output in multiple formats (JSON, CSV, terminal display)
  - Identify energy hotspots and provide optimization suggestions
- **Key Patterns:**
  - **Data Pipeline:** Raw measurements → Aggregation → Reporting
  - **Strategy Pattern:** Different output formats (JSON, CSV, terminal)
- **Implementation:**
  - Integrated into CLI commands (measure, analyze)
  - Rich terminal formatting for interactive display
  - JSON export for programmatic consumption

## 6. Future Extensions (Experimental)

The following modules exist in the codebase but are in experimental/development stages:

- **src/optimizer/**: Energy optimization analysis and suggestions (experimental)
- **src/analyzer/**: Static code analysis for energy patterns (experimental)
- **src/ide/**: IDE integration support (experimental)

These modules represent planned future capabilities and are not yet fully integrated into the main workflow.


---

## 2. Repository Structure and Modules

The CodeGreen project is organized as a hybrid Python-C++ system where high-performance measurement is handled by the C++ NEMB backend, and language processing/instrumentation is handled by Python.

```
/codegreen/
├── CMakeLists.txt                         # Main build configuration
├── install.sh                             # Automated installation script
├── pyproject.toml                         # Python package configuration
├── setup.py                               # Python setup script
├── config/
│   └── codegreen.json                    # Default configuration
├── bin/                                  # Generated at build time (gitignored)
│   ├── codegreen                         # C++ NEMB binary
│   ├── src/                              # Copied instrumentation files
│   └── runtime/                          # Runtime modules
├── lib/                                  # Generated at build time (gitignored)
│   ├── libcodegreen-nemb.so              # Compiled NEMB library
│   └── libcodegreen-core.a               # Core static library
├── src/
│   ├── __init__.py                       # Package initialization with path setup
│   ├── cli/
│   │   ├── cli.py                        # Typer-based CLI commands
│   │   └── entrypoint.py                 # Entry point with path independence
│   ├── instrumentation/                  # Tree-sitter based code analysis
│   │   ├── language_engine.py            # Multi-language coordinator
│   │   ├── bridge_analyze.py             # AST analysis via Tree-sitter
│   │   ├── bridge_instrument.py          # Code instrumentation
│   │   ├── language_configs.py           # Language-specific SCM queries
│   │   ├── ast_processor.py              # AST manipulation
│   │   ├── configs/                      # Language configuration JSONs
│   │   │   ├── python.json
│   │   │   ├── cpp.json
│   │   │   ├── c.json
│   │   │   └── java.json
│   │   └── language_runtimes/            # Runtime integration code
│   │       ├── python/codegreen_runtime.py
│   │       ├── cpp/codegreen/runtime.hpp
│   │       ├── c/codegreen_runtime.h
│   │       └── java/codegreen/runtime/CodeGreenRuntime.java
│   ├── measurement/                      # C++ NEMB backend
│   │   ├── CMakeLists.txt
│   │   ├── main.cpp                      # C++ binary entry point
│   │   ├── include/nemb/
│   │   │   ├── codegreen_energy.hpp      # Public API
│   │   │   ├── core/
│   │   │   │   ├── measurement_coordinator.hpp  # Multi-provider orchestration
│   │   │   │   └── energy_provider.hpp          # Abstract provider interface
│   │   │   ├── drivers/
│   │   │   │   ├── intel_rapl_provider.hpp      # Intel/AMD RAPL
│   │   │   │   ├── nvidia_nvml_provider.hpp     # NVIDIA GPU
│   │   │   │   └── amd_gpu_provider.hpp         # AMD ROCm
│   │   │   └── utils/
│   │   │       └── precision_timer.hpp          # High-resolution timing
│   │   └── src/nemb/
│   │       ├── codegreen_energy.cpp       # Checkpoint implementation
│   │       ├── config_loader.cpp          # JSON config parser
│   │       ├── core/
│   │       │   └── measurement_coordinator.cpp  # Background polling
│   │       └── drivers/
│   │           ├── intel_rapl_provider.cpp      # RAPL implementation
│   │           ├── nvidia_nvml_provider.cpp     # NVML implementation
│   │           └── amd_gpu_provider.cpp         # ROCm implementation
│   ├── analyzer/                         # Static analysis modules (experimental)
│   ├── optimizer/                        # Optimization suggestions (experimental)
│   ├── ide/                              # IDE integration (experimental)
│   └── utils/                            # Shared utilities
├── docs/
│   ├── architecture/
│   │   ├── checkpointing-architecture.md # Checkpoint system specification
│   │   └── nemb-vs-v1.md                 # V1→V2 architectural evolution
│   ├── design/
│   │   ├── architecture.md               # This document
│   │   └── codegreen_arch.mmd            # Mermaid architecture diagram
│   ├── configuration-guide.md            # Configuration reference
│   ├── USAGE.md                          # User guide
│   └── website/                          # MkDocs documentation site
│       ├── mkdocs.yml
│       └── docs/
├── scripts/
│   └── commands.txt                      # Complete CLI command reference
├── third_party/
│   ├── tree-sitter-python/               # Python grammar
│   ├── tree-sitter-cpp/                  # C++ grammar
│   ├── tree-sitter-c/                    # C grammar
│   └── tree-sitter-java/                 # Java grammar
├── tests/
│   └── ...                               # Unit and integration tests
├── .gitignore
├── LICENSE
└── README.md
```

---

## 3. Architecture Diagram

The system architecture is visualized in the Mermaid diagram located at `docs/design/codegreen_arch.mmd`. The diagram shows:

- **User Interface Layer (Purple):** CLI as the primary interface
- **Python Layer (Green):** Language processing and instrumentation
  - Language Engine coordinates multi-language support
  - Tree-sitter provides AST parsing
  - Bridge components handle analysis and instrumentation
- **C++ NEMB Layer (Blue):** High-performance measurement backend
  - EnergyMeter provides checkpoint API
  - MeasurementCoordinator orchestrates multiple providers
  - Background polling thread samples hardware at 10ms/1ms intervals
  - Correlation engine matches checkpoints to energy readings
- **Hardware Providers (Red):** Energy sensor drivers
  - Intel/AMD RAPL for CPU energy
  - NVIDIA NVML for NVIDIA GPU energy
  - AMD ROCm for AMD GPU energy
- **Language Support (Yellow):** Tree-sitter grammars
  - Python, C++, C, Java parsers

The data flow demonstrates the complete measurement cycle from CLI invocation through instrumentation, execution, measurement, correlation, and reporting.

---

## 4. Key Considerations and Best Practices

- **Clear Interface Contracts:**  
  Each module defines explicit API contracts (for instance, how the Instrumentation Engine communicates with the Measurement Engine) so that new plugins (for languages or hardware) can be added without modifying existing code.

- **Plugin/Extension System:**  
  Employ a plugin architecture via configuration or dependency injection to support both language adapters and hardware measurement modules. This enables the addition of new languages or devices without redundant code.

- **Modular Testing:**  
  Write comprehensive unit and integration tests for each module to ensure that new changes do not break existing functionality.

- **Documentation:**  
  Maintain up-to-date documentation in the `docs/` directory. This includes architectural designs, API documentation, contribution guidelines, and usage examples to support future extensibility and onboarding.

- **Continuous Integration/Delivery (CI/CD):**  
  Implement CI pipelines (e.g., via GitHub Actions, Travis CI, or GitLab CI) to automatically run tests and build packages, ensuring that updates in one module do not adversely affect others.

- **Versioning and Dependency Management:**  
  Use semantic versioning for each package and employ CMake for dependency resolution and build management.

- **IDE and User Experience:**  
  The IDE integration layer is decoupled from core functionality, allowing independent development of plugins for different IDEs while reusing the underlying measurement and instrumentation libraries.

- **Future Proofing:**  
  The design supports any language or hardware by abstracting implementation details in the core engine and providing clear extension points. This flexibility allows integration of emerging hardware counters or dynamic runtime instrumentation without major code rewrites.

---

## 4. How It Works Together

### Current Workflow

1. **User Executes CLI Command:**
   ```bash
   codegreen measure python script.py --precision high
   ```

2. **Analysis Phase (Python):**
   - CLI invokes `LanguageEngine` to analyze source code
   - Tree-sitter parser generates AST for the target language
   - `bridge_analyze.py` identifies instrumentation points using SCM queries
   - Returns analysis result with function boundaries and metadata

3. **Instrumentation Phase (Python):**
   - `bridge_instrument.py` injects checkpoint calls at identified points
   - For Python: Creates `script_instrumented.py` with runtime imports
   - For C/C++/Java: Prepares instrumentation configuration for C++ binary

4. **Measurement Phase (C++ NEMB):**
   - NEMB `MeasurementCoordinator` starts background polling thread
   - Energy providers (RAPL, NVML, ROCm) sampled at 10ms (or 1ms high-accuracy)
   - Application executes, calls `mark_checkpoint(name)` at instrumentation points
   - Checkpoints generate timestamp markers (format: `name#inv_N_tTHREADID`)
   - Background thread records `(timestamp, cumulative_energy)` tuples

5. **Correlation Phase (C++ NEMB):**
   - After execution, `get_checkpoint_measurements()` correlates markers with readings
   - Binary search finds surrounding energy readings for each checkpoint
   - Linear interpolation calculates energy at exact checkpoint timestamp
   - Returns `CorrelatedCheckpoint` objects with energy attribution

6. **Reporting Phase (Python CLI):**
   - CLI receives measurement results from NEMB
   - Aggregates data by function/method
   - Calculates statistics (total energy, average power, invocations)
   - Outputs to terminal (Rich formatting) or exports to JSON/CSV

### Extensibility Points

1. **Adding a New Language:**
   - Add Tree-sitter grammar to `third_party/tree-sitter-{language}/`
   - Create `configs/{language}.json` with SCM query patterns
   - Add language-specific runtime in `language_runtimes/{language}/`
   - Register in `LanguageEngine`

2. **Supporting New Hardware:**
   - Implement `EnergyProvider` interface in `src/measurement/src/nemb/drivers/`
   - Override `get_reading()` and `get_spec()` methods
   - Register provider in `detect_available_providers()`
   - No changes needed to core measurement logic

3. **Custom Analysis/Reporting:**
   - Measurement results available as JSON via `--output` flag
   - Can be consumed by external tools for custom analysis
   - Future: Plugin system for custom report generators

---