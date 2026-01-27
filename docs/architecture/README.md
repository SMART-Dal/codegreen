# CodeGreen Architecture Documentation

Comprehensive architecture documentation for CodeGreen's NEMB (Native Energy Measurement Backend) system.

## Core Architecture Documents

### [NEMB Design Overview](nemb-design.md)
Industry-grade energy measurement system design covering:
- System architecture and component hierarchy
- Hardware abstraction layer design
- Measurement accuracy techniques
- Noise reduction and statistical filtering
- Performance optimization strategies
- Hardware-specific implementations (Intel, AMD, NVIDIA, ARM)

### [Checkpointing Architecture](checkpointing-architecture.md)
Technical specification of the checkpoint system:
- Signal-generator model and format specification
- Thread-local invocation tracking implementation
- Energy correlation algorithm (binary search + interpolation)
- Memory ordering guarantees and performance characteristics
- Multi-threading support and clock synchronization

### [Instrumentation System](instrumentation.md)
Source code instrumentation and checkpoint injection:
- LanguageEngine orchestration and analysis pipeline
- Tree-sitter AST parsing and query execution
- Language configuration via JSON files
- Code transformation and checkpoint injection
- Adding support for new programming languages

### [NEMB vs V1 Architecture](nemb-vs-v1.md)
Architectural evolution from V1 to V2:
- PMT-based V1 architecture limitations
- NEMB V2 signal-generator model
- Performance comparisons (25-100x improvement)
- Migration path and compatibility

## Getting Started

### [Quick Start Guide](quickstart.md)
Get started with CodeGreen in minutes:
- Installation (system dependencies, build, init-sensors)
- Basic usage commands
- Language support (Python, C++, C, Java)
- Troubleshooting common issues

### [C++ Backend Development](cpp_guide.md)
NEMB backend development guide:
- Building and debugging NEMB
- Core components (EnergyMeter, MeasurementCoordinator, EnergyProvider)
- Developing custom energy providers
- Testing and best practices

## Hardware Integration

### [Intel RAPL Guide](intel_rapl_guide.md)
Intel CPU energy measurement:
- RAPL domains (PKG, PP0, PP1, DRAM)
- MSR access and energy unit calculation
- Counter wraparound handling
- Production deployment best practices

### [NVIDIA GPU Guide](nvidia_gpu_guide.md)
NVIDIA GPU energy measurement:
- NVML API integration
- Power management and P-states
- Multi-GPU support
- Thermal monitoring correlation

### [AMD Hardware Guide](amd_hardware_guide.md)
AMD CPU and GPU measurement:
- AMD RAPL implementation (Zen architecture)
- ROCm SMI integration for GPUs
- Chiplet-aware energy attribution
- Platform-specific considerations

## Best Practices

### [Measurement Accuracy Guide](measurement_accuracy_best_practices.md)
Achieving production-grade accuracy:
- Multi-source validation techniques
- Statistical uncertainty quantification
- Environmental compensation (temperature, frequency)
- Cross-validation with external references
- Calibration and validation frameworks

## Documentation Structure

```
docs/architecture/
├── README.md                           # This index
├── architecture.md                     # High-level system architecture
├── codegreen_arch.mmd                  # Architecture diagram (Mermaid)
├── codegreen_arch.png                  # Architecture diagram (PNG)
├── codegreen_arch.svg                  # Architecture diagram (SVG)
├── nemb-design.md                      # NEMB design overview
├── checkpointing-architecture.md       # Checkpoint system spec
├── nemb-vs-v1.md                       # V1→V2 evolution
├── instrumentation.md                  # Source code instrumentation system
├── quickstart.md                       # Installation & basic usage
├── cpp_guide.md                        # NEMB C++ development
├── intel_rapl_guide.md                 # Intel CPU measurement
├── nvidia_gpu_guide.md                 # NVIDIA GPU measurement
├── amd_hardware_guide.md               # AMD hardware measurement
└── measurement_accuracy_best_practices.md  # Accuracy guidelines
```

## Related Documentation

- **Design Docs**: `docs/design/` - High-level architecture diagrams
- **Usage Guide**: `docs/USAGE.md` - Complete CLI command reference
- **Configuration**: `docs/configuration-guide.md` - NEMB configuration options
- **Theory**: `theory.txt` - Mathematical foundations and validation

## Contributing

When adding new architecture documentation:

1. **Focus**: One topic per document
2. **Depth**: Sufficient detail for implementation
3. **Cross-references**: Link to related documents
4. **Code examples**: Include real implementation snippets
5. **Accuracy**: Verify against current codebase

## Document Maintenance

Architecture docs are verified against:
- Implementation: `src/measurement/`
- Tests: `tests/cpp/`
- Configuration: `config/codegreen.json`

Last comprehensive review: 2026-01-19
