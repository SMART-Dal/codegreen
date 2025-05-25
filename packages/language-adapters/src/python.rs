use tree_sitter::Language;
use crate::LanguageAdapter;

extern "C" {
    fn tree_sitter_python() -> Language;
}

/// Python language adapter implementation
pub struct PythonAdapter;

impl PythonAdapter {
    pub fn new() -> Self {
        PythonAdapter
    }
}

impl LanguageAdapter for PythonAdapter {
    fn get_language_id(&self) -> &'static str {
        "python"
    }

    fn get_grammar(&self) -> Language {
        unsafe { tree_sitter_python() }
    }

    fn get_function_query(&self) -> &'static str {
        r#"
        (function_definition
            name: (identifier) @function.name
            parameters: (parameters) @function.params
            body: (block) @function.body
        )
        "#
    }

    fn get_class_query(&self) -> &'static str {
        r#"
        (class_definition
            name: (identifier) @class.name
            body: (block) @class.body
        )
        "#
    }

    fn get_import_query(&self) -> &'static str {
        r#"
        (import_statement) @import
        (import_from_statement) @import.from
        "#
    }
} 