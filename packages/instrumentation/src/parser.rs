use crate::{InstrumentationError, Language, Result};
use tree_sitter::{Parser as TreeSitterParser, Query, QueryCursor};

/// Parser for different programming languages
pub struct Parser {
    parser: TreeSitterParser,
}

impl Parser {
    /// Create a new parser for the given language
    pub fn new(language: Language) -> Result<Self> {
        let mut parser = TreeSitterParser::new();
        
        // Set the language
        let language = match language {
            Language::Python => tree_sitter_python::language(),
            Language::JavaScript => tree_sitter_javascript::language(),
            Language::Rust => tree_sitter_rust::language(),
        };
        
        parser.set_language(language).map_err(InstrumentationError::TreeSitterError)?;
        
        Ok(Self { parser })
    }

    /// Parse source code
    pub fn parse(&mut self, source: &str) -> Result<tree_sitter::Tree> {
        self.parser
            .parse(source, None)
            .ok_or_else(|| InstrumentationError::ParserError("Failed to parse source code".into()))
    }

    /// Get the parser
    pub fn parser(&self) -> &TreeSitterParser {
        &self.parser
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parser_creation() {
        let parser = Parser::new(Language::Python).unwrap();
        assert!(parser.parser().language().is_some());
    }

    #[test]
    fn test_parse_python() {
        let mut parser = Parser::new(Language::Python).unwrap();
        let source = "def hello(): pass";
        let tree = parser.parse(source).unwrap();
        assert!(!tree.root_node().has_error());
    }
} 