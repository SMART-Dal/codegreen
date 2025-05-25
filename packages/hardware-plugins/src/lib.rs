//! Hardware-specific plugins for energy measurement
//! 
//! This module provides plugins for different hardware platforms to measure
//! energy consumption.

pub mod intel;
pub mod amd;
pub mod arm;
pub mod common;
pub mod nvidia;

use thiserror::Error;
use std::time::Instant;
use serde::{Serialize, Deserialize};
use async_trait::async_trait;
use std::fmt;
use std::error::Error;
use std::time::Duration;

pub use intel::IntelRaplPlugin;
pub use amd::AmdEnergyPlugin;
pub use arm::ArmEnergyPlugin;
pub use nvidia::NvidiaGpuPlugin;
pub use common::HardwarePlugin;

/// Errors that can occur during hardware plugin operations
#[derive(Error, Debug)]
pub enum HardwarePluginError {
    #[error("Failed to initialize hardware plugin: {0}")]
    InitializationError(String),
    
    #[error("Failed to read energy measurements: {0}")]
    MeasurementError(String),
    
    #[error("Unsupported hardware: {0}")]
    UnsupportedHardware(String),
}

/// Initialize hardware plugins
pub fn init() -> Result<(), HardwarePluginError> {
    // TODO: Initialize hardware plugins
    Ok(())
}

/// Get available hardware plugins
pub fn get_available_plugins() -> Vec<String> {
    // TODO: Implement plugin discovery
    Vec::new()
}

/// Represents energy measurement data
// #[derive(Debug, Clone)]
// pub struct EnergyMeasurement {
//     pub timestamp: u64,
//     pub value: f64,
//     pub unit: String,
//     pub source: String,
// }

/// Represents a measurement result from hardware sensors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Measurement {
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub joules: f64,
}

/// Represents errors that can occur during hardware measurements
#[derive(Debug, Error)]
pub enum HardwareError {
    #[error("Device not found: {0}")]
    DeviceNotFound(String),
    #[error("Permission denied: {0}")]
    PermissionDenied(String),
    #[error("Sensor error: {0}")]
    SensorError(String),
    #[error("Unsupported operation: {0}")]
    UnsupportedOperation(String),
    #[error("Other error: {0}")]
    Other(String),
}

/// Plugin registry for managing hardware plugins
pub struct PluginRegistry {
    plugins: Vec<Box<dyn HardwarePlugin>>,
}

impl PluginRegistry {
    pub fn new() -> Self {
        let mut registry = Self {
            plugins: Vec::new(),
        };
        if let Ok(plugin) = IntelRaplPlugin::new() {
            registry.register_plugin(Box::new(plugin));
        }
        if let Ok(plugin) = AmdEnergyPlugin::new() {
            registry.register_plugin(Box::new(plugin));
        }
        if let Ok(plugin) = ArmEnergyPlugin::new() {
            registry.register_plugin(Box::new(plugin));
        }
        if let Ok(plugin) = NvidiaGpuPlugin::new() {
            registry.register_plugin(Box::new(plugin));
        }
        registry
    }
    
    pub fn register_plugin(&mut self, plugin: Box<dyn HardwarePlugin>) {
        self.plugins.push(plugin);
    }
    
    pub fn get_available_plugins(&self) -> Vec<&dyn HardwarePlugin> {
        self.plugins.iter()
            .filter(|p| p.is_available())
            .map(|p| p.as_ref())
            .collect()
    }
    
    pub fn get_plugin_by_name(&self, name: &str) -> Option<&dyn HardwarePlugin> {
        self.plugins.iter()
            .find(|p| p.name() == name)
            .map(|p| p.as_ref())
    }

    pub fn get_plugins(&self) -> &[Box<dyn HardwarePlugin>] {
        &self.plugins
    }
}