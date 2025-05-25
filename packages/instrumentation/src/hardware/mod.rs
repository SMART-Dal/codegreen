use std::sync::Arc;
use tokio::sync::Mutex;
use anyhow::Result;
use tracing::{info, error};
use futures_util::future::TryFutureExt;
use hardware_plugins::{HardwarePlugin, Measurement};
use crate::error::InstrumentationError;

/// Async wrapper around hardware plugins
pub struct AsyncHardwarePlugin {
    plugin: Arc<Mutex<Box<dyn HardwarePlugin>>>,
}

impl AsyncHardwarePlugin {
    pub fn new(plugin: Box<dyn HardwarePlugin>) -> Self {
        Self {
            plugin: Arc::new(Mutex::new(plugin)),
        }
    }

    pub async fn start_measurement(&self) -> Result<Measurement, InstrumentationError> {
        let mut plugin = self.plugin.lock().await;
        plugin.start_measurement().await.map_err(|e| InstrumentationError::HardwareError(Box::new(e)))
    }

    pub async fn stop_measurement(&self) -> Result<Measurement, InstrumentationError> {
        let mut plugin = self.plugin.lock().await;
        plugin.stop_measurement().await.map_err(|e| InstrumentationError::HardwareError(Box::new(e)))
    }

    pub async fn get_measurement(&self) -> Result<Measurement, InstrumentationError> {
        let plugin = self.plugin.lock().await;
        plugin.get_measurement().map_err(|e| InstrumentationError::HardwareError(Box::new(e)))
    }

    pub async fn get_name(&self) -> String {
        let plugin = self.plugin.lock().await;
        plugin.name().to_string()
    }
}

/// Manages multiple hardware plugins
pub struct EnergyMonitor {
    plugins: Vec<AsyncHardwarePlugin>,
    start_measurements: Vec<Measurement>,
}

impl EnergyMonitor {
    pub fn new() -> Self {
        Self {
            plugins: Vec::new(),
            start_measurements: Vec::new(),
        }
    }

    pub fn register_plugin(&mut self, plugin: Box<dyn HardwarePlugin>) {
        self.plugins.push(AsyncHardwarePlugin::new(plugin));
    }

    pub async fn start_measurement(&mut self) -> Result<(), InstrumentationError> {
        self.start_measurements.clear();
        for plugin in &self.plugins {
            if let Ok(measurement) = plugin.start_measurement().await {
                self.start_measurements.push(measurement);
            }
        }
        Ok(())
    }

    pub async fn stop_measurement(&mut self) -> Result<Vec<Measurement>, InstrumentationError> {
        let mut end_measurements = Vec::new();
        for (i, plugin) in self.plugins.iter().enumerate() {
            if let Ok(end) = plugin.stop_measurement().await {
                let start = &self.start_measurements[i];
                end_measurements.push(Measurement {
                    timestamp: end.timestamp,
                    joules: end.joules - start.joules,
                });
            }
        }
        Ok(end_measurements)
    }

    pub async fn get_total_energy(&self) -> Result<f64, InstrumentationError> {
        let mut total = 0.0;
        for plugin in &self.plugins {
            if let Ok(measurement) = plugin.get_measurement().await {
                total += measurement.joules;
            }
        }
        Ok(total)
    }
} 