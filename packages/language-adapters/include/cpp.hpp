#pragma once

#include "tree_sitter_adapter.hpp"
#include <tree_sitter/api.h>

// Forward declaration of tree-sitter-cpp language function
extern "C" const TSLanguage *tree_sitter_cpp();

namespace codegreen {

/// C++ language adapter using tree-sitter
class CppAdapter : public TreeSitterAdapter {
public:
    CppAdapter();
    ~CppAdapter() override = default;

    /// Get the language ID
    std::string get_language_id() const override;

    /// Get supported file extensions
    std::vector<std::string> get_file_extensions() const override;

    /// Instrument C++ code with energy measurement calls
    std::string instrument_code(const std::string& source_code, 
                               const std::vector<CodeCheckpoint>& checkpoints) override;

    /// Analyze C++ code for energy optimization opportunities
    bool analyze(const std::string& source_code) override;

    /// Get optimization suggestions specific to C++
    std::vector<std::string> get_suggestions() const override;

protected:
    /// Override to handle C++-specific node types
    bool should_generate_checkpoint(const std::string& node_type) const override;

    /// Extract function/method/class names from C++ AST nodes
    std::string extract_function_name(TSNode node, const std::string& source_code) const override;

    /// Generate C++-specific checkpoints
    std::vector<CodeCheckpoint> generate_node_checkpoints(
        TSNode node, 
        const std::string& source_code,
        const std::string& node_type
    ) override;

private:
    std::vector<std::string> optimization_suggestions_;

    /// Helper methods for C++ code instrumentation
    std::string generate_measurement_include() const;
    std::string generate_checkpoint_call(const CodeCheckpoint& checkpoint) const;
    std::vector<std::string> split_lines(const std::string& source_code) const;
    std::string join_lines(const std::vector<std::string>& lines) const;
    std::string get_indentation(const std::string& line) const;

    /// Analyze specific C++ patterns for energy optimization
    void analyze_loops(const std::string& source_code);
    void analyze_memory_usage(const std::string& source_code);
    void analyze_templates(const std::string& source_code);
    void analyze_containers(const std::string& source_code);
};

} // namespace codegreen