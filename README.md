# Codegreen

Codegreen is a comprehensive energy measurement and analysis tool for software systems. It provides a unified interface for measuring energy consumption across different hardware platforms and programming languages.

## Project Structure

```
codegreen/
├── core/                           # Core measurement engine and orchestration
│   ├── src/
│   │   ├── adapters/              # Hardware adapter interfaces
│   │   ├── measurement/           # Measurement session management
│   │   ├── plugin/                # Plugin system
│   │   └── error.rs               # Error handling
│   ├── tests/                     # Core tests
│   └── benches/                   # Benchmark tests
│
├── packages/
│   ├── instrumentation/           # Code instrumentation tools
│   │   ├── src/
│   │   ├── examples/             # Usage examples
│   │   └── tests/                # Package tests
│   │
│   ├── hardware-plugins/         # Hardware-specific implementations
│   │   ├── src/
│   │   │   ├── intel/           # Intel-specific implementations
│   │   │   ├── arm/             # ARM-specific implementations
│   │   │   └── common/          # Shared hardware utilities
│   │   └── tests/
│   │
│   ├── language-adapters/        # Language-specific analyzers
│   │   ├── src/
│   │   │   ├── python/          # Python analyzer
│   │   │   ├── javascript/      # JavaScript/TypeScript analyzer
│   │   │   └── rust/            # Rust analyzer
│   │   └── tests/
│   │
│   ├── ide/                      # IDE integration
│   │   ├── src/
│   │   │   ├── vscode/          # VS Code extension
│   │   │   └── jetbrains/       # JetBrains plugin
│   │   └── tests/
│   │
│   ├── optimizer/                # Energy optimization tools
│   │   ├── src/
│   │   │   ├── analysis/        # Code analysis
│   │   │   └── suggestions/     # Optimization suggestions
│   │   └── tests/
│   │
│   └── visualization/            # Data visualization
│       ├── src/
│       │   ├── dashboards/      # Grafana dashboards
│       │   └── reports/         # Report generation
│       └── tests/
│
├── docker/                        # Docker configurations
│   ├── grafana/                  # Grafana setup
│   ├── prometheus/               # Prometheus setup
│   └── influxdb/                 # InfluxDB setup
│
├── docs/                         # Project documentation
│   ├── architecture/            # Architecture diagrams and docs
│   ├── api/                     # API documentation
│   └── guides/                  # User guides
│
├── scripts/                      # Build and utility scripts
├── Cargo.toml                    # Workspace configuration
└── README.md                     # This file
```

## Components

### Core
The central orchestration layer that:
- Manages measurement sessions
- Coordinates hardware plugins
- Integrates language adapters
- Provides unified APIs

### Hardware Plugins
Platform-specific implementations for:
- Intel RAPL
- ARM energy counters
- External power meters
- Custom hardware

### Language Adapters
Language-specific analyzers for:
- Python
- JavaScript/TypeScript
- Rust
- C/C++

### Instrumentation
Tools for:
- Code instrumentation
- Performance profiling
- Energy analysis

### IDE Integration
Editor plugins for:
- VS Code
- JetBrains IDEs
- Real-time energy insights

### Optimizer
Energy optimization tools:
- Code analysis
- Optimization suggestions
- Best practices

### Visualization
Data presentation tools:
- Interactive dashboards
- Custom reports
- Trend analysis

## Development Guidelines

### Code Organization
- Follow Rust module organization best practices
- Keep modules focused and single-responsibility
- Use feature flags for optional functionality
- Maintain clear public APIs

### Testing
- Write unit tests for all public APIs
- Include integration tests for component interactions
- Add benchmarks for performance-critical code
- Maintain high test coverage

### Documentation
- Document all public APIs with examples
- Keep README files up to date
- Include architecture diagrams
- Write clear commit messages

### Error Handling
- Use custom error types
- Provide meaningful error messages
- Include error context where helpful
- Handle errors at appropriate levels

## Getting Started

1. Install dependencies:
```bash
cargo build
```

2. Run tests:
```bash
cargo test
```

3. Build documentation:
```bash
cargo doc --open
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and ensure they pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
