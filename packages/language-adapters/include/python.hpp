#pragma once

#include "tree_sitter_adapter.hpp"
#include <tree_sitter/api.h>

// Forward declaration of tree-sitter-python language function
extern "C" const TSLanguage *tree_sitter_python();

namespace codegreen {

/// Python language adapter using tree-sitter
class PythonAdapter : public TreeSitterAdapter {
public:
    PythonAdapter();
    ~PythonAdapter() override = default;

    /// Get the language ID
    std::string get_language_id() const override;

    /// Get supported file extensions
    std::vector<std::string> get_file_extensions() const override;

    /// Instrument Python code with energy measurement calls
    std::string instrument_code(const std::string& source_code, 
                               const std::vector<CodeCheckpoint>& checkpoints) override;

    /// Analyze Python code for energy optimization opportunities
    bool analyze(const std::string& source_code) override;

    /// Get optimization suggestions specific to Python
    std::vector<std::string> get_suggestions() const override;

protected:
    /// Override to handle Python-specific node types
    bool should_generate_checkpoint(const std::string& node_type) const override;

    /// Extract function/method names from Python AST nodes
    std::string extract_function_name(TSNode node, const std::string& source_code) const override;

    /// Check if checkpoint insertion should be skipped for a line
    bool should_skip_checkpoint_insertion(const std::string& line, 
                                        const std::vector<std::string>& lines, 
                                        size_t line_index) const override;

    /// Generate Python-specific checkpoints
    std::vector<CodeCheckpoint> generate_node_checkpoints(
        TSNode node, 
        const std::string& source_code,
        const std::string& node_type
    ) override;

private:
    std::vector<std::string> optimization_suggestions_;

    /// Helper methods for Python code instrumentation
    std::string generate_measurement_import() const;
    std::string generate_checkpoint_call(const CodeCheckpoint& checkpoint) const;
    std::vector<std::string> split_lines(const std::string& source_code) const;
    std::string join_lines(const std::vector<std::string>& lines) const;
    std::string get_indentation(const std::string& line) const;

    /// Analyze specific Python patterns for energy optimization
    void analyze_list_comprehensions(const std::string& source_code);
    void analyze_loops(const std::string& source_code);
    void analyze_imports(const std::string& source_code);
    void analyze_string_operations(const std::string& source_code);
};

} // namespace codegreen
