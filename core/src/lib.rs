use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::time::{Duration, Instant};
use thiserror::Error;
use energy_hardware_plugins::{HardwarePlugin, PluginRegistry};
use energy_language_adapters::LanguageAdapter;

pub mod adapters;
pub mod measurement;
pub mod plugin;

/// Represents a measurement of energy consumption
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnergyMeasurement {
    /// The timestamp when the measurement was taken
    pub timestamp: Instant,
    /// The energy consumption in joules
    pub joules: f64,
    /// The power consumption in watts
    pub watts: f64,
    /// The source of the measurement (e.g., "cpu", "gpu", "system")
    pub source: String,
}

/// Represents a measurement session with start and end measurements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeasurementSession {
    /// The start measurement
    pub start: EnergyMeasurement,
    /// The end measurement
    pub end: EnergyMeasurement,
    /// The duration of the session
    pub duration: Duration,
    /// The total energy consumed during the session
    pub total_energy: f64,
}

/// Errors that can occur during energy measurement
#[derive(Error, Debug)]
pub enum EnergyError {
    #[error("Hardware not supported: {0}")]
    HardwareNotSupported(String),
    #[error("Measurement failed: {0}")]
    MeasurementFailed(String),
    #[error("Plugin error: {0}")]
    PluginError(String),
    #[error("Language adapter error: {0}")]
    LanguageAdapterError(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// Result type for energy measurement operations
pub type EnergyResult<T> = Result<T, EnergyError>;

/// Core measurement engine that manages hardware plugins and language adapters
pub struct MeasurementEngine {
    plugin_registry: PluginRegistry,
    language_adapters: Vec<Box<dyn LanguageAdapter>>,
}

impl MeasurementEngine {
    /// Create a new measurement engine
    pub fn new() -> Self {
        Self {
            plugin_registry: PluginRegistry::new(),
            language_adapters: Vec::new(),
        }
    }

    /// Register a language adapter
    pub fn register_language_adapter(&mut self, adapter: Box<dyn LanguageAdapter>) {
        self.language_adapters.push(adapter);
    }

    /// Get all registered language adapters
    pub fn language_adapters(&self) -> &[Box<dyn LanguageAdapter>] {
        &self.language_adapters
    }

    /// Start measurements from all hardware plugins
    pub async fn start_measurements(&self) -> EnergyResult<Vec<EnergyMeasurement>> {
        let mut measurements = Vec::new();
        for plugin in self.plugin_registry.get_available_plugins() {
            if plugin.is_supported() {
                plugin.initialize()?;
                measurements.push(plugin.start_measurement()?);
            }
        }
        Ok(measurements)
    }

    /// Stop measurements and calculate deltas
    pub async fn stop_measurements(
        &self,
        start_measurements: Vec<EnergyMeasurement>,
    ) -> EnergyResult<Vec<MeasurementSession>> {
        let mut sessions = Vec::new();
        for (plugin, start) in self.plugin_registry.get_available_plugins().iter().zip(start_measurements) {
            if plugin.is_supported() {
                let end = plugin.stop_measurement()?;
                sessions.push(MeasurementSession {
                    start,
                    end,
                    duration: end.timestamp.duration_since(start.timestamp),
                    total_energy: end.joules - start.joules,
                });
            }
        }
        Ok(sessions)
    }

    /// Analyze code with language adapters
    pub fn analyze_code(&self, source_code: &str, language_id: &str) -> EnergyResult<()> {
        if let Some(adapter) = self.language_adapters.iter().find(|a| a.get_language_id() == language_id) {
            let ast = adapter.parse(source_code);
            // TODO: Implement code analysis logic
            Ok(())
        } else {
            Err(EnergyError::LanguageAdapterError(format!(
                "No adapter found for language: {}",
                language_id
            )))
        }
    }
} 