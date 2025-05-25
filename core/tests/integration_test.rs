use energy_core::{MeasurementEngine, EnergyResult, EnergyError};
use energy_language_adapters::LanguageAdapter;
use energy_hardware_plugins::{PluginRegistry, HardwarePlugin};
use std::time::Duration;
use tokio::time::sleep;

// Test data
const TEST_PYTHON_CODE: &str = r#"
def calculate_sum(a, b):
    return a + b

def main():
    result = calculate_sum(5, 10)
    print(f"Sum: {result}")

if __name__ == "__main__":
    main()
"#;

#[tokio::test]
async fn test_energy_measurement_flow() -> EnergyResult<()> {
    // Create measurement engine
    let mut engine = MeasurementEngine::new();

    // Start measurements
    let start_measurements = engine.start_measurements().await?;
    assert!(!start_measurements.is_empty(), "No measurements started");

    // Analyze Python code
    engine.analyze_code(TEST_PYTHON_CODE, "python")?;

    // Simulate some work
    sleep(Duration::from_millis(100)).await;

    // Stop measurements
    let sessions = engine.stop_measurements(start_measurements).await?;
    assert!(!sessions.is_empty(), "No measurement sessions returned");

    // Verify measurements
    for session in sessions {
        assert!(session.duration.as_millis() >= 100, "Duration too short");
        assert!(session.total_energy >= 0.0, "Negative energy consumption");
        assert!(session.end.joules >= session.start.joules, "End energy less than start energy");
    }

    Ok(())
}

#[tokio::test]
async fn test_unsupported_language() {
    let engine = MeasurementEngine::new();
    let result = engine.analyze_code(TEST_PYTHON_CODE, "unsupported_language");
    assert!(matches!(result, Err(EnergyError::LanguageAdapterError(_))));
}

#[tokio::test]
async fn test_measurement_without_analysis() -> EnergyResult<()> {
    let engine = MeasurementEngine::new();
    let start_measurements = engine.start_measurements().await?;
    sleep(Duration::from_millis(100)).await;
    let sessions = engine.stop_measurements(start_measurements).await?;
    
    assert!(!sessions.is_empty(), "No measurement sessions returned");
    for session in sessions {
        assert!(session.total_energy >= 0.0, "Negative energy consumption");
    }

    Ok(())
}

#[tokio::test]
async fn test_multiple_measurements() -> EnergyResult<()> {
    let mut engine = MeasurementEngine::new();
    
    // First measurement
    let start1 = engine.start_measurements().await?;
    engine.analyze_code(TEST_PYTHON_CODE, "python")?;
    sleep(Duration::from_millis(50)).await;
    let sessions1 = engine.stop_measurements(start1).await?;

    // Second measurement
    let start2 = engine.start_measurements().await?;
    engine.analyze_code(TEST_PYTHON_CODE, "python")?;
    sleep(Duration::from_millis(50)).await;
    let sessions2 = engine.stop_measurements(start2).await?;

    // Verify both measurements
    assert_eq!(sessions1.len(), sessions2.len(), "Different number of sessions");
    for (s1, s2) in sessions1.iter().zip(sessions2.iter()) {
        assert!(s1.total_energy >= 0.0, "Negative energy in first measurement");
        assert!(s2.total_energy >= 0.0, "Negative energy in second measurement");
    }

    Ok(())
}

#[tokio::test]
async fn test_measurement_consistency() -> EnergyResult<()> {
    let mut engine = MeasurementEngine::new();
    let mut measurements = Vec::new();

    // Take multiple measurements of the same code
    for _ in 0..3 {
        let start = engine.start_measurements().await?;
        engine.analyze_code(TEST_PYTHON_CODE, "python")?;
        sleep(Duration::from_millis(50)).await;
        let sessions = engine.stop_measurements(start).await?;
        measurements.push(sessions);
    }

    // Verify consistency
    assert_eq!(measurements.len(), 3, "Wrong number of measurement sets");
    for i in 1..measurements.len() {
        assert_eq!(
            measurements[i].len(),
            measurements[0].len(),
            "Inconsistent number of sessions"
        );
    }

    Ok(())
} 