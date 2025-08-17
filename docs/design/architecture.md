# CodeGreen Architecture Overview

This document provides an overview of the CodeGreen tool's architecture. CodeGreen is designed as a modular, language-agnostic energy measurement system that supports multiple hardware platforms and scenarios. Its design follows best practices to ensure extensibility, maintainability, and reusability.

## 1. High-Level Architecture Overview

#### A. Core Layers

1. **Measurement Engine (Core Library)**
   - **Purpose:**  
     Provides a language- and platform-agnostic abstraction over energy measurement. It defines interfaces for starting/stopping measurements and calculating energy consumption.
   - **Responsibilities:**  
     - Define common APIs for energy measurement (e.g., `startMeasurement()`, `stopMeasurement()`, `calculateDelta()`).
     - Implement the Hardware Abstraction Layer (HAL) to integrate with multiple energy sources (e.g., Intel RAPL, ARM counters, external meters).
     - Offer a plugin mechanism for new hardware measurement modules.
   - **Key Patterns:**  
     - **Adapter/Strategy:** For integrating different hardware implementations.
     - **Dependency Injection:** To allow flexible swapping and testing of measurement strategies.

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

3. **IDE Integration / User Interface**
   - **Purpose:**  
     Provides an interactive experience (via an IDE plugin or standalone UI) where users can trigger instrumentation, execution, and view energy reports.
   - **Responsibilities:**  
     - Handle user interactions (e.g., button clicks) to start the measurement process.
     - Interface with the Instrumentation Engine to parse and instrument code.
     - Display results in an accessible format (tables, charts, etc.).
   - **Key Patterns:**  
     - **Facade:** Simplify interactions with a unified control panel.
     - **Modularity:** Allow integration with multiple IDEs (e.g., VSCode, IntelliJ) via adapter plugins.

4. **Reporting and Aggregation**
   - **Purpose:**  
     Aggregates raw measurement data to produce per-method energy consumption metrics and offers output in standard formats.
   - **Responsibilities:**  
     - Process raw measurement data.
     - Generate outputs such as CSV, JSON, or interactive dashboards.
   - **Key Patterns:**  
     - **Separation of Concerns:** Decouple reporting from measurement, enabling independent improvements.

## 5. Visualization and Dashboard

- **Purpose:**  
  To provide an interactive dashboard and visualization tools that allow users to explore energy consumption data through dynamic plots, charts, and reports.
- **Responsibilities:**  
  - Generate dynamic visualizations (e.g., bar charts, line graphs, heat maps).
  - Integrate with the reporting module to visualize aggregated data.
  - Offer filtering and drill-down capabilities for detailed analysis.
- **Key Patterns:**  
  - **Modular UI Components:** Reusable components for data visualization.
  - **Integration with Reporting:** Leverage existing measurement data for visual insights.
- **Extensibility:**  
  New visualization components can be added as separate plugins or extensions within the module.

## 6. Energy Optimizers and Refactoring

- **Purpose:**  
  To analyze energy consumption patterns and recommend optimizations or refactoring approaches to improve energy efficiency.
- **Responsibilities:**  
  - Analyze energy usage data to identify hotspots and inefficiencies.
  - Provide recommendations or automated refactoring suggestions for energy-efficient code.
  - Integrate with code analysis tools and IDEs for seamless feedback.
- **Key Patterns:**  
  - **Analysis Pipeline:** Process measurement data to produce actionable insights.
  - **Plugin Architecture:** Enable integration of new optimization strategies without modifying core modules.
- **Extensibility:**  
  New optimization strategies or heuristics can be added as plugins within this module.


---

## 2. Repository Structure and Modules

The CodeGreen project is organized as a monorepo where each module is developed and tested as an independent package. This modular structure promotes code reuse and simplifies the process of adding new features or supporting additional languages and hardware platforms.

```
/codegreen/
├── CMakeLists.txt                  # Main CMake configuration
├── src/                            # Main application source
│   └── main.cpp                   # Entry point
├── core/                           # Core measurement engine library
│   ├── CMakeLists.txt             # Core library build config
│   ├── include/                    # Public headers
│   │   ├── measurement_engine.hpp
│   │   ├── energy_monitor.hpp
│   │   ├── measurement_session.hpp
│   │   ├── measurement.hpp
│   │   ├── plugin/
│   │   │   ├── hardware_plugin.hpp
│   │   │   └── plugin_registry.hpp
│   │   └── adapters/
│   │       └── language_adapter.hpp
│   └── src/                        # Implementation files
│       ├── measurement_engine.cpp
│       ├── energy_monitor.cpp
│       ├── measurement_session.cpp
│       └── plugin/
│           └── plugin_registry.cpp
├── packages/                        # Feature packages
│   ├── ide/                        # IDE integration
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   └── src/
│   ├── optimizer/                  # Code optimization
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   └── src/
│   ├── visualization/              # Data visualization
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   └── src/
│   ├── instrumentation/            # Code instrumentation
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   └── src/
│   ├── hardware-plugins/           # Hardware monitoring plugins
│   │   ├── CMakeLists.txt
│   │   ├── include/
│   │   └── src/
│   └── language-adapters/          # Language-specific adapters
│       ├── CMakeLists.txt
│       ├── include/
│       └── src/
├── docs/                           # Architecture docs, design guidelines, tutorials, etc.
│   └── design/
│       └── architecture.md         # This design document
├── scripts/                        # Build and utility scripts
│   └── build.sh                   # Build script
├── .gitignore
├── LICENSE
└── README.md
```

---

## 3. Key Considerations and Best Practices

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

1. **User Workflow:**
   - A developer clicks a button in their IDE (via the ide module).
   - The IDE plugin invokes the Instrumentation Engine (instrumentation) to parse the currently open file using language-specific parsers.
   - Detected method blocks are instrumented by injecting calls to the Measurement Engine (core).
   - As the application executes, the Measurement Engine (utilizing hardware plugins from hardware-plugins) records energy consumption.
   - Once execution is complete, the data is aggregated and presented in a structured report via the IDE plugin.

2. **Extensibility:**
   - **Adding a New Language:**  
     Implement new parsing rules and instrumentation logic in the language-adapters module.
   - **Supporting New Hardware:**  
     Develop and integrate a new hardware plugin within the hardware-plugins module that conforms to the common measurement interface.
   - **Enhancing the UI:**  
     Extend the ide module with additional features or support for other IDEs without altering the core measurement or instrumentation components.

---