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