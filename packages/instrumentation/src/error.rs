use std::error::Error;
use std::fmt;
use thiserror::Error;

/// Errors that can occur during instrumentation
#[derive(Debug, Error)]
pub enum InstrumentationError {
    #[error("Hardware error: {0}")]
    HardwareError(#[from] Box<dyn Error + Send + Sync>),
    #[error("Language error: {0}")]
    LanguageError(String),
    #[error("Measurement error: {0}")]
    MeasurementError(String),
    #[error("Language not supported: {0}")]
    LanguageNotSupported(String),
    #[error("Query error: {0}")]
    QueryError(String),
    #[error("Tree-sitter error: {0}")]
    TreeSitterError(String),
    #[error("InfluxDB error: {0}")]
    InfluxError(#[from] influxdb::Error),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Parser error: {0}")]
    ParserError(String),
    #[error("Anyhow error: {0}")]
    AnyhowError(#[from] anyhow::Error),
}

impl From<String> for InstrumentationError {
    fn from(err: String) -> Self {
        InstrumentationError::LanguageError(err)
    }
} 