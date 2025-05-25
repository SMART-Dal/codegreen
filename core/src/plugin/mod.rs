use crate::adapters::EnergyAdapter;
use crate::EnergyResult;
use hardware_plugins::HardwarePlugin;
use std::any::Any;
use std::path::Path;
use std::sync::Arc;

/// Plugin metadata
#[derive(Debug, Clone)]
pub struct PluginMetadata {
    /// Plugin name
    pub name: String,
    /// Plugin version
    pub version: String,
    /// Plugin description
    pub description: String,
    /// Plugin author
    pub author: String,
}

/// Plugin trait that all plugins must implement
pub trait Plugin: Send + Sync {
    /// Get plugin metadata
    fn metadata(&self) -> &PluginMetadata;

    /// Initialize the plugin
    fn initialize(&self) -> EnergyResult<()>;

    /// Create an energy adapter from this plugin
    fn create_adapter(&self) -> EnergyResult<Box<dyn EnergyAdapter>>;

    /// Get plugin-specific data
    fn get_data(&self) -> Option<&dyn Any>;
}

/// Plugin manager that handles loading and managing plugins
pub struct PluginManager {
    adapters: Vec<Box<dyn EnergyAdapter>>,
}

impl PluginManager {
    /// Create a new plugin manager
    pub fn new() -> Self {
        Self {
            adapters: Vec::new(),
        }
    }

    /// Load a plugin from a shared library
    pub fn load_plugin(&mut self, _path: &Path) -> EnergyResult<()> {
        // TODO: Implement dynamic plugin loading
        // This would involve:
        // 1. Loading the shared library
        // 2. Finding the plugin entry point
        // 3. Creating a plugin instance
        // 4. Adding it to the plugins list
        Ok(())
    }

    /// Register a new adapter
    pub fn register_adapter(&mut self, adapter: Box<dyn EnergyAdapter>) {
        self.adapters.push(adapter);
    }

    /// Get all registered adapters
    pub fn get_adapters(&self) -> &[Box<dyn EnergyAdapter>] {
        &self.adapters
    }

    /// Create a new adapter from an existing one
    pub fn create_adapter(&self, adapter: &dyn EnergyAdapter) -> EnergyResult<Box<dyn EnergyAdapter>> {
        // Since we can't clone the trait object directly, we need to create a new adapter
        // based on the adapter's name and type
        match adapter.name() {
            "intel_rapl" => {
                let plugin = hardware_plugins::IntelRaplPlugin::new()?;
                Ok(Box::new(crate::adapters::IntelRaplAdapter::new(Box::new(plugin))))
            }
            "arm_pmu" => {
                let plugin = hardware_plugins::ArmEnergyPlugin::new()?;
                Ok(Box::new(crate::adapters::ArmPmuAdapter::new(Box::new(plugin))))
            }
            "nvidia_gpu" => {
                let plugin = hardware_plugins::NvidiaGpuPlugin::new()?;
                Ok(Box::new(crate::adapters::NvidiaGpuAdapter::new(Box::new(plugin))))
            }
            _ => Err(crate::EnergyError::HardwareError(
                hardware_plugins::HardwareError::UnsupportedOperation(
                    format!("Unknown adapter type: {}", adapter.name())
                )
            ))
        }
    }
} 