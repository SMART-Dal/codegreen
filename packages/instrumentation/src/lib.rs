//! Code instrumentation tools for energy measurement
//! 
//! This package provides tools for instrumenting code to measure energy consumption
//! across different programming languages.

mod error;
mod instrumenter;
mod parser;

pub use error::InstrumentationError;
pub use instrumenter::Instrumenter;
pub use parser::Parser;

/// Result type for instrumentation operations
pub type Result<T> = std::result::Result<T, InstrumentationError>;

/// Supported programming languages
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Language {
    Python,
    JavaScript,
    Rust,
}

impl Language {
    /// Get the language name as a string
    pub fn as_str(&self) -> &'static str {
        match self {
            Language::Python => "python",
            Language::JavaScript => "javascript",
            Language::Rust => "rust",
        }
    }
}

/// Configuration for instrumentation
#[derive(Debug, Clone)]
pub struct InstrumentationConfig {
    /// The language to instrument
    pub language: Language,
    /// Whether to instrument function calls
    pub instrument_functions: bool,
    /// Whether to instrument loops
    pub instrument_loops: bool,
    /// Whether to instrument memory operations
    pub instrument_memory: bool,
}

impl Default for InstrumentationConfig {
    fn default() -> Self {
        Self {
            language: Language::Python,
            instrument_functions: true,
            instrument_loops: true,
            instrument_memory: true,
        }
    }
}

use std::collections::HashMap;
use tree_sitter::{Parser, Query, QueryCursor};
use tree_sitter_python::language;
use tokio::sync::Mutex;
use std::sync::Arc;

pub mod hardware;
pub mod metrics;

use hardware::{EnergyMonitor, RAPLSource};
use metrics::{MetricsStore, EnergyMeasurement};
use chrono::Utc;

pub trait LanguageAdapter {
    fn get_language_id(&self) -> &str;
    fn get_grammar(&self) -> tree_sitter::Language;
    fn parse(&self, source_code: &str) -> tree_sitter::Tree;
    fn get_function_query(&self) -> &str;
    fn get_class_query(&self) -> &str;
    fn get_import_query(&self) -> &str;
}

pub struct PythonAdapter {
    parser: Parser,
}

impl PythonAdapter {
    pub fn new() -> Self {
        let mut parser = Parser::new();
        parser.set_language(language()).unwrap();
        Self { parser }
    }
}

impl LanguageAdapter for PythonAdapter {
    fn get_language_id(&self) -> &str {
        "python"
    }

    fn get_grammar(&self) -> tree_sitter::Language {
        language()
    }

    fn parse(&self, source_code: &str) -> tree_sitter::Tree {
        self.parser.parse(source_code, None).unwrap()
    }

    fn get_function_query(&self) -> &str {
        r#"
        (function_definition
            name: (identifier) @function.name
            parameters: (parameters) @function.params
            body: (block) @function.body
        )
        "#
    }

    fn get_class_query(&self) -> &str {
        r#"
        (class_definition
            name: (identifier) @class.name
            body: (block) @class.body
        )
        "#
    }

    fn get_import_query(&self) -> &str {
        r#"
        (import_statement) @import
        (import_from_statement) @import.from
        "#
    }
}

pub struct InstrumentationEngine {
    adapters: HashMap<String, Box<dyn LanguageAdapter>>,
    energy_monitor: Arc<Mutex<EnergyMonitor>>,
    metrics_store: Arc<Mutex<MetricsStore>>,
}

impl InstrumentationEngine {
    pub fn new(metrics_store: MetricsStore) -> Self {
        let mut monitor = EnergyMonitor::new();
        if let Ok(rapl_source) = RAPLSource::new() {
            tokio::spawn(async move {
                monitor.add_source(Box::new(rapl_source)).await;
            });
        }

        Self {
            adapters: HashMap::new(),
            energy_monitor: Arc::new(Mutex::new(monitor)),
            metrics_store: Arc::new(Mutex::new(metrics_store)),
        }
    }

    pub fn register_adapter(&mut self, adapter: Box<dyn LanguageAdapter>) {
        self.adapters.insert(adapter.get_language_id().to_string(), adapter);
    }

    pub fn get_adapter(&self, language_id: &str) -> Option<&Box<dyn LanguageAdapter>> {
        self.adapters.get(language_id)
    }

    pub async fn instrument(&self, source_code: &str, language_id: &str) -> Result<String, String> {
        let adapter = self.get_adapter(language_id)
            .ok_or_else(|| format!("No adapter found for language: {}", language_id))?;

        let tree = adapter.parse(source_code);
        let query = Query::new(adapter.get_grammar(), adapter.get_function_query())
            .map_err(|e| e.to_string())?;
        
        let mut cursor = QueryCursor::new();
        let matches = cursor.matches(&query, tree.root_node(), source_code.as_bytes());
        
        let mut instrumented_code = source_code.to_string();
        let mut offset = 0;

        for match_ in matches {
            let function_node = match_.captures[0].node;
            let start_position = function_node.start_position();
            let end_position = function_node.end_position();

            // Add measurement hooks
            let before_hook = self.generate_before_hook();
            let after_hook = self.generate_after_hook();

            // Insert hooks at the appropriate positions
            instrumented_code = self.insert_at_position(
                &instrumented_code,
                &before_hook,
                start_position.row,
                start_position.column + offset,
            );
            offset += before_hook.len();

            instrumented_code = self.insert_at_position(
                &instrumented_code,
                &after_hook,
                end_position.row,
                end_position.column + offset,
            );
            offset += after_hook.len();
        }

        Ok(instrumented_code)
    }

    async fn record_measurement(&self, function_name: &str, language: &str) -> Result<(), String> {
        let monitor = self.energy_monitor.lock().await;
        let metrics = self.metrics_store.lock().await;

        // Start measurement
        monitor.start_measurement().await.map_err(|e| e.to_string())?;

        // Get energy consumption
        let energy = monitor.get_total_energy_consumption().await.map_err(|e| e.to_string())?;

        // Record measurement
        let measurement = EnergyMeasurement {
            timestamp: Utc::now(),
            energy_joules: energy,
            source: "RAPL".to_string(),
            function_name: function_name.to_string(),
            language: language.to_string(),
        };

        metrics.record_measurement(measurement).await.map_err(|e| e.to_string())?;

        // Stop measurement
        monitor.stop_measurement().await.map_err(|e| e.to_string())?;

        Ok(())
    }

    fn generate_before_hook(&self) -> String {
        "\n__energy_measurement_start();\n".to_string()
    }

    fn generate_after_hook(&self) -> String {
        "\n__energy_measurement_end();\n".to_string()
    }

    fn insert_at_position(
        &self,
        source: &str,
        insert: &str,
        row: usize,
        column: usize,
    ) -> String {
        let mut lines: Vec<&str> = source.lines().collect();
        if row < lines.len() {
            let line = lines[row];
            let (before, after) = line.split_at(column);
            lines[row] = &format!("{}{}{}", before, insert, after);
        }
        lines.join("\n")
    }
} 