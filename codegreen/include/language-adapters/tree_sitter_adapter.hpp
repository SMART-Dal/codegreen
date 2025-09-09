#pragma once

#include "adapters/language_adapter.hpp"
#include <tree_sitter/api.h>
#include <memory>
#include <unordered_map>
#include <functional>

namespace codegreen {

/// Base class for tree-sitter based language adapters
class TreeSitterAdapter : public LanguageAdapter {
public:
    explicit TreeSitterAdapter(const TSLanguage* language);
    virtual ~TreeSitterAdapter();

    /// Parse source code using tree-sitter and return language-agnostic AST
    std::unique_ptr<ASTNode> parse(const std::string& source_code) override;

    /// Generate energy measurement checkpoints from source code
    std::vector<CodeCheckpoint> generate_checkpoints(const std::string& source_code) override;

protected:
    /// Convert tree-sitter node to language-agnostic AST node
    virtual std::unique_ptr<ASTNode> convert_node(TSNode node, const std::string& source_code);

    /// Generate checkpoints for a specific node type
    virtual std::vector<CodeCheckpoint> generate_node_checkpoints(
        TSNode node, 
        const std::string& source_code,
        const std::string& node_type
    );

    /// Get node type name from tree-sitter node
    std::string get_node_type(TSNode node) const;

    /// Get node text from source code
    std::string get_node_text(TSNode node, const std::string& source_code) const;

    /// Check if node type should generate checkpoints
    virtual bool should_generate_checkpoint(const std::string& node_type) const;
    
    /// Check if checkpoint should be generated with adaptive spacing
    virtual bool should_generate_checkpoint_adaptive(const std::string& node_type, 
                                                   TSNode node, 
                                                   const std::string& source_code) const;

    /// Get function/method name from node
    virtual std::string extract_function_name(TSNode node, const std::string& source_code) const;

    /// Generate unique checkpoint ID
    std::string generate_checkpoint_id(const std::string& type, const std::string& name, size_t line) const;

    /// Check if checkpoint insertion should be skipped for a line
    virtual bool should_skip_checkpoint_insertion(const std::string& line, 
                                                const std::vector<std::string>& lines, 
                                                size_t line_index) const;
    
    /// Smart filtering to avoid trivial checkpoints
    virtual bool is_trivial_operation(const std::string& node_type, TSNode node, 
                                     const std::string& source_code) const;
    
    /// Check if checkpoint would be redundant with nearby checkpoints
    virtual bool is_checkpoint_redundant(const std::string& node_type, TSNode node,
                                        const std::vector<CodeCheckpoint>& existing_checkpoints) const;
    
    /// Estimate execution time for a node (for adaptive checkpoint generation)
    virtual double estimate_node_execution_time(TSNode node, const std::string& node_type, 
                                               const std::string& source_code) const;

private:
    TSParser* parser_;
    TSTree* tree_;
    const TSLanguage* language_;
    
    // Adaptive checkpoint configuration - optimized for accuracy
    static constexpr double MIN_MEASURABLE_TIME_MS = 5.0;   // 5 milliseconds - avoid noise
    static constexpr double NOISE_THRESHOLD_MS = 10.0;     // 10 milliseconds - meaningful operations
    static constexpr size_t MAX_CHECKPOINTS_PER_FUNCTION = 20;  // Reduce checkpoint spam
    
    // Smart filtering configuration
    static constexpr double TRIVIAL_OPERATION_THRESHOLD_MS = 1.0;  // Skip trivial ops
    static constexpr size_t MIN_NODE_SIZE_FOR_CHECKPOINT = 10;     // Minimum characters
    
    /// Recursive helper for AST conversion
    void convert_children(TSNode node, ASTNode* ast_node, const std::string& source_code);
    
    /// Recursive helper for checkpoint generation
    void traverse_for_checkpoints(
        TSNode node, 
        const std::string& source_code, 
        std::vector<CodeCheckpoint>& checkpoints,
        int depth = 0
    );
};

} // namespace codegreen