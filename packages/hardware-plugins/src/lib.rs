use std::error::Error;
use std::fmt;
use std::time::{Duration, Instant};

/// Represents a measurement result from hardware sensors
#[derive(Debug, Clone)]
pub struct Measurement {
    pub timestamp: Instant,
    pub power_watts: f64,
    pub temperature_celsius: Option<f64>,
    pub additional_metrics: std::collections::HashMap<String, f64>,
}

/// Represents errors that can occur during hardware measurements
#[derive(Debug)]
pub enum HardwareError {
    DeviceNotFound(String),
    PermissionDenied(String),
    SensorError(String),
    UnsupportedOperation(String),
    Other(String),
}

impl fmt::Display for HardwareError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            HardwareError::DeviceNotFound(msg) => write!(f, "Device not found: {}", msg),
            HardwareError::PermissionDenied(msg) => write!(f, "Permission denied: {}", msg),
            HardwareError::SensorError(msg) => write!(f, "Sensor error: {}", msg),
            HardwareError::UnsupportedOperation(msg) => write!(f, "Unsupported operation: {}", msg),
            HardwareError::Other(msg) => write!(f, "Other error: {}", msg),
        }
    }
}

impl Error for HardwareError {}

/// Trait that all hardware measurement plugins must implement
pub trait HardwarePlugin: Send + Sync {
    /// Initialize the hardware plugin
    fn initialize(&mut self) -> Result<(), HardwareError>;
    
    /// Get the name of the hardware plugin
    fn name(&self) -> &'static str;
    
    /// Get a description of the hardware plugin
    fn description(&self) -> &'static str;
    
    /// Check if the hardware is available and supported
    fn is_available(&self) -> bool;
    
    /// Start measuring energy consumption
    fn start_measurement(&mut self) -> Result<(), HardwareError>;
    
    /// Stop measuring energy consumption
    fn stop_measurement(&mut self) -> Result<(), HardwareError>;
    
    /// Get the current measurement
    fn get_measurement(&self) -> Result<Measurement, HardwareError>;
    
    /// Get the supported metrics for this hardware
    fn supported_metrics(&self) -> Vec<&'static str>;
}

/// Plugin registry for managing hardware plugins
pub struct PluginRegistry {
    plugins: Vec<Box<dyn HardwarePlugin>>,
}

impl PluginRegistry {
    pub fn new() -> Self {
        Self { plugins: Vec::new() }
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
}

// Re-export common types
pub use self::Measurement;
pub use self::HardwareError;
pub use self::HardwarePlugin;
pub use self::PluginRegistry; 