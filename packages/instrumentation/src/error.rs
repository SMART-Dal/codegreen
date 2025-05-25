use thiserror::Error;

/// Errors that can occur during instrumentation
#[derive(Error, Debug)]
pub enum InstrumentationError {
    #[error("Parser error: {0}")]
    ParserError(String),

    #[error("Language not supported: {0}")]
    UnsupportedLanguage(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Tree-sitter error: {0}")]
    TreeSitterError(#[from] tree_sitter::Error),
} 