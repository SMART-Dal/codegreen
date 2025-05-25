use crate::{EnergyAdapter, EnergyResult};
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
    plugins: Vec<Arc<dyn Plugin>>,
}

impl PluginManager {
    /// Create a new plugin manager
    pub fn new() -> Self {
        Self {
            plugins: Vec::new(),
        }
    }

    /// Load a plugin from a shared library
    pub fn load_plugin(&mut self, path: &Path) -> EnergyResult<()> {
        // TODO: Implement dynamic plugin loading
        // This would involve:
        // 1. Loading the shared library
        // 2. Finding the plugin entry point
        // 3. Creating a plugin instance
        // 4. Adding it to the plugins list
        Ok(())
    }

    /// Get all loaded plugins
    pub fn plugins(&self) -> &[Arc<dyn Plugin>] {
        &self.plugins
    }

    /// Create adapters from all loaded plugins
    pub fn create_adapters(&self) -> EnergyResult<Vec<Box<dyn EnergyAdapter>>> {
        let mut adapters = Vec::new();
        for plugin in &self.plugins {
            adapters.push(plugin.create_adapter()?);
        }
        Ok(adapters)
    }
} 