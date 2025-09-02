#pragma once

#include "tree_sitter_adapter.hpp"
#include <tree_sitter/api.h>

// Forward declaration of tree-sitter-java language function
extern "C" const TSLanguage *tree_sitter_java();

namespace codegreen {

/// Java language adapter using tree-sitter
class JavaAdapter : public TreeSitterAdapter {
public:
    JavaAdapter();
    ~JavaAdapter() override = default;

    /// Get the language ID
    std::string get_language_id() const override;

    /// Get supported file extensions
    std::vector<std::string> get_file_extensions() const override;

    /// Instrument Java code with energy measurement calls
    std::string instrument_code(const std::string& source_code, 
                               const std::vector<CodeCheckpoint>& checkpoints) override;

    /// Analyze Java code for energy optimization opportunities
    bool analyze(const std::string& source_code) override;

    /// Get optimization suggestions specific to Java
    std::vector<std::string> get_suggestions() const override;

protected:
    /// Override to handle Java-specific node types
    bool should_generate_checkpoint(const std::string& node_type) const override;

    /// Extract function/method/class names from Java AST nodes
    std::string extract_function_name(TSNode node, const std::string& source_code) const override;

    /// Generate Java-specific checkpoints
    std::vector<CodeCheckpoint> generate_node_checkpoints(
        TSNode node, 
        const std::string& source_code,
        const std::string& node_type
    ) override;

private:
    std::vector<std::string> optimization_suggestions_;

    /// Helper methods for Java code instrumentation
    std::string generate_measurement_import() const;
    std::string generate_checkpoint_call(const CodeCheckpoint& checkpoint) const;
    std::vector<std::string> split_lines(const std::string& source_code) const;
    std::string join_lines(const std::vector<std::string>& lines) const;
    std::string get_indentation(const std::string& line) const;

    /// Analyze specific Java patterns for energy optimization
    void analyze_collections(const std::string& source_code);
    void analyze_string_operations(const std::string& source_code);
    void analyze_loops(const std::string& source_code);
    void analyze_memory_usage(const std::string& source_code);
};

} // namespace codegreen
