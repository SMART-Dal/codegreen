# Codegreen Core

The **Codegreen Core** is the central orchestration layer of the Codegreen system. It provides the foundation for energy measurement and analysis across multiple programming languages and hardware architectures.

## Architecture

The core module:
- Orchestrates hardware plugins and language adapters
- Manages measurement sessions and data collection
- Provides a unified interface for energy analysis
- Handles error management and system state

## Components

### Measurement Engine
- Coordinates energy measurements across hardware
- Manages measurement sessions
- Handles data aggregation and validation

### Plugin System
- Integrates with hardware-specific plugins
- Provides plugin lifecycle management
- Ensures consistent measurement interfaces

### Language Adapters
- Integrates with language-specific analyzers
- Provides code analysis capabilities
- Enables energy-aware code optimization

## Usage

```rust
use codegreen_core::{MeasurementEngine, EnergyResult};

async fn measure_energy() -> EnergyResult<()> {
    let mut engine = MeasurementEngine::new();
    
    // Start measurements
    let start_measurements = engine.start_measurements().await?;
    
    // Analyze code
    engine.analyze_code(source_code, "python")?;
    
    // Stop measurements
    let sessions = engine.stop_measurements(start_measurements).await?;
    
    Ok(())
}
```

## Integration

The core module integrates with:
- Hardware plugins for energy measurement
- Language adapters for code analysis
- Storage systems for data persistence
- Visualization tools for data presentation
