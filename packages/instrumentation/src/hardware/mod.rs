use std::sync::Arc;
use tokio::sync::Mutex;
use anyhow::Result;
use tracing::{info, error};
use energy_hardware_plugins::{HardwarePlugin, PluginRegistry, Measurement};

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

    pub async fn start_measurement(&self) -> Result<()> {
        let mut plugin = self.plugin.lock().await;
        plugin.start_measurement()
            .map_err(|e| anyhow::anyhow!("Failed to start measurement: {}", e))
    }

    pub async fn stop_measurement(&self) -> Result<()> {
        let mut plugin = self.plugin.lock().await;
        plugin.stop_measurement()
            .map_err(|e| anyhow::anyhow!("Failed to stop measurement: {}", e))
    }

    pub async fn get_measurement(&self) -> Result<Measurement> {
        let plugin = self.plugin.lock().await;
        plugin.get_measurement()
            .map_err(|e| anyhow::anyhow!("Failed to get measurement: {}", e))
    }

    pub async fn get_name(&self) -> String {
        let plugin = self.plugin.lock().await;
        plugin.name().to_string()
    }
}

/// Manages multiple hardware plugins
pub struct EnergyMonitor {
    plugins: Vec<AsyncHardwarePlugin>,
}

impl EnergyMonitor {
    pub fn new() -> Self {
        Self {
            plugins: Vec::new(),
        }
    }

    pub async fn add_plugin(&mut self, plugin: Box<dyn HardwarePlugin>) {
        self.plugins.push(AsyncHardwarePlugin::new(plugin));
    }

    pub async fn start_measurement(&self) -> Result<()> {
        for plugin in &self.plugins {
            if let Err(e) = plugin.start_measurement().await {
                error!("Failed to start measurement for {}: {}", plugin.get_name().await, e);
            }
        }
        Ok(())
    }

    pub async fn stop_measurement(&self) -> Result<()> {
        for plugin in &self.plugins {
            if let Err(e) = plugin.stop_measurement().await {
                error!("Failed to stop measurement for {}: {}", plugin.get_name().await, e);
            }
        }
        Ok(())
    }

    pub async fn get_total_energy_consumption(&self) -> Result<f64> {
        let mut total = 0.0;
        for plugin in &self.plugins {
            match plugin.get_measurement().await {
                Ok(measurement) => total += measurement.power_watts,
                Err(e) => error!("Failed to get energy consumption for {}: {}", plugin.get_name().await, e),
            }
        }
        Ok(total)
    }
} 