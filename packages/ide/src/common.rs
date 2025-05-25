//! Common functionality for IDE integration

use serde::{Serialize, Deserialize};

/// Common configuration for all IDE integrations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommonConfig {
    pub enable_telemetry: bool,
    pub log_level: String,
    pub workspace_path: String,
}

/// Common plugin interface
pub trait Plugin {
    fn name(&self) -> &str;
    fn version(&self) -> &str;
    fn initialize(&mut self) -> Result<(), String>;
    fn shutdown(&mut self) -> Result<(), String>;
}

/// Default implementation of common configuration
impl Default for CommonConfig {
    fn default() -> Self {
        Self {
            enable_telemetry: true,
            log_level: "info".to_string(),
            workspace_path: ".".to_string(),
        }
    }
} 