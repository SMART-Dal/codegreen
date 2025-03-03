# Energy Core

The **Energy Core** module is the foundation of Code Green. It provides the core measurement engine and a Hardware Abstraction Layer (HAL) to interface with various energy sources.

**Responsibilities:**
- Define common interfaces and APIs for energy measurement (e.g., startMeasurement, stopMeasurement, calculateDelta).
- Implement hardware-specific adapters (e.g., Intel RAPL, ARM counters, external meters) using adapter/strategy patterns.
- Offer a plugin mechanism for integrating new hardware measurement techniques.

**Design Patterns:**
- **Adapter/Strategy:** To plug in different hardware implementations.
- **Dependency Injection:** For ease of testing and swapping implementations.

**Usage and Extension:**
- Use the provided APIs to integrate energy measurements into other components.
- Extend by adding new adapters for emerging hardware without modifying the core logic.
