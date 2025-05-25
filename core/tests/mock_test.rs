use energy_core::{MeasurementEngine, EnergyResult, EnergyMeasurement};
use energy_hardware_plugins::{HardwarePlugin, PluginRegistry};
use mockall::predicate::*;
use mockall::mock;
use std::sync::Arc;
use tokio::time::sleep;
use std::time::Duration;

// Mock the HardwarePlugin trait
mock! {
    pub HardwarePlugin {
        fn name(&self) -> &'static str;
        fn is_supported(&self) -> bool;
        fn initialize(&self) -> EnergyResult<()>;
        fn start_measurement(&self) -> EnergyResult<EnergyMeasurement>;
        fn stop_measurement(&self) -> EnergyResult<EnergyMeasurement>;
    }
}

#[tokio::test]
async fn test_mock_hardware_plugin() -> EnergyResult<()> {
    // Create a mock plugin
    let mut mock_plugin = MockHardwarePlugin::new();
    
    // Set up expectations
    mock_plugin.expect_name()
        .return_const("mock_plugin");
    
    mock_plugin.expect_is_supported()
        .return_const(true);
    
    mock_plugin.expect_initialize()
        .returning(|| Ok(()));
    
    mock_plugin.expect_start_measurement()
        .returning(|| {
            Ok(EnergyMeasurement {
                timestamp: std::time::Instant::now(),
                joules: 100.0,
                watts: 50.0,
                source: "mock".to_string(),
            })
        });
    
    mock_plugin.expect_stop_measurement()
        .returning(|| {
            Ok(EnergyMeasurement {
                timestamp: std::time::Instant::now(),
                joules: 150.0,
                watts: 50.0,
                source: "mock".to_string(),
            })
        });

    // Create measurement engine with mock plugin
    let mut engine = MeasurementEngine::new();
    let plugin_registry = PluginRegistry::new();
    plugin_registry.register_plugin(Arc::new(mock_plugin));

    // Test measurement flow
    let start_measurements = engine.start_measurements().await?;
    assert!(!start_measurements.is_empty());
    
    sleep(Duration::from_millis(100)).await;
    
    let sessions = engine.stop_measurements(start_measurements).await?;
    assert!(!sessions.is_empty());
    
    for session in sessions {
        assert_eq!(session.total_energy, 50.0);
        assert!(session.duration.as_millis() >= 100);
    }

    Ok(())
}

#[tokio::test]
async fn test_mock_plugin_error_handling() {
    // Create a mock plugin that fails
    let mut mock_plugin = MockHardwarePlugin::new();
    
    mock_plugin.expect_name()
        .return_const("failing_plugin");
    
    mock_plugin.expect_is_supported()
        .return_const(true);
    
    mock_plugin.expect_initialize()
        .returning(|| Err(energy_core::EnergyError::PluginError("Init failed".to_string())));
    
    // Create measurement engine with failing plugin
    let mut engine = MeasurementEngine::new();
    let plugin_registry = PluginRegistry::new();
    plugin_registry.register_plugin(Arc::new(mock_plugin));

    // Test error handling
    let result = engine.start_measurements().await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_mock_plugin_unsupported() -> EnergyResult<()> {
    // Create a mock plugin that's not supported
    let mut mock_plugin = MockHardwarePlugin::new();
    
    mock_plugin.expect_name()
        .return_const("unsupported_plugin");
    
    mock_plugin.expect_is_supported()
        .return_const(false);
    
    // Create measurement engine with unsupported plugin
    let mut engine = MeasurementEngine::new();
    let plugin_registry = PluginRegistry::new();
    plugin_registry.register_plugin(Arc::new(mock_plugin));

    // Test unsupported plugin handling
    let start_measurements = engine.start_measurements().await?;
    assert!(start_measurements.is_empty());
    
    let sessions = engine.stop_measurements(start_measurements).await?;
    assert!(sessions.is_empty());

    Ok(())
} 