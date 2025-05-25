use energy_instrumentation::{InstrumentationEngine, PythonAdapter, metrics::MetricsStore};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    // Create metrics store
    let metrics_store = MetricsStore::new("http://localhost:8086")?;

    // Create and configure the instrumentation engine
    let mut engine = InstrumentationEngine::new(metrics_store);
    let python_adapter = PythonAdapter::new();
    engine.register_adapter(Box::new(python_adapter));

    // Example Python code with multiple functions and classes
    let source_code = r#"
def calculate_sum(a, b):
    result = a + b
    return result

class Calculator:
    def add(self, x, y):
        return x + y
    
    def subtract(self, x, y):
        return x - y

def main():
    calc = Calculator()
    result = calc.add(5, 3)
    print(f"Result: {result}")
"#;

    // Instrument the code
    match engine.instrument(source_code, "python").await {
        Ok(instrumented_code) => {
            println!("Original code:\n{}", source_code);
            println!("\nInstrumented code:\n{}", instrumented_code);
        }
        Err(e) => eprintln!("Error during instrumentation: {}", e),
    }

    Ok(())
} 