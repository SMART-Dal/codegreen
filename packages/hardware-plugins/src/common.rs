//! Common functionality for hardware plugins

use serde::{Serialize, Deserialize};
use async_trait::async_trait;
use chrono::Utc;
use crate::{Measurement, HardwareError};

/// Common configuration for all hardware plugins
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginConfig {
    pub sampling_interval_ms: u64,
    pub enabled_sources: Vec<String>,
    pub log_level: String,
}

/// Base plugin implementation with common functionality
pub struct BasePlugin {
    name: &'static str,
    description: &'static str,
    enabled: bool,
    device_path: String,
}

impl BasePlugin {
    pub fn new(name: &'static str, description: &'static str, device_path: String) -> Self {
        Self {
            name,
            description,
            enabled: true,
            device_path,
        }
    }

    pub fn name(&self) -> &'static str {
        self.name
    }

    pub fn description(&self) -> &'static str {
        self.description
    }

    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    pub fn device_path(&self) -> &str {
        &self.device_path
    }
}

/// Default implementation of plugin configuration
impl Default for PluginConfig {
    fn default() -> Self {
        Self {
            sampling_interval_ms: 1000,
            enabled_sources: Vec::new(),
            log_level: "info".to_string(),
        }
    }
}

/// Trait that all hardware measurement plugins must implement
#[async_trait]
pub trait HardwarePlugin: Send + Sync {
    /// Get the name of the hardware plugin
    fn name(&self) -> &'static str;
    
    /// Get a description of the hardware plugin
    fn description(&self) -> &'static str;
    
    /// Check if the hardware is available and supported
    fn is_available(&self) -> bool;
    
    /// Check if the hardware is supported
    fn is_supported(&self) -> bool;
    
    /// Initialize the hardware plugin
    fn initialize(&mut self) -> Result<(), HardwareError>;
    
    /// Start measuring energy consumption
    async fn start_measurement(&self) -> Result<Measurement, HardwareError>;
    
    /// Stop measuring energy consumption
    async fn stop_measurement(&self) -> Result<Measurement, HardwareError>;
    
    /// Get the current measurement
    fn get_measurement(&self) -> Result<Measurement, HardwareError>;
    
    /// Get the supported metrics for this hardware
    fn supported_metrics(&self) -> Vec<&'static str>;
    
    /// Get the total energy consumption
    async fn get_total_energy_consumption(&self) -> Result<f64, HardwareError>;
}

/// Default implementations for common plugin functionality
pub trait DefaultPluginImpl: HardwarePlugin {
    fn base(&self) -> &BasePlugin;
    fn is_supported(&self) -> bool;
}

/// Default implementations for HardwarePlugin trait
#[async_trait]
impl<T: DefaultPluginImpl> HardwarePlugin for T {
    fn name(&self) -> &'static str {
        self.base().name()
    }

    fn description(&self) -> &'static str {
        self.base().description()
    }

    fn is_available(&self) -> bool {
        self.base().is_enabled()
    }

    fn is_supported(&self) -> bool {
        DefaultPluginImpl::is_supported(self)
    }

    fn initialize(&mut self) -> Result<(), HardwareError> {
        Ok(())
    }

    async fn start_measurement(&self) -> Result<Measurement, HardwareError> {
        Ok(Measurement {
            timestamp: Utc::now(),
            joules: 0.0,
        })
    }

    async fn stop_measurement(&self) -> Result<Measurement, HardwareError> {
        Ok(Measurement {
            timestamp: Utc::now(),
            joules: 0.0,
        })
    }

    fn get_measurement(&self) -> Result<Measurement, HardwareError> {
        Ok(Measurement {
            timestamp: Utc::now(),
            joules: 0.0,
        })
    }

    fn supported_metrics(&self) -> Vec<&'static str> {
        vec!["power", "energy"]
    }

    async fn get_total_energy_consumption(&self) -> Result<f64, HardwareError> {
        Ok(0.0)
    }
} 