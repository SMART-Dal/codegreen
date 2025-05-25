//! Language-specific adapters for energy measurement
//! 
//! This module provides adapters for different programming languages to measure
//! and analyze energy consumption.

pub mod python;
pub mod rust;
pub mod cpp;
pub mod common;

use thiserror::Error;

/// Errors that can occur during language adapter operations
#[derive(Error, Debug)]
pub enum LanguageAdapterError {
    #[error("Failed to initialize language adapter: {0}")]
    InitializationError(String),
    
    #[error("Failed to parse code: {0}")]
    ParseError(String),
    
    #[error("Unsupported language feature: {0}")]
    UnsupportedFeature(String),
}

/// Initialize language adapters
pub fn init() -> Result<(), LanguageAdapterError> {
    // TODO: Initialize language adapters
    Ok(())
}

/// Get available language adapters
pub fn get_available_adapters() -> Vec<String> {
    // TODO: Implement adapter discovery
    Vec::new()
}

/// Represents a code analysis result
#[derive(Debug, Clone)]
pub struct AnalysisResult {
    pub language: String,
    pub energy_score: f64,
    pub hotspots: Vec<CodeHotspot>,
    pub suggestions: Vec<OptimizationSuggestion>,
}

/// Represents a code section with high energy consumption
#[derive(Debug, Clone)]
pub struct CodeHotspot {
    pub file_path: String,
    pub line_start: usize,
    pub line_end: usize,
    pub energy_impact: f64,
    pub description: String,
}

/// Represents a suggestion for optimizing energy consumption
#[derive(Debug, Clone)]
pub struct OptimizationSuggestion {
    pub description: String,
    pub impact: f64,
    pub difficulty: String,
    pub code_snippet: String,
}

use tree_sitter::{Language, Parser, Tree};

/// Trait for language-specific adapters that handle parsing and analysis
pub trait LanguageAdapter {
    /// Get the language identifier (e.g., 'python', 'java', 'cpp')
    fn get_language_id(&self) -> &'static str;

    /// Get the Tree-sitter grammar for this language
    fn get_grammar(&self) -> Language;

    /// Parse the given source code and return an AST
    fn parse(&self, source_code: &str) -> Tree {
        let mut parser = Parser::new();
        parser.set_language(self.get_grammar()).unwrap();
        parser.parse(source_code, None).unwrap()
    }

    /// Get the query for finding function/method definitions in this language
    fn get_function_query(&self) -> &'static str;

    /// Get the query for finding class definitions in this language
    fn get_class_query(&self) -> &'static str;

    /// Get the query for finding import/require statements in this language
    fn get_import_query(&self) -> &'static str;
} 