# Energy Instrumentation

The **Energy Instrumentation** module leverages Tree-sitter for language-agnostic parsing and code instrumentation. It identifies method or function boundaries and injects measurement hooks to capture energy consumption at a fine granularity.

## Features
- High-performance Rust implementation for minimal measurement noise
- Language-agnostic parsing using Tree-sitter
- Plugin system for language-specific adapters
- Zero-cost abstractions and direct memory management

## Building
```bash
# Install Rust if you haven't already
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build the project
cargo build --release

# Run tests
cargo test
```

## Usage
```rust
use energy_instrumentation::{InstrumentationEngine, PythonAdapter};

fn main() {
    let mut engine = InstrumentationEngine::new();
    let python_adapter = PythonAdapter::new();
    engine.register_adapter(Box::new(python_adapter));

    let source_code = r#"
    def calculate_sum(a, b):
        result = a + b
        return result
    "#;

    match engine.instrument(source_code, "python") {
        Ok(instrumented_code) => println!("{}", instrumented_code),
        Err(e) => eprintln!("Error: {}", e),
    }
}
```

## Adding New Language Support
1. Create a new adapter implementing the `LanguageAdapter` trait
2. Add the corresponding Tree-sitter grammar dependency
3. Register the adapter with the `InstrumentationEngine`

## Performance
- Minimal runtime overhead
- No garbage collection pauses
- Direct memory management
- Native machine code execution
- Efficient Tree-sitter integration
