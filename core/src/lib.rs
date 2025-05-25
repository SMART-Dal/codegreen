use serde::{Deserialize, Serialize};
use std::time::Duration;
use thiserror::Error;
use hardware_plugins::{HardwarePlugin, PluginRegistry, HardwareError, Measurement};
use language_adapters::LanguageAdapter;
use chrono::{DateTime, Utc};
use std::collections::HashMap;

pub mod adapters;
pub mod measurement;
pub mod plugin;

/// Represents a measurement session with start and end measurements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeasurementSession {
    pub start_measurements: HashMap<String, Measurement>,
    pub end_measurements: HashMap<String, Measurement>,
    pub start: DateTime<Utc>,
    pub end: DateTime<Utc>,
    pub duration: Duration,
    pub total_energy: f64,
}

impl MeasurementSession {
    /// Create a new measurement session
    pub fn new() -> Self {
        Self {
            start_measurements: HashMap::new(),
            end_measurements: HashMap::new(),
            start: Utc::now(),
            end: Utc::now(),
            duration: Duration::from_secs(0),
            total_energy: 0.0,
        }
    }

    /// Add a start measurement
    pub fn add_start_measurement(&mut self, source: String, measurement: Measurement) {
        self.start_measurements.insert(source, measurement);
    }

    /// Add an end measurement
    pub fn add_end_measurement(&mut self, source: String, measurement: Measurement) {
        let timestamp = measurement.timestamp;
        self.end_measurements.insert(source, measurement);
        self.end = timestamp;
        self.duration = self.end.signed_duration_since(self.start).to_std().unwrap_or_default();
        self.calculate_total_energy();
    }

    /// Calculate total energy consumption
    fn calculate_total_energy(&mut self) {
        self.total_energy = 0.0;
        for (source, end_measurement) in &self.end_measurements {
            if let Some(start_measurement) = self.start_measurements.get(source) {
                self.total_energy += end_measurement.joules - start_measurement.joules;
            }
        }
    }

    /// Get the duration of the measurement session
    pub fn get_duration(&self) -> Duration {
        self.duration
    }

    /// Get the total energy consumption
    pub fn get_total_energy(&self) -> f64 {
        self.total_energy
    }

    /// Get all measurements for a specific source
    pub fn get_measurements(&self, source: &str) -> Option<(Measurement, Measurement)> {
        let start = self.start_measurements.get(source)?;
        let end = self.end_measurements.get(source)?;
        Some((start.clone(), end.clone()))
    }
}

/// Errors that can occur during energy measurement
#[derive(Debug, Error)]
pub enum EnergyError {
    #[error("Hardware error: {0}")]
    HardwareError(#[from] HardwareError),
    #[error("Language error: {0}")]
    LanguageError(String),
    #[error("Measurement error: {0}")]
    MeasurementError(String),
}

impl From<String> for EnergyError {
    fn from(err: String) -> Self {
        EnergyError::LanguageError(err)
    }
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

    /// Analyze code with language adapters
    pub fn analyze_code(&self, source_code: &str, language_id: &str) -> EnergyResult<()> {
        if let Some(adapter) = self.language_adapters.iter().find(|a| a.get_language_id() == language_id) {
            let _ast = adapter.parse(source_code);
            // TODO: Implement code analysis logic
            Ok(())
        } else {
            Err(EnergyError::LanguageError(format!(
                "No adapter found for language: {}",
                language_id
            )))
        }
    }
}

pub struct EnergyMonitor {
    registry: PluginRegistry,
}

impl EnergyMonitor {
    pub fn new() -> Self {
        Self {
            registry: PluginRegistry::new(),
        }
    }

    pub fn register_plugin(&mut self, plugin: Box<dyn HardwarePlugin>) {
        self.registry.register_plugin(plugin);
    }

    pub async fn start_measurement(&self) -> EnergyResult<MeasurementSession> {
        let plugins = self.registry.get_plugins();
        let mut session = MeasurementSession::new();
        for plugin in plugins {
            let measurement = plugin.get_measurement().map_err(EnergyError::HardwareError)?;
            session.add_start_measurement(plugin.name().to_string(), measurement);
        }
        Ok(session)
    }

    pub async fn stop_measurement(&self, mut session: MeasurementSession) -> EnergyResult<MeasurementSession> {
        let plugins = self.registry.get_plugins();
        for plugin in plugins {
            let measurement = plugin.get_measurement().map_err(EnergyError::HardwareError)?;
            session.add_end_measurement(plugin.name().to_string(), measurement);
        }
        Ok(session)
    }

    pub fn get_plugins(&self) -> Vec<&dyn HardwarePlugin> {
        self.registry.get_available_plugins()
    }
} 