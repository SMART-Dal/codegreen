use tree_sitter::{Parser, Language};
use crate::error::InstrumentationError;

/// Parser for different programming languages
pub struct InstrumentationParser {
    parser: Parser,
}

impl InstrumentationParser {
    /// Create a new parser
    pub fn new() -> Self {
        Self {
            parser: Parser::new(),
        }
    }

    /// Set the language for the parser
    pub fn set_language(&mut self, language: Language) -> Result<(), InstrumentationError> {
        self.parser.set_language(language)
            .map_err(|e| InstrumentationError::TreeSitterError(e.to_string()))?;
        Ok(())
    }

    /// Parse source code
    pub fn parse(&mut self, source: &str) -> Result<tree_sitter::Tree, InstrumentationError> {
        self.parser.parse(source, None)
            .ok_or_else(|| InstrumentationError::ParserError("Failed to parse source code".to_string()))
    }

    /// Get the parser
    pub fn parser(&self) -> &Parser {
        &self.parser
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parser_creation() {
        let parser = InstrumentationParser::new();
        assert!(parser.parser().language().is_none());
    }

    #[test]
    fn test_parse_python() {
        let mut parser = InstrumentationParser::new();
        let language = tree_sitter_python::language();
        parser.set_language(language).unwrap();
        let source = "def hello(): pass";
        let tree = parser.parse(source).unwrap();
        assert!(!tree.root_node().has_error());
    }
} 