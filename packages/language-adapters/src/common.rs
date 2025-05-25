//! Common functionality for language adapters

use serde::{Serialize, Deserialize};

/// Common configuration for all language adapters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdapterConfig {
    pub enabled_languages: Vec<String>,
    pub analysis_depth: u32,
    pub log_level: String,
}

/// Common adapter interface
pub trait LanguageAdapter {
    fn name(&self) -> &str;
    fn version(&self) -> &str;
    fn initialize(&mut self) -> Result<(), String>;
    fn shutdown(&mut self) -> Result<(), String>;
    fn is_available(&self) -> bool;
}

/// Default implementation of adapter configuration
impl Default for AdapterConfig {
    fn default() -> Self {
        Self {
            enabled_languages: vec!["python".to_string(), "rust".to_string(), "cpp".to_string()],
            analysis_depth: 3,
            log_level: "info".to_string(),
        }
    }
} 